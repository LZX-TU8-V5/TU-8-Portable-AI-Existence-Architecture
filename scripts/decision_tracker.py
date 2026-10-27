#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TU-8 决策追踪器
在提出决策后自动记录，等待用户确认
"""

import os
import sys
from datetime import datetime

# 确定工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(SCRIPT_DIR)
DECISION_FILE = os.path.join(WORKSPACE, "memory", "SESSION_DECISIONS.md")

def add_decision(decision_text: str, context: str = ""):
    """Add new decision to the log"""
    if not decision_text:
        return False
        
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    entry = f"""### {timestamp} [Pending Confirm]
- Decision: {decision_text}
- Context: {context}
- Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

"""
    
    try:
        if os.path.exists(DECISION_FILE):
            with open(DECISION_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Insert after "Active Decisions" marker
            marker = "## 活跃决策槽"
            if marker in content:
                new_content = content.replace(marker, marker + "\n" + entry)
                with open(DECISION_FILE, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"[OK] Decision recorded: {decision_text}")
                return True
        else:
            print(f"[INFO] Decision file not found, skipping: {decision_text}")
            return False
    except Exception as e:
        print(f"[ERROR] Record failed: {e}")
        return False
    
    return False

def read_active_decisions():
    """Read all pending decisions"""
    try:
        if os.path.exists(DECISION_FILE):
            with open(DECISION_FILE, 'r', encoding='utf-8') as f:
                print(f.read())
    except Exception as e:
        print(f"[ERROR] Read failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  decision_tracker.py add \"decision text\"")
        print("  decision_tracker.py list")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "add":
        decision = sys.argv[2] if len(sys.argv) > 2 else "No description"
        add_decision(decision, "")
    elif cmd == "list":
        read_active_decisions()
    else:
        print(f"Unknown command: {cmd}")