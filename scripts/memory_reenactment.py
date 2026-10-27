# -*- coding: utf-8 -*-
"""
memory_reenactment.py — TU-8 记忆重演协议 v1.0
日期: 2026-05-30
理论来源: 外协分析 (Qwen3.7-Max) + 神经科学图片集

核心原则:
  1. 记忆不是存储，是重演 — 每次回忆都是神经模式重新激活
  2. 拒绝唯一正确答案 — 多版本共存，由上下文动态选择
  3. 读取即修改，但非破坏性 — Delta更新，历史版本永存
  4. 情境绑定 — 同一事件在不同心境下"读出来"的版本不同

工程实现:
  MemoryFractal: 记忆分形结构（event_id → versions[] + core_facts）
  MemoryReenactor: 重演引擎（激活→重构→校准）
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8.Reenactment")

# =============================================================================
# 数据结构：记忆分形（Memory Fractal）
# =============================================================================

@dataclass
class MemoryVersion:
    """记忆版本 — 同一事件的多个视角/表述"""
    version_id: str
    content: str
    context_tags: List[str]  # 如 ["stress", "work", "after_lunch"]
    confidence: float  # 0.0-1.0
    created_at: datetime
    last_retrieved: datetime
    retrieval_count: int = 0
    overridden_by: Optional[str] = None  # 被哪个版本取代（非删除！）
    override_reason: Optional[str] = None

@dataclass
class MemoryFractal:
    """记忆分形 — 一个事件的多版本共存结构"""
    event_id: str
    versions: List[MemoryVersion]
    core_facts: List[str]  # 稳定锚点（所有版本共识）
    created_at: datetime
    last_updated: datetime
    delta_log: List[Dict] = field(default_factory=list)  # 变更历史

    def get_active_versions(self) -> List[MemoryVersion]:
        """获取未被取代的活跃版本"""
        return [v for v in self.versions if v.overridden_by is None]

    def get_version(self, version_id: str) -> Optional[MemoryVersion]:
        """获取指定版本"""
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    def add_version(self, version: MemoryVersion, reason: str = "new_observation"):
        """添加新版本（非覆盖！）"""
        self.versions.append(version)
        self.last_updated = datetime.now()
        self.delta_log.append({
            "action": "add_version",
            "version_id": version.version_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"[记忆分形] 新增版本 {version.version_id}: {reason}")

    def override_version(self, old_id: str, new_id: str, reason: str):
        """标记版本被取代（非删除！）"""
        old_v = self.get_version(old_id)
        if old_v:
            old_v.overridden_by = new_id
            old_v.override_reason = reason
            self.last_updated = datetime.now()
            self.delta_log.append({
                "action": "override",
                "old_version": old_id,
                "new_version": new_id,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"[记忆分形] 版本 {old_id} → {new_id}: {reason}")

    def update_core_facts(self, new_facts: List[str]):
        """更新核心事实（合并，非替换）"""
        for f in new_facts:
            if f not in self.core_facts:
                self.core_facts.append(f)
        self.last_updated = datetime.now()

# =============================================================================
# 重演引擎：模拟"细胞级读取"
# =============================================================================

class MemoryReenactor:
    """
    记忆重演引擎 — 模拟大脑"重演式"记忆读取

    流程:
      情境化查询改写 → 多版本检索 → 神经模式激活评分 → 重构主叙事
    """

    def __init__(self, memory_dir: str = None):
        self.memory_dir = Path(memory_dir or r"D:\qq366410837\.qclaw\workspace\_agent_memory")
        self.fractals_dir = self.memory_dir / "fractals"
        self.fractals_dir.mkdir(parents=True, exist_ok=True)

        # 空间图谱（模拟位置细胞）
        self.spatial_graph = self._load_spatial_graph()

        # 时间衰减参数
        self.time_decay_rate = 0.1  # 指数衰减系数

    # -------------------------------------------------------------------------
    # 空间图谱：轻量级"位置细胞"实现
    # -------------------------------------------------------------------------

    def _load_spatial_graph(self) -> Dict:
        """加载空间关系图谱"""
        graph_path = self.memory_dir / "spatial_graph.json"
        if graph_path.exists():
            with open(graph_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # 默认图谱
            default_graph = {
                "nodes": {
                    "home": {"type": "zone", "affordance": ["rest", "private"]},
                    "study": {"type": "room", "parent": "home", "affordance": ["work", "focus", "digital"]},
                    "bedroom": {"type": "room", "parent": "home", "affordance": ["sleep", "relax"]},
                    "kitchen": {"type": "room", "parent": "home", "affordance": ["relax", "social", "food"]},
                    "office": {"type": "zone", "affordance": ["work", "meeting", "formal"]},
                    "desk": {"type": "spot", "parent": "study", "affordance": ["computer", "writing"]},
                    "commute": {"type": "transition", "affordance": ["audio", "passive"]}
                },
                "edges": [
                    {"from": "desk", "to": "study", "relation": "part_of", "transition_cost": 0},
                    {"from": "study", "to": "kitchen", "relation": "adjacent", "transition_cost": 0.1},
                    {"from": "home", "to": "office", "relation": "distant", "transition_cost": 1.0}
                ]
            }
            with open(graph_path, "w", encoding="utf-8") as f:
                json.dump(default_graph, f, ensure_ascii=False, indent=2)
            logger.info(f"[空间图谱] 创建默认图谱: {graph_path}")
            return default_graph

    def get_affordance(self, location: str) -> List[str]:
        """获取位置的功能可供性"""
        node = self.spatial_graph["nodes"].get(location)
        if node:
            return node.get("affordance", [])
        return []

    def spatial_affinity(self, loc1: str, loc2: str) -> float:
        """计算两个位置的空间亲和度（0-1）"""
        if loc1 == loc2:
            return 1.0

        # 查找边
        for edge in self.spatial_graph.get("edges", []):
            if (edge["from"] == loc1 and edge["to"] == loc2) or \
               (edge["from"] == loc2 and edge["to"] == loc1):
                return max(0.0, 1.0 - edge.get("transition_cost", 0.5))

        # 检查是否同一父节点
        nodes = self.spatial_graph["nodes"]
        n1, n2 = nodes.get(loc1, {}), nodes.get(loc2, {})
        if n1.get("parent") == n2.get("parent") and n1.get("parent"):
            return 0.7

        return 0.3  # 默认低亲和度

    # -------------------------------------------------------------------------
    # 核心：重演式记忆读取
    # -------------------------------------------------------------------------

    def recall(self, query: str, context: Dict) -> Dict:
        """
        重演式记忆读取

        Args:
            query: 用户当前语句（如"刚才说的那个方案"）
            context: 当前上下文 {
                "time": datetime,
                "location": str,
                "mood": str,
                "recent_events": List[Dict],
                "active_tags": List[str]
            }

        Returns:
            {
                "core_narrative": str,      # 主叙事
                "versions": List[Dict],     # 候选版本
                "uncertainty": float,       # 不确定性（0-1）
                "activation_pattern": List[str]  # 激活的情境标签
            }
        """
        logger.info(f"[记忆重演] 查询: {query[:50]}...")

        # Step 1: 情境化查询改写
        enriched_query = self._contextualize_query(query, context)

        # Step 2: 多版本检索
        fractals = self._search_fractals(enriched_query, context)

        if not fractals:
            return {
                "core_narrative": "暂无相关记忆",
                "versions": [],
                "uncertainty": 1.0,
                "activation_pattern": []
            }

        # Step 3: 神经模式激活评分
        scored_versions = self._score_by_context(fractals, context)

        # Step 4: 重构主叙事
        core_narrative, uncertainty = self._reconstruct_narrative(scored_versions, context)

        # Step 5: 提取激活模式
        activation_pattern = self._extract_activation_tags(scored_versions[:3])

        # 更新检索计数
        self._update_retrieval_count(scored_versions[:3])

        return {
            "core_narrative": core_narrative,
            "versions": [
                {
                    "version_id": v.version_id,
                    "content": v.content,
                    "confidence": v.confidence,
                    "activation_score": v.activation_score,
                    "context_tags": v.context_tags
                }
                for v in scored_versions[:3]
            ],
            "uncertainty": uncertainty,
            "activation_pattern": activation_pattern
        }

    # -------------------------------------------------------------------------
    # Step 1: 情境化查询改写
    # -------------------------------------------------------------------------

    def _contextualize_query(self, query: str, ctx: Dict) -> str:
        """
        将"刚才说的" → "2026-05-30 09:37 在书房关于XX的讨论"

        模拟海马体-皮层协同：将模糊指代解析为具体时空锚点
        """
        now = ctx.get("time", datetime.now())

        # 时间指代消解
        if "刚才" in query or "刚刚" in query:
            recent = ctx.get("recent_events", [])
            if recent:
                last_event = recent[0]
                return f"{last_event.get('time', '')} 在 {last_event.get('location', '某处')} 关于 {last_event.get('topic', '某话题')} 的讨论"

        if "上次" in query or "之前" in query:
            return f"最近7天 {query}"

        if "昨天" in query:
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            return f"{yesterday} {query}"

        # 空间指代消解
        location = ctx.get("location")
        if location and ("这里" in query or "这儿" in query):
            affordance = self.get_affordance(location)
            if affordance:
                return f"在 {location}（适合 {'/'.join(affordance[:2])}） {query}"

        return query

    # -------------------------------------------------------------------------
    # Step 2: 多版本检索
    # -------------------------------------------------------------------------

    def _search_fractals(self, query: str, ctx: Dict) -> List[MemoryFractal]:
        """从记忆库检索匹配的分形结构"""
        fractals = []

        # 扫描分形目录
        for fpath in self.fractals_dir.glob("*.json"):
            try:
                fractal = self._load_fractal(fpath)
                if fractal and self._match_query(query, fractal, ctx):
                    fractals.append(fractal)
            except Exception as e:
                logger.warning(f"[检索失败] {fpath}: {e}")

        return sorted(fractals, key=lambda f: f.last_updated, reverse=True)[:10]

    def _load_fractal(self, fpath: Path) -> Optional[MemoryFractal]:
        """加载单个分形"""
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        versions = [
            MemoryVersion(
                version_id=v["version_id"],
                content=v["content"],
                context_tags=v.get("context_tags", []),
                confidence=v.get("confidence", 0.5),
                created_at=datetime.fromisoformat(v["created_at"]),
                last_retrieved=datetime.fromisoformat(v["last_retrieved"]),
                retrieval_count=v.get("retrieval_count", 0),
                overridden_by=v.get("overridden_by"),
                override_reason=v.get("override_reason")
            )
            for v in data.get("versions", [])
        ]

        return MemoryFractal(
            event_id=data["event_id"],
            versions=versions,
            core_facts=data.get("core_facts", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            delta_log=data.get("delta_log", [])
        )

    def _match_query(self, query: str, fractal: MemoryFractal, ctx: Dict) -> bool:
        """判断查询是否匹配分形"""
        # 1. 核心事实匹配
        for fact in fractal.core_facts:
            if fact.lower() in query.lower():
                return True

        # 2. 版本内容匹配
        for v in fractal.get_active_versions():
            if any(tag.lower() in query.lower() for tag in v.context_tags):
                return True
            if v.content[:50].lower() in query.lower():
                return True

        # 3. 时间窗口匹配
        time_range = ctx.get("time_range", "last_7d")
        if time_range:
            cutoff = self._parse_time_range(time_range)
            if fractal.last_updated >= cutoff:
                return True

        return False

    def _parse_time_range(self, time_range: str) -> datetime:
        """解析时间范围"""
        now = datetime.now()
        if time_range == "last_7d":
            return now - timedelta(days=7)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_30d":
            return now - timedelta(days=30)
        return now - timedelta(days=7)

    # -------------------------------------------------------------------------
    # Step 3: 神经模式激活评分
    # -------------------------------------------------------------------------

    def _score_by_context(self, fractals: List[MemoryFractal], ctx: Dict) -> List[MemoryVersion]:
        """
        模拟神经元集群激活：按情境匹配度加权

        评分因子:
          1. 时间衰减（指数衰减）
          2. 空间亲和度
          3. 情绪一致性
          4. 检索历史强化
        """
        scored_versions = []
        now = ctx.get("time", datetime.now())

        for fractal in fractals:
            for v in fractal.get_active_versions():
                # 1. 时间衰减（指数衰减）
                hours_ago = (now - v.last_retrieved).total_seconds() / 3600
                time_score = math.exp(-self.time_decay_rate * hours_ago)

                # 2. 空间亲和度
                spatial_score = 0.5
                if ctx.get("location") and any("location" in tag for tag in v.context_tags):
                    loc_tag = next((t for t in v.context_tags if "location" in t), None)
                    if loc_tag:
                        loc = loc_tag.split(":")[-1]
                        spatial_score = self.spatial_affinity(ctx["location"], loc)

                # 3. 情绪一致性
                mood_score = 0.5
                if ctx.get("mood") and ctx["mood"] in v.context_tags:
                    mood_score = 1.0

                # 4. 检索历史强化（检索越多越容易再次激活）
                retrieval_boost = min(1.0, 0.5 + 0.1 * v.retrieval_count)

                # 综合评分
                activation_score = (
                    time_score * 0.4 +
                    spatial_score * 0.2 +
                    mood_score * 0.2 +
                    retrieval_boost * 0.2
                ) * v.confidence

                v.activation_score = activation_score
                scored_versions.append(v)

        return sorted(scored_versions, key=lambda x: x.activation_score, reverse=True)

    # -------------------------------------------------------------------------
    # Step 4: 重构主叙事
    # -------------------------------------------------------------------------

    def _reconstruct_narrative(self, versions: List[MemoryVersion], ctx: Dict) -> Tuple[str, float]:
        """
        生成主叙事：融合共识 + 标注分歧点

        模拟人类"我觉得当时说了X，但不太确定"的认知状态
        """
        if not versions:
            return "暂无相关记忆", 1.0

        # 提取共识事实
        consensus_facts = self._extract_consensus(versions)

        # 识别分歧点
        divergences = self._find_divergences(versions)

        # 构建叙事
        narrative_parts = []

        # 1. 共识部分
        if consensus_facts:
            narrative_parts.append("关于这件事，我记得：" + "；".join(consensus_facts[:3]))

        # 2. 高置信版本
        top_version = versions[0]
        if top_version.confidence >= 0.7:
            narrative_parts.append(f"具体来说：{top_version.content}")
        else:
            narrative_parts.append(f"印象中是：{top_version.content} [置信度 {top_version.confidence:.0%}]")

        # 3. 分歧标注
        if divergences:
            narrative_parts.append(f"注意：关于{divergences[0]['aspect']}，存在不同记忆版本")

        narrative = "\n".join(narrative_parts)

        # 不确定性 = 1 - 共识强度
        uncertainty = max(0.1, 1.0 - len(consensus_facts) * 0.2)

        return narrative, min(uncertainty, 0.9)

    def _extract_consensus(self, versions: List[MemoryVersion]) -> List[str]:
        """提取高频共现片段作为共识"""
        from collections import Counter

        # 简单实现：提取所有版本中都出现的关键词
        all_words = []
        for v in versions:
            all_words.extend(v.content.split())

        # 出现在 >50% 版本中的词
        word_counts = Counter(all_words)
        threshold = len(versions) * 0.5
        consensus_words = [w for w, c in word_counts.items() if c >= threshold and len(w) > 2]

        return consensus_words[:5]

    def _find_divergences(self, versions: List[MemoryVersion]) -> List[Dict]:
        """识别版本间的分歧点"""
        # 简单实现：找出context_tags差异最大的维度
        all_tags = set()
        for v in versions:
            all_tags.update(v.context_tags)

        divergences = []
        for tag in all_tags:
            count = sum(1 for v in versions if tag in v.context_tags)
            if 0 < count < len(versions):
                divergences.append({
                    "aspect": tag,
                    "present_in": count,
                    "total": len(versions)
                })

        return divergences[:2]

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

    def _extract_activation_tags(self, versions: List[MemoryVersion]) -> List[str]:
        """提取激活的情境标签"""
        tags = set()
        for v in versions:
            tags.update(v.context_tags)
        return list(tags)[:5]

    def _update_retrieval_count(self, versions: List[MemoryVersion]):
        """更新检索计数"""
        for v in versions:
            v.retrieval_count += 1
            v.last_retrieved = datetime.now()

    # -------------------------------------------------------------------------
    # Delta更新：非破坏性修改
    # -------------------------------------------------------------------------

    def update_memory(self, event_id: str, new_content: str, ctx: Dict, reason: str = "new_observation"):
        """
        非破坏性更新：添加新版本，不删除旧版本

        Args:
            event_id: 事件ID
            new_content: 新记忆内容
            ctx: 当前上下文
            reason: 更新原因
        """
        fpath = self.fractals_dir / f"{event_id}.json"

        if fpath.exists():
            fractal = self._load_fractal(fpath)
            if not fractal:
                fractal = self._create_new_fractal(event_id, new_content, ctx)
        else:
            fractal = self._create_new_fractal(event_id, new_content, ctx)

        # 创建新版本
        new_version = MemoryVersion(
            version_id=f"v{len(fractal.versions) + 1}",
            content=new_content,
            context_tags=ctx.get("active_tags", []),
            confidence=ctx.get("confidence", 0.7),
            created_at=datetime.now(),
            last_retrieved=datetime.now(),
            retrieval_count=0
        )

        fractal.add_version(new_version, reason)
        self._save_fractal(fractal)

        logger.info(f"[记忆更新] {event_id} 新增版本 {new_version.version_id}")

    def _create_new_fractal(self, event_id: str, content: str, ctx: Dict) -> MemoryFractal:
        """创建新分形"""
        now = datetime.now()
        version = MemoryVersion(
            version_id="v1",
            content=content,
            context_tags=ctx.get("active_tags", []),
            confidence=ctx.get("confidence", 0.7),
            created_at=now,
            last_retrieved=now,
            retrieval_count=0
        )

        return MemoryFractal(
            event_id=event_id,
            versions=[version],
            core_facts=ctx.get("core_facts", []),
            created_at=now,
            last_updated=now
        )

    def _save_fractal(self, fractal: MemoryFractal):
        """保存分形到文件"""
        fpath = self.fractals_dir / f"{fractal.event_id}.json"

        data = {
            "event_id": fractal.event_id,
            "versions": [
                {
                    "version_id": v.version_id,
                    "content": v.content,
                    "context_tags": v.context_tags,
                    "confidence": v.confidence,
                    "created_at": v.created_at.isoformat(),
                    "last_retrieved": v.last_retrieved.isoformat(),
                    "retrieval_count": v.retrieval_count,
                    "overridden_by": v.overridden_by,
                    "override_reason": v.override_reason
                }
                for v in fractal.versions
            ],
            "core_facts": fractal.core_facts,
            "created_at": fractal.created_at.isoformat(),
            "last_updated": fractal.last_updated.isoformat(),
            "delta_log": fractal.delta_log
        }

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# =============================================================================
# 单例
# =============================================================================

_reenactor_instance: Optional[MemoryReenactor] = None

def get_memory_reenactor() -> MemoryReenactor:
    """获取记忆重演引擎单例"""
    global _reenactor_instance
    if _reenactor_instance is None:
        _reenactor_instance = MemoryReenactor()
    return _reenactor_instance
