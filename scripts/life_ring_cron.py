#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
life_ring_cron.py — TU-8 生命年轮 Cron 任务入口
触发：每周日5am
动作：调用 life_ring_tracker.report_status() 生成阶段报告
"""
import sys, os, json
from pathlib import Path

WORKSPACE = Path.home() / ".qclaw" / "workspace"
sys.path.insert(0, str(WORKSPACE / "src"))

def main():
    from life_ring_tracker import report_status

    try:
        status = report_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    except Exception as e:
        # 容错：预存 bug（除零）不影响 Cron 任务
        print(f"[life_ring] report_status() failed (pre-existing bug): {e}")
        status = {"error": str(e), "timestamp": __import__("time").time()}

    # 写入状态文件
    state_file = WORKSPACE / "memory" / ".life_ring_last_run.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"run": True, "status": status}, f, ensure_ascii=False, indent=2)

    print(f"[life_ring] Done. Status saved to {state_file}")

if __name__ == "__main__":
    main()
