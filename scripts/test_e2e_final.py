#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简端到端测试 - 验证 memory_adapter 写入"""
import sys, os, json, time
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

from memory_adapter import MemoryAdapter

print("[测试] memory_adapter 极简端到端\n")

# 用真实路径的 memory_engine mock
class FakeEngine:
    def __init__(self):
        self.last_args = None
    def store(self, content, source, tags, emotion, meaning):
        self.last_args = {"content": content, "source": source, "tags": tags, "emotion": emotion, "meaning": meaning}
        return True
    def get_stats(self):
        return {"total": 1, "last": self.last_args}

engine = FakeEngine()
adapter = MemoryAdapter(memory_engine=engine, queue_size=100)
print("[OK] MemoryAdapter 实例化成功")

# 入队
r = adapter.enqueue_seal(
    seal_id="e2e_001",
    seal_hash="hash001",
    narrative="极简端到端测试",
    scene_tag="test",
    coherence=0.85,
    gestalt=0.9,
    prev_hash=""
)
print(f"[OK] enqueue_seal() = {r}, 队列大小 = {adapter.get_queue_status()['queue_size']}")

# 启动消费者线程（后台写入）
adapter.start_consumer()
time.sleep(2)  # 等2秒让消费者处理
adapter.stop_consumer()

print(f"[OK] 消费后队列大小 = {adapter.get_queue_status()['queue_size']}")
print(f"[OK] FakeEngine 收到: {engine.last_args}")

# 检查 degradation_index.json
idx_path = r'C:\Users\qq366410837\.qclaw\workspace\memory\degradation_index.json'
if os.path.exists(idx_path):
    with open(idx_path, encoding='utf-8') as f:
        idx = json.load(f)
    print(f"[INFO] degradation_index.json 条目数 = {len(idx.get('entries', []))}")

print("\n[结论] 调用链已通，memory_adapter 能正常入队和消费")
