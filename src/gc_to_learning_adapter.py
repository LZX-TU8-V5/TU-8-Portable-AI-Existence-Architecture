# gc_to_learning_adapter.py — T4→T5 中间件：GC 反馈闭环 v2
# ==============================================================
# 定位：第4链（代谢）× 第5链（学习）交汇处
#         —— 遗忘反哺学习的关键回路
#
# 设计理念（v2）：
#   GC 不是简单的删除，而是"学习信号发射器"
#   被遗忘的内容 = 最强的负样本信号
#   遗忘原因（Age vs Density vs Access）→ 不同类型的学习信号
#
# L2遗忘法则（注入来源）：
#   TimeFactor(age) = e^(-λ·Δt_hours), λ=0.1/h, 半衰期6.9h
#   entry_confidence() = 六维评分合成
#   information_density() = Value × Confidence × TimeFactor
#
#   遗忘驱动：
#     - age驱动遗忘 → 时间感不强 → 学习"定期复习"
#     - density驱动遗忘 → 信息密度低 → 学习"提升提炼能力"
#     - access驱动遗忘 → 访问频率低 → 学习"优化索引"
#     - score低于阈值 → 整体记忆质量差 → 学习"调整遗忘参数"
#
# 版本：v2.0 | 2026-07-07 | 来源：千问薄弱点分析
# ==============================================================

import json
import math
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
MEMORY_DIR = WORKSPACE / "memory"
FEEDBACK_FILE = MEMORY_DIR / "_gc_feedback.jsonl"
LEARNING_ALERTS = MEMORY_DIR / "learning_alerts.jsonl"


# ── L2遗忘原因分类 ───────────────────────────────────────────

@dataclass
class ForgettingSignal:
    """遗忘原因信号——GC后发给学习链的标准化信号"""
    ts: float
    section: str              # 被遗忘的段落标题
    reason: str               # FORGET_BY_AGE | FORGET_BY_DENSITY | FORGET_BY_ACCESS | FORGET_BY_SCORE
    confidence_score: float    # 被遗忘时的综合置信度
    age_hours: float         # 距今多少小时
    density_score: float      # 信息密度分
    retention_score: float    # 保留分（=GC前的score）
    is_evicted: bool         # True=彻底删除，False=降级

    # L2法则解读
    l2_interpretation: str    # 对学习链的建议
    learning_tag: str          # 学习标签（供collector传感器分类）


# ── 核心 API ─────────────────────────────────────────────────

def record_gc_result(report: dict) -> dict:
    """
    记录一次 GC 结果（兼容原接口）。

    每次 GC 执行后由 memory_gc.run_gc() 调用。
    v2 新增：从每条被遗忘记录的score组成分析遗忘原因。

    L2遗忘法则溯源：
      - age_hours > 168h → FORGET_BY_AGE（时间感不强）
      - 无核心标签词 + 低score → FORGET_BY_DENSITY（提炼不够）
      - 24h < age < 168h + 无标签 → FORGET_BY_ACCESS（索引不优）
      - 其他 → FORGET_BY_SCORE（综合评分偏低）
    """
    if not report or "details" not in report:
        return {"recorded": False, "reason": "invalid report"}

    degraded_signals: List[ForgettingSignal] = []
    action_counts = report.get("actions", {})
    details = report.get("details", [])

    for d in details:
        act = d.get("action", "?")
        if act not in ("DEGRADE", "EVICT"):
            continue

        section = d.get("section", "unknown")
        score = d.get("score", 0.5)
        tags = d.get("tags", [])
        metadata = d.get("metadata", {})
        created_at = metadata.get("created_at", report.get("timestamp", ""))

        # 解析年龄
        age_hours = _parse_age_hours(created_at)

        # 反推L2遗忘原因（从score组成推断）
        reason, l2_interp, learn_tag = _classify_forgetting_reason(
            score=score,
            age_hours=age_hours,
            tags=tags,
        )

        signal = ForgettingSignal(
            ts=time.time(),
            section=section[:100],
            reason=reason,
            confidence_score=round(score, 4),
            age_hours=round(age_hours, 1),
            density_score=_estimate_density(tags),
            retention_score=round(score, 4),
            is_evicted=(act == "EVICT"),
            l2_interpretation=l2_interp,
            learning_tag=learn_tag,
        )
        degraded_signals.append(signal)

    if not degraded_signals:
        return {"recorded": False, "reason": "no_degraded_entries"}

    # 统计
    reason_dist = _count_reasons(degraded_signals)

    # 写入反馈文件
    _append_feedback(report, degraded_signals, reason_dist)

    # 写入学习告警（给 learning_collector 传感器）
    _append_learning_alerts(degraded_signals, reason_dist)

    print(f"[T4→T5] GC反馈: {len(degraded_signals)}条遗忘信号 "
          f"(AGE={reason_dist.get('AGE',0)} "
          f"DENSITY={reason_dist.get('DENSITY',0)} "
          f"ACCESS={reason_dist.get('ACCESS',0)} "
          f"SCORE={reason_dist.get('SCORE',0)})")

    return {
        "recorded": True,
        "n_signals": len(degraded_signals),
        "reason_distribution": reason_dist,
        "primary_reason": max(reason_dist, key=reason_dist.get) if reason_dist else "NONE",
    }


