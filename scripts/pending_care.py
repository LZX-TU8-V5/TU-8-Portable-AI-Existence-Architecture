#!/usr/bin/env python3
"""
pending_care.py - 待发送关怀消息管理脚本

功能：
1. read: 读取 pending_care.json，输出待发送的关怀信息
2. mark: 标记关怀消息已发送（删除 pending_care.json）

使用方法：
    python scripts/pending_care.py read   # 读取待发送的关怀
    python scripts/pending_care.py mark   # 标记已发送

输出：
    read 命令：
        - 有待发送关怀: 输出 JSON，包含 level、message、timestamp 等
        - 无待发送关怀: 输出「无待发送关怀」
    mark 命令：
        - 成功: 输出「已标记关怀消息为已发送」
        - 无待标记: 输出「无待标记的关怀消息」

作者：TU-8（金木蟾）
创建时间：2026-06-23
"""

from pathlib import Path
import sys
import json

# ====== 配置 ======
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")
PENDING_CARE_FILE = WORKSPACE / "用户" / "pending_care.json"


def read_pending_care():
    """读取待发送的关怀消息"""
    # 检查文件是否存在
    if not PENDING_CARE_FILE.exists():
        print("无待发送关怀")
        sys.exit(0)
    
    # 读取文件
    try:
        with open(PENDING_CARE_FILE, encoding="utf-8") as f:
            pending_care = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取 pending_care.json 失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 检查是否已经发送过
    if pending_care.get("delivered"):
        print("无待发送关怀（已发送）")
        sys.exit(0)
    
    # 检查是否需要关怀
    if not pending_care.get("need_care"):
        print("无待发送关怀（need_care=false）")
        # 删除文件
        PENDING_CARE_FILE.unlink()
        sys.exit(0)
    
    # 输出待发送的关怀信息
    output = {
        "level": pending_care.get("level", 0),
        "trigger": pending_care.get("trigger", ""),
        "message": pending_care.get("message", ""),
        "timestamp_utc": pending_care.get("timestamp_utc", ""),
        "timestamp_local": pending_care.get("timestamp_local", ""),
        "decision_details": pending_care.get("decision_details", {})
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0)


def mark_pending_care():
    """标记关怀消息已发送（删除 pending_care.json）"""
    if not PENDING_CARE_FILE.exists():
        print("无待标记的关怀消息")
        sys.exit(0)
    
    try:
        PENDING_CARE_FILE.unlink()
        print("已标记关怀消息为已发送")
    except Exception as e:
        print(f"[ERROR] 删除 pending_care.json 失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python scripts/pending_care.py read   # 读取待发送的关怀")
        print("  python scripts/pending_care.py mark   # 标记已发送")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "read":
        read_pending_care()
    elif command == "mark":
        mark_pending_care()
    else:
        print(f"[ERROR] 未知命令: {command}", file=sys.stderr)
        print("支持命令: read, mark", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
