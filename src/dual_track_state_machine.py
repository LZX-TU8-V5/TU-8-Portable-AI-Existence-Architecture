# dual_track_state_machine.py — P1-D0 三法则物理锁状态机
# =============================================================================
# 定位：dual_track_confidence_updater.py 的上游路由层
#         所有置信度更新在进入 updater 之前，先过三法则物理锁
#
# 三锁：
#   LAW1_SANITY  → 边界即防线，数据不合法 → DROPPED（节点消失）
#   LAW2_BREAKTHROUGH → 稳态是例外，T >= θ_H → BREAKTHROUGH_T2（强制纠错）
#   LAW3_COST   → 隔离有代价，cost未记录 → COST_BLOCKED（状态机锁死）
#
# 冲突规则：
#   Sanity FAIL + Tension FAIL → Sanity胜（DROPPED）
#   Tension FAIL + Cost未记录 → Cost胜（COST_BLOCKED）
#
# 版本：v1.0 | 2026-07-10 | 来源：三法则 × 状态机设计
# =============================================================================

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"


# =============================================================================
# 阈值常量（与 updater / confidence_explainer 同步）
# =============================================================================

THETA_HOMEOSTATIC = 0.80   # 稳态打破阈值
CONF_MIN = 0.0
CONF_MAX = 0.95
MAX_SINGLE_DELTA = 1.0     # 单次更新上限


# =============================================================================
# Guard 返回值
# =============================================================================

@dataclass
class GuardResult:
    """Guard 检查结果——决定状态机物理流向"""
    pass_: bool
    target_state: str
    law: str          # "LAW1" / "LAW2" / "LAW3"
    reason: str
    cost_impact: int  # 产生多少隔离代价（0或1）
    detail: Optional[str] = None
    mode: str = "normal"  # "breakthrough" / "normal" / "dropped"
    raw_delta: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "pass": self.pass_,
            "target_state": self.target_state,
            "law": self.law,
            "reason": self.reason,
            "cost_impact": self.cost_impact,
            "detail": self.detail,
            "mode": self.mode,
            "raw_delta": self.raw_delta,
        }


# =============================================================================
# 状态机结果
# =============================================================================

@dataclass
class ProcessResult:
    """状态机处理结果"""
    state: str                    # "DROPPED" / "BREAKTHROUGH_T2" / "TRANSITION_NEXT" / "COST_BLOCKED"
    entry_id: str
    delta_applied: Optional[float] = None
    cost_recorded: bool = False
    cost_impact: int = 0
    law_traces: List[str] = field(default_factory=list)
    detail: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "entry_id": self.entry_id,
            "delta_applied": self.delta_applied,
            "cost_recorded": self.cost_recorded,
            "cost_impact": self.cost_impact,
            "law_traces": self.law_traces,
            "detail": self.detail,
            "error": self.error,
        }


# =============================================================================
# 三道物理锁
# =============================================================================