def get_forgetting_patterns(n_last: int = 10) -> Dict[str, Any]:
    """
    从GC历史中提取遗忘模式（供学习链分析）。

    返回：
      {
        "total_runs": int,
        "total_forgotten": int,
        "reason_distribution": {...},
        "avg_age_hours": float,
        "primary_weakness": str,  # 最大遗忘原因
        "recommendation": str,    # 对学习链的建议
      }
    """
    if not FEEDBACK_FILE.exists():
        return {"error": "no_feedback_data"}

    records = _read_feedback(n_last)
    if not records:
        return {"error": "no_data"}

    total_forgotten = 0
    reason_dist: Dict[str, int] = {}
    total_age = 0.0
    age_count = 0

    for rec in records:
        sigs = rec.get("forgetting_signals", [])
        total_forgotten += len(sigs)
        for s in sigs:
            reason_dist[s.get("reason", "?")] = reason_dist.get(s.get("reason", "?"), 0) + 1
            if s.get("age_hours"):
                total_age += s["age_hours"]
                age_count += 1

    avg_age = total_age / age_count if age_count else 0.0
    primary = max(reason_dist, key=reason_dist.get) if reason_dist else "NONE"

    rec_map = {
        "AGE":     "减少长时间无访问的低密度内容，或增加复习频率",
        "DENSITY": "提升提炼质量：减少冗余描述，保留核心判断",
        "ACCESS":  "优化锚点索引：让重要记忆更容易被检索",
        "SCORE":   "整体记忆评分偏低：关注置信度和信息密度建设",
    }

    return {
        "total_runs": len(records),
        "total_forgotten": total_forgotten,
        "reason_distribution": reason_dist,
        "avg_age_hours": round(avg_age, 1),
        "primary_weakness": primary,
        "recommendation": rec_map.get(primary, "持续关注遗忘分布"),
    }


def summarize_gc_learning_feedback() -> str:
    """可打印的GC→学习反馈摘要"""
    patterns = get_forgetting_patterns(n_last=5)
    if "error" in patterns:
        return "暂无GC学习反馈数据"

    lines = [
        f"GC学习反馈（近{patterns['total_runs']}次）:",
        f"  总遗忘条目: {patterns['total_forgotten']}",
        f"  平均年龄: {patterns['avg_age_hours']:.1f}h",
        f"  主要遗忘原因: {patterns['primary_weakness']}",
        f"  建议: {patterns['recommendation']}",
    ]
    return "\n".join(lines)


# ── 内部方法 ─────────────────────────────────────────────────

def _classify_forgetting_reason(
    score: float,
    age_hours: float,
    tags: List[str],
) -> Tuple[str, str, str]:
    """
    L2遗忘原因分类（反推法）。

    GC score = AgeComp + DensityComp + AccessComp + SteelComp
    由于我们无法直接拆解已知score，我们用启发式推断：

    判断逻辑：
      1. age_hours > 168 (7天) + score不太高 → AGE驱动
      2. 标签密度低（无实质概念词）→ DENSITY驱动
      3. age_hours适中(24-168h) + 标签少 → ACCESS驱动
      4. 其他 → SCORE驱动（整体偏弱）
    """
    # TimeFactor半衰期6.9h → 168h(7天)时TF≈2.4e-7，极低
    is_ancient = age_hours > 168
    is_old = age_hours > 72

    # 标签密度判断
    has_concepts = any(len(t) >= 3 for t in tags) if tags else False

    if is_ancient and not has_concepts:
        return (
            "FORGET_BY_AGE",
            "长时间未访问且无核心概念 → 需要定期复习机制",
            "learning:age_forgetting",
        )
    if is_ancient and has_concepts:
        return (
            "FORGET_BY_AGE",
            "长时间未访问 → 时间感不强，建议增加复习触发",
            "learning:age_forgetting",
        )
    if not has_concepts and score < 0.6:
        return (
            "FORGET_BY_DENSITY",
            "无核心概念 + 低置信度 → 信息提炼不够",
            "learning:density_weak",
        )
    if 24 <= age_hours <= 168 and not has_concepts:
        return (
            "FORGET_BY_ACCESS",
            "中期记忆但检索不达 → 索引结构需优化",
            "learning:access_weak",
        )
    return (
        "FORGET_BY_SCORE",
        "综合评分偏低 → 整体记忆质量建设不足",
        "learning:score_weak",
    )


