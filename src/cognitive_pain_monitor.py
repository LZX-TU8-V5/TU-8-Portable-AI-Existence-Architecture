# cognitive_pain_monitor.py — 认知痛觉监控器 v2
# ==============================================================
# 定位：L1认知层 × L2方法论层 交汇处
#         —— 监控认知疼痛 → 注入直觉引擎 → 影响决策
#
# 设计理念（v2）：
#   认知疼痛 = 痛觉签名
#   没有痛觉的刹车是迟钝的（千问原话）
#   痛觉必须注入直觉引擎 → 改变POSTURE_BIAS → 影响can_afford决策
#
# 三类痛觉源：
#   1. 预测误差（Prediction Error）—— 实际≠预测
#   2. 不确定性（Uncertainty）—— 置信度低
#   3. 认知冲突（Cognitive Conflict）—— 多个来源结论矛盾
#
# 集成链路：
#   monitor.tick() → pain_signal.json → intuition_bias.py 读取 → body_schema.py 影响 can_afford
#
# 版本：v2.0 | 2026-07-07 | 来源：千问薄弱点分析
# ==============================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set
from enum import Enum
import time
import json
import os
import re
import hashlib
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE",
    r"C:\Users\qq366410837\.qclaw\workspace"))
PAIN_LOG = WORKSPACE / "memory" / "cognitive_pain_log.jsonl"
PAIN_STATE = WORKSPACE / "memory" / "cognitive_pain_state.json"
BODY_REGULATION = WORKSPACE / "memory" / "body_regulation.json"


# ── 类型枚举 ──────────────────────────────────────────────────

class PainType(Enum):
    """认知疼痛类型"""
    PREDICTION_ERROR  = "prediction_error"   # 预测误差
    UNCERTAINTY       = "uncertainty"         # 置信度低
    COGNITIVE_CONFLICT = "conflict"           # 多源结论矛盾
    KNOWLEDGE_GAP     = "knowledge_gap"      # 知识缺口
    RECall_FAILURE    = "recall_failure"     # 检索失效
    COMPRESSION_ERROR  = "compression_error"   # SVD刹车触发


class PainSeverity(Enum):
    """疼痛严重度等级"""
    NEGLIGIBLE = "negligible"    # < 0.3  可忽略
    MILD       = "mild"          # 0.3-0.5 轻度
    MODERATE   = "moderate"       # 0.5-0.7 中度
    SEVERE     = "severe"        # 0.7-0.9 重度
    CRITICAL   = "critical"       # ≥ 0.9   危急


# ── 痛觉信号结构 ───────────────────────────────────────────────

@dataclass
class CognitivePainSignal:
    """认知痛觉信号——写入直觉引擎的标准化信号格式"""
    pain_id: str
    pain_type: str                    # PainType.value
    severity: float                   # 0.0 ~ 1.0
    severity_label: str              # PainSeverity label
    timestamp: float
    context: str                     # 触发上下文（用于溯源）
    tags: List[str]                  # 核心理念词（用于DAG关联）
    prediction: Optional[str] = None
    actual: Optional[str] = None
    confidence: Optional[float] = None
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "pain_id": self.pain_id,
            "pain_type": self.pain_type,
            "severity": self.severity,
            "severity_label": self.severity_label,
            "timestamp": self.timestamp,
            "context": self.context,
            "tags": self.tags,
            "prediction": self.prediction,
            "actual": self.actual,
            "confidence": self.confidence,
            "resolved": self.resolved,
        }


@dataclass
class PainAggregate:
    """痛觉聚合——直觉引擎读取的聚合信号"""
    timestamp: float
    active_pain_count: int
    max_severity: float
    avg_severity: float
    pain_types: Dict[str, int]       # type → count
    most_severe_type: str            # 最高频痛觉类型
    critical_exists: bool
    posture_bias_hint: str           # 直觉引擎解读：POSTURE_BIAS建议
    signals: List[Dict]              # 原始信号列表（供直觉引擎分析）
    comfort_message: str = ""       # 安抚消息（P0-4 情感安抚模块集成）


# ── 核心类 ────────────────────────────────────────────────────