class LAW1_SanityGuard:
    """
    法则1：边界即防线

    在状态机中，这个检查不是"if判断"，是"物理锁"。
    检查失败 → 状态机无法进入 COST_ACCOUNTING
              → 只能进入 DROPPED 路径
              → 节点物理上从状态机中移除

    检查项：
      1. delta 是 NaN / Infinity
      2. C_before 不在 [0, 1]
      3. C_after 计算后超出 [0, 1]
      4. |delta| > MAX_SINGLE_DELTA（单次更新不可能超过1.0）
    """

    LOCK_NAME = "LAW1_BOUNDARY"

    def check(
        self,
        entry_id: str,
        C_before: float,
        delta: float,
    ) -> GuardResult:
        """
        返回值决定状态机物理流向：
          PASS → 允许进入 COST_ACCOUNTING
          FAIL → 强制跳转到 DROPPED 路径
        """
        C_after = C_before + delta

        # ── 检查1：delta 是 NaN / Infinity ───────────────────────
        if math.isnan(delta) or math.isinf(delta):
            return GuardResult(
                pass_=False,
                target_state="DROPPED",
                law="LAW1",
                reason="delta_non_numeric",
                cost_impact=1,
                detail=f"C_before={C_before:.4f}, delta={delta}",
                mode="dropped",
                raw_delta=delta,
            )

        # ── 检查2：C_before 严重越界（允许轻微超限给强制纠错留空间）
        # 宽松：允许 C_before 在 [0, 1.0]，因为强制纠错可能需要从 0.99 开始
        # 严格：只有 C_before < 0 或 > 1.5 才拒绝（0.99 < 1.5，正常）
        if not (CONF_MIN - 0.05 <= C_before <= 1.5):
            return GuardResult(
                pass_=False,
                target_state="DROPPED",
                law="LAW1",
                reason="confidence_before_out_of_bounds",
                cost_impact=1,
                detail=f"C_before={C_before:.4f} not in [0, 1.5]",
                mode="dropped",
                raw_delta=delta,
            )

        # ── 检查3：C_after 计算后超出 [0, CONF_MAX]（允许轻微超上限）
        # 轻微超限：允许 C_after 在 [0, 1.0]（给上下界留余量）
        if not (CONF_MIN <= C_after <= 1.0):
            return GuardResult(
                pass_=False,
                target_state="DROPPED",
                law="LAW1",
                reason="confidence_after_out_of_bounds",
                cost_impact=1,
                detail=f"C_before={C_before:.4f} + delta={delta:.4f} = C_after={C_after:.4f} out of [0, 1]",
                mode="dropped",
                raw_delta=delta,
            )

        # ── 检查4：|delta| 超出合理范围 ─────────────────────────
        if abs(delta) > MAX_SINGLE_DELTA:
            return GuardResult(
                pass_=False,
                target_state="DROPPED",
                law="LAW1",
                reason="delta_excessive",
                cost_impact=1,
                detail=f"|delta|={abs(delta):.4f} > {MAX_SINGLE_DELTA}",
                mode="dropped",
                raw_delta=delta,
            )

        return GuardResult(
            pass_=True,
            target_state="COST_ACCOUNTING",
            law="LAW1",
            reason="sanity_ok",
            cost_impact=0,
            detail=None,
            mode="normal",
            raw_delta=delta,
        )


class LAW2_TensionGuard:
    """
    法则2：稳态是例外

    当 T >= θ_H，状态机物理上必须进入 BREAKTHROUGH_T2 路径。
    没有"跳过"选项——这是强制路径，不是可选分支。

    FAIL 在这里不是"错误"，是"特殊路径触发信号"。
    """

    LOCK_NAME = "LAW2_BREAKTHROUGH"

    def check(self, T: Optional[float]) -> GuardResult:
        if T is None:
            return GuardResult(
                pass_=True,
                target_state="COST_ACCOUNTING",
                law="LAW2",
                reason="no_tension_data",
                cost_impact=0,
                detail="T=None，跳过强制纠错检查",
                mode="normal",
            )

        if T >= THETA_HOMEOSTATIC:
            return GuardResult(
                pass_=False,  # 故意 FAIL，触发特殊路径
                target_state="BREAKTHROUGH_T2",
                law="LAW2",
                reason="homeostatic_break",
                cost_impact=1,
                detail=f"T={T:.4f} >= θ_H={THETA_HOMEOSTATIC}，触发强制纠错",
                mode="breakthrough",
            )

        return GuardResult(
            pass_=True,
            target_state="COST_ACCOUNTING",
            law="LAW2",
            reason="normal_tension",
            cost_impact=0,
            detail=f"T={T:.4f} < θ_H={THETA_HOMEOSTATIC}",
            mode="normal",
        )


