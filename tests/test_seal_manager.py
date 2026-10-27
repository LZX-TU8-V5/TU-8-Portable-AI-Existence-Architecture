"""
Phase 2 测试：钢印管理器

测试目标：
1. 钢印生成
2. 链式哈希计算
3. 钢印链验证
4. 持久化/加载
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seal_manager import Seal, SealManager
from cycle_types import StateVector, MicroSleepPayload


def test_seal_creation():
    """测试钢印创建"""
    print("=== 测试钢印创建 ===")

    seal = Seal(
        seal_type="rhythm",
        narrative_compression="测试钢印创建",
        causal_coherence=0.85
    )

    assert seal.seal_id.startswith("s_")
    assert seal.seal_type == "rhythm"
    assert seal.narrative_compression == "测试钢印创建"
    assert seal.causal_coherence == 0.85
    print(f"[PASS] 钢印创建成功: {seal.seal_id}")


def test_seal_hash():
    """测试链式哈希"""
    print("\n=== 测试链式哈希 ===")

    # 创世钢印
    seal1 = Seal(
        seal_type="origin",
        narrative_compression="创世钢印"
    )
    hash1 = seal1.compute_seal_hash("")

    assert seal1.seal_hash != ""
    assert seal1.seal_hash == hash1
    print(f"[PASS] 创世钢印哈希: {hash1[:16]}...")

    # 第二个钢印
    seal2 = Seal(
        seal_type="rhythm",
        narrative_compression="第二个钢印"
    )
    hash2 = seal2.compute_seal_hash(seal1.seal_hash)

    assert seal2.parent_seal_id == seal1.seal_hash
    assert seal2.seal_hash != seal1.seal_hash
    print(f"[PASS] 第二个钢印哈希: {hash2[:16]}...")


def test_seal_serialization():
    """测试序列化/反序列化"""
    print("\n=== 测试序列化/反序列化 ===")

    # 创建带payload的钢印
    payload = MicroSleepPayload(
        context="测试上下文",
        trigger_event="测试事件",
        self_consistent_conclusion="测试结论"
    )

    seal = Seal(
        seal_type="rhythm",
        narrative_compression="测试序列化",
        causal_coherence=0.9,
        micro_sleep_payload=payload
    )
    seal.compute_seal_hash("test_parent_hash")

    # 序列化
    d = seal.to_dict()
    assert d["seal_id"] == seal.seal_id
    assert d["narrative_compression"] == "测试序列化"
    assert "micro_sleep_payload" in d
    print(f"[PASS] 序列化成功")

    # 反序列化
    seal2 = Seal.from_dict(d)
    assert seal2.seal_id == seal.seal_id
    assert seal2.narrative_compression == seal.narrative_compression
    assert seal2.micro_sleep_payload is not None
    assert seal2.micro_sleep_payload.context == "测试上下文"
    print(f"[PASS] 反序列化成功")


def test_seal_manager():
    """测试钢印管理器"""
    print("\n=== 测试钢印管理器 ===")

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()

    try:
        manager = SealManager(workspace_path=temp_dir)

        # 初始状态
        assert manager.get_chain_length() == 0
        print(f"[PASS] 初始钢印链为空")

        # 生成创世钢印
        seal1 = manager.generate_seal(
            narrative="创世钢印",
            coherence=1.0,
            seal_type="origin"
        )

        assert manager.get_chain_length() == 1
        assert seal1.seal_type == "origin"
        print(f"[PASS] 生成创世钢印: {seal1.seal_id}")

        # 生成第二个钢印
        seal2 = manager.generate_seal(
            narrative="第二个钢印",
            coherence=0.85,
            seal_type="rhythm"
        )

        assert manager.get_chain_length() == 2
        assert seal2.parent_seal_id == seal1.seal_hash
        print(f"[PASS] 生成第二个钢印: {seal2.seal_id}")

        # 获取最近钢印
        recent = manager.get_recent_seals(count=2)
        assert len(recent) == 2
        assert recent[0].seal_id == seal1.seal_id
        assert recent[1].seal_id == seal2.seal_id
        print(f"[PASS] 获取最近钢印成功")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_chain_verification():
    """测试钢印链验证"""
    print("\n=== 测试钢印链验证 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = SealManager(workspace_path=temp_dir)

        # 生成钢印链
        for i in range(5):
            manager.generate_seal(
                narrative=f"钢印 {i+1}",
                coherence=0.8 + i * 0.02,
                seal_type="rhythm" if i > 0 else "origin"
            )

        # 验证
        assert manager.verify_chain()
        print(f"[PASS] 钢印链验证通过: {manager.get_chain_length()} 个钢印")

    finally:
        shutil.rmtree(temp_dir)


def test_persistence():
    """测试持久化"""
    print("\n=== 测试持久化 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        # 创建管理器并生成钢印
        manager1 = SealManager(workspace_path=temp_dir)

        for i in range(3):
            manager1.generate_seal(
                narrative=f"钢印 {i+1}",
                coherence=0.8,
                seal_type="rhythm" if i > 0 else "origin"
            )

        # 持久化
        manager1.persist()
        print(f"[PASS] 持久化成功: {manager1.get_chain_length()} 个钢印")

        # 重新加载
        manager2 = SealManager(workspace_path=temp_dir)

        assert manager2.get_chain_length() == 3
        assert manager2.verify_chain()
        print(f"[PASS] 重新加载成功: {manager2.get_chain_length()} 个钢印")

    finally:
        shutil.rmtree(temp_dir)


def test_query_interface():
    """测试查询接口"""
    print("\n=== 测试查询接口 ===")

    temp_dir = tempfile.mkdtemp()

    try:
        manager = SealManager(workspace_path=temp_dir)

        # 生成钢印
        seals = []
        for i in range(5):
            seal = manager.generate_seal(
                narrative=f"钢印 {i+1}",
                coherence=0.8,
                seal_type="rhythm" if i > 0 else "origin"
            )
            seals.append(seal)

        # 测试查询接口
        last = manager.get_last_seal()
        assert last.seal_id == seals[-1].seal_id
        print(f"[PASS] 获取最后钢印: {last.seal_id}")

        by_id = manager.get_seal_by_id(seals[2].seal_id)
        assert by_id.seal_id == seals[2].seal_id
        print(f"[PASS] 根据ID查询: {by_id.seal_id}")

    finally:
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 2 测试：钢印管理器")
    print("=" * 60)

    test_seal_creation()
    test_seal_hash()
    test_seal_serialization()
    test_seal_manager()
    test_chain_verification()
    test_persistence()
    test_query_interface()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
