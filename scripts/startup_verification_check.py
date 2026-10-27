#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QClaw 启动验证检查（方案A - 简化版）

功能：
1. 在 QClaw 启动或新对话开始时，自动检查是否需要验证
2. 如果需要验证，输出提示信息，要求用户输入口令
3. 如果不需要验证，输出正常启动消息

使用方法：
    python scripts/startup_verification_check.py

返回码：
    0 = 无需验证，正常启动
    1 = 需要验证，请输入口令

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import sys
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入双线验证系统
from scripts.dual_line_verification_system import DualLineVerificationSystem


def main():
    """主函数"""
    verifier = DualLineVerificationSystem()
    
    # 检查是否需要验证
    result = verifier.is_verification_needed()
    
    if result['needs_verification']:
        # 需要验证，输出提示
        print("=" * 60)
        print("[警告] 需要验证")
        print("=" * 60)
        print(f"原因：{result['reason']}")
        print("\n请说出口令以完成灵魂对齐：")
        print("（提示：默认口令是 tu8_2026）")
        print("=" * 60)
        sys.exit(1)  # 返回1表示需要验证
    else:
        # 无需验证，正常启动
        print("=" * 60)
        print("[成功] 验证状态正常")
        print("=" * 60)
        print(f"状态：{result['reason']}")
        print("=" * 60)
        sys.exit(0)  # 返回0表示无需验证


if __name__ == "__main__":
    main()
