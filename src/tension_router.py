"""
张力路由三轨
===============
将张力信号分发到三个通道：
  低张力（T < T_LOW）→ 直接归档（零算力）
  中张力（T < T_HIGH）→ 通道A：躯体标记（BodyState微调）
  高张力（T ≥ T_HIGH）→ 摩擦代谢总线（欧拉旋转）

接口：
  route(text, tension_value) -> dict
  route_vector(vector: StructuralVector) -> dict
"""

import json
import time
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
STATE_FILE = WS / "_agent_memory" / "tension_router_state.json"
HISTORY_FILE = WS / "_agent_memory" / "tension_router_history.jsonl"

# ── 阈值配置 ─────────────────────────────────────────
T_LOW = 0.3
T_HIGH = 0.7


# ══════════════════════════════════════════════════════
# 路由状态
# ══════════════════════════════════════════════════════

@dataclass
class RouterState:
    low_count: int = 0       # 低张力归档计数
    somatic_count: int = 0    # 中张力躯体计数
    bus_count: int = 0       # 高张力总线计数
    last_route: str = "idle"
    last_updated: str = ""
    pending_bus_theta: float = 0.0  # 待推送总线的theta累加值


def _load_state() -> RouterState:
    try:
        d = json.load(open(STATE_FILE, encoding="utf-8"))
        return RouterState(**d)
    except Exception:
        return RouterState()


def _save_state(state: RouterState) -> None:
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
# 三轨路由
# ══════════════════════════════════════════════════════

def _get_route(tension: float) -> str:
    """判定路由轨道"""
    if tension < T_LOW:
        return "archive"
    elif tension < T_HIGH:
        return "somatic"
    else:
        return "bus"


def _write_somatic_signal(tension: float, context: str = "") -> None:
    """
    通道A：躯体标记
    写入 body_somatic_signal.json，供 BodyState 读取微调
    """
    try:
        sig_file = WS / "_agent_memory" / "body_somatic_signal.json"
        data = {
            "tension": round(tension, 4),
            "context": context,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        }
        sig_file.parent.mkdir(parents=True, exist_ok=True)
        sig_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def route(tension: float, context: str = "") -> dict:
    """
    张力路由主入口

    参数：
      tension: 张力量值 ∈ [0, 1]
      context: 上下文文本（供躯体信号记录）

    返回：
      {
        "route": str,           # "archive" | "somatic" | "bus"
        "tension": float,
        "t_low": float,
        "t_high": float,
        "bus_theta": float,     # 若路由到总线，返回应推送的theta值
        "somatic_written": bool, # 躯体信号是否已写入
      }
    """
    state = _load_state()
    route_type = _get_route(tension)

    if route_type == "archive":
        state.low_count += 1
        result = {"route": "archive", "bus_theta": 0.0, "somatic_written": False}

    elif route_type == "somatic":
        state.somatic_count += 1
        _write_somatic_signal(tension, context)
        result = {"route": "somatic", "bus_theta": 0.0, "somatic_written": True}

    else:  # bus
        state.bus_count += 1
        # θ 增量 = tension 映射到 Δθ（0.1π尺度）
        delta_theta = tension * math.pi * 0.1
        state.pending_bus_theta += delta_theta
        result = {"route": "bus", "bus_theta": round(delta_theta, 6), "somatic_written": False}

    state.last_route = route_type
    _save_state(state)

    _append_history({
        "ts": time.time(),
        "route": route_type,
        "tension": tension,
        "bus_theta_delta": result["bus_theta"],
        "pending_theta": state.pending_bus_theta,
    })

    return {
        "route": route_type,
        "tension": round(tension, 4),
        "t_low": T_LOW,
        "t_high": T_HIGH,
        "bus_theta": result["bus_theta"],
        "somatic_written": result["somatic_written"],
        "stats": {
            "low_count": state.low_count,
            "somatic_count": state.somatic_count,
            "bus_count": state.bus_count,
        },
    }


def route_vector(vector) -> dict:
    """
    从结构矢量路由
    使用 vector.tension_signal 作为张力值
    """
    tension = min(getattr(vector, "tension_signal", 0.0), 1.0)
    context = getattr(vector, "raw_text", "")
    return route(tension, context)


def get_state() -> dict:
    """读取路由状态"""
    state = _load_state()
    return {
        "low_count": state.low_count,
        "somatic_count": state.somatic_count,
        "bus_count": state.bus_count,
        "last_route": state.last_route,
        "pending_bus_theta": round(state.pending_bus_theta, 6),
        "t_low": T_LOW,
        "t_high": T_HIGH,
    }


# ══════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== tension_router self-test ===")

    # Test 1: 低张力 → archive
    r = route(0.1)
    assert r["route"] == "archive", f"0.1应归档，实际{r['route']}"
    assert r["somatic_written"] == False
    print(f"  [PASS] Test1: tension=0.1 → {r['route']}")

    # Test 2: 中张力 → somatic
    r = route(0.5)
    assert r["route"] == "somatic", f"0.5应躯体，实际{r['route']}"
    assert r["somatic_written"] == True
    print(f"  [PASS] Test2: tension=0.5 → {r['route']}")

    # Test 3: 高张力 → bus
    r = route(0.9)
    assert r["route"] == "bus", f"0.9应总线，实际{r['route']}"
    assert r["bus_theta"] > 0
    print(f"  [PASS] Test3: tension=0.9 → {r['route']}，Δθ={r['bus_theta']:.4f}")

    # Test 4: 边界
    assert route(0.3)["route"] == "somatic", "T_LOW=0.3 应somatic"
    assert route(0.7)["route"] == "bus", "T_HIGH=0.7 应bus"
    print("  [PASS] Test4: 边界 T_LOW=0.3/somatic, T_HIGH=0.7/bus")

    # Test 5: 统计
    s = get_state()
    assert s["low_count"] == 1
    assert s["somatic_count"] == 1
    assert s["bus_count"] == 1
    print(f"  [PASS] Test5: stats {s}")

    print("=== ALL TESTS PASSED ===")
