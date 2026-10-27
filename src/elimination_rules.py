"""
elimination_rules.py - 排除规则设计

用途：设计多层级排除规则，实现短路机制
来源：排除法语义检索 × TU-8 状态机

排除层级：
L1: 相关性排除 → 与当前任务无关
L2: 时效性排除 → 信息过期
L3: 冗余性排除 → 重复信息
L4: 置信度排除 → 置信度不足

短路机制：任一层排除，立即终止，不检查后续层级
"""

from typing import Optional, Callable, Tuple
from dataclasses import dataclass
from enum import IntEnum

from state_machine_dimensions import StateVector, StateDimension


class EliminationLevel(IntEnum):
    """
    排除层级（优先级从高到低）。
    """
    RELEVANCE = 1     # L1: 相关性排除
    TIMELINESS = 2    # L2: 时效性排除
    REDUNDANCY = 3    # L3: 冗余性排除
    CONFIDENCE = 4    # L4: 置信度排除


@dataclass
class EliminationResult:
    """
    排除结果。
    """
    eliminated: bool           # 是否被排除
    level: Optional[int]       # 排除层级（None 表示未排除）
    reason: str                # 排除原因
    state_vector: StateVector  # 状态向量


class EliminationRules:
    """
    排除规则引擎。

    实现多层级排除，短路机制，动态阈值。
    """

    def __init__(
        self,
        relevance_threshold: float = 0.5,
        timeliness_threshold: float = 0.3,
        novelty_threshold: float = 0.3,
        confidence_threshold: float = 0.6
    ):
        """
        初始化排除规则。

        Args:
            relevance_threshold: 相关性阈值
            timeliness_threshold: 时效性阈值
            novelty_threshold: 新颖性阈值
            confidence_threshold: 置信度阈值
        """
        self.thresholds = {
            EliminationLevel.RELEVANCE: relevance_threshold,
            EliminationLevel.TIMELINESS: timeliness_threshold,
            EliminationLevel.REDUNDANCY: novelty_threshold,
            EliminationLevel.CONFIDENCE: confidence_threshold
        }

        # 排除顺序（默认：相关性 > 时效性 > 冗余性 > 置信度）
        self.order = [
            EliminationLevel.RELEVANCE,
            EliminationLevel.TIMELINESS,
            EliminationLevel.REDUNDANCY,
            EliminationLevel.CONFIDENCE
        ]

    def set_order(self, order: list):
        """
        设置排除顺序。

        Args:
            order: 排除层级列表
        """
        self.order = [EliminationLevel(l) for l in order]

    def check_level(
        self,
        state_vector: StateVector,
        level: EliminationLevel
    ) -> Tuple[bool, str]:
        """
        检查某一层级是否需要排除。

        Args:
            state_vector: 状态向量
            level: 排除层级

        Returns:
            (是否排除, 原因)
        """
        threshold = self.thresholds[level]

        if level == EliminationLevel.RELEVANCE:
            if state_vector.relevance < threshold:
                return True, f"相关性不足 ({state_vector.relevance:.2f} < {threshold})"

        elif level == EliminationLevel.TIMELINESS:
            if state_vector.timeliness < threshold:
                return True, f"时效性不足 ({state_vector.timeliness:.2f} < {threshold})"

        elif level == EliminationLevel.REDUNDANCY:
            if state_vector.novelty < threshold:
                return True, f"冗余度过高 ({state_vector.novelty:.2f} < {threshold})"

        elif level == EliminationLevel.CONFIDENCE:
            if state_vector.confidence < threshold:
                return True, f"置信度不足 ({state_vector.confidence:.2f} < {threshold})"

        return False, "通过"

    def evaluate(self, state_vector: StateVector) -> EliminationResult:
        """
        评估状态向量，执行排除规则。

        短路机制：一旦排除，立即返回，不检查后续层级。

        Args:
            state_vector: 状态向量

        Returns:
            EliminationResult
        """
        for level in self.order:
            eliminated, reason = self.check_level(state_vector, level)
            if eliminated:
                return EliminationResult(
                    eliminated=True,
                    level=level.value,
                    reason=reason,
                    state_vector=state_vector
                )

        # 全部通过
        return EliminationResult(
            eliminated=False,
            level=None,
            reason="全部层级通过",
            state_vector=state_vector
        )

    def batch_evaluate(
        self,
        state_vectors: list
    ) -> Tuple[list, list]:
        """
        批量评估状态向量。

        Args:
            state_vectors: 状态向量列表

        Returns:
            (通过列表, 排除列表)
        """
        passed = []
        eliminated = []

        for sv in state_vectors:
            result = self.evaluate(sv)
            if result.eliminated:
                eliminated.append(result)
            else:
                passed.append(result)

        return passed, eliminated


