"""
circuit_breaker.py — 好奇熔断器
=====================================

来源：Raven Agent max_retry=3
定位：防止无限重试，保护系统资源

核心逻辑：
  同一 prediction_id 连续 N 次失败 → 状态转为 ARCHIVED_UNSOLVED
  冻结后不再触发主动好奇，仅保留元数据供后续批量分析

状态定义：
  ACTIVE      = 活跃，可触发好奇脉冲
  RETRYING    = 重试中（1-2次失败）
  FROZEN      = 已冻结（连续3次失败）
  RESOLVED    = 已解决（conf_delta > 0.1 或 error < 0.3）

参数：
  MAX_RETRY = 3（连续失败阈值）
  ERROR_THRESHOLD = 0.3（失败判定：error > 此值 且 conf_delta < 0.05）
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import file_lock as flock

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
TZ = timezone(timedelta(hours=8))

# ─── 常量 ────────────────────────────────────────────────────

MAX_RETRY = 3
ERROR_THRESHOLD = 0.3
CONF_DELTA_THRESHOLD = 0.05

PRED_PATH = os.path.join(MEM, "curiosity_prediction.json")
EVENT_PATH = os.path.join(MEM, "curiosity_events.jsonl")
BREAKER_STATE_PATH = os.path.join(MEM, "curiosity_breaker_state.json")


class BreakerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETRYING = "RETRYING"
    FROZEN = "FROZEN"
    RESOLVED = "RESOLVED"


# ─── 熔断状态管理 ──────────────────────────────────────────────

def load_breaker_state() -> Dict:
    """加载熔断状态。"""
    return flock.safe_read_json(BREAKER_STATE_PATH, {
        "predictions": {},  # prediction_id -> {status, retry_count, last_error, frozen_at}
        "stats": {
            "total_frozen": 0,
            "total_resolved": 0,
        }
    })


def save_breaker_state(state: Dict):
    """保存熔断状态。"""
    with flock.FileLock(BREAKER_STATE_PATH):
        flock.atomic_write_json(BREAKER_STATE_PATH, state)


def get_prediction_status(prediction_id: str) -> Dict:
    """获取单个预测的熔断状态。"""
    state = load_breaker_state()
    return state.get("predictions", {}).get(prediction_id, {
        "status": BreakerStatus.ACTIVE.value,
        "retry_count": 0,
        "last_error": 0.0,
        "last_conf_delta": 0.0,
        "frozen_at": None,
    })


def should_skip_prediction(prediction_id: str) -> bool:
    """判断是否应跳过该预测（已冻结）。"""
    info = get_prediction_status(prediction_id)
    return info.get("status") == BreakerStatus.FROZEN.value


# ─── 熔断检查核心 ──────────────────────────────────────────────

def check_and_update(prediction_id: str, error_score: float, conf_delta: float) -> Dict:
    """
    检查并更新熔断状态。

    返回：{
        "status": 新状态,
        "retry_count": 当前重试次数,
        "should_freeze": 是否应冻结,
        "action": "continue" | "freeze" | "resolve"
    }
    """
    state = load_breaker_state()

    # 初始化或获取现有记录
    if prediction_id not in state["predictions"]:
        state["predictions"][prediction_id] = {
            "status": BreakerStatus.ACTIVE.value,
            "retry_count": 0,
            "last_error": 0.0,
            "last_conf_delta": 0.0,
            "frozen_at": None,
            "created_at": datetime.now(TZ).isoformat(),
        }

    pred_state = state["predictions"][prediction_id]
    current_status = pred_state["status"]

    # 已冻结或已解决 → 不再更新
    if current_status in [BreakerStatus.FROZEN.value, BreakerStatus.RESOLVED.value]:
        return {
            "status": current_status,
            "retry_count": pred_state["retry_count"],
            "should_freeze": current_status == BreakerStatus.FROZEN.value,
            "action": "none",
        }

    # 判断本次是否失败
    is_failure = (error_score > ERROR_THRESHOLD and abs(conf_delta) < CONF_DELTA_THRESHOLD)

    if is_failure:
        # 失败：增加重试计数
        pred_state["retry_count"] += 1
        pred_state["last_error"] = error_score
        pred_state["last_conf_delta"] = conf_delta

        if pred_state["retry_count"] >= MAX_RETRY:
            # 达到阈值 → 冻结
            pred_state["status"] = BreakerStatus.FROZEN.value
            pred_state["frozen_at"] = datetime.now(TZ).isoformat()
            state["stats"]["total_frozen"] += 1
            action = "freeze"
            should_freeze = True
        else:
            # 还在重试中
            pred_state["status"] = BreakerStatus.RETRYING.value
            action = "continue"
            should_freeze = False
    else:
        # 成功：解决
        pred_state["status"] = BreakerStatus.RESOLVED.value
        pred_state["resolved_at"] = datetime.now(TZ).isoformat()
        state["stats"]["total_resolved"] += 1
        action = "resolve"
        should_freeze = False

    save_breaker_state(state)

    return {
        "status": pred_state["status"],
        "retry_count": pred_state["retry_count"],
        "should_freeze": should_freeze,
        "action": action,
        "last_error": error_score,
        "last_conf_delta": conf_delta,
    }


# ─── 批量历史修复 ──────────────────────────────────────────────

def backfill_from_events() -> Dict:
    """
    从现有 curiosity_events.jsonl 回填熔断状态。
    用于首次启用熔断器时修复历史数据。
    """
    if not os.path.exists(EVENT_PATH):
        return {"backfilled": 0, "reason": "no events file"}

    events = []
    with open(EVENT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

    if not events:
        return {"backfilled": 0, "reason": "empty events"}

    # 按 prediction_id 分组
    by_pred: Dict[str, List[Dict]] = {}
    for e in events:
        pid = e.get("prediction_id", "")
        if pid:
            if pid not in by_pred:
                by_pred[pid] = []
            by_pred[pid].append(e)

    state = load_breaker_state()
    backfilled = 0

    for prediction_id, evts in by_pred.items():
        if prediction_id in state["predictions"]:
            continue  # 已有记录

        # 统计失败次数
        failures = 0
        last_error = 0.0
        last_conf_delta = 0.0

        for e in evts:
            err = e.get("error_score", 0)
            conf = e.get("confidence_delta", 0)
            if err > ERROR_THRESHOLD and abs(conf) < CONF_DELTA_THRESHOLD:
                failures += 1
                last_error = err
                last_conf_delta = conf

        # 回填状态
        if failures >= MAX_RETRY:
            status = BreakerStatus.FROZEN.value
            state["stats"]["total_frozen"] += 1
            frozen_at = evts[-1].get("timestamp", "")
        elif failures > 0:
            status = BreakerStatus.RETRYING.value
            frozen_at = None
        else:
            status = BreakerStatus.ACTIVE.value
            frozen_at = None

        state["predictions"][prediction_id] = {
            "status": status,
            "retry_count": failures,
            "last_error": last_error,
            "last_conf_delta": last_conf_delta,
            "frozen_at": frozen_at,
            "backfilled": True,
        }
        backfilled += 1

    save_breaker_state(state)

    return {
        "backfilled": backfilled,
        "total_predictions": len(by_pred),
        "frozen": sum(1 for p in state["predictions"].values() if p["status"] == BreakerStatus.FROZEN.value),
    }


# ─── 统计报告 ──────────────────────────────────────────────────

def get_breaker_stats() -> Dict:
    """获取熔断器统计。"""
    state = load_breaker_state()
    predictions = state.get("predictions", {})

    by_status = {}
    for p in predictions.values():
        st = p.get("status", "UNKNOWN")
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "total_predictions": len(predictions),
        "by_status": by_status,
        "stats": state.get("stats", {}),
        "frozen_predictions": [
            {"id": pid, "retry_count": p["retry_count"], "frozen_at": p.get("frozen_at")}
            for pid, p in predictions.items()
            if p.get("status") == BreakerStatus.FROZEN.value
        ],
    }


# ─── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="好奇熔断器")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--backfill", action="store_true", help="从历史事件回填")
    parser.add_argument("--check", type=str, help="检查指定 prediction_id")

    args = parser.parse_args()

    if args.stats:
        stats = get_breaker_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.backfill:
        result = backfill_from_events()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.check:
        info = get_prediction_status(args.check)
        print(json.dumps(info, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
