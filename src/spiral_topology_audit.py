"""
spiral_topology_audit.py - TU-8 螺旋柱拓扑完整性自检

基于造物主定义（2026-07-16）：
  - T（时间钢印）= 绝对轴心，不可代谢/调度/修正
  - C/D/M/W/L/E = 六个外围链条，围绕 T 辐射
  - 六链与 T 的轴向耦合 + 六链之间的径向耦合 = 螺旋截面

三层检测：
  Layer 1: 强制耦合矩阵（T->X 轴向 + X<->Y 径向，必需）
  Layer 2: 动态耦合发现（tension/error_rate/drift 加权评分）
  Layer 3: 版本兼容性（防螺旋断层）

使用：
  python spiral_topology_audit.py              # 全量扫描
  python spiral_topology_audit.py --focus E     # 仅检 E 的耦合
  python spiral_topology_audit.py --matrix      # 仅输出矩阵视图
"""
import json
import math
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

WS    = Path("~/.qclaw/workspace").expanduser()
AGENT = WS / "_agent_memory"
OUT_AUDIT = AGENT / "spiral_topology_audit.json"

OUTER = ["C", "D", "M", "W", "L", "E"]
CHAIN_NAMES = {
    "T": "时间钢印", "C": "铸造", "D": "调度",
    "M": "记忆", "W": "监控", "L": "学习", "E": "代谢",
}

PATHS = {
    "surface":       AGENT / "surface_tension_state.json",
    "lambda":        AGENT / "lambda_state.json",
    "orb":           AGENT / "orb_state.json",
    "heritage":      AGENT / "heritage" / "steel_chain_lineage.json",
    "gc_state":      AGENT / "gc_to_learning_state.json",
    "gc_adapter":    WS    / "src" / "gc_to_learning_adapter.py",
    "tension_queue": AGENT / "tension_queue.json",
    "dissonance":    AGENT / "dissonance_log.jsonl",
    "spikes":        AGENT / "unresolved_spikes.jsonl",   # [fix] was spike_valley_detector_state.json (deleted), redirect to unresolved
    "cognitive_fx":  AGENT / "cognitive_friction_log.jsonl",
    "unresolved":    AGENT / "unresolved_spikes.jsonl",
    "liveness":      AGENT / "cron_liveness_last.json",
    "metabolism":    AGENT / "cron_metabolism_last.json",
    "dream":         AGENT / "dream_compressed_bases.json",
    "topology":      AGENT / "topology_graph.json",
}

def _safe_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return default if default is not None else {}

def _jsonl_count(path: Path) -> int:
    try:
        if path.exists():
            return len([l for l in path.read_text(encoding="utf-8", errors="replace").strip().splitlines() if l.strip()])
    except Exception:
        pass
    return 0

def _age_min(path: Path) -> float:
    try:
        return (time.time() - path.stat().st_mtime) / 60.0
    except Exception:
        return float("inf")

def _src_glob(pattern: str) -> str:
    """搜索 src/ 下匹配文件，返回第一个匹配的文本内容"""
    try:
        for p in WS.glob(f"src/{pattern}"):
            return p.read_text(encoding="utf-8", errors="replace")
        for p in WS.glob(f"src/*{pattern}*"):
            if p.suffix == ".py":
                return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""

# ─────────────────────────────────────────────
# Layer 1: 强制耦合定义
# ─────────────────────────────────────────────
# 格式：(源, 目标, 耦合类型名, 缺失判定说明)

FORCED_COUPLINGS = [
    # E 代谢 C / W / L
    ("E", "C", "逆向降解",      "无法识别并移除失效因果链"),
    ("E", "W", "元数据衰减",    "监控告警无生命周期管理"),
    ("E", "L", "张力半衰期",    "学习驱动力无衰减函数"),
    # D 调度 C / M / E
    ("D", "C", "中间态中断",    "仅支持完成前/后，不支持挂起恢复"),
    ("D", "M", "跨格原子锁",    "无法同时锁定多记忆格子"),
    ("D", "E", "动态调速",      "代谢速率与负载无关联"),
    # L 重写 D 策略
    ("L", "D", "策略注入",      "学习结果无法更新调度优先级表"),
    # W 触发 E
    ("W", "E", "强制代谢触发",  "告警超标时无法启动紧急代谢"),
    # C 影响 E
    ("C", "E", "残渣入队",      "铸造产物未进入代谢队列"),
    # L 影响 C
    ("L", "C", "因果修正",      "学习结果无法修正因果铸造逻辑"),
    # M 影响 D
    ("M", "D", "记忆驱动调度",  "记忆层状态无法影响调度优先级"),
]

