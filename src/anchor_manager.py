"""
认知锚点管理器

负责认知锚点的生成、管理和持久化。

创建时间：2026-06-27 03:30 GMT+8
来源：consciousness_cycle.py 重构 Phase 3
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

from cycle_types import CognitiveAnchor, AnchorCandidate

logger = logging.getLogger(__name__)

WORKSPACE_D = os.path.expanduser("~/.qclaw/workspace")


class AnchorManager:
    """认知锚点管理器

    负责：
    1. 锚点候选队列管理
    2. 锚点生成与固化
    3. 锚点持久化
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or WORKSPACE_D
        self.anchors: List[CognitiveAnchor] = []
        self.candidates: List[AnchorCandidate] = []
        self._anchors_path = os.path.join(self.workspace_path, "memory", "anchors.json")

        # 配置
        self.candidate_queue_max = 20
        self.priority_threshold = 0.6

        # 加载锚点
        self._load_anchors()

    # -------------------------------------------------------------------------
    # 候选队列管理
    # -------------------------------------------------------------------------

    def enqueue_candidate(
        self,
        trigger: str,
        related_seal_ids: List[str],
        content: str,
        priority: float = 0.5
    ) -> bool:
        """将锚点候选加入队列

        Args:
            trigger: 触发条件
            related_seal_ids: 相关钢印ID列表
            content: 候选内容
            priority: 优先级（0-1）

        Returns:
            是否成功加入
        """
        # 创建候选
        candidate = AnchorCandidate(
            trigger=trigger,
            related_seal_ids=related_seal_ids,
            candidate_content=content,
            priority=priority
        )

        self.candidates.append(candidate)
        logger.info(f"锚点候选入队: {trigger} (priority={priority:.2f})")

        # 检查队列是否已满，清理低优先级候选
        if len(self.candidates) > self.candidate_queue_max:
            self._cleanup_candidates()

        return True

    def _cleanup_candidates(self):
        """清理候选队列（保留高优先级）"""
        if not self.candidates:
            return

        # 按优先级排序
        self.candidates.sort(key=lambda c: c.priority, reverse=True)

        # 保留前 candidate_queue_max 个
        removed = len(self.candidates) - self.candidate_queue_max
        if removed > 0:
            self.candidates = self.candidates[:self.candidate_queue_max]
            logger.info(f"清理低优先级候选: {removed} 个")

    def get_candidates(self, count: int = 5) -> List[AnchorCandidate]:
        """获取候选队列

        Args:
            count: 获取数量

        Returns:
            候选列表（按优先级排序）
        """
        self.candidates.sort(key=lambda c: c.priority, reverse=True)
        return self.candidates[:count]

    def consume_candidate(self, index: int = 0) -> Optional[AnchorCandidate]:
        """消费候选（从队列移除）

        Args:
            index: 候选索引（默认消费最高优先级）

        Returns:
            被消费的候选
        """
        if not self.candidates or index >= len(self.candidates):
            return None

        candidate = self.candidates.pop(index)
        logger.info(f"消费锚点候选: {candidate.trigger}")
        return candidate

    # -------------------------------------------------------------------------
    # 锚点生成
    # -------------------------------------------------------------------------

    def create_anchor(
        self,
        content: str,
        anchor_type: str = "insight",
        confidence: float = 0.8,
        seal_ids: Optional[List[str]] = None,
        source_hash: str = ""
    ) -> CognitiveAnchor:
        """创建认知锚点

        Args:
            content: 锚点内容
            anchor_type: 锚点类型（interaction/insight/milestone/interface/meta_cognition/emergency）
            confidence: 置信度
            seal_ids: 相关钢印ID列表
            source_hash: 源压缩哈希

        Returns:
            新创建的锚点
        """
        # 创建锚点
        anchor = CognitiveAnchor(
            seal_ids=seal_ids or [],
            anchor_type=anchor_type,
            content=content,
            confidence=confidence,
            source_compression_hash=source_hash
        )

        # 添加到列表
        self.anchors.append(anchor)

        # 持久化
        self._persist()

        logger.info(f"创建认知锚点: {anchor.anchor_id} (type={anchor_type})")

        return anchor

    def create_from_candidate(
        self,
        candidate: AnchorCandidate,
        anchor_type: str = "insight",
        confidence: float = 0.8
    ) -> CognitiveAnchor:
        """从候选创建锚点

        Args:
            candidate: 锚点候选
            anchor_type: 锚点类型
            confidence: 置信度

        Returns:
            新创建的锚点
        """
        return self.create_anchor(
            content=candidate.candidate_content,
            anchor_type=anchor_type,
            confidence=confidence,
            seal_ids=candidate.related_seal_ids
        )

    # -------------------------------------------------------------------------
    # 触发检查
    # -------------------------------------------------------------------------

    def should_externalize(
        self,
        seal_chain_length: int,
        last_seal_coherence: float,
        milestone_gap: int = 10
    ) -> Optional[Dict]:
        """检查是否应该外化锚点

        Args:
            seal_chain_length: 钢印链长度
            last_seal_coherence: 最后钢印的连贯度
            milestone_gap: 里程碑间隔

        Returns:
            触发信息或 None
        """
        # 条件 1：候选队列已满
        if len(self.candidates) >= self.candidate_queue_max:
            return {"trigger": "queue_full", "priority": 1.0}

        # 条件 2：钢印链里程碑
        if seal_chain_length > 0 and seal_chain_length % milestone_gap == 0:
            return {
                "trigger": "milestone",
                "priority": 0.8,
                "seal_count": seal_chain_length
            }

        # 条件 3：低连贯度
        if last_seal_coherence < 0.5:
            return {
                "trigger": "low_coherence",
                "priority": 0.9,
                "coherence": last_seal_coherence
            }

        return None

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def _persist(self):
        """持久化锚点"""
        os.makedirs(os.path.dirname(self._anchors_path), exist_ok=True)

        # 序列化
        data = {
            "anchors": [anchor.to_dict() for anchor in self.anchors],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # 写入文件
        with open(self._anchors_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"锚点已持久化: {len(self.anchors)} 个")

    def _load_anchors(self):
        """加载锚点"""
        if not os.path.exists(self._anchors_path):
            logger.info("锚点文件不存在，从空开始")
            return

        try:
            with open(self._anchors_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.anchors = [
                CognitiveAnchor.from_dict(anchor_d)
                for anchor_d in data.get("anchors", [])
            ]

            logger.info(f"加载锚点: {len(self.anchors)} 个")

        except Exception as e:
            logger.error(f"加载锚点失败: {e}")
            self.anchors = []

    # -------------------------------------------------------------------------
    # 查询接口
    # -------------------------------------------------------------------------

    def get_anchor_by_id(self, anchor_id: str) -> Optional[CognitiveAnchor]:
        """根据ID获取锚点"""
        for anchor in self.anchors:
            if anchor.anchor_id == anchor_id:
                return anchor
        return None

    def get_anchors_by_type(self, anchor_type: str) -> List[CognitiveAnchor]:
        """根据类型获取锚点"""
        return [a for a in self.anchors if a.anchor_type == anchor_type]

    def get_recent_anchors(self, count: int = 5) -> List[CognitiveAnchor]:
        """获取最近的锚点"""
        return self.anchors[-count:] if self.anchors else []

    def get_total_count(self) -> int:
        """获取锚点总数"""
        return len(self.anchors)

    def get_candidate_count(self) -> int:
        """获取候选数量"""
        return len(self.candidates)
