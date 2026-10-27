"""
摩擦代谢总线 — 欧拉相位角模型
===================================
数学框架：e^(iθ) = cosθ + i·sinθ
模长守恒：|e^(iθ)| = 1（系统永不崩溃的安全边界）

功能：
  θ 累加 → 欧拉旋转 → apply_patch() → θ=0 → 总线释放
  cosθ = 主意识参与度（实部）
  sinθ = 潜意识参与度（虚部）

接口：
  push_event(tension)  → θ 累加（旋转）
  apply_patch(patch)   → θ = 0（总线释放）
  get_state()          → 当前 theta / cosθ / sinθ
"""

import json
import time
import math
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
STATE_FILE = WS / "_agent_memory" / "friction_bus_state.json"
HISTORY_FILE = WS / "_agent_memory" / "friction_bus_history.jsonl"

# ── 阈值配置 ─────────────────────────────────────────
T_LOW = 0.3      # 低张力 → 直接归档
T_HIGH = 0.7     # 高张力 → 进入总线
T_BUS_ENTER = 0.7  # 总线入口阈值（与T_HIGH同值）
_SIN_ACUTE = 1e-10  # |e^iθ|-1 的数值误差容忍


# ══════════════════════════════════════════════════════
# 状态数据结构
# ══════════════════════════════════════════════════════

class BusStatus(Enum):
    IDLE = "idle"           # 总线空闲，无高张力事件
    ROTATING = "rotating"   # θ 旋转中（摩擦代谢）
    PATCH_APPLIED = "patch_applied"  # 补丁已施加，等待确认
    RELEASING = "releasing" # θ → 0，总线释放中


@dataclass
class FrictionBusState:
    theta: float = 0.0           # 相位角 θ ∈ [0, π]
    cos_theta: float = 1.0      # cosθ = 主意识参与度
    sin_theta: float = 0.0      # sinθ = 潜意识参与度
    status: str = BusStatus.IDLE.value
    current_patch: Optional[str] = None
    events_since_last_patch: int = 0
    total_rotations: int = 0     # 历史累计旋转次数
    last_updated: Optional[str] = None


# ══════════════════════════════════════════════════════
# 状态读写
# ══════════════════════════════════════════════════════

def _load_state() -> FrictionBusState:
    try:
        d = json.load(open(STATE_FILE, encoding="utf-8"))
        return FrictionBusState(**d)
    except Exception:
        return FrictionBusState()


