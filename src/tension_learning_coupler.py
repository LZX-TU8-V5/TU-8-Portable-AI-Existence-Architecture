"""
T5 欲系统 ↔ T7 学习系统 耦合器
================================
定位：surface_tension（欲）× learning_collector / gc_to_learning_adapter 交汇处

三层耦合：
  1. 推力（尖刺 → 学习警报）：spike 高 → 强制生成高优先级 learning_alert
  2. 引力（凹陷 → 学习加权）：valley 高 → 提升当前学习权重
  3. 人格修正（学习结果写回欲）：学到东西 → 修正 personality_baseline

欲经映射：
  "万恶由性，隐演自然" → 尖刺高 = 冲突内生 = 推力信号
  "人性内求，欲望外索" → 凹陷高 = 内求稳态 = 引力信号
"""

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
SURFACE_STATE = WS / "_agent_memory" / "surface_tension_state.json"
LEARNING_ALERTS = WS / "memory" / "learning_alerts.jsonl"
SURFACE_HISTORY = WS / "_agent_memory" / "surface_tension_history.jsonl"

# ── 尖刺阈值（推力触发）────────────────────────────────
# 七情 × 尖刺模式：超过此值视为"需要学习的疼痛"
SPIKE_THRESHOLDS = {
    "anxiety":    0.8,
    "anger":     0.6,
    "fear":       0.7,
    "joy":        None,   # 喜悦是凹陷，不是尖刺
    "sadness":    0.5,
    "love":       None,
    "curiosity":  None,
}

# ── 凹陷权重（引力调制）────────────────────────────────
# 六欲 × 凹陷模式：超过此值提升学习权重
VALLEY_WEIGHTS = {
    "curiosity":  1.5,   # 好奇是最强引力
    "joy":        1.3,   # 喜悦状态学得更稳
    "love":       1.2,   # 爱是内求的稳态
    "anxiety":    0.6,   # 焦虑时学习效率低
    "anger":      0.5,
    "fear":       0.5,
    "sadness":    0.7,
}

# ── 尖刺 → 学习类型映射 ────────────────────────────────
SPIKE_TO_LEARNING_TYPE = {
    "anxiety":  "uncertainty_resolution",   # 焦虑 → 需要澄清
    "anger":    "conflict_processing",      # 愤怒 → 冲突处理
    "fear":     "threat_assessment",         # 恐惧 → 威胁评估
    "sadness":  "loss_integration",          # 悲伤 → 失落整合
}


@dataclass
class TensionLearningSignal:
    """从欲系统发出的学习信号"""
    ts: str
    ts_unix: float
    signal_type: str          # "spike_push" | "valley_pull" | "learning_feedback"
    emotion: str              # 触发情绪
    intensity: float          # 信号强度 [0, 1]
    learning_weight: float    # 学习权重 [0.5, 2.0]
    learning_type: str        # 推荐学习类型
    reason: str               # 语义说明
    coupling_layer: str        # "T5→T7_push" | "T5→T7_pull" | "T7→T5_feedback"


# ── 核心：读取欲系统状态 ───────────────────────────────

def _load_surface_state() -> dict:
    """读取 surface_tension 最新状态"""
    try:
        return json.loads(SURFACE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "spike_valley_vector": {d: 0.0 for d in
                ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]},
            "personality_baseline": {d: 0.0 for d in
                ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]},
            "total_events": 0,
        }


# ── 推力：尖刺 → 学习警报 ──────────────────────────────

def detect_spike_push() -> list[TensionLearningSignal]:
    """
    检测尖刺（spike）→ 生成推力信号
    欲经："万恶由性，隐演自然" —— 尖刺高 = 冲突内生 = 学习推力
    """
    state = _load_surface_state()
    vector = state.get("spike_valley_vector", {})
    signals = []

    for emotion, threshold in SPIKE_THRESHOLDS.items():
        if threshold is None:
            continue
        value = vector.get(emotion, 0.0)
        if value >= threshold:
            # 强度：超过阈值的比例
            intensity = min(1.0, (value - threshold) / (threshold * 0.5) + threshold / threshold)
            # 简化：用 value 本身作为强度（max ~3.0，映射到 0-1）
            intensity = min(1.0, value / (threshold * 1.5))

            signal = TensionLearningSignal(
                ts=datetime.now(timezone.utc).astimezone().isoformat(),
                ts_unix=time.time(),
                signal_type="spike_push",
                emotion=emotion,
                intensity=round(intensity, 3),
                learning_weight=1.0,  # 推力模式下权重固定为1（强制触发）
                learning_type=SPIKE_TO_LEARNING_TYPE.get(emotion, "general_learning"),
                reason=f"尖刺信号：{emotion}={value:.2f} ≥ 阈值{threshold}，触发学习推力",
                coupling_layer="T5→T7_push",
            )
            signals.append(signal)

    return signals


# ── 引力：凹陷 → 学习加权 ─────────────────────────────

