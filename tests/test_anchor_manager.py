"""
Phase 3 测试：锚点管理器

测试目标：
1. 候选队列管理
2. 锚点创建
3. 触发检查
4. 持久化
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from anchor_manager import AnchorManager
from cycle_types import CognitiveAnchor, AnchorCandidate


def test_candidate_queue():
    """测试候选队列"""
    print("=== 测试候选队列 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)

        # 添加候选
        manager.enqueue_candidate(
            trigger="检测到模式",
            related_seal_ids=["seal_001"],
            content="用户偏好简洁风格",
            priority=0.7
        )

        assert manager.get_candidate_count() == 1
        print(f"[PASS] 候选入队成功")

        # 添加多个候选
        for i in range(5):
            manager.enqueue_candidate(
                trigger=f"触发{i+1}",
                related_seal_ids=[f"seal_{i:03d}"],
                content=f"内容{i+1}",
                priority=0.5 + i * 0.05
            )

        assert manager.get_candidate_count() == 6
        print(f"[PASS] 多个候选入队: {manager.get_candidate_count()} 个")

        # 获取候选（按优先级排序）
        candidates = manager.get_candidates(count=3)
        assert len(candidates) == 3
        assert candidates[0].priority >= candidates[1].priority
        print(f"[PASS] 获取候选（按优先级）: 最高={candidates[0].priority:.2f}")

    finally:
        shutil.rmtree(temp_dir)


def test_candidate_cleanup():
    """测试候选清理"""
    print("\n=== 测试候选清理 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)
        manager.candidate_queue_max = 5  # 设置较小的上限

        # 添加超过上限的候选
        for i in range(10):
            manager.enqueue_candidate(
                trigger=f"触发{i+1}",
                related_seal_ids=[f"seal_{i:03d}"],
                content=f"内容{i+1}",
                priority=0.3 + i * 0.07
            )

        # 应该只保留前5个
        assert manager.get_candidate_count() == 5
        print(f"[PASS] 清理后候选数: {manager.get_candidate_count()}")

        # 验证保留的是高优先级
        candidates = manager.get_candidates()
        for c in candidates:
            assert c.priority >= 0.5
        print(f"[PASS] 保留高优先级候选")

    finally:
        shutil.rmtree(temp_dir)


def test_anchor_creation():
    """测试锚点创建"""
    print("\n=== 测试锚点创建 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)

        # 创建锚点
        anchor = manager.create_anchor(
            content="用户偏好：简洁、安全、三轨道架构",
            anchor_type="milestone",
            confidence=0.85,
            seal_ids=["seal_001", "seal_002"],
            source_hash="abc123"
        )

        assert anchor.anchor_id.startswith("anchor_")
        assert anchor.anchor_type == "milestone"
        assert len(anchor.seal_ids) == 2
        print(f"[PASS] 创建锚点: {anchor.anchor_id}")

        # 验证已持久化
        assert manager.get_total_count() == 1
        print(f"[PASS] 锚点已持久化: {manager.get_total_count()} 个")

    finally:
        shutil.rmtree(temp_dir)


def test_create_from_candidate():
    """测试从候选创建锚点"""
    print("\n=== 测试从候选创建锚点 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)

        # 添加候选
        manager.enqueue_candidate(
            trigger="检测到里程碑",
            related_seal_ids=["seal_001"],
            content="这是里程碑内容",
            priority=0.8
        )

        # 消费候选
        candidate = manager.consume_candidate()
        assert candidate is not None
        print(f"[PASS] 消费候选: {candidate.trigger}")

        # 从候选创建锚点
        anchor = manager.create_from_candidate(
            candidate=candidate,
            anchor_type="milestone",
            confidence=0.9
        )

        assert anchor.content == "这是里程碑内容"
        assert len(anchor.seal_ids) == 1
        print(f"[PASS] 从候选创建锚点: {anchor.anchor_id}")

    finally:
        shutil.rmtree(temp_dir)


def test_should_externalize():
    """测试触发检查"""
    print("\n=== 测试触发检查 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)

        # 场景 1：候选队列满
        for i in range(20):
            manager.enqueue_candidate(
                trigger=f"触发{i}",
                related_seal_ids=[],
                content=f"内容{i}",
                priority=0.5
            )

        trigger = manager.should_externalize(
            seal_chain_length=5,
            last_seal_coherence=0.8
        )

        assert trigger is not None
        assert trigger["trigger"] == "queue_full"
        print(f"[PASS] 触发: queue_full (priority={trigger['priority']})")

        # 清空候选
        manager.candidates = []

        # 场景 2：里程碑
        trigger = manager.should_externalize(
            seal_chain_length=10,
            last_seal_coherence=0.8,
            milestone_gap=10
        )

        assert trigger is not None
        assert trigger["trigger"] == "milestone"
        print(f"[PASS] 触发: milestone (seal_count={trigger['seal_count']})")

        # 场景 3：低连贯度
        trigger = manager.should_externalize(
            seal_chain_length=5,
            last_seal_coherence=0.3
        )

        assert trigger is not None
        assert trigger["trigger"] == "low_coherence"
        print(f"[PASS] 触发: low_coherence (coherence={trigger['coherence']})")

        # 场景 4：无触发
        trigger = manager.should_externalize(
            seal_chain_length=5,
            last_seal_coherence=0.8
        )

        assert trigger is None
        print(f"[PASS] 无触发条件")

    finally:
        shutil.rmtree(temp_dir)


def test_persistence():
    """测试持久化"""
    print("\n=== 测试持久化 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        # 创建管理器并添加锚点
        manager1 = AnchorManager(workspace_path=temp_dir)

        for i in range(3):
            manager1.create_anchor(
                content=f"锚点{i+1}",
                anchor_type="insight",
                confidence=0.8
            )

        print(f"[PASS] 创建锚点: {manager1.get_total_count()} 个")

        # 重新加载
        manager2 = AnchorManager(workspace_path=temp_dir)

        assert manager2.get_total_count() == 3
        print(f"[PASS] 重新加载: {manager2.get_total_count()} 个锚点")

    finally:
        shutil.rmtree(temp_dir)


def test_query_interface():
    """测试查询接口"""
    print("\n=== 测试查询接口 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = AnchorManager(workspace_path=temp_dir)

        # 创建不同类型的锚点
        types = ["interaction", "insight", "milestone", "insight"]
        for i, anchor_type in enumerate(types):
            manager.create_anchor(
                content=f"锚点{i+1}",
                anchor_type=anchor_type,
                confidence=0.8
            )

        # 按类型查询
        insights = manager.get_anchors_by_type("insight")
        assert len(insights) == 2
        print(f"[PASS] insight类型锚点: {len(insights)} 个")

        # 获取最近锚点
        recent = manager.get_recent_anchors(count=2)
        assert len(recent) == 2
        print(f"[PASS] 最近锚点: {len(recent)} 个")

    finally:
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 3 测试：锚点管理器")
    print("=" * 60)

    test_candidate_queue()
    test_candidate_cleanup()
    test_anchor_creation()
    test_create_from_candidate()
    test_should_externalize()
    test_persistence()
    test_query_interface()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
