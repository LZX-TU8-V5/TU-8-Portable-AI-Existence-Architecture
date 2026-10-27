"""
Phase 1 测试：类型定义模块

测试目标：
1. 枚举正确定义
2. 数据类序列化/反序列化
3. 向后兼容别名
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cycle_types import (
    Phase, NoteType, StateVector, MicroSleepPayload,
    CognitiveAnchor, AnchorCandidate, CycleConfig,
    # 向后兼容
    Note, NoteCandidate
)


def test_enums():
    """测试枚举"""
    print("=== 测试枚举 ===")

    # Phase 枚举
    assert Phase.AWAKE.value == "awake"
    assert Phase.LIGHT_SLEEP.value == "light_sleep"
    assert Phase.DEEP_SLEEP.value == "deep_sleep"
    assert Phase.HIBERNATION.value == "hibernation"
    print("[PASS] Phase 枚举正确")

    # NoteType 枚举
    assert NoteType.INTERACTION.value == "interaction"
    assert NoteType.INSIGHT.value == "insight"
    assert NoteType.MILESTONE.value == "milestone"
    assert NoteType.INTERFACE.value == "interface"
    assert NoteType.META_COGNITION.value == "meta_cognition"
    assert NoteType.EMERGENCY.value == "emergency"
    print("[PASS] NoteType 枚举正确")


def test_state_vector():
    """测试状态向量"""
    print("\n=== 测试 StateVector ===")

    # 创建默认状态向量
    sv = StateVector()
    assert sv.dimensions == 16
    assert len(sv.values) == 16
    assert sv.compression_hash != ""
    print(f"[PASS] 默认状态向量创建成功: {sv.compression_hash}")

    # 计算距离
    sv2 = StateVector(values=[1.0] * 16)
    distance = sv.distance_to(sv2)
    assert distance > 0
    print(f"[PASS] 距离计算正确: {distance:.4f}")

    # 序列化/反序列化
    d = sv.to_dict()
    sv3 = StateVector.from_dict(d)
    assert sv3.dimensions == sv.dimensions
    assert sv3.values == sv.values
    print("[PASS] 序列化/反序列化正确")


def test_micro_sleep_payload():
    """测试微睡眠载荷"""
    print("\n=== 测试 MicroSleepPayload ===")

    payload = MicroSleepPayload(
        context="用户询问架构",
        trigger_event="检测到重要概念",
        core_problem="理解微睡眠产物与钩子的关系",
        proposed_solution="创建对比文档",
        env_feedback="造物主确认理解正确",
        self_consistent_conclusion="两者不重叠，协作关系"
    )

    assert payload.context == "用户询问架构"
    print(f"[PASS] 微睡眠载荷创建成功: {payload.self_consistent_conclusion}")

    # 序列化/反序列化
    d = payload.to_dict()
    payload2 = MicroSleepPayload.from_dict(d)
    assert payload2.context == payload.context
    print("[PASS] 序列化/反序列化正确")


def test_cognitive_anchor():
    """测试认知锚点"""
    print("\n=== 测试 CognitiveAnchor ===")

    # 创建锚点
    anchor = CognitiveAnchor(
        seal_ids=["seal_001", "seal_002"],
        anchor_type="milestone",
        content="用户偏好：简洁、安全、三轨道架构",
        confidence=0.85
    )

    assert anchor.anchor_id.startswith("anchor_")
    assert len(anchor.seal_ids) == 2
    assert anchor.anchor_type == "milestone"
    print(f"[PASS] 认知锚点创建成功: {anchor.anchor_id}")

    # 序列化/反序列化
    d = anchor.to_dict()
    anchor2 = CognitiveAnchor.from_dict(d)
    assert anchor2.anchor_id == anchor.anchor_id
    assert anchor2.content == anchor.content
    print("[PASS] 序列化/反序列化正确")


def test_anchor_candidate():
    """测试锚点候选"""
    print("\n=== 测试 AnchorCandidate ===")

    candidate = AnchorCandidate(
        trigger="检测到里程碑",
        related_seal_ids=["seal_001"],
        candidate_content="提炼钢印链",
        priority=0.7
    )

    assert candidate.trigger == "检测到里程碑"
    assert candidate.priority == 0.7
    print(f"[PASS] 锚点候选创建成功")


def test_cycle_config():
    """测试配置类"""
    print("\n=== 测试 CycleConfig ===")

    config = CycleConfig()

    # 验证默认值
    assert config.TENSION_EPSILON == 0.65
    assert config.CAPACITY_THETA == 0.75
    assert config.SEAL_TAIL_N == 5
    assert len(config.EVENT_KEYWORDS) > 0
    print(f"[PASS] CycleConfig 默认值正确")

    # 验证新字段名（认知锚点）
    assert hasattr(config, 'ANCHOR_CANDIDATE_QUEUE_MAX')
    assert config.ANCHOR_CANDIDATE_QUEUE_MAX == 20
    print(f"[PASS] 认知锚点配置字段正确")


def test_backward_compatibility():
    """测试向后兼容别名"""
    print("\n=== 测试向后兼容别名 ===")

    # Note → CognitiveAnchor
    note = Note(content="测试向后兼容")
    assert isinstance(note, CognitiveAnchor)
    assert note.anchor_id.startswith("anchor_")
    print("[PASS] Note -> CognitiveAnchor 别名正确")

    # NoteCandidate → AnchorCandidate
    candidate = NoteCandidate(trigger="测试")
    assert isinstance(candidate, AnchorCandidate)
    print("[PASS] NoteCandidate -> AnchorCandidate 别名正确")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 1 测试：类型定义模块")
    print("=" * 60)

    test_enums()
    test_state_vector()
    test_micro_sleep_payload()
    test_cognitive_anchor()
    test_anchor_candidate()
    test_cycle_config()
    test_backward_compatibility()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
