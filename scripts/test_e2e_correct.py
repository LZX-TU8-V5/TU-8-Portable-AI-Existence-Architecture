#!/usr/bin/env python3
import sys, json, os, tempfile
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

from unittest.mock import Mock
from memory_adapter import MemoryAdapter

print("[测试] MemoryAdapter 最小端到端\n")

# 用真实临时文件做 memory_engine
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = os.path.join(tmpdir, "test_memory.json")
    
    # mock memory_engine.store() 写入临时文件
    class FakeEngine:
        def store(self, content, metadata=None):
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump({"content": content, "metadata": metadata}, f)
            return True
        def get_stats(self):
            return {"total": 1}
    
    engine = FakeEngine()
    adapter = MemoryAdapter(memory_engine=engine, queue_size=100)
    print("[OK] MemoryAdapter 实例化成功")
    
    # 正确调用 enqueue_seal
    result = adapter.enqueue_seal(
        seal_id="test_e2e_001",
        seal_hash="abc123hash",
        narrative="端到端测试叙事内容",
        scene_tag="test",
        coherence=0.85,
        gestalt=0.9,
        prev_hash=""
    )
    print(f"[OK] enqueue_seal() 返回: {result}")
    
    # 消费队列（真正写入）
    consumed = adapter.consume_one()
    print(f"[OK] consume_one() 返回: {consumed}")
    
    # 检查临时文件是否写入
    if os.path.exists(db_path):
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[OK] 文件写入成功: {data.get('content', '')[:50]}")
    else:
        print("[WARN] 文件未写入")

# 检查 degradation_index.json（真实路径）
index_path = r'C:\Users\qq366410837\.qclaw\workspace\memory\degradation_index.json'
print(f"\n[检查] degradation_index.json:")
if os.path.exists(index_path):
    with open(index_path, 'r', encoding='utf-8') as f:
        idx = json.load(f)
    entries = idx.get('entries', [])
    print(f"  条目数: {len(entries)}")
    if entries:
        e = entries[-1]
        print(f"  最新条目: id={e.get('id')}, level={e.get('level')}")
else:
    print("  文件不存在（尚未有写入）")

print("\n[结论] 调用链验证完成")