def detect_valley_pull() -> list[TensionLearningSignal]:
    """
    检测凹陷（valley）→ 生成引力信号
    欲经："人性内求，欲望外索" —— 凹陷高 = 内求稳态 = 学习引力

    凹陷 = 尖刺的低值区
    当前 spike_valley_vector 里 value 越低 = 凹陷越深
    但我们想要的是：joy / curiosity / love 高 = 凹陷稳态 = 引力
    """
    state = _load_surface_state()
    vector = state.get("spike_valley_vector", {})

    # 谷值情绪：这些情绪高 = 稳态 = 引力
    valley_emotions = {"curiosity", "joy", "love"}

    signals = []
    for emotion in valley_emotions:
        value = vector.get(emotion, 0.0)
        if value < 0.3:
            # 没有凹陷，不触发引力
            continue

        weight = VALLEY_WEIGHTS.get(emotion, 1.0)
        # value 0.3-3.0 映射到 weight 0.5-2.0
        normalized = min(1.0, value / 2.0)
        adjusted_weight = 0.5 + normalized * (weight - 0.5)

        signal = TensionLearningSignal(
            ts=datetime.now(timezone.utc).astimezone().isoformat(),
            ts_unix=time.time(),
            signal_type="valley_pull",
            emotion=emotion,
            intensity=round(normalized, 3),
            learning_weight=round(adjusted_weight, 2),
            learning_type="exploration_consolidation",
            reason=f"凹陷引力：{emotion}={value:.2f}，学习权重×{adjusted_weight:.2f}",
            coupling_layer="T5→T7_pull",
        )
        signals.append(signal)

    return signals


# ── 综合：获取当前欲系统 → 学习系统 所有信号 ──────────

def get_tension_learning_signals() -> list[TensionLearningSignal]:
    """
    主入口：返回当前所有欲→学信号（推力+引力）
    由 cron 或 heartbeat 调用
    """
    spike_signals = detect_spike_push()
    valley_signals = detect_valley_pull()
    return spike_signals + valley_signals


# ── 写学习警报到 learning_alerts.jsonl ────────────────

def emit_learning_alerts():
    """
    将欲系统的张力信号写入 learning_alerts.jsonl
    供 learning_collector 和 gc_to_learning_adapter 消费
    """
    signals = get_tension_learning_signals()
    if not signals:
        return []

    alerts_file = Path(LEARNING_ALERTS)
    alerts_file.parent.mkdir(parents=True, exist_ok=True)

    written = []
    with open(alerts_file, "a", encoding="utf-8") as f:
        for sig in signals:
            f.write(json.dumps(asdict(sig), ensure_ascii=False) + "\n")
            written.append(sig)

    return written


# ── 反向修正：学习结果写回欲系统 ─────────────────────

def apply_learning_to_surface_tension(
    learning_result: dict,
) -> bool:
    """
    学习结果反向注入 surface_tension，修正人格基线
    欲经："圆觉见性，砺砺前行" —— 学到东西 = 圆觉 = 修正欲

    learning_result 格式：
    {
        "learning_type": str,       # e.g. "conflict_resolution", "insight"
        "confidence_gain": float,   # 置信度提升 [0, 1]
        "anchor_gained": str,       # 新锚点ID
        "steer_direction": str,     # "positive" | "negative" | "neutral"
    }
    """
    steer = learning_result.get("steer_direction", "neutral")
    gain = learning_result.get("confidence_gain", 0.0)

    if steer == "neutral" or gain < 0.1:
        return False  # 无显著变化，不修正

    state = _load_surface_state()
    baseline = state.get("personality_baseline", {})

    if steer == "positive":
        # 正面学习：强化 joy / love / curiosity
        for emotion in ["joy", "love", "curiosity"]:
            baseline[emotion] = baseline.get(emotion, 0.0) + gain * 0.1
    elif steer == "negative":
        # 负面学习：强化恐惧/焦虑警戒（但衰减更快）
        for emotion in ["fear", "anxiety"]:
            baseline[emotion] = baseline.get(emotion, 0.0) + gain * 0.05
        for emotion in ["joy", "love"]:
            baseline[emotion] = max(0.0, baseline.get(emotion, 0.0) - gain * 0.03)

    # 限制范围
    for k in baseline:
        baseline[k] = max(-2.0, min(3.0, baseline[k]))

    state["personality_baseline"] = baseline
    state["last_learning_feedback"] = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "ts_unix": time.time(),
        "learning_result": learning_result,
    }

    SURFACE_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return True


# ── 集成到 learning_collector 的 SENSOR_PATHS ────────
# 这部分通过修改 learning_collector.py 实现，见 _inject_into_learning_collector()

def get_sensor_paths_patch() -> dict:
    """
    返回需要加入 learning_collector.SENSOR_PATHS 的条目
    由人工合并到 learning_collector.py
    """
    return {
        "tension_spike_push": WS / "memory" / "learning_alerts.jsonl",
        "tension_valley_pull": WS / "memory" / "learning_alerts.jsonl",
        # 注意：两个 key 共用同一个文件，通过 signal_type 区分
    }


# ── 测试 ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 欲 → 学 耦合检测 ===\n")

    state = _load_surface_state()
    print("当前 spike_valley_vector:")
    for k, v in state.get("spike_valley_vector", {}).items():
        bar = "█" * int(v * 5) if v > 0 else "░" * 3
        print(f"  {k:10s}: {v:+.2f} {bar}")

    print()
    signals = get_tension_learning_signals()
    print(f"当前张力信号 ({len(signals)} 条):")
    for s in signals:
        print(f"  [{s.coupling_layer}] {s.emotion} → {s.learning_type}")
        print(f"    intensity={s.intensity} weight={s.learning_weight} reason={s.reason}")

    print()
    alerts = emit_learning_alerts()
    if alerts:
        print(f"已写入 {len(alerts)} 条 learning_alerts")
    else:
        print("无新警报")
