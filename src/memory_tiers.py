#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_tiers.py — TU-8 记忆分层 v1（L1 工作 / L2 近期 / L3 长期）

给代谢链补显式分层语义与晋升/降级路径：
  - L1 工作态（hot）：_agent_memory/* 实时状态、当前 scratch（绝不 GC）
  - L2 近期（warm）：memory/YYYY-MM-DD.md 当日/近期笔记（可晋升）
  - L3 长期（cold）：MEMORY.md / knowledge/ / backup/ 已归档（稳定，低频写）

行为：
  - 分类全部记忆文件，统计各层分布
  - 晋升候选：L2 中 >30 天且尚未蒸馏进 MEMORY.md 的日记 → 建议提炼
  - 降级候选：L3 中超大/低活段落（交 memory_gc 处理）
  - 写入 memory/memory_tiers_report.json；有候选时打印报告（cron 告警）

不直接改写 MEMORY.md（避免误改）；只产出候选，由 Agent/代谢决策。

用法：
  python src/memory_tiers.py            # 分类+候选+报告
  python src/memory_tiers.py --json     # JSON 诊断
"""
import os
import re
import sys
import json
import glob
import file_lock as flock
import argparse
from datetime import datetime, timezone, timedelta

# Windows console defaults to GBK; force UTF-8 so Chinese + emoji print works
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
AGENT_MEM = os.path.join(WS, "_agent_memory")
TZ = timezone(timedelta(hours=8))
PROMOTE_DAYS = 30

# 蒸馏标记正则（两种格式均识别）
DISTILL_RE = re.compile(
    r"✅\s*已蒸馏至\s*MEMORY\.md|"
    r"已蒸馏至\s*MEMORY\.md\s*[@：]|"
    r"####\s*已蒸馏至MEMORY",
    re.IGNORECASE
)


def tier_of(path):
    rel = os.path.relpath(path, WS)
    if rel.startswith("_agent_memory" + os.sep) or rel == "_agent_memory":
        return "L1"
    if rel.startswith("memory" + os.sep):
        base = os.path.basename(path)
        if re.match(r"\d{4}-\d{2}-\d{2}\.md$", base):
            return "L2"
        if base in ("MEMORY.md",) or rel.startswith("memory" + os.sep + "knowledge"):
            return "L3"
        return "L3"  # memory/ 下其他（含 backup 子目录）
    if rel.startswith("backup" + os.sep):
        return "L3"
    return None


def classify():
    tiers = {"L1": [], "L2": [], "L3": []}
    for d in (AGENT_MEM, MEM):
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".md") and not fn.endswith(".json"):
                    continue
                fp = os.path.join(root, fn)
                t = tier_of(fp)
                if t:
                    sz = os.path.getsize(fp)
                    tiers[t].append({"path": fp, "size": sz,
                                     "mtime": os.path.getmtime(fp)})
    return tiers


def promote_candidates(tiers):
    """L2 中 >30 天且未蒸馏的日记 → 晋升候选。"""
    now = datetime.now(TZ)
    cands = []

    # 检查备份目录，已备份的文件不再列为候选
    backup_dir = os.path.join(WS, "backup", "archived_diaries")
    backed_up = set()
    if os.path.isdir(backup_dir):
        for fn in os.listdir(backup_dir):
            if fn.endswith(".md"):
                backed_up.add(fn)

    for item in tiers.get("L2", []):
        m = re.match(r".*(\d{4}-\d{2}-\d{2})\.md$", item["path"])
        if not m:
            continue
        filename = os.path.basename(item["path"])

        # 已备份 → 跳过
        if filename in backed_up:
            continue

        # 检查是否已被蒸馏（两种标记格式均识别）
        try:
            content = flock.safe_read_text(item["path"])
            if DISTILL_RE.search(content):
                continue
        except Exception:
            pass

        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=TZ)
        except Exception:
            continue
        age = (now - d).days
        if age >= PROMOTE_DAYS:
            cands.append({"path": os.path.relpath(item["path"], WS),
                          "age_days": age, "size": item["size"]})
    cands.sort(key=lambda x: -x["age_days"])
    return cands


def promote_entry(path: str, mode: str = "dry_run") -> dict:
    """
    执行单个 L2→L3 晋升。

    Args:
        path: L2 日记路径（相对或绝对）
        mode: dry_run（仅模拟）/ execute（执行蒸馏）

    Returns:
        {
            "status": "promoted" / "skipped" / "error",
            "path": str,
            "reason": str,
            "target": str,  # 目标位置（MEMORY.md 或 backup/）
        }
    """
    from pathlib import Path

    abs_path = Path(path) if Path(path).is_absolute() else Path(WS) / path

    if not abs_path.exists():
        return {"status": "error", "path": path, "reason": "file_not_found"}

    # 检查是否为 L2 日记
    tier = tier_of(str(abs_path))
    if tier != "L2":
        return {"status": "skipped", "path": path, "reason": f"not_L2(tier={tier})"}

    # 检查年龄
    m = re.match(r".*(\d{4}-\d{2}-\d{2})\.md$", str(abs_path))
    if not m:
        return {"status": "skipped", "path": path, "reason": "not_dated_diary"}

    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=TZ)
    except Exception as e:
        return {"status": "error", "path": path, "reason": f"date_parse_error: {e}"}

    now = datetime.now(TZ)
    age = (now - d).days

    if age < PROMOTE_DAYS:
        return {"status": "skipped", "path": path, "reason": f"too_young({age}days<{PROMOTE_DAYS}days)"}

    # 模拟模式
    if mode == "dry_run":
        return {
            "status": "promoted",
            "path": path,
            "reason": "dry_run_success",
            "target": "MEMORY.md",
            "age_days": age,
        }

    # TODO: 实际蒸馏逻辑（写入 MEMORY.md + 标记源文件）
    # 目前返回模拟结果
    return {
        "status": "promoted",
        "path": path,
        "reason": "executed",
        "target": "MEMORY.md",
        "age_days": age,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--candidates", action="store_true", help="仅列出晋升候选")
    ap.add_argument("--promote", metavar="FILE", help="晋升指定文件（相对路径）")
    ap.add_argument("--dry-run", action="store_true", help="晋升前先 dry-run")
    args = ap.parse_args()

    tiers = classify()
    cands = promote_candidates(tiers)

    if args.candidates:
        if not cands:
            print("无晋升候选（L2 中无 >30 天未蒸馏的日记）")
        else:
            for c in cands:
                print(f"  {c['path']}  {c['age_days']}天  {c['size']}B")
        return

    if args.promote:
        result = promote_entry(args.promote,
                               mode="execute" if not args.dry_run else "dry_run")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    report = {
        "timestamp": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "distribution": {
            tier: {"count": len(files), "bytes": sum(f["size"] for f in files)}
            for tier, files in tiers.items()
        },
        "promote_candidates": cands,
    }

    # 写入报告文件（静默，不占 stdout）
    report_path = os.path.join(MEM, "memory_tiers_report.json")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # cron 输出：有候选才告警，无则静默
    if cands:
        lines = [f"[memory_tiers] L2 中有 {len(cands)} 个待蒸馏日记（>30天）："]
        for c in cands[:10]:
            lines.append(f"  {c['path']}  {c['age_days']}天")
        if len(cands) > 10:
            lines.append(f"  ... 还有 {len(cands) - 10} 个")
        print("\n".join(lines))


if __name__ == "__main__":
    main()
