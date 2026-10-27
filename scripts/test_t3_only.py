#!/usr/bin/env python3
"""
最小测试：只测 T3 记忆入队
"""
import sys
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

from memory_adapter import MemoryAdapter
import json

class MockEngine:
    """正确的 store 签名"""
    def store(self, content, source, tags, meaning=0.0, emotion=0.0):
        self.last_content = content
        self.last_source = source
        return True

# 测试 1：直接调用 enqueue_seal
print('=== 测试 1：直接调用 enqueue_seal ===')
engine = MockEngine()
ma = MemoryAdapter(memory_engine=engine)

try:
    result = ma.enqueue_seal(
        seal_id="test_id",
        seal_hash="test_hash",
        narrative="test narrative",
        scene_tag="test",
        coherence=0.8,
        gestalt=0.5,
        prev_hash="prev_hash",
    )
    print(f'enqueue_seal result: {result}')
    print(f'queue size: {ma.queue_size()}')
    
    # 消费
    consumed = ma.consume_one()
    print(f'consumed: {consumed}')
    
except Exception as e:
    import traceback
    print(f'ERROR: {e}')
    traceback.print_exc()

print()
print('=== 测试 2：检查 MemoryAdapter 方法 ===')
print(f'enqueue_seal callable: {callable(ma.enqueue_seal)}')
print(f'enqueue callable: {callable(ma.enqueue)}')
print(f'consume_one callable: {callable(ma.consume_one)}')
print(f'queue_size callable: {callable(ma.queue_size)}')

print()
print('=== 测试 3：检查 MockEngine.store 签名 ===')
import inspect
sig = inspect.signature(engine.store)
print(f'store signature: {sig}')