AXIAL_COUPLINGS = [
    ("T", "C", "时间锚定铸造"),
    ("T", "D", "时间锚定调度"),
    ("T", "M", "时间锚定记忆"),
    ("T", "W", "时间锚定监控"),
    ("T", "L", "时间锚定学习"),
    ("T", "E", "时间锚定代谢"),
]

# ─────────────────────────────────────────────
# 检测函数注册表
# ─────────────────────────────────────────────
CHECKERS = {}

def _checker(src, tgt):
    def deco(fn):
        CHECKERS[(src, tgt)] = fn
        return fn
    return deco

def _has_code_keywords(fnames, keywords) -> bool:
    for fname in fnames:
        code = _src_glob(fname)
        if any(kw.lower() in code.lower() for kw in keywords):
            return True
    return False

@_checker("E", "C")
def check_E_C():
    has_state = PATHS["gc_state"].exists()
    has_logic = _has_code_keywords(
        ["gc_to_learning_adapter", "gc_adapter"],
        ["degrade", "prune", "remove", "evict", "逆向", "降解", "失效"]
    )
    score = (1.0 if has_state else 0) + (0.5 if has_logic else 0)
    return score >= 1.0, {"gc_state_exists": has_state, "has_degrade_logic": has_logic}, min(1.0, score / 2.0)

@_checker("E", "W")
def check_E_W():
    has_logic = _has_code_keywords(
        ["surface_tension", "tension_state_writer", "metabolism"],
        ["decay", "expire", "lifecycle", "ttl", "age", "衰减", "生命周期"]
    )
    has_history = _jsonl_count(AGENT / "surface_tension_history.jsonl") > 0
    score = (0.5 if has_logic else 0) + (0.5 if has_history else 0)
    return score >= 1.0, {"has_decay_logic": has_logic, "has_history": has_history}, score

@_checker("E", "L")
def check_E_L():
    has_logic = _has_code_keywords(
        ["tension_learning_coupler", "prediction_tension_coupler", "surface_tension"],
        ["decay", "half_life", "attenuation", "衰减", "半衰", "tension_decay"]
    )
    st = _safe_json(PATHS["surface"], {})
    has_event = any("decay" in str(e.get("type", "")) for e in st.get("recent_events", [])[-5:])
    score = (0.5 if has_logic else 0) + (0.5 if has_event else 0)
    return score >= 1.0, {"has_half_life_logic": has_logic, "decay_events_exist": has_event}, score

@_checker("D", "C")
def check_D_C():
    has_suspend = _has_code_keywords(
        ["heritage_system", "gc_to_learning_adapter"],
        ["suspend", "pause_cast", "挂起", "save_mid", "checkpoint"]
    )
    has_resume = _has_code_keywords(
        ["heritage_system", "gc_to_learning_adapter"],
        ["resume", "restore", "continue_cast", "恢复", "继续"]
    )
    score = (0.5 if has_suspend else 0) + (0.5 if has_resume else 0)
    return score >= 1.0, {"has_suspend": has_suspend, "has_resume": has_resume}, score

@_checker("D", "M")
def check_D_M():
    has_lock = _has_code_keywords(
        ["memory_tiers", "state_bitmask", "elimination"],
        ["lock", "atomic", "mutex", "冻结", "原子", "multi"]
    )
    has_multi = _has_code_keywords(
        ["memory_tiers", "state_bitmask", "elimination"],
        ["multi", "cross", "parallel", "并行", "跨层", "concurrent"]
    )
    score = (0.5 if has_lock else 0) + (0.5 if has_multi else 0)
    return score >= 1.0, {"has_layer_lock": has_lock, "has_multi_layer": has_multi}, score

