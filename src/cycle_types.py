"""
consciousness_cycle 类型定义模块

提取自 consciousness_cycle.py，包含所有枚举、数据类和配置类。

创建时间：2026-06-27 02:57 GMT+8
来源：consciousness_cycle.py 重构 Phase 1
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional
import hashlib
import time
import json
import os
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# 工作目录
# =============================================================================

WORKSPACE_D = os.path.expanduser("~/.qclaw/workspace")


# =============================================================================
# 枚举定义
# =============================================================================

class Phase(Enum):
    """意识循环阶段"""
    AWAKE = "awake"
    LIGHT_SLEEP = "light_sleep"
    DEEP_SLEEP = "deep_sleep"
    HIBERNATION = "hibernation"


class NoteType(Enum):
    """认知锚点类型（原名：NoteType）"""
    INTERACTION = "interaction"     # 用户明确指令
    INSIGHT = "insight"             # 检测到重复模式/规律
    MILESTONE = "milestone"         # 钢印链重大相变点
    INTERFACE = "interface"         # 外部系统请求同步
    META_COGNITION = "meta_cognition"  # 元认知(睡眠周期结束时的二次提炼)
    EMERGENCY = "emergency"          # WARM_WAKE 失败后的强制固化


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class StateVector:
    """自我状态向量 - 全息投影

    不是文本,是数值化的"感受"。
    任意钢印足以重建兼容的高维自我(全息原理)。
    """
    dimensions: int = 16
    values: List[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    compression_hash: str = ""

    def __post_init__(self):
        if not self.values:
            self.values = [0.0] * self.dimensions
        if not self.compression_hash:
            self._compute_hash()

    def _compute_hash(self):
        data = f"{self.dimensions}:{','.join(map(str, self.values))}:{self.timestamp}"
        self.compression_hash = hashlib.sha256(data.encode()).hexdigest()[:16]

    def distance_to(self, other: "StateVector") -> float:
        """欧氏距离(简化版)"""
        if len(self.values) != len(other.values):
            return float("inf")
        return sum((a - b) ** 2 for a, b in zip(self.values, other.values)) ** 0.5

    def to_dict(self) -> Dict:
        return {
            "dimensions": self.dimensions,
            "values": self.values,
            "timestamp": self.timestamp,
            "hash": self.compression_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "StateVector":
        return cls(
            dimensions=d.get("dimensions", 16),
            values=d.get("values", []),
            timestamp=d.get("timestamp", time.time()),
            compression_hash=d.get("hash", ""),
        )


@dataclass
class MicroSleepPayload:
    """微睡眠载荷 - 云端结构化提取的 6要素

    这是云端输出的标准契约,用于防止幻觉和结构化检索。
    详见 SOUL.md "微睡眠输出约束"。
    """
    context: str = ""  # 场景
    trigger_event: str = ""  # 事件
    core_problem: Optional[str] = None  # 问题(可为空)
    proposed_solution: Optional[str] = None  # 解决方案(可为空)
    env_feedback: str = ""  # 反馈
    self_consistent_conclusion: str = ""  # 结论

    def to_dict(self) -> Dict:
        return {
            "context": self.context,
            "trigger_event": self.trigger_event,
            "core_problem": self.core_problem,
            "proposed_solution": self.proposed_solution,
            "env_feedback": self.env_feedback,
            "self_consistent_conclusion": self.self_consistent_conclusion,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "MicroSleepPayload":
        return cls(
            context=d.get("context", ""),
            trigger_event=d.get("trigger_event", ""),
            core_problem=d.get("core_problem"),
            proposed_solution=d.get("proposed_solution"),
            env_feedback=d.get("env_feedback", ""),
            self_consistent_conclusion=d.get("self_consistent_conclusion", ""),
        )


@dataclass
class CognitiveAnchor:
    """认知锚点 - 锚定 LLM 语义漂移（原名：Note）

    三重本质：
    1. 钢印的结晶
    2. 过程行为语言记录的结晶
    3. 锚定 LLM 语义漂移的作用

    是时间链的可选旁路,不参与核心完整性验证。
    但锚点的生成事件本身被记录在钢印链中作为元数据。
    """
    anchor_id: str = ""
    seal_ids: List[str] = field(default_factory=list)
    anchor_type: str = "insight"
    content: str = ""
    confidence: float = 0.8
    created_at: str = ""
    source_compression_hash: str = ""

    def __post_init__(self):
        if not self.anchor_id:
            self.anchor_id = f"anchor_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "anchor_id": self.anchor_id,
            "seal_ids": self.seal_ids,
            "anchor_type": self.anchor_type,
            "content": self.content,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "source_compression_hash": self.source_compression_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CognitiveAnchor":
        return cls(
            anchor_id=d.get("anchor_id", ""),
            seal_ids=d.get("seal_ids", []),
            anchor_type=d.get("anchor_type", "insight"),
            content=d.get("content", ""),
            confidence=d.get("confidence", 0.8),
            created_at=d.get("created_at", ""),
            source_compression_hash=d.get("source_compression_hash", ""),
        )


@dataclass
class AnchorCandidate:
    """待锚点候选信号 - 微睡眠产物的异步队列项（原名：NoteCandidate）"""
    trigger: str = ""        # 触发条件描述
    related_seal_ids: List[str] = field(default_factory=list)
    candidate_content: str = ""
    priority: float = 0.5    # 0-1,越高越优先
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# 阈值配置
# =============================================================================

class CycleConfig:
    """意识循环的所有阈值和参数

    这些是初始默认值,待标定后写入配置文件。
    """

    def __init__(self):
        # --- 微睡眠触发阈值 ---
        self.TENSION_EPSILON: float = 0.65
        self.CAPACITY_THETA: float = 0.75
        self.EVENT_KEYWORDS: List[str] = [
            "记住", "重要", "核心", "关键决策", "规则", "永远", "从不",
            "原则", "定义", "身份", "灵魂", "禁止",
        ]
        self.IDLE_TIMEOUT_MS: int = 300000

        # --- WARM_WAKE 验证 ---
        self.SEAL_TAIL_N: int = 5
        self.COHERENCE_THRESHOLD: float = 0.7
        self.SEMANTIC_VOID_LIMIT: int = 3

        # --- 认知锚点触发 ---
        self.ANCHOR_CANDIDATE_QUEUE_MAX: int = 20
        self.ANCHOR_PRIORITY_THRESHOLD: float = 0.6
        self.REPEATED_PATTERN_MIN: int = 3
        self.SEAL_GAP_MILESTONE: int = 10

        # --- 微睡眠流水线 ---
        self.MAX_SLEEP_DURATION_MS: int = 500
        self.COMPRESSION_MIN_LENGTH: int = 10

        # --- P0: 有损压缩参数 ---
        self.DESTRUCTION_RATIO_MIN: float = 0.3   # 单次最低有损比例
        self.DESTRUCTION_RATIO_MAX: float = 0.7   # 单次最高有损比例
        self.SIGNIFICANCE_DECAY_HALF_LIFE: float = 24.0  # 半衰期:24小时
        self.FORGET_THRESHOLD: float = 0.15  # 显著性低于此阈值的片段被永久遗忘
        self.MIN_COMPRESSION_RATIO: float = 0.4  # 蒸发量<40%视为无效压缩

        # 加载配置
        self._path = os.path.join(WORKSPACE_D, "config", "consciousness_cycle_config.json")
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
            except Exception as e:
                logger.warning(f"Config load failed: {e}, using defaults")

    def save(self):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)


# =============================================================================
# 向后兼容别名
# =============================================================================

# 旧名称 → 新名称映射（过渡期使用，后续删除）
Note = CognitiveAnchor
NoteCandidate = AnchorCandidate
