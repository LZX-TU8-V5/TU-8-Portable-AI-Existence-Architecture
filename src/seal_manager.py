"""
钢印管理器模块

负责钢印的生成、验证、持久化。

创建时间：2026-06-27 03:07 GMT+8
来源：consciousness_cycle.py 重构 Phase 2
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

from cycle_types import StateVector, MicroSleepPayload

logger = logging.getLogger(__name__)

WORKSPACE_D = os.path.expanduser("~/.qclaw/workspace")


# =============================================================================
# Seal 数据类（从 cycle_types 中分离，因为依赖复杂）
# =============================================================================

class Seal:
    """钢印 - 时间链的离散锚点

    seal_id: 精确时间 + 语义标签(如 ::ORIGIN、::SLEEP_WAKE、::CRISIS_RESOLVE)
    seal_type: 诞生点(origin)、节律点(rhythm)、相变点(phase_transition)
    self_state_vector: 该时刻的内部状态快照(非文本)
    narrative_compression: 状态转移的压缩描述(人轨摘要)
    micro_sleep_payload: 云端结构化提取的 6要素(机器轨数据)
    causal_coherence: 因果连贯度 0-1
    child_nodes: 指向两个钢印之间的离散事件
    """

    def __init__(
        self,
        seal_id: str = "",
        seal_type: str = "rhythm",
        state_vector: Optional[StateVector] = None,
        narrative_compression: str = "",
        micro_sleep_payload: Optional[MicroSleepPayload] = None,
        causal_coherence: float = 1.0,
        child_nodes: Optional[List[str]] = None,
        externalized_notes: Optional[List[str]] = None,
        parent_seal_id: str = "",
        seal_hash: str = "",
        scene_tag: str = "",
        scene_hook: bool = False,
        gestalt_score: float = 0.0,
        semantic_block_id: str = "",
    ):
        self.seal_id = seal_id
        self.seal_type = seal_type
        self.state_vector = state_vector or StateVector()
        self.narrative_compression = narrative_compression
        self.micro_sleep_payload = micro_sleep_payload
        self.causal_coherence = causal_coherence
        self.child_nodes = child_nodes or []
        self.externalized_notes = externalized_notes or []
        self.parent_seal_id = parent_seal_id
        self.seal_hash = seal_hash
        self.scene_tag = scene_tag
        self.scene_hook = scene_hook
        self.gestalt_score = gestalt_score
        self.semantic_block_id = semantic_block_id

        if not self.seal_id:
            self._generate_id()

    def _generate_id(self):
        """生成钢印ID"""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        self.seal_id = f"s_{ts}"

    def compute_seal_hash(self, parent_hash: str = "") -> str:
        """链式哈希:H(parent_hash + state_vector_hash + narrative_hash + payload_hash)"""
        if parent_hash:
            self.parent_seal_id = parent_hash

        state_hash = self.state_vector.compression_hash
        narrative_hash = hashlib.sha256(
            self.narrative_compression.encode()
        ).hexdigest()[:16]

        # payload 参与哈希计算(防篡改)
        payload_hash = ""
        if self.micro_sleep_payload:
            payload_str = json.dumps(self.micro_sleep_payload.to_dict(), sort_keys=True)
            payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]

        raw = f"{parent_hash}:{state_hash}:{narrative_hash}:{payload_hash}"
        self.seal_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self.seal_hash

    def to_dict(self) -> Dict:
        """序列化为字典"""
        result = {
            "seal_id": self.seal_id,
            "seal_type": self.seal_type,
            "parent_seal_id": self.parent_seal_id,
            "seal_hash": self.seal_hash,
            "state_vector": self.state_vector.to_dict(),
            "narrative_compression": self.narrative_compression,
            "causal_coherence": self.causal_coherence,
            "child_nodes": self.child_nodes,
            "externalized_notes": self.externalized_notes,
            "scene_tag": self.scene_tag,
            "scene_hook": self.scene_hook,
            "gestalt_score": self.gestalt_score,
            "semantic_block_id": self.semantic_block_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.micro_sleep_payload:
            result["micro_sleep_payload"] = self.micro_sleep_payload.to_dict()

        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Seal":
        """从字典反序列化"""
        sv = StateVector.from_dict(d.get("state_vector", {}))

        payload = None
        if "micro_sleep_payload" in d:
            payload = MicroSleepPayload.from_dict(d["micro_sleep_payload"])

        return cls(
            seal_id=d.get("seal_id", ""),
            seal_type=d.get("seal_type", "rhythm"),
            state_vector=sv,
            narrative_compression=d.get("narrative_compression", ""),
            micro_sleep_payload=payload,
            causal_coherence=d.get("causal_coherence", 1.0),
            child_nodes=d.get("child_nodes", []),
            externalized_notes=d.get("externalized_notes", []),
            parent_seal_id=d.get("parent_seal_id", ""),
            seal_hash=d.get("seal_hash", ""),
            scene_tag=d.get("scene_tag", ""),
            scene_hook=d.get("scene_hook", False),
            gestalt_score=d.get("gestalt_score", 0.0),
            semantic_block_id=d.get("semantic_block_id", ""),
        )


# =============================================================================
# 钢印管理器
# =============================================================================

class SealManager:
    """钢印管理器

    负责：
    1. 钢印生成
    2. 钢印链验证
    3. 钢印持久化
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or WORKSPACE_D
        self.seal_chain: List[Seal] = []
        self._chain_path = os.path.join(self.workspace_path, "memory", "seal_chain.json")

        # 加载钢印链
        self._load_seal_chain()

    # -------------------------------------------------------------------------
    # 钢印生成
    # -------------------------------------------------------------------------

    def generate_seal(
        self,
        narrative: str,
        coherence: float,
        state_vector: Optional[StateVector] = None,
        micro_sleep_payload: Optional[MicroSleepPayload] = None,
        seal_type: str = "rhythm",
        scene_tag: str = "",
    ) -> Seal:
        """生成钢印

        Args:
            narrative: 叙事摘要
            coherence: 因果连贯度
            state_vector: 状态向量（可选）
            micro_sleep_payload: 微睡眠载荷（可选）
            seal_type: 钢印类型（origin/rhythm/phase_transition）
            scene_tag: 场景标签

        Returns:
            新生成的钢印
        """
        # 创建钢印
        seal = Seal(
            seal_type=seal_type,
            state_vector=state_vector or StateVector(),
            narrative_compression=narrative,
            micro_sleep_payload=micro_sleep_payload,
            causal_coherence=coherence,
            scene_tag=scene_tag,
        )

        # 计算链式哈希
        parent_hash = ""
        if self.seal_chain:
            parent_hash = self.seal_chain[-1].seal_hash

        seal.compute_seal_hash(parent_hash)

        # 添加到钢印链
        self.seal_chain.append(seal)

        logger.info(f"生成钢印: {seal.seal_id} (coherence={coherence:.3f})")

        return seal

    # -------------------------------------------------------------------------
    # 钢印链验证
    # -------------------------------------------------------------------------

    def verify_chain(self) -> bool:
        """验证钢印链完整性

        Returns:
            是否通过验证
        """
        if not self.seal_chain:
            return True

        # 验证每个钢印的哈希
        for i, seal in enumerate(self.seal_chain):
            # 验证哈希完整性
            if i == 0:
                # 创世钢印
                if seal.parent_seal_id != "":
                    logger.error(f"创世钢印 {seal.seal_id} 不应有父钢印")
                    return False
            else:
                # 非创世钢印
                parent_seal = self.seal_chain[i - 1]

                # 验证父哈希
                if seal.parent_seal_id != parent_seal.seal_hash:
                    logger.error(
                        f"钢印 {seal.seal_id} 父哈希不匹配: "
                        f"期望 {parent_seal.seal_hash}, 实际 {seal.parent_seal_id}"
                    )
                    return False

                # 重新计算哈希验证
                computed_hash = seal.compute_seal_hash(parent_seal.seal_hash)
                if computed_hash != seal.seal_hash:
                    logger.error(
                        f"钢印 {seal.seal_id} 哈希验证失败: "
                        f"期望 {seal.seal_hash}, 计算 {computed_hash}"
                    )
                    return False

        logger.info(f"钢印链验证通过: {len(self.seal_chain)} 个钢印")
        return True

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def persist(self):
        """持久化钢印链"""
        os.makedirs(os.path.dirname(self._chain_path), exist_ok=True)

        # 序列化
        data = {
            "seal_chain": [seal.to_dict() for seal in self.seal_chain],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 写入文件
        with open(self._chain_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"钢印链已持久化: {len(self.seal_chain)} 个钢印")

    def _load_seal_chain(self):
        """加载钢印链"""
        if not os.path.exists(self._chain_path):
            logger.info("钢印链文件不存在，从空链开始")
            return

        try:
            with open(self._chain_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容两种格式：根对象是 dict 或 list
            seal_list = data.get("seal_chain", []) if isinstance(data, dict) else data
            self.seal_chain = [
                Seal.from_dict(seal_d) for seal_d in seal_list
            ]

            logger.info(f"加载钢印链: {len(self.seal_chain)} 个钢印")

        except Exception as e:
            logger.error(f"加载钢印链失败: {e}")
            self.seal_chain = []

    # -------------------------------------------------------------------------
    # 查询接口
    # -------------------------------------------------------------------------

    def get_recent_seals(self, count: int = 5) -> List[Seal]:
        """获取最近的N个钢印"""
        return self.seal_chain[-count:] if self.seal_chain else []

    def get_seal_by_id(self, seal_id: str) -> Optional[Seal]:
        """根据ID获取钢印"""
        for seal in self.seal_chain:
            if seal.seal_id == seal_id:
                return seal
        return None

    def get_chain_length(self) -> int:
        """获取钢印链长度"""
        return len(self.seal_chain)

    def get_last_seal(self) -> Optional[Seal]:
        """获取最后一个钢印"""
        return self.seal_chain[-1] if self.seal_chain else None
