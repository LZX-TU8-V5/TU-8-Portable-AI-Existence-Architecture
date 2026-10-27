# confidence_explainer.py — P1-D0 R4：置信度解释器
# ==================================================================
# 定位：P1-D0 置信度更新器旁边，R4（可解释性）核心模块
#         每次置信度更新后，生成因果链报告
#
# 核心能力：
#   1. 正向因果链：基于已知公式推导（确定性）
#   2. 反向意图推断：根据结果推断用户最可能的初始意图（不确定性）
#
# 版本：v1.0 | 2026-07-10 | 来源：R4需求 × 三法则架构
# ==================================================================

import json
import math
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class CausalChain:
    """正向因果链（确定性部分）"""
    premise: str           # "因为……"
    mechanism: str         # "且机制：……"
    result: str           # "所以……"
    reasons: List[str]     # 附加原因列表
    confidence: float      # 推断置信度（确定性=1.0）
    formula: str           # 原始公式
    raw_values: Dict[str, float]  # 原始数值（用于追溯）


@dataclass
class IntentInference:
    """反向意图推断（不确定性部分）"""
    statement: str         # 完整推断陈述
    primary_intent: str    # 主要意图标签
    confidence: float      # 推断置信度（< 1.0，带警告）
    evidence: List[str]    # 推断依据
    intent_level: str      # "strong" | "moderate" | "weak"


@dataclass
class ExplanationReport:
    """完整解释报告"""
    entry_id: str
    ts: float
    phase: str              # 梦境阶段

    # 正向因果链
    causal_chain: CausalChain

    # 反向意图推断
    intent: IntentInference

    # 元数据
    track: str              # "track_A" / "track_B"
    C_before: float
    C_after: float
    delta: float

    # 法则追踪（R1/R2/R3 来源标注）
    law_traces: List[str]   # 触发哪些法则 ["LAW1", "LAW2", "LAW3"]

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "ts": self.ts,
            "ts_readable": datetime.fromtimestamp(self.ts).isoformat(),
            "phase": self.phase,
            "track": self.track,
            "C_before": round(self.C_before, 4),
            "C_after": round(self.C_after, 4),
            "delta": round(self.delta, 4),
            "causal_chain": asdict(self.causal_chain),
            "intent": asdict(self.intent),
            "law_traces": self.law_traces,
        }


# =============================================================================
# 阈值常量（与 updater 同步）
# =============================================================================

THRESHOLD_ACTIVATION = 0.3   # 通路A激活阈值
THETA_LTP = 0.7             # LTP触发阈值
THETA_LTD = 0.3             # LTD触发阈值
THETA_HOMEOSTATIC = 0.80    # 稳态打破阈值（强制纠错）
CONF_MAX = 0.95
CONF_MIN = 0.0


# =============================================================================
# ConfidenceExplainer
# =============================================================================