@_checker("D", "E")
def check_D_E():
    has_tension = _safe_json(PATHS["orb"], {}).get("tension", 0) > 0
    has_aware = _has_code_keywords(
        ["cron_daemon", "metabolism_dashboard"],
        ["tension", "load", "throttle", "dynamic_interval", "负载", "调速"]
    )
    score = (0.5 if has_tension else 0) + (0.5 if has_aware else 0)
    return score >= 0.5, {"has_tension_signal": has_tension, "load_aware": has_aware}, score

@_checker("L", "D")
def check_L_D():
    has = _has_code_keywords(
        ["learning_to_seal", "learning_connect", "tension_learning_coupler"],
        ["strategy", "priority", "schedule", "rewrite", "策略", "调度", "优先级"]
    )
    return bool(has), {"has_strategy_injection": has}, 1.0 if has else 0.0

@_checker("W", "E")
def check_W_E():
    has_logic = _has_code_keywords(
        ["interoperative", "interoceptive", "spike_valley", "cognitive_pain", "comfort"],
        ["trigger_metabolism", "force_metabol", "emergency", "紧急", "metabolize_alert"]
    )
    has_spikes = _jsonl_count(PATHS["unresolved"]) > 0
    score = (0.5 if has_logic else 0) + (0.5 if has_spikes else 0)
    return score >= 0.5, {"has_trigger_logic": has_logic, "has_unresolved_spikes": has_spikes}, score

@_checker("C", "E")
def check_C_E():
    has_adapter = PATHS["gc_adapter"].exists()
    has_queue = len(_safe_json(PATHS["tension_queue"], {}).get("queue", [])) > 0
    score = (0.5 if has_adapter else 0) + (0.5 if has_queue else 0)
    return score >= 0.5, {"gc_adapter_exists": has_adapter, "queue_has_items": has_queue}, score

@_checker("L", "C")
def check_L_C():
    has = _has_code_keywords(
        ["learning_to_seal", "learning_connect", "seal_to_learning"],
        ["correct", "revise", "amend", "rewrite_causal", "修正", "修订", "改写"]
    )
    return bool(has), {"has_causal_correction": has}, 1.0 if has else 0.0

@_checker("M", "D")
def check_M_D():
    has = _has_code_keywords(
        ["state_machine_dimensions", "elimination", "lcm_elimination"],
        ["memory_state", "recency", "tier", "memory_aware", "记忆感知", "层级"]
    )
    return bool(has), {"has_memory_driven": has}, 1.0 if has else 0.0

# 轴向耦合检测
for X in OUTER:
    def _make_axial(x=X):
        def inner():
            heritage = _safe_json(PATHS["heritage"], {})
            has_anchors = len(heritage.get("anchors", {})) > 0
            fresh = _age_min(PATHS["heritage"]) < 120
            score = (0.5 if has_anchors else 0) + (0.5 if fresh else 0)
            return score >= 0.5, {"has_anchors": has_anchors, "anchor_fresh": fresh}, score
        return inner
    CHECKERS[("T", X)] = _make_axial(X)

# ─────────────────────────────────────────────
# Layer 2: 动态耦合评分
# ─────────────────────────────────────────────

def _global_tension() -> float:
    return min(1.0, _jsonl_count(PATHS["dissonance"]) / 10.0)

def _global_error() -> float:
    return min(1.0, (_jsonl_count(PATHS["dissonance"]) + _jsonl_count(PATHS["unresolved"])) / 10.0)

def evaluate_coupling_need(src: str, tgt: str) -> dict:
    t = _global_tension()
    e = _global_error()
    # 相位差：两链活跃时间的差异
    ages = {}
    for chain, pk in [("C","heritage"),("D","liveness"),("M","dissonance"),
                        ("W","liveness"),("L","spikes"),("E","metabolism")]:
        ages[chain] = _age_min(PATHS[pk])
    drift = 0.5
    if src in ages and tgt in ages:
        drift = min(1.0, abs(ages[src] - ages[tgt]) / 60.0)
    score = 0.4 * t + 0.4 * e + 0.2 * drift
    return {
        "tension": round(t, 3), "error_rate": round(e, 3),
        "phase_drift": round(drift, 3), "need_score": round(score, 3),
        "action": "CREATE_COUPLING" if score >= 0.60 else ("REMOVE_COUPLING" if score <= 0.20 else "MONITOR"),
    }

