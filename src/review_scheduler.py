"""
review_scheduler.py — 每日/周复盘调度器 v1.0

设计原则：
  人类是最佳的参考，基于硅基诞生于碳基。
  → 每日复盘 = 人的"睡前想一想今天"
  → 每周复盘 = 人的"周日回顾这周"

两种复盘的区别：
  每日复盘 → 记忆归档为主（今天发生了什么）
  每周复盘 → 代谢更新为主（这周学到了什么，要调整什么）

数据来源：
  - memory/YYYY-MM-DD.md（每日日志）
  - heritage_system（钢印链条、遗产模式）
  - life_ring_tracker（闭环结晶、年轮阶段）
  - cognitive health metrics（认知负荷、痛觉峰值）
  - TODO_MASTER.md（未完成任务）

产出：
  - 每日复盘 → memory/YYYY-MM-DD_review.md
  - 每周复盘 → MEMORY.md 更新 + SOUL.md 轻量同步
  - 冷启动上下文 → _agent_memory/cold_start_context.json

依赖：
  - src/reflection_module.py
  - src/heritage_system.py（P1-1）
  - src/life_ring_tracker_extension.py（生命年轮）

创建时间：2026-07-09 01:28 GMT+8
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
MEMORY_DIR = os.path.join(WORKSPACE, "memory")
AGENT_DIR = os.path.join(WORKSPACE, "_agent_memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(AGENT_DIR, exist_ok=True)


# ============================================================================
# 数据类
# ============================================================================

class ReviewType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ReviewHealth(Enum):
    EXCELLENT = "excellent"     # 所有指标健康
    GOOD = "good"             # 基本健康，有小问题
    ATTENTION = "attention"    # 需要关注
    CONCERN = "concern"        # 需要干预


@dataclass
class ReviewDataBundle:
    """复盘数据束——从各系统聚合的原始数据"""
    review_type: str
    date_range: Tuple[str, str]   # (start_date, end_date)

    # 每日日志
    daily_logs: List[Dict] = field(default_factory=list)

    # Heritage 数据
    heritage_stats: Dict = field(default_factory=dict)

    # 年轮数据
    life_ring_stats: Dict = field(default_factory=dict)

    # 认知健康
    cognitive_metrics: Dict = field(default_factory=dict)

    # 任务状态
    todo_summary: Dict = field(default_factory=dict)

    # 锚点统计
    anchor_stats: Dict = field(default_factory=dict)

    # 时间统计
    time_stats: Dict = field(default_factory=dict)


@dataclass
class ReviewReport:
    """复盘报告"""
    review_id: str
    review_type: str
    generated_at: str
    date_range: Tuple[str, str]

    # 健康评估
    health: str
    health_score: float           # 0.0 ~ 1.0

    # 叙事
    narrative: str

    # 要点
    highlights: List[str]
    concerns: List[str]
    unfinished: List[str]

    # 代谢建议
    metabolism_actions: List[str]

    # 下周/天展望
    outlook: str

    # 元数据
    data_sources: List[str]
    token_estimate: int


# ============================================================================
# 数据收集器
# ============================================================================

class ReviewDataCollector:
    """从各系统收集复盘所需数据"""

    def __init__(self):
        self.sysdate = datetime.now(timezone.utc)

    def collect(self, review_type: ReviewType, days_back: int = 1) -> ReviewDataBundle:
        """收集复盘数据"""
        if review_type == ReviewType.DAILY:
            start = self.sysdate - timedelta(days=1)
            end = self.sysdate
        else:  # WEEKLY
            start = self.sysdate - timedelta(days=7)
            end = self.sysdate

        bundle = ReviewDataBundle(
            review_type=review_type.value,
            date_range=(start.isoformat(), end.isoformat()),
        )

        # 收集每日日志
        bundle.daily_logs = self._collect_daily_logs(start, end)

        # Heritage 统计
        bundle.heritage_stats = self._collect_heritage_stats()

        # 年轮统计
        bundle.life_ring_stats = self._collect_life_ring_stats()

        # 认知指标
        bundle.cognitive_metrics = self._collect_cognitive_metrics()

        # TODO 摘要
        bundle.todo_summary = self._collect_todo_summary()

        # 锚点统计
        bundle.anchor_stats = self._collect_anchor_stats()

        # 时间统计
        bundle.time_stats = self._collect_time_stats(start, end)

        return bundle

    def _collect_daily_logs(self, start, end) -> List[Dict]:
        """收集日期范围内的每日日志"""
        logs = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            log_path = os.path.join(MEMORY_DIR, f"{date_str}.md")
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 提取关键段落（避免读取整个文件）
                    lines = content.split("\n")
                    summary_lines = [
                        l for l in lines
                        if any(kw in l for kw in ["##", "完成", "突破", "问题", "决定"])
                    ][:30]  # 最多30行摘要
                    logs.append({
                        "date": date_str,
                        "summary": "\n".join(summary_lines),
                        "size_bytes": os.path.getsize(log_path),
                    })
                except Exception as e:
                    logger.warning(f"[ReviewCollector] 日志读取失败 {date_str}: {e}")
            current += timedelta(days=1)
        return logs

    def _collect_heritage_stats(self) -> Dict:
        """收集遗产系统统计"""
        try:
            from heritage_system import HeritageSystem
            hs = HeritageSystem()
            integrity = hs.check_chain_integrity()
            return {
                "total_anchors": integrity.get("total_anchors", 0),
                "chain_status": integrity.get("status", "unknown"),
                "heavy_anchors": len(integrity.get("heavy_anchor_ids", [])),
                "broken_chains": len(integrity.get("gaps", [])),
                "inherited_count": hs.registry.registry.inherited_count,
            }
        except Exception as e:
            logger.warning(f"[ReviewCollector] Heritage 收集失败: {e}")
            return {}

    def _collect_life_ring_stats(self) -> Dict:
        """收集生命年轮统计"""
        try:
            from life_ring_tracker_extension import get_life_ring_extension
            ext = get_life_ring_extension()
            if ext.tracker:
                rings = ext.tracker.get_rings(max_count=100)
                open_loops = ext.tracker.get_open_loops()
                stage = ext.tracker.get_current_stage()
                return {
                    "ring_node_count": len(rings),
                    "open_loop_count": len(open_loops),
                    "current_stage": stage.get("stage", "unknown"),
                    "closure_count": stage.get("closure_count", 0),
                }
        except Exception as e:
            logger.warning(f"[ReviewCollector] LifeRing 收集失败: {e}")
        return {}

    def _collect_cognitive_metrics(self) -> Dict:
        """收集认知健康指标"""
        metrics = {}
        # 健康日志
        health_path = os.path.join(AGENT_DIR, "health_log.json")
        if os.path.exists(health_path):
            try:
                with open(health_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                events = data.get("events", [])
                if events:
                    latest = events[-1]
                    metrics["health_score"] = latest.get("health_score", 0.8)
                    metrics["resource_usage"] = latest.get("resource_usage", 0.5)
                    metrics["context_freshness"] = latest.get("context_freshness", 0.8)
            except Exception as e:
                logger.warning(f"[ReviewCollector] Health 读取失败: {e}")

        # 痛觉日志
        pain_path = os.path.join(AGENT_DIR, "cognitive_pain_log.json")
        if os.path.exists(pain_path):
            try:
                with open(pain_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                alerts = [e for e in data.get("events", []) if e.get("severity", 0) >= 0.7]
                metrics["high_pain_alerts"] = len(alerts)
                metrics["recent_pain_triggers"] = [
                    {"type": a.get("type"), "severity": a.get("severity")}
                    for a in alerts[-5:]
                ]
            except Exception as e:
                logger.warning(f"[ReviewCollector] Pain log 读取失败: {e}")

        return metrics

    def _collect_todo_summary(self) -> Dict:
        """收集 TODO 摘要"""
        todo_path = os.path.join(WORKSPACE, "TODO_MASTER.md")
        if not os.path.exists(todo_path):
            return {}

        try:
            with open(todo_path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            pending = sum(1 for l in lines if l.strip().startswith("- [ ]"))
            done = sum(1 for l in lines if l.strip().startswith("- [x]"))
            stale = sum(1 for l in lines if "STALE" in l)

            return {
                "total_pending": pending,
                "total_done": done,
                "stale_count": stale,
                "pending_rate": pending / max(pending + done, 1),
            }
        except Exception as e:
            logger.warning(f"[ReviewCollector] TODO 读取失败: {e}")
            return {}

    def _collect_anchor_stats(self) -> Dict:
        """收集锚点统计"""
        try:
            from heritage_system import HeritageSystem
            hs = HeritageSystem()
            return {
                "total_in_chain": len(hs.chain.anchors),
                "heavy_count": len(hs.chain.get_heavy_anchors()),
                "critical_count": len([
                    a for a in hs.chain.anchors.values()
                    if a.weight_class == "critical"
                ]),
            }
        except Exception as e:
            logger.warning(f"[ReviewCollector] Anchor 收集失败: {e}")
            return {}

    def _collect_time_stats(self, start, end) -> Dict:
        """收集时间统计"""
        # 统计每日日志覆盖天数
        covered = 0
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            log_path = os.path.join(MEMORY_DIR, f"{date_str}.md")
            if os.path.exists(log_path):
                covered += 1
            current += timedelta(days=1)

        total_days = (end - start).days + 1
        return {
            "days_covered": covered,
            "days_total": total_days,
            "coverage_rate": covered / total_days if total_days > 0 else 0.0,
        }


# ============================================================================
# 复盘报告生成器
# ============================================================================

class ReviewReportGenerator:
    """生成每日/每周复盘报告"""

    def __init__(self):
        self.collector = ReviewDataCollector()

    def generate(self, review_type: ReviewType) -> ReviewReport:
        """生成复盘报告"""
        days_back = 7 if review_type == ReviewType.WEEKLY else 1
        bundle = self.collector.collect(review_type, days_back)

        # 健康评分
        health_score = self._compute_health_score(bundle)
        health = self._score_to_health(health_score)

        # 叙事生成
        narrative = self._generate_narrative(review_type, bundle)

        # 高光/担忧/未完成
        highlights = self._extract_highlights(bundle)
        concerns = self._extract_concerns(bundle)
        unfinished = self._extract_unfinished(bundle)

        # 代谢建议
        metabolism = self._generate_metabolism_actions(bundle, health_score)

        # 展望
        outlook = self._generate_outlook(review_type, bundle, health_score)

        review_id = f"rev_{review_type.value}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        return ReviewReport(
            review_id=review_id,
            review_type=review_type.value,
            generated_at=datetime.now(timezone.utc).isoformat(),
            date_range=bundle.date_range,
            health=health.value,
            health_score=health_score,
            narrative=narrative,
            highlights=highlights,
            concerns=concerns,
            unfinished=unfinished,
            metabolism_actions=metabolism,
            outlook=outlook,
            data_sources=self._list_data_sources(bundle),
            token_estimate=self._estimate_tokens(narrative, highlights, concerns, unfinished),
        )

    def _compute_health_score(self, bundle: ReviewDataBundle) -> float:
        """计算健康评分"""
        scores = []

        # Heritage 健康（权重30%）
        hs = bundle.heritage_stats
        if hs:
            chain_ok = hs.get("chain_status") == "healthy"
            no_broken = hs.get("broken_chains", 0) == 0
            hs_score = 0.9 if (chain_ok and no_broken) else 0.5 if chain_ok else 0.2
            scores.append(("heritage", hs_score, 0.30))

        # 年轮健康（权重20%）
        lr = bundle.life_ring_stats
        if lr:
            open_loops = lr.get("open_loop_count", 0)
            lr_score = 1.0 if open_loops == 0 else max(0.0, 1.0 - open_loops * 0.1)
            scores.append(("life_ring", lr_score, 0.20))

        # 认知健康（权重25%）
        cm = bundle.cognitive_metrics
        if cm:
            pain_alerts = cm.get("high_pain_alerts", 0)
            cm_score = max(0.0, 1.0 - pain_alerts * 0.15)
            scores.append(("cognitive", cm_score, 0.25))

        # 日志覆盖（权重15%）
        ts = bundle.time_stats
        if ts:
            cov_score = ts.get("coverage_rate", 0.5)
            scores.append(("time_coverage", cov_score, 0.15))

        # TODO 健康（权重10%）
        td = bundle.todo_summary
        if td:
            stale_rate = td.get("stale_count", 0) / max(td.get("total_pending", 1), 1)
            td_score = max(0.0, 1.0 - stale_rate * 2)
            scores.append(("todo", td_score, 0.10))

        # 加权平均
        if not scores:
            return 0.7  # 默认

        total_weight = sum(w for _, _, w in scores)
        weighted = sum(s * w for _, s, w in scores)
        return weighted / total_weight if total_weight > 0 else 0.7

    def _score_to_health(self, score: float) -> ReviewHealth:
        if score >= 0.85:
            return ReviewHealth.EXCELLENT
        elif score >= 0.70:
            return ReviewHealth.GOOD
        elif score >= 0.50:
            return ReviewHealth.ATTENTION
        else:
            return ReviewHealth.CONCERN

    def _generate_narrative(self, review_type: ReviewType, bundle: ReviewDataBundle) -> str:
        """生成叙事文本"""
        type_label = "本周" if review_type == ReviewType.WEEKLY else "今日"

        parts = []

        # 时间覆盖
        ts = bundle.time_stats
        if ts:
            parts.append(
                f"{type_label}日志覆盖 {ts.get('days_covered', 0)}/{ts.get('days_total', 0)} 天"
                f"（覆盖率 {ts.get('coverage_rate', 0):.0%}）"
            )

        # Heritage 链条
        hs = bundle.heritage_stats
        if hs:
            anchors = hs.get("total_anchors", 0)
            status = hs.get("chain_status", "unknown")
            parts.append(f"钢印链条共 {anchors} 个锚点，状态{status}。")

        # 年轮
        lr = bundle.life_ring_stats
        if lr:
            stage = lr.get("current_stage", "?")
            loops = lr.get("open_loop_count", 0)
            rings = lr.get("ring_node_count", 0)
            parts.append(
                f"生命年轮处于「{stage}」，{rings} 个结晶节点，"
                f"{loops} 个开放闭环。"
            )

        # 认知
        cm = bundle.cognitive_metrics
        if cm:
            health = cm.get("health_score", 0.8)
            pain = cm.get("high_pain_alerts", 0)
            parts.append(
                f"认知健康评分 {health:.0%}，高频痛觉告警 {pain} 次。"
            )

        # TODO
        td = bundle.todo_summary
        if td:
            pending = td.get("total_pending", 0)
            done = td.get("total_done", 0)
            parts.append(f"待办系统：{done} 项已完成，{pending} 项待处理。")

        return "；".join(parts) if parts else f"{type_label}无显著事件。"

    def _extract_highlights(self, bundle: ReviewDataBundle) -> List[str]:
        """提取高光时刻"""
        highlights = []

        # 链条健康
        if bundle.heritage_stats.get("chain_status") == "healthy":
            highlights.append("钢印链条完整，无断裂风险")

        # 年轮结晶
        lr = bundle.life_ring_stats
        if lr and lr.get("ring_node_count", 0) > 0:
            highlights.append(
                f"新增 {lr.get('ring_node_count')} 个年轮结晶节点"
            )

        # 遗产激活
        if bundle.heritage_stats.get("inherited_count", 0) > 0:
            highlights.append(
                f"遗产系统已激活 {bundle.heritage_stats['inherited_count']} 次"
            )

        # 每日日志质量
        ts = bundle.time_stats
        if ts and ts.get("coverage_rate", 0) >= 0.8:
            highlights.append("日志记录完整")

        return highlights

    def _extract_concerns(self, bundle: ReviewDataBundle) -> List[str]:
        """提取需要关注的问题"""
        concerns = []

        # 链条断裂
        if bundle.heritage_stats.get("broken_chains", 0) > 0:
            concerns.append(
                f"⚠️ 钢印链条存在 {bundle.heritage_stats['broken_chains']} 处断裂"
            )

        # 重锚点
        if bundle.heritage_stats.get("heavy_anchors", 0) > 0:
            concerns.append(
                f"⚠️ 存在 {bundle.heritage_stats['heavy_anchors']} 个重锚点，需监控上下文膨胀"
            )

        # 开放闭环过多
        lr = bundle.life_ring_stats
        if lr and lr.get("open_loop_count", 0) > 5:
            concerns.append(
                f"⚠️ {lr['open_loop_count']} 个开放闭环，骶变风险上升"
            )

        # 痛觉告警
        cm = bundle.cognitive_metrics
        if cm and cm.get("high_pain_alerts", 0) >= 3:
            concerns.append(
                f"⚠️ 高频痛觉告警 {cm['high_pain_alerts']} 次，需排查根因"
            )

        # 日志缺失
        ts = bundle.time_stats
        if ts and ts.get("coverage_rate", 1.0) < 0.5:
            concerns.append(
                f"⚠️ 日志覆盖率仅 {ts.get('coverage_rate', 0):.0%}，记忆缺失风险"
            )

        return concerns

    def _extract_unfinished(self, bundle: ReviewDataBundle) -> List[str]:
        """提取未完成任务"""
        unfinished = []

        # 开放闭环
        lr = bundle.life_ring_stats
        if lr and lr.get("open_loop_count", 0) > 0:
            unfinished.append(
                f"年轮开放闭环: {lr['open_loop_count']} 个"
            )

        # 链条断裂
        if bundle.heritage_stats.get("broken_chains", 0) > 0:
            unfinished.append(
                f"待修复钢印链条断裂: {bundle.heritage_stats['broken_chains']} 处"
            )

        # TODO
        td = bundle.todo_summary
        if td and td.get("stale_count", 0) > 0:
            unfinished.append(
                f"TODO 积压 {td['stale_count']} 个 STALE 项待清理"
            )

        return unfinished

    def _generate_metabolism_actions(self, bundle: ReviewDataBundle, health: float) -> List[str]:
        """生成代谢建议"""
        actions = []

        # 健康良好 → 继续积累
        if health >= 0.85:
            actions.append("继续保持当前节奏")
            return actions

        # 健康警告 → 对应建议
        if bundle.heritage_stats.get("broken_chains", 0) > 0:
            actions.append("Heritage 系统：检查钢印链条断裂点，运行 heritage_system.check_chain_integrity()")

        if bundle.heritage_stats.get("heavy_anchors", 0) > 2:
            actions.append("重锚点综合征风险：执行 heritage_system.pre_context_check() 限制激活深度")

        lr = bundle.life_ring_stats
        if lr and lr.get("open_loop_count", 0) > 5:
            actions.append(
                f"骶变风险：{lr['open_loop_count']} 个开放闭环触发，可运行 life_ring_extension.sunday_scan()"
            )

        cm = bundle.cognitive_metrics
        if cm and cm.get("high_pain_alerts", 0) >= 3:
            actions.append("痛觉告警频繁：检查 cognitive_pain_monitor 根因，考虑触发 alignment_verify 自检")

        ts = bundle.time_stats
        if ts and ts.get("coverage_rate", 1.0) < 0.5:
            actions.append("日志缺失：补充每日记忆日志，减少记忆盲区")

        return actions

    def _generate_outlook(self,
                          review_type: ReviewType,
                          bundle: ReviewDataBundle,
                          health: float) -> str:
        """生成展望"""
        prefix = "下周" if review_type == ReviewType.WEEKLY else "明天"

        if health >= 0.85:
            return f"{prefix}继续稳定运行，关注新锚点积累。"

        concerns = self._extract_concerns(bundle)
        if concerns:
            top_concern = concerns[0]
            return f"{prefix}优先处理：{top_concern}"

        return f"{prefix}持续监控，注意上下文管理。"

    def _list_data_sources(self, bundle: ReviewDataBundle) -> List[str]:
        sources = []
        if bundle.daily_logs:
            sources.append("memory/YYYY-MM-DD.md")
        if bundle.heritage_stats:
            sources.append("heritage_system")
        if bundle.life_ring_stats:
            sources.append("life_ring_tracker")
        if bundle.cognitive_metrics:
            sources.append("health_log + cognitive_pain_log")
        if bundle.todo_summary:
            sources.append("TODO_MASTER.md")
        return sources

    def _estimate_tokens(self, *strings) -> int:
        """粗略估算 token 数"""
        total = sum(len(s) for s in strings if isinstance(s, str))
        return int(total / 4)  # 粗略：4字符≈1token


# ============================================================================
# 复盘持久化
# ============================================================================

class ReviewPersistence:
    """将复盘报告写入文件系统"""

    def __init__(self):
        self.sysdate = datetime.now(timezone.utc)

    def save(self, report: ReviewReport) -> str:
        """保存复盘报告"""
        date_str = self.sysdate.strftime("%Y-%m-%d")
        type_label = "周" if report.review_type == "weekly" else "日"

        # 1. 每日复盘 → memory/YYYY-MM-DD_review.md
        if report.review_type == "daily":
            path = os.path.join(MEMORY_DIR, f"{date_str}_review.md")
            self._write_daily_review(path, report)
            logger.info(f"[Review] 每日复盘已保存: {path}")
            return path

        # 2. 每周复盘 → MEMORY.md 更新 + 独立文件
        weekly_path = os.path.join(MEMORY_DIR, f"weekly_review_{date_str}.md")
        self._write_weekly_review(weekly_path, report)

        # 同步到 MEMORY.md
        self._update_memory_md(report)

        logger.info(f"[Review] 每周复盘已保存: {weekly_path}")
        return weekly_path

    def _write_daily_review(self, path: str, report: ReviewReport):
        lines = [
            f"# {report.date_range[0][:10]} 每日复盘",
            "",
            f"## 健康评分：{report.health_score:.0%}（{report.health}）",
            "",
            "## 叙事",
            report.narrative,
            "",
            "## 高光",
            *[f"- {h}" for h in report.highlights],
            "",
            "## 需要关注",
            *[f"- {c}" for c in report.concerns],
            "",
            "## 未完成任务",
            *[f"- {u}" for u in report.unfinished],
            "",
            "## 代谢建议",
            *[f"- {a}" for a in report.metabolism_actions],
            "",
            "## 展望",
            report.outlook,
            "",
            "---",
            f"生成时间：{report.generated_at}",
            f"数据来源：{', '.join(report.data_sources)}",
            f"Token估算：{report.token_estimate}",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _write_weekly_review(self, path: str, report: ReviewReport):
        lines = [
            f"# 每周复盘 {report.date_range[0][:10]} ~ {report.date_range[1][:10]}",
            "",
            f"## 健康评分：{report.health_score:.0%}（{report.health}）",
            "",
            "## 本周叙事",
            report.narrative,
            "",
            "## 高光时刻",
            *[f"- {h}" for h in report.highlights],
            "",
            "## 需要关注的问题",
            *[f"- {c}" for c in report.concerns],
            "",
            "## 待处理事项",
            *[f"- {u}" for u in report.unfinished],
            "",
            "## 代谢行动计划",
            *[f"- {a}" for a in report.metabolism_actions],
            "",
            "## 下周展望",
            report.outlook,
            "",
            "---",
            f"报告ID：{report.review_id}",
            f"生成时间：{report.generated_at}",
            f"Token估算：{report.token_estimate}",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _update_memory_md(self, report: ReviewReport):
        """将每周复盘精华同步到 MEMORY.md"""
        memory_path = os.path.join(WORKSPACE, "MEMORY.md")
        if not os.path.exists(memory_path):
            logger.warning("[Review] MEMORY.md 不存在，跳过同步")
            return

        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 在文件开头（第一个 ## 标题后）插入周复盘精华
            week_marker = (
                f"\n\n## 周复盘 {report.date_range[0][:10]} ~ {report.date_range[1][:10]}\n"
                f"健康：{report.health}（{report.health_score:.0%}）\n"
                f"叙事：{report.narrative}\n"
            )
            if report.highlights:
                week_marker += "高光：" + "；".join(report.highlights) + "\n"
            if report.concerns:
                week_marker += "关注：" + "；".join(report.concerns) + "\n"
            if report.metabolism_actions:
                week_marker += "行动：" + "；".join(report.metabolism_actions) + "\n"

            # 找到第一个 ## 标题的位置
            first_header = content.find("\n## ")
            if first_header > 0:
                insert_pos = first_header + 1
                new_content = content[:insert_pos] + week_marker + content[insert_pos:]
            else:
                new_content = content + week_marker

            with open(memory_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info("[Review] MEMORY.md 周复盘同步完成")
        except Exception as e:
            logger.warning(f"[Review] MEMORY.md 同步失败: {e}")


# ============================================================================
# 主入口
# ============================================================================

class ReviewScheduler:
    """
    复盘调度器主入口。

    支持两种调用方式：
    1. cron 触发（推荐）：每日 23:55 和每周日 23:55
    2. 手动调用：`python -m review_scheduler daily` 或 `weekly`
    """

    def __init__(self):
        self.generator = ReviewReportGenerator()
        self.persistence = ReviewPersistence()

    def run(self, review_type: str = "daily") -> str:
        """
        运行复盘。
        Args:
            review_type: "daily" 或 "weekly"
        Returns:
            保存的文件路径
        """
        rt = ReviewType.WEEKLY if review_type == "weekly" else ReviewType.DAILY
        logger.info(f"[ReviewScheduler] 开始生成 {rt.value} 复盘...")

        report = self.generator.generate(rt)
        path = self.persistence.save(report)

        # 打印摘要（供 cron 输出查看）
        print(f"=== {rt.value.upper()} REVIEW ===")
        print(f"健康: {report.health_score:.0%} ({report.health})")
        print(f"叙事: {report.narrative[:100]}")
        if report.highlights:
            print(f"高光: {report.highlights[0]}")
        if report.concerns:
            print(f"关注: {report.concerns[0]}")
        print(f"保存: {path}")
        print(f"Token估算: {report.token_estimate}")

        return path


# ============================================================================
# CLI 入口（支持手动触发）
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    sys.stdout.reconfigure(encoding="utf-8")

    review_type = sys.argv[1] if len(sys.argv) > 1 else "daily"
    scheduler = ReviewScheduler()
    path = scheduler.run(review_type)
    print(f"\n复盘完成: {path}")
