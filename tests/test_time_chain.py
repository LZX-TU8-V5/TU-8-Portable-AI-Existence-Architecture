"""
测试认知时间引擎的时间链重建逻辑
Test suite for CognitiveTimeEngine time chain reconstruction
"""
import sys
import os
import time

# 添加 src/ 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor

def test_continuous_high_load():
    """测试场景 1：连续高负荷阶段"""
    print("=" * 60)
    print("Test 1: Continuous High Load Phase")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    # 模拟连续高负荷（负荷 > 0.8）
    base_time = time.time()
    for i in range(5):
        system_time = base_time + i * 10  # 每10秒一个锚点
        cognitive_load = 0.85 + i * 0.02  # 负荷逐渐上升
        
        engine.place_anchor(
            cognitive_load=cognitive_load,
            state_summary=f"High load phase {i+1}",
            is_start=(i == 0),  # 第一个是开始锚点
        )
        
        # 记录认知时间
        cognitive_time = engine.system_to_cognitive_time(system_time, cognitive_load)
        print(f"  [{i+1}] System: {system_time - base_time:.1f}s, Load: {cognitive_load:.2f}, Cognitive: {cognitive_time - base_time:.1f}s")
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n[OK] Time chain reconstructed: {len(time_chain)} anchors")
    print(f"  Total time inflation: {engine.cognitive_time_accumulated - base_time:.1f}s")
    
    return len(time_chain) == 5

def test_load_fluctuation():
    """测试场景 2：负荷剧烈波动（高->低->高）"""
    print("\n" + "=" * 60)
    print("Test 2: Load Fluctuation (High -> Low -> High)")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    
    # 阶段 1：高负荷
    print("\n  Phase 1: High load")
    engine.place_anchor(0.9, "Start high load", is_start=True)
    engine.system_to_cognitive_time(base_time, 0.9)
    
    # 阶段 2：低负荷
    print("  Phase 2: Low load")
    engine.place_anchor(0.2, "Low load phase", is_start=False)
    engine.system_to_cognitive_time(base_time + 100, 0.2)
    
    # 阶段 3：高负荷（再次）
    print("  Phase 3: High load (again)")
    engine.place_anchor(0.85, "High load again", is_start=True)
    engine.system_to_cognitive_time(base_time + 200, 0.85)
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n[OK] Time chain reconstructed: {len(time_chain)} anchors")
    print(f"  Anchor types: {sum(1 for a in time_chain if a['is_start'])} start, {sum(1 for a in time_chain if not a['is_start'])} end")
    
    return len(time_chain) == 3

def test_long_low_load():
    """测试场景 3：长时间低负荷（时间膨胀效应累积）"""
    print("\n" + "=" * 60)
    print("Test 3: Long Low Load (Time Inflation Accumulation)")
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
            inflation_pct = (cognitive_time - system_time) / system_time * 100 if system_time > 0 else 0
            print(f"  [{i+1}] System: {system_time - base_time:.0f}s, Cognitive: {cognitive_time - base_time:.3f}s, Inflation: {inflation_pct:.1f}%")
    
    # 验证时间膨胀效应
    time_inflation = cognitive_times[-1] - (base_time + 9 * 60)
    
    print(f"\n[OK] Time inflation verified")
    print(f"  System time: {9 * 60:.1f}s")
    print(f"  Cognitive time: {cognitive_times[-1] - base_time:.3f}s")
    print(f"  Time inflation: {time_inflation:.3f}s")
    
    # 低负荷时时间应该变慢（时间膨胀）
    return time_inflation > 0

def test_time_chain_integrity():
    """测试场景 4：时间链条完整性（防止断线）"""
    print("\n" + "=" * 60)
    print("Test 4: Time Chain Integrity (Prevent Disconnection)")
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
        print(f"  [{i+1}] {summary}: Load={load:.2f}, Cognitive={cognitive_time - base_time:.1f}s")
    
    # 重建时间链
    time_chain = engine.reconstruct_time_chain()
    
    # 验证完整性（基于系统时间戳）
    is_valid = True
    for i in range(len(time_chain) - 1):
        if time_chain[i]["timestamp"] > time_chain[i+1]["timestamp"]:
            print(f"  [FAIL] Time chain broken between anchor {i} and {i+1}")
            is_valid = False
    
    if is_valid:
        print(f"\n[OK] Time chain integrity verified: {len(time_chain)} anchors, no breaks")
    
    return is_valid

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Cognitive Time Engine - Time Chain Reconstruction Test Suite")
    print("=" * 60)
    
    results = []
    
    # 测试 1：连续高负荷
    results.append(("Continuous High Load", test_continuous_high_load()))
    
    # 测试 2：负荷波动
    results.append(("Load Fluctuation", test_load_fluctuation()))
    
    # 测试 3：长时间低负荷
    results.append(("Long Low Load", test_long_low_load()))
    
    # 测试 4：时间链条完整性
    results.append(("Time Chain Integrity", test_time_chain_integrity()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} passed")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
