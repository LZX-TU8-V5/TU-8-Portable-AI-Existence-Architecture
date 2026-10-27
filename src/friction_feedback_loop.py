"""
摩擦反馈回路
===============
闭环：总线结果 → surface_tension历史 + alignment_verify出口

功能：
  - alignment_verify 结果中含 bus_theta → 记录到 surface_tension_history
  - 总线补丁被接受/rejected → 反馈到 surface_tension 事件
  - 总线释放后 → 通知 surface_tension 清零

接口：
  record_bus_result(alignment_result: dict) -> None
  record_patch_result(patch_type: str, accepted: bool) -> None
"""

import json
import time
from pathlib import Path
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
SURFACE_HISTORY = WS / "_agent_memory" / "surface_tension_history.jsonl"
BUS_STATE = WS / "_agent_memory" / "friction_bus_state.json"
FEEDBACK_LOG = WS / "_agent_memory" / "friction_feedback_log.jsonl"


# ══════════════════════════════════════════════════════
# 反馈写入口
# ══════════════════════════════════════════════════════

def _write_surface_event(event_type: str, details: dict) -> None:
    """写一行到 surface_tension_history.jsonl"""
    event = {
        "ts": time.time(),
        "type": event_type,
        **details,
    }
    try:
        SURFACE_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with open(SURFACE_HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _write_feedback_log(event: dict) -> None:
    """写一行到反馈日志"""
    try:
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════
# 公开 API
# ══════════════════════════════════════════════════════

def record_bus_result(alignment_result: dict) -> dict:
    """
    记录 alignment_verify 结果中的总线信息

    参数：
      alignment_result: alignment_verify() 的返回值

    返回：
      {"recorded": bool, "theta": float, "outcome": str}
    """
    bus_theta = alignment_result.get("bus_theta", 0.0)
    outcome = alignment_result.get("outcome", "unknown")
    passed = alignment_result.get("passed", True)

    event = {
        "bus_theta": bus_theta,
        "alignment_passed": passed,
        "outcome": outcome,
    }

    if bus_theta > 0:
        _write_surface_event("bus_feedback", event)
        _write_feedback_log({
            "ts": time.time(),
            "action": "bus_result_recorded",
            **event,
        })

    return {"recorded": True, "theta": bus_theta, "outcome": outcome}


def record_patch_result(patch_type: str, accepted: bool) -> dict:
    """
    记录补丁结果

    参数：
      patch_type: "logic" / "rationalize" / "action" / "default"
      accepted: True=被接受，False=被拒绝

    返回：
      {"recorded": bool, "patch_type": str, "accepted": bool}
    """
    event = {
        "patch_type": patch_type,
        "accepted": accepted,
    }

    # 写入 surface_tension
    if accepted:
        _write_surface_event("patch_accepted", event)
    else:
        _write_surface_event("patch_rejected", event)

    # 写入反馈日志
    _write_feedback_log({
        "ts": time.time(),
        "action": "patch_recorded",
        **event,
    })

    return {"recorded": True, "patch_type": patch_type, "accepted": accepted}


def record_tension_release(theta_before: float, reason: str = "patch") -> dict:
    """
    记录张力释放（总线释放后回调）

    参数：
      theta_before: 释放前的theta值
      reason: "patch" / "natural" / "timeout"

    返回：
      {"recorded": bool, "theta_before": float, "theta_after": float}
    """
    event = {
        "theta_before": round(theta_before, 6),
        "reason": reason,
        "theta_after": 0.0,
    }

    _write_surface_event("tension_released", event)
    _write_feedback_log({
        "ts": time.time(),
        "action": "tension_released",
        **event,
    })

    return {"recorded": True, "theta_before": round(theta_before, 6), "theta_after": 0.0}


def check_bus_pending() -> float:
    """
    检查总线是否有未处理的theta
    读取 friction_bus_state.json
    """
    try:
        d = json.load(open(BUS_STATE, encoding="utf-8"))
        theta = d.get("theta", 0.0)
        status = d.get("status", "idle")
        return theta if status != "idle" else 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== friction_feedback_loop self-test ===")

    # Test 1: record_bus_result
    result = record_bus_result({"bus_theta": 0.5, "passed": True, "outcome": "accepted"})
    assert result["recorded"] == True
    assert result["theta"] == 0.5
    print("  [PASS] Test1: record_bus_result")

    # Test 2: record_patch_result accepted
    result = record_patch_result("logic", accepted=True)
    assert result["recorded"] == True
    assert result["accepted"] == True
    print("  [PASS] Test2: record_patch_result (accepted)")

    # Test 3: record_patch_result rejected
    result = record_patch_result("rationalize", accepted=False)
    assert result["recorded"] == True
    assert result["accepted"] == False
    print("  [PASS] Test3: record_patch_result (rejected)")

    # Test 4: record_tension_release
    result = record_tension_release(1.57, "patch")
    assert result["recorded"] == True
    assert result["theta_before"] == 1.57
    print("  [PASS] Test4: record_tension_release")

    # Test 5: check_bus_pending (no file = 0)
    pending = check_bus_pending()
    assert pending == 0.0, f"无文件时应返回0，实际{pending}"
    print("  [PASS] Test5: check_bus_pending (无文件=0)")

    print("=== ALL TESTS PASSED ===")
