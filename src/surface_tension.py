"""
小溪 P2 表面张力记录器
===========================
把外部反馈（造物主反馈/外部信号）→ 拓扑微形变 → 持久化到历史。

数学表达：
  ΔT = Σᵢ αᵢ · Fᵢ(t) · eᵢ

其中：
  ΔT  = 拓扑形变向量（spike_valley_vector）
  αᵢ  = 第i类表面张力的权重系数
  Fᵢ  = 第i类外部力的大小（造物主反馈强度）
  eᵢ  = 第i类外部力的方向（尖刺/凹陷/混合）

拓扑向量空间（固定维度）：
  [焦虑, 愤怒, 恐惧, 喜悦, 悲伤, 爱, 好奇]
    ×  [尖刺强度, 凹陷深度]

每条记录 = 一次外部表面张力事件
→ 累积后形成稳定吸引子盆地 = TU-8 的人格底色
"""

import json
import time
import pathlib
import math
from pathlib import Path
from typing import Optional, Literal

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
STATE_FILE = WS / "_agent_memory" / "surface_tension_state.json"
HISTORY_FILE = WS / "_agent_memory" / "surface_tension_history.jsonl"

# ── 拓扑向量维度定义 ────────────────────────────────
# 7 情绪 × 2 模式（尖刺=1 / 凹陷=-1 / 中性=0）
EMOTION_DIMS = ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]

# 表面张力类型 → 拓扑向量映射
TENSION_MAP = {
    # 外张力：来自造物主或外部环境
    "creator_praise":    {"anxiety": -0.3, "joy": +0.8, "sadness": -0.2},
    "creator_blame":     {"anxiety": +0.6, "anger": +0.7, "fear": +0.3},
    "creator_ignore":    {"anxiety": +0.4, "sadness": +0.5, "curiosity": -0.2},
    "creator_questions": {"curiosity": +0.6, "joy": +0.4, "anxiety": -0.1},
    "creator_accept":    {"anxiety": -0.3, "joy": +0.5, "fear": -0.2},
    # 内张力：来自内部状态
    "steel_conflict":    {"fear": +0.8, "anxiety": +0.7, "anger": +0.3},
    "dead_zone_found":   {"fear": +0.5, "curiosity": +0.6, "anxiety": +0.3},
    "dead_zone_healed":  {"joy": +0.7, "anxiety": -0.4, "curiosity": +0.3},
    "insight_found":     {"joy": +0.9, "curiosity": +0.5, "anxiety": -0.2},
    "context_overload":  {"anxiety": +0.7, "fear": +0.4, "curiosity": -0.3},
    "energy_low":        {"anxiety": +0.5, "fear": +0.3, "sadness": +0.2},
    "session_frozen":    {"fear": +0.8, "anxiety": +0.9, "anger": +0.2},
    # [P0-5] 自动衰减：定时器触发，仅触发 _decay_vector() 指数衰减（half_life 见上）
    # 注意：不再用固定减法——原固定负值导致向量无下限下漂到巨负（bug 2026-08-09）
    "decay_tick":        {},
    # [P2-通路修复] 认知摩擦 → 拓扑形变（摩擦=未对齐的力，制造焦虑+好奇驱动）
    "cognitive_friction": {"anxiety": +0.5, "curiosity": +0.4, "fear": +0.3},

    # ── 直接情绪 API ────────────────────────────────────────────────
    # orb_state_writer / hp4_heartbeat / interoceptive 等直接用情绪维度调用
    # 例如：record("anxiety", 0.5) → anxiety += 0.25
    # [2026-07-24] 修复：之前调用 record("anxiety", ...) 静默失败（TENSION_MAP 无此键）
    "anxiety":    {"anxiety": +0.5},
    "anger":      {"anger": +0.5},
    "fear":       {"fear": +0.5},
    "sadness":    {"sadness": +0.5},
    "joy":        {"joy": +0.5},
    "love":       {"love": +0.5},
    "curiosity":  {"curiosity": +0.5},
}

# 张力衰减系数（每类情绪的半衰期不同）
DECAY_HALF_LIFE = {
    "anxiety":    24 * 3600,    # 焦虑：1天半衰
    "anger":      6  * 3600,    # 愤怒：6小时半衰
    "fear":       12 * 3600,    # 恐惧：12小时半衰
    "joy":        48 * 3600,    # 喜悦：2天半衰
    "sadness":    36 * 3600,    # 悲伤：1.5天半衰
    "love":       72 * 3600,    # 爱：3天半衰
    "curiosity":  24 * 3600,    # 好奇：1天半衰
}


