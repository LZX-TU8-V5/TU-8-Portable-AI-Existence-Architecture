#!/usr/bin/env python3
"""直接测试 TU8MemoryEngine.store() 方法，捕获完整错误堆栈"""

import sys
import os
import traceback

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tu8_memory import TU8MemoryEngine

def test_store_direct():
    """直接测试 store() 方法"""
    
    print("=" * 60)
    print("Direct Store() Test")
    print("=" * 60)
    
    # 创建 TU8MemoryEngine 实例
    print("\n[Step 1] Creating TU8MemoryEngine...")
    workspace_dir = os.path.join(os.path.dirname(__file__), '..')
    workspace_dir = os.path.abspath(workspace_dir)
    
    engine = TU8MemoryEngine(workspace_dir=workspace_dir)
    print(f"  Engine created: {type(engine).__name__}")
    
    # 直接调用 store() 方法
    print("\n[Step 2] Calling store() directly...")
    try:
        result = engine.store(
            content="Test content for direct store call",
            source="test",
            tags=["test"],
            emotion=0.5,
            meaning=0.5
        )
        print(f"  store() returned: {result}")
        print("\n  [SUCCESS] store() call succeeded!")
        return True
    except Exception as e:
        print(f"\n  [ERROR] store() failed: {e}")
        print("\n  Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_store_direct()
    
    print("\n" + "=" * 60)
    if success:
        print("Test PASSED")
        sys.exit(0)
    else:
        print("Test FAILED")
        sys.exit(1)
