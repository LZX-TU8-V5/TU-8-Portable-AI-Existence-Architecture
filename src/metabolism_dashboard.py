"""
src/metabolism_dashboard.py — TU-8 代谢仪表盘 + 统一入口
=========================================================
核心职责：
  1. 统一视图：展示所有代谢子系统状态
  2. 顶层驱动：提供 run_metabolism_cycle() 统一触发所有代谢点
  3. 代谢调度：将 metabolic_pipeline 接入 dream_check 管线

代谢子系统地图：
  ┌─────────────────────────────────────────────┐
  │            TU-8 代谢系统                    │
  │                                              │
  │  ┌──────────────┐   ┌────────────────────┐  │
  │  │ 认知代谢      │   │ 记忆代谢            │  │
  │  │ (confidence_ │   │ (metabolic_       │  │
  │  │  decay_engine│   │  pipeline + gc)   │  │
  │  └──────┬───────┘   └────────┬─────────┘  │
  │         │                     │             │
  │         ▼                     ▼             │
  │  ┌──────────────────┐  ┌──────────────┐    │
  │  │ gc_to_learning   │  │  user_metabol │    │
  │  │ _adapter (v2)    │  │  _to_gc_adapter│   │
  │  └────────┬─────────┘  └───────┬──────┘    │
  │           │                    │            │
  │           └────────┬───────────┘            │
  │                    ▼                        │
  │           ┌────────────────┐               │
  │           │learning_to_gc  │               │
  │           │_adapter         │               │
  │           └────────┬───────┘               │
  │                    ▼                        │
  │           ┌────────────────┐               │
  │           │ seal_to_gc     │               │
  │           │ _adapter       │               │
  │           └────────────────┘               │
  └─────────────────────────────────────────────┘

调用入口：
  python src/metabolism_dashboard.py              # 仪表盘视图
  python src/metabolism_dashboard.py --run         # 完整代谢循环
  python src/metabolism_dashboard.py --run pipeline # 仅代谢管道
  python src/metabolism_dashboard.py --run decay   # 仅置信度衰减
  python src/metabolism_dashboard.py --health      # 健康报告
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
SRC = WORKSPACE / "src"
AGENT = WORKSPACE / "_agent_memory"

# ============================================================================
# 子系统状态读取器
# ============================================================================

def _read_json(path: Path, fallback=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _read_log_lines(path: Path, max_lines: int = 50) -> list[dict]:
    try:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result = []
        for line in lines[-max_lines:]:
            line = line.strip()
            if line:
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return result
    except Exception:
        return []


# ── 认知代谢（版本树剪枝）────────────────────────────────────────────────

def get_confidence_decay_status() -> dict:
    """置信度衰减引擎状态"""
    decay_log = WORKSPACE / "memory" / "reconstruction" / "confidence_decay_log.json"
    log_lines = _read_log_lines(decay_log, 50)
    last_runs = [l for l in log_lines if l.get("event") == "decay_completed"][-5:]
    total_pruned = sum(1 for l in log_lines if l.get("event") == "pruned")
    return {
        "name": "认知代谢（版本树剪枝）",
        "subsystem": "confidence_decay_engine",
        "log_file": str(decay_log),
        "total_pruned": total_pruned,
        "last_runs": last_runs,
        "status": "active" if log_lines else "unknown",
    }


# ── 记忆代谢（管道）───────────────────────────────────────────────────────

def get_memory_metabolism_status() -> dict:
    """记忆代谢管道状态"""
    state = _read_json(WORKSPACE / "memory" / "metabolic_pipeline_log.jsonl", None)
    log_lines = _read_log_lines(WORKSPACE / "memory" / "metabolic_pipeline_log.jsonl", 5)
    last_run = None
    if log_lines:
        last_run = log_lines[-1].get("timestamp", None)

    # 检查各类记忆文件
    archive_dir = WORKSPACE / "memory" / "archive"
    archive_count = len(list(archive_dir.glob("*.md"))) if archive_dir.exists() else 0

    memory_md_size = (WORKSPACE / "MEMORY.md").stat().st_size if (WORKSPACE / "MEMORY.md").exists() else 0

    diary_files = sorted(WORKSPACE.glob("memory/2026-07-*.md"))
    diary_count = len([f for f in diary_files if "archive" not in str(f) and f.name != "MEMORY.md"])

    return {
        "name": "记忆代谢（管道）",
        "subsystem": "metabolic_pipeline",
        "last_run": last_run,
        "archive_count": archive_count,
        "diary_pending": diary_count,
        "memory_md_size_kb": round(memory_md_size / 1024, 1),
        "last_log": log_lines[-1] if log_lines else None,
        "status": "active",
    }


# ── USER.md 代谢 ────────────────────────────────────────────────────────

def get_user_metabolism_status() -> dict:
    """USER.md 代谢状态"""
    state = _read_json(WORKSPACE / "memory" / "user_metabolism_state.json", {})
    return {
        "name": "USER.md 代谢",
        "subsystem": "user_metabolism",
        "state_file": str(WORKSPACE / "memory" / "user_metabolism_state.json"),
        "last_metabolized": state.get("last_run", None),
        "entries_processed": state.get("entries_processed", 0),
        "entries_pruned": state.get("entries_pruned", 0),
        "status": "active" if state else "unknown",
    }


# ── TODO 代谢 ───────────────────────────────────────────────────────────

def get_todo_metabolism_status() -> dict:
    """TODO_MASTER.md 代谢状态"""
    state = _read_json(WORKSPACE / "_agent_memory" / "todo_metabolism_state.json", {})
    return {
        "name": "TODO 代谢",
        "subsystem": "todo_metabolism",
        "state_file": str(WORKSPACE / "_agent_memory" / "todo_metabolism_state.json"),
        "last_scan": state.get("last_scan", None),
        "stale_count": state.get("stale_count", 0),
        "duplicate_count": state.get("duplicate_count", 0),
        "status": "active" if state else "unknown",
    }


# ── 记忆分层 ────────────────────────────────────────────────────────────

def get_memory_tiers_status() -> dict:
    """记忆分层状态"""
    state = _read_json(WORKSPACE / "memory" / "memory_tiers_state.json", {})
    return {
        "name": "记忆分层",
        "subsystem": "memory_tiers",
        "state_file": str(WORKSPACE / "memory" / "memory_tiers_state.json"),
        "l1_count": state.get("l1_count", 0),
        "l2_count": state.get("l2_count", 0),
        "l3_count": state.get("l3_count", 0),
        "pending_promotion": state.get("pending_promotion", 0),
        "last_scan": state.get("last_scan", None),
        "status": "active" if state else "unknown",
    }


# ── 遗产系统 ────────────────────────────────────────────────────────────

def get_heritage_status() -> dict:
    """遗产继承系统状态"""
    lineage_file = WORKSPACE / "heritage_system" / "steel_chain_lineage.json"
    frames = _read_json(lineage_file, {})
    return {
        "name": "遗产继承",
        "subsystem": "heritage_system",
        "lineage_file": str(lineage_file),
        "inherited_frames": len(frames.get("frames", [])),
        "chain_integrity": frames.get("chain_integrity", "unknown"),
        "status": "active" if frames else "unknown",
    }


# ── 张力蒸馏（T0）───────────────────────────────────────────────────────

def get_tension_distiller_status() -> dict:
    """T0 矛盾蒸馏器状态"""
    state = _read_json(AGENT / "tension_distiller_state.json", {})
    return {
        "name": "T0 矛盾蒸馏",
        "subsystem": "tension_distiller",
        "state_file": str(AGENT / "tension_distiller_state.json"),
        "nodes_queued": state.get("queue_depth", 0),
        "last_distill": state.get("last_run", None),
        "top_tension": state.get("top_tension", 0.0),
        "status": "active" if state else "unknown",
    }


# ── 失谐系统（T2+T3）──────────────────────────────────────────────────

def get_dissonance_status() -> dict:
    """T2/T3 失谐系统状态"""
    hang_state = _read_json(WORKSPACE / "_agent_memory" / "dissonance_hang_points.json", {})
    resp_state = _read_json(WORKSPACE / "_agent_memory" / "respiration_state.json", {})

    hang_points = hang_state.get("hang_points", [])
    unresolved = [h for h in hang_points if h.get("resolved_at") is None]
    critical = [h for h in unresolved if h.get("dissonance_level") == "critical"]

    cycles = resp_state.get("cycles", [])
    active = [c for c in cycles if c.get("completed_at") is None]

    return {
        "name": "T2/T3 失谐呼吸",
        "subsystem": "dissonance_amplifier + tension_respirator",
        "hang_points_total": len(hang_points),
        "hang_unresolved": len(unresolved),
        "hang_critical": len(critical),
        "respiration_active_cycles": len(active),
        "respiration_by_stage": {},
        "status": "active",
    }


# ── Cron 健康状态 ───────────────────────────────────────────────────────

def get_cron_health() -> dict:
    """所有代谢相关 cron 的健康状态"""
    cron_jobs = [
        ("dream_check_every4h", "TU8_dream_check_every4h", "dream_check 每4h"),
        ("dream_check_daily3am", "TU8_dream_check_daily3am", "dream_check 3am"),
        ("dream_check_weekly5am", "TU8_dream_check_weekly5am", "dream_check 周5am"),
        ("memory_metabolism_sunday", "TU-8 记忆代谢（每周日10:00）", "记忆代谢 周日"),
        ("todo_metabolism", "TU8待办代谢", "TODO代谢 8am"),
        ("memory_tiers", "TU8记忆分层", "记忆分层 9am"),
        ("survival_monitor", "TU8监测存活", "存活监测 6h"),
        ("interoception", "TU8内感受(体感环)", "内感受 6h"),
    ]
    return {
        "note": "详细 cron 状态见 cron list 命令",
        "jobs": cron_jobs,
    }


# ============================================================================
# 统一仪表盘
# ============================================================================

def get_metabolism_dashboard() -> dict:
    """获取完整代谢仪表盘"""
    subsystems = [
        get_confidence_decay_status(),
        get_memory_metabolism_status(),
        get_user_metabolism_status(),
        get_todo_metabolism_status(),
        get_memory_tiers_status(),
        get_heritage_status(),
        get_tension_distiller_status(),
        get_dissonance_status(),
    ]

    # 健康度评分（基于各子系统状态）
    active_count = sum(1 for s in subsystems if s.get("status") == "active")
    health_score = round(active_count / len(subsystems) * 100, 1)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health_score": health_score,
        "subsystems_total": len(subsystems),
        "subsystems_active": active_count,
        "subsystems": subsystems,
    }


def print_dashboard(d: dict):
    """打印仪表盘"""
    print(f"\n{'='*60}")
    print(f"  TU-8 代谢仪表盘  {d['timestamp']}")
    print(f"{'='*60}")
    print(f"  健康度: {d['health_score']}%  ({d['subsystems_active']}/{d['subsystems_total']} 子系统活跃)")
    print()

    for s in d["subsystems"]:
        status_icon = "✅" if s.get("status") == "active" else "⚠️"
        print(f"  {status_icon} [{s['subsystem']}] {s['name']}")

        # 子系统特有信息
        sub = s["subsystem"]
        if sub == "confidence_decay_engine":
            print(f"      版本树节点: {s.get('active_nodes','?')} | 累计剪枝: {s.get('pruned_total',0)}")
        elif sub == "metabolic_pipeline":
            print(f"      待归档日记: {s.get('diary_pending',0)} | 归档库: {s.get('archive_count',0)} | MEMORY.md: {s.get('memory_md_size_kb','?')}KB")
        elif sub == "user_metabolism":
            print(f"      处理条目: {s.get('entries_processed',0)} | 剪枝: {s.get('entries_pruned',0)}")
        elif sub == "todo_metabolism":
            print(f"      STALE项: {s.get('stale_count',0)} | 重复项: {s.get('duplicate_count',0)}")
        elif sub == "memory_tiers":
            l1 = s.get("l1_count", 0)
            l2 = s.get("l2_count", 0)
            l3 = s.get("l3_count", 0)
            print(f"      L1:{l1} L2:{l2} L3:{l3} | 待晋升: {s.get('pending_promotion',0)}")
        elif sub == "heritage_system":
            print(f"      继承帧: {s.get('inherited_frames',0)}")
        elif sub == "tension_distiller":
            print(f"      队列节点: {s.get('nodes_queued',0)} | 最高张力: {s.get('top_tension',0):.3f}")
        elif sub in ("dissonance_amplifier + tension_respirator",):
            print(f"      悬挂缺口: {s.get('hang_unresolved',0)} (critical: {s.get('hang_critical',0)}) | 呼吸周期: {s.get('respiration_active_cycles',0)}")

        print()

    print(f"  {'='*60}\n")


# ============================================================================
# 统一代谢循环驱动
# ============================================================================

def run_confidence_decay() -> dict:
    """运行置信度衰减引擎"""
    try:
        sys.path.insert(0, str(SRC))
        from confidence_decay_engine import decay_all
        result = decay_all()
        return {"ok": True, "action": "confidence_decay", "result": result}
    except Exception as e:
        return {"ok": False, "action": "confidence_decay", "error": str(e)}


def run_metabolic_pipeline(stage: str = "all", dry_run: bool = True) -> dict:
    """运行记忆代谢管道"""
    try:
        sys.path.insert(0, str(SRC))
        from metabolic_pipeline import MetabolicPipeline
        pipe = MetabolicPipeline()
        if stage == "all":
            result = pipe.run(dry_run=dry_run)
        elif stage == "distill":
            result = {"stages": {"distill": pipe.distill(dry_run=dry_run)}}
        elif stage == "gc":
            result = {"stages": {"gc": pipe.gc(dry_run=dry_run)}}
        elif stage == "archive":
            result = {"stages": {"archive": pipe.archive(dry_run=dry_run)}}
        else:
            result = {"error": f"unknown stage: {stage}"}
        return {"ok": True, "action": f"metabolic_pipeline({stage})", "result": result}
    except Exception as e:
        return {"ok": False, "action": f"metabolic_pipeline({stage})", "error": str(e)}


def run_gc_to_learning() -> dict:
    """运行 GC→学习反馈"""
    try:
        sys.path.insert(0, str(SRC))
        from gc_to_learning_adapter import (
            get_forgetting_patterns,
            record_gc_result,
            summarize_gc_learning_feedback,
        )
        patterns = get_forgetting_patterns()
        record_gc_result(patterns)
        summary = summarize_gc_learning_feedback()
        result = {"patterns": patterns, "summary": summary}
        return {"ok": True, "action": "gc_to_learning", "result": result}
    except Exception as e:
        return {"ok": False, "action": "gc_to_learning", "error": str(e)}


def run_full_metabolism_cycle(dry_run: bool = True) -> dict:
    """
    完整代谢循环（顶层驱动）

    执行顺序（符合消化逻辑）：
      1. 置信度衰减（认知消化）→ 识别可剪枝节点
      2. GC→学习反馈（认知排泄）→ 清理后推送学习系统
      3. 代谢管道（记忆消化）→ 日记提炼→去重→GC→归档
      4. 张力蒸馏（梦境期）→ 矛盾节点提取

    目标：每天 dream_check 时自动调用，作为代谢的总驱动入口
    """
    results = {}

    # 1. 认知代谢
    results["confidence_decay"] = run_confidence_decay()

    # 2. GC→学习
    results["gc_to_learning"] = run_gc_to_learning()

    # 3. 记忆代谢（蒸馏+GC+归档）
    results["metabolic_pipeline"] = run_metabolic_pipeline(stage="all", dry_run=dry_run)

    # 4. 状态汇总
    ok_count = sum(1 for v in results.values() if v.get("ok", False))
    health_score = round(ok_count / len(results) * 100, 1)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "health_score": health_score,
        "ok_count": ok_count,
        "total_count": len(results),
        "results": results,
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 代谢仪表盘 + 统一驱动")
    parser.add_argument("--run", choices=["all", "pipeline", "decay", "gc_learn"], default=None,
                        help="运行代谢循环")
    parser.add_argument("--dry", action="store_true", default=False,
                        help="dry_run 模式（默认关闭，正式运行）")
    parser.add_argument("--health", action="store_true", help="仅显示健康报告")
    args = parser.parse_args()

    if args.run:
        if args.run == "all":
            print("=== 完整代谢循环 ===")
            result = run_full_metabolism_cycle(dry_run=args.dry)
            print(f"健康度: {result['health_score']}%")
            for key, val in result["results"].items():
                icon = "✅" if val.get("ok") else "❌"
                err = f" | ERROR: {val.get('error')}" if not val.get("ok") else ""
                print(f"  {icon} {key}{err}")
        elif args.run == "pipeline":
            result = run_metabolic_pipeline(stage="all", dry_run=args.dry)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.run == "decay":
            result = run_confidence_decay()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.run == "gc_learn":
            result = run_gc_to_learning()
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        d = get_metabolism_dashboard()
        print_dashboard(d)
