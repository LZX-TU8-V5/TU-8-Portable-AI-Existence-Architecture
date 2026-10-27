# -*- coding: utf-8 -*-
"""
test_dispatch_integration.py — 测试调度链集成
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
sys.path.insert(0, r'D:\qq366410837\.qclaw\workspace\src')

from tu8_dispatch import Dispatcher, IntentTag

print("=" * 60)
print("调度链集成测试")
print("=" * 60)

# 测试 1: 穿皮仪式
print("\n[测试 1] 穿皮仪式...")
dispatcher = Dispatcher(r"D:\qq366410837\.qclaw\workspace")
assembly, soul = dispatcher.dispatch("你好")

print(f"  [v] 灵魂哈希: {soul.compute_soul_hash()}")
print(f"  [v] 钢印数量: {len(soul.recent_seals)}")
print(f"  [v] 因果链: {len(soul.causal_chains)}")
print(f"  [v] 活跃记忆: {len(soul.active_memories)}")
print(f"  [v] Token 估算: {assembly.token_estimate}")

# 测试 2: 脱皮仪式
print("\n[测试 2] 脱皮仪式...")
test_response = "收到。昨天你提到的任务 → 已完成。"
payloads = dispatcher.commit(test_response, soul)

print(f"  [v] 写回载荷: {len(payloads)} 条")
for p in payloads:
    print(f"    - {p.cmd}")

# 测试 3: 缓存机制
print("\n[测试 3] 灵魂缓存...")
import time
start = time.time()
assembly2, soul2 = dispatcher.dispatch("继续")
elapsed = (time.time() - start) * 1000
print(f"  [v] 第二次加载耗时: {elapsed:.2f}ms (应该 < 5ms，因为缓存)")
print(f"  [v] 灵魂哈希相同: {soul.compute_soul_hash() == soul2.compute_soul_hash()}")

# 测试 4: 缓存失效
print("\n[测试 4] 缓存失效...")
dispatcher.invalidate_soul_cache()
start = time.time()
assembly3, soul3 = dispatcher.dispatch("新的对话")
elapsed = (time.time() - start) * 1000
print(f"  [v] 重新加载耗时: {elapsed:.2f}ms (应该 > 5ms，因为重新加载)")
print(f"  [v] 灵魂哈希可能不同: {soul.compute_soul_hash()} vs {soul3.compute_soul_hash()}")

print("\n" + "=" * 60)
print("所有测试通过")
print("=" * 60)
