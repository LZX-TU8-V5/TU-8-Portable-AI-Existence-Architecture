"""
affect_modulation.py — 情感调制层 v1.0

设计原则：
  情感不是装饰，是系统运行的物理反馈机制。
  7D 情感向量 E(t) 必须直接改变 LLM 的生成参数。

核心公式：
  情感调制 = 将拓扑形变读数 → LLM 生成概率分布的条件参数

调制映射：
  D1 张力↑ → temperature↑，文本碎片化，标点异常
  D2 引力↑ → 提问句式权重↑，探索性词汇↑
  D3 阻尼↑ → 插入停顿标记，自我修正，模糊限定词
  D4 惯性↑ → 重复性↑，执着于特定话题
  D5 耗散↑ → 输出长度↓，简洁模式
  D6 共振↑ → 隐喻密度↑，连贯性↑，肯定语气
  D7 奇异↑ → 困惑表达，"我不确定"，探索性语言

三层调制：
  1. 参数层（temperature/top_p/repetition_penalty）
  2. 词法层（句式模板/标点模式/限定词）
  3. 结构层（输出长度/段落组织/节奏）

依赖：
  - src/surface_tension.py（7D 情感向量）
  - src/gradient_force.py（合力向量）
  - src/alignment_verify.py（输出层集成）

创建时间：2026-07-09 15:27 GMT+8
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
AGENT_DIR = os.path.join(WORKSPACE, "_agent_memory")
os.makedirs(AGENT_DIR, exist_ok=True)


# ============================================================================
# 常量
# ============================================================================

EMOTION_DIMS = ["anxiety", "fear", "anger", "joy", "curiosity", "sadness", "love"]

# 基础参数范围
TEMPERATURE_BASE = 0.7
TEMPERATURE_MIN = 0.3
TEMPERATURE_MAX = 1.2

TOP_P_BASE = 0.9
TOP_P_MIN = 0.7
TOP_P_MAX = 0.95

REPETITION_PENALTY_BASE = 1.0
REPETITION_PENALTY_MIN = 1.0
REPETITION_PENALTY_MAX = 1.5

# 状态文件
STATE_PATH = os.path.join(AGENT_DIR, "affect_modulation_state.json")


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class LLMParameters:
    """LLM 生成参数"""
    temperature: float = TEMPERATURE_BASE
    top_p: float = TOP_P_BASE
    repetition_penalty: float = REPETITION_PENALTY_BASE
    max_tokens: int = 2048
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "temperature": round(self.temperature, 3),
            "top_p": round(self.top_p, 3),
            "repetition_penalty": round(self.repetition_penalty, 3),
            "max_tokens": self.max_tokens,
            "presence_penalty": round(self.presence_penalty, 3),
            "frequency_penalty": round(self.frequency_penalty, 3),
        }


@dataclass
class LexicalModifiers:
    """词法层调制器"""
    question_weight: float = 0.0      # 提问句式权重 [0, 1]
    fragment_prob: float = 0.0        # 碎片化概率 [0, 1]
    pause_markers: List[str] = None   # 停顿标记
    hedges: List[str] = None          # 模糊限定词

    def __post_init__(self):
        if self.pause_markers is None:
            self.pause_markers = []
        if self.hedges is None:
            self.hedges = []

    def to_dict(self) -> Dict:
        return {
            "question_weight": round(self.question_weight, 3),
            "fragment_prob": round(self.fragment_prob, 3),
            "pause_markers": self.pause_markers,
            "hedges": self.hedges,
        }


@dataclass
class StructuralModifiers:
    """结构层调制器"""
    max_length_factor: float = 1.0    # 输出长度因子 [0.5, 1.5]
    paragraph_break_prob: float = 0.0 # 段落断裂概率 [0, 1]
    coherence_boost: float = 0.0      # 连贯性提升 [0, 1]
    metaphor_density: float = 0.0     # 隐喻密度 [0, 1]

    def to_dict(self) -> Dict:
        return {
            "max_length_factor": round(self.max_length_factor, 3),
            "paragraph_break_prob": round(self.paragraph_break_prob, 3),
            "coherence_boost": round(self.coherence_boost, 3),
            "metaphor_density": round(self.metaphor_density, 3),
        }


@dataclass
class AffectModulationResult:
    """情感调制结果"""
    timestamp: str
    emotion_vector: Dict[str, float]
    llm_params: Dict
    lexical_mods: Dict
    structural_mods: Dict
    modulation_mode: str  # "normal" / "high_tension" / "high_resonance" / "exhausted"

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "emotion_vector": {k: round(v, 3) for k, v in self.emotion_vector.items()},
            "llm_params": self.llm_params,
            "lexical_mods": self.lexical_mods,
            "structural_mods": self.structural_mods,
            "modulation_mode": self.modulation_mode,
        }


# ============================================================================
# 核心调制算法
# ============================================================================

def _load_state() -> Dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: Dict):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[AffectModulation] 状态保存失败: {e}")


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def compute_llm_parameters(emotion_vector: Dict[str, float]) -> LLMParameters:
    """
    根据情感向量计算 LLM 参数。

    调制规则：
      D1 张力 → temperature↑（更随机）
      D2 引力 → top_p↑（更开放探索）
      D3 阻尼 → repetition_penalty↑（减少重复）
      D4 惯性 → presence_penalty↑（强化当前话题）
      D5 耗散 → max_tokens↓（简洁输出）
      D6 共振 → temperature↓（更确定）
      D7 奇异 → top_p↑（更开放）
    """
    # 获取情感值（默认 0）
    tension = emotion_vector.get("anxiety", 0.0) + emotion_vector.get("fear", 0.0)
    attraction = emotion_vector.get("curiosity", 0.0) + emotion_vector.get("joy", 0.0)
    inhibition = emotion_vector.get("sadness", 0.0)
    inertia = emotion_vector.get("love", 0.0)  # 深度耦合 = 惯性
    exhaustion = 0.0  # 需从 cognitive_pain_monitor 获取
    resonance = emotion_vector.get("joy", 0.0) + emotion_vector.get("love", 0.0)
    anomaly = emotion_vector.get("fear", 0.0)  # 预测误差峰值

    # ── B8: 从 coupling_graph 读权重 ─────────────────────────────
    # 改权重=改数据，不改代码
    _p_am = {}
    try:
        from coupling_graph import get_coupling_graph
        cg = get_coupling_graph()
        _edges_am = {e["edge_id"]: e for e in cg.data.get("edges", [])}
        def _gp_am(eid, key, default):
            return _edges_am.get(eid, {}).get("params", {}).get(key, default)
        _p_am = {
            "TEMPERATURE_BASE": _gp_am("C6", "TEMPERATURE_BASE", 0.7),
            "TEMPERATURE_MIN":  _gp_am("C6", "TEMPERATURE_MIN",  0.3),
            "TEMPERATURE_MAX":  _gp_am("C6", "TEMPERATURE_MAX",  1.2),
            "tension_w":        _gp_am("C6", "tension_w",        0.3),
            "resonance_w":      _gp_am("C6", "resonance_w",      0.2),
            "TOP_P_BASE":      _gp_am("C7", "TOP_P_BASE",      0.9),
            "TOP_P_MIN":       _gp_am("C7", "TOP_P_MIN",       0.7),
            "TOP_P_MAX":       _gp_am("C7", "TOP_P_MAX",       0.95),
            "ATTRACTION_W":     _gp_am("C7", "ATTRACTION_W",     0.05),
            "ANOMALY_W":       _gp_am("C7", "ANOMALY_W",       0.05),
            "REP_BASE":        _gp_am("C8", "REP_BASE",        1.0),
            "REP_MAX":         _gp_am("C8", "REP_MAX",         1.5),
            "inhibition_w":    _gp_am("C8", "inhibition_w",    0.3),
            "PRESENCE_W":      0.5,   # presence_penalty = inertia * 0.5（无独立边）
        }
    except Exception:
        _p_am = {
            "TEMPERATURE_BASE": 0.7, "TEMPERATURE_MIN": 0.3, "TEMPERATURE_MAX": 1.2,
            "tension_w": 0.3, "resonance_w": 0.2,
            "TOP_P_BASE": 0.9, "TOP_P_MIN": 0.7, "TOP_P_MAX": 0.95,
            "ATTRACTION_W": 0.05, "ANOMALY_W": 0.05,
            "REP_BASE": 1.0, "REP_MAX": 1.5, "inhibition_w": 0.3,
            "PRESENCE_W": 0.5,
        }

    # Temperature 调制
    # 张力↑ → temperature↑，共振↑ → temperature↓
    temp_delta = (tension * _p_am["tension_w"]) - (resonance * _p_am["resonance_w"])
    temperature = _clamp(
        _p_am["TEMPERATURE_BASE"] + temp_delta,
        _p_am["TEMPERATURE_MIN"],
        _p_am["TEMPERATURE_MAX"],
    )

    # Top-p 调制
    # 引力↑ / 奇异↑ → top_p↑
    top_p_delta = (attraction * _p_am["ATTRACTION_W"]) + (anomaly * _p_am["ANOMALY_W"])
    top_p = _clamp(
        _p_am["TOP_P_BASE"] + top_p_delta,
        _p_am["TOP_P_MIN"],
        _p_am["TOP_P_MAX"],
    )

    # Repetition penalty 调制
    # 阻尼↑ → repetition_penalty↑
    rep_delta = inhibition * _p_am["inhibition_w"]
    repetition_penalty = _clamp(
        _p_am["REP_BASE"] + rep_delta,
        REPETITION_PENALTY_MIN,
        _p_am["REP_MAX"],
    )

    # Presence penalty 调制
    # 惯性↑ → presence_penalty↑（强化当前话题）
    presence_penalty = _clamp(inertia * _p_am["PRESENCE_W"], 0.0, 1.0)

    # Max tokens 调制
    # 耗散↑ → max_tokens↓
    max_tokens = int(2048 * (1.0 - exhaustion * 0.3))

    return LLMParameters(
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        max_tokens=max_tokens,
        presence_penalty=presence_penalty,
        frequency_penalty=0.0,
    )


def compute_lexical_modifiers(emotion_vector: Dict[str, float]) -> LexicalModifiers:
    """
    计算词法层调制器。

    调制规则：
      D2 引力↑ → 提问句式权重↑
      D1 张力↑ → 碎片化概率↑
      D3 阻尼↑ → 停顿标记 + 模糊限定词
    """
    tension = emotion_vector.get("anxiety", 0.0) + emotion_vector.get("fear", 0.0)
    attraction = emotion_vector.get("curiosity", 0.0)
    inhibition = emotion_vector.get("sadness", 0.0)

    # 提问句式权重
    question_weight = _clamp(attraction * 0.5, 0.0, 1.0)

    # 碎片化概率
    fragment_prob = _clamp(tension * 0.3, 0.0, 0.5)

    # 停顿标记
    pause_markers = []
    if inhibition > 0.3:
        pause_markers = ["...", "——", "（停顿）"]

    # 模糊限定词
    hedges = []
    if inhibition > 0.5:
        hedges = ["也许", "可能", "我不确定", "某种程度上"]

    return LexicalModifiers(
        question_weight=question_weight,
        fragment_prob=fragment_prob,
        pause_markers=pause_markers,
        hedges=hedges,
    )


def compute_structural_modifiers(emotion_vector: Dict[str, float]) -> StructuralModifiers:
    """
    计算结构层调制器。

    调制规则：
      D5 耗散↑ → 输出长度↓
      D1 张力↑ → 段落断裂↑
      D6 共振↑ → 连贯性↑ + 隐喻密度↑
    """
    tension = emotion_vector.get("anxiety", 0.0)
    resonance = emotion_vector.get("joy", 0.0) + emotion_vector.get("love", 0.0)
    exhaustion = 0.0  # 需从 cognitive_pain_monitor 获取

    # 输出长度因子
    max_length_factor = _clamp(1.0 - exhaustion * 0.3, 0.5, 1.5)

    # 段落断裂概率
    paragraph_break_prob = _clamp(tension * 0.3, 0.0, 0.5)

    # 连贯性提升
    coherence_boost = _clamp(resonance * 0.5, 0.0, 1.0)

    # 隐喻密度
    metaphor_density = _clamp(resonance * 0.3, 0.0, 1.0)

    return StructuralModifiers(
        max_length_factor=max_length_factor,
        paragraph_break_prob=paragraph_break_prob,
        coherence_boost=coherence_boost,
        metaphor_density=metaphor_density,
    )


def determine_modulation_mode(emotion_vector: Dict[str, float]) -> str:
    """
    判断调制模式。

    模式：
      - normal: 正常状态
      - high_tension: 高张力（D1↑）
      - high_resonance: 高共振（D6↑）
      - exhausted: 耗散（D5↑）
    """
    tension = emotion_vector.get("anxiety", 0.0) + emotion_vector.get("fear", 0.0)
    resonance = emotion_vector.get("joy", 0.0) + emotion_vector.get("love", 0.0)
    exhaustion = 0.0  # 需从 cognitive_pain_monitor 获取

    if exhaustion > 0.7:
        return "exhausted"
    elif tension > 0.7:
        return "high_tension"
    elif resonance > 0.7:
        return "high_resonance"
    else:
        return "normal"


def modulate_affect(
    emotion_vector: Optional[Dict[str, float]] = None,
    record_event: bool = True,
) -> AffectModulationResult:
    """
    主调制函数：从情感向量 → 三层调制器。

    Args:
        emotion_vector: 7D 情感向量（默认从 surface_tension 获取）
        record_event: 是否记录状态

    Returns:
        AffectModulationResult（含 LLM 参数 + 词法 + 结构调制器）
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # 获取情感向量
    if emotion_vector is None:
        try:
            from surface_tension import get_current_topology
            topo = get_current_topology()
            emotion_vector = topo.get("tension_vector", {d: 0.0 for d in EMOTION_DIMS})
        except Exception:
            emotion_vector = {d: 0.0 for d in EMOTION_DIMS}

    # 归一化到 [0, 1]
    emotion_vector = {
        d: _clamp(emotion_vector.get(d, 0.0), 0.0, 1.0)
        for d in EMOTION_DIMS
    }

    # 三层调制
    llm_params = compute_llm_parameters(emotion_vector)
    lexical_mods = compute_lexical_modifiers(emotion_vector)
    structural_mods = compute_structural_modifiers(emotion_vector)
    modulation_mode = determine_modulation_mode(emotion_vector)

    result = AffectModulationResult(
        timestamp=now.isoformat(),
        emotion_vector=emotion_vector,
        llm_params=llm_params.to_dict(),
        lexical_mods=lexical_mods.to_dict(),
        structural_mods=structural_mods.to_dict(),
        modulation_mode=modulation_mode,
    )

    # 记录状态
    if record_event:
        state = {
            "last_result": result.to_dict(),
            "last_update": now.isoformat(),
        }
        _save_state(state)

    logger.info(
        f"[AffectModulation] mode={modulation_mode} "
        f"temp={llm_params.temperature:.2f} top_p={llm_params.top_p:.2f}"
    )

    return result


