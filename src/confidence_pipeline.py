# confidence_pipeline.py — P1-D0 R1+R2+R4 三件套串联集成
# =============================================================================
# 定位：dual_track_state_machine + synaptic_confidence_updater + confidence_explainer
#         三件套串联，形成完整的"计算→锁检→解释"流水线
#
# 流程：
#   输入信号
#     → SynapticUpdater（数学计算）
#     → T2StateMachine（三法则物理锁）
#     → ConfidenceExplainer（因果报告）
#     → 输出结果 + 报告
#
# 版本：v1.0 | 2026-07-10
# =============================================================================

import sys
from pathlib import Path
from typing import Optional, Dict, Any

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
sys.path.insert(0, str(WORKSPACE / "src"))

from synaptic_confidence_updater import SynapticConfidenceUpdater
from dual_track_state_machine import T2StateMachine, CostState
from confidence_explainer import ConfidenceExplainer


# =============================================================================
# ConfidencePipeline
# =============================================================================

class ConfidencePipeline:
    """
    置信度更新流水线——三件套串联

    使用方式：
        pipeline = ConfidencePipeline()
        result = pipeline.process(
            entry_id="concept_v5",
            C_before=0.99,
            track="track_B",
            T=1.0,
            phase="t2_amplifier",
        )
        # result = {updater_result, state_result, report, explainer_summary}
    """

    def __init__(self):
        self.updater = SynapticConfidenceUpdater()
        self.state_machine = T2StateMachine()
        self.explainer = ConfidenceExplainer()
        self._session_count = 0

    def process(
        self,
        entry_id: str,
        C_before: float,
        track: str,
        phase: str,
        T: Optional[float] = None,
        S: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        流水线主入口

        三阶段：
          Stage 1（Updater）：数学计算 → raw_delta
          Stage 2（StateMachine）：三锁检查 → 物理流转
          Stage 3（Explainer）：因果报告 → human_readable
        """
        meta = metadata or {}
        self._session_count += 1

        # ── Stage 1：数学计算 ────────────────────────────────────
        # 构造上下文，委托给 updater
        from dual_track_confidence_updater import DreamSignalContext, DreamPhase

        phase_enum = DreamPhase.T2 if "t2" in phase else DreamPhase.T1
        ctx = DreamSignalContext(
            entry_id=entry_id,
            phase=phase_enum,
            confidence_current=C_before,
            track=track,
            activation_strength=S,
            tension_resolved=T,
        )

        updater_result = self.updater.process_dream_signal(ctx)

        # ── Stage 2：三锁检查 ───────────────────────────────────
        state_result = self.state_machine.process(
            entry_id=entry_id,
            C_before=C_before,
            track=track,
            T=T,
            raw_delta=updater_result.delta,
            phase=phase,
            metadata={
                "mode": updater_result.metadata.get("mode"),
                "denied": updater_result.metadata.get("denied"),
                "reason": updater_result.metadata.get("reason"),
            },
        )

        # ── Stage 3：因果报告 ────────────────────────────────────
        # 只有正常流转或强制纠错才生成报告（DROP/BLOCKED 不生成）
        report = None
        if state_result.state in ("TRANSITION_NEXT", "BREAKTHROUGH_T2"):
            C_after = C_before + (state_result.delta_applied or updater_result.delta)
            report = self.explainer.explain(
                entry_id=entry_id,
                track=track,
                C_before=C_before,
                C_after=C_after,
                delta=state_result.delta_applied or updater_result.delta,
                activation_strength=S,
                tension_resolved=T,
                phase=phase,
                metadata={
                    "mode": updater_result.metadata.get("mode"),
                    "denied": updater_result.metadata.get("denied"),
                    "reason": updater_result.metadata.get("reason"),
                    **meta,
                },
            )

        return {
            "entry_id": entry_id,
            "session_count": self._session_count,
            "stage1_updater": {
                "delta_raw": updater_result.delta,
                "C_before": updater_result.confidence_before,
                "C_after": updater_result.confidence_after,
                "metadata": updater_result.metadata,
            },
            "stage2_state_machine": state_result.to_dict(),
            "stage3_explainer_report": report.to_dict() if report else None,
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "session_count": self._session_count,
            "explainer_summary": self.explainer.summary(),
            "cost_report": self.state_machine.get_cost_report(),
        }

    def flush_reports(self) -> int:
        """T2结束后调用：将累积的解释报告批量写入文件"""
        return self.explainer.flush_to_file()


# =============================================================================
# 演示
# =============================================================================

if __name__ == "__main__":
    import io, json
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

    print("=" * 60)
    print("ConfidencePipeline 三件套串联演示")
    print("=" * 60)

    pipeline = ConfidencePipeline()

    cases = [
        # case 1：正常更新
        {
            "entry_id": "concept_topo",
            "C_before": 0.50,
            "track": "track_A",
            "phase": "t0_distiller",
            "S": 0.80,
        },
        # case 2：强制纠错
        {
            "entry_id": "belief_strong",
            "C_before": 0.99,
            "track": "track_B",
            "phase": "t2_amplifier",
            "T": 1.0,
        },
        # case 3：高置信度保护（C=0.90, S=0.9 → LTP，限制因子生效）
        {
            "entry_id": "steel_mark",
            "C_before": 0.90,
            "track": "track_A",
            "phase": "t1_connector",
            "S": 0.90,
        },
    ]

    for i, case in enumerate(cases, 1):
        print(f"\n{'='*50}")
        print(f"Case {i}: {case['entry_id']}")
        print(f"  输入：C={case['C_before']}, track={case['track']}, ", end="")
        if "S" in case:
            print(f"S={case['S']}", end="")
        if "T" in case:
            print(f"T={case['T']}", end="")
        print()

        result = pipeline.process(**case)

        print(f"\n  ─ Stage 1（Updater）：Δ={result['stage1_updater']['delta_raw']:+.4f}")
        print(f"  ─ Stage 2（StateMachine）：{result['stage2_state_machine']['state']}")
        print(f"    法则：{result['stage2_state_machine']['law_traces']}")
        print(f"    代价：cost={result['stage2_state_machine']['cost_impact']}, recorded={result['stage2_state_machine']['cost_recorded']}")

        report = result["stage3_explainer_report"]
        if report:
            print(f"\n  ─ Stage 3（Explainer）：")
            print(f"    因果链：{report['causal_chain']['mechanism']}")
            print(f"    意图推断：{report['intent']['primary_intent']}（{report['intent']['confidence']:.0%}）")
        else:
            print(f"  ─ Stage 3：跳过（状态={result['stage2_state_machine']['state']}）")

    # 汇总
    print(f"\n{'='*60}")
    summary = pipeline.summary()
    print(f"汇总：")
    print(f"  处理条数：{summary['session_count']}")
    print(f"  解释器：{summary['explainer_summary']}")
    print(f"  状态代价：总cost={summary['cost_report']['total_cost']}")
