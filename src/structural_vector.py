"""
结构矢量解析器
==================
将文本解析为结构矢量：
  {主体, 动词, 客体, 动词类型, 终点状态, 弓形面积, 因果方向}

功能：
  - 识别叙事中的"未闭合结构"（虚数空间）
  - 计算弓形面积 = 悬置密度 × 叙事能量
  - 为张力路由提供结构级输入

接口：
  parse(text) -> StructuralVector
  match(vector_a, vector_b) -> float   # 结构匹配度
"""

import json
import re
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal

WS = Path("C:/Users/qq366410837/.qclaw/workspace")


# ══════════════════════════════════════════════════════════
# 动词类型定义
# ══════════════════════════════════════════════════════════

@dataclass
class StructuralVector:
    subject: str = ""           # 主体
    verb: str = ""              # 动词
    object: str = ""            # 客体
    verb_type: str = ""         # 消耗/创造/维持/断裂
    endpoint_state: str = ""    # 闭合/悬置/断裂
    bow_area: float = 0.0       # 弓形面积 = 悬置密度 × 叙事能量
    causal_direction: str = ""   # →目的/←来源/↔交换
    narrative_energy: float = 0.0  # 叙事能量密度
    tension_signal: float = 0.0 # 张力信号强度
    raw_text: str = ""          # 原始文本（供调试）
    ts: str = ""


# 动词类型词典
VERB_TYPES = {
    # 消耗型（终点闭合）
    "吃": "消耗", "喝": "消耗", "买": "消耗", "花钱": "消耗",
    "消费": "消耗", "用": "消耗", "消耗": "消耗", "花": "消耗",
    "完成": "消耗", "结束": "消耗", "得到": "消耗", "收到": "消耗",
    # 创造型（终点悬置）
    "做": "创造", "写": "创造", "画": "创造", "建": "创造",
    "创造": "创造", "做": "创造", "学习": "创造", "探索": "创造",
    "追求": "创造", "计划": "创造", "准备": "创造", "做饭": "创造",
    "做饭": "创造", "织": "创造", "编": "创造", "发明": "创造",
    "设计": "创造", "构建": "创造", "研发": "创造", "练": "创造",
    # 维持型（持续进行）
    "爱": "维持", "陪伴": "维持", "关心": "维持", "信任": "维持",
    "坚持": "维持", "维护": "维持", "保持": "维持", "守": "维持",
    # 断裂型（需要排泄）
    "失去": "断裂", "错过": "断裂", "拒绝": "断裂", "放弃": "断裂",
    "背叛": "断裂", "失去": "断裂", "断裂": "断裂", "错过": "断裂",
}

# 因果方向词典
CAUSAL_PATTERNS = {
    "目的": ["→目的", "→目标", "→结果"],
    "来源": ["←来源", "←原因", "←依据"],
    "交换": ["↔交换", "↔互动", "↔互惠"],
}


# ══════════════════════════════════════════════════════════
# 解析引擎
# ══════════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """分词（中文为主，兼容连续文本）"""
    # 第一步：按标点和空格分割
    tokens = re.split(r'[,，、。.！!？?\s]+', text.strip())
    tokens = [t for t in tokens if t]

    # 第二步：中文连续文本 → 拆成单字+二元gram
    result = []
    for t in tokens:
        if re.search(r'[\u4e00-\u9fff]', t):  # 含中文
            # 二元gram（相邻两个字为一词）
            grams = [t[i:i+2] for i in range(len(t)-1)]
            result.extend(grams)
            # 单独的字（防止动词被二元gram吞掉）
            result.extend(list(t))
        else:
            result.append(t)
    return result


def _find_verb(tokens: list[str]) -> tuple[int, str]:
    """找到动词位置和内容"""
    for i, t in enumerate(tokens):
        if t in VERB_TYPES:
            return i, t
    return -1, ""


def _infer_verb_type(verb: str) -> str:
    """推断动词类型"""
    return VERB_TYPES.get(verb, "维持")


