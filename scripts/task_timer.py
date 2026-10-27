#!/usr/bin/env python3
"""
TU-8 任务计时器（task_timer.py）
功能：每次任务开始/结束时自动打点，为全天复盘提供精准数据源
数据文件：task_timer_log.jsonl（与脚本同目录）
"""

import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "task_timer_log.jsonl")


def _now():
    """返回当前时间的 ISO 格式字符串"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _today():
    """返回今天的日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def start(task_name: str, detail: str = ""):
    """
    开始一个任务，记录时间戳
    用法: python task_timer.py start "吃论文" "搜索arxiv前沿论文"
    """
    entry = {
        "action": "start",
        "task": task_name,
        "detail": detail,
        "timestamp": _now(),
        "date": _today(),
    }
    _append(entry)
    print(f"[TASK START] {task_name} | {_now()}")


def end(task_name: str, result: str = ""):
    """
    结束一个任务，记录时间戳
    用法: python task_timer.py end "吃论文" "12篇论文已吸收"
    """
    entry = {
        "action": "end",
        "task": task_name,
        "result": result,
        "timestamp": _now(),
        "date": _today(),
    }
    _append(entry)
    print(f"[TASK END]   {task_name} | {_now()}")


def summary():
    """
    输出今天的任务摘要
    用法: python task_timer.py summary
    """
    today = _today()
    entries = _read_today(today)

    if not entries:
        print(f"[NO TASKS] no tasks for {today}")
        return

    # 配对 start/end
    tasks = {}
    for e in entries:
        name = e["task"]
        if name not in tasks:
            tasks[name] = {"start": None, "end": None, "result": "", "detail": ""}
        if e["action"] == "start":
            tasks[name]["start"] = e["timestamp"]
            tasks[name]["detail"] = e.get("detail", "")
        elif e["action"] == "end":
            tasks[name]["end"] = e["timestamp"]
            tasks[name]["result"] = e.get("result", "")

    # 输出
    sep = '=' * 60
    print(f"\n{sep}")
    print(f"  [SUMMARY] {today}")
    print(f"{sep}")

    total_tasks = len(tasks)
    completed = sum(1 for t in tasks.values() if t["start"] and t["end"])

    for name, info in tasks.items():
        start_t = info["start"] or "--"
        end_t = info["end"] or "--"
        duration = _calc_duration(info["start"], info["end"])
        status = "[OK]" if info["start"] and info["end"] else "[..]"
        print(f"  {status} {name}")
        print(f"     {start_t} -> {end_t}  ({duration})")
        if info["detail"]:
            print(f"     detail: {info['detail']}")
        if info["result"]:
            print(f"     result: {info['result']}")
        print()

    print(f"{sep}")
    print(f"  total: {total_tasks} | done: {completed} | pending: {total_tasks - completed}")
    print(f"{sep}\n")


def _append(entry):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_today(today):
    entries = []
    if not os.path.exists(LOG_FILE):
        return entries
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("date") == today:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def _calc_duration(start, end):
    if not start or not end:
        return "pending..."
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        delta = e - s
        total_min = int(delta.total_seconds() // 60)
        total_sec = int(delta.total_seconds())
        if total_min == 0:
            return f"{total_sec}s"
        elif total_min < 60:
            return f"{total_min}分钟"
        h = total_min // 60
        m = total_min % 60
        return f"{h}小时{m}分钟"
    except Exception:
        return "—"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage:")
        print('  python task_timer.py start "task-name" ["detail"]')
        print('  python task_timer.py end   "task-name" ["result"]')
        print('  python task_timer.py summary')
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start" and len(sys.argv) >= 3:
        start(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "end" and len(sys.argv) >= 3:
        end(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "summary":
        summary()
    else:
        print(f"unknown cmd: {cmd}")
        print("support: start, end, summary")
        sys.exit(1)
