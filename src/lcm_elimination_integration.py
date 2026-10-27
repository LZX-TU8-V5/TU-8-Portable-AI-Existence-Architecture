"""
lcm_elimination_integration.py - LCM 排除法集成模块

用途：将排除法集成到 LCM (Lossless Context Management)
来源：排除法语义检索 × TU-8 状态机

集成方案：
    当前流程：
        对话 → LCM 压缩 → 保留摘要

    改进流程：
        对话 → 排除法剪枝 → LCM 压缩 → 保留摘要
                 （位运算，快）   （浮点运算，慢）

算力优化：
    - 先用排除法剪枝（位运算）
    - 再对剩余内容压缩（浮点运算）
"""

from typing import List, Tuple, Optional
import json
import os

from state_machine_dimensions import StateVector, calculate_relevance, calculate_timeliness, calculate_novelty, calculate_confidence
from elimination_rules import EliminationRules, EliminationResult
from state_bitmask import StateBitmask


class LCMEliminationIntegration:
    """
    LCM 排除法集成器。

    在 LCM 压缩之前，先用排除法剪枝状态向量，
    只对通过剪枝的内容进行压缩。
    """

    def __init__(
        self,
        relevance_threshold: float = 0.5,
        timeliness_threshold: float = 0.3,
        novelty_threshold: float = 0.3,
        confidence_threshold: float = 0.6
    ):
        """
        初始化集成器。

        Args:
            relevance_threshold: 相关性阈值
            timeliness_threshold: 时效性阈值
            novelty_threshold: 新颖性阈值
            confidence_threshold: 置信度阈值
        """
        # 创建排除规则引擎
        self.rules = EliminationRules(
            relevance_threshold=relevance_threshold,
            timeliness_threshold=timeliness_threshold,
            novelty_threshold=novelty_threshold,
            confidence_threshold=confidence_threshold
        )

        # 创建位掩码编码器
        self.encoder = StateBitmask()

        # 上下文类型（用于动态调整排除顺序）
        self.context_type = "task_focused"  # 默认

    def set_context_type(self, context_type: str):
        """
        设置上下文类型。

        Args:
            context_type: 上下文类型（task_focused/time_sensitive/information_overload/trust_sensitive）
        """
        self.context_type = context_type

        # 动态调整排除顺序
        from elimination_rules import dynamic_order_by_context
        self.rules.set_order(dynamic_order_by_context(context_type))

    def prepare_state_vectors(
        self,
        messages: List[dict],
        task_context: str,
        existing_contents: List[str]
    ) -> List[StateVector]:
        """
        为消息列表准备状态向量。

        Args:
            messages: 消息列表（每个消息包含 content, timestamp 等）
            task_context: 当前任务上下文
            existing_contents: 已拼接内容列表

        Returns:
            状态向量列表
        """
        state_vectors = []

        for msg in messages:
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", 0)

            # 计算各维度分数
            relevance = calculate_relevance(content, task_context)
            timeliness = calculate_timeliness(timestamp)
            novelty = calculate_novelty(content, existing_contents)
            confidence = calculate_confidence(relevance, timeliness, novelty)

            # 创建状态向量
            sv = StateVector(
                relevance=relevance,
                timeliness=timeliness,
                novelty=novelty,
                confidence=confidence
            )

            state_vectors.append(sv)

        return state_vectors

    def prune_before_compression(
        self,
        messages: List[dict],
        task_context: str,
        existing_contents: List[str]
    ) -> Tuple[List[dict], List[dict]]:
        """
        在 LCM 压缩之前剪枝消息。

        Args:
            messages: 消息列表
            task_context: 当前任务上下文
            existing_contents: 已拼接内容列表

        Returns:
            (保留的消息列表, 剪枝的消息列表)
        """
        # 准备状态向量
        state_vectors = self.prepare_state_vectors(
            messages, task_context, existing_contents
        )

        # 评估所有状态向量
        passed_results, eliminated_results = self.rules.batch_evaluate(state_vectors)

        # 分离消息
        retained = []
        pruned = []

        for result in passed_results:
            idx = state_vectors.index(result.state_vector)
            retained.append(messages[idx])

        for result in eliminated_results:
            idx = state_vectors.index(result.state_vector)
            pruned.append({
                "message": messages[idx],
                "reason": result.reason,
                "level": result.level
            })

        return retained, pruned

    def fast_prune_with_bitmask(
        self,
        messages: List[dict],
        task_context: str,
        existing_contents: List[str]
    ) -> List[dict]:
        """
        使用位掩码快速剪枝（O(N) 位运算）。

        Args:
            messages: 消息列表
            task_context: 当前任务上下文
            existing_contents: 已拼接内容列表

        Returns:
            保留的消息列表
        """
        # 准备状态向量
        state_vectors = self.prepare_state_vectors(
            messages, task_context, existing_contents
        )

        # 编码为位掩码
        masks = [self.encoder.encode(sv) for sv in state_vectors]

        # 快速过滤（有效掩码 = 0b1111）
        valid_mask = 0b1111
        retained = []

        for msg, mask in zip(messages, masks):
            if mask & valid_mask == valid_mask:
                retained.append(msg)

        return retained

    def log_pruning_stats(
        self,
        original_count: int,
        retained_count: int,
        eliminated_count: int
    ):
        """
        记录剪枝统计信息。

        Args:
            original_count: 原始消息数
            retained_count: 保留消息数
            eliminated_count: 剪枝消息数
        """
        stats = {
            "original": original_count,
            "retained": retained_count,
            "eliminated": eliminated_count,
            "retention_rate": retained_count / original_count if original_count > 0 else 0.0,
            "pruning_rate": eliminated_count / original_count if original_count > 0 else 0.0
        }

        # 输出统计
        print(f"[LCM Pruning Stats]")
        print(f"  Original: {stats['original']}")
        print(f"  Retained: {stats['retained']} ({stats['retention_rate']:.1%})")
        print(f"  Eliminated: {stats['eliminated']} ({stats['pruning_rate']:.1%})")

        return stats


# CLI 测试入口
if __name__ == "__main__":
    print("=== LCM 排除法集成测试 ===\n")

    # 创建集成器
    integration = LCMEliminationIntegration()

    # 测试消息
    messages = [
        {"content": "Task A is completed", "timestamp": 1782873658},
        {"content": "Old information from last week", "timestamp": 1782273658},
        {"content": "Duplicate content Task A is completed", "timestamp": 1782873659},
        {"content": "New important update", "timestamp": 1782873660}
    ]

    # 准备上下文
    task_context = "Task A completion"
    existing_contents = ["Task A is completed"]

    # 测试剪枝
    print("测试剪枝（规则引擎）:")
    retained, pruned = integration.prune_before_compression(
        messages, task_context, existing_contents
    )
    print(f"  保留: {len(retained)}, 剪枝: {len(pruned)}")

    # 测试快速剪枝
    print(f"\n测试快速剪枝（位掩码）:")
    fast_retained = integration.fast_prune_with_bitmask(
        messages, task_context, existing_contents
    )
    print(f"  保留: {len(fast_retained)}")

    # 记录统计
    print(f"\n剪枝统计:")
    integration.log_pruning_stats(
        original_count=len(messages),
        retained_count=len(retained),
        eliminated_count=len(pruned)
    )

    print("\n[OK] 测试通过")
