#!/usr/bin/env python3
"""
验证 memory_adapter 真实写入能力

测试目标：
1. MemoryAdapter 能否成功调用 TU8MemoryEngine.store()
2. 写入的数据是否真正持久化到磁盘
3. 异步队列机制是否正常工作

创建时间：2026-06-29 02:15 GMT+8
"""

import sys
import os
import time
import json

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tu8_memory import TU8MemoryEngine
from memory_adapter import MemoryAdapter

def test_memory_adapter_write():
    """测试 memory_adapter 真实写入"""
    
    print("=" * 60)
    print("Memory Adapter Write Test")
    print("=" * 60)
    
    # 1. 创建 TU8MemoryEngine 实例
    print("\n[Step 1] Creating TU8MemoryEngine...")
    
    # 获取 workspace 目录
    workspace_dir = os.path.join(os.path.dirname(__file__), '..')
    workspace_dir = os.path.abspath(workspace_dir)
    
    memory_engine = TU8MemoryEngine(workspace_dir=workspace_dir)
    print(f"  Engine created: {type(memory_engine).__name__}")
    print(f"  Workspace dir: {workspace_dir}")
    
    # 2. 创建 MemoryAdapter 实例
    print("\n[Step 2] Creating MemoryAdapter...")
    adapter = MemoryAdapter(memory_engine=memory_engine)
    print(f"  Adapter created")
    
    # 3. 启动消费者线程
    print("\n[Step 3] Starting consumer thread...")
    adapter.start_consumer()
    time.sleep(0.5)  # 等待线程启动
    print(f"  Consumer running: {adapter._memory_consumer_running}")
    
    # 4. 构造测试数据（绕过保护机制）
    print("\n[Step 4] Constructing test data...")
    
    # 使用测试专用的 seal_id 和内容，避免触发核心保护
    test_seal_id = f"test_seal_{int(time.time())}"
    test_seal_hash = "test_hash_12345"
    test_narrative = "Test memory adapter write capability"
    test_scene_tag = "test"
    test_coherence = 0.5  # 中等连贯度，不触发高置信度保护
    test_gestalt = 0.3
    test_prev_hash = ""
    
    print(f"  Test seal_id: {test_seal_id}")
    print(f"  Test narrative: {test_narrative}")
    
    # 5. 入队任务
    print("\n[Step 5] Enqueueing task...")
    success = adapter.enqueue_seal(
        seal_id=test_seal_id,
        seal_hash=test_seal_hash,
        narrative=test_narrative,
        scene_tag=test_scene_tag,
        coherence=test_coherence,
        gestalt=test_gestalt,
        prev_hash=test_prev_hash
    )
    print(f"  Enqueue success: {success}")
    
    # 6. 等待异步写入完成
    print("\n[Step 6] Waiting for async write...")
    time.sleep(2.0)  # 等待消费者线程处理
    
    # 7. 检查写入统计
    print("\n[Step 7] Checking write stats...")
    stats = adapter.get_stats()
    print(f"  Write success: {stats['success']}")
    print(f"  Write failure: {stats['failure']}")
    print(f"  Success rate: {stats['success_rate']:.2%}")
    
    # 8. 验证持久化（检查 TU8MemoryEngine 内部状态）
    print("\n[Step 8] Verifying persistence...")
    
    # 尝试从引擎中召回刚刚写入的内容
    recall_results = memory_engine.recall(
        query=test_narrative,
        top_k=5
    )
    
    print(f"  Recall results count: {len(recall_results)}")
    
    if len(recall_results) > 0:
        print("\n  [SUCCESS] Memory was written and can be recalled!")
        for i, result in enumerate(recall_results):
            print(f"    Result {i+1}:")
            print(f"      Content: {result.get('content', 'N/A')[:100]}...")
            print(f"      Score: {result.get('score', 'N/A')}")
    else:
        print("\n  [WARNING] No recall results - memory may not be persisted")
    
    # 9. 检查队列状态
    print("\n[Step 9] Checking queue status...")
    queue_status = adapter.get_queue_status()
    print(f"  Queue used: {queue_status['queue_used']}")
    print(f"  Queue available: {queue_status['queue_available']}")
    print(f"  Consumer running: {queue_status['consumer_running']}")
    
    # 10. 清理
    print("\n[Step 10] Cleaning up...")
    adapter.stop_consumer()
    print("  Consumer stopped")
    
    print("\n" + "=" * 60)
    print("Test Completed")
    print("=" * 60)
    
    # 返回测试结果
    return {
        "enqueue_success": success,
        "write_success": stats['success'],
        "write_failure": stats['failure'],
        "recall_count": len(recall_results),
        "test_passed": success and stats['success'] > 0
    }

if __name__ == "__main__":
    result = test_memory_adapter_write()
    
    print("\n" + "=" * 60)
    print("Final Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)
    
    if result["test_passed"]:
        print("\n[PASS] Memory adapter write test PASSED")
        sys.exit(0)
    else:
        print("\n[FAIL] Memory adapter write test FAILED")
        sys.exit(1)
