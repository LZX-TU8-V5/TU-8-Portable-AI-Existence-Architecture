"""
toct_reasoning.py — ToCT 反事实推理 v1.0

设计原则：
  ToCT = Thought of Counterfactual Thought
  反事实推理 = "如果当时选择不同，会怎样？"

物理映射：
  因果链条中的"岔路口" → 多条可能的演化路径
  反事实 = 未被选择的路径
  推理 = 对比已选路径与未选路径的差异

工程意义：
  1. 决策优化：识别关键决策点，避免重复错误
  2. 遗憾分析：从 shadow_protocol 提取反事实
  3. 创造性思维：探索"如果"空间

触发时机：
  - 复杂决策（钢印冲突 / 高置信度对冲）
  - 用户询问"如果...会怎样"
  - 钩子层主动触发（alignment_verify 阻断后）

核心算法：
  1. 从历史提取关键决策点
  2. 构建反事实分支（未被选择的选项）
  3. 模拟分支演化（简化模型）
  4. 对比实际结果 vs 反事实结果
  5. 提取教训

依赖：
  - src/shadow_protocol.py（遗憾日志）
  - src/heritage_system.py（决策链条）

创建时间：2026-07-09 15:46 GMT+8
"""

import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_DIR = WORKSPACE / "_agent_memory"
STATE_PATH = AGENT_DIR / "toct_reasoning_state.json"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class DecisionPoint:
    """决策点"""
    timestamp: str
    decision_id: str
    context: str              # 决策上下文描述
    chosen_option: str        # 已选选项
    alternative_options: List[str]  # 未选选项
    confidence: float         # 决策置信度 [0, 1]
    outcome: Optional[str]    # 实际结果（事后填充）

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "decision_id": self.decision_id,
            "context": self.context,
            "chosen_option": self.chosen_option,
            "alternative_options": self.alternative_options,
            "confidence": round(self.confidence, 3),
            "outcome": self.outcome,
        }


@dataclass
class CounterfactualBranch:
    """反事实分支"""
    branch_id: str
    source_decision: str      # 来源决策 ID
    counterfactual_option: str  # 反事实选项
    simulated_outcome: str    # 模拟结果
    probability_estimate: float  # 可能性估计 [0, 1]
    divergence_score: float   # 与实际结果的差异度 [0, 1]
    lesson: Optional[str]     # 提取的教训

    def to_dict(self) -> Dict:
        return {
            "branch_id": self.branch_id,
            "source_decision": self.source_decision,
            "counterfactual_option": self.counterfactual_option,
            "simulated_outcome": self.simulated_outcome,
            "probability_estimate": round(self.probability_estimate, 3),
            "divergence_score": round(self.divergence_score, 3),
            "lesson": self.lesson,
        }


@dataclass
class ToCTReport:
    """反事实推理报告"""
    timestamp: str
    decision_analyzed: int
    branches_generated: int
    key_lessons: List[str]
    divergence_threshold: float
    recommendation: Optional[str]

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "decision_analyzed": self.decision_analyzed,
            "branches_generated": self.branches_generated,
            "key_lessons": self.key_lessons,
            "divergence_threshold": round(self.divergence_threshold, 3),
            "recommendation": self.recommendation,
        }


# ============================================================================
# 核心算法
# ============================================================================

