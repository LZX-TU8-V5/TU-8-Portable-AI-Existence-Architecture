"""
seal_to_gc_adapter.py — T2→T4 中间件：钢印加权影响 GC 评分

功能：
  当 GC 评分 MEMORY.md 段落时，查该段落是否有关联钢印。
  有钢印背书的段落获得 score 加成（最高 +0.15），降低被归档概率。

设计决策：
  - 不修改 GC 核心公式，只在 _metabolic_score() 返回值上加 seal_bonus
  - 映射策略：段落标题关键词与钢印 summary 做匹配（轻量级）
  - 将来可升级为语义匹配
"""

import json
import os
import re
import time
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.environ.get("QCLAW_WORKSPACE",
    os.path.expanduser("~/.qclaw/workspace"))))

SEAL_INDEX = WORKSPACE / "memory" / "time_chain" / "seal_index.json"

# 钢印类型到加权的映射
SEAL_TYPE_WEIGHT = {
    "response": 0.10,           # 响应钢印 → 基础背书
    "deep_sleep": 0.05,         # 深睡期钢印 → 弱背书
    "memory_to_seal": 0.08,     # 记忆→钢印 → 中等
    "conflict": 0.12,           # 冲突钢印 → 重要
    "error": 0.10,              # 错误钢印 → 需要记住
    "learning:alert": 0.12,     # 学习产物告警
    "learning:intuition": 0.10, # 学习产物直觉
    "learning:preference": 0.08,# 学习产物偏好
    "learning:memo": 0.06,      # 学习产物备忘
    "learning:rule": 0.10,      # 学习产物规则
    "default": 0.05,            # 未知类型 - 弱背书
}

# 钢印场景标签到主题匹配词的映射
SCENE_TOPICS = {
    "learning:alert": ["异常", "异常检测", "anomaly", "alert", "monitor", "监控"],
    "learning:intuition": ["直觉", "intuition", "模式", "模式识别", "pattern"],
    "learning:preference": ["偏好", "preference", "偏好", "profile", "user", "用户"],
    "learning:memo": ["笔记", "memo", "存档", "archive"],
    "learning:rule": ["规则", "rule", "规范", "约束", "methodology", "方法论"],
    "response": ["决策", "response", "回复", "对话"],
    "conflict": ["冲突", "conflict", "矛盾", "争议", "align"],
    "error": ["错误", "bug", "error", "故障", "失败"],
    "memory_to_seal": ["记忆", "记忆提取", "memory"],
    "deep_sleep": ["深睡", "梦境", "代谢", "gc", "dream"],
    "default": [],
}


_keywords_cache = None
_cache_time = 0


def _load_seal_keywords() -> list[tuple[str, float]]:
    """
    加载所有钢印及其加权因子，提取主题匹配词。

    不再使用摘要关键词（摘要内容与段落标题无交集），
    改用场景标签推导的主题词。

    返回: [(keyword, weight), ...]
    """
    global _keywords_cache, _cache_time

    now = time.time()
    if _keywords_cache and (now - _cache_time) < 300:
        return _keywords_cache

    if not SEAL_INDEX.exists():
        _keywords_cache = []
        _cache_time = now
        return []

    try:
        seals = json.loads(SEAL_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _keywords_cache = []
        _cache_time = now
        return []

    if isinstance(seals, dict):
        seals = list(seals.values())

    keywords = []
    for s in (seals if isinstance(seals, list) else []):
        scene = s.get("scene_tag", "")
        weight = SEAL_TYPE_WEIGHT.get(scene, SEAL_TYPE_WEIGHT["default"])

        # 从场景标签推导主题词
        scene_key = scene.split(":")[0] if ":" in scene else scene
        topics = SCENE_TOPICS.get(scene, SCENE_TOPICS.get(scene_key, []))

        for topic in topics:
            keywords.append((topic.lower(), weight))

    # 合并重复（取最高权重）
    merged = {}
    for kw, w in keywords:
        merged[kw] = max(merged.get(kw, 0), w)

    _keywords_cache = list(merged.items())
    _cache_time = now
    return _keywords_cache


def compute_seal_bonus(section_title: str, section_content: str = "") -> float:
    """
    计算给定段落的钢印加权奖励分。

    参数:
        section_title: 段落标题（GC 的 meta.title）
        section_content: 段落全文（可选，更精确匹配）

    返回:
        bonus: 0.0 ~ 0.15 的加权奖励
    """
    keywords = _load_seal_keywords()
    if not keywords:
        return 0.0

    # 在标题和内容中匹配钢印关键词
    combined = section_title + " " + section_content
    matched_weights = []

    for kw, w in keywords:
        if kw in combined.lower():
            matched_weights.append(w)

    if not matched_weights:
        return 0.0

    # 取最高权重（一条强匹配钢印比多条弱匹配更有意义）
    max_weight = max(matched_weights)
    # 上限 0.15
    return min(max_weight, 0.15)


def hook_metabolic_score(original_score: float, section_title: str, 
                         section_content: str = "") -> float:
    """
    GC 评分钩子：在原 _metabolic_score 返回值上叠加钢印奖励。

    用法:
        final_score = hook_metabolic_score(orig_score, title, content)
        然后传入 _recommend_action(final_score, age)
    """
    bonus = compute_seal_bonus(section_title, section_content)
    if bonus > 0:
        print(f"[T2→T4] seal_bonus: {bonus} -> {section_title[:40]}")
    return original_score + bonus


if __name__ == "__main__":
    # 测试
    keywords = _load_seal_keywords()
    print(f"Seal keywords: {len(keywords)} loaded")

    titles = ["2026-07-01 千问对话", "旧日志 6月", "2026-07-05 学习链"]
    for t in titles:
        b = compute_seal_bonus(t)
        print(f"  '{t}': bonus={b}")