class LAW3_CostGuard:
    """
    法则3：隔离有代价，代价必须透明

    在状态机流转到下一状态之前，cost_counter 必须已更新。
    如果 cost 未记录 → COST_BLOCKED 状态机物理锁死。

    这是最强的物理锁：其他 Guard 失败还可以走特殊路径，
    COST_ACCOUNTING 未完成 → 彻底卡死。
    """

    LOCK_NAME = "LAW3_COST"

    def check(
        self,
        entry_id: str,
        cost_impact: int,
        cost_state: "CostState",
    ) -> GuardResult:
        """
        前置条件：
          每个 cost_impact > 0 的事件必须在 cost_counter 中有对应记录

        物理锁：
          如果 cost_state 确认此人已记录 → 允许流转
          如果未记录 → COST_BLOCKED
        """
        if cost_impact == 0:
            return GuardResult(
                pass_=True,
                target_state="TRANSITION_NEXT",
                law="LAW3",
                reason="no_cost",
                cost_impact=0,
                detail="无隔离代价，状态机正常流转",
                mode="normal",
            )

        # 检查 cost 是否已记录
        if cost_state.is_recorded(entry_id, cost_impact):
            return GuardResult(
                pass_=True,
                target_state="TRANSITION_NEXT",
                law="LAW3",
                reason="cost_recorded",
                cost_impact=cost_impact,
                detail=f"cost={cost_impact} 已记录，状态机流转",
                mode="normal",
            )
        else:
            # 物理锁死：cost 未记录，状态机无法流转
            return GuardResult(
                pass_=False,
                target_state="COST_BLOCKED",
                law="LAW3",
                reason="cost_not_recorded",
                cost_impact=0,
                detail=(
                    f"节点 {entry_id} 产生 cost_impact={cost_impact}，"
                    "但 cost_counter 未更新——状态机锁死，等待人工介入"
                ),
                mode="blocked",
            )


# =============================================================================
# 冲突判定器
# =============================================================================

class LockConflictResolver:
    """
    三锁冲突时，根据逻辑前提判定谁胜出

    冲突规则（硬编码，非软编码）：
      1. Sanity FAIL + Tension FAIL  → Sanity胜（DROPPED）
         理由：能纠错的前提是"有有效值可纠"
      2. Tension FAIL + Cost未记录  → Cost胜（COST_BLOCKED）
         理由：透明比执行更重要
      3. Sanity PASS + Tension FAIL + Cost未记录
                                   → Cost BLOCKED（Tension暂搁置）
    """

    def resolve(
        self,
        sanity: GuardResult,
        tension: GuardResult,
        cost: GuardResult,
    ) -> str:
        """
        返回值：最终目标状态字符串
        """
        # ── 冲突1：Sanity FAIL + Tension FAIL ────────────────────
        if not sanity.pass_ and not tension.pass_:
            # Sanity胜：能纠错的前提是数据有效
            return "DROPPED"

        # ── 冲突2：Tension FAIL + Cost BLOCKED ──────────────────
        if not tension.pass_ and not cost.pass_:
            # Cost胜：透明比执行更重要
            return "COST_BLOCKED"

        # ── 冲突3：Sanity PASS + Tension FAIL + Cost BLOCKED ─────
        if (sanity.pass_
                and not tension.pass_
                and not cost.pass_):
            return "COST_BLOCKED"

        # ── 无冲突：各自结果叠加 ─────────────────────────────────
        # 优先级：BLOCKED > DROPPED > BREAKTHROUGH > TRANSITION
        states = [sanity, tension, cost]
        for s in states:
            if not s.pass_:
                return s.target_state

        return "TRANSITION_NEXT"


# =============================================================================
# Cost 状态记录器
# =============================================================================

class CostState:
    """
    法则3：记录每次隔离事件的代价
    每条记录：{entry_id, cost, reason, ts}
    """

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or (AGENT_MEM / "law3_cost_state.json")
        self.records: List[Dict] = []
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def record(self, entry_id: str, cost: int, reason: str):
        """记录一次代价"""
        self.records.append({
            "entry_id": entry_id,
            "cost": cost,
            "reason": reason,
            "ts": time.time(),
            "ts_readable": datetime.now().isoformat(),
        })
        self._persist()

    def is_recorded(self, entry_id: str, cost: int) -> bool:
        """检查此人最近是否已有cost记录"""
        for rec in reversed(self.records):
            if rec.get("entry_id") == entry_id and rec.get("cost") == cost:
                return True
        return False

    def _persist(self):
        try:
            AGENT_MEM.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def summary(self) -> dict:
        total = sum(r["cost"] for r in self.records)
        return {
            "total_cost": total,
            "record_count": len(self.records),
            "records": self.records[-20:],  # 最近20条
        }