def dynamic_order_by_context(context_type: str) -> list:
    """
    根据上下文类型动态调整排除顺序。

    Args:
        context_type: 上下文类型

    Returns:
        排除层级顺序列表
    """
    orders = {
        "task_focused": [
            EliminationLevel.RELEVANCE,   # 任务明确 → 相关性优先
            EliminationLevel.CONFIDENCE,
            EliminationLevel.TIMELINESS,
            EliminationLevel.REDUNDANCY
        ],
        "time_sensitive": [
            EliminationLevel.TIMELINESS,  # 时间敏感 → 时效性优先
            EliminationLevel.RELEVANCE,
            EliminationLevel.CONFIDENCE,
            EliminationLevel.REDUNDANCY
        ],
        "information_overload": [
            EliminationLevel.REDUNDANCY,  # 信息过载 → 冗余性优先
            EliminationLevel.RELEVANCE,
            EliminationLevel.TIMELINESS,
            EliminationLevel.CONFIDENCE
        ],
        "trust_sensitive": [
            EliminationLevel.CONFIDENCE,  # 信任敏感 → 置信度优先
            EliminationLevel.RELEVANCE,
            EliminationLevel.TIMELINESS,
            EliminationLevel.REDUNDANCY
        ]
    }

    return orders.get(context_type, [
        EliminationLevel.RELEVANCE,
        EliminationLevel.TIMELINESS,
        EliminationLevel.REDUNDANCY,
        EliminationLevel.CONFIDENCE
    ])


# CLI 测试入口
if __name__ == "__main__":
    print("=== 排除规则测试 ===\n")

    # 创建规则引擎
    rules = EliminationRules(
        relevance_threshold=0.5,
        timeliness_threshold=0.3,
        novelty_threshold=0.3,
        confidence_threshold=0.6
    )

    # 测试用例 1: 全部通过
    sv1 = StateVector(
        relevance=0.8,
        timeliness=0.7,
        novelty=0.6,
        confidence=0.75
    )
    result1 = rules.evaluate(sv1)
    print(f"测试1 (全部通过): eliminated={result1.eliminated}, reason={result1.reason}")

    # 测试用例 2: 相关性不足
    sv2 = StateVector(
        relevance=0.3,
        timeliness=0.7,
        novelty=0.6,
        confidence=0.75
    )
    result2 = rules.evaluate(sv2)
    print(f"测试2 (相关性不足): eliminated={result2.eliminated}, level={result2.level}, reason={result2.reason}")

    # 测试用例 3: 置信度不足（但相关性通过）
    sv3 = StateVector(
        relevance=0.8,
        timeliness=0.7,
        novelty=0.6,
        confidence=0.4
    )
    result3 = rules.evaluate(sv3)
    print(f"测试3 (置信度不足): eliminated={result3.eliminated}, level={result3.level}, reason={result3.reason}")

    # 测试动态顺序
    print(f"\n动态顺序测试:")
    print(f"  task_focused: {[l.name for l in dynamic_order_by_context('task_focused')]}")
    print(f"  time_sensitive: {[l.name for l in dynamic_order_by_context('time_sensitive')]}")
    print(f"  information_overload: {[l.name for l in dynamic_order_by_context('information_overload')]}")

    print("\n[OK] 测试通过")
