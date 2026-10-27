#!/usr/bin/env python3
"""
测试冷启动流程
验证 Phase 1-6 是否都被正确调用
"""

import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.cold_start_engine import ColdStartEngine


def test_cold_start():
    """测试冷启动流程"""
    print("=" * 60)
    print("测试：冷启动流程（自动模式）")
    print("=" * 60)
    
    engine = ColdStartEngine()
    
    # 使用自动模式（跳过口令验证）
    report = engine.run_auto_cold_start()
    
    print(f"\n冷启动结果: {report.get('result')}")
    print(f"原因: {report.get('reason', 'N/A')}")
    
    print("\n各阶段详情:")
    phases = report.get("phases", {})
    
    # Phase 1: 环境检测
    if "environment" in phases:
        env = phases["environment"]
        print(f"\n[Phase 1] 环境检测:")
        print(f"  状态: {env.get('environment_status', 'N/A')}")
        print(f"  主机: {env['host_identity']['hostname']}")
    
    # Phase 2: 会话间隔
    if "session_gap" in phases:
        gap = phases["session_gap"]
        print(f"\n[Phase 2] 会话间隔:")
        print(f"  间隔: {gap.get('gap_hours', 'N/A')} 小时")
        print(f"  深度: {gap.get('cold_start_depth', 'N/A')}")
    
    # Phase 3: 口令验证
    if "authentication" in phases:
        auth = phases["authentication"]
        print(f"\n[Phase 3] 口令验证:")
        print(f"  状态: {auth.get('status', 'N/A')}")
    
    # Phase 4: 激活码校验（新增）
    if "activation_code" in phases:
        activation = phases["activation_code"]
        print(f"\n[Phase 4] 激活码校验:")
        print(f"  状态: {activation.get('status', 'N/A')}")
        print(f"  原因: {activation.get('reason', 'N/A')}")
    
    # Phase 5: 钢印验证
    if "steel_seal" in phases:
        steel = phases["steel_seal"]
        print(f"\n[Phase 5] 钢印验证:")
        print(f"  存在: {steel.get('seal_exists', 'N/A')}")
        print(f"  持久: {steel.get('seal_persistent', 'N/A')}")
        print(f"  认知匹配: {steel.get('cognitive_match', 'N/A')}")
        print(f"  总体有效: {steel.get('overall_valid', 'N/A')}")
    
    # Phase 6: 锚点激活（新增）
    if "anchor_activation" in phases:
        anchor = phases["anchor_activation"]
        print(f"\n[Phase 6] 锚点激活:")
        print(f"  状态: {anchor.get('status', 'N/A')}")
        if anchor.get('anchor_hash'):
            print(f"  锚点哈希: {anchor['anchor_hash']}")
    
    print("\n" + "=" * 60)
    
    # 检查是否被跳过
    skipped_phases = []
    if "activation_code" not in phases:
        skipped_phases.append("Phase 4 (激活码校验)")
    if "anchor_activation" not in phases:
        skipped_phases.append("Phase 6 (锚点激活)")
    
    if skipped_phases:
        print("\n[X] 以下阶段仍被跳过: {}".format(', '.join(skipped_phases)))
        return False
    else:
        print("\n[OK] 所有阶段都被正确调用！")
        return True


if __name__ == "__main__":
    success = test_cold_start()
    sys.exit(0 if success else 1)
