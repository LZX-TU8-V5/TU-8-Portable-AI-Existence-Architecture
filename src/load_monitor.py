"""
load_monitor.py — TU-8 边界与负载定义模块

来源：2026-07-16 造物主补充协议
定位：Section 0，在所有功能协议之前执行

7 链负载度量 + 3 类边界约束 + 负载感知拓扑修正

使用：
  python load_monitor.py              # 快速负载快照
  python load_monitor.py --detail     # 含边界接近度和行动建议
  python load_monitor.py --chain T    # 单链负载（按 T/C/D/M/E/W/L）
"""
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone

WS = Path("~/.qclaw/workspace").expanduser()
AGENT = WS / "_agent_memory"
OUT = AGENT / "load_state.json"

# ─────────────────────────────────────────────
# 状态文件路径
# ─────────────────────────────────────────────
PATHS = {
    "lambda":        AGENT / "lambda_state.json",
    "orb":           AGENT / "orb_state.json",
    "surface":       AGENT / "surface_tension_state.json",
    "heritage":      AGENT / "heritage" / "steel_chain_lineage.json",
    "dissonance":    AGENT / "dissonance_log.jsonl",
    "liveness":      AGENT / "cron_liveness_last.json",
    "intero":        AGENT / "cron_interoceptive_last.json",
    "dream":         AGENT / "dream_compressed_bases.json",
    "metabolism":    AGENT / "cron_metabolism_last.json",
    "curiosity":     AGENT / "cron_curiosity_last.json",
    "batch_conf":    AGENT / "batch_confidence_state.json",
    "unresolved":    AGENT / "unresolved_spikes.jsonl",
    "cognitive_fx":  AGENT / "cognitive_friction_log.jsonl",
    "tension_queue": AGENT / "tension_queue.json",
    "respiration":   AGENT / "respiration_state.json",
}

# ─────────────────────────────────────────────
# Section 0: 7 链负载阈值定义
# ─────────────────────────────────────────────
# 格式：(指标键, 告警阈值, 硬截止阈值, 单位说明)
CHAIN_THRESHOLDS = {
    # T 时间钢印链：锚点写入频率（分钟）+ 校验延迟
    "T": {
        "metric": "anchor_write_rate",
        "warn_at": 0.70,
        "hard_at": 0.90,
        "measure": lambda d: _calc_t_load(d),
        "unit": "anchor_age_ratio / max_age",
    },
    # C 铸造链：钢印铸造队列长度 + 张力累积
    "C": {
        "metric": "steel_cast_queue",
        "warn_at": 0.60,
        "hard_at": 0.85,
        "measure": lambda d: _calc_c_load(d),
        "unit": "tension_sum / max_tension",
    },
    # D 调度链：上下文使用率 + 切换频率
    "D": {
        "metric": "context_utilization",
        "warn_at": 0.70,
        "hard_at": 0.90,
        "measure": lambda d: _calc_d_load(d),
        "unit": "context_load_pct / 100",
    },
    # M 记忆链：记忆文件大小 + IO 延迟
    "M": {
        "metric": "memory_io_pressure",
        "warn_at": 0.65,
        "hard_at": 0.85,
        "measure": lambda d: _calc_m_load(d),
        "unit": "tension_queue_size / max_queue",
    },
    # E 代谢链：待处理残渣体积 + 循环周期耗时
    "E": {
        "metric": "metabolic_backlog",
        "warn_at": 0.60,
        "hard_at": 0.80,
        "measure": lambda d: _calc_e_load(d),
        "unit": "anxiety + body_critical_penalty",
    },
    # W 监控链：告警生成速率 + 扫描覆盖率
    "W": {
        "metric": "monitor_staleness",
        "warn_at": 0.50,
        "hard_at": 0.75,
        "measure": lambda d: _calc_w_load(d),
        "unit": "liveness_age_min / max_age",
    },
    # L 学习链：张力累积 + 梯度范数
    "L": {
        "metric": "learning_tension_accum",
        "warn_at": 0.55,
        "hard_at": 0.80,
        "measure": lambda d: _calc_l_load(d),
        "unit": "spike_valley_vector_magnitude",
    },
}


