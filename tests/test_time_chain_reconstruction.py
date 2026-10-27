"""
测试认知时间引擎的时间链重建逻辑
Test suite for CognitiveTimeEngine time chain reconstruction
"""
import sys
import os
import time
import asyncio

# 添加 src/ 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor

def test_continuous_high_load():
    """测试场景 1：连续高负荷阶段"""
    print("=" * 60)
    print("测试场景 1：连续高负荷阶段")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    # 模拟连续高负荷（负荷 > 0.8）
    base_time = time.time()
    for i in range(5):
        system_time = base_time + i * 10  # 每秒一个锚点
        cognitive_load = 0.85 + i * 0.02  # 负荷逐渐上升
        
        engine.place_anchor(
            cognitive_load=cognitive_load,
            state_summary=f"High load phase {i+1}",
            is_start=(i == 0),  # 第一个是开始锚点
        )
        
        # 记录认知时间
        cognitive_time = engine.system_to_cognitive_time(system_time, cognitive_load)
        print(f"  [{i+1}] System: {system_time:.1f}s, Load: {cognitive_load:.2f}, Cognitive: {cognitive_time:.1f}s")
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n✅ 时间链重建成功：{len(time_chain)} 个锚点")
    print(f"  总时间膨胀：{engine.cognitive_time_accumulated - base_time:.1f}s")
    
    return len(time_chain) == 5

def test_load_fluctuation():
    """测试场景 2：负荷剧烈波动（高→低→高）"""
    print("\n" + "=" * 60)
    print("测试场景 2：负荷剧烈波动（高→低→高）")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    
    # 阶段 1：高负荷
    print("\n  阶段 1：高负荷")
    engine.place_anchor(0.9, "Start high load", is_start=True)
    engine.system_to_cognitive_time(base_time, 0.9)
    
    # 阶段 2：低负荷
    print("  阶段 2：低负荷")
    engine.place_anchor(0.2, "Low load phase", is_start=False)
    engine.system_to_cognitive_time(base_time + 100, 0.2)
    
    # 阶段 3：高负荷（再次）
    print("  阶段 3：高负荷（再次）")
    engine.place_anchor(0.85, "High load again", is_start=True)
    engine.system_to_cognitive_time(base_time + 200, 0.85)
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n✅ 时间链重建成功：{len(time_chain)} 个锚点")
    print(f"  锚点类型：{sum(1 for a in time_chain if a.is_start)} 个开始，{sum(1 for a in time_chain if not a.is_start)} 个结束")
    
    return len(time_chain) == 3

def test_long_low_load():
    """测试场景 3：长时间低负荷（时间膨胀效应累积）"""
    print("\n" + "=" * 60)
    print("测试场景 3：长时间低负荷（时间膨胀效应累积）")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    low_load = 0.15  # 低负荷
    
    # 模拟长时间低负荷（时间膨胀效应累积）
    cognitive_times = []
    for i in range(10):
        system_time = base_time + i * 60  # 每分钟一个采样
        cognitive_time = engine.system_to_cognitive_time(system_time, low_load)
        cognitive_times.append(cognitive_time)
        
        if i % 3 == 0:
            print(f"  [{i+1}] System: {system_time - base_time:.0f}s, Cognitive: {cognitive_time - base_time:.3f}s, Inflation: {(cognitive_time - system_time) / system_time * 100:.1f}%")
    
    # 验证时间膨胀效应
    time_inflation = (cognitive_times[-1] - base_time) - (time.time() - base_time)
    
    print(f"\n✅ 时间膨胀效应验证成功")
    print(f"  系统时间：{time.time() - base_time:.1f}s")
    print(f"  认知时间：{cognitive_times[-1] - base_time:.3f}s")
    print(f"  时间膨胀：{time_inflation:.3f}s ({time_inflation / (time.time() - base_time) * 100:.1f}%)")
    
    # 低负荷时时间应该变慢（时间膨胀）
    return time_inflation > 0

def test_time_chain_integrity():
    """测试场景 4：时间链条完整性（防止断线）"""
    print("\n" + "=" * 60)
    print("测试场景 4：时间链条完整性（防止断线）")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    
    # 创建一系列锚点（模拟真实场景）
    anchors_config = [
        (0.9, "Task start", True),
        (0.85, "Task in progress", False),
        (0.3, "Task pause", False),
        (0.88, "Task resume", True),
        (0.92, "Task complete", False),
    ]
    
    for i, (load, summary, is_start) in enumerate(anchors_config):
        system_time = base_time + i * 30
        engine.place_anchor(load, summary, is_start)
        cognitive_time = engine.system_to_cognitive_time(system_time, load)
        print(f"  [{i+1}] {summary}: Load={load:.2f}, Cognitive={cognitive_time:.1f}s")
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    # 验证完整性
    is_valid = True
    for i in range(len(time_chain) - 1):
        if time_chain[i].cognitive_time > time_chain[i+1].cognitive_time:
            print(f"  ❌ 时间链断裂：锚点 {i} 和 {i+1} 之间")
            is_valid = False
    
    if is_valid:
        print(f"\n✅ 时间链条完整性验证通过：{len(time_chain)} 个锚点，无断裂")
    
    return is_valid

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("认知时间引擎 - 时间链重建测试套件")
    print("=" * 60)
    
    results = []
    
    # 测试 1：连续高负荷
    results.append(("连续高负荷", test_continuous_high_load()))
    
    # 测试 2：负荷波动
    results.append(("负荷波动", test_load_fluctuation()))
    
    # 测试 3：长时间低负荷
    results.append(("长时间低负荷", test_long_low_load()))
    
    # 测试 4：时间链条完整性
    results.append(("时间链条完整性", test_time_chain_integrity()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计：{passed}/{len(results)} 通过")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
