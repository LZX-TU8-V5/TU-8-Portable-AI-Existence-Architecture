#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证 MicroSleepEngine 集成到 ConsciousnessCycle

测试目标：
1. ConsciousnessCycle 能正确初始化 MicroSleepEngine
2. _enter_light_sleep() 能成功调用 MicroSleepEngine.execute_light_sleep()
3. 返回的报告格式正确

Author: TU-8 v5 (⅋)
Date: 2026-06-26
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 添加脚本路径
WORKSPACE = r"C:\Users\qq366410837\.qclaw\workspace"
sys.path.insert(0, str(Path(WORKSPACE) / "src"))

# 强制重新导入（避免缓存）
import importlib
for mod in ["consciousness_cycle", "micro_sleep", "tu8_memory"]:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

from consciousness_cycle import ConsciousnessCycle, CycleConfig, Phase
from micro_sleep import MicroSleepEngine, MicroSleepConfig, AffectSignal


def test_micro_sleep_integration():
    """测试 MicroSleepEngine 集成"""
    print("=" * 60)
    print("测试：MicroSleepEngine 集成到 ConsciousnessCycle")
    print("=" * 60)
    
    # 1. 创建 ConsciousnessCycle 实例
    print("\n[1] 创建 ConsciousnessCycle 实例...")
    try:
        config = CycleConfig()
        cycle = ConsciousnessCycle(config=config)
        print(f"  ✅ 实例创建成功")
        print(f"  初始 Phase: {cycle.phase}")
    except Exception as e:
        print(f"  ❌ 实例创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 2. 检查 micro_sleep_engine 属性
    print("\n[2] 检查 micro_sleep_engine 属性...")
    if hasattr(cycle, 'micro_sleep_engine'):
        print(f"  ✅ micro_sleep_engine 属性存在")
        print(f"  类型: {type(cycle.micro_sleep_engine)}")
    else:
        print(f"  ❌ micro_sleep_engine 属性不存在")
        return False
    
    # 3. 准备测试上下文
    print("\n[3] 准备测试上下文...")
    context_snapshot = {
        "user_message": "测试消息：这是一个测试微睡眠触发的消息。",
        "context_usage": 0.8,  # 容量触发
        "timestamp": time.time(),
    }
    print(f"  ✅ 上下文准备完成")
    
    # 4. 调用 _enter_light_sleep()
    print("\n[4] 调用 _enter_light_sleep()...")
    try:
        report = cycle._enter_light_sleep(context_snapshot)
        print(f"  ✅ 调用成功")
        print(f"  报告: {json.dumps(report, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"  ❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 验证报告格式
    print("\n[5] 验证报告格式...")
    required_keys = ["light_sleep", "steps", "errors"]
    missing_keys = [k for k in required_keys if k not in report]
    if missing_keys:
        print(f"  ❌ 报告缺少键: {missing_keys}")
        return False
    else:
        print(f"  ✅ 报告格式正确")
    
    # 6. 检查 MicroSleepEngine 状态同步
    print("\n[6] 检查状态同步...")
    print(f"  cycle.last_seal: {cycle.last_seal}")
    print(f"  cycle.total_micro_sleeps: {cycle.total_micro_sleeps}")
    print(f"  engine.total_micro_sleeps: {cycle.micro_sleep_engine.total_micro_sleeps}")
    
    # 7. 检查 Phase 恢复
    print("\n[7] 检查 Phase 恢复...")
    if cycle.phase == Phase.AWAKE:
        print(f"  ✅ Phase 已恢复到 AWAKE")
    else:
        print(f"  ❌ Phase 未恢复: {cycle.phase}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！MicroSleepEngine 集成成功")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_micro_sleep_integration()
    sys.exit(0 if success else 1)