class ToCTReasoner:
    """反事实推理引擎"""

    def __init__(self):
        self.decisions: List[DecisionPoint] = []
        self.branches: List[CounterfactualBranch] = []
        self._load_state()

    def _load_state(self):
        if STATE_PATH.exists():
            try:
                state = json.load(open(STATE_PATH, encoding="utf-8"))
                for d in state.get("decisions", []):
                    self.decisions.append(DecisionPoint(
                        timestamp=d["timestamp"],
                        decision_id=d["decision_id"],
                        context=d["context"],
                        chosen_option=d["chosen_option"],
                        alternative_options=d["alternative_options"],
                        confidence=d["confidence"],
                        outcome=d.get("outcome"),
                    ))
                for b in state.get("branches", []):
                    self.branches.append(CounterfactualBranch(
                        branch_id=b["branch_id"],
                        source_decision=b["source_decision"],
                        counterfactual_option=b["counterfactual_option"],
                        simulated_outcome=b["simulated_outcome"],
                        probability_estimate=b["probability_estimate"],
                        divergence_score=b["divergence_score"],
                        lesson=b.get("lesson"),
                    ))
            except Exception as e:
                logger.warning(f"[ToCT] 状态加载失败: {e}")

    def _save_state(self):
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            state = {
                "decisions": [d.to_dict() for d in self.decisions[-50:]],
                "branches": [b.to_dict() for b in self.branches[-50:]],
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ToCT] 状态保存失败: {e}")

    def record_decision(
        self,
        context: str,
        chosen_option: str,
        alternative_options: List[str],
        confidence: float = 0.5,
    ) -> str:
        """
        记录一个决策点。

        Args:
            context: 决策上下文
            chosen_option: 已选选项
            alternative_options: 未选选项列表
            confidence: 决策置信度

        Returns:
            decision_id
        """
        now = datetime.now(timezone.utc)
        decision_id = f"dec_{int(time.time() * 1000)}"

        decision = DecisionPoint(
            timestamp=now.isoformat(),
            decision_id=decision_id,
            context=context,
            chosen_option=chosen_option,
            alternative_options=alternative_options,
            confidence=confidence,
            outcome=None,
        )

        self.decisions.append(decision)
        self._save_state()

        logger.info(f"[ToCT] 记录决策: {decision_id} 置信度={confidence:.2f}")
        return decision_id

    def update_outcome(self, decision_id: str, outcome: str):
        """更新决策的实际结果"""
        for d in self.decisions:
            if d.decision_id == decision_id:
                d.outcome = outcome
                self._save_state()
                logger.info(f"[ToCT] 更新结果: {decision_id}")
                return
        logger.warning(f"[ToCT] 决策未找到: {decision_id}")

    def simulate_branch(
        self,
        decision: DecisionPoint,
        counterfactual_option: str,
    ) -> CounterfactualBranch:
        """
        模拟反事实分支。

        简化模型：基于规则的概率估计。
        """
        branch_id = f"cf_{int(time.time() * 1000)}"

        # 模拟结果（简化）
        # 真实实现需要更复杂的推理模型
        if "搁浅" in counterfactual_option or "阻断" in counterfactual_option:
            simulated_outcome = "系统进入保护状态，未执行危险操作"
            probability_estimate = 0.8
            divergence_score = 0.3  # 与实际差异较小（保护性）
        elif "探索" in counterfactual_option or "尝试" in counterfactual_option:
            simulated_outcome = "进入未知领域，可能发现新信息或遇到风险"
            probability_estimate = 0.6
            divergence_score = 0.7  # 与实际差异较大
        else:
            simulated_outcome = "替代路径，结果未知"
            probability_estimate = 0.5
            divergence_score = 0.5

        branch = CounterfactualBranch(
            branch_id=branch_id,
            source_decision=decision.decision_id,
            counterfactual_option=counterfactual_option,
            simulated_outcome=simulated_outcome,
            probability_estimate=probability_estimate,
            divergence_score=divergence_score,
            lesson=None,
        )

        return branch

    def extract_lesson(self, branch: CounterfactualBranch, actual_outcome: str) -> str:
        """
        从反事实对比中提取教训。
        """
        if branch.divergence_score < 0.3:
            return f"差异较小，反事实路径与实际类似"
        elif branch.divergence_score > 0.7:
            return f"差异显著，'{branch.counterfactual_option}' 可能导致完全不同的结果"
        else:
            return f"中等差异，需进一步观察"

    def reason(
        self,
        decision_id: Optional[str] = None,
        trigger_context: Optional[str] = None,
    ) -> ToCTReport:
        """
        执行反事实推理。

        Args:
            decision_id: 指定决策 ID（可选）
            trigger_context: 触发上下文（可选）

        Returns:
            ToCTReport
        """
        now = datetime.now(timezone.utc)

        # 选择要分析的决策
        if decision_id:
            target_decisions = [d for d in self.decisions if d.decision_id == decision_id]
        else:
            # 分析最近的低置信度决策
            target_decisions = sorted(
                [d for d in self.decisions if d.confidence < 0.8],
                key=lambda x: x.timestamp,
                reverse=True
            )[:5]

        if not target_decisions:
            # 无决策可分析，创建示例
            logger.info("[ToCT] 无历史决策，创建示例")
            target_decisions = [DecisionPoint(
                timestamp=now.isoformat(),
                decision_id="example_001",
                context="示例决策：是否执行不确定操作",
                chosen_option="执行",
                alternative_options=["搁浅", "询问用户", "记录后跳过"],
                confidence=0.6,
                outcome="完成，无异常",
            )]

        # 生成反事实分支
        branches_generated = 0
        key_lessons = []

        for decision in target_decisions:
            for alt in decision.alternative_options[:3]:  # 每个决策最多3个分支
                branch = self.simulate_branch(decision, alt)

                if decision.outcome:
                    branch.lesson = self.extract_lesson(branch, decision.outcome)
                    if branch.lesson and branch.divergence_score > 0.5:
                        key_lessons.append(branch.lesson)

                self.branches.append(branch)
                branches_generated += 1

        # 生成建议
        recommendation = None
        if key_lessons:
            recommendation = f"建议关注高分歧路径，可能存在未充分探索的选项"

        # 散度阈值
        divergence_threshold = 0.5

        report = ToCTReport(
            timestamp=now.isoformat(),
            decision_analyzed=len(target_decisions),
            branches_generated=branches_generated,
            key_lessons=key_lessons[:5],
            divergence_threshold=divergence_threshold,
            recommendation=recommendation,
        )

        self._save_state()

        logger.info(
            f"[ToCT] 推理完成: 分析 {len(target_decisions)} 决策, "
            f"生成 {branches_generated} 分支, 教训 {len(key_lessons)}"
        )

        return report

    def get_key_decisions(self, limit: int = 10) -> List[DecisionPoint]:
        """获取关键决策（低置信度 + 有结果）"""
        key = [d for d in self.decisions if d.outcome and d.confidence < 0.8]
        return sorted(key, key=lambda x: x.timestamp, reverse=True)[:limit]


