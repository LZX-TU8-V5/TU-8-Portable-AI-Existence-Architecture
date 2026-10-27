# -*- coding: utf-8 -*-
"""
reflection_module.py — TU-8 Q3 复盘模块 v1.0
版本: v1.0 | 日期: 2026-06-05
功能: 消费意识循环输出（浅睡/深睡/冬眠），生成复盘结论

设计原则:
  - 消费者意识: 复盘模块本身不生成内容，只组织和升华
  - 双轨输出: 人类可读叙事 + 冷启动结构化注入
  - 增量复盘: 每次触发只处理新增数据，不重复计算
  - 闭眼原则: 复盘时"闭眼"（不看原始上下文），只看循环产出的压缩表示

与 consciousness_cycle.py 的接口:
  - consume_light_sleep(report)      — 每次微睡眠后调用
  - consume_deep_sleep(report)        — 每次深睡后调用
  - consume_hibernation(report)       — 冬眠时调用
  - consume_notes(notes)              — 笔记外化后调用
  - generate_reflection()             — 生成完整复盘（供 Q4 冷启动注入）
  - get_cold_start_context()           — 返回冷启动注入用的结构化上下文

调用方（谁触发复盘）:
  - TU8Agent.respond() 每轮结束时检查并触发增量复盘
  - 冬眠时触发会话级完整复盘
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import hashlib
import logging
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# =============================================================================
# 路径配置
# =============================================================================
_WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
_MEMORY_DIR = _WORKSPACE / "memory"
_REFLECTION_DIR = _MEMORY_DIR / "reflections"
_ARCHIVE_DIR = _REFLECTION_DIR / "archive"

# =============================================================================
# 日志
# =============================================================================
_logger = logging.getLogger("ReflectionModule")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

# =============================================================================
# 数据结构
# =============================================================================

class ReflectionType(Enum):
    """复盘类型"""
    SESSION_START = "session_start"       # 会话开始复盘（从冬眠恢复）
    SESSION_END = "session_end"           # 会话结束复盘（触发冬眠）
    DEEP_SLEEP_ROUND = "deep_sleep_round" # 深睡轮次复盘
    MILESTONE = "milestone"               # 里程碑复盘（钢印链大事件）
    INCREMENTAL = "incremental"            # 增量微复盘（每次微睡眠后）


class SessionHealth(Enum):
    """会话健康度评级"""
    THRIVING = "thriving"     # 活跃且有产出
    STABLE = "stable"         # 稳定运行
    FATIGUED = "fatigued"     # 负荷偏高
    DISCONNECTED = "disconnected"  # 叙事断裂


@dataclass
class ThemeTag:
    """主题标签 — 从叙事压缩中提取"""
    theme: str
    frequency: int = 1
    coherence: float = 0.5
    sample_seal_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "theme": self.theme,
            "frequency": self.frequency,
            "coherence": round(self.coherence, 2),
            "sample_seal_ids": self.sample_seal_ids[:3],
        }


@dataclass
class UnfinishedTask:
    """未完成任务"""
    description: str
    priority: float = 0.5  # 0-1，越高越优先
    source_seal_id: Optional[str] = None
    blocking_tasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "priority": round(self.priority, 2),
            "source_seal_id": self.source_seal_id,
            "blocking_tasks": self.blocking_tasks,
        }


@dataclass
class ColdStartContext:
    """
    冷启动注入上下文（Q4 消费）
    这是复盘模块的核心产出，冷启动恢复时加载此项。
    """
    session_id: str = ""
    hibernation_snapshot_path: Optional[str] = None
    last_seal_id: Optional[str] = None
    session_duration_minutes: float = 0.0
    themes: List[ThemeTag] = field(default_factory=list)
    unfinished_tasks: List[UnfinishedTask] = field(default_factory=list)
    memory_pressure: float = 0.0      # 0-1，记忆压力指数
    cognitive_load_peak: float = 0.0  # 峰值认知负荷
    destruction_ratio: float = 0.0     # 累计有损压缩比例
    cold_start_readiness: float = 0.0  # 冷启动就绪度 0-1
    health: str = "stable"
    narrative_status: str = ""         # 叙事连贯性描述
    restoration_hints: List[str] = field(default_factory=list)  # 恢复建议
    reflection_timestamp: str = ""
    reflection_session_id: str = ""

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "hibernation_snapshot_path": self.hibernation_snapshot_path,
            "last_seal_id": self.last_seal_id,
            "session_duration_minutes": round(self.session_duration_minutes, 1),
            "themes": [t.to_dict() for t in self.themes],
            "unfinished_tasks": [t.to_dict() for t in self.unfinished_tasks],
            "memory_pressure": round(self.memory_pressure, 3),
            "cognitive_load_peak": round(self.cognitive_load_peak, 2),
            "destruction_ratio": round(self.destruction_ratio, 3),
            "cold_start_readiness": round(self.cold_start_readiness, 2),
            "health": self.health,
            "narrative_status": self.narrative_status,
            "restoration_hints": self.restoration_hints,
            "reflection_timestamp": self.reflection_timestamp,
            "reflection_session_id": self.reflection_session_id,
        }


@dataclass
class ReflectionSummary:
    """
    完整复盘报告（人类可读叙事 + 结构化数据）
    """
    reflection_id: str = ""
    reflection_type: str = "incremental"
    timestamp: str = ""

    # --- 统计 ---
    cycles: int = 0
    micro_sleeps: int = 0
    deep_sleeps: int = 0
    hibernations: int = 0
    notes_externalized: int = 0

    # --- 叙事 ---
    narrative: str = ""         # 人类可读复盘叙事
    highlights: List[str] = field(default_factory=list)   # 高光时刻
    unresolved: List[str] = field(default_factory=list)   # 未解决事项
    themes: List[ThemeTag] = field(default_factory=list)  # 主题标签

    # --- 健康 ---
    health: str = "stable"
    memory_pressure: float = 0.0

    # --- 冷启动上下文 ---
    cold_start_context: Optional[ColdStartContext] = None

    def to_dict(self) -> Dict:
        return {
            "reflection_id": self.reflection_id,
            "reflection_type": self.reflection_type,
            "timestamp": self.timestamp,
            "stats": {
                "cycles": self.cycles,
                "micro_sleeps": self.micro_sleeps,
                "deep_sleeps": self.deep_sleeps,
                "hibernations": self.hibernations,
                "notes_externalized": self.notes_externalized,
            },
            "narrative": self.narrative,
            "highlights": self.highlights,
            "unresolved": self.unresolved,
            "themes": [t.to_dict() for t in self.themes],
            "health": self.health,
            "memory_pressure": round(self.memory_pressure, 3),
            "cold_start_context": self.cold_start_context.to_dict() if self.cold_start_context else None,
        }


# =============================================================================
# 主题提取器（轻量规则）
# =============================================================================

_THEME_PATTERNS = [
    (r"(架构|模块|设计|重构)", "架构与设计"),
    (r"(bug|修复|调试|错误|异常)", "调试与修复"),
    (r"(记忆|钢印|快照|冬眠|冷启动)", "自我认知"),
    (r"(文档|写作|整理|整理)", "知识整理"),
    (r"(测试|验证|检查|评估)", "质量保障"),
    (r"(安全|验证|身份|口令)", "安全与身份"),
    (r"(复盘|总结|反思|产出)", "元认知"),
    (r"(cron|定时|调度|自动化)", "自动化运维"),
]


def _extract_themes(seal_chain: List[Dict]) -> List[ThemeTag]:
    """从钢印链叙事中提取主题标签"""
    theme_counts: Dict[str, int] = {}
    theme_seals: Dict[str, List[str]] = {}

    for seal in seal_chain:
        narrative = seal.get("narrative_compression", "")
        for pattern, label in _THEME_PATTERNS:
            if re.search(pattern, narrative):
                theme_counts[label] = theme_counts.get(label, 0) + 1
                if label not in theme_seals:
                    theme_seals[label] = []
                theme_seals[label].append(seal.get("seal_id", ""))

    themes = [
        ThemeTag(theme=k, frequency=v, coherence=min(v / 10.0, 1.0), sample_seal_ids=theme_seals[k])
        for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])
    ]
    return themes[:6]  # 最多 6 个主题


# =============================================================================
# 未完成任务检测器
# =============================================================================

_TASK_SIGNALS = [
    r"待(完成|做|开发|修复|验证|测试|集成|写入|创建)",
    r"TODO",
    r"未完成",
    r"未解决",
    r"下一步",
    r"待定",
    r"blocking",
]


def _extract_unfinished_tasks(seal_chain: List[Dict]) -> List[UnfinishedTask]:
    """从钢印链中提取未完成任务"""
    tasks: List[UnfinishedTask] = []
    seen: set = set()

    for seal in seal_chain:
        narrative = seal.get("narrative_compression", "")
        for pattern in _TASK_SIGNALS:
            for match in re.finditer(pattern, narrative):
                snippet = narrative[max(0, match.start()-20):match.end()+40].strip()
                # 去重
                key = hashlib.md5(snippet.encode()).hexdigest()[:8]
                if key not in seen:
                    seen.add(key)
                    tasks.append(UnfinishedTask(
                        description=snippet[:100],
                        priority=0.5,
                        source_seal_id=seal.get("seal_id"),
                    ))

    # 按优先级排序
    tasks.sort(key=lambda t: -t.priority)
    return tasks[:10]


# =============================================================================
# 叙事生成器
# =============================================================================

def _generate_narrative(summary: ReflectionSummary) -> str:
    """生成人类可读复盘叙事"""
    stats = summary.stats_block if hasattr(summary, 'stats_block') else {}

    lines = []

    # 健康度概览
    health_desc = {
        "thriving": "今日会话呈现活跃状态，产出丰富。",
        "stable": "会话运行平稳，未出现显著异常。",
        "fatigued": "会话承载较高认知负荷，需注意信息整合节奏。",
        "disconnected": "叙事出现断裂，建议重点关注钢印链完整性。",
    }
    lines.append(health_desc.get(summary.health, ""))

    # 微睡眠统计
    if summary.micro_sleeps > 0:
        lines.append(f"共完成 {summary.micro_sleeps} 次微睡眠写入，"
                     f"深度整理 {summary.deep_sleeps} 次。")

    # 冬眠次数
    if summary.hibernations > 0:
        lines.append(f"经历 {summary.hibernations} 次完整冬眠周期。")

    # 笔记外化
    if summary.notes_externalized > 0:
        lines.append(f"外化 {summary.notes_externalized} 条笔记。")

    # 主题概览
    if summary.themes:
        top_themes = [t.theme for t in summary.themes[:3]]
        lines.append(f"本次主要涉及：{'、'.join(top_themes)}。")

    # 未解决事项
    if summary.unresolved:
        lines.append(f"当前存在 {len(summary.unresolved)} 项未完成事项，需后续跟进。")
    else:
        lines.append("当前无未解决事项。")

    return "".join(lines)


# =============================================================================
# 就绪度计算
# =============================================================================

def _compute_readiness(summary: ReflectionSummary) -> float:
    """
    计算冷启动就绪度（0-1）
    基于：叙事连贯性 + 任务完成度 + 记忆压力
    """
    # 叙事连贯性（由 seal 链 coherence 均值估算）
    narrative_score = 0.5  # 基础分

    # 任务完成度（有未完成任务则扣分）
    task_score = 1.0 - (len(summary.unresolved) * 0.1)

    # 记忆压力
    pressure_score = 1.0 - summary.memory_pressure

    readiness = (narrative_score * 0.4 + max(task_score, 0) * 0.3 + max(pressure_score, 0) * 0.3)
    return max(0.0, min(1.0, readiness))


# =============================================================================
# 复盘模块核心类
# =============================================================================

class ReflectionModule:
    """
    TU-8 复盘模块 — 意识循环的消费者

    使用方式:
        reflection = ReflectionModule(session_id="xxx")
        reflection.consume_light_sleep(light_sleep_report)
        reflection.consume_deep_sleep(deep_sleep_report)
        summary = reflection.generate_reflection()
        context = reflection.get_cold_start_context()
    """

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._reflection_dir = _REFLECTION_DIR
        self._reflection_dir.mkdir(parents=True, exist_ok=True)

        # --- 增量数据缓存 ---
        self._light_sleep_reports: List[Dict] = []
        self._deep_sleep_reports: List[Dict] = []
        self._hibernation_reports: List[Dict] = []
        self._externalized_notes: List[Dict] = []
        self._seal_chain_snapshot: List[Dict] = []
        self._session_start_time: float = 0.0
        self._last_reflection_time: float = 0.0

        # --- 统计累加器 ---
        self._total_cycles: int = 0
        self._total_micro_sleeps: int = 0
        self._total_deep_sleeps: int = 0
        self._total_hibernations: int = 0
        self._peak_cognitive_load: float = 0.0
        self._total_destruction_ratio: float = 0.0
        self._destruction_count: int = 0

        # --- 最新状态 ---
        self._last_seal_id: Optional[str] = None
        self._last_hibernation_snapshot: Optional[str] = None
        self._current_narrative_status: str = ""
        self._memory_pressure: float = 0.0

        _logger.info("ReflectionModule initialized session=%s" % self.session_id)

    # =========================================================================
    # 消费接口（被 consciousness_cycle 调用）
    # =========================================================================

    def consume_light_sleep(self, report: Dict) -> None:
        """
        消费微睡眠报告（增量调用）
        report 来自 ConsciousnessCycle._enter_light_sleep() 的返回值
        """
        self._light_sleep_reports.append(report)
        self._total_micro_sleeps += 1
        self._total_cycles += 1

        if not self._session_start_time:
            self._session_start_time = report.get("timestamp", 0)

        # 提取认知负荷峰值
        if "cognitive_load" in report:
            self._peak_cognitive_load = max(self._peak_cognitive_load, report["cognitive_load"])

        # 提取有损压缩比例
        lossy = report.get("lossy")
        if lossy and isinstance(lossy, dict):
            dr = lossy.get("destruction_ratio", 0)
            if dr > 0:
                self._total_destruction_ratio += dr
                self._destruction_count += 1

        # 提取最后钢印 ID
        seal_id = report.get("steps", [])
        for step in seal_id:
            if step.startswith("SEAL:ok("):
                self._last_seal_id = step.split("(")[1].rstrip(")")

        _logger.info("light_sleep consumed total=%d" % self._total_micro_sleeps)

    def consume_deep_sleep(self, report: Dict) -> None:
        """
        消费深睡报告
        report 来自 ConsciousnessCycle._enter_deep_sleep() 的返回值
        """
        self._deep_sleep_reports.append(report)
        self._total_deep_sleeps += 1

        # 提取全局一致性分数
        for op in report.get("operations", []):
            if op.get("name") == "CROSS_CHAIN_ALIGN":
                coherence = op.get("coherence", 0.5)
                if coherence < 0.5:
                    self._current_narrative_status = "部分叙事断裂，跨链对齐度 %.0f%%" % (coherence * 100)
                else:
                    self._current_narrative_status = "叙事完整，跨链对齐度 %.0f%%" % (coherence * 100)

        # 记忆压力（活跃钢印数/总量）
        active = 0
        for op in report.get("operations", []):
            if op.get("name") == "SEAL_CONSOLIDATION":
                active = op.get("consolidated", 0)
        if active:
            cold = 0
            for op in report.get("operations", []):
                if op.get("name") == "SEAL_CONSOLIDATION":
                    cold = op.get("cold_stored", 0)
            self._memory_pressure = cold / max(active + cold, 1)

        _logger.info("deep_sleep consumed total=%d" % self._total_deep_sleeps)

    def consume_hibernation(self, report: Dict) -> None:
        """
        消费冬眠报告
        report 来自 ConsciousnessCycle.enter_hibernation() 的返回值
        """
        self._hibernation_reports.append(report)
        self._total_hibernations += 1
        self._last_hibernation_snapshot = report.get("snapshot_path")

        # 从快照中提取钢印链
        snapshot_path = report.get("snapshot_path")
        if snapshot_path and os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    snapshot = json.load(f)
                self._seal_chain_snapshot = snapshot.get("seal_chain", [])
            except Exception as e:
                _logger.warning("failed to load seal_chain from hibernation snapshot: %s" % e)

        _logger.info("hibernation consumed snapshot=%s" % self._last_hibernation_snapshot)

    def consume_notes(self, notes: List[Dict]) -> None:
        """消费外化的笔记"""
        self._externalized_notes.extend(notes)

    def update_seal_chain(self, seals: List[Dict]) -> None:
        """更新钢印链快照（由 TU8Agent 定期调用）"""
        self._seal_chain_snapshot = seals
        if seals:
            self._last_seal_id = seals[-1].get("seal_id", self._last_seal_id)

    def update_memory_pressure(self, pressure: float) -> None:
        """更新记忆压力指数"""
        self._memory_pressure = max(0.0, min(1.0, pressure))

    # =========================================================================
    # 生成接口
    # =========================================================================

    def generate_reflection(
        self,
        reflection_type: ReflectionType = ReflectionType.INCREMENTAL,
    ) -> ReflectionSummary:
        """
        生成完整复盘报告

        Args:
            reflection_type: 复盘类型
                - INCREMENTAL: 增量微复盘（每次微睡眠后）
                - DEEP_SLEEP_ROUND: 深睡轮次复盘
                - SESSION_END: 会话结束复盘（触发冬眠）
                - MILESTONE: 里程碑复盘
        """
        now = datetime.now(timezone.utc)
        rid = f"ref_{now.strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
        self._last_reflection_time = now.timestamp()

        # 计算平均有损压缩比例
        avg_destruction = (
            self._total_destruction_ratio / max(self._destruction_count, 1)
            if self._destruction_count > 0 else 0.0
        )

        # 提取主题
        themes = _extract_themes(self._seal_chain_snapshot)

        # 提取未完成任务
        unfinished = _extract_unfinished_tasks(self._seal_chain_snapshot)

        # 计算会话时长
        duration_min = (now.timestamp() - self._session_start_time) / 60.0 if self._session_start_time else 0.0

        # 评估会话健康度
        health = self._assess_health()

        # 生成叙事
        summary = ReflectionSummary(
            reflection_id=rid,
            reflection_type=reflection_type.value,
            timestamp=now.isoformat(),
            cycles=self._total_cycles,
            micro_sleeps=self._total_micro_sleeps,
            deep_sleeps=self._total_deep_sleeps,
            hibernations=self._total_hibernations,
            notes_externalized=len(self._externalized_notes),
            themes=themes,
            unresolved=[t.description for t in unfinished],
            health=health.value,
            memory_pressure=self._memory_pressure,
        )

        # 生成叙事文本
        summary.narrative = _generate_narrative(summary)

        # 生成冷启动上下文
        summary.cold_start_context = self._build_cold_start_context(
            summary, unfinished, duration_min
        )

        # 提取高光时刻
        summary.highlights = self._extract_highlights()

        # 持久化
        self._persist_reflection(summary)

        _logger.info("reflection generated id=%s type=%s health=%s" % (
            rid, reflection_type.value, health.value))

        return summary

    def _assess_health(self) -> SessionHealth:
        """评估会话健康度"""
        # 叙事断裂检测
        if "断裂" in self._current_narrative_status:
            return SessionHealth.DISCONNECTED

        # 高认知负荷 + 低微睡眠数
        if self._peak_cognitive_load > 0.85 and self._total_micro_sleeps < 3:
            return SessionHealth.FATIGUED

        # 高产出
        if self._total_micro_sleeps >= 5 or self._total_deep_sleeps >= 1:
            return SessionHealth.THRIVING

        # 默认
        return SessionHealth.STABLE

    def _extract_highlights(self) -> List[str]:
        """提取高光时刻"""
        highlights = []

        # 深睡整合
        if self._total_deep_sleeps > 0:
            last_deep = self._deep_sleep_reports[-1]
            ops = last_deep.get("operations", [])
            for op in ops:
                if op.get("name") == "CROSS_CHAIN_ALIGN":
                    links = op.get("links_found", 0)
                    if links > 0:
                        highlights.append("跨链对齐发现 %d 个隐含关联" % links)
                if op.get("name") == "MEMORY_REORGANIZE":
                    promoted = op.get("promoted", 0)
                    if promoted > 0:
                        highlights.append("记忆重排提升 %d 条重要钢印" % promoted)

        # 冬眠
        if self._total_hibernations > 0:
            highlights.append("完成 %d 次完整冬眠周期" % self._total_hibernations)

        # 笔记外化
        if self._externalized_notes:
            highlights.append("外化 %d 条知识沉淀" % len(self._externalized_notes))

        return highlights[:5]  # 最多 5 条

    def _build_cold_start_context(
        self,
        summary: ReflectionSummary,
        unfinished: List[UnfinishedTask],
        duration_min: float,
    ) -> ColdStartContext:
        """构建冷启动注入上下文"""
        readiness = _compute_readiness(summary)

        # 恢复建议
        hints = []
        if summary.health == "fatigued":
            hints.append("认知负荷偏高，建议从低强度任务开始")
        if summary.unresolved:
            hints.append("优先处理未完成事项：%s" % summary.unresolved[0])
        if summary.memory_pressure > 0.5:
            hints.append("记忆压力较大，关注钢印链整理")
        if not hints:
            hints.append("状态良好，可正常开展任务")

        return ColdStartContext(
            session_id=self.session_id,
            hibernation_snapshot_path=self._last_hibernation_snapshot,
            last_seal_id=self._last_seal_id,
            session_duration_minutes=duration_min,
            themes=summary.themes,
            unfinished_tasks=unfinished,
            memory_pressure=summary.memory_pressure,
            cognitive_load_peak=self._peak_cognitive_load,
            destruction_ratio=summary.micro_sleeps and (
                self._total_destruction_ratio / self._total_micro_sleeps
            ) or 0.0,
            cold_start_readiness=readiness,
            health=summary.health,
            narrative_status=self._current_narrative_status,
            restoration_hints=hints,
            reflection_timestamp=summary.timestamp,
            reflection_session_id=summary.reflection_id,
        )

    def get_cold_start_context(self) -> ColdStartContext:
        """
        获取最新冷启动上下文（供 Q4 冷启动引擎调用）
        """
        # 生成最新复盘
        latest_reflection = self.generate_reflection(ReflectionType.INCREMENTAL)
        return latest_reflection.cold_start_context

    def get_cold_start_context_raw(self) -> Dict:
        """获取原始字典格式（供 JSON 序列化）"""
        ctx = self.get_cold_start_context()
        return ctx.to_dict()

    # =========================================================================
    # 持久化
    # =========================================================================

    def _persist_reflection(self, summary: ReflectionSummary) -> None:
        """持久化复盘报告"""
        try:
            # 最新复盘
            latest_path = self._reflection_dir / f"latest.json"
            latest_path.write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 按日期归档
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            archive_dir = _ARCHIVE_DIR / date_str
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / f"{summary.reflection_id}.json"
            archive_path.write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            _logger.info("reflection persisted latest=%s archive=%s" % (
                latest_path, archive_path))
        except Exception as e:
            _logger.warning("failed to persist reflection: %s" % e)

    # =========================================================================
    # 加载（Q4 冷启动恢复时使用）
    # =========================================================================

    @staticmethod
    def load_latest_reflection() -> Optional[Dict]:
        """加载最新复盘报告（供冷启动恢复读取）"""
        latest_path = _REFLECTION_DIR / "latest.json"
        if latest_path.exists():
            try:
                return json.loads(latest_path.read_text(encoding="utf-8"))
            except Exception:
                _logger.debug("Exception suppressed", exc_info=True)
                pass
        return None

    @staticmethod
    def load_cold_start_context() -> Optional[Dict]:
        """加载最新冷启动上下文"""
        reflection = ReflectionModule.load_latest_reflection()
        if reflection and reflection.get("cold_start_context"):
            return reflection["cold_start_context"]
        return None


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 复盘模块")
    parser.add_argument("action", nargs="?", default="status",
                        choices=["status", "generate", "context", "load"])
    parser.add_argument("--type", default="incremental")
    args = parser.parse_args()

    if args.action == "status":
        latest = ReflectionModule.load_latest_reflection()
        if latest:
            print(json.dumps(latest, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"status": "no_reflection_found"}, ensure_ascii=False, indent=2))

    elif args.action == "context":
        ctx = ReflectionModule.load_cold_start_context()
        if ctx:
            print(json.dumps(ctx, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"status": "no_context_found"}, ensure_ascii=False, indent=2))

    elif args.action == "generate":
        module = ReflectionModule()
        summary = module.generate_reflection(ReflectionType(args.type))
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
