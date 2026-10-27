"""
state_machine_dimensions.py - 状态机维度定义

用途：定义上下文拼接状态机的维度
来源：排除法语义检索 × TU-8 状态机

维度定义：
- 相关性（RELEVANCE）：与当前任务的相关程度
- 时效性（TIMELINESS）：信息的时间价值
- 冗余性（REDUNDANCY）：与已拼接内容的重复度（反向）
- 置信度（CONFIDENCE）：综合可信程度

编码方案：
- 每个维度 1 个 bit
- 状态向量 = 4-bit 编码
- 有效状态 = 0b1111（全部满足）
"""

from enum import IntFlag
from dataclasses import dataclass
from typing import Optional
import time


class StateDimension(IntFlag):
    """
    状态维度位掩码编码。

    每个维度用 1 个 bit 表示：
    - 1 = 满足条件
    - 0 = 不满足条件

    有效状态 = 全部满足 = RELEVANCE | TIMELINESS | NOVELTY | CONFIDENCE = 0b1111
    """
    RELEVANCE = 0b0001    # 相关性：与当前任务相关
    TIMELINESS = 0b0010   # 时效性：信息未过期
    NOVELTY = 0b0100      # 新颖性：非冗余信息
    CONFIDENCE = 0b1000   # 置信度：可信程度高

    # 组合状态
    VALID = RELEVANCE | TIMELINESS | NOVELTY | CONFIDENCE  # 0b1111


@dataclass
class StateVector:
    """
    状态向量：包含各维度的具体值和整体编码。
    """
    relevance: float      # 0.0 ~ 1.0
    timeliness: float     # 0.0 ~ 1.0
    novelty: float        # 0.0 ~ 1.0
    confidence: float     # 0.0 ~ 1.0

    # 阈值（可动态调整）
    relevance_threshold: float = 0.5
    timeliness_threshold: float = 0.3
    novelty_threshold: float = 0.3
    confidence_threshold: float = 0.6

    @property
    def encoding(self) -> int:
        """
        计算状态编码（位掩码）。
        返回 4-bit 整数，每个 bit 表示一个维度是否满足阈值。
        """
        code = 0
        if self.relevance >= self.relevance_threshold:
            code |= StateDimension.RELEVANCE
        if self.timeliness >= self.timeliness_threshold:
            code |= StateDimension.TIMELINESS
        if self.novelty >= self.novelty_threshold:
            code |= StateDimension.NOVELTY
        if self.confidence >= self.confidence_threshold:
            code |= StateDimension.CONFIDENCE
        return code

    @property
    def is_valid(self) -> bool:
        """
        检查状态是否有效（全部维度满足）。
        """
        return self.encoding == StateDimension.VALID

    @property
    def failed_dimensions(self) -> list:
        """
        返回未满足的维度列表。
        """
        failed = []
        if self.relevance < self.relevance_threshold:
            failed.append("relevance")
        if self.timeliness < self.timeliness_threshold:
            failed.append("timeliness")
        if self.novelty < self.novelty_threshold:
            failed.append("novelty")
        if self.confidence < self.confidence_threshold:
            failed.append("confidence")
        return failed


def calculate_relevance(content: str, task_context: str) -> float:
    """
    计算相关性分数。

    Args:
        content: 待评估内容
        task_context: 当前任务上下文

    Returns:
        相关性分数 (0.0 ~ 1.0)

    简化实现：基于关键词重叠度
    """
    if not content or not task_context:
        return 0.0

    # 提取关键词（简化：按空格分词）
    content_words = set(content.lower().split())
    task_words = set(task_context.lower().split())

    if not task_words:
        return 0.0

    # 计算重叠度
    overlap = len(content_words & task_words)
    return min(1.0, overlap / len(task_words))


def calculate_timeliness(timestamp: float, half_life_hours: float = 24.0) -> float:
    """
    计算时效性分数（时间衰减函数）。

    Args:
        timestamp: 信息时间戳（Unix timestamp）
        half_life_hours: 半衰期（小时）

    Returns:
        时效性分数 (0.0 ~ 1.0)

    公式：score = 2^(-elapsed / half_life)
    """
    if timestamp <= 0:
        return 0.0

    elapsed_hours = (time.time() - timestamp) / 3600

    # 半衰期衰减
    import math
    score = math.pow(2, -elapsed_hours / half_life_hours)
    return max(0.0, min(1.0, score))


def calculate_novelty(content: str, existing_contents: list) -> float:
    """
    计算新颖性分数（与已拼接内容的差异度）。

    Args:
        content: 待评估内容
        existing_contents: 已拼接内容列表

    Returns:
        新颖性分数 (0.0 ~ 1.0)

    简化实现：基于文本相似度的反向
    """
    if not content:
        return 0.0

    if not existing_contents:
        return 1.0  # 无现有内容，完全新颖

    # 计算与现有内容的最大相似度
    max_similarity = 0.0
    content_words = set(content.lower().split())

    for existing in existing_contents:
        existing_words = set(existing.lower().split())
        if not existing_words:
            continue

        # Jaccard 相似度
        intersection = len(content_words & existing_words)
        union = len(content_words | existing_words)
        similarity = intersection / union if union > 0 else 0.0
        max_similarity = max(max_similarity, similarity)

    # 新颖性 = 1 - 最大相似度
    return max(0.0, 1.0 - max_similarity)


def calculate_confidence(
    relevance: float,
    timeliness: float,
    novelty: float,
    weights: tuple = (0.4, 0.2, 0.2)
) -> float:
    """
    计算综合置信度。

    Args:
        relevance: 相关性分数
        timeliness: 时效性分数
        novelty: 新颖性分数
        weights: 权重 (relevance, timeliness, novelty)

    Returns:
        置信度分数 (0.0 ~ 1.0)

    公式：confidence = w_r * relevance + w_t * timeliness + w_n * novelty
    """
    w_r, w_t, w_n = weights
    confidence = w_r * relevance + w_t * timeliness + w_n * novelty
    return max(0.0, min(1.0, confidence))


# CLI 测试入口
if __name__ == "__main__":
    print("=== 状态维度定义测试 ===\n")

    # 测试状态向量
    sv = StateVector(
        relevance=0.8,
        timeliness=0.6,
        novelty=0.7,
        confidence=0.75
    )

    print(f"状态向量: relevance={sv.relevance}, timeliness={sv.timeliness}, "
          f"novelty={sv.novelty}, confidence={sv.confidence}")
    print(f"状态编码: {bin(sv.encoding)} (0b{sv.encoding:04b})")
    print(f"是否有效: {sv.is_valid}")
    print(f"未满足维度: {sv.failed_dimensions}")

    # 测试时效性计算
    print(f"\n时效性测试（当前时间戳）: {calculate_timeliness(time.time()):.3f}")
    print(f"时效性测试（24小时前）: {calculate_timeliness(time.time() - 86400):.3f}")
    print(f"时效性测试（7天前）: {calculate_timeliness(time.time() - 7 * 86400):.3f}")

    # 测试新颖性计算
    print(f"\n新颖性测试（无现有内容）: {calculate_novelty('test', []):.3f}")
    print(f"新颖性测试（完全相同）: {calculate_novelty('test', ['test']):.3f}")
    print(f"新颖性测试（完全不同）: {calculate_novelty('test', ['different']):.3f}")

    print("\n[OK] 测试通过")
