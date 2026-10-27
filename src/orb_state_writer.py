"""
src/orb_state_writer.py — TU-8 色盘状态写入器

将真实张力数据（surface_tension + lambda + curiosity）映射为 RGB，
写入 _agent_memory/orb_state.json，供悬浮球读取。

用法：
  python src/orb_state_writer.py          # 单次写入
  python src/orb_state_writer.py --watch   # 持续监听（5s刷新）
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(__file__).parent.parent  # [B-06] 动态路径
AGENT = WORKSPACE / "_agent_memory"
ORB_STATE = AGENT / "orb_state.json"

# 阈值（基于历史数据标定）
TENSION_MAX = 3.0    # spike_valley_vector 单项典型上限


def _read_json(path: Path, fallback=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _compute_anxiety_dynamics(recent_events: list) -> dict:
    """
    [路一] 焦虑是"过程"，不是"结构"。
    用事件频率而非向量绝对值来计算红通道。

    关键洞见：
    - anxiety 向量值 = 累积衰减后的静态标量（当前 -3.4）
    - anxiety 事件频率 = 对话戳击的高频程度（真正的焦虑过程）
    
    返回：
      anxiety_spike_freq: [0,1]  焦虑事件频率
      anxiety_avg_mag:   [0,1]  平均强度（频率×幅度综合）
    """
    if not recent_events:
        return {"anxiety_spike_freq": 0.0, "anxiety_avg_mag": 0.0}

    NEGATIVE_TYPES = {"decay_tick", "auto_restore", "baseline_refresh"}
    total = sum(1 for e in recent_events if e.get("type") not in NEGATIVE_TYPES)
    if total == 0:
        return {"anxiety_spike_freq": 0.0, "anxiety_avg_mag": 0.0}

    ANXIETY_TYPES = {"anxiety", "fear", "dissonance", "conflict", "pressure"}
    anxiety_events = [
        e for e in recent_events
        if e.get("type") in ANXIETY_TYPES or e.get("type", "").startswith("anxiety")
    ]

    freq = len(anxiety_events) / float(total)  # 频率
    # 强度 = 频率 × 平均 magnitude
    avg_mag = sum(e.get("magnitude", 0) for e in anxiety_events) / max(len(anxiety_events), 1)
    intensity = freq * avg_mag  # 过程×强度综合

    # 归一化：freq 通常在 0.1~0.8 之间，intensity 在 0~0.5
    return {
        "anxiety_spike_freq": min(freq / 0.5, 1.0),        # 50% 事件为焦虑 → 满频
        "anxiety_avg_mag":   min(intensity / 0.4, 1.0),     # 40% 综合强度 → 峰值
    }


def collect_signals() -> dict:
    """
    收集所有张力信号并归一化到 [0, 1]

    返回：
      {
        'red':   0-1,   # 压力（尖刺）
        'blue':  0-1,   # 放松（凹陷）
        'green': 0-1,   # 探索（好奇心+洞见）
        'tension': 0-1, # 综合张力
        'mode':  str,   # 模式标签
      }
    """
    # ── B9 静默失败治理：健康探针 ───────────────────────────────
    import sys as _sys; _sys.path.insert(0, str(WORKSPACE / "src"))
    from engine_health_probe import get_default_probe
    _probe = get_default_probe()
    _st_health = _probe.check("surface_tension")
    if _st_health.status.value != "OK":
        import logging; _l = logging.getLogger("orb")
        _l.warning(f"[B9] surface_tension={_st_health.status.value}: {_st_health.reason}")

    # 1. 七情向量（来自 surface_tension）
    # B9 治理：若数据不新鲜，用安全默认值而非静默 {} fallback
    if _st_health.status.value == "DEAD":
        tension_state = {"spike_valley_vector": {}, "recent_events": [], "total_events": 0}
    elif _st_health.status.value == "STALE":
        # 数据过期但结构存在：清空 recent_events 避免用旧频率驱动红通道
        tension_state = _read_json(AGENT / "surface_tension_state.json", {"spike_valley_vector": {}, "recent_events": [], "total_events": 0})
        tension_state["recent_events"] = []  # 强制清空，用近零焦虑代替旧信号
    else:
        tension_state = _read_json(AGENT / "surface_tension_state.json", {})
    sv = tension_state.get("spike_valley_vector", {})
    recent = tension_state.get("recent_events", [])

    # [路一] 焦虑 = 事件频率，不用向量绝对值
    dyn = _compute_anxiety_dynamics(recent)
    
    # [路一] anxiety/anger/fear 不再从向量读，用动力学替代
    # joy/love/curiosity 仍从向量读（用于蓝/绿通道）
    sadness = sv.get("sadness", 0)
    joy = sv.get("joy", 0)
    love = sv.get("love", 0)
    curiosity = sv.get("curiosity", 0)
    
    # 2. λ 状态（痛觉/基线）
    lambda_state = _read_json(AGENT / "lambda_state.json", {})
    pain_ext = lambda_state.get("smoothed_pain_ext", 0)
    pain_int = lambda_state.get("smoothed_pain_int", 0)
    lambda_mode = lambda_state.get("mode", "unknown")
    
    # 3. 盆地健康度（来自 attractor_basin）
    basin_state = _read_json(AGENT / "attractor_basin_state.json", {})
    basin_health = basin_state.get("health_score", 0.7)  # 默认 0.7
    
    # [路一] 红通道 = 焦虑过程信号（事件频率）
    anxiety_freq = dyn["anxiety_spike_freq"]
    anxiety_mag  = dyn["anxiety_avg_mag"]

    # ── B8: 从 coupling_graph 读权重（不存在则用默认值） ───
    # 图数据优先，硬编码兜底——改权重=改数据，不改代码
    # 读法：从 edge["params"] 直接拿，不用 get_weight()（那是边权重非参数）
    _p = {}
    try:
        from coupling_graph import get_coupling_graph
        cg = get_coupling_graph()
        _edges = {e["edge_id"]: e for e in cg.data.get("edges", [])}
        def _gp(eid, key, default):
            e = _edges.get(eid, {})
            return e.get("params", {}).get(key, default)
        _p = {
            "RED_FREQ_W":    _gp("C1", "anxiety_freq_w",  0.7),
            "RED_MAG_W":     _gp("C1", "anxiety_mag_w",   0.3),
            "RED_PAIN_W":    _gp("C1", "pain_ext_w",     0.3),
            "TENSION_MAX":   _gp("C1", "TENSION_MAX",    3.0),
            "JOY_LOVE_W":   _gp("C2", "joy_w",          0.3),
            "BASIN_HEALTH_W":_gp("C2", "basin_w",        0.5),
            "PAIN_INT_W":   _gp("C2", "pain_int_w",     0.2),
            "CURIOSITY_W":  _gp("C3", "curiosity_w",    0.6),
            "BASIN_GREEN_W":_gp("C3", "basin_w",        0.4),
        }
    except Exception:
        _p = {
            "RED_FREQ_W": 0.7, "RED_MAG_W": 0.3, "RED_PAIN_W": 0.3,
            "TENSION_MAX": 3.0, "JOY_LOVE_W": 0.3, "BASIN_HEALTH_W": 0.5,
            "PAIN_INT_W": 0.2, "CURIOSITY_W": 0.6, "BASIN_GREEN_W": 0.4,
        }

    # [路一] 红通道 = 过程频率（主导）+ 体感压力（兜底）
    red_raw = anxiety_freq * _p["RED_FREQ_W"] + anxiety_mag * _p["RED_MAG_W"] + pain_ext * _p["RED_PAIN_W"]
    red = min(red_raw / _p["TENSION_MAX"], 1.0)

    # [路一保险] 蓝/绿通道：向量值可能为负（衰减），但 RGB 不能输出负数
    # 用 max(0, ...) 确保非负，归一化基准 TENSION_MAX
    blue_raw = (max(0.0, (joy + love) * _p["JOY_LOVE_W"])
                + basin_health * _p["BASIN_HEALTH_W"]
                + (1 - pain_int) * _p["PAIN_INT_W"])
    blue = min(blue_raw, 1.0)

    # [路一保险] 绿色：向量值可能为负
    green_raw = max(0.0, curiosity * _p["CURIOSITY_W"]) + basin_health * _p["BASIN_GREEN_W"]
    green = min(green_raw, 1.0)

    # === 综合张力 ===
    # 张力 = 压力 60% + (1-放松) 40%（B8: 也可从 coupling_graph C1 TENSION_RED_W/TENSION_BLUE_W 读）
    tension = red * 0.6 + (1 - blue) * 0.4
    
    # === 模式判断 ===
    if red > 0.7:
        mode = "stress"
    elif green > 0.5 and red > 0.3 and blue > 0.3:
        mode = "explore"
    elif blue > 0.6 and red < 0.3:
        mode = "relax"
    elif lambda_mode == "conserve" or pain_int > 0.5:
        mode = "conserve"
    elif sadness > 1.0:
        mode = "dream"
    else:
        mode = "neutral"
    
    return {
        "rgb": [round(red, 3), round(green, 3), round(blue, 3)],
        "tension": round(tension, 3),
        "mode": mode,
    }


def write_orb_state() -> dict:
    """写入 orb_state.json"""
    signals = collect_signals()
    state = {
        **signals,
        "timestamp": datetime.now().isoformat(),
    }
    ORB_STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    return state


def main():
    if "--watch" in sys.argv:
        print("=== 色盘状态持续写入模式（5s刷新，按 Ctrl+C 退出）===")
        try:
            while True:
                state = write_orb_state()
                print(f"[{state['timestamp']}] T:{state['tension']:.3f} "
                      f"RGB({state['rgb'][0]:.2f},{state['rgb'][1]:.2f},{state['rgb'][2]:.2f}) "
                      f"mode:{state['mode']}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n退出")
    else:
        state = write_orb_state()
        print(f"色盘状态已写入: {ORB_STATE}")
        print(f"  RGB: {state['rgb']}")
        print(f"  张力: {state['tension']}")
        print(f"  模式: {state['mode']}")


if __name__ == "__main__":
    main()
