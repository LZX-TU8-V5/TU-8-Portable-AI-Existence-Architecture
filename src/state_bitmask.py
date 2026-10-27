"""
state_bitmask.py - 状态位掩码编码

用途：实现状态位掩码编码和快速排除
来源：排除法语义检索 × TU-8 状态机

核心设计：
- 每个状态维度用 1 个 bit 表示
- 状态向量 = 多维度 bit 组合
- 排除操作 = 位运算（AND/OR/XOR）

优势：
- O(1) 排除检查（位运算）
- 无分支（适合GPU SIMD）
- 快速剪枝（位掩码过滤）
"""

from typing import List, Tuple
from state_machine_dimensions import StateVector, StateDimension


class StateBitmask:
    """
    状态位掩码编码器。

    将状态向量编码为位掩码，支持快速位运算。
    """

    def __init__(self, dimensions: List[int] = None):
        """
        初始化位掩码编码器。

        Args:
            dimensions: 维度列表（默认使用 StateDimension 的所有维度）
        """
        if dimensions is None:
            # 默认：使用 StateDimension 的所有维度
            self.dimensions = [
                StateDimension.RELEVANCE,
                StateDimension.TIMELINESS,
                StateDimension.NOVELTY,
                StateDimension.CONFIDENCE
            ]
        else:
            self.dimensions = dimensions

        # 构建维度到索引的映射
        self.dim_to_index = {dim: i for i, dim in enumerate(self.dimensions)}

    def encode(self, state_vector: StateVector) -> int:
        """
        将状态向量编码为位掩码。

        Args:
            state_vector: 状态向量

        Returns:
            位掩码（整数）
        """
        mask = 0
        for i, dim in enumerate(self.dimensions):
            if state_vector.encoding & dim:
                mask |= (1 << i)
        return mask

    def decode(self, mask: int) -> List[str]:
        """
        将位掩码解码为维度名称列表。

        Args:
            mask: 位掩码

        Returns:
            满足的维度名称列表
        """
        satisfied = []
        for i, dim in enumerate(self.dimensions):
            if mask & (1 << i):
                satisfied.append(dim.name)
        return satisfied

    def check_elimination(
        self,
        state_vector: StateVector,
        exclude_mask: int
    ) -> Tuple[bool, str]:
        """
        检查状态向量是否需要排除。

        Args:
            state_vector: 状态向量
            exclude_mask: 排除掩码（哪些维度不满足就排除）

        Returns:
            (是否排除, 原因)
        """
        mask = self.encode(state_vector)

        # 检查是否有任何排除维度不满足
        for i, dim in enumerate(self.dimensions):
            if exclude_mask & (1 << i):
                if not (mask & (1 << i)):
                    return True, f"{dim.name} not satisfied"

        return False, "pass"

    def batch_filter(
        self,
        state_vectors: List[StateVector],
        valid_mask: int
    ) -> Tuple[List[StateVector], List[StateVector]]:
        """
        批量过滤状态向量。

        Args:
            state_vectors: 状态向量列表
            valid_mask: 有效掩码（哪些维度必须满足）

        Returns:
            (通过的列表, 排除的列表)
        """
        passed = []
        excluded = []

        for sv in state_vectors:
            mask = self.encode(sv)
            if mask & valid_mask == valid_mask:
                passed.append(sv)
            else:
                excluded.append(sv)

        return passed, excluded

    def fast_elimination(
        self,
        state_vectors: List[StateVector],
        rules_engine: 'EliminationRules'
    ) -> List[StateVector]:
        """
        快速排除（结合位掩码和规则引擎）。

        先用位掩码快速排除（O(1) 每位），
        再用规则引擎精细检查（仅对通过的）。

        Args:
            state_vectors: 状态向量列表
            rules_engine: 排除规则引擎

        Returns:
            通过的状态向量列表
        """
        # 第一遍：位掩码快速排除
        fast_passed = []
        for sv in state_vectors:
            mask = self.encode(sv)
            # 快速检查：至少满足一个维度
            if mask != 0:
                fast_passed.append(sv)

        # 第二遍：规则引擎精细检查
        from elimination_rules import EliminationRules
        if isinstance(rules_engine, EliminationRules):
            final_passed, _ = rules_engine.batch_evaluate(fast_passed)
            return [r.state_vector for r in final_passed]

        return fast_passed


def create_default_bitmask() -> StateBitmask:
    """
    创建默认位掩码编码器。

    Returns:
        默认编码器（4 维度）
    """
    return StateBitmask()


def create_extended_bitmask(extra_dimensions: List[int]) -> StateBitmask:
    """
    创建扩展位掩码编码器。

    Args:
        extra_dimensions: 额外维度列表

    Returns:
        扩展编码器
    """
    default = [
        StateDimension.RELEVANCE,
        StateDimension.TIMELINESS,
        StateDimension.NOVELTY,
        StateDimension.CONFIDENCE
    ]
    all_dims = default + extra_dimensions
    return StateBitmask(all_dims)


# CLI 测试入口
if __name__ == "__main__":
    print("=== 状态位掩码编码测试 ===\n")

    # 创建编码器
    encoder = create_default_bitmask()

    # 测试编码
    sv1 = StateVector(
        relevance=0.8,
        timeliness=0.6,
        novelty=0.7,
        confidence=0.75
    )
    mask1 = encoder.encode(sv1)
    print(f"状态向量1 编码: {bin(mask1)} (0b{mask1:04b})")
    print(f"  解码: {encoder.decode(mask1)}")

    # 测试排除检查
    sv2 = StateVector(
        relevance=0.3,  # 不满足
        timeliness=0.6,
        novelty=0.7,
        confidence=0.75
    )
    exclude_mask = encoder.encode(
        StateVector(relevance=1.0, timeliness=0.0, novelty=0.0, confidence=0.0)
    )
    excluded, reason = encoder.check_elimination(sv2, exclude_mask)
    print(f"\n排除检查（相关性必须满足）:")
    print(f"  状态向量2: excluded={excluded}, reason={reason}")

    # 测试批量过滤
    svs = [sv1, sv2]
    valid_mask = encoder.encode(
        StateVector(relevance=1.0, timeliness=0.0, novelty=0.0, confidence=0.0)
    )
    passed, excluded_list = encoder.batch_filter(svs, valid_mask)
    print(f"\n批量过滤（相关性必须通过）:")
    print(f"  通过: {len(passed)}, 排除: {len(excluded_list)}")

    print("\n[OK] 测试通过")