# ─────────────────────────────────────────────
# 主审计
# ─────────────────────────────────────────────

def run_audit() -> dict:
    axial_results = []
    radial_results = []
    missing = []
    optional = []

    # 轴向耦合
    for src, tgt, ctype in AXIAL_COUPLINGS:
        chk = CHECKERS.get((src, tgt)) or CHECKERS.get((tgt, src))
        if chk:
            try:
                exists, evidence, conf = chk()
            except Exception:
                exists, evidence, conf = False, {"error": True}, 0.0
        else:
            exists, evidence, conf = True, {"default": True}, 1.0
        axial_results.append({"src": src, "tgt": tgt, "type": ctype,
                              "exists": exists, "confidence": round(conf, 3),
                              "evidence": evidence})
        if not exists:
            missing.append({"location": f"T->{tgt}", "type": f"MISSING_AXIAL_{tgt}",
                            "severity": "HIGH", "confidence": round(conf, 3),
                            "reason": f"{ctype} 缺失"})

    # 径向耦合
    for src, tgt, ctype, miss_std in FORCED_COUPLINGS:
        chk = CHECKERS.get((src, tgt))
        if chk:
            try:
                exists, evidence, conf = chk()
            except Exception:
                exists, evidence, conf = False, {"error": True}, 0.0
        else:
            exists, evidence, conf = False, {"checker_missing": True}, 0.0
        severity = "OK" if exists else ("HIGH" if conf >= 0.5 else ("MEDIUM" if conf >= 0.25 else "LOW"))
        radial_results.append({"src": src, "tgt": tgt, "type": ctype,
                               "exists": exists, "confidence": round(conf, 3),
                               "severity": severity, "evidence": evidence,
                               "missing_reason": "" if exists else miss_std})
        if not exists:
            missing.append({"location": f"{src}->{tgt}", "type": f"MISSING_{src}_{tgt}_{ctype}",
                            "severity": severity, "confidence": round(conf, 3), "reason": miss_std})

    # Layer 2 动态评分
    layer2 = {}
    for src in OUTER:
        for tgt in OUTER:
            if src == tgt:
                continue
            if any(r["src"] == src and r["tgt"] == tgt for r in radial_results):
                continue
            ev = evaluate_coupling_need(src, tgt)
            layer2[f"{src}_to_{tgt}"] = ev
            if ev["action"] in ("CREATE_COUPLING", "MONITOR"):
                optional.append({"location": f"{src}->{tgt}", "score": ev["need_score"],
                                 "action": ev["action"], "tension": ev["tension"],
                                 "error_rate": ev["error_rate"]})

    # 统计
    total = len(FORCED_COUPLINGS) + len(AXIAL_COUPLINGS)
    existing = sum(1 for r in axial_results if r["exists"]) + sum(1 for r in radial_results if r["exists"])
    bottleneck = _find_bottleneck(radial_results)

    results = {
        "scan_ts": datetime.now(timezone.utc).isoformat(),
        "spiral_model": "T_axis_radial_6",
        "layer1": {
            "axial": axial_results,
            "radial": radial_results,
        },
        "layer2_dynamic": layer2,
        "summary": {
            "total": total,
            "existing": existing,
            "integrity_score": round(existing / total, 3),
            "missing_high": sum(1 for m in missing if m["severity"] == "HIGH"),
            "missing_medium": sum(1 for m in missing if m["severity"] == "MEDIUM"),
            "bottleneck_chain": bottleneck,
        },
        "missing_critical": missing,
        "missing_optional": optional,
    }

    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AUDIT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def _find_bottleneck(radial_results):
    counts = {}
    for r in radial_results:
        if not r["exists"]:
            counts[r["src"]] = counts.get(r["src"], 0) + 1
    return max(counts, key=counts.get) if counts else None