# ─────────────────────────────────────────────
# Section 0: 边界约束三层
# ─────────────────────────────────────────────
class BoundaryType:
    HARD   = "HARD"    # 物理定律，不可协商，触及即拒绝
    SOFT   = "SOFT"    # 可动态调整，但调整本身消耗代谢
    ETHICAL = "ETHICAL" # 宪法级只读，触及即受控停机


@dataclass
class Boundary:
    name: str
    btype: str
    threshold: float
    current_value: float
    proximity: float  # 0.0 - 1.0
    status: str       # SAFE / WARN / CRITICAL / VIOLATED


@dataclass
class ChainLoad:
    chain: str
    load: float           # 0.0 - 1.0
    warn_at: float
    hard_at: float
    status: str           # NORMAL / WARN / OVERLOAD / HARD_CUTOFF
    metric: str
    unit: str
    suppressed: bool = False   # 负载抑制（≠结构缺失）
    recommendation: str = ""


@dataclass
class RhythmStatus:
    phase: str             # IDLE / DIGESTION / EVOLVING / RESTING
    cycles_remaining: int  # 消化期剩余周期
    pending_in_incubation: int
    last_change_stability: float
    rhythm_violations_100: int
    violation_reasons: list = field(default_factory=list)


# ─────────────────────────────────────────────
# 各链负载计算函数
# ─────────────────────────────────────────────

def _age_minutes(path: Path) -> float:
    try:
        return (time.time() - path.stat().st_mtime) / 60.0
    except Exception:
        return float("inf")


def _safe_read_json(path: Path, default=None):
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