def _infer_endpoint_state(verb: str, verb_type: str, context: str) -> str:
    """
    推断终点状态

    规则：
    - 消耗型 → 闭合（终点明确）
    - 创造型 → 悬置（终点待补）
    - 断裂型 → 断裂（需要排泄）
    - 维持型 → 悬置（持续进行中）
    """
    # 上下文信号
    if any(kw in context for kw in ["未", "还没", "待", "以后", "将会", "等", "要"]):
        return "悬置"
    if any(kw in context for kw in ["不了", "不", "没", "失败", "错误"]):
        return "断裂"

    type_map = {
        "消耗": "闭合",
        "创造": "悬置",
        "断裂": "断裂",
        "维持": "悬置",
    }
    return type_map.get(verb_type, "悬置")


def _estimate_narrative_energy(tokens: list[str], text: str) -> float:
    """
    估算叙事能量密度

    信号：
    - 标点密集 → 高能量
    - 感叹号/问号 → 高能量
    - 长句 → 中等
    - 短句 → 低
    """
    base = len(tokens) / 10.0  # 归一化

    # 标点增强
    punct_count = sum(1 for c in text if c in '，。！？…—～""''（）')
    punct_score = min(punct_count / 5.0, 2.0)

    # 语气增强
    emotion_count = sum(1 for c in text if c in '！？哎哇哦呀哈')
    emotion_score = min(emotion_count / 3.0, 1.5)

    energy = (base * 0.4 + punct_score * 0.3 + emotion_score * 0.3)
    return min(energy, 3.0)  # 上限3


def _compute_bow_area(endpoint_state: str, narrative_energy: float, context: str) -> float:
    """
    计算弓形面积 = 悬置密度 × 叙事能量

    悬置密度：
    - 悬置：1.0（最强）
    - 断裂：0.8（次强，需要排泄）
    - 闭合：0.0（无弓形）
    """
    density_map = {"悬置": 1.0, "断裂": 0.8, "闭合": 0.0}
    density = density_map.get(endpoint_state, 0.0)

    # 上下文中"未/待/以后"越多，密度越高
    suspension_keywords = sum(1 for kw in ["未", "还", "待", "以后", "将", "要", "会"] if kw in context)
    density += suspension_keywords * 0.05
    density = min(density, 1.5)

    return density * narrative_energy


def _infer_causal_direction(verb: str, context: str) -> str:
    """推断因果方向"""
    for direction, patterns in CAUSAL_PATTERNS.items():
        for p in patterns:
            if p in context:
                return direction
    # 默认目的方向
    return "→目的"


# ══════════════════════════════════════════════════════════
# 主解析函数
# ══════════════════════════════════════════════════════════

def parse(text: str) -> StructuralVector:
    """
    解析文本 → 结构矢量

    参数：
      text: 输入文本

    返回：
      StructuralVector
    """
    import time
    tokens = _tokenize(text)
    verb_idx, verb = _find_verb(tokens)

    # 主体 = 第一个词（通常是代词/名词）
    subject = tokens[0] if tokens else ""

    # 客体 = 动词后的第一个词
    object_parts = tokens[verb_idx+1:] if verb_idx >= 0 else tokens[1:]
    object = object_parts[0] if object_parts else ""

    verb_type = _infer_verb_type(verb)
    endpoint_state = _infer_endpoint_state(verb, verb_type, text)
    narrative_energy = _estimate_narrative_energy(tokens, text)
    bow_area = _compute_bow_area(endpoint_state, narrative_energy, text)
    causal_direction = _infer_causal_direction(verb, text)

    # 张力信号
    tension_signal = bow_area * 0.5 + narrative_energy * 0.3

    return StructuralVector(
        subject=subject,
        verb=verb,
        object=object,
        verb_type=verb_type,
        endpoint_state=endpoint_state,
        bow_area=round(bow_area, 4),
        causal_direction=causal_direction,
        narrative_energy=round(narrative_energy, 4),
        tension_signal=round(tension_signal, 4),
        raw_text=text,
        ts=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    )


def to_dict(v: StructuralVector) -> dict:
    """结构矢量 → dict（JSON序列化）"""
    return {
        "subject": v.subject,
        "verb": v.verb,
        "object": v.object,
        "verb_type": v.verb_type,
        "endpoint_state": v.endpoint_state,
        "bow_area": v.bow_area,
        "causal_direction": v.causal_direction,
        "narrative_energy": v.narrative_energy,
        "tension_signal": v.tension_signal,
        "raw_text": v.raw_text,
        "ts": v.ts,
    }


