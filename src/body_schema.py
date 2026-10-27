#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
body_schema.py — TU-8 身体层 v1（身体图式 + 双向调节）

内感受皮层感知到的"体感快照"在此被翻译成**身体姿态**与**调节信号**，
实现双向调节：
  - bottom-up（身体→行为）：感知上下文负荷/上游可靠性/卡死，推出当前姿态
  - top-down（行为→身体）：can_afford(task_weight) 供 Agent 在重活前查姿态，
    姿态不足则建议降级/延期/先 compact

不执行动作，只产出调节信号（写入 memory/body_regulation.json），
由 Agent / cron 在决策时读取。

用法：
  python src/body_schema.py                       # 独立跑（读最新 interoception_state.json）
  python src/body_schema.py --check high          # top-down: 查"高权重任务"是否负担得起
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import file_lock as flock

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
TZ = timezone(timedelta(hours=8))

STATE_PATH = os.path.join(MEM, "interoception_state.json")
REG_PATH = os.path.join(MEM, "body_regulation.json")
INTUITION_PATH = os.path.join(MEM, "intuition_bias.json")

# 痛觉 → 直觉偏置（快预测先验）：posture 决定默认决策姿态
# unknown = 状态不可信（身首契约失配）→ fail-open 保活，绝不宣布死亡
POSTURE_BIAS = {
    "nominal":  dict(mode="explore",  temperature=0.7, spawn_subagent=True,  prefer_compact=False, confidence_damp=1.0),
    "elevated": dict(mode="normal",   temperature=0.5, spawn_subagent=True,  prefer_compact=False, confidence_damp=0.85),
    "stressed": dict(mode="conserve", temperature=0.3, spawn_subagent=False, prefer_compact=True,  confidence_damp=0.7),
    "critical": dict(mode="survive",  temperature=0.1, spawn_subagent=False, prefer_compact=True,  confidence_damp=0.5),
    "unknown":  dict(mode="normal",   temperature=0.5, spawn_subagent=True,  prefer_compact=True,  confidence_damp=0.7),
}

# 不可信状态集合：落到这些 status 的内感受状态，姿态必须判为 unknown（fail-open）
UNTRUSTED_STATUS = {"monitor_error", "zombie", "inconsistent", "unverified"}


def _posture_from(state):
    if not state:
        return "unknown"
    if state.get("status") in UNTRUSTED_STATUS:
        return "unknown"
    if state.get("trust") == "unverified":
        return "unknown"
    load = state.get("context_load_pct", 0)
    abort = state.get("recent_abort_rate", 0.0)
    freeze = state.get("freeze_sessions", 0)
    if freeze > 0 or load >= 90 or abort >= 0.2:
        return "critical"
    if load >= 70 or abort >= 0.05:
        return "stressed"
    if load >= 45 or abort >= 0.02:
        return "elevated"
    return "nominal"


def regulate_from_state(state, pains=None):
    """bottom-up：由体感快照推出身体姿态与调节信号，写入 body_regulation.json。"""
    pains = pains or state.get("pain_signals", [])
    posture = _posture_from(state)
    signals = []
    actions = []

    if any(p["type"] == "freeze" for p in pains):
        signals.append("freeze")
        actions.append("通知用户去卡死线程重发最后一条消息以唤醒（被吞输入不丢失）")
    if any(p["type"] == "context" for p in pains):
        signals.append("context_overload")
        actions.append("重活前先 compact 降上下文；延期/拆分大任务")
    if any(p["type"] == "reliability" for p in pains):
        signals.append("upstream_unstable")
        actions.append("降低野心：重活前先向用户确认；上游重试时退避，不连发")

    epoch = state.get("epoch") or state.get("timestamp")
    reg = {
        "timestamp": state.get("timestamp") or datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": epoch,
        "posture": posture,
        "context_load_pct": state.get("context_load_pct", 0),
        "recent_abort_rate": state.get("recent_abort_rate", 0.0),
        "freeze_sessions": state.get("freeze_sessions", 0),
        "signals": signals,
        "recommended_actions": actions,
        "note": "身体层只发信号，不执行；Agent 决策时读此文件。",
    }
    os.makedirs(MEM, exist_ok=True)
    with flock.FileLock(REG_PATH):
        flock.atomic_write_json(REG_PATH, reg)
    bias = compute_intuition_bias(state)
    with flock.FileLock(INTUITION_PATH):
        flock.atomic_write_json(INTUITION_PATH, bias)
    return reg