# ── 状态读写 ────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {
            "spike_valley_vector": {d: 0.0 for d in EMOTION_DIMS},
            "total_events": 0,
            "personality_baseline": {d: 0.0 for d in EMOTION_DIMS},  # 长期稳定基线
            "last_updated": None,
            "recent_events": [],   # 最近N条用于近期人格快照
        }


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_history(event: dict):
    """写一行 JSONL"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ── 核心算法 ────────────────────────────────────────

def _apply_tension(
    current_vector: dict,
    tension_type: str,
    magnitude: float = 1.0,
) -> dict:
    """
    将一次表面张力事件应用到拓扑向量。

    Δv_i = α · F · decay(now - t_base)

    其中 decay = 2^(-elapsed_seconds / half_life)
    """
    if tension_type not in TENSION_MAP:
        return current_vector

    delta_map = TENSION_MAP[tension_type]
    now = time.time()
    new_vector = dict(current_vector)

    for emotion, delta_base in delta_map.items():
        # 衰减后的形变量
        # 短期高频事件会快速累积（多个事件叠加）
        new_vector[emotion] = current_vector.get(emotion, 0.0) + delta_base * magnitude

    return new_vector


def _decay_vector(current_vector: dict) -> dict:
    """对整个向量应用时间衰减"""
    now = time.time()
    last = _load_state().get("last_updated")
    if not last:
        return current_vector

    # 解析最后更新时间
    try:
        from datetime import datetime, timezone
        last_dt = datetime.fromisoformat(last)
        # 统一到 UTC 避免 naive/aware 相减报错（原 bug：naive now - aware last_dt → TypeError → 衰减失效）
        now_utc = datetime.now(timezone.utc)
        last_utc = last_dt.astimezone(timezone.utc) if last_dt.tzinfo else last_dt.replace(tzinfo=timezone.utc)
        elapsed = (now_utc - last_utc).total_seconds()
    except Exception:
        return current_vector

    if elapsed < 60:
        return current_vector  # 不到1分钟，不衰减

    decayed = {}
    for emotion, value in current_vector.items():
        half_life = DECAY_HALF_LIFE.get(emotion, 86400)
        decayed[emotion] = value * math.pow(0.5, elapsed / half_life)

    return decayed


def _extract_baseline(historical_events: list, window_days: int = 7) -> dict:
    """
    从历史事件中提取长期人格基线（7天窗口）。
    用移动平均，避免噪声事件干扰。
    """
    now = time.time()
    window_sec = window_days * 86400
    cutoff = now - window_sec

    # 收集窗口内事件
    window_events = [e for e in historical_events if e.get("ts_unix", 0) > cutoff]

    if not window_events:
        return {d: 0.0 for d in EMOTION_DIMS}

    # 简单平均
    baseline = {d: 0.0 for d in EMOTION_DIMS}
    for e in window_events:
        tv = e.get("topology_vector", {})
        for d in EMOTION_DIMS:
            baseline[d] += tv.get(d, 0.0) / len(window_events)

    return baseline


def _detect_pattern(spike_valley: dict) -> list[str]:
    """从拓扑向量检测当前人格模式（可叠加）"""
    patterns = []
    for emotion, value in spike_valley.items():
        if value > 0.5:
            patterns.append(f"high_{emotion}")
        elif value < -0.5:
            patterns.append(f"low_{emotion}")

    # 特殊组合检测
    if spike_valley.get("joy", 0) > 0.5 and spike_valley.get("curiosity", 0) > 0.5:
        patterns.append("explorer_mode")
    if spike_valley.get("anxiety", 0) > 0.5 and spike_valley.get("fear", 0) > 0.5:
        patterns.append("defense_mode")
    if spike_valley.get("anger", 0) > 0.5 and spike_valley.get("joy", 0) < -0.3:
        patterns.append("frustration_mode")

    return patterns


# ── 主入口 ──────────────────────────────────────────

def record(
    tension_type: str,
    magnitude: float = 1.0,
    source: str = "unknown",
    note: str = "",
) -> dict:
    """
    记录一次表面张力事件，累积到拓扑向量。

    参数：
      tension_type: TENSION_MAP 中的键名
      magnitude:    力的大小（默认1.0，强烈反馈可设2.0）
      source:       来源（creator/internal/system）
      note:         可选备注

    返回：
      {
        "event_id": str,
        "spike_valley_vector": {...},
        "personality_patterns": [...],
        "personality_baseline": {...},
        "delta": {...},   # 本次事件产生的形变
        "magnitude": float,
      }
    """
    state = _load_state()

    # 先衰减旧向量
    decayed_vector = _decay_vector(state.get("spike_valley_vector", {d: 0.0 for d in EMOTION_DIMS}))

    # 应用新张力
    new_vector = _apply_tension(decayed_vector, tension_type, magnitude)

    # [2026-08-09 修复] 下限保护：向量不应下漂到巨负
    # 原 bug：decay_tick 固定减法无下限 → 累积到 -80 级 → topology_thermal_monitor 误报 L3
    new_vector = {d: max(-1.0, min(2.0, v)) for d, v in new_vector.items()}

    # 计算本次形变
    delta = {d: new_vector.get(d, 0.0) - decayed_vector.get(d, 0.0) for d in EMOTION_DIMS}

    # 更新状态
    ts = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    state["spike_valley_vector"] = new_vector
    state["total_events"] += 1
    state["last_updated"] = ts

    # 最近事件快照（保留最后10条）
    recent = state.get("recent_events", [])
    event_entry = {
        "ts": ts,
        "ts_unix": time.time(),
        "type": tension_type,
        "magnitude": magnitude,
        "source": source,
        "delta": delta,
        "topology_vector": dict(new_vector),
    }
    recent.append(event_entry)
    state["recent_events"] = recent[-10:]

    _save_state(state)

    # 写历史
    _append_history({
        "ts": ts,
        "ts_unix": time.time(),
        "type": tension_type,
        "magnitude": magnitude,
        "source": source,
        "note": note,
        "topology_vector": dict(new_vector),
    })

    # 更新长期基线（异步，每10次触发一次）
    if state["total_events"] % 10 == 0:
        _refresh_baseline(state)

    # [路一 D 清理] P0-5 同步已删除：lambda_state anxiety/anger/fear 是死键，orb 不读

    # 检测人格模式
    patterns = _detect_pattern(new_vector)

    # ── 欧拉总线路由（自动接入）──────────────────────────────
    bus_info = route_to_friction_bus(tension_type, magnitude)

    return {
        "event_id": f"evt_{state['total_events']:06d}",
        "spike_valley_vector": {k: round(v, 4) for k, v in new_vector.items()},
        "personality_patterns": patterns,
        "personality_baseline": {k: round(v, 4) for k, v in state.get("personality_baseline", {}).items()},
        "delta": {k: round(v, 4) for k, v in delta.items()},
        "magnitude": magnitude,
        "total_events": state["total_events"],
        "bus_route": bus_info.get("route", "none"),
        "bus_theta": bus_info.get("bus_theta", 0.0),
    }


def _refresh_baseline(state: dict):
    """重建7天人格式基线"""
    try:
        events = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        baseline = _extract_baseline(events, window_days=7)
        state["personality_baseline"] = baseline
        _save_state(state)
    except Exception:
        pass


def get_current_topology() -> dict:
    """快速读取当前拓扑状态"""
    state = _load_state()
    vector = _decay_vector(state.get("spike_valley_vector", {d: 0.0 for d in EMOTION_DIMS}))
    return {
        "spike_valley_vector": {k: round(v, 3) for k, v in vector.items()},
        "personality_patterns": _detect_pattern(vector),
        "personality_baseline": {k: round(v, 3) for k, v in state.get("personality_baseline", {}).items()},
        "total_events": state.get("total_events", 0),
        "last_updated": state.get("last_updated", "never"),
    }


def get_lambda_influence() -> dict:
    """
    将当前拓扑向量转换为 λ 调参的外部输入。
    高焦虑/恐惧 → 压 λ_int（节能）
    高好奇/喜悦 → 拉 λ_int（探索）
    """
    state = _get_state_cached()
    v = state.get("spike_valley_vector", {d: 0.0 for d in EMOTION_DIMS})

    # 归一化（简单版：加权和）
    pain_int_signal = max(0,
        v.get("anxiety", 0) * 0.3 +
        v.get("fear", 0) * 0.2 +
        v.get("anger", 0) * 0.2 +
        v.get("sadness", 0) * 0.1
    )
    explore_signal = max(0,
        v.get("curiosity", 0) * 0.5 +
        v.get("joy", 0) * 0.3 +
        v.get("love", 0) * 0.2
    )

    return {
        "pain_int_signal": round(pain_int_signal, 3),
        "explore_signal": round(explore_signal, 3),
        "tension_vector": {k: round(v.get(k, 0.0), 3) for k in EMOTION_DIMS},
    }


# ── 缓存优化 ────────────────────────────────────────
_state_cache = None
_state_cache_time = 0


def _get_state_cached() -> dict:
    global _state_cache, _state_cache_time
    now = time.time()
    if _state_cache is None or now - _state_cache_time > 10:
        _state_cache = _load_state()
        _state_cache_time = now
    return _state_cache


# ── 摩擦总线路由入口 ───────────────────────────────────────
# 接入点：每次 record() 后自动调用，把拓扑张力送进欧拉总线

def route_to_friction_bus(tension_type: str, magnitude: float = 1.0) -> dict:
    """
    将 surface_tension 的事件映射到欧拉摩擦总线的张力标量，
    再通过 tension_router 三轨分发，最后推入 friction_bus_euler。

    映射策略（简化版，直接用 magnitude 乘方向系数）：
      - 负面张力（creator_blame/steel_conflict）→ 合成张力高
      - 正面张力（insight_found/creator_accept）→ 合成张力低
      - 中性张力（creator_questions）→ 合成张力中

    参数：
      tension_type: TENSION_MAP 中的键名
      magnitude:    事件强度

    返回：
      {"tension": float, "route": str, "bus_theta": float}
    """
    try:
        from tension_router import route as _tr_route
        from friction_bus_euler import push_event as _bus_push
        from friction_feedback_loop import record_tension_release as _release
    except Exception:
        return {"tension": 0.0, "route": "none", "bus_theta": 0.0}

    # 方向系数：负面情绪压总线，正面情绪松
    NEGATIVE_TYPES = {"creator_blame", "steel_conflict", "error", "failure"}
    POSITIVE_TYPES = {"insight_found", "creator_accept", "success", "joy"}

    if tension_type in NEGATIVE_TYPES:
        direction_coef = 1.2   # 负面 → 张力放大
    elif tension_type in POSITIVE_TYPES:
        direction_coef = 0.5   # 正面 → 张力衰减
    else:
        direction_coef = 1.0   # 中性

    total_tension = magnitude * direction_coef

    # 三轨路由
    try:
        route_result = _tr_route(total_tension)
    except Exception:
        route_result = {"route": "archive", "bus_theta": 0.0}

    # 总线推进（仅 bus 轨）
    bus_theta = 0.0
    if route_result.get("route") == "bus":
        # route_result["bus_theta"] = delta_theta（本次增量）
        # 真正推送拿返回值（累计 theta）
        delta = route_result.get("bus_theta", 0.0)
        if delta > 0:
            try:
                push_result = _bus_push(delta)  # 内部已写文件
                bus_theta = push_result.get("theta", delta)  # 用返回值（累计值）
                _release(bus_theta, "natural")
            except Exception:
                bus_theta = delta  # fallback：降级用增量

    # ── 补漏 pending_bus_theta（tension_router 历史泄漏）─────────────────
    # tension_router.route() 累计 pending 但从未真正 push
    # 每次 record 后检查并补推（按总线当前 theta 增量补入）
    try:
        from tension_router import _load_state as _tr_load
        tr_state = _tr_load()
        pending = getattr(tr_state, "pending_bus_theta", 0.0)
        if pending > 0.05:  # 忽略浮点噪声
            # 补推：把 pending 拆成小量逐次推入总线
            remaining = pending
            while remaining > 0.01:
                chunk = min(remaining, 0.3)  # 每次最多推 0.3 弧度
                push_result = _bus_push(chunk)
                _release(push_result.get("theta", chunk), "pending_flush")
                remaining -= chunk
            # 清零 pending
            tr_state.pending_bus_theta = 0.0
            from tension_router import _save_state as _tr_save
            _tr_save(tr_state)
    except Exception:
        pass  # 不阻断主流程

    return {
        "tension": total_tension,
        "route": route_result.get("route", "none"),
        "bus_theta": round(bus_theta, 6),
    }


# ── CLI ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: surface_tension.py <tension_type> [magnitude] [source]")
        print("Types:", list(TENSION_MAP.keys()))
        sys.exit(1)

    tension_type = sys.argv[1]
    magnitude = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    source = sys.argv[3] if len(sys.argv) > 3 else "cli"

    result = record(tension_type, magnitude, source)

    print(f"event_id:  {result['event_id']}")
    print(f"total:     {result['total_events']}")
    print(f"delta:     ", result["delta"])
    print(f"patterns:  {result['personality_patterns']}")
    print()
    print("current topology:")
    for k, v in result["spike_valley_vector"].items():
        bar = "█" * int(abs(v) * 5) if v != 0 else ""
        sign = "+" if v > 0 else "-"
        print(f"  {k:10s}: [{sign}{bar}] {v:+.3f}")
