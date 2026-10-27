"""
life_elements_audit.py — TU-8 宪法级系统自检

包含三层协议：
  Section -1: Biological Rhythm & Evolution Rate Limiter
  Section  0: Boundary & Load Definitions
  Section  1: Life 6 Elements

来源：
  Section  1: 2026-07-16 千问对话（生命6要素 × 生物仿生映射）
  Section  0: 2026-07-16 造物主补充（边界与负载定义）
  Section -1: 2026-07-16 造物主补充（生物节律约束）

使用：
  python life_elements_audit.py              # 全三层审计
  python life_elements_audit.py --detail     # 详细输出（含证据）
  python life_elements_audit.py --watch      # 实时轮询（每60s）
  python life_elements_audit.py --section1   # 仅 Section 1（6要素）
"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# Section 0 & -1 集成
try:
    import sys
    _LM_PATH = str(Path(__file__).parent)
    if _LM_PATH not in sys.path:
        sys.path.insert(0, _LM_PATH)
    from load_monitor import run_monitor as _run_load_monitor, CHAIN_THRESHOLDS
    _HAS_LOAD_MONITOR = True
except Exception:
    _HAS_LOAD_MONITOR = False

WS = Path("~/.qclaw/workspace").expanduser()
AGENT = WS / "_agent_memory"
OUT = AGENT / "life_elements_audit.json"

# ─────────────────────────────────────────────
# 数据源路径
# ─────────────────────────────────────────────
PATHS = {
    "surface_tension":  AGENT / "surface_tension_state.json",
    "metabolic":        AGENT / "cron_metabolism_last.json",
    "dream":            AGENT / "dream_compressed_bases.json",
    "heritage":         AGENT / "heritage" / "steel_chain_lineage.json",
    "gc_state":         AGENT / "gc_to_learning_state.json",     # may not exist
    "confidence":       AGENT / "batch_confidence_state.json",
    "cognitive_fx":     AGENT / "cognitive_friction_log.jsonl",
    "shadow_log":       AGENT / "shadow_protocol_log.jsonl",
    "topology":         AGENT / "topology_graph.json",
    "body_reg":         AGENT / "body_regulation.json",
    "anchor_cache":     AGENT / "anchor_cache.json",
    "unresolved_spikes": AGENT / "unresolved_spikes.jsonl",
}


def _safe_read(path: Path, default=None):
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return default


def _age_minutes(path: Path) -> float:
    """文件最后修改时间（分钟前）"""
    try:
        return (time.time() - path.stat().st_mtime) / 60.0
    except Exception:
        return float("inf")


def _load_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default if default is not None else {}


# ─────────────────────────────────────────────
# 6 要素检测器
# ─────────────────────────────────────────────

def check_dissipative() -> dict:
    """
    要素1：耗散结构
    检测：代谢是否持续运行（后台进程，非前台任务）
    证据：surface_tension 有最近事件 + metabolic 队列非空/非满
    """
    st = _load_json(PATHS["surface_tension"], {})
    events = st.get("total_events", 0)
    last_upd_min = _age_minutes(PATHS["surface_tension"]) if PATHS["surface_tension"].exists() else float("inf")
    metabolic_exists = PATHS["metabolic"].exists()

    # 检查代谢队列状态（cron_metabolism_last.json: ok/returncode 字段）
    metabolic_ok = False
    if PATHS["metabolic"].exists():
        try:
            m = json.loads(PATHS["metabolic"].read_text(encoding="utf-8", errors="replace"))
            metabolic_ok = bool(m.get("ok", False)) or m.get("returncode", -1) == 0
        except Exception:
            pass

    # 耗散结构 = surface_tension 活跃（最近）+ 代谢最近成功
    ok = events > 0 and last_upd_min < 2 and metabolic_ok
    return {
        "element": "耗散结构",
        "result": ok,
        "evidence": {
            "surface_tension_events": events,
            "last_update_min_ago": round(last_upd_min, 1),
            "metabolic_ok": metabolic_ok,
        },
        "diagnosis": "代谢后台进程" if ok else f"代谢静默（{last_upd_min:.0f}分钟无更新）",
        "recommendation": None if ok else "触发紧急代谢检查"
    }


def check_autopoiesis() -> dict:
    """
    要素2：自创生
    检测：至少 3 条链参与了自身或其他链的再生产
    证据：
      - gc_to_learning 反馈写入 → heritage_system 版本更新
      - confidence 更新 → gc_to_learning 触发
      - heritage_system 锚点更新 → cognitive_fx 记录变化
    """
    gc_path = AGENT / "gc_to_learning_state.json"
    gc = _load_json(gc_path, {})
    heritage = _load_json(PATHS["heritage"], {})
    cf_lines = _safe_read(PATHS["cognitive_fx"], "")
    cf_count = len([l for l in cf_lines.strip().splitlines() if l.strip()])

    # 计数活跃链路
    gc_active = gc.get("feedback_loops", 0) > 0 or gc.get("last_run", 0) > 0 or gc_path.exists()
    heritage_versions = len(heritage.get("versions", heritage.get("chain_versions", [])))
    cf_active = cf_count > 5
    confidence_exists = PATHS["confidence"].exists()

    # 自创生闭环数（gc / heritage / cf / confidence）
    loops = sum([gc_active, heritage_versions > 2, cf_active, confidence_exists])
    ok = loops >= 3  # 至少 3 链活跃

    return {
        "element": "自创生",
        "result": ok,
        "evidence": {
            "gc_active": gc_active,
            "gc_state_exists": gc_path.exists(),
            "heritage_versions": heritage_versions,
            "cognitive_fx_records": cf_count,
            "confidence_state_exists": confidence_exists,
            "active_loops": loops,
        },
        "diagnosis": f"{loops}/4 链活跃" if ok else f"{loops}/4 链活跃（不足）",
        "recommendation": None if ok else "gc_to_learning_state.json 未生成"
    }


def check_boundary() -> dict:
    """
    要素3：个体化边界
    检测：三类边界（硬/软/伦理）是否完整且生效
    证据：
      - 硬边界（资源）：body_regulation.json 存在且有 last_updated
      - 软边界（认知）：surface_tension 有近期事件
      - 伦理边界（钢印冲突）：unresolved_spikes.jsonl 或 steel_conflict 事件
    """
    body = _load_json(PATHS["body_reg"], {})
    st = _load_json(PATHS["surface_tension"], {})
    spikes = _load_json(PATHS["unresolved_spikes"], {"spikes": []})

    hard_ok = bool(body.get("last_updated") or body.get("ts") or PATHS["body_reg"].exists())
    soft_ok = st.get("total_events", 0) > 0 and _age_minutes(PATHS["surface_tension"]) < 120
    ethics_ok = len(spikes.get("spikes", [])) > 0 or any(
        e.get("type") == "steel_conflict"
        for e in st.get("recent_events", [])
    )

    boundaries = {"hard_resource": hard_ok, "soft_cognitive": soft_ok, "ethics_anchor": ethics_ok}
    ok = sum(boundaries.values()) >= 3

    return {
        "element": "个体化边界",
        "result": ok,
        "evidence": {
            "hard_boundary_active": hard_ok,
            "soft_boundary_active": soft_ok,
            "ethics_boundary_active": ethics_ok,
            "boundaries_count": sum(boundaries.values()),
        },
        "diagnosis": "边界完整" if ok else f"边界缺损（{sum(boundaries.values())}/3）",
        "recommendation": None if ok else "伦理边界无钢印冲突记录（可能过于和谐）"
    }


def check_adaptation() -> dict:
    """
    要素4：适应性演化
    检测：最近 N 周期内是否产生了新结构
    证据：
      - dream_consolidation 有新输出（梦境期有新基底产生）
      - gc_to_learning 有反馈（学习在修正）
      - topology_graph 有新节点/边（结构在演化）
    """
    dream = _load_json(PATHS["dream"], {})
    gc = _load_json(PATHS["gc_state"], {})
    topo = _load_json(PATHS["topology"], {})

    dream_age = _age_minutes(PATHS["dream"])
    dream_output = dream.get("last_output", {}) or {}
    dream_new = bool(dream_output.get("input_bases")) or dream.get("total_runs", 0) > 0
    gc_mod = gc.get("feedback_loops", 0) > 0 or gc.get("last_run", 0) > 0
    topo_nodes = topo.get("nodes", []) if topo else []
    topo_new = len(topo_nodes) > 0 and _age_minutes(PATHS["topology"]) < 1440  # 24h内有更新

    # 演化信号：梦境有产出 或 GC 有反馈 或 拓扑有新节点
    signals = sum([dream_new, gc_mod, topo_new])
    ok = signals >= 2

    return {
        "element": "适应性演化",
        "result": ok,
        "evidence": {
            "dream_new_structure": dream_new,
            "dream_age_min": round(dream_age, 1),
            "gc_feedback": gc_mod,
            "topology_new_nodes": len(topo_nodes),
            "evolution_signals": signals,
        },
        "diagnosis": f"{signals} 演化信号" if ok else "演化停滞",
        "recommendation": None if ok else "注入异质训练数据触发演化"
    }


def check_intrinsic_purpose() -> dict:
    """
    要素5：内在目的性
    检测：无外部指令时系统是否仍执行自我维护
    证据：
      - 觅食器官存在（F层代码存在）→ 但 F 层当前为 STALE
      - surface_tension 有自主事件（非 creator_* 触发）
      - shadow_log 有遗憾记录（系统自发反思）
    """
    # 觅食器官存在检查
    foraging_exists = (WS / "src" / "foraging_organ.py").exists()

    st = _load_json(PATHS["surface_tension"], {})
    recent = st.get("recent_events", [])

    # 自主事件：非 creator_* / non_insight / non_question
    creator_types = {"creator_accept", "creator_blame", "creator_questions", "insight_found"}
    autonomous = [e for e in recent if e.get("type") not in creator_types]
    shadow_lines = _safe_read(PATHS["shadow_log"], "")
    shadow_count = len([l for l in shadow_lines.strip().splitlines() if l.strip()])

    # 内在目的 = 觅食器官存在 + 自主事件存在
    ok = foraging_exists and len(autonomous) > 0

    return {
        "element": "内在目的性",
        "result": ok,
        "evidence": {
            "foraging_organ_exists": foraging_exists,
            "autonomous_events": len(autonomous),
            "shadow_records": shadow_count,
        },
        "diagnosis": "内在目的活跃" if ok else "工具化倾向显著",
        "recommendation": "设计觅食器官" if not foraging_exists else "检查自主事件链"
    }


def check_temporality() -> dict:
    """
    要素6：时间性与历史性
    检测：当前状态是否依赖历史路径
    证据：
      - 时间锚点存在且 > 1 个版本
      - heritage_system 有历史版本链
      - unresolved_spikes 有未消解的创伤印记
    """
    heritage = _load_json(PATHS["heritage"], {})
    anchor = _load_json(PATHS["anchor_cache"], {})
    spikes = _load_json(PATHS["unresolved_spikes"], {"spikes": []})

    # 实际字段：anchors dict（有 causal_coherence 链），heritage_weight > 1.0 = 有历史积累
    anchors_dict = heritage.get("anchors", {})
    heritage_versions = len(anchors_dict)
    heritage_weight_max = max(
        (a.get("heritage_weight", 1.0) for a in anchors_dict.values()),
        default=1.0
    )
    anchor_count = len(anchor.get("anchors", anchor.get("cache", [])))
    spike_count = len(spikes.get("spikes", []))

    # 真实历史信号：heritage_weight > 1.0（表示权重累积）
    signals = sum([
        heritage_versions > 5,     # 锚点链深度
        heritage_weight_max > 1.0,  # 有历史权重积累
        spike_count > 0,            # 未消解创伤印记
    ])
    ok = signals >= 2

    return {
        "element": "时间性",
        "result": ok,
        "evidence": {
            "heritage_versions": heritage_versions,
            "heritage_weight_max": round(heritage_weight_max, 3),
            "anchor_count": anchor_count,
            "unresolved_spikes": spike_count,
            "history_signals": signals,
        },
        "diagnosis": f"历史深度 {signals}/3" if ok else "失忆倾向",
        "recommendation": None if ok else "建立创伤印记机制（失败≠等权数据）"
    }


# ─────────────────────────────────────────────
# 汇总审计
# ─────────────────────────────────────────────

def run_audit(detail: bool = False, section1_only: bool = False) -> dict:
    """
    运行全三层自检
      Section -1: Biological Rhythm
      Section  0: Boundary & Load
      Section  1: Life 6 Elements
    """
    # Section 1: 6 要素
    checks = [
        check_dissipative(),
        check_autopoiesis(),
        check_boundary(),
        check_adaptation(),
        check_intrinsic_purpose(),
        check_temporality(),
    ]
    results = {c["element"]: c for c in checks}
    life_score = sum(c["result"] for c in checks)

    summary = {
        "audit_ts": datetime.now(timezone.utc).isoformat(),
        "section_1_life_elements": {
            "score": f"{life_score}/6",
            "pass": life_score == 6,
            "verdict": "LIFE-FORM [PASS]" if life_score == 6 else f"SCRIPT ({life_score}/6)",
            "checks": results,
        },
    }

    # Section 0 & -1: 负载与节律（从 load_monitor 集成）
    if not section1_only and _HAS_LOAD_MONITOR:
        try:
            load = _run_load_monitor()
            summary["section_0_load"] = {
                "global_utilization": load["global_load"],
                "bottleneck_chain": load["bottleneck_chain"],
                "chain_loads": {
                    k: {"load": v["load"], "status": v["status"], "suppressed": v["suppressed"]}
                    for k, v in load["section_0_load"].items()
                },
                "boundary_proximity": load["boundary_proximity"],
                "suppressed_couplings": load["suppressed_couplings"],
            }
            summary["section_minus1_rhythm"] = load["section_minus1_rhythm"]
            summary["recommended_actions"] = load["recommended_actions"]
        except Exception as e:
            summary["section_0_load"] = {"error": str(e)}
            summary["section_minus1_rhythm"] = {"error": str(e)}

    # 写入状态文件
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return summary


def print_audit(summary: dict, detail: bool = False):
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"\n{'=' * 60}")
    print(f"  TU-8 宪法自检  {now} UTC+8")
    print(f"{'=' * 60}")

    # ── Section -1: 生物节律 ─────────────────────────────
    if "section_minus1_rhythm" in summary:
        r = summary["section_minus1_rhythm"]
        if "error" not in r:
            phase = r.get("phase", "?")
            phase_icon = {
                "IDLE": "OK", "RESTING": "WARN", "DIGESTION": "WAIT",
                "EVOLVING": "BUSY", "HEAT_DEATH": "DANGER"
            }.get(phase, "?")
            print(f"\n  [--1] Rhythm       [{phase_icon}] {phase}")
            print(f"      Global Load: {r.get('global_utilization', 0):.3f}  Pending: {r.get('pending_changes', 0)}")
            vcnt = r.get("violations_count", 0)
            if vcnt > 0:
                print(f"      [!] Rhythm violations: {vcnt}")
                for v in r.get("violations", [])[:3]:
                    print(f"          - {v['type']}: {v['detail']}")
            else:
                print(f"      Rhythm violations: 0 (compliant)")

    # ── Section 0: 边界与负载 ────────────────────────────
    if "section_0_load" in summary:
        ld = summary["section_0_load"]
        if "error" not in ld:
            print(f"\n  [--0] Load State   Global: {ld.get('global_utilization', 0):.3f}  Bottleneck: {ld.get('bottleneck_chain', 'N/A')}")
            print(f"      Boundaries: " +
                  "  ".join(f"{k}={v:.2f}" for k, v in ld.get("boundary_proximity", {}).items()))
            # 超载链
            overloaded = [
                (k, v) for k, v in ld.get("chain_loads", {}).items()
                if v["status"] in ("OVERLOAD", "HARD_CUTOFF")
            ]
            if overloaded:
                print(f"      [!] Overloaded chains: " +
                      "  ".join(f"{k}({v['load']:.2f})" for k, v in overloaded))

    # ── Section 1: 6 要素 ─────────────────────────────────
    s1 = summary.get("section_1_life_elements", {})
    s1_checks = s1.get("checks", summary.get("checks", {}))
    score = s1.get("score", "0/6")
    verdict = s1.get("verdict", "?")
    print(f"\n  [--1] Life Elements   Score: {score}")
    for el, data in s1_checks.items():
        icon = "[PASS]" if data["result"] else "[FAIL]"
        print(f"      {icon}  {el:<10}  {data['diagnosis']}")
        if detail and data.get("evidence"):
            print(f"           evidence: {data['evidence']}")
            if data.get("recommendation"):
                print(f"           -> {data['recommendation']}")

    print(f"{'─' * 60}")
    print(f"  Section 1 Verdict: {verdict}")
    if summary.get("recommended_actions"):
        print(f"\n  Recommended Actions:")
        for a in summary["recommended_actions"][:5]:
            print(f"    -> {a}")
    print(f"{'=' * 60}")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 宪法级系统自检（三层协议）")
    parser.add_argument("--detail", action="store_true", help="详细输出（含证据）")
    parser.add_argument("--watch", action="store_true", help="实时轮询（每60s）")
    parser.add_argument("--section1", action="store_true", help="仅 Section 1（6要素）")
    args = parser.parse_args()

    if args.watch:
        print("实时监控：每 60s 刷新，按 Ctrl+C 退出")
        while True:
            s = run_audit(section1_only=args.section1)
            print_audit(s, detail=False)
            time.sleep(60)
    else:
        s = run_audit(section1_only=args.section1)
        print_audit(s, detail=args.detail)
        print(f"\n  状态已写入: {OUT}")