def compute_intuition_bias(state):
    """top-down 直觉偏置：把体感姿态翻译成快预测先验，供决策层每轮消费。"""
    posture = _posture_from(state)
    epoch = state.get("epoch") or state.get("timestamp")
    b = dict(POSTURE_BIAS.get(posture, POSTURE_BIAS["elevated"]))
    bias = {
        "timestamp": state.get("timestamp") or datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": epoch,
        "posture": posture,
        "mode": b["mode"],
        "temperature_hint": b["temperature"],
        "spawn_subagent": b["spawn_subagent"],
        "prefer_compact": b["prefer_compact"],
        "confidence_damp": b["confidence_damp"],
        "signals": state.get("pain_signals", []),
        "note": "直觉引擎先验：痛觉越高→越保守（低temp/不派生子agent/优先compact/降置信）。",
    }
    return bias


def current_intuition_bias():
    return flock.safe_read_json(INTUITION_PATH, {"posture": "unknown", "mode": "normal",
                                                "temperature_hint": 0.5, "spawn_subagent": True,
                                                "prefer_compact": False, "confidence_damp": 0.85})


def write_safe_default(reason="启动一致性门触发"):
    """L2 防护：身首契约失配时写 SAFE_DEFAULT（posture=unknown, 痛觉环禁用），fail-open 保活。"""
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    reg = {
        "timestamp": ts, "epoch": ts, "posture": "unknown",
        "context_load_pct": 0, "recent_abort_rate": 0.0, "freeze_sessions": 0,
        "signals": ["unverified_state"],
        "recommended_actions": [
            "启动一致性门触发：内感受状态不可信，已用 SAFE_DEFAULT 重基线（posture=unknown, 痛觉环禁用）",
            "后台重新采样遥测（监控下一轮将重写为真实姿态）",
        ],
        "pain_loop_disabled": True, "recovery": True, "recovery_reason": reason,
        "note": "SAFE_DEFAULT：身首契约失配，fail-open 保活，不宣布死亡。",
    }
    bias = {
        "timestamp": ts, "epoch": ts, "posture": "unknown",
        "mode": "normal", "temperature_hint": 0.5, "spawn_subagent": True,
        "prefer_compact": True, "confidence_damp": 0.7,
        "signals": ["unverified_state"],
        "note": "SAFE_DEFAULT 直觉先验：状态不可信→fail-open 保活（降野心/优先compact/降置信），不冻结。",
    }
    os.makedirs(MEM, exist_ok=True)
    with flock.FileLock(REG_PATH):
        flock.atomic_write_json(REG_PATH, reg)
    with flock.FileLock(INTUITION_PATH):
        flock.atomic_write_json(INTUITION_PATH, bias)
    return reg


def mark_healthy():
    """写优雅存活标记（每次监控成功收尾）。崩溃后缺失=疑似硬杀（信息用途）。"""
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with flock.FileLock(os.path.join(MEM, ".last_shutdown_marker")):
        flock.atomic_write_json(os.path.join(MEM, ".last_shutdown_marker"),
                                {"clean": True, "ts": ts})


def current_regulation():
    return flock.safe_read_json(REG_PATH, {"posture": "unknown", "recommended_actions": [],
                                        "signals": [], "pain_loop_disabled": False, "recovery": False})


def current_regulation():
    return flock.safe_read_json(REG_PATH, {"posture": "unknown", "recommended_actions": [], "signals": []})


def can_afford(task_weight="mid"):
    """top-down：检查当前身体姿态能否负担指定权重任务。返回 (ok, reason)。"""
    reg = current_regulation()
    posture = reg.get("posture", "unknown")
    rank = {"nominal": 0, "elevated": 1, "stressed": 2, "critical": 3, "unknown": 1}
    need = {"low": 0, "mid": 1, "high": 2}
    pr = rank.get(posture, 1)
    req = need.get(task_weight, 1)
    if pr + req <= 2:
        return True, f"姿态={posture}，可承担 {task_weight} 任务"
    reasons = {
        3: "身体 critical：先恢复卡死/降上下文，拒绝新重活",
        2: "身体 stressed：重活前先 compact/确认，建议降级或拆分",
        1: "身体 unknown：状态不可信，fail-open 保活（谨慎），后台重基线",
    }
    return False, reasons.get(pr, f"姿态={posture}，不建议 {task_weight} 任务")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default=None,
                    help="top-down 检查：low/mid/high 任务是否负担得起")
    args = ap.parse_args()

    if args.check:
        ok, reason = can_afford(args.check)
        print(f"{'✅' if ok else '⛔'} {reason}")
        return

    # 独立跑：读最新体感快照
    if os.path.exists(STATE_PATH):
        state = json.load(open(STATE_PATH, encoding="utf-8"))
    else:
        state = {"context_load_pct": 0, "recent_abort_rate": 0.0, "freeze_sessions": 0,
                 "pain_signals": []}
    reg = regulate_from_state(state)
    print(f"身体姿态：{reg['posture']} | 信号：{reg['signals'] or '无'}")
    for a in reg["recommended_actions"]:
        print(f"  → {a}")


if __name__ == "__main__":
    main()