def _save_state(state: FrictionBusState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state.last_updated = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    STATE_FILE.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _append_history(event: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ══════════════════════════════════════════════════════
# 核心算法
# ══════════════════════════════════════════════════════

def _rotate(theta: float, delta: float) -> float:
    """
    欧拉旋转：θ += delta
    限制在 [0, π] 区间（π = 最极端张力）
    """
    return max(0.0, min(math.pi, theta + delta))


def _decompose_theta(theta: float) -> tuple[float, float]:
    """
    张力三角函数分解（19号任务）
    返回 (cosθ, sinθ)

    cosθ = 主意识参与度（实部）
    sinθ = 潜意识参与度（虚部）
    """
    return math.cos(theta), math.sin(theta)


def _conservation_check(theta: float) -> bool:
    """
    结构守恒不变量监控
    |e^(iθ)| = sqrt(cos²θ + sin²θ) 必须 = 1
    数值误差容忍：< 1e-10
    """
    cos_t, sin_t = _decompose_theta(theta)
    norm = math.sqrt(cos_t**2 + sin_t**2)
    return abs(norm - 1.0) < _SIN_ACUTE


def _update_state(state: FrictionBusState, theta: float) -> FrictionBusState:
    """更新状态 + 数学校验"""
    cos_t, sin_t = _decompose_theta(theta)
    state.theta = theta
    state.cos_theta = cos_t
    state.sin_theta = sin_t
    state.events_since_last_patch += 1
    if state.status == BusStatus.IDLE.value:
        state.status = BusStatus.ROTATING.value
    return state


# ══════════════════════════════════════════════════════
# 公开 API
# ══════════════════════════════════════════════════════

def push_event(tension: float) -> dict:
    """
    推送张力事件到总线（欧拉旋转）

    参数：
      tension: 张力量值 ∈ [0, 1]

    返回：
      {
        "theta": float,        # 当前相位角
        "cos_theta": float,    # 主意识参与度
        "sin_theta": float,    # 潜意识参与度
        "status": str,         # 总线状态
        "conserved": bool,     # 守恒检验
        "should_enter_bus": bool  # 是否应进入总线
      }
    """
    state = _load_state()

    # 欧拉旋转
    theta = _rotate(state.theta, tension * math.pi * 0.1)  # tension∈[0,1]映射到Δθ∈[0, 0.1π]
    cos_t, sin_t = _decompose_theta(theta)

    # 守恒校验
    conserved = _conservation_check(theta)

    # 总线状态判断
    should_enter = theta >= T_BUS_ENTER

    state = _update_state(state, theta)
    _save_state(state)

    _append_history({
        "ts": time.time(),
        "type": "push",
        "tension_input": tension,
        "delta_theta": tension * math.pi * 0.1,
        "theta": theta,
        "cos_theta": cos_t,
        "sin_theta": sin_t,
        "status": state.status,
        "conserved": conserved,
    })

    return {
        "theta": round(theta, 6),
        "cos_theta": round(cos_t, 6),
        "sin_theta": round(sin_t, 6),
        "status": state.status,
        "conserved": conserved,
        "should_enter_bus": should_enter,
    }


def apply_patch(patch_type: str = "default") -> dict:
    """
    施加结构补丁：e^(iπ) + 1 = 0
    θ → 0，总线释放

    参数：
      patch_type: 补丁类型（"logic" / "rationalize" / "action" / "default"）

    返回：
      {
        "theta": float,        # 补丁后相位角（应为 0）
        "cos_theta": float,    # 应为 1.0
        "sin_theta": float,    # 应为 0.0
        "status": str,
        "released": bool,      # 总线是否已释放
        "conserved": bool,
      }
    """
    state = _load_state()

    old_theta = state.theta
    theta = 0.0
    cos_t, sin_t = _decompose_theta(theta)
    conserved = _conservation_check(theta)

    state.theta = theta
    state.cos_theta = cos_t
    state.sin_theta = sin_t
    state.status = BusStatus.RELEASING.value
    state.current_patch = patch_type
    state.total_rotations += 1
    state.events_since_last_patch = 0

    _save_state(state)

    _append_history({
        "ts": time.time(),
        "type": "patch",
        "patch_type": patch_type,
        "old_theta": old_theta,
        "theta": theta,
        "cos_theta": cos_t,
        "sin_theta": sin_t,
        "status": state.status,
        "conserved": conserved,
    })

    return {
        "theta": round(theta, 6),
        "cos_theta": round(cos_t, 6),
        "sin_theta": round(sin_t, 6),
        "status": state.status,
        "released": True,
        "conserved": conserved,
    }


def get_state() -> dict:
    """读取当前总线状态"""
    state = _load_state()
    return {
        "theta": round(state.theta, 6),
        "cos_theta": round(state.cos_theta, 6),
        "sin_theta": round(state.sin_theta, 6),
        "status": state.status,
        "current_patch": state.current_patch,
        "events_since_last_patch": state.events_since_last_patch,
        "total_rotations": state.total_rotations,
        "conserved": _conservation_check(state.theta),
    }


def reset() -> None:
    """强制重置总线为空闲态"""
    state = FrictionBusState()
    _save_state(state)


# ══════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== friction_bus_euler self-test ===")
    reset()

    # Test 1: 初始状态
    s = get_state()
    assert s["theta"] == 0.0, f"初始 theta 应为 0，实际 {s['theta']}"
    assert s["cos_theta"] == 1.0, f"cos(0) 应为 1.0，实际 {s['cos_theta']}"
    assert s["sin_theta"] == 0.0, f"sin(0) 应为 0，实际 {s['sin_theta']}"
    assert s["conserved"] == True, "初始守恒检验应通过"
    print("  [PASS] Test1: 初始状态")

    # Test 2: 张力累加（旋转）
    result = push_event(tension=0.8)
    s = get_state()
    assert s["theta"] > 0, f"theta 应增加，实际 {s['theta']}"
    assert s["cos_theta"] < 1.0, f"cosθ 应 < 1.0（主意识参与下降）"
    assert s["sin_theta"] > 0, f"sinθ 应 > 0（潜意识参与增加）"
    assert s["conserved"] == True, "旋转后守恒检验应通过"
    print(f"  [PASS] Test2: 旋转后 theta={s['theta']:.4f} cos={s['cos_theta']:.4f} sin={s['sin_theta']:.4f}")

    # Test 3: 守恒不变量
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        cos_t, sin_t = _decompose_theta(t)
        norm = math.sqrt(cos_t**2 + sin_t**2)
        err = abs(norm - 1.0)
        assert err < 1e-10, f"θ={t} 守恒误差 {err} 超出容忍"
    print("  [PASS] Test3: |e^iθ|=1 守恒（θ=0~3全覆盖）")

    # Test 4: 补丁释放
    result = apply_patch("logic")
    s = get_state()
    assert s["theta"] == 0.0, f"补丁后 theta 应为 0，实际 {s['theta']}"
    assert s["cos_theta"] == 1.0, f"补丁后 cosθ 应为 1.0"
    assert s["sin_theta"] == 0.0, f"补丁后 sinθ 应为 0"
    assert s["released"] == True, "总线应已释放"
    assert s["conserved"] == True, "补丁后守恒检验应通过"
    print("  [PASS] Test4: apply_patch 释放总线，θ=0，|e^iθ|=1")

    # Test 5: 三角函数分解
    test_thetas = [0.0, 0.5, 1.0, 1.5708, 2.0, 2.5, 3.0]
    for t in test_thetas:
        cos_t, sin_t = _decompose_theta(t)
        cos_ref = math.cos(t)
        sin_ref = math.sin(t)
        assert abs(cos_t - cos_ref) < 1e-9, f"θ={t} cos误差 {abs(cos_t-cos_ref)}"
        assert abs(sin_t - sin_ref) < 1e-9, f"θ={t} sin误差 {abs(sin_t-sin_ref)}"
    print("  [PASS] Test5: _decompose_theta 精度（7个采样点）")

    print("=== ALL TESTS PASSED ===")
    reset()
