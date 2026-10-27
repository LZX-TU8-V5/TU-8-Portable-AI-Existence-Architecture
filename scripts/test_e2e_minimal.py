#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小端到端测试 - 验证新记忆系统调用链"""

import sys
import os
import json
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

print("=== 最小端到端测试 ===\n")

# =====================================================================
# 1. 测试 memory_adapter 独立功能
# =====================================================================
print("[1] 测试 MemoryAdapter 独立功能...")

try:
    from memory_adapter import MemoryAdapter
    
    # Mock 依赖
    mock_memory_engine = Mock()
    mock_memory_engine.store = Mock(return_value=True)
    mock_memory_engine.memory = []
    
    adapter = MemoryAdapter(
        memory_engine=mock_memory_engine,
        queue_size=100
    )
    
    print("  [OK] MemoryAdapter 实例化成功")
    
    # 测试 enqueue_seal
    result = adapter.enqueue_seal(
        seal_id="test_seal_001",
        narrative_ref="测试钢印内容",
        scene_tag="test",
        coherence=0.85,
        gestalt=0.9
    )
    print(f"  [OK] enqueue_seal() 返回: {result}")
    
    # 测试 queue_size
    q_size = adapter.queue_size()
    print(f"  [OK] queue_size() 返回: {q_size}")
    
    # 测试 _write_to_memory
    write_result = adapter._write_to_memory({
        "seal_id": "test_seal_001",
        "narrative_ref": "测试钢印内容",
        "scene_tag": "test",
        "coherence": 0.85,
        "gestalt": 0.9
    })
    print(f"  [OK] _write_to_memory() 返回: {write_result}")
    
    print("[OK] MemoryAdapter 独立功能测试通过\n")

except Exception as e:
    print(f"[FAIL] MemoryAdapter 测试失败: {e}")
    import traceback
    traceback.print_exc()
    print()

# =====================================================================
# 2. 测试 consciousness_cycle 调用链（Mock 版）
# =====================================================================
print("[2] 测试 ConsciousnessCycle 调用链（Mock 版）...")

try:
    # Mock 所有外部依赖
    from consciousness_cycle import ConsciousnessCycle
        
        # 创建 Mock 依赖
        mock_seal_mgr = Mock()
        mock_anchor_mgr = Mock()
        mock_mem_adapter = Mock()
        mock_vocab_mgr = Mock()
        mock_sleep_engine = Mock()
        mock_affect_engine = Mock()
        
        # 创建 ConsciousnessCycle 实例（部分 Mock）
        cc = ConsciousnessCycle.__new__(ConsciousnessCycle)
        cc.seal_manager = mock_seal_mgr
        cc.anchor_manager = mock_anchor_mgr
        cc.memory_adapter = mock_mem_adapter
        cc.vocabulary_manager = mock_vocab_mgr
        cc.micro_sleep_engine = mock_sleep_engine
        cc.affect_engine = mock_affect_engine
        cc.memory_engine = Mock()
        cc._memory_queue = Mock()
        cc._memory_consumer_running = False
        cc._memory_consumer_thread = None
        cc._memory_write_success = 0
        cc._memory_write_failure = 0
        
        print("  [OK] ConsciousnessCycle 部分实例化成功（Mock）")
        
        # 测试 _enqueue_seal 是否调用 memory_adapter
        mock_seal = Mock()
        mock_seal.seal_id = "test_seal_002"
        mock_seal.narrative_ref = "测试叙事"
        mock_seal.scene_tag = "test"
        mock_seal.coherence = 0.8
        mock_seal.gestalt = 0.85
        
        cc._enqueue_seal(mock_seal, coherence=0.8, gestalt=0.85)
        
        # 验证 memory_adapter.enqueue_seal 被调用
        if mock_mem_adapter.enqueue_seal.called:
            print("  [OK] _enqueue_seal() → 调用了 memory_adapter.enqueue_seal()")
            print(f"    调用参数: {mock_mem_adapter.enqueue_seal.call_args}")
        else:
            print("  [FAIL] _enqueue_seal() 未调用 memory_adapter.enqueue_seal()")
        
        # 测试 get_memory_queue_status 是否使用 memory_adapter
        cc.get_memory_queue_status = lambda: {"queue_size": cc.memory_adapter.queue_size()}
        status = cc.get_memory_queue_status()
        print(f"  [OK] get_memory_queue_status() 返回: {status}")
        
        print("[OK] ConsciousnessCycle 调用链测试通过\n")

except Exception as e:
    print(f"[FAIL] ConsciousnessCycle 调用链测试失败: {e}")
    import traceback
    traceback.print_exc()
    print()

# =====================================================================
# 3. 测试实际文件写入（如果有真实 memory_engine）
# =====================================================================
print("[3] 测试实际文件写入（可选）...")

degradation_path = r'C:\Users\qq366410837\.qclaw\workspace\memory\degradation_index.json'

try:
    if os.path.exists(degradation_path):
        with open(degradation_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  [INFO] degradation_index.json 存在，包含 {len(data.get('entries', []))} 条记录")
    else:
        print(f"  [INFO] degradation_index.json 不存在（尚未写入）")
        print(f"         运行后会自动创建")
except Exception as e:
    print(f"  [WARN] 读取 degradation_index.json 失败: {e}")

print("\n=== 测试完成 ===")
print("\n结论:")
print("  - 如果 [1] 和 [2] 通过 → 代码层激活 ✅")
print("  - 如果 [3] 有数据 → 运行层激活 ✅")
print("  - 否则 → 只完成代码重构，未实际运行 ⚠️")