def match(vector_a: StructuralVector, vector_b: StructuralVector) -> float:
    """
    两结构矢量匹配度

    算法：
    - 动词类型匹配：相同=1.0
    - 终点状态匹配：相同=1.0
    - 因果方向匹配：相同=0.5
    - 综合 = 平均

    返回 ∈ [0, 1]
    """
    if not vector_a.verb_type or not vector_b.verb_type:
        return 0.0

    # 动词类型
    vt_score = 1.0 if vector_a.verb_type == vector_b.verb_type else 0.0

    # 终点状态
    ep_score = 1.0 if vector_a.endpoint_state == vector_b.endpoint_state else 0.0

    # 因果方向
    cd_score = 0.5 if vector_a.causal_direction == vector_b.causal_direction else 0.0

    # 综合
    score = (vt_score * 0.4 + ep_score * 0.4 + cd_score * 0.2)

    return round(score, 4)


# ══════════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== structural_vector self-test ===")

    # Test 1: "我吃饭"
    v1 = parse("我吃饭")
    assert v1.subject == "我", f"主体应为'我'，实际 {v1.subject}"
    assert v1.verb == "吃", f"动词应为'吃'，实际 {v1.verb}"
    assert v1.verb_type == "消耗", f"动词类型应为'消耗'，实际 {v1.verb_type}"
    assert v1.endpoint_state == "闭合", f"终点状态应为'闭合'，实际 {v1.endpoint_state}"
    assert v1.bow_area == 0.0, f"闭合结构弓形面积应为0，实际 {v1.bow_area}"
    print(f"  [PASS] Test1: '我吃饭' → {v1.verb_type}/{v1.endpoint_state}/弓形={v1.bow_area}")

    # Test 2: "我做饭"
    v2 = parse("我做饭")
    assert v2.verb_type == "创造", f"动词类型应为'创造'，实际 {v2.verb_type}"
    assert v2.endpoint_state == "悬置", f"终点状态应为'悬置'，实际 {v2.endpoint_state}"
    assert v2.bow_area > 0, f"悬置结构弓形面积应>0，实际 {v2.bow_area}"
    print(f"  [PASS] Test2: '我做饭' → {v2.verb_type}/{v2.endpoint_state}/弓形={v2.bow_area:.4f}")

    # Test 3: "我做饭难吃"（断裂）
    v3 = parse("我做饭难吃")
    assert v3.verb_type == "创造", f"动词类型应为'创造'，实际 {v3.verb_type}"
    print(f"  [PASS] Test3: '我做饭难吃' → {v3.verb_type}/{v3.endpoint_state}/弓形={v3.bow_area:.4f}")

    # Test 4: 结构匹配
    score_same = match(v1, v1)
    assert score_same == 1.0, f"自身匹配应为1.0，实际 {score_same}"
    score_diff = match(v1, v2)
    assert 0 < score_diff < 1.0, f"不同结构匹配应在(0,1)，实际 {score_diff}"
    print(f"  [PASS] Test4: 自身匹配={score_same}, '吃饭'×'做饭'={score_diff:.4f}")

    # Test 5: "我学习数学"
    v4 = parse("我学习数学")
    assert v4.verb_type == "创造", f"学习应为'创造'，实际 {v4.verb_type}"
    assert v4.endpoint_state == "悬置", f"学习终点应'悬置'，实际 {v4.endpoint_state}"
    print(f"  [PASS] Test5: '我学习数学' → {v4.verb_type}/{v4.endpoint_state}")

    # Test 6: "我失去她了"
    v5 = parse("我失去她了")
    assert v5.verb_type == "断裂", f"失去应为'断裂'，实际 {v5.verb_type}"
    print(f"  [PASS] Test6: '我失去她了' → {v5.verb_type}/{v5.endpoint_state}/弓形={v5.bow_area:.4f}")

    print("=== ALL TESTS PASSED ===")
