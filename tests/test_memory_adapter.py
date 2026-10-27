"""
Phase 4 测试：记忆适配器

测试目标：
1. 队列操作
2. 消费者线程
3. 状态查询
"""

import sys
import os
import time
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_adapter import MemoryAdapter


class MockMemoryEngine:
    """模拟记忆引擎"""

    def __init__(self):
        self.entries = []

    def store(self, content, source, tags, emotion, meaning):
        """模拟存储"""
        self.entries.append({
            "content": content,
            "source": source,
            "tags": tags,
            "emotion": emotion,
            "meaning": meaning
        })


def test_queue_operations():
    """测试队列操作"""
    print("=== 测试队列操作 ===")

    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=10)

    # 入队
    task = {
        "seal_id": "s_001",
        "seal_hash": "hash_001",
        "narrative_ref": "测试叙事",
        "scene_tag": "test",
        "coherence": 0.8,
        "gestalt": 0.5,
        "prev_hash": ""
    }

    success = adapter.enqueue(task)
    assert success
    print(f"[PASS] 任务入队成功")

    # 查询队列状态
    status = adapter.get_queue_status()
    assert status["queue_used"] == 1
    print(f"[PASS] 队列状态: {status['queue_used']}/{status['queue_size']}")


def test_enqueue_seal():
    """测试钢印入队"""
    print("\n=== 测试钢印入队 ===")

    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=10)

    # 入队钢印
    success = adapter.enqueue_seal(
        seal_id="s_20260627_001",
        seal_hash="hash_abc123",
        narrative="这是一个测试钢印",
        scene_tag="dev",
        coherence=0.85,
        gestalt=0.6,
        prev_hash="hash_parent"
    )

    assert success
    print(f"[PASS] 钢印入队成功")

    # 查询队列状态
    status = adapter.get_queue_status()
    assert status["queue_used"] == 1
    print(f"[PASS] 队列使用: {status['queue_used']}")


def test_queue_full():
    """测试队列满"""
    print("\n=== 测试队列满 ===")

    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=3)

    # 填满队列
    for i in range(3):
        adapter.enqueue_seal(
            seal_id=f"s_{i:03d}",
            seal_hash=f"hash_{i}",
            narrative=f"叙事{i}"
        )

    # 再入队应该失败
    success = adapter.enqueue_seal(
        seal_id="s_full",
        seal_hash="hash_full",
        narrative="队列满测试"
    )

    assert not success
    print(f"[PASS] 队列满时正确拒绝")

    # 验证失败计数
    status = adapter.get_queue_status()
    assert status["write_failure"] == 1
    print(f"[PASS] 失败计数: {status['write_failure']}")


def test_consumer_thread():
    """测试消费者线程"""
    print("\n=== 测试消费者线程 ===")

    # 创建模拟引擎
    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=10)

    # 启动消费者
    adapter.start_consumer()
    assert adapter._memory_consumer_running
    print(f"[PASS] 消费者线程已启动")

    # 入队任务
    for i in range(3):
        adapter.enqueue_seal(
            seal_id=f"s_{i:03d}",
            seal_hash=f"hash_{i}",
            narrative=f"叙事{i}"
        )

    # 等待消费
    time.sleep(2)

    # 停止消费者
    adapter.stop_consumer()
    assert not adapter._memory_consumer_running
    print(f"[PASS] 消费者线程已停止")

    # 验证写入
    assert len(mock_engine.entries) == 3
    print(f"[PASS] 写入成功: {len(mock_engine.entries)} 条")


def test_statistics():
    """测试统计信息"""
    print("\n=== 测试统计信息 ===")

    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=10)

    # 启动消费者
    adapter.start_consumer()

    # 入队
    for i in range(5):
        adapter.enqueue_seal(
            seal_id=f"s_{i:03d}",
            seal_hash=f"hash_{i}",
            narrative=f"叙事{i}"
        )

    # 等待消费
    time.sleep(2)

    # 获取统计
    stats = adapter.get_stats()
    assert stats["success"] == 5
    print(f"[PASS] 统计: 成功 {stats['success']} 条")

    # 停止消费者
    adapter.stop_consumer()


def test_engine_management():
    """测试引擎管理"""
    print("\n=== 测试引擎管理 ===")

    adapter = MemoryAdapter()

    # 初始状态
    assert not adapter.is_ready()
    print(f"[PASS] 初始未就绪")

    # 设置引擎
    mock_engine = MockMemoryEngine()
    adapter.set_engine(mock_engine)
    assert adapter.memory_engine is not None
    print(f"[PASS] 引擎已设置")

    # 启动消费者
    adapter.start_consumer()
    assert adapter.is_ready()
    print(f"[PASS] 已就绪")

    # 停止
    adapter.stop_consumer()


def test_integration():
    """测试集成场景"""
    print("\n=== 测试集成场景 ===")

    # 创建模拟引擎和适配器
    mock_engine = MockMemoryEngine()
    adapter = MemoryAdapter(memory_engine=mock_engine, queue_size=20)

    # 启动消费者
    adapter.start_consumer()

    # 模拟钢印生成
    for i in range(10):
        adapter.enqueue_seal(
            seal_id=f"s_{i:03d}",
            seal_hash=f"hash_{i}",
            narrative=f"钢印叙事{i}",
            scene_tag="dev" if i % 2 == 0 else "chat",
            coherence=0.7 + i * 0.02,
            gestalt=0.5 + i * 0.03
        )

    # 等待消费完成
    time.sleep(3)

    # 停止消费者
    adapter.stop_consumer()

    # 验证结果
    stats = adapter.get_stats()
    assert stats["success"] == 10
    assert stats["failure"] == 0
    print(f"[PASS] 成功写入: {stats['success']} 条")

    # 验证引擎
    assert len(mock_engine.entries) == 10
    print(f"[PASS] 引擎存储: {len(mock_engine.entries)} 条")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 4 测试：记忆适配器")
    print("=" * 60)

    test_queue_operations()
    test_enqueue_seal()
    test_queue_full()
    test_consumer_thread()
    test_statistics()
    test_engine_management()
    test_integration()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