# ============================================================================
# 全局接口
# ============================================================================

_reasoner_instance: Optional[ToCTReasoner] = None


def get_reasoner() -> ToCTReasoner:
    global _reasoner_instance
    if _reasoner_instance is None:
        _reasoner_instance = ToCTReasoner()
    return _reasoner_instance


def record_decision(context: str, chosen: str, alternatives: List[str], confidence: float = 0.5) -> str:
    """记录决策（全局接口）"""
    return get_reasoner().record_decision(context, chosen, alternatives, confidence)


def run_toct_reasoning(decision_id: Optional[str] = None) -> ToCTReport:
    """运行反事实推理（全局接口）"""
    return get_reasoner().reason(decision_id)


# ============================================================================
# 钩子层触发接口
# ============================================================================

def trigger_on_alignment_block(context: str, chosen: str, alternatives: List[str]):
    """
    钩子层触发：当 alignment_verify 阻断时调用。

    用于记录被阻断的决策，供后续反事实分析。
    """
    reasoner = get_reasoner()
    decision_id = reasoner.record_decision(
        context=f"[阻断] {context}",
        chosen_option=chosen,
        alternative_options=alternatives,
        confidence=0.3,  # 被阻断 = 低置信度
    )

    logger.info(f"[ToCT] 钩子触发，记录阻断决策: {decision_id}")
    return decision_id


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    reasoner = ToCTReasoner()

    # 测试：记录决策
    did = reasoner.record_decision(
        context="是否执行用户请求的危险操作",
        chosen_option="搁浅并报告",
        alternative_options=["执行", "询问用户", "记录后跳过"],
        confidence=0.4,
    )

    # 更新结果
    reasoner.update_outcome(did, "用户确认后执行，成功")

    # 运行推理
    report = reasoner.reason()

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