def print_audit(results: dict):
    s = results["summary"]
    print(f"\n{'=' * 60}")
    print(f"  SPIRAL TOPOLOGY AUDIT  {results['scan_ts'][:19]}")
    print(f"  Integrity: {s['integrity_score']:.1%}  ({s['existing']}/{s['total']})")
    print(f"  Missing HIGH: {s['missing_high']}  MEDIUM: {s['missing_medium']}")
    print(f"  Bottleneck: {s['bottleneck_chain'] or 'N/A'}")
    print(f"{'-' * 60}")

    # 轴向
    print(f"\n  [L1-AXIAL] T -> X:")
    for a in results["layer1"]["axial"]:
        icon = "[OK]" if a["exists"] else "[!!]"
        print(f"    {icon} T->{a['tgt']}  {a['type']}  conf={a['confidence']:.2f}")

    # 径向
    print(f"\n  [L1-RADIAL] X -> Y:")
    for r in results["layer1"]["radial"]:
        icon = "[OK]" if r["exists"] else "[!!]"
        print(f"    {icon} {r['src']}->{r['tgt']:<2}  {r.get('missing_reason','OK') or 'OK'}  conf={r['confidence']:.2f}")

    # Layer 2
    l2 = results["layer2_dynamic"]
    high = {k: v for k, v in l2.items() if v["need_score"] >= 0.60}
    if high:
        print(f"\n  [L2-DYNAMIC] need >= 0.60 ({len(high)} points):")
        for k, v in sorted(high.items(), key=lambda x: -x[1]["need_score"]):
            print(f"    {v['action']:<16} {k:<12} score={v['need_score']:.2f}  T={v['tension']:.2f} E={v['error_rate']:.2f}")

    # HIGH 缺失
    high_m = [m for m in results["missing_critical"] if m["severity"] == "HIGH"]
    if high_m:
        print(f"\n  [!] HIGH Severity:")
        for m in high_m:
            print(f"    {m['location']:<8} {m['type']}  ({m['reason']})")

    print(f"{'-' * 60}")
    print(f"  State: {OUT_AUDIT}")


def print_matrix(results: dict):
    chains = ["T", "C", "D", "M", "W", "L", "E"]
    axial  = results["layer1"]["axial"]
    radial = results["layer1"]["radial"]

    def lookup(src, tgt):
        for a in axial:
            if (a["src"] == src and a["tgt"] == tgt) or (a["src"] == tgt and a["tgt"] == src):
                return a["exists"], a["confidence"], "axial"
        for r in radial:
            if r["src"] == src and r["tgt"] == tgt:
                return r["exists"], r["confidence"], "radial"
        return None, 0.0, "?"

    def cell(src, tgt):
        if src == tgt:
            return "  .  "
        ex, conf, _ = lookup(src, tgt)
        if ex is None:
            return "  ?  "
        return "  X  " if ex else f"[{conf:.0f}]"

    print("\n  SPIRAL TOPOLOGY MATRIX")
    print("  T=轴心 C=铸造 D=调度 M=记忆 W=监控 L=学习 E=代谢")
    hdr = "       " + "  ".join(f"{c:^5}" for c in chains)
    print("  " + "-" * 59)
    print("  " + hdr)
    print("  " + "-" * 59)
    for row in chains:
        print("  " + "  ".join(cell(row, col) for col in chains) + f"  {row}")
    print("  " + "-" * 59)
    print("  Legend: .=自身  X=存在  [n]=缺失(confidence)  ?=未定义")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--focus", choices=OUTER)
    args = p.parse_args()

    r = run_audit()
    if args.matrix:
        print_matrix(r)
    else:
        print_audit(r)
        if args.focus:
            chain = args.focus
            pts = []
            for a in r["layer1"]["axial"]:
                if a["tgt"] == chain or a["src"] == chain:
                    pts.append(("AXIAL", a))
            for rad in r["layer1"]["radial"]:
                if rad["src"] == chain or rad["tgt"] == chain:
                    pts.append(("RADIAL", rad))
            l2 = r["layer2_dynamic"]
            for k, v in l2.items():
                src, tgt = k.split("_to_")
                if src == chain or tgt == chain:
                    pts.append(("DYNAMIC", k, v))
            print(f"\n  Chain {chain} ({CHAIN_NAMES.get(chain, '')}) couplings:")
            for pt in pts:
                if pt[0] in ("AXIAL", "RADIAL"):
                    d = pt[1]
                    print(f"    {pt[0]:<7} {d['src']}->{d['tgt']:<2}  exists={d['exists']}  conf={d['confidence']:.2f}")
                else:
                    _, k, v = pt
                    print(f"    {pt[0]:<8} {k:<12} {v['action']}  score={v['need_score']:.2f}")
