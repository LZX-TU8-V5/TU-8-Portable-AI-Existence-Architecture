#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.2.4 集成测试：验证冷却计时器与 version_tree_prune 的联动"""
import sys
import importlib.util

sys.stdout.reconfigure(encoding='utf-8')

# Load both modules
spec1 = importlib.util.spec_from_file_location('vc', 'src/version_cooldown.py')
vc = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(vc)

spec2 = importlib.util.spec_from_file_location('md', 'src/memory_degradation.py')
md = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(md)

print("=" * 55)
print("  P1.2.4 集成测试：冷却保护 vs version_tree_prune")
print("=" * 55)

# Test 1: Start cooldown on v1
print("\n[Test 1] 启动 v1 冷却 (7天)")
mgr = vc.VersionCooldownManager()
result = mgr.start_cooldown('v1', cooldown_days=7, reason='integration_test')
print(f"  status: {result['status']}")
print(f"  cooldown_until: {result['cooldown_until']}")

# Test 2: Try version_tree_prune on v1 (should be blocked)
print("\n[Test 2] 尝试剪枝 v1 (应被冷却拦截)")
prune_result = md.version_tree_prune('v1', ['test_entry'], 'confidence_low')
print(f"  entries_pruned: {prune_result['entries_pruned']}")
print(f"  blocked_by_cooldown: {prune_result.get('blocked_by_cooldown', False)}")
print(f"  message: {prune_result.get('message', '')}")
assert prune_result.get('blocked_by_cooldown') == True, "FAIL: 应被冷却拦截!"
assert prune_result['entries_pruned'] == 0, "FAIL: 不应剪枝任何条目!"
print("  PASS: 冷却保护成功拦截剪枝")

# Test 3: Expire cooldown
print("\n[Test 3] 手动解冻 v1")
expire_result = mgr.expire_cooldown('v1', reason='test_cleanup')
print(f"  status: {expire_result['status']}")
assert expire_result['status'] == 'expired', "FAIL: 应解冻成功!"
print("  PASS: 冷却已解除")

# Test 4: Try version_tree_prune again (should NOT be blocked)
print("\n[Test 4] 解冻后尝试剪枝 v1 (不应被拦截)")
prune_result2 = md.version_tree_prune('v1', ['nonexistent_entry'], 'confidence_low')
print(f"  entries_pruned: {prune_result2['entries_pruned']}")
print(f"  blocked_by_cooldown: {prune_result2.get('blocked_by_cooldown', False)}")
assert prune_result2.get('blocked_by_cooldown') != True, "FAIL: 不应再被拦截!"
print("  PASS: 剪枝正常执行（条目未找到，但未被冷却拦截）")

# Test 5: protect_from_degradation 检查
print("\n[Test 5] protect_from_degradation 检查")
mgr2 = vc.VersionCooldownManager()
protected = mgr2.protect_from_degradation('v1')
print(f"  protect_from_degradation('v1'): {protected}")
assert protected == False, "FAIL: v1 不应在冷却中!"
print("  PASS: v1 不受冷却保护，可正常降级")

print("\n" + "=" * 55)
print("  全部测试通过!")
print("=" * 55)