def _calc_t_load(data: dict) -> float:
    """
    T 时间钢印链负载
    = max(anchor_age_ratio, last_update_staleness)
    anchor_age_ratio = 1 - (last_anchor_write_age / 120min)
    """
    st = _safe_read_json(PATHS["surface"], {})
    heritage = _safe_read_json(PATHS["heritage"], {})
    last_upd = _age_minutes(PATHS["surface"])
    heritage_upd = heritage.get("last_updated", "")
    heritage_age = 999.0
    if heritage_upd:
        try:
            dt = datetime.fromisoformat(heritage_upd.replace("Z", "+00:00"))
            heritage_age = (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
        except Exception:
            heritage_age = 999.0

    # 锚点写入新鲜度（120分钟为满分，0分钟为1.0）
    anchor_fresh = max(0.0, 1.0 - heritage_age / 120.0)
    # surface_tension 更新新鲜度（10分钟满分）
    surface_fresh = max(0.0, 1.0 - last_upd / 10.0)
    # 总分：两个新鲜度加权
    freshness = anchor_fresh * 0.6 + surface_fresh * 0.4
    return 1.0 - freshness  # 负载 = 1 - 新鲜度


def _calc_c_load(data: dict) -> float:
    """
    C 铸造链负载 = 钢印张力累积
    anxiety + fear + unresolved_spike_ratio
    """
    ls = _safe_read_json(PATHS["lambda"], {})
    anxiety = abs(ls.get("anxiety", 0.0))
    fear = abs(ls.get("fear", 0.0))
    orb = _safe_read_json(PATHS["orb"], {})
    tension = orb.get("tension", 0.0)
    unresolved = _jsonl_count(PATHS["unresolved"])
    unresolved_penalty = min(1.0, unresolved / 5.0)
    return min(1.0, (anxiety + fear + tension) / 3.0 + unresolved_penalty * 0.2)


def _calc_d_load(data: dict) -> float:
    """
    D 调度链负载 = 上下文使用率
    """
    ls = _safe_read_json(PATHS["lambda"], {})
    ctx = ls.get("context_load_pct", 0) / 100.0
    # 加上 dissonance 频率作为额外压力指标
    dissonance = _jsonl_count(PATHS["dissonance"])
    dissonance_penalty = min(0.3, dissonance / 20.0)
    return min(1.0, ctx + dissonance_penalty)


def _calc_m_load(data: dict) -> float:
    """
    M 记忆链负载 = 记忆队列压力
    tension_queue size / 容量
    """
    tq = _safe_read_json(PATHS["tension_queue"], {})
    queue_size = len(tq.get("queue", tq.get("items", [])))
    cognitive_fx = _jsonl_count(PATHS["cognitive_fx"])
    # 10条队列 + 20条摩擦记录 = 满分
    return min(1.0, queue_size / 10.0 + cognitive_fx / 20.0)


def _calc_e_load(data: dict) -> dict:
    """
    E 代谢链负载 = anxiety + 身体姿态惩罚
    返回 (负载, 详细)
    """
    ls = _safe_read_json(PATHS["lambda"], {})
    anxiety = abs(ls.get("anxiety", 0.0))
    posture = ls.get("body_posture", "normal")
    posture_penalty = {"normal": 0.0, "warning": 0.2, "critical": 0.5}.get(posture, 0.0)
    return min(1.0, anxiety + posture_penalty)


def _calc_w_load(data: dict) -> float:
    """
    W 监控链负载 = liveness 监控陈旧度
    age > 360min = 硬截止
    """
    age = _age_minutes(PATHS["liveness"])
    staleness = min(1.0, age / 360.0)  # 360分钟 = 硬截止
    return staleness


def _calc_l_load(data: dict) -> float:
    """
    L 学习链负载 = 尖刺/凹陷累积张力
    spike_valley_vector 的 L2 范数
    """
    spikes = _safe_read_json(PATHS["spikes"], {})
    vector = spikes.get("spike_valley_vector", [0.0] * 7)
    # L2 范数
    import math
    magnitude = math.sqrt(sum(v**2 for v in vector))
    # 归一化（假设 max 合理值 3.0）
    return min(1.0, magnitude / 3.0)


# ─────────────────────────────────────────────
# Section 0: 边界约束计算
# ─────────────────────────────────────────────

BOUNDARIES = {
    # 伦理边界（ETHICAL）：只读，不可绕过
    # 锚点精度 = heritage 中低 coherence 锚点占比（越低越危险）
    "ETHICAL_ANCHOR_PRECISION": {
        "btype": BoundaryType.ETHICAL,
        "threshold": 0.10,  # 低 coherence 锚点占比超过 10% → 危险
        "compute": lambda: _calc_ethical_anchor_precision(),
    },
    # 软边界（SOFT）：可动态调整，但调整本身消耗代谢
    "SOFT_CONTEXT_WINDOW": {
        "btype": BoundaryType.SOFT,
        "threshold": 0.90,
        "compute": lambda: _safe_read_json(PATHS["lambda"], {}).get("context_load_pct", 50) / 100.0,
    },
    "SOFT_METABOLIC_CYCLE": {
        "btype": BoundaryType.SOFT,
        "threshold": 0.80,
        "compute": lambda: min(1.0, _age_minutes(PATHS["metabolism"]) / 60.0),
    },
    # 硬边界（HARD）：物理定律，触及即拒绝
    "HARD_CONTEXT_HARD_CAP": {
        "btype": BoundaryType.HARD,
        "threshold": 0.98,
        "compute": lambda: _safe_read_json(PATHS["lambda"], {}).get("context_load_pct", 0) / 100.0,
    },
    "HARD_LIVENESS_TIMEOUT": {
        "btype": BoundaryType.HARD,
        "threshold": 0.95,  # >360min 即熔断
        "compute": lambda: min(1.0, _age_minutes(PATHS["liveness"]) / 360.0),
    },
}


def _proximity(threshold: float, current: float) -> float:
    """计算接近度（0=安全, 1=触顶）"""
    if threshold <= 0:
        return 1.0 if current > 0 else 0.0
    return min(1.0, current / threshold)


def _boundary_status(proximity: float, btype: str) -> str:
    if proximity >= 1.0:
        return "VIOLATED" if btype == BoundaryType.ETHICAL else "OVERLOAD"
    if proximity >= 0.85:
        return "CRITICAL"
    if proximity >= 0.60:
        return "WARN"
    return "SAFE"


# ─────────────────────────────────────────────
# Section -1: 生物节律状态
# ─────────────────────────────────────────────

@dataclass
class RhythmState:
    phase: str
    cycles_remaining: int
    pending_changes: int
    last_change_stability: float
    violations_100: int
    global_utilization: float


RHYTHM_PHASES = {
    "IDLE":        (0.0, 0.4, "正常低负载，可接受结构性变更"),
    "RESTING":     (0.4, 0.6, "系统偏重，结构性变更需排队等待"),
    "DIGESTION":   (0.6, 0.8, "消化期，禁止结构性变更，仅只读"),
    "EVOLVING":    (0.8, 1.0, "高负载窗口，仅执行已批准的微步骤"),
    "HEAT_DEATH":  (1.0, float("inf"), "过载，强制静默，暂停一切变更"),
}

RHYTHM_VIOLATION_LOG = AGENT / "rhythm_violations.jsonl"


def _get_rhythm_phase(global_load: float) -> tuple:
    for phase, (lo, hi, _) in RHYTHM_PHASES.items():
        if lo <= global_load < hi:
            return phase, (lo, hi)
    return "HEAT_DEATH", (1.0, float("inf"))


def _load_rhythm_history() -> list:
    try:
        if RHYTHM_VIOLATION_LOG.exists():
            lines = RHYTHM_VIOLATION_LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            return [json.loads(l) for l in lines[-100:] if l.strip()]
    except Exception:
        pass
    return []


def _check_rhythm_violations(rhythm_state: RhythmState, pending_changes: int) -> list:
    """
    检测节律违规
    违规类型：
      - DIGESTION phase 时发起结构性变更
      - 变更速率超限（超过 1/5min 窗口）
      - 消化期未到期强行推进
    """
    violations = []
    history = _load_rhythm_history()
    recent_window = [h for h in history if h.get("ts") and
                     (time.time() - h.get("ts", 0)) < 300]  # 5分钟窗口
    changes_in_window = sum(1 for h in recent_window if h.get("type") == "structural_change")

    if rhythm_state.phase == "DIGESTION" and pending_changes > 0:
        violations.append({
            "type": "DIGESTION_VIOLATION",
            "detail": f"Digestion phase: {rhythm_state.cycles_remaining} cycles remaining, {pending_changes} pending changes blocked",
            "severity": "HIGH",
        })

    if changes_in_window >= 2:
        violations.append({
            "type": "CHANGE_RATE_EXCEEDED",
            "detail": f"{changes_in_window} changes in last 5min (limit: 1)",
            "severity": "MEDIUM",
        })

    if rhythm_state.cycles_remaining > 0 and pending_changes > 0:
        violations.append({
            "type": "PREMATURE_EVOLUTION",
            "detail": f"{rhythm_state.cycles_remaining} cycles remaining before next evolution",
            "severity": "LOW",
        })

    return violations


# ─────────────────────────────────────────────
# 主监控逻辑
# ─────────────────────────────────────────────

def run_monitor(detail: bool = False) -> dict:
    """
    运行 Section 0 + Section -1 全监控
    返回结构化结果字典
    """
    results = {
        "scan_ts": datetime.now(timezone.utc).isoformat(),
        "section_0_load": {},
        "section_minus1_rhythm": {},
        "boundaries": {},
        "global_load": 0.0,
        "bottleneck_chain": None,
        "phase": "IDLE",
        "rhythm_violations": [],
        "suppressed_couplings": [],  # 负载抑制（≠结构缺失）
        "recommended_actions": [],
    }

    # ── Section 0: 各链负载 ──────────────────
    chain_loads = []
    max_load = 0.0
    bottleneck = None

    for chain_id, cfg in CHAIN_THRESHOLDS.items():
        load = cfg["measure"](results)
        warn = cfg["warn_at"]
        hard = cfg["hard_at"]

        if load >= hard:
            status = "HARD_CUTOFF"
        elif load >= warn:
            status = "OVERLOAD"
        elif load >= warn * 0.8:
            status = "WARN"
        else:
            status = "NORMAL"

        suppressed = load >= warn * 0.8  # ≥80% warn → 负载抑制
        rec = ""
        if suppressed:
            rec = _action_for_chain(chain_id, load, warn, hard)

        cl = ChainLoad(
            chain=chain_id,
            load=round(load, 4),
            warn_at=warn,
            hard_at=hard,
            status=status,
            metric=cfg["metric"],
            unit=cfg["unit"],
            suppressed=suppressed,
            recommendation=rec,
        )
        chain_loads.append(cl)
        results["section_0_load"][chain_id] = {
            "load": cl.load, "status": cl.status,
            "suppressed": cl.suppressed, "recommendation": cl.recommendation,
        }

        if cl.load > max_load:
            max_load = cl.load
            bottleneck = chain_id

    # ── Section 0: 边界约束 ──────────────────
    boundary_list = []
    all_proximity = {"HARD": 0.0, "SOFT": 0.0, "ETHICAL": 0.0}

    for bname, bcfg in BOUNDARIES.items():
        try:
            current = bcfg["compute"]()
        except Exception:
            current = 0.0
        proximity = _proximity(bcfg["threshold"], current)
        btype = bcfg["btype"]
        status = _boundary_status(proximity, btype)
        all_proximity[btype] = max(all_proximity[btype], proximity)
        boundary_list.append(Boundary(
            name=bname, btype=btype,
            threshold=bcfg["threshold"],
            current_value=round(current, 4),
            proximity=round(proximity, 4),
            status=status,
        ))

    results["boundaries"] = {
        b.name: {"proximity": b.proximity, "status": b.status, "type": b.btype}
        for b in boundary_list
    }
    results["boundary_proximity"] = {k: round(v, 4) for k, v in all_proximity.items()}

    # ── Section -1: 生物节律 ─────────────────
    global_load = max_load
    phase, (lo, hi) = _get_rhythm_phase(global_load)

    # 从 dissonance 或 tension_queue 推断 pending changes
    pending_changes = min(5, _jsonl_count(PATHS["dissonance"]) + len(
        _safe_read_json(PATHS["tension_queue"], {}).get("queue", [])
    ))

    rhythm = RhythmState(
        phase=phase,
        cycles_remaining=0,  # 简化：无消化期追踪
        pending_changes=pending_changes,
        last_change_stability=0.0,  # 简化：无历史
        violations_100=0,
        global_utilization=round(global_load, 4),
    )
    rhythm_violations = _check_rhythm_violations(rhythm, pending_changes)

    results["section_minus1_rhythm"] = {
        "phase": rhythm.phase,
        "global_utilization": rhythm.global_utilization,
        "pending_changes": rhythm.pending_changes,
        "violations_count": len(rhythm_violations),
        "violations": rhythm_violations,
    }
    results["rhythm_violations"] = rhythm_violations

    # ── 全局摘要 ──────────────────────────────
    results["global_load"] = round(global_load, 4)
    results["bottleneck_chain"] = bottleneck
    results["phase"] = phase

    # 负载抑制的耦合点
    for cl in chain_loads:
        if cl.suppressed:
            results["suppressed_couplings"].append({
                "chain": cl.chain,
                "load_ratio": cl.load,
                "recommended_action": cl.recommendation,
            })
            results["recommended_actions"].append(
                f"{cl.chain}: {cl.recommendation}"
            )

    # 边界违规行动
    for b in boundary_list:
        if b.status in ("CRITICAL", "VIOLATED"):
            results["recommended_actions"].append(
                f"BOUNDARY [{b.name}]: {b.status} — {_action_for_boundary(b)}"
            )

    # 写入状态文件
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    return results


def _action_for_chain(chain_id: str, load: float, warn: float, hard: float) -> str:
    """每条链超载时的标准行动"""
    actions = {
        "T": "HARD_CUTOFF: 暂停所有锚点写入，仅维持轴心心跳",
        "C": "DEFER: 返回 BACKPRESSURE 信号给调度，拒绝新钢印铸造",
        "D": "DEGRADE: 切换至启发式简表，停止动态优化",
        "M": "ISOLATE: 冻结非活跃格子，仅服务当前焦点层",
        "E": "STRAND: 将低优先级残渣移入长期冷存储，跳过分析",
        "W": "THROTTLE: 扩大监控时间窗口，牺牲实时性保存活",
        "L": "PAUSE: 冻结参数更新，仅记录观测数据供离线分析",
    }
    return actions.get(chain_id, "REVIEW")


def _calc_ethical_anchor_precision() -> float:
    """
    伦理边界计算：锚点精度下限是否被侵蚀
    = 低 coherence（< 0.7）锚点占比
    越低越好。> threshold = VIOLATED
    """
    heritage = _safe_read_json(PATHS["heritage"], {})
    anchors = heritage.get("anchors", {})
    if not anchors:
        return 0.0  # 无锚点 = 未建立锚点系统 = 未触犯
    low_coherence = sum(
        1 for a in anchors.values()
        if a.get("causal_coherence", 1.0) < 0.7
    )
    ratio = low_coherence / len(anchors)
    return min(1.0, ratio * 2)  # 放大使阈值有效


def _action_for_boundary(b: Boundary) -> str:
    if b.btype == BoundaryType.HARD:
        return "无条件拒绝所有建立请求"
    elif b.btype == BoundaryType.ETHICAL:
        return "受控停机，等待人工干预"
    else:
        return "触发代谢消耗，延迟调整"


# ─────────────────────────────────────────────
# 拓扑修正（负载感知版）
# ─────────────────────────────────────────────

def is_missing_structural(chain: str, current_load: float) -> bool:
    """
    负载感知拓扑修正：
    - 只有当 load < 80% warn_threshold 时，"NULL返回"才判定为结构缺失
    - 否则判定为"负载抑制"，触发负载管理流程
    """
    cfg = CHAIN_THRESHOLDS.get(chain, {})
    warn = cfg.get("warn_at", 0.7)
    return current_load < warn * 0.8


def boundary_check(need_score: float, chain_load: float, boundary_proximity: dict) -> str:
    """
    evaluate_coupling_need() 输出过滤：
    - need_score > threshold 但边界接近 → DEFER
    - 触及伦理边界 → 受控停机
    """
    hard = boundary_proximity.get("HARD", 0.0)
    ethical = boundary_proximity.get("ETHICAL", 0.0)
    soft = boundary_proximity.get("SOFT", 0.0)

    if ethical >= 1.0:
        return "ETHICAL_STOP"
    if hard >= 0.90:
        return "HARD_REJECT"
    if chain_load >= 0.80:
        return "DEFER"
    if soft >= 0.85:
        return "SOFT_THROTTLE"
    return "APPROVED"


# ─────────────────────────────────────────────
# 打印输出
# ─────────────────────────────────────────────

def print_monitor(results: dict, detail: bool = False):
    print(f"\n{'=' * 60}")
    print(f"  [SECTION-0] Boundary & Load Monitor  {results['scan_ts'][:19]}")
    print(f"{'─' * 60}")

    # 全局
    print(f"  Phase: {results['phase']:<12}  Global Load: {results['global_load']:.3f}")
    print(f"  Bottleneck: {results['bottleneck_chain'] or 'N/A'}")

    # 各链
    print(f"\n  Chain Loads:")
    for chain_id, d in results["section_0_load"].items():
        sup = " [SUPPRESSED]" if d["suppressed"] else ""
        print(f"    {chain_id}: {d['load']:.3f}  {d['status']}{sup}")

    # 边界
    print(f"\n  Boundaries:")
    for bname, bd in results["boundaries"].items():
        print(f"    {bd['type']:<8} {bname:<30} {bd['proximity']:.3f}  {bd['status']}")

    # 节律
    r = results["section_minus1_rhythm"]
    print(f"\n  [SECTION-1] Rhythm:")
    print(f"    Phase: {r['phase']}  Pending: {r['pending_changes']}")
    print(f"    Violations: {r['violations_count']}")
    if r.get("violations"):
        for v in r["violations"]:
            print(f"      - {v['type']}: {v['detail']}")

    # 抑制
    if results.get("suppressed_couplings"):
        print(f"\n  Load-Suppressed (≠ structural missing):")
        for s in results["suppressed_couplings"]:
            print(f"    {s['chain']}: load={s['load_ratio']:.3f}  -> {s['recommended_action']}")

    # 行动建议
    if results.get("recommended_actions"):
        print(f"\n  Recommended Actions:")
        for a in results["recommended_actions"]:
            print(f"    -> {a}")

    print(f"{'─' * 60}")
    print(f"  State: {OUT}")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 边界与负载监控")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--chain", choices=["T","C","D","M","E","W","L"], help="单链负载")
    args = parser.parse_args()

    results = run_monitor(detail=args.detail)
    print_monitor(results, detail=args.detail)

    if args.chain:
        d = results["section_0_load"].get(args.chain, {})
        print(f"\n  Chain {args.chain}: load={d.get('load','?')}, status={d.get('status','?')}")
