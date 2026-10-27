#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
todo_metabolism.py — TU-8 待办代谢扫描

把 TODO 接入代谢闭环：扫描 TODO_MASTER.md，识别应被淘汰/核实的项：
  - STALE：带 [创建 YYYY-MM-DD] 且距今 > STALE_DAYS(60) 天仍未完成的项
  - 重复：归一化后文本相同的多个未完成项
  - 待核实区：旧文件待核实项数量（建议造物主逐一确认）

输出：
  - 有 STALE/重复 → 输出简短报告（cron 转告警）
  - 无 → 输出空（cron 静默，不骚扰）

用法：
  python src/todo_metabolism.py            # 扫描并输出
  python src/todo_metabolism.py --json     # JSON 输出（含诊断）
"""
import os
import re
import json
import sys
import argparse
from datetime import datetime, timezone, timedelta
import file_lock as flock

# 强制 stdout UTF-8（Windows 控制台兼容）
if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

HOME = os.path.expanduser("~")
TODO = os.path.join(HOME, ".qclaw", "workspace", "TODO_MASTER.md")
STALE_DAYS = 60
TZ = timezone(timedelta(hours=8))

DATE_RE = re.compile(r"\[(?:创建\s+)?(\d{4}-\d{2}-\d{2})\]")
UNFIN_RE = re.compile(r"^\s*-\s*\[\s*\]\s*\*\*(.+?)\*\*\s*(.*)$")
UNFIN_RE2 = re.compile(r"^\s*-\s*\[\s*\]\s*(.+?)\s*$")
SECTION_RE = re.compile(r"^#{2,3}\s+(.*)$")


def norm(text):
    t = text.lower()
    t = re.sub(r"[\*\-\(\）\)\[\]【】、，。：:/\s]", "", t)
    return t


def parse(path=TODO):
    if not os.path.exists(path):
        return [], 0, []
    lines = flock.safe_read_text(path).splitlines()
    items = []          # (text, date_str|None, section)
    section = ""
    review_count = 0
    in_review = False
    for ln in lines:
        m = SECTION_RE.match(ln)
        if m:
            section = m.group(1).strip()
            in_review = "待核实" in section
            continue
        um = UNFIN_RE.match(ln) or UNFIN_RE2.match(ln)
        if um:
            text = (um.group(1) or "").strip()
            rest = (um.group(2) if um.lastindex and um.lastindex >= 2 else "")
            dm = DATE_RE.search(ln)
            date_str = dm.group(1) if dm else None
            items.append((text, date_str, section))
        elif in_review and re.match(r"^\s*-\s+\S", ln) and "[ ]" not in ln:
            review_count += 1
    return items, review_count, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--path", default=TODO, help="TODO 文件路径（默认 TODO_MASTER.md）")
    args = ap.parse_args()

    items, review_count, _ = parse(args.path)
    now = datetime.now(TZ)
    stale, undated = [], []
    for text, date_str, section in items:
        if date_str:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
                age = (now - d).days
                if age > STALE_DAYS:
                    stale.append((text, date_str, age, section))
            except Exception:
                undated.append(text)
        else:
            undated.append(text)

    # 重复检测（归一化后相同）
    seen = {}
    dups = []
    for text, date_str, section in items:
        n = norm(text)
        if len(n) < 4:
            continue
        if n in seen:
            if seen[n] is not None:
                dups.append(seen[n]); seen[n] = None
            dups.append((text, date_str, section))
        else:
            seen[n] = (text, date_str, section)

    report_lines = []
    if stale:
        report_lines.append(f"⚠️ {len(stale)} 项待办超期(> {STALE_DAYS}天)未推进，建议核实后划掉或重排：")
        for text, ds, age, sec in stale[:12]:
            report_lines.append(f"  - [{age}天/{ds}] {text}（{sec}）")
    if dups:
        report_lines.append(f"🔁 发现 {len(dups)} 个疑似重复项，建议合并：")
        for text, ds, sec in dups[:12]:
            report_lines.append(f"  - {text}（{sec}）")

    if args.json:
        out = {"stale": stale, "dups": dups,
               "undated_count": len(undated), "review_count": review_count,
               "total_unfinished": len(items)}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if not report_lines:
        # 健康：静默（cron 不骚扰）
        return
    print("\n".join(report_lines))


if __name__ == "__main__":
    main()
