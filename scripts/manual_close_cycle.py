#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动关环脚本

功能：
1. 创建今天的活动期（如果不存在）
2. 结束活动期
3. 触发复盘

使用方法：
    python scripts/manual_close_cycle.py

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import sys
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入测试目标
from scripts.dual_line_verification_system import DualLineVerificationSystem
from scripts.activity_period_tracker import ActivityPeriodTracker
from scripts.retrospective_period_provider import RetrospectivePeriodProvider


def main():
    """主函数"""
    print("=" * 60)
    print("手动关环流程")
    print("=" * 60)
    print()
    
    # 1. 验证（如果未验证）
    print("[步骤1] 检查验证状态...")
    verifier = DualLineVerificationSystem()
    verify_result = verifier.verify('tu8_2026')
    print(f"- 验证结果: {verify_result['success']}")
    print(f"- 消息: {verify_result['message']}")
    print()
    
    # 2. 创建/检查活动期
    print("[步骤2] 检查活动期...")
    tracker = ActivityPeriodTracker()
    activity = tracker.get_current_activity_period()
    
    if not activity or not activity.get('is_active'):
        print("- 无活跃活动期，创建新的活动期...")
        activity = tracker.mark_activity_start(verification_method='manual')
        print(f"- 活动期已创建: {activity['start_hour']:02d}:{activity['start_minute']:02d}")
    else:
        print(f"- 活动期已存在: {activity['start_hour']:02d}:{activity['start_minute']:02d}")
    print()
    
    # 3. 结束活动期
    print("[步骤3] 结束活动期...")
    tracker.end_current_activity_period()
    print("- 活动期已结束")
    print()
    
    # 4. 触发复盘
    print("[步骤4] 触发复盘...")
    
    # 删除今天的复盘日志（测试用）
    retrospective_log = project_root / "logs" / "retrospective_log.json"
    if retrospective_log.exists():
        print("- 删除今日复盘日志（测试模式）...")
        retrospective_log.unlink()
    
    provider = RetrospectivePeriodProvider()
    result = provider.trigger_retrospective()
    
    if result['should_trigger']:
        print("- ✅ 复盘已触发！")
        print(f"- 复盘周期: {result['period']['period_label']}")
        print(f"- 提示长度: {len(result['prompt'])} 字符")
        print()
        print("=" * 60)
        print("复盘提示：")
        print("=" * 60)
        print()
        print(result['prompt'])
        print()
        print("=" * 60)
    else:
        print("- ❌ 未触发复盘")
        print(f"- 原因: {result.get('prompt', '未知')}")
        print()
    
    print("=" * 60)
    print("关环流程完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
