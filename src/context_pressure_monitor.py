#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
context_pressure_monitor.py
TU-8 内感受皮层 · 上下文压力监测器

功能：
  - 读取 memory/context_control.json
  - 判断 posture_zone
  - 更新 heartbeat_state.json 中的上下文压力状态
  - 记录连续 critical 次数（用于"首轮警告+二轮兜底"逻辑）

用法：
  python src/context_pressure_monitor.py
  → 输出 JSON 到 _agent_memory/heartbeat_state.json
"""

import json
import sys
from pathlib import Path

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
CONTEXT_CTRL = WORKSPACE / "memory" / "context_control.json"
HEARTBEAT_STATE = WORKSPACE / "_agent_memory" / "heartbeat_state.json"

# 阈值
CONTEXT_WARN_THRESHOLD = 0.8   # context_load_pct ≥ 0.8 → 警告
CONTEXT_CRITICAL_POSTURES = ["critical"]
CONTEXT_WARN_POSTURES = ["warning", "elevated"]


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_heartbeat_state() -> dict:
    """读取心跳状态，缺失则返回默认结构"""
    default = {
        "context_pressure": {
            "posture_zone": "unknown",
            "load_pct": None,
            "critical_count": 0,
            "first_warning_shown": False,
            "warning_issued_at": None,
            "last_check": None,
        },
        "lastChecks": {}
    }
    data = load_json(HEARTBEAT_STATE)
    if data is None:
        return default
    if "context_pressure" not in data:
        data["context_pressure"] = default["context_pressure"]
    return data


def save_heartbeat_state(state: dict):
    save_json(HEARTBEAT_STATE, state)


def run() -> dict:
    """执行检测，返回当前压力状态"""
    import time
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    ctrl = load_json(CONTEXT_CTRL)
    state = load_heartbeat_state()
    cp = state.setdefault("context_pressure", {})

    result = {
        "posture_zone": "unknown",
        "load_pct": None,
        "action": "none",
        "message": None,
    }

    if ctrl is None:
        cp["posture_zone"] = "no_data"
        cp["last_check"] = now_iso
        save_heartbeat_state(state)
        return result

    posture = ctrl.get("posture_zone", "unknown")
    load_pct = ctrl.get("context_load_pct")
    critical_count = cp.get("critical_count", 0)
    first_warning_shown = cp.get("first_warning_shown", False)

    # 更新状态
    cp["posture_zone"] = posture
    cp["load_pct"] = load_pct
    cp["last_check"] = now_iso

    if posture in CONTEXT_CRITICAL_POSTURES:
        critical_count += 1
        cp["critical_count"] = critical_count

        if critical_count == 1:
            # 首次检测到 critical → 记录警告已发出
            cp["first_warning_shown"] = True
            cp["warning_issued_at"] = now_iso
            result["action"] = "warn_user"
            result["message"] = (
                f"⚠️ 上下文趋近上限（posture={posture}，load={load_pct}）。"
                "建议输入「压缩」清理上下文继续工作。"
            )
        elif critical_count >= 2 and not first_warning_shown:
            # 回跳后再次 critical（二轮兜底）
            cp["first_warning_shown"] = True
            cp["warning_issued_at"] = now_iso
            result["action"] = "second_warn"
            result["message"] = (
                "⚠️ 上下文压力持续（critical 连续第 2 次检测）。"
                "请输入「压缩」继续，否则下轮继续提醒。"
            )
        else:
            # 已在警告状态，等待用户触发
            result["action"] = "await_user"
            result["message"] = (
                "⏳ 上下文压力持续中，等待造物主触发压缩。"
            )
    else:
        # posture 缓解 → 重置计数器
        if critical_count > 0:
            cp["critical_count"] = 0
            cp["first_warning_shown"] = False
            cp["warning_issued_at"] = None
            result["action"] = "reset"
            result["message"] = "✅ 上下文压力已缓解，计数器重置。"

    cp["last_check"] = now_iso
    result["posture_zone"] = posture
    result["load_pct"] = load_pct

    save_heartbeat_state(state)

    # 打印诊断
    print(f"[context_pressure] posture={posture} load={load_pct} "
          f"critical_count={critical_count} action={result['action']}")
    if result["message"]:
        print(result["message"])

    return result


if __name__ == "__main__":
    result = run()
    # 输出完整结果 JSON（供调用方解析）
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)
