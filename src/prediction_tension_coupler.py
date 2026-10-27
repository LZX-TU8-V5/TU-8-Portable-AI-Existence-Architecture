"""
预测模型 ↔ 欲系统 耦合器
===========================
定位：七情六欲 × 置信度 × 预测误差 三维闭环

欲经原理：
  预测准确（低误差）→ 凹陷（内求稳态/掌控感）
  预测失败（高误差）→ 尖刺（七情/焦虑/愤怒/恐惧）

耦合链路：
  cognitive_pain_monitor（预测误差/不确定性）
    → surface_tension（尖刺/凹陷记录）
      → dual_track_confidence_updater（未解尖刺→Track B）
        → confidence_pipeline（置信度修正）
          → 回写 surface_tension（修正后凹陷加深）

三维耦合：
  ① 外部：prediction_error + uncertainty → surface_tension（尖刺）
  ② 内部：surface_tension 未解尖刺 → Track B 置信度加权
  ③ 身体：系统熵 + 体感环状态 → surface_tension 基线
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
SURFACE_STATE = WS / "_agent_memory" / "surface_tension_state.json"
SURFACE_HISTORY = WS / "_agent_memory" / "surface_tension_history.jsonl"
UNRESOLVED_SPIKES = WS / "_agent_memory" / "unresolved_spikes.jsonl"
BODY_STATE = WS / "memory" / "body_regulation.json"
COGNITIVE_PAIN = WS / "memory" / "cognitive_pain_monitor.json"

# ── 预测误差 → 七情映射 ───────────────────────────────
# 低置信度 + 高误差 = 极度焦虑（高尖刺）
# 高置信度 + 预测失败 = 震惊/愤怒（尖锐刺）
# 低误差 + 稳态 = 好奇凹陷

PREDICTION_ERROR_MAP = {
    # (confidence_level, error_magnitude) → (emotion, spike_intensity)
    # confidence_level: "low" | "medium" | "high"
    # error_magnitude: "low" | "medium" | "high"
    ("low",   "high"):  ("anxiety",  0.9),   # 低置信+大误差 = 恐慌
    ("high",  "high"):  ("anger",    0.8),   # 高置信+大误差 = 震惊/愤怒
    ("medium","high"):  ("fear",     0.7),   # 中置信+大误差 = 恐惧
    ("low",   "medium"):("anxiety",  0.5),   # 低置信+中误差 = 焦虑
    ("medium","medium"):("fear",     0.4),   # 中置信+中误差 = 紧张
    ("high",  "medium"):("anger",    0.4),   # 高置信+中误差 = 轻微愤怒
    ("low",   "low"):   ("sadness",  0.3),  # 低置信+小误差 = 悲伤
    ("medium","low"):   ("curiosity",0.5),   # 中置信+小误差 = 好奇（想搞清楚）
    ("high",  "low"):   ("curiosity",0.3),  # 高置信+小误差 = 微好奇
}

# ── 预测误差置信度分界 ───────────────────────────────
CONF_LEVELS = {
    "high":   (0.75, 1.0),
    "medium": (0.4,  0.75),
    "low":    (0.0,  0.4),
}

ERROR_LEVELS = {
    "high":   (0.7,  1.0),
    "medium": (0.3,  0.7),
    "low":    (0.0,  0.3),
}


def _classify(value: float, levels: dict) -> str:
    for name, (lo, hi) in levels.items():
        if lo <= value < hi:
            return name
    return "low"


@dataclass
class PredictionTensionSignal:
    """预测误差 → 尖刺/凹陷信号"""
    ts: str
    ts_unix: float
    # 预测误差信息
    prediction: str
    actual: str
    confidence: float           # 原始置信度
    error_magnitude: float      # 误差幅度 [0, 1]
    # 映射结果
    emotion: str               # 触发的情绪
    tension_type: str          # surface_tension 的 tension_type
    magnitude: float          # 尖刺/凹陷强度
    is_valley: bool            # True=凹陷（好奇），False=尖刺（七情）
    coupling_layer: str         # "外部→欲"
    # 未解追踪
    spike_id: str              # 用于追踪是否已解决


# ── 耦合①：预测误差 → surface_tension ─────────────────

def predict_error_to_tension(
    prediction: str,
    actual: str,
    confidence: float,
    error_magnitude: float,
    context: str = "",
    tags: Optional[list] = None,
) -> PredictionTensionSignal:
    """
    主入口：预测误差事件 → 尖刺/凹陷信号
    由 cognitive_pain_monitor 调用（或外部直接调用）
    """
    conf_level = _classify(confidence, CONF_LEVELS)
    err_level = _classify(error_magnitude, ERROR_LEVELS)

    emotion, spike_intensity = PREDICTION_ERROR_MAP.get(
        (conf_level, err_level),
        ("anxiety", 0.5)
    )

    # 尖刺 vs 凹陷判定
    # 高误差 → 尖刺（七情）; 低误差 → 凹陷（好奇/爱）
    is_valley = err_level == "low" and conf_level != "low"
    tension_type = "insight_found" if is_valley else "steel_conflict"

    sig = PredictionTensionSignal(
        ts=datetime.now(timezone.utc).astimezone().isoformat(),
        ts_unix=time.time(),
        prediction=prediction,
        actual=actual,
        confidence=confidence,
        error_magnitude=error_magnitude,
        emotion=emotion,
        tension_type=tension_type,
        magnitude=round(spike_intensity * (error_magnitude if not is_valley else (1 - error_magnitude)), 3),
        is_valley=is_valley,
        coupling_layer="外部→欲",
        spike_id=f"pred_{int(time.time() * 1000)}",
    )

    _write_unresolved_spike(sig)
    return sig


def _write_unresolved_spike(sig: PredictionTensionSignal):
    """写入未解尖刺追踪文件"""
    UNRESOLVED_SPIKES.parent.mkdir(parents=True, exist_ok=True)
    with open(UNRESOLVED_SPIKES, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(sig), ensure_ascii=False) + "\n")


# ── 耦合②：未解尖刺 → Track B 置信度 ─────────────────

def get_unresolved_tension_score() -> float:
    """
    计算未解尖刺的张力分
    供 dual_track_confidence_updater Track B 使用

    公式：未解尖刺越多 + 越新鲜 + 越强 = 张力越高
    """
    if not UNRESOLVED_SPIKES.exists():
        return 0.0

    try:
        lines = UNRESOLVED_SPIKES.read_text(encoding="utf-8").strip().split("\n")
    except Exception:
        return 0.0

    now = time.time()
    total_tension = 0.0
    count = 0

    for line in lines[-50:]:  # 只看最近50条
        try:
            sig = json.loads(line)
        except Exception:
            continue

        # 只算尖刺，不算凹陷
        if sig.get("is_valley", False):
            continue

        age_hours = (now - sig["ts_unix"]) / 3600
        # 衰减：1小时内满强度，之后每小时减半
        decay = max(0.1, 1.0 - age_hours * 0.1)
        contribution = sig["magnitude"] * decay
        total_tension += contribution
        count += 1

    # 归一化：10个未解尖刺×1.0强度 = 1.0分
    return min(1.0, total_tension / 10.0)


def resolve_spike(spike_id: str, resolution: str):
    """
    标记尖刺已解决（由 cognitive_friction_detector 或置信度更新调用）
    从 unresolved_spikes 移除（改为 resolved）
    """
    if not UNRESOLVED_SPIKES.exists():
        return

    lines = []
    resolved = None
    for line in UNRESOLVED_SPIKES.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            sig = json.loads(line)
        except Exception:
            continue
        if sig.get("spike_id") == spike_id:
            sig["resolved"] = True
            sig["resolution"] = resolution
            sig["resolved_at"] = time.time()
            resolved = sig
        else:
            lines.append(line)

    UNRESOLVED_SPIKES.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 已解决的尖刺 → 写入 surface_tension（消退信号）
    if resolved:
        _emit_valley_from_resolution(resolved)


def _emit_valley_from_resolution(resolved_sig: dict):
    """解决尖刺 → 凹陷信号（"学会了"）"""
    surface_tension_module = _get_surface_tension_module()
    if surface_tension_module:
        # 解决=减少焦虑，喜悦/好奇上升
        surface_tension_module.record(
            tension_type="insight_found",
            magnitude=resolved_sig.get("magnitude", 0.5) * 0.8,
            source="prediction_tension_coupler",
        )


def _get_surface_tension_module():
    try:
        import sys
        sys.path.insert(0, str(WS / "src"))
        import importlib
        mod = importlib.import_module("surface_tension")
        return mod
    except Exception:
        return None


# ── 耦合③：身体状态 → surface_tension 基线 ───────────

def body_state_to_tension() -> dict:
    """
    读取 body_regulation.json
    系统熵高 → 基础张力升高
    由 cron 调用，周期性更新基线
    """
    result = {"updated": False, "baseline_changes": {}}

    try:
        body = json.loads(BODY_STATE.read_text(encoding="utf-8"))
    except Exception:
        return result

    # 从 body_state 提取张力信号
    tension_signals = {}

    # cognitive_pain severity → 尖刺
    cog_pain = body.get("cognitive_pain", {})
    if cog_pain:
        max_severity = cog_pain.get("max_severity", 0.0)
        if max_severity >= 0.5:
            tension_signals["anxiety"] = max_severity * 0.5
        elif max_severity >= 0.3:
            tension_signals["fear"] = max_severity * 0.3

    # 体感环状态 → 系统熵
    intero = body.get("interoceptive_state", {})
    if intero:
        status = intero.get("status", "ok")
        if status == "degraded":
            tension_signals["anxiety"] = tension_signals.get("anxiety", 0.0) + 0.3
            tension_signals["fear"] = tension_signals.get("fear", 0.0) + 0.2
        elif status == "monitor_error":
            tension_signals["fear"] = tension_signals.get("fear", 0.0) + 0.5

    # system_entropy（如果有）
    entropy = body.get("system_entropy", 0.0)
    if entropy > 0.5:
        tension_signals["anxiety"] = tension_signals.get("anxiety", 0.0) + entropy * 0.4

    if not tension_signals:
        return result

    # 写入 surface_tension_state 的 baseline
    try:
        state = json.loads(SURFACE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return result

    baseline = state.get("personality_baseline", {})
    for emotion, delta in tension_signals.items():
        old = baseline.get(emotion, 0.0)
        new = old + delta * 0.1  # 小步修正
        baseline[emotion] = round(max(-2.0, min(3.0, new)), 3)
        result["baseline_changes"][emotion] = f"{old:.3f} → {new:.3f}"

    state["personality_baseline"] = baseline
    state["last_body_feedback"] = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "ts_unix": time.time(),
        "signals": tension_signals,
    }
    SURFACE_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    result["updated"] = True
    return result


# ── 快捷入口：供 cognitive_pain_monitor 集成 ─────────

def pain_prediction_error_to_tension(
    context: str,
    prediction: str,
    actual: str,
    confidence: float,
    tags: Optional[list] = None,
) -> PredictionTensionSignal:
    """
    cognitive_pain_monitor.record_prediction_error() 后调用此函数
    将预测误差同步到欲系统

    计算 error_magnitude:
      - 如果有 actual：string_error = Levenshtein(prediction, actual) / max(len)
      - 如果没有：error_magnitude = 1 - confidence
    """
    if prediction and actual:
        # 简化的字符串误差
        max_len = max(len(prediction), len(actual), 1)
        error_magnitude = 1.0 - (sum(
            p == a for p, a in zip(prediction, actual)
        ) / max_len)
    else:
        error_magnitude = 1.0 - confidence

    error_magnitude = max(0.0, min(1.0, error_magnitude))

    return predict_error_to_tension(
        prediction=prediction,
        actual=actual,
        confidence=confidence,
        error_magnitude=error_magnitude,
        context=context,
        tags=tags,
    )


# ── 测试 ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 预测模型 ↔ 欲系统 耦合测试 ===\n")

    print("① 预测误差 → 尖刺测试")
    cases = [
        ("低置信+大误差", 0.2, 0.85),
        ("高置信+大误差", 0.9, 0.8),
        ("中置信+中误差", 0.55, 0.5),
        ("高置信+小误差", 0.85, 0.2),
    ]
    for name, conf, err in cases:
        sig = predict_error_to_tension(
            prediction="X is Y",
            actual="X is Z",
            confidence=conf,
            error_magnitude=err,
            context="test",
        )
        print(f"  [{name}] confidence={conf} error={err}")
        print(f"    → {sig.emotion}, tension_type={sig.tension_type}, "
              f"mag={sig.magnitude}, is_valley={sig.is_valley}")

    print()
    print("② 未解张力分（Track B 输入）")
    score = get_unresolved_tension_score()
    print(f"  未解张力分: {score:.3f} / 1.0")

    print()
    print("③ 身体状态 → 基线")
    result = body_state_to_tension()
    print(f"  更新: {result['updated']}")
    if result["baseline_changes"]:
        for k, v in result["baseline_changes"].items():
            print(f"    {k}: {v}")
    else:
        print("  (无变化)")
