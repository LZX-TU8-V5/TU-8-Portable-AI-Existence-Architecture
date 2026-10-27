#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dream_txn.py — TU-8 梦境期事务日志（Dream WAL / 预写日志）

防"身首异处"的 L1 治本层。

根因：梦境期（记忆晋升 + GC + 代谢 + 直觉 + 学习）是一次跨多文件的长事务。
微秒断电 / 硬杀会在事务中途杀死进程，留下跨文件语义不一致（GC 半做完），
进而让内感受皮层误判"身体已死"（Zombie）。file_lock 只防单文件半截写，
防不了这种跨文件事务不一致。

机制：
  begin(phases, targets)  → 写 dream_txn.journal {status:in_progress, ...}
  mark_phase(name)        → 追加已完成阶段（可选，丰富恢复报告）
  commit()                → status:committed 并删除日志（事务干净完成）
  recover()               → boot 调用：若发现 in_progress（硬杀/失败中断）
                            → 隔离（删除日志，下次梦境从头重建）+ 返回中断信息，
                              供启动一致性门（L2）触发 unknown 重基线

回滚策略：GC/晋升具幂等性，故不强行快照回滚，而是"隔离 + 下次重跑"（quarantine）。
"""
import os
import sys
import json
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import file_lock as flock

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
JOURNAL = os.path.join(MEM, "dream_txn.journal")
TZ = timezone(timedelta(hours=8))


def _now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def begin(phases, targets, epoch=None):
    j = {
        "status": "in_progress",
        "started_at": _now(),
        "epoch": epoch or _now(),
        "phases": list(phases),
        "targets": list(targets),
        "done": [],
        "note": "梦境期事务日志（Dream WAL）：status=in_progress 表示事务未完成（疑似硬杀/失败中断）",
    }
    with flock.FileLock(JOURNAL):
        flock.atomic_write_json(JOURNAL, j)
    return j


def mark_phase(name):
    j = flock.safe_read_json(JOURNAL)
    if not j or j.get("status") != "in_progress":
        return None
    if name not in j["done"]:
        j["done"].append(name)
    with flock.FileLock(JOURNAL):
        flock.atomic_write_json(JOURNAL, j)
    return j


def commit():
    j = flock.safe_read_json(JOURNAL)
    if not j:
        return None
    j["status"] = "committed"
    j["committed_at"] = _now()
    with flock.FileLock(JOURNAL):
        flock.atomic_write_json(JOURNAL, j)
    try:
        if os.path.exists(JOURNAL):
            os.remove(JOURNAL)
    except Exception:
        pass
    return True


def recover():
    """boot 调用。返回中断信息 dict 或 None（无中断）。隔离=删除未完成日志。"""
    j = flock.safe_read_json(JOURNAL)
    if not j or j.get("status") != "in_progress":
        return None
    info = {
        "interrupted": True,
        "started_at": j.get("started_at"),
        "done": j.get("done"),
        "phases": j.get("phases"),
        "targets": j.get("targets"),
    }
    try:
        if os.path.exists(JOURNAL):
            os.remove(JOURNAL)
    except Exception:
        pass
    return info


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["begin", "mark", "commit", "recover"])
    ap.add_argument("--phase", default=None)
    ap.add_argument("--phases", default="")
    ap.add_argument("--targets", default="")
    args = ap.parse_args()
    if args.action == "begin":
        begin(args.phases.split(",") if args.phases else [],
              args.targets.split(",") if args.targets else [])
    elif args.action == "mark":
        mark_phase(args.phase)
    elif args.action == "commit":
        commit()
    elif args.action == "recover":
        print(json.dumps(recover(), ensure_ascii=False))