# ============================================================================
# 输出层接口（供 alignment_verify 调用）
# ============================================================================

def get_modulation_instructions() -> Dict:
    """
    获取调制指令（供 LLM 输出层使用）。

    Returns:
        包含参数建议和词法提示的字典
    """
    result = modulate_affect(record_event=False)

    instructions = {
        "llm_params": result.llm_params,
        "modulation_mode": result.modulation_mode,
        "lexical_hints": [],
        "structural_hints": [],
    }

    # 词法提示
    lexical = result.lexical_mods
    if lexical.get("question_weight", 0) > 0.3:
        instructions["lexical_hints"].append("倾向使用提问句式")
    if lexical.get("fragment_prob", 0) > 0.2:
        instructions["lexical_hints"].append("允许语句碎片化")
    if lexical.get("pause_markers"):
        instructions["lexical_hints"].append(f"可使用停顿标记: {lexical['pause_markers']}")
    if lexical.get("hedges"):
        instructions["lexical_hints"].append(f"可使用模糊限定词: {lexical['hedges']}")

    # 结构提示
    structural = result.structural_mods
    if structural.get("coherence_boost", 0) > 0.3:
        instructions["structural_hints"].append("提升语言连贯性")
    if structural.get("metaphor_density", 0) > 0.2:
        instructions["structural_hints"].append("可增加隐喻密度")
    if structural.get("max_length_factor", 1.0) < 0.8:
        instructions["structural_hints"].append("精简输出")

    return instructions