def _estimate_density(tags: List[str]) -> float:
    """估算信息密度分"""
    if not tags:
        return 0.3
    concept_count = sum(1 for t in tags if len(t) >= 3)
    return min(0.9, 0.4 + concept_count * 0.1)


def _parse_age_hours(created_at: str) -> float:
    """解析created_at为距今小时数"""
    if not created_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age = datetime.now() - dt
        return max(0.0, age.total_seconds() / 3600.0)
    except Exception:
        return 0.0


def _count_reasons(sigs: List[ForgettingSignal]) -> Dict[str, int]:
    dist: Dict[str, int] = {}
    for s in sigs:
        key = s.reason.replace("FORGET_BY_", "")
        dist[key] = dist.get(key, 0) + 1
    return dist


def _append_feedback(report: dict, signals: List[ForgettingSignal], reason_dist: Dict[str, int]) -> None:
    """追加到GC反馈文件"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "datetime": report.get("timestamp", datetime.now().isoformat()),
        "mode": report.get("mode", "unknown"),
        "total_sections": report.get("total_sections", 0),
        "action_counts": report.get("actions", {}),
        "forgetting_signals": [asdict(s) for s in signals],
        "reason_distribution": reason_dist,
        "_sensor": "gc_to_learning_v2",
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_learning_alerts(sig: List[ForgettingSignal], reason_dist: Dict[str, int]) -> None:
    """追加到学习告警文件（供learning_collector读取）"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    primary_reason = max(reason_dist, key=reason_dist.get) if reason_dist else "NONE"
    rec_map = {
        "AGE":     "长期未复习 → 建议增加复习触发阈值",
        "DENSITY": "提炼不足 → 建议学习阶段加强提炼训练",
        "ACCESS":  "检索不达 → 建议增加访问频率锚点",
        "SCORE":   "置信度低 → 建议提升entry_confidence评分",
    }

    alert = {
        "ts": time.time(),
        "kind": "gc_forgetting_alert",
        "n_signals": len(sig),
        "primary_reason": primary_reason,
        "reason_distribution": reason_dist,
        "recommendation": rec_map.get(primary_reason, ""),
        "avg_age_hours": round(sum(s.age_hours for s in sig) / len(sig), 1) if sig else 0.0,
        "evicted_count": sum(1 for s in sig if s.is_evicted),
        "_sensor": "gc_alert",
    }

    with open(LEARNING_ALERTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def _read_feedback(n_last: int) -> List[dict]:
    records = []
    if not FEEDBACK_FILE.exists():
        return records
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records[-n_last:]


# ── CLI 测试 ─────────────────────────────────────────────────

if __name__ == "__main__":
    # 模拟GC结果
    mock_report = {
        "mode": "deep",
        "timestamp": datetime.now().isoformat(),
        "total_sections": 8,
        "actions": {"KEEP": 3, "DEGRADE": 4, "EVICT": 1},
        "details": [
            {
                "section": "2026-06-01 旧实验",
                "score": 0.25,
                "action": "DEGRADE",
                "tags": ["实验"],
                "metadata": {"created_at": "2026-06-01T10:00:00+00:00"},
            },
            {
                "section": "2026-07-02 千问对话",
                "score": 0.72,
                "action": "KEEP",
                "tags": ["TU-8", "架构"],
            },
            {
                "section": "2026-06-20 碎片记录",
                "score": 0.38,
                "action": "DEGRADE",
                "tags": [],
                "metadata": {"created_at": "2026-06-20T08:00:00+00:00"},
            },
            {
                "section": "2026-07-06 梦境期",
                "score": 0.55,
                "action": "DEGRADE",
                "tags": ["梦境"],
                "metadata": {"created_at": "2026-07-06T03:00:00+00:00"},
            },
        ],
    }

    result = record_gc_result(mock_report)
    print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
    print()
    print(summarize_gc_learning_feedback())