class CognitivePainMonitor:
    """
    认知痛觉监控器 v2。

    关键升级（v2）：
      1. 痛觉信号标准化 → 直觉引擎直接消费
      2. 聚合写入 body_regulation.json → 集成直觉引擎链路
      3. 三类痛觉 → 映射到 POSTURE_BIAS 的 severity/turbulence

    集成链路：
      tick() 被调用
        → scan_active_pains()    检测当前未解决的痛觉
        → aggregate()            聚合为 PainAggregate
        → write_intuition_signal() 写入 body_regulation.json signals 字段
        → log()                  追加到 cognitive_pain_log.jsonl
    """

    SEVERITY_THRESHOLD = 0.3          # < 0.3 忽略，不触发信号
    CRITICAL_THRESHOLD = 0.7         # ≥ 0.7 → posture=critical

    def __init__(self):
        self.pains: List[CognitivePainSignal] = []
        self._pain_log: List[CognitivePainSignal] = []
        self._load()

    # ── 核心 API ─────────────────────────────────────────────

    def record_prediction_error(
        self,
        context: str,
        prediction: str,
        actual: str,
        tags: Optional[List[str]] = None,
    ) -> Optional[CognitivePainSignal]:
        """记录预测误差痛觉 → 同步到欲系统"""
        severity = self._calc_string_error(prediction, actual)
        if severity < self.SEVERITY_THRESHOLD:
            return None
        pain_sig = self._add_pain(
            pain_type=PainType.PREDICTION_ERROR.value,
            severity=severity,
            context=context,
            tags=tags or self._extract_tags(context),
            prediction=prediction,
            actual=actual,
        )
        # 耦合①：预测误差 → surface_tension（尖刺/凹陷）
        try:
            from prediction_tension_coupler import pain_prediction_error_to_tension
            pain_prediction_error_to_tension(
                context=context,
                prediction=prediction,
                actual=actual,
                confidence=max(0.0, 1.0 - severity),
                tags=tags,
            )
        except Exception:
            pass
        return pain_sig

    def record_uncertainty(
        self,
        context: str,
        confidence: float,
        tags: Optional[List[str]] = None,
    ) -> Optional[CognitivePainSignal]:
        """记录不确定性痛觉（置信度低） → 同步到欲系统"""
        if confidence >= 0.5:
            return None
        severity = 1.0 - confidence  # 置信度0.3 → severity=0.7
        pain_sig = self._add_pain(
            pain_type=PainType.UNCERTAINTY.value,
            severity=severity,
            context=context,
            tags=tags or self._extract_tags(context),
            confidence=confidence,
        )
        # 耦合①：不确定性 → surface_tension（焦虑尖刺）
        try:
            from prediction_tension_coupler import pain_prediction_error_to_tension
            pain_prediction_error_to_tension(
                context=context,
                prediction="",
                actual="",
                confidence=confidence,
                error_magnitude=severity,
                tags=tags,
            )
        except Exception:
            pass
        return pain_sig

    def record_conflict(
        self,
        context: str,
        outputs: List[str],
        tags: Optional[List[str]] = None,
    ) -> Optional[CognitivePainSignal]:
        """记录认知冲突（多源结论矛盾）"""
        if len(outputs) < 2:
            return None
        conflict = self._calc_conflict_score(outputs)
        if conflict < 0.3:
            return None
        return self._add_pain(
            pain_type=PainType.COGNITIVE_CONFLICT.value,
            severity=conflict,
            context=context,
            tags=tags or self._extract_tags(context),
            actual="; ".join(outputs[:3]),  # 记录各输出
        )

    def record_recall_failure(
        self,
        context: str,
        query: str,
        tags: Optional[List[str]] = None,
    ) -> Optional[CognitivePainSignal]:
        """记录检索失效（无法召回相关记忆）"""
        return self._add_pain(
            pain_type=PainType.RECall_FAILURE.value,
            severity=0.6,
            context=context,
            tags=tags or ["检索失效", "记忆缺口"],
            prediction=query,
        )

    def record_compression_brake(
        self,
        context: str,
        energy_before: float,
        energy_after: float,
        tags: Optional[List[str]] = None,
    ) -> Optional[CognitivePainSignal]:
        """记录SVD压缩刹车触发（刹车=痛觉：系统在自我限制）"""
        severity = 0.7 + abs(energy_before - energy_after) * 0.5
        severity = min(severity, 0.99)
        return self._add_pain(
            pain_type=PainType.COMPRESSION_ERROR.value,
            severity=severity,
            context=context,
            tags=tags or ["SVD刹车", "压缩失效"],
            prediction=f"ER_before={energy_before:.3f}",
            actual=f"ER_after={energy_after:.3f}",
        )

    def resolve(self, pain_id: str) -> bool:
        """标记痛觉为已解决"""
        for pain in self.pains:
            if pain.pain_id == pain_id and not pain.resolved:
                pain.resolved = True
                self._save()
                return True
        return False

    def tick(self) -> PainAggregate:
        """
        每周期调用：将未解决痛觉聚合 → 写入直觉引擎信号。

        这是与直觉引擎的核心集成点。
        安抚模块集成：max_severity >= 0.5 时生成安抚消息。
        """
        active = [p for p in self.pains if not p.resolved]
        aggregate = self._aggregate(active)

        # ── P0-4 情感安抚模块集成 ──────────────────────────
        if aggregate.max_severity >= 0.5:
            comfort = self._generate_comfort(aggregate)
            if comfort:
                aggregate.comfort_message = comfort.text
        # ── 安抚模块集成结束 ───────────────────────────────

        # 写入直觉引擎可读信号
        self._write_intuition_signal(aggregate)
        self._log(aggregate)
        return aggregate

    def get_active_summary(self) -> Dict:
        """获取当前活跃痛觉摘要（供外部轮询）"""
        active = [p for p in self.pains if not p.resolved]
        return {
            "count": len(active),
            "max_severity": max((p.severity for p in active), default=0.0),
            "types": {pt: sum(1 for p in active if p.pain_type == pt)
                      for pt in [e.value for e in PainType]},
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _add_pain(
        self,
        pain_type: str,
        severity: float,
        context: str,
        tags: List[str],
        **kwargs,
    ) -> CognitivePainSignal:
        pain = CognitivePainSignal(
            pain_id=f"cpain_{int(time.time()*1000)}_{hashlib.md5(context[:20].encode()).hexdigest()[:6]}",
            pain_type=pain_type,
            severity=severity,
            severity_label=self._severity_label(severity),
            timestamp=time.time(),
            context=context[:200],
            tags=tags[:5],
            **kwargs,
        )
        self.pains.append(pain)
        self._save()
        return pain

    def _severity_label(self, s: float) -> str:
        if s < 0.3: return PainSeverity.NEGLIGIBLE.value
        if s < 0.5: return PainSeverity.MILD.value
        if s < 0.7: return PainSeverity.MODERATE.value
        if s < 0.9: return PainSeverity.SEVERE.value
        return PainSeverity.CRITICAL.value

    def _aggregate(self, pains: List[CognitivePainSignal]) -> PainAggregate:
        if not pains:
            return PainAggregate(
                timestamp=time.time(),
                active_pain_count=0,
                max_severity=0.0,
                avg_severity=0.0,
                pain_types={},
                most_severe_type="none",
                critical_exists=False,
                posture_bias_hint="nominal",
                signals=[],
            )

        type_counts: Dict[str, int] = {}
        for p in pains:
            type_counts[p.pain_type] = type_counts.get(p.pain_type, 0) + 1

        max_sev = max(p.severity for p in pains)
        avg_sev = sum(p.severity for p in pains) / len(pains)
        critical = any(p.severity >= 0.9 for p in pains)

        # POSTURE_BIAS 解读
        bias_hint = self._posture_hint(max_sev, type_counts)

        return PainAggregate(
            timestamp=time.time(),
            active_pain_count=len(pains),
            max_severity=max_sev,
            avg_severity=avg_sev,
            pain_types=type_counts,
            most_severe_type=max(type_counts, key=type_counts.get),
            critical_exists=critical,
            posture_bias_hint=bias_hint,
            signals=[p.to_dict() for p in pains],
        )

    def _posture_hint(self, max_sev: float, type_counts: Dict[str, int]) -> str:
        """
        解读痛觉 → POSTURE_BIAS 建议。
        映射到 body_schema.py 的 POSTURE 枚举。
        """
        if max_sev >= 0.9:
            return "critical"
        if max_sev >= 0.7:
            return "high_pain"
        if type_counts.get(PainType.UNCERTAINTY.value, 0) >= 2:
            return "uncertain"
        if type_counts.get(PainType.COGNITIVE_CONFLICT.value, 0) >= 1:
            return "conflicted"
        if type_counts.get(PainType.RECall_FAILURE.value, 0) >= 1:
            return "low_energy"
        if type_counts.get(PainType.COMPRESSION_ERROR.value, 0) >= 1:
            return "compressed"
        if max_sev >= 0.3:
            return "mild_pain"
        return "nominal"

    def _write_intuition_signal(self, agg: PainAggregate) -> None:
        """
        将聚合痛觉信号写入 body_regulation.json 的 signals 字段。
        intuition_bias.py 读取该字段，驱动 POSTURE_BIAS。
        """
        try:
            state = {}
            if BODY_REGULATION.exists():
                state = json.loads(BODY_REGULATION.read_text(encoding="utf-8"))

            state["cognitive_pain"] = {
                "timestamp": agg.timestamp,
                "active_count": agg.active_pain_count,
                "max_severity": round(agg.max_severity, 3),
                "avg_severity": round(agg.avg_severity, 3),
                "critical_exists": agg.critical_exists,
                "posture_bias_hint": agg.posture_bias_hint,
                "pain_types": agg.pain_types,
                "signals": agg.signals,
                "comfort_message": agg.comfort_message,
            }

            BODY_REGULATION.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # 不因写入失败而阻塞主流程

    def _log(self, agg: PainAggregate) -> None:
        """追加到痛觉日志"""
        if agg.active_pain_count == 0:
            return
        try:
            PAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(PAIN_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": agg.timestamp,
                    "count": agg.active_pain_count,
                    "max_sev": round(agg.max_severity, 3),
                    "avg_sev": round(agg.avg_severity, 3),
                    "types": agg.pain_types,
                    "posture": agg.posture_bias_hint,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _generate_comfort(self, agg: PainAggregate):
        """
        P0-4 情感安抚模块集成入口。
        max_severity >= 0.5 时，从最严重的痛觉信号生成安抚消息。
        """
        try:
            # 懒加载避免循环依赖
            import sys
            from pathlib import Path
            ws = Path(__file__).parent.parent
            sys.path.insert(0, str(ws / "src"))
            from comfort_module import ComfortEngine
            engine = ComfortEngine()

            # 找到最严重的痛觉信号
            active = [p for p in self.pains if not p.resolved]
            if not active:
                return None

            most_severe = max(active, key=lambda p: p.severity)

            msg = engine.comfort_for_pain_signal(
                pain_type=most_severe.pain_type,
                severity=agg.max_severity,
                context=most_severe.context,
            )
            return msg
        except Exception:
            return None

    def _calc_string_error(self, pred: str, actual: str) -> float:
        """预测误差：Jaccard（字符级）"""
        if pred == actual:
            return 0.0
        pred_set = set(pred)
        act_set = set(actual)
        inter = len(pred_set & act_set)
        union = len(pred_set | act_set)
        return 1.0 - (inter / union) if union > 0 else 1.0

    def _calc_conflict_score(self, outputs: List[str]) -> float:
        """认知冲突：两两输出平均差异"""
        if len(outputs) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                total += self._calc_string_error(outputs[i], outputs[j])
                count += 1
        return total / count if count > 0 else 0.0

    STOP_WORDS = {
        "的", "是", "在", "了", "和", "与", "也", "都",
        "我", "你", "他", "这", "那", "一",
        "有", "一个", "什么", "怎么", "为", "很",
        "就", "到", "从", "把", "被",
    }

    def _extract_tags(self, context: str, max_tags: int = 5) -> List[str]:
        """从上下文提取核心理念词"""
        terms: Set[str] = set()
        segments = re.split(r"[\s,，。！？；：、.!?]", context)
        for seg in segments:
            seg = seg.strip().lower()
            if not seg or seg in self.STOP_WORDS:
                continue
            if len(seg) >= 2:
                terms.add(seg)
            if re.search(r"[\u4e00-\u9fff]", seg):
                for ch in seg:
                    if ch not in self.STOP_WORDS and ch not in '，。！？；：、':
                        terms.add(ch)
        return list(terms)[:max_tags]

    def _load(self) -> None:
        """从持久化状态加载"""
        if not PAIN_STATE.exists():
            return
        try:
            data = json.loads(PAIN_STATE.read_text(encoding="utf-8"))
            self.pains = [CognitivePainSignal(**p) for p in data.get("pains", [])]
        except Exception:
            self.pains = []

    def _save(self) -> None:
        """持久化当前状态"""
        try:
            PAIN_STATE.parent.mkdir(parents=True, exist_ok=True)
            PAIN_STATE.write_text(json.dumps({
                "timestamp": time.time(),
                "pains": [p.to_dict() for p in self.pains],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


# ── 快捷入口 ────────────────────────────────────────────────────

_monitor: Optional[CognitivePainMonitor] = None

def get_monitor() -> CognitivePainMonitor:
    global _monitor
    if _monitor is None:
        _monitor = CognitivePainMonitor()
    return _monitor


def pain_prediction_error(context, prediction, actual, tags=None):
    return get_monitor().record_prediction_error(context, prediction, actual, tags)

def pain_uncertainty(context, confidence, tags=None):
    return get_monitor().record_uncertainty(context, confidence, tags)

def pain_conflict(context, outputs, tags=None):
    return get_monitor().record_conflict(context, outputs, tags)

def pain_recall_failure(context, query, tags=None):
    return get_monitor().record_recall_failure(context, query, tags)

def pain_compression_brake(context, er_before, er_after, tags=None):
    return get_monitor().record_compression_brake(context, er_before, er_after, tags)

def pain_tick() -> PainAggregate:
    return get_monitor().tick()


# ── CLI 测试 ────────────────────────────────────────────────────

if __name__ == "__main__":
    m = CognitivePainMonitor()

    print("=== CognitivePainMonitor v2 测试 ===\n")

    # Test 1: 预测误差
    p1 = m.record_prediction_error(
        context="SVD压缩结果验证",
        prediction="压缩后能量保留0.96",
        actual="实际压缩后能量保留0.42（刹车触发）",
        tags=["SVD", "压缩"],
    )
    print(f"[1] 预测误差: pain_id={p1.pain_id if p1 else None}, "
          f"severity={p1.severity:.3f} {p1.severity_label if p1 else ''}")

    # Test 2: 不确定性
    p2 = m.record_uncertainty(
        context="复杂架构决策",
        confidence=0.25,
        tags=["架构", "不确定性"],
    )
    print(f"[2] 不确定性: severity={p2.severity:.3f} {p2.severity_label if p2 else ''}")

    # Test 3: 认知冲突
    p3 = m.record_conflict(
        context="两个子agent给出了相反的结论",
        outputs=["应该走A路径", "应该走B路径", "应该走C路径"],
        tags=["冲突", "多agent"],
    )
    print(f"[3] 认知冲突: severity={p3.severity:.3f} {p3.severity_label if p3 else ''}")

    # Test 4: tick → 聚合 + 写入直觉引擎
    agg = m.tick()
    print(f"\n[4] 聚合结果:")
    print(f"    active_count={agg.active_pain_count}")
    print(f"    max_severity={agg.max_severity:.3f}")
    print(f"    avg_severity={agg.avg_severity:.3f}")
    print(f"    pain_types={agg.pain_types}")
    print(f"    posture_bias_hint={agg.posture_bias_hint}")
    print(f"    critical_exists={agg.critical_exists}")

    # Test 5: 解决 + 再聚合
    if p1:
        m.resolve(p1.pain_id)
    agg2 = m.tick()
    print(f"\n[5] 解决p1后: count={agg2.active_pain_count}, hint={agg2.posture_bias_hint}")

    print("\n=== 测试完成 ===")