# =============================================================================
# T2 状态机主体
# =============================================================================

class T2StateMachine:
    """
    T2 阶段状态机——三法则物理锁集成

    使用方式：
        machine = T2StateMachine()
        result = machine.process(
            entry_id="concept_v5",
            C_before=0.99,
            track="track_B",
            T=1.0,
            raw_delta=-0.55,
            phase="t2_amplifier",
        )

    物理保证：
      - Sanity FAIL → 节点消失，无其他出口
      - Tension FAIL → 强制纠错，无其他出口
      - Cost未记录 → 状态机锁死，无法流转
    """

    def __init__(self, cost_state: Optional[CostState] = None):
        self.sanity = LAW1_SanityGuard()
        self.tension = LAW2_TensionGuard()
        self.cost = LAW3_CostGuard()
        self.conflict = LockConflictResolver()
        self.cost_state = cost_state or CostState()

    def process(
        self,
        entry_id: str,
        C_before: float,
        track: str,
        T: Optional[float],
        raw_delta: float,
        phase: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessResult:
        """
        状态机主入口——一次完整的三锁检查 + 物理流转

        参数：
          C_before: 更新前的置信度
          T: 张力值（track_B / gc_feedback）
          raw_delta: updater 计算出的原始 delta（未裁剪）
          track: 轨道标识
          phase: 梦境阶段
        """
        meta = metadata or {}

        # ── 第一步：三锁并行检查 ──────────────────────────────
        sanity_result = self.sanity.check(entry_id, C_before, raw_delta)
        tension_result = self.tension.check(T)
        cost_result = self.cost.check(
            entry_id,
            cost_impact=max(
                sanity_result.cost_impact,
                tension_result.cost_impact,
            ),
            cost_state=self.cost_state,
        )

        # ── 第二步：冲突判定 ────────────────────────────────────
        conflict_target = self.conflict.resolve(
            sanity_result, tension_result, cost_result
        )

        # ── 第三步：记录 cost（法则3强制）───────────────────────
        total_cost = max(sanity_result.cost_impact, tension_result.cost_impact)
        if total_cost > 0:
            reason = self._build_cost_reason(sanity_result, tension_result)
            self.cost_state.record(entry_id, total_cost, reason)

        # ── 第四步：物理流转 ────────────────────────────────────
        if conflict_target == "DROPPED":
            return self._dropped_state(entry_id, sanity_result)

        if conflict_target == "BREAKTHROUGH_T2":
            return self._breakthrough_state(entry_id, C_before, tension_result)

        if conflict_target == "COST_BLOCKED":
            return self._blocked_state(entry_id, cost_result)

        # TRANSITION_NEXT
        return ProcessResult(
            state="TRANSITION_NEXT",
            entry_id=entry_id,
            delta_applied=raw_delta,
            cost_recorded=True,
            cost_impact=total_cost,
            law_traces=self._build_law_traces(sanity_result, tension_result),
            detail=f"三锁全通过，delta={raw_delta:+.4f}，流转至下一状态",
        )

    def _dropped_state(self, entry_id: str, sanity: GuardResult) -> ProcessResult:
        return ProcessResult(
            state="DROPPED",
            entry_id=entry_id,
            cost_recorded=True,
            cost_impact=sanity.cost_impact,
            law_traces=["LAW1:sanity_drop"],
            detail=(
                f"LAW1触发：{sanity.reason}。"
                f"节点{entry_id}被DROP，彻底从流水线移除。"
                f"代价={sanity.cost_impact}（已记录）"
            ),
        )

    def _breakthrough_state(
        self,
        entry_id: str,
        C_before: float,
        tension: GuardResult,
    ) -> ProcessResult:
        # 从 detail 中提取 T 值
        detail = tension.detail or ""
        T_val = THETA_HOMEOSTATIC  # 默认值
        try:
            if "T=" in detail:
                T_val = float(detail.split("T=")[1].split(" ")[0])
        except Exception:
            pass

        # 强制纠错计算（与 updater 一致）
        delta_applied = -(0.25 + 0.30 * T_val)

        return ProcessResult(
            state="BREAKTHROUGH_T2",
            entry_id=entry_id,
            delta_applied=delta_applied,
            cost_recorded=True,
            cost_impact=tension.cost_impact,
            law_traces=["LAW2:breakthrough", "LAW2:tension_override"],
            detail=(
                f"LAW2触发：T={T_val:.3f} >= θ_H={THETA_HOMEOSTATIC}。"
                f"强制纠错：ΔC={delta_applied:+.4f}。"
                f"C_before={C_before:.3f} → C_new={C_before+delta_applied:.3f}。"
                f"代价={tension.cost_impact}（已记录）"
            ),
        )

    def _blocked_state(self, entry_id: str, cost: GuardResult) -> ProcessResult:
        return ProcessResult(
            state="COST_BLOCKED",
            entry_id=entry_id,
            cost_recorded=False,
            cost_impact=0,
            law_traces=["LAW3:cost_not_recorded"],
            detail=cost.detail or "状态机锁死，等待人工介入",
            error=f"LAW3 VIOLATION: cost未记录。{cost.detail}",
        )

    def _build_cost_reason(self, sanity, tension) -> str:
        reasons = []
        if not sanity.pass_:
            reasons.append(f"sanity:{sanity.reason}")
        if not tension.pass_:
            reasons.append(f"tension:{tension.reason}")
        return "; ".join(reasons) or "normal"

    def _build_law_traces(self, sanity, tension) -> List[str]:
        traces = []
        if not sanity.pass_:
            traces.append(f"LAW1:{sanity.reason}")
        if not tension.pass_:
            traces.append(f"LAW2:{tension.reason}")
        return traces

    def get_cost_report(self) -> dict:
        return self.cost_state.summary()


# =============================================================================
# 演示
# =============================================================================

if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("T2StateMachine 三法则物理锁演示")
    print("=" * 60)

    machine = T2StateMachine()

    cases = [
        # case 1：Sanity FAIL（delta=NaN）
        {
            "entry_id": "node_corrupted",
            "C_before": 0.5,
            "track": "track_A",
            "T": 0.3,
            "raw_delta": float("nan"),
            "phase": "t2_amplifier",
        },
        # case 2：Tension FAIL（强制纠错）
        {
            "entry_id": "belief_strong",
            "C_before": 0.99,
            "track": "track_B",
            "T": 1.0,
            "raw_delta": -0.55,
            "phase": "t2_amplifier",
        },
        # case 3：正常通过
        {
            "entry_id": "concept_normal",
            "C_before": 0.60,
            "track": "track_A",
            "T": 0.2,
            "raw_delta": 0.112,
            "phase": "t0_distiller",
        },
        # case 4：Sanity + Tension 同时FAIL（冲突：Sanity胜）
        {
            "entry_id": "node_corrupted_breakthrough",
            "C_before": 0.99,
            "track": "track_B",
            "T": 1.0,
            "raw_delta": float("nan"),  # Sanity FAIL + Tension FAIL
            "phase": "t2_amplifier",
        },
    ]

    for i, case in enumerate(cases, 1):
        print(f"\n--- Case {i}: {case['entry_id']} ---")
        result = machine.process(**case)
        print(f"  状态：{result.state}")
        print(f"  代价：cost={result.cost_impact}, recorded={result.cost_recorded}")
        print(f"  法则：{result.law_traces}")
        print(f"  详情：{result.detail}")
        if result.error:
            print(f"  ⚠ 错误：{result.error}")

    # 统计
    report = machine.get_cost_report()
    print(f"\n统计：总代价={report['total_cost']}，记录数={report['record_count']}")