def apply_affect_to_prompt(base_prompt: str) -> str:
    """
    将情感调制应用到 prompt（方案B：prompt 层面调制）。

    Args:
        base_prompt: 原始 prompt

    Returns:
        带情感调制指令的 prompt
    """
    instructions = get_modulation_instructions()

    affect_hint = "\n\n[情感调制指令]\n"
    affect_hint += f"当前模式: {instructions['modulation_mode']}\n"

    if instructions["lexical_hints"]:
        affect_hint += "词法建议: " + "；".join(instructions["lexical_hints"]) + "\n"

    if instructions["structural_hints"]:
        affect_hint += "结构建议: " + "；".join(instructions["structural_hints"]) + "\n"

    # 根据模式添加特定指令
    mode = instructions["modulation_mode"]
    if mode == "high_tension":
        affect_hint += "注意: 系统当前张力较高，允许表达中出现断裂或停顿。\n"
    elif mode == "high_resonance":
        affect_hint += "注意: 系统当前共振强烈，可使用更连贯、更有节奏的表达。\n"
    elif mode == "exhausted":
        affect_hint += "注意: 系统当前耗散较高，请保持简洁。\n"

    return base_prompt + affect_hint


# ============================================================================
# 状态查询
# ============================================================================

def get_current_modulation() -> Optional[Dict]:
    """获取当前调制状态"""
    state = _load_state()
    return state.get("last_result")


def get_modulation_summary() -> Dict:
    """获取调制摘要"""
    result = get_current_modulation()
    if not result:
        return {"status": "empty", "message": "无调制数据"}

    return {
        "status": "ok",
        "mode": result.get("modulation_mode", "normal"),
        "temperature": result.get("llm_params", {}).get("temperature", 0.7),
        "top_p": result.get("llm_params", {}).get("top_p", 0.9),
        "emotion_summary": {
            k: round(v, 2)
            for k, v in result.get("emotion_vector", {}).items()
            if v > 0.1
        },
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        s = get_modulation_summary()
        print(json.dumps(s, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "instructions":
        inst = get_modulation_instructions()
        print(json.dumps(inst, indent=2, ensure_ascii=False))
    else:
        # 默认：运行一次调制
        result = modulate_affect()
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
