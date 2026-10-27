#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prune_guard_cron.py — 节点剪枝联动 + 剪枝热保护 的 cron 驱动

由 cron_daemon.py 周期性调用（建议 interval=300s），执行：
  1. ForgetPruneLinkage.link_once()  遗忘-剪枝联动（能量=0+无连接→自动删；崩溃级张力→强制剪枝）
  2. PruneThermalGuard.guard_once()  剪枝热保护（NORMAL/L1/L2/L3 分级响应）

结果写入 _agent_memory/cron_prune_guard_last.json。
退出码：0 = 正常执行（无论是否触发剪枝）；1 = 异常。

层级: P1（节点剪枝优化）
创建: 2026-07-21
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
SRC = WS / "src"
AGENT = WS / "_agent_memory"
# 详细报告写独立文件；cron_prune_guard_last.json 留给 cron_daemon 的 run_script 包装（含 stdout/returncode）
DETAIL = AGENT / "prune_guard_detail.json"
OUTPUT = DETAIL

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main():
    from forget_prune_linkage import ForgetPruneLinkage
    from prune_thermal_guard import PruneThermalGuard

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": True,
        "forget_prune": None,
        "prune_thermal": None,
        "errors": [],
    }

    # ── 1. 遗忘-剪枝联动 ────────────────────────────────────────────────
    try:
        link = ForgetPruneLinkage()
        lr = link.link_once()
        report["forget_prune"] = {
            "checked_snapshots": lr.checked_snapshots,
            "auto_pruned": lr.auto_pruned,
            "crash_triggered": lr.crash_triggered,
            "crash_pruned": lr.crash_pruned,
            "skipped": lr.skipped,
            "tension_value": round(lr.tension_value, 4),
        }
    except Exception as e:
        report["ok"] = False
        report["errors"].append(f"forget_prune_linkage: {e!r}")

    # ── 2. 剪枝热保护 ──────────────────────────────────────────────────
    try:
        guard = PruneThermalGuard()
        gr = guard.guard_once()
        report["prune_thermal"] = {
            "level": gr.level,
            "tension_integral": round(gr.tension_integral, 4),
            "action_taken": gr.action_taken,
            "admission_paused": gr.admission_paused,
            "unloaded": gr.unloaded,
            "truncated": gr.truncated,
        }
    except Exception as e:
        report["ok"] = False
        report["errors"].append(f"prune_thermal_guard: {e!r}")

    # ── 写出结果 ────────────────────────────────────────────────────────
    AGENT.mkdir(parents=True, exist_ok=True)
    with open(DETAIL, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 控制台摘要（供 cron_daemon 捕获）
    fp = report["forget_prune"]
    pt = report["prune_thermal"]
    if fp and pt:
        print(
            f"[prune_guard] forget: auto_pruned={len(fp['auto_pruned'])} "
            f"crash={fp['crash_triggered']}({len(fp['crash_pruned'])}); "
            f"thermal: {pt['level']} action={pt['action_taken']} "
            f"unloaded={len(pt['unloaded'])} truncated={len(pt['truncated'])}"
        )
    if not report["ok"]:
        print(f"[prune_guard] ERRORS: {report['errors']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 绝不因异常导致 daemon 卡死
        err = {"ts": datetime.now(timezone.utc).isoformat(), "ok": False, "fatal": repr(e)}
        try:
            AGENT.mkdir(parents=True, exist_ok=True)
            with open(DETAIL, "w", encoding="utf-8") as f:
                json.dump(err, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        print(f"[prune_guard] FATAL: {e!r}")
        sys.exit(1)
