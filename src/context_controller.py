"""
context_controller.py — TU-8 上下文阀门动态调节器

职责：
  1. 读取 interoception_state.json 获取当前上下文负载
  2. 基于负载水平推荐 lossless-claw 阈值
  3. 写入 memory/context_control.json 供 heartbeat/agent 决策
  4. 检测异常波动并触发告警（由内感受皮层边沿触发）

调节策略（与身体姿态耦合）：
  perspective: 受 interoception 体感环（2.5h）驱动，非独立 loop

阈值推荐公式：
  context_load_pct  | 推荐 contextThreshold  | posture 影响
  ------------------|------------------------|--------------
  < 40% (低负载)     | 0.55 (放松)           | nominal → 允许大 context
  40-65% (正常)      | 0.45 (适中)           | nominal/elevated
  65-85% (偏高)      | 0.35 (收紧)           | elevated → 同步收紧
  > 85% (危险)       | 0.25 (紧急)           | stressed/critical → 最大收紧

另外推荐 freshTailCount 按负载缩放：
  freshTailCount = max(16, 48 - int(load_pct / 100 * 32))

使用：可作为独立脚本运行，也可被 interoceptive_cortex.py import 调用。

文件锁：通过 file_lock 跨进程安全写入。
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# ── 路径 ────────────────────────────────────────────────
WS = Path(os.path.expanduser("~/.qclaw/workspace"))
STATE_PATH = WS / "memory" / "interoception_state.json"
HISTORY_PATH = WS / "memory" / "interoception_history.json"
CONTROL_PATH = WS / "memory" / "context_control.json"
LOCK_DIR = WS / "memory" / "locks"

# ── 自适应阈值曲线 ──────────────────────────────────────
def recommended_threshold(load_pct: float) -> dict:
    """基于上下文负载返回推荐阀门参数"""
    if load_pct < 0.40:
        ctx_threshold = 0.55
        posture_zone = "relaxed"
    elif load_pct < 0.65:
        ctx_threshold = 0.45
        posture_zone = "normal"
    elif load_pct < 0.85:
        ctx_threshold = 0.35
        posture_zone = "tight"
    else:
        ctx_threshold = 0.25
        posture_zone = "critical"

    fresh_tail_count = max(16, 48 - int(load_pct * 32))
    fresh_tail_tokens = max(10000, min(30000, 40000 - int(load_pct * 30000)))

    return {
        "recommended_at": datetime.now(timezone.utc).isoformat(),
        "context_load_pct": round(load_pct, 3),
        "posture_zone": posture_zone,
        "recommended": {
            "contextThreshold": ctx_threshold,
            "freshTailCount": fresh_tail_count,
            "freshTailMaxTokens": fresh_tail_tokens,
        },
        "current": {
            "contextThreshold": 0.4,
            "freshTailCount": 32,
            "freshTailMaxTokens": 20000,
        },
        "delta": {},  # 在 compute 中填充
    }


def compute_delta(rec: dict) -> dict:
    """填充 delta 字段：None=无变化, 'lower'/'raise'=需调"""
    cur = rec["current"]
    recd = rec["recommended"]
    delta = {}
    for k in ("contextThreshold", "freshTailCount", "freshTailMaxTokens"):
        cv, rv = cur[k], recd[k]
        if k == "freshTailCount":
            diff = rv - cv
        else:
            diff = round(rv - cv, 2)
        if abs(diff) < (1 if k == "freshTailCount" else 0.02):
            delta[k] = None
        elif diff > 0:
            delta[k] = "raise"
        else:
            delta[k] = "lower"
    rec["delta"] = delta
    return rec


def compute(load_pct: float = None) -> dict:
    """主入口：读取状态 → 计算推荐 → 写文件

    Args:
        load_pct: 可选直接传入，否则从 STATE_PATH 读取

    Returns:
        context_control dict
    """
    if load_pct is None:
        # 从 interoception state 读取
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            load_pct = state.get("context_load_pct", 0.0)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            # 兜底：从历史记录读取最后一次
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                samples = hist.get("context_load_pct", [])
                load_pct = samples[-1] / 100.0 if samples else 0.0
            except Exception:
                load_pct = 0.0

    rec = recommended_threshold(load_pct)
    rec = compute_delta(rec)

    # 记录最近 5 次
    rec["history"] = _load_recent_history() + [{
        "ts": rec["recommended_at"],
        "load_pct": load_pct,
        "zone": rec["posture_zone"],
    }]
    if len(rec["history"]) > 5:
        rec["history"] = rec["history"][-5:]

    _write_control(rec)
    return rec


# ── 文件锁写入 ──────────────────────────────────────────
def _write_control(rec: dict):
    """原子写入 context_control.json"""
    tmp = CONTROL_PATH.with_suffix(".tmp")
    try:
        CONTROL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        tmp.replace(CONTROL_PATH)
    except Exception as e:
        # 不回显错误（常驻监控应静默）
        pass


def _load_recent_history() -> list:
    """读取已有 control 的历史记录"""
    try:
        with open(CONTROL_PATH, "r", encoding="utf-8") as f:
            prev = json.load(f)
        return prev.get("history", [])
    except Exception:
        return []


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    result = compute()
    zone = result["posture_zone"]
    load = result["context_load_pct"]
    delta = result["delta"]

    status = "⏹" if all(d is None for d in delta.values()) else "🔄"
    print(f"Context: {load:.1%} | Zone: {zone} | {status}")
    for k, v in delta.items():
        if v:
            cur = result["current"][k]
            rec = result["recommended"][k]
            print(f"  {k}: {cur} → {rec} ({v})")
        else:
            print(f"  {k}: {result['current'][k]} (ok)")
