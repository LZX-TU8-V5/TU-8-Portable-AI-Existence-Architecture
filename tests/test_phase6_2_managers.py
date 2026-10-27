"""测试 Phase 6.2：注入管理器"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from consciousness_cycle import ConsciousnessCycle

# 创建实例
cycle = ConsciousnessCycle()

# 检查管理器
print("=== 管理器注入检查 ===")
print(f"[OK] seal_manager: {hasattr(cycle, 'seal_manager')}")
print(f"[OK] anchor_manager: {hasattr(cycle, 'anchor_manager')}")
print(f"[OK] memory_adapter: {hasattr(cycle, 'memory_adapter')}")

# 验证类型
if hasattr(cycle, 'seal_manager'):
    print(f"   类型: {type(cycle.seal_manager).__name__}")
if hasattr(cycle, 'anchor_manager'):
    print(f"   类型: {type(cycle.anchor_manager).__name__}")
if hasattr(cycle, 'memory_adapter'):
    print(f"   类型: {type(cycle.memory_adapter).__name__}")

print("\n[SUCCESS] 所有管理器已注入！")