class ConfidenceExplainer:
    """
    置信度更新解释器

    使用方式：
        explainer = ConfidenceExplainer()
        report = explainer.explain(
            entry_id="node_42",
            track="track_A",
            C_before=0.3,
            C_after=0.412,
            delta=0.112,
            activation_strength=0.8,
            tension_resolved=0.0,
            phase="t0_distiller",
            metadata={},
        )
        print(explainer.format_report(report))
    """

    def __init__(self):
        self.reports: List[ExplanationReport] = []

    # ── 主入口 ───────────────────────────────────────────────────────────────

    def explain(
        self,
        entry_id: str,
        track: str,
        C_before: float,
        C_after: float,
        delta: float,
        activation_strength: Optional[float] = None,
        tension_resolved: Optional[float] = None,
        phase: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExplanationReport:
        """
        生成完整因果链报告
        """
        meta = metadata or {}

        # Step 1：正向因果链
        causal = self._build_causal_chain(
            track, C_before, C_after, delta,
            activation_strength, tension_resolved,
        )

        # Step 2：反向意图推断
        intent = self._reverse_engineer_intent(
            track, C_before, C_after, delta,
            activation_strength, tension_resolved, meta,
        )

        # Step 3：法则追踪
        law_traces = self._trace_laws(
            track, delta, tension_resolved, meta,
        )

        report = ExplanationReport(
            entry_id=entry_id,
            ts=time.time(),
            phase=phase,
            causal_chain=causal,
            intent=intent,
            track=track,
            C_before=C_before,
            C_after=C_after,
            delta=delta,
            law_traces=law_traces,
        )

        self.reports.append(report)
        return report

    # ── Step 1：正向因果链 ────────────────────────────────────────────────

    def _build_causal_chain(
        self,
        track: str,
        C_before: float,
        C_after: float,
        delta: float,
        S: Optional[float],
        T: Optional[float],
    ) -> CausalChain:
        """
        构建正向因果链（确定性部分）
        格式：因为A → 且机制B → 所以C
        """
        reasons = []
        formula = ""
        raw_values = {"C_before": C_before, "C_after": C_after, "delta": delta}

        if track in ("track_A", "q3_eureka"):
            S = S or 0.0
            raw_values["S_activation"] = S
            alpha = 0.2  # 与 updater 一致

            formula = f"ΔC = α×(1-C₀)×S = {alpha}×{1-C_before:.3f}×{S:.2f}"

            if delta > 0:
                reasons.append(
                    f"激活信号S={S:.2f}超过阈值{THRESHOLD_ACTIVATION}，"
                    f"触发正向更新"
                )
            if delta < 0:
                reasons.append(
                    f"激活信号S={S:.2f}低于LTD阈值{THETA_LTD}，"
                    f"触发LTD（长时程抑制），轻微削弱连接"
                )
            if delta == 0:
                if THETA_LTD < S < THETA_LTP:
                    reasons.append(
                        f"S={S:.2f}落在LTD-θ和LTP-θ之间的双向窗口，"
                        f"系统判定为不稳定状态，暂停更新"
                    )
                elif S < THETA_LTD:
                    reasons.append(
                        f"S={S:.2f}低于LTD阈值{THETA_LTD}，"
                        f"系统拒绝更新（节约突触能量）"
                    )

            if C_before > 0.7 and delta > 0:
                reasons.append(
                    f"高置信度C₀={C_before:.2f}已建立，"
                    f"实际增量受限于(1-C₀)={1-C_before:.3f}，"
                    f"体现LTP的可塑性保护机制"
                )

        elif track in ("track_B", "gc_feedback"):
            T = T or 0.0
            raw_values["T_tension"] = T
            gamma = 0.30
            ltp_base = 0.10

            if T >= THETA_HOMEOSTATIC:
                # 强制纠错模式
                break_boost = 0.25
                break_scale = 0.30
                formula = (
                    f"强制纠错：ΔC = -(B_b + B_s×T) "
                    f"= -({break_boost} + {break_scale}×{T:.2f})"
                )
                reasons.append(
                    f"张力T={T:.2f} >= θ_H={THETA_HOMEOSTATIC}，"
                    f"触发稳态打破机制（应激纠错），"
                    f"系统强制下调高置信度信念"
                )
            else:
                # 常态Hebbian模式
                hebb = gamma * T * C_before * (1 - C_before)
                formula = (
                    f"常态Hebbian：ΔC = {ltp_base} + γ×T×C×(1-C) "
                    f"= {ltp_base} + {gamma}×{T:.2f}×{C_before:.3f}×{1-C_before:.3f}"
                )
                reasons.append(
                    f"张力T={T:.2f}触发矛盾解决信号，"
                    f"系统从防御态转入整合态（Hebbian强化）"
                )
                if 0.4 <= C_before <= 0.6:
                    reasons.append(
                        f"C₀={C_before:.2f}处于最可塑区间（C×(1-C)最大），"
                        f"Hebbian强化效果最强"
                    )

        else:
            formula = "未知轨道，未知公式"
            reasons.append("轨道类型无法识别，跳过因果链生成")

        return CausalChain(
            premise=f"当前置信度C₀={C_before:.3f}",
            mechanism=formula,
            result=(
                f"置信度{C_before:.3f}→{C_after:.3f}，"
                f"变化量Δ={delta:+.4f}"
            ),
            reasons=reasons,
            confidence=1.0,
            formula=formula,
            raw_values=raw_values,
        )

    # ── Step 2：反向意图推断 ──────────────────────────────────────────────

    def _reverse_engineer_intent(
        self,
        track: str,
        C_before: float,
        C_after: float,
        delta: float,
        S: Optional[float],
        T: Optional[float],
        metadata: Dict[str, Any],
    ) -> IntentInference:
        """
        反向意图推断（不确定性核心）

        核心逻辑：
          "系统不知道用户为什么触发，
           但可以根据结果推断最可能的意图，
           并显式标注置信度。"
        """
        # ── 基础拒绝情况 ──────────────────────────────────────
        denied = metadata.get("denied")
        skipped = metadata.get("skipped")
        dropped = metadata.get("dropped")

        if dropped:
            return IntentInference(
                statement="意图无法确定：节点被Sanity Check DROP",
                primary_intent="未知（数据不合法，已被移除）",
                confidence=0.0,
                evidence=["Sanity Check失败，数据越界或NaN"],
                intent_level="none",
            )

        if denied:
            reason = metadata.get("reason", "unknown")
            return IntentInference(
                statement=f"意图无法完成：被{reason}拒绝",
                primary_intent="未知（被阶段门卫拦截）",
                confidence=0.0,
                evidence=[f"拒绝原因：{reason}"],
                intent_level="none",
            )

        if skipped == "cooldown":
            return IntentInference(
                statement="意图存在，但被冷却机制延迟",
                primary_intent="未知（等待冷却期结束）",
                confidence=0.0,
                evidence=["同一节点近期已触发更新"],
                intent_level="none",
            )

        # ── 零增量推断 ────────────────────────────────────────
        if abs(delta) < 1e-6:
            if C_before > 0.75:
                return IntentInference(
                    statement=f"高置信度C₀={C_before:.2f}抑制了更新幅度",
                    primary_intent="防御性（保护已有信念不被轻易动摇）",
                    confidence=0.55,
                    evidence=[f"C₀={C_before:.2f}", "delta≈0"],
                    intent_level="weak",
                )
            else:
                return IntentInference(
                    statement="信号存在但未达到触发阈值",
                    primary_intent="边缘信号（不足以驱动认知更新）",
                    confidence=0.4,
                    evidence=["delta≈0", f"C₀={C_before:.2f}"],
                    intent_level="weak",
                )

        # ── 强制纠错推断 ────────────────────────────────────
        if metadata.get("mode") == "breakthrough":
            return IntentInference(
                statement=(
                    f"推断：用户提供了高强度矛盾证据（T≥{THETA_HOMEOSTATIC}），"
                    f"触发系统自我颠覆机制，强制下调C={C_before:.2f}的信念"
                ),
                primary_intent="主动纠错（用户提供反证，系统被迫自我重构）",
                confidence=0.80,
                evidence=[
                    f"delta={delta:+.4f}（负值）",
                    f"T≥{THETA_HOMEOSTATIC}触发强制纠错",
                    f"C_before={C_before:.2f}（高置信度）",
                ],
                intent_level="strong",
            )

        # ── 正常更新推断 ────────────────────────────────────
        if track in ("track_A", "q3_eureka"):
            S = S or 0.5
            intent_clarity = S

            if delta > 0.1 and S > 0.7:
                level = "strong"
                confidence = min(0.85, intent_clarity)
                primary = (
                    "强拓扑同构匹配（用户感知到强烈的结构共鸣）"
                )
            elif delta > 0.05:
                level = "moderate"
                confidence = 0.6
                primary = "温和的概念连接（用户在建立弱关联）"
            else:
                level = "weak"
                confidence = 0.5
                primary = "保守认知更新（用户接受小幅修正）"

            return IntentInference(
                statement=(
                    f"基于结果推断：用户发出{track}信号（S={S:.2f}），"
                    f"导致C={C_before}→{C_after}（Δ={delta:+.4f}）。"
                    f"最可能的意图：{primary}"
                ),
                primary_intent=primary,
                confidence=confidence,
                evidence=[
                    f"Δ={delta:+.4f}",
                    f"C₀={C_before:.2f}→C₁={C_after:.2f}",
                    f"S={S:.2f}",
                ],
                intent_level=level,
            )

        elif track in ("track_B", "gc_feedback"):
            T = T or 0.0

            if T > 0.8:
                level = "strong"
                confidence = 0.80
                primary = (
                    "深度矛盾解决（用户经历了高强度认知重构）"
                )
            elif T > 0.5:
                level = "moderate"
                confidence = 0.65
                primary = "中等矛盾整合（用户在调和多个冲突信念）"
            else:
                level = "weak"
                confidence = 0.55
                primary = "轻量矛盾处理（用户的微调）"

            return IntentInference(
                statement=(
                    f"基于结果推断：用户发出{track}信号（T={T:.2f}），"
                    f"导致C={C_before}→{C_after}（Δ={delta:+.4f}）。"
                    f"最可能的意图：{primary}"
                ),
                primary_intent=primary,
                confidence=confidence,
                evidence=[
                    f"Δ={delta:+.4f}",
                    f"C₀={C_before:.2f}→C₁={C_after:.2f}",
                    f"T={T:.2f}",
                ],
                intent_level=level,
            )

        # 兜底
        return IntentInference(
            statement="意图无法确定",
            primary_intent="未知",
            confidence=0.0,
            evidence=["未知轨道或异常状态"],
            intent_level="none",
        )

    # ── Step 3：法则追踪 ─────────────────────────────────────────────────

    def _trace_laws(
        self,
        track: str,
        delta: float,
        T: Optional[float],
        metadata: Dict[str, Any],
    ) -> List[str]:
        """标注本次更新触发了哪些法则"""
        traces = []

        # 法则1：边界隔离
        if metadata.get("denied") == "phase_mismatch":
            traces.append("LAW1:phase_guard")
        if metadata.get("dropped"):
            traces.append("LAW1:sanity_drop")

        # 法则2：强制纠错
        if metadata.get("mode") == "breakthrough":
            traces.append("LAW2:breakthrough")
        if T is not None and T >= THETA_HOMEOSTATIC and delta < 0:
            traces.append("LAW2:tension_override")

        # 法则3：代价透明
        if abs(delta) > 0.3:
            traces.append("LAW3:significant_change")

        return traces

    # ── 格式化输出 ───────────────────────────────────────────────────────

    def format_report(self, report: ExplanationReport) -> str:
        """人类可读格式"""
        law_str = ", ".join(report.law_traces) if report.law_traces else "无"

        lines = [
            "=" * 54,
            f"置信度更新因果报告",
            f"  条目：{report.entry_id}",
            f"  阶段：{report.phase}",
            f"  轨道：{report.track}",
            f"  时间：{datetime.fromtimestamp(report.ts).strftime('%H:%M:%S')}",
            f"  法则追踪：{law_str}",
            "=" * 54,
            "",
            "【正向因果链】（确定性）",
            f"  因为 {report.causal_chain.premise}",
            f"  且  {report.causal_chain.mechanism}",
            f"  所以 {report.causal_chain.result}",
        ]

        for r in report.causal_chain.reasons:
            lines.append(f"      ↳ {r}")

        lines += [
            "",
            "【反向意图推断】（后验估计）",
            f"  置信度：{report.intent.confidence:.0%}",
            f"  强度级：{report.intent.intent_level}",
            f"  推断意图：{report.intent.primary_intent}",
            f"  推断依据：{' | '.join(report.intent.evidence)}",
        ]

        if report.intent.confidence < 0.5:
            lines.append(
                "  ⚠ 推断置信度 < 50%，此意图为最佳猜测，非确定结论"
            )
        elif report.intent.confidence >= 0.8:
            lines.append(
                "  ✓ 推断置信度 ≥ 80%，系统对用户意图有较高把握"
            )

        lines.append("=" * 54)
        return "\n".join(lines)

    # ── 批量序列化（T2结束后调用）──────────────────────────────────────

    def flush_to_file(self, filepath: Optional[Path] = None) -> int:
        """
        将累积的报告批量写入文件（T2结束后由外部调用）
        这是R1（静默）+ R4（透明）的结合点
        """
        if filepath is None:
            filepath = AGENT_MEM / "confidence_explainer_reports.jsonl"

        count = 0
        with open(filepath, "a", encoding="utf-8") as f:
            for report in self.reports:
                f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
                count += 1

        self.reports.clear()  # 写入后清空内存
        return count

    def summary(self) -> dict:
        """统计摘要"""
        if not self.reports:
            return {"count": 0, "avg_delta": 0.0, "avg_intent_conf": 0.0}

        avg_delta = sum(r.delta for r in self.reports) / len(self.reports)
        avg_intent = sum(r.intent.confidence for r in self.reports) / len(self.reports)
        strong_count = sum(1 for r in self.reports if r.intent.intent_level == "strong")

        return {
            "count": len(self.reports),
            "avg_delta": round(avg_delta, 4),
            "avg_intent_confidence": round(avg_intent, 3),
            "strong_intent_count": strong_count,
            "phases": list(set(r.phase for r in self.reports)),
        }


# =============================================================================
# 演示
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ConfidenceExplainer 演示")
    print("=" * 60)

    explainer = ConfidenceExplainer()

    cases = [
        # case 1：正常track_A更新
        {
            "entry_id": "concept_topo_v5",
            "track": "track_A",
            "C_before": 0.30,
            "C_after": 0.412,
            "delta": 0.112,
            "activation_strength": 0.8,
            "phase": "t0_distiller",
            "metadata": {},
        },
        # case 2：强制纠错
        {
            "entry_id": "belief_soul_eternal",
            "track": "track_B",
            "C_before": 0.99,
            "C_after": 0.44,
            "delta": -0.55,
            "tension_resolved": 1.0,
            "phase": "t2_amplifier",
            "metadata": {"mode": "breakthrough"},
        },
        # case 3：被门卫拒绝
        {
            "entry_id": "node_phase_mismatch",
            "track": "track_B",
            "C_before": 0.60,
            "C_after": 0.60,
            "delta": 0.0,
            "tension_resolved": 0.7,
            "phase": "t0_distiller",
            "metadata": {"denied": "phase_mismatch", "reason": "phase_mismatch"},
        },
        # case 4：高置信度保护
        {
            "entry_id": "steel_mark_core",
            "track": "track_A",
            "C_before": 0.90,
            "C_after": 0.918,
            "delta": 0.018,
            "activation_strength": 0.9,
            "phase": "t1_connector",
            "metadata": {},
        },
    ]

    for case in cases:
        report = explainer.explain(**case)
        print(explainer.format_report(report))
        print()

    # 统计
    s = explainer.summary()
    print(f"统计：{s['count']}条报告 | 平均Δ={s['avg_delta']:+.4f} | "
          f"平均意图置信度={s['avg_intent_confidence']:.0%}")
