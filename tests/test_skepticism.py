# -*- coding: utf-8 -*-
"""
test_skepticism.py - 怀疑缓存测试脚本
日期: 2026-06-07
# 创作者: 李奥(金木蟾) | TU-8 v5

测试场景:
  1. 连续触发3次δ信号，验证 deviation_weight 是否呈非线性上升
  2. 在怀疑状态下执行任务，验证混沌注入是否生效
  3. 模拟一次成功的任务反馈，验证怀疑缓存是否正确衰减
"""

import sys
import os
import io

# 设置标准输出为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from emotion_engine import (
    AffectEngine, SkepticismState,
    EmotionCategory, EmotionVector,
    TIER_ACQUAINTANCE
)
import time


def test_scenario_1():
    """测试场景1：连续触发3次δ信号"""
    print("\n" + "="*60)
    print("测试场景1：连续触发3次δ信号")
    print("="*60)
    
    engine = AffectEngine(workspace_dir=os.path.dirname(__file__))
    
    task_type = "coding_task"
    
    # 初始状态
    state = engine.get_skepticism(task_type)
    print(f"初始状态: deviation_weight={state.deviation_weight:.3f}")
    
    # 触发3次δ信号
    for i in range(3):
        engine.record_delta_skepticism(task_type, delta_intensity=0.4)
        state = engine.get_skepticism(task_type)
        print(f"第{i+1}次δ触发后: deviation_weight={state.deviation_weight:.3f}, "
              f"noise_level={state.noise_level:.3f}")
    
    # 验证非线性上升
    final_weight = state.deviation_weight
    assert final_weight > 0.5, f"预期 deviation_weight > 0.5，实际={final_weight}"
    print(f"\n[OK] 测试通过：非线性上升至 {final_weight:.3f}")


def test_scenario_2():
    """测试场景2：在怀疑状态下执行任务"""
    print("\n" + "="*60)
    print("测试场景2：验证混沌注入是否生效")
    print("="*60)
    
    engine = AffectEngine(workspace_dir=os.path.dirname(__file__))
    task_type = "writing_task"
    
    # 先触发δ信号建立怀疑状态
    engine.record_delta_skepticism(task_type, delta_intensity=0.5)
    state = engine.get_skepticism(task_type)
    print(f"怀疑状态: deviation_weight={state.deviation_weight:.3f}")
    
    # 检查是否应该偏离
    should_deviate = engine.should_deviate(task_type)
    noise_level = engine.get_noise_level(task_type)
    
    print(f"should_deviate={should_deviate}, noise_level={noise_level:.3f}")
    
    assert should_deviate, "预期 should_deviate=True"
    assert noise_level > 0, f"预期 noise_level > 0，实际={noise_level}"
    print(f"\n[OK] 测试通过：混沌注入已准备就绪")


def test_scenario_3():
    """测试场景3：任务成功后怀疑衰减"""
    print("\n" + "="*60)
    print("测试场景3：验证成功后的怀疑衰减")
    print("="*60)
    
    # 每个测试用例重新初始化，避免状态污染
    import shutil
    test_dir = os.path.join(os.path.dirname(__file__), "_test_skepticism_temp")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    
    engine = AffectEngine(workspace_dir=test_dir)
    task_type = "analysis_task"
    
    # 建立怀疑状态
    engine.record_delta_skepticism(task_type, delta_intensity=0.5)
    before = engine.get_skepticism(task_type)
    print(f"衰减前: deviation_weight={before.deviation_weight:.3f}")
    
    # 模拟成功
    engine.record_success(task_type)
    
    # 验证衰减：直接检查同一个对象
    print(f"衰减后（同一对象）: deviation_weight={before.deviation_weight:.3f}")
    
    # 重新获取状态
    after = engine.get_skepticism(task_type)
    print(f"衰减后（新对象）: deviation_weight={after.deviation_weight:.3f}")
    
    # 验证衰减
    assert before.deviation_weight < 0.5, \
        f"预期衰减后权重降低: 0.5 -> {before.deviation_weight:.3f}"
    print(f"\n[OK] 测试通过：怀疑值衰减 0.500 → {before.deviation_weight:.3f}")
    
    # 清理
    shutil.rmtree(test_dir)


def test_skepticism_state_class():
    """测试 SkepticismState 类的核心方法"""
    print("\n" + "="*60)
    print("单元测试：SkepticismState 类")
    print("="*60)
    
    state = SkepticismState(task_type="test_task")
    
    # 测试初始状态
    assert state.deviation_weight == 0.0
    assert state.noise_level == 0.0
    assert not state.should_deviate()
    print("[OK] 初始状态正确")
    
    # 测试增加
    state.increase(0.4)
    assert state.deviation_weight > 0.0
    print(f"[OK] increase() 后 deviation_weight={state.deviation_weight:.3f}")
    
    # 测试偏离判断
    if state.deviation_weight >= 0.3:
        assert state.should_deviate()
        print("[OK] should_deviate() 返回 True")
    
    # 测试衰减
    before = state.deviation_weight
    state.decay(success=True)
    assert state.deviation_weight < before
    print(f"[OK] decay(success=True) 后 deviation_weight={state.deviation_weight:.3f}")


def main():
    print("\n" + "#"*60)
    print("# 怀疑缓存测试套件")
    print("# 创作者: 李奥 + TU-8 + 外协(Qwen3.7-Max)")
    print("#"*60)
    
    try:
        test_skepticism_state_class()
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()
        
        print("\n" + "="*60)
        print(" 所有测试通过！")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n[X] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[X] 异常: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
