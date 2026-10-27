#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试深度集成：认知组件已集成到 consciousness_cycle.py
验证 P2 自我知识功能是否正常工作
"""

import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def test_integration():
    """测试深度集成"""
    print("=" * 60)
    print("Deep Integration Test - P2 Cognitive Components")
    print("=" * 60)
    
    try:
        # 导入 ConsciousnessCycle
        from consciousness_cycle import ConsciousnessCycle
        
        print("\n[1] Initializing ConsciousnessCycle...")
        cycle = ConsciousnessCycle()
        print("    OK: ConsciousnessCycle initialized")
        
        # 验证认知组件是否已初始化
        print("\n[2] Checking cognitive components...")
        components = [
            ("cognitive_evaluator", "CognitiveLoadEvaluator"),
            ("cognitive_time_engine", "CognitiveTimeEngine"),
            ("cognitive_aligner", "CognitiveManifoldAligner"),
            ("cognitive_integration", "CognitiveIntegration"),
        ]
        
        all_ok = True
        for attr_name, class_name in components:
            if hasattr(cycle, attr_name):
                print(f"    OK: {attr_name} initialized")
            else:
                print(f"    FAIL: {attr_name} NOT FOUND")
                all_ok = False
        
        if not all_ok:
            print("\n❌ Some cognitive components are missing!")
            return False
        
        # 测试 tick() 方法（带认知处理）
        print("\n[3] Testing tick() with cognitive processing...")
        
        test_context = {
            "user_message": "Test message for cognitive load evaluation",
            "kv_cache_size_mb": 512,
            "active_tokens": 1024,
            "context_window_used": 0.6,
        }
        
        report = cycle.tick(context_snapshot=test_context)
        
        print(f"    Cycle: {report.get('cycle', 'N/A')}")
        print(f"    Cognitive Load: {report.get('cognitive_load', 'N/A')}")
        print(f"    Cognitive Time: {report.get('cognitive_time', 'N/A')}")
        print(f"    Cognitive Steps: {report.get('cognitive_steps', 'N/A')}")
        
        # 验证认知指标是否在报告中
        if "cognitive_load" in report and "cognitive_time" in report:
            print("    OK: Cognitive metrics in tick() report")
        else:
            print("    FAIL: Cognitive metrics missing from report")
            return False
        
        # 测试微睡眠（带认知处理）
        print("\n[4] Testing micro-sleep with cognitive processing...")
        
        ms_report = cycle._enter_micro_sleep(test_context)
        
        if "cognitive_status" in ms_report:
            print("    OK: Cognitive status in micro-sleep report")
            cognitive_status = ms_report["cognitive_status"]
            print(f"    Total Steps: {cognitive_status.get('total_steps', 'N/A')}")
            print(f"    High Load Count: {cognitive_status.get('high_load_count', 'N/A')}")
        else:
            print("    WARNING: Cognitive status not in micro-sleep report")
        
        # 测试时间链重建
        print("\n[5] Testing time chain reconstruction...")
        time_chain = cycle.cognitive_time_engine.reconstruct_time_chain()
        print(f"    Time chain anchors: {len(time_chain)}")
        
        if len(time_chain) > 0:
            print("    OK: Time chain reconstructed")
            for i, anchor in enumerate(time_chain[:3]):  # 显示前 3 个
                print(f"      [{i+1}] {anchor['state_summary']} (load={anchor['cognitive_load']:.2f})")
        else:
            print("    WARNING: Time chain is empty")
        
        # 测试认知整合状态
        print("\n[6] Testing cognitive integration status...")
        integration_status = cycle.cognitive_integration.get_status()
        print(f"    Total Steps: {integration_status.get('total_steps', 0)}")
        print(f"    High Load Count: {integration_status.get('high_load_count', 0)}")
        print(f"    Consolidation Count: {integration_status.get('consolidation_count', 0)}")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! Deep integration successful.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
