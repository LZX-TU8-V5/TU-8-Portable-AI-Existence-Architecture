"""
复盘触发器（供 cron 任务调用）

功能：
1. 检查是否应该触发复盘（基于动态活动期）
2. 如果应该触发，生成复盘提示
3. 输出复盘提示（供 agent 发送）

使用方法：
    python scripts/trigger_retrospective.py

返回码：
    0 = 不应该触发复盘
    1 = 应该触发复盘（提示已输出到 stdout）

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import sys
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入复盘周期提供器
from scripts.retrospective_period_provider import RetrospectivePeriodProvider


def main():
    """主函数"""
    provider = RetrospectivePeriodProvider()
    
    # 检查是否应该触发复盘
    result = provider.trigger_retrospective()
    
    if result['should_trigger']:
        # 应该触发复盘，输出提示
        print(result['prompt'])
        sys.exit(1)  # 返回1表示应该触发
    else:
        # 不应该触发复盘
        print("[复盘触发器] 当前不需要复盘")
        sys.exit(0)  # 返回0表示不需要触发


if __name__ == "__main__":
    main()
