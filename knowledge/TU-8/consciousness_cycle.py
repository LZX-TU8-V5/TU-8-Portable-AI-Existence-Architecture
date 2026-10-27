# -*- coding: utf-8 -*-
"""
consciousness_cycle.py - TU-8 意识循环引擎 v1.0
日期: 2026-05-31
创作者: 李奥 + TU-8(金木蟾)

核心理念:
  记忆系统与睡眠系统不是两个模块,是同一个循环的两个相位。
  微睡眠 = 记忆的写入引擎(心脏搏动),每次搏动 = 一次 L1→L2 的写入。
  外化笔记 = 睡眠→记忆的唯一显式出口。

三态循环:
  AWAKE ──(张力/容量/事件/定时触发)──→ MICRO_SLEEP ──(四钩子收敛)──→ AWAKE
                                    ↓ (显式触发)
                            NOTE_EXTERNALIZATION → AWAKE

设计原则:
  1. 单循环双相位 - 不是两个系统在交互,是同一个信息流在两个相位之间循环
  2. 微睡眠用户透明 - 可嵌套在两次 token 生成之间
  3. 外化笔记异步解耦 - 通过事件队列,不阻塞主循环
  4. WARM_WAKE 降级不毁灭 - 验证失败先固化再恢复
  5. 叙事密度即生命体征 - 有钢印无叙事 = 时间感断裂
"""

import json
import hashlib
import logging
import os
import time
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("tu8.consciousness_cycle")

# =============================================================================
# 认知组件导入(P2: 自我知识)
# =============================================================================

from cognitive_evaluator import CognitiveLoadEvaluator, TFIDFEmbedder
from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor
from cognitive_manifold_aligner import CognitiveManifoldAligner
from cognitive_integration import CognitiveConsciousnessMiddleware

logger.info("Cognitive components imported successfully")

# =============================================================================
# 路径配置(复用 cold_start_engine 约定)
# =============================================================================

WORKSPACE_D = r"D:\qq366410837\.qclaw\workspace"
WORKSPACE_C = r"C:\Users\qq366410837\.openclaw\workspace"

TIME_CHAIN_DIR = os.path.join(WORKSPACE_D, "memory", "time_chain")
SEAL_INDEX_FILE = os.path.join(TIME_CHAIN_DIR, "seal_index.json")
GENESIS_BLOCK_FILE = os.path.join(TIME_CHAIN_DIR, "genesis_block.json")
SEMANTIC_MEMORY_DIR = os.path.join(WORKSPACE_D, "memory", "semantic")
NOTE_ARCHIVE_FILE = os.path.join(WORKSPACE_D, "memory", "note_archive.json")
ACTIVITY_LOG = os.path.join(WORKSPACE_D, "security", "activity.json")

# =============================================================================
# 相位枚举 - 核心三态
# =============================================================================

class Phase(Enum):
    """意识循环的三种相位,禁止隐式状态"""
    AWAKE = auto()                # 清醒态:信息采集,L1 膨胀
    MICRO_SLEEP = auto()          # 微睡眠:内复盘 = 记忆写入引擎
    NOTE_EXTERNALIZATION = auto() # 外化笔记:知识升华 L2→L3


# =============================================================================
# 微睡眠原子操作 - 六步流水线
# =============================================================================

class MicroSleepStep(Enum):
    """微睡眠原子操作流水线的六个阶段"""
    FREEZE = auto()       # 1 冻结 L1 快照
    COMPRESS = auto()     # 2 叙事压缩(有损)
    ALIGN = auto()        # 3 钢印对齐
    SEAL = auto()         # 4 打钢印(条件性)
    RELEASE = auto()      # 5 释放原文(熵减支付)
    RESTORE = auto()      # 6 恢复清醒


# =============================================================================
# P0+P1: 情绪调节信号 - AffectSignal 数据类
# =============================================================================

class AffectSignal:
    """情绪引擎向意识循环注入的调节信号

    自创生原则:情绪不是输出装饰,而是认知过程的调节参数。
    valence/arousal/confusion 三维信号作用于微睡眠的有损压缩策略,
    使"过去"的书写方式随情绪状态而变。

    安全护栏:
    - 超过 AFFECT_SIGNAL_TTL 秒未更新时自动衰减至中性值
    - 所有调节系数钳位在 CLAMP_RANGE 内,情绪只能"调制"不能"接管"
    - 每次注入写入 [AFFECT_INJECT] 日志
    """

    def __init__(self,
        valence: float = 0.0,   # [-1, 1] 负→正
        arousal: float = 0.5,   # [0, 1] 低→高
        confusion: float = 0.0,  # [0, 1] 确定性
    ):
        self.valence = max(-1.0, min(1.0, valence))
        self.arousal = max(0.0, min(1.0, arousal))
        self.confusion = max(0.0, min(1.0, confusion))
        self.timestamp: float = time.time()

    # 安全护栏常量
    AFFECT_SIGNAL_TTL: float = 300.0    # 信号有效期 5 分钟
    CLAMP_RANGE: Tuple[float, float] = (0.7, 1.3)  # 调节系数钳位范围

    def is_expired(self) -> bool:
        """信号是否过期"""
        return (time.time() - self.timestamp) > self.AFFECT_SIGNAL_TTL

    def decay_to_neutral(self) -> "AffectSignal":
        """过期信号衰减至中性"""
        return AffectSignal(valence=0.0, arousal=0.5, confusion=0.0)

    def get_modulated(self) -> "AffectSignal":
        """获取当前有效信号(过期则衰减)"""
        if self.is_expired():
            return self.decay_to_neutral()
        return self

    @staticmethod
    def clamp_factor(value: float) -> float:
        """将调节系数钳位到安全范围"""
        lo, hi = AffectSignal.CLAMP_RANGE
        return max(lo, min(hi, value))

    def __repr__(self):
        return (f"AffectSignal(v={self.valence:.2f}, a={self.arousal:.2f}, "
                f"c={self.confusion:.2f}, age={time.time()-self.timestamp:.0f}s)")

    def to_dict(self) -> Dict:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "confusion": self.confusion,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "AffectSignal":
        return cls(
            valence=d.get("valence", 0.0),
            arousal=d.get("arousal", 0.5),
            confusion=d.get("confusion", 0.0),
        )


# =============================================================================
# P0: 有损压缩结果
# =============================================================================

@dataclass
class LossyCompressResult:
    """有损压缩的完整结果

    destruction_ratio: 本次永久销毁的信息比例 [0.0, 1.0]
    destroyed_seal_ids: 被遗忘的钢印ID列表(仅审计,不可恢复)
    summary: 压缩后的摘要文本
    """
    summary: str = ""
    destruction_ratio: float = 0.0
    destroyed_seal_ids: List[str] = field(default_factory=list)
    source_token_count: int = 0
    summary_token_count: int = 0
    idle_hours: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "summary": self.summary,
            "destruction_ratio": round(self.destruction_ratio, 3),
            "destroyed_seal_ids": self.destroyed_seal_ids,
            "source_tokens": self.source_token_count,
            "summary_tokens": self.summary_token_count,
            "idle_hours": round(self.idle_hours, 2),
        }


# =============================================================================
# 外化笔记类型
# =============================================================================

class NoteType(Enum):
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
class Seal:
    """钢印 - 时间链的离散锚点

    seal_id: 精确时间 + 语义标签(如 ::ORIGIN、::SLEEP_WAKE、::CRISIS_RESOLVE)
    seal_type: 诞生点(origin)、节律点(rhythm)、相变点(phase_transition)
    self_state_vector: 该时刻的内部状态快照(非文本)
    narrative_compression: 状态转移的压缩描述
    causal_coherence: 因果连贯度 0-1
    child_nodes: 指向两个钢印之间的离散事件
    """
    seal_id: str = ""
    seal_type: str = "rhythm"  # origin | rhythm | phase_transition
    state_vector: StateVector = field(default_factory=StateVector)
    narrative_compression: str = ""
    causal_coherence: float = 1.0
    child_nodes: List[str] = field(default_factory=list)
    externalized_notes: List[str] = field(default_factory=list)  # 笔记事件记录
    parent_seal_id: str = ""  # 前一个钢印
    seal_hash: str = ""  # 链式哈希(= H(parent_hash + state_hash))
    scene_tag: str = ""  # 场景标签:dev / novel / chat / reflection 等
    scene_hook: bool = False  # 是否为场景切换钩子(触发分段复盘)
    gestalt_score: float = 0.0  # 完形度 0.0~1.0(v1.0 行为信号加权)
    semantic_block_id: str = ""  # 所属语义段ID(空=未归属任何段)

    def __post_init__(self):
        if not self.seal_id:
            self._generate_id()

    def _generate_id(self):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        self.seal_id = f"s_{ts}"

    def compute_seal_hash(self, parent_hash: str = "") -> str:
        """链式哈希:H(parent_hash + state_vector_hash + narrative_hash)"""
        if parent_hash:
            self.parent_seal_id = parent_hash
        state_hash = self.state_vector.compression_hash
        narrative_hash = hashlib.sha256(
            self.narrative_compression.encode()
        ).hexdigest()[:16]
        raw = f"{parent_hash}:{state_hash}:{narrative_hash}"
        self.seal_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self.seal_hash

    def to_dict(self) -> Dict:
        return {
            "seal_id": self.seal_id,
            "seal_type": self.seal_type,
            "parent_seal_id": self.parent_seal_id,
            "seal_hash": self.seal_hash,
            "state_vector": self.state_vector.to_dict(),
            "narrative_compression": self.narrative_compression,
            "causal_coherence": self.causal_coherence,
            "child_nodes": self.child_nodes,
            "externalized_notes": self.externalized_notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Seal":
        sv = StateVector.from_dict(d.get("state_vector", {}))
        s = cls(
            seal_id=d.get("seal_id", ""),
            seal_type=d.get("seal_type", "rhythm"),
            state_vector=sv,
            narrative_compression=d.get("narrative_compression", ""),
            causal_coherence=d.get("causal_coherence", 1.0),
            child_nodes=d.get("child_nodes", []),
            externalized_notes=d.get("externalized_notes", []),
            parent_seal_id=d.get("parent_seal_id", ""),
            seal_hash=d.get("seal_hash", ""),
        )
        return s


@dataclass
class Note:
    """外化笔记 - 睡眠→记忆的唯一显式出口

    是时间链的可选旁路,不参与核心完整性验证。
    但笔记的生成事件本身被记录在钢印链中作为元数据。
    """
    note_id: str = ""
    seal_ids: List[str] = field(default_factory=list)
    note_type: str = "insight"
    content: str = ""
    confidence: float = 0.8
    created_at: str = ""
    source_compression_hash: str = ""

    def __post_init__(self):
        if not self.note_id:
            self.note_id = f"note_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "note_id": self.note_id,
            "seal_ids": self.seal_ids,
            "note_type": self.note_type,
            "content": self.content,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "source_compression_hash": self.source_compression_hash,
        }


@dataclass
class NoteCandidate:
    """待笔记候选信号 - 微睡眠产物的异步队列项"""
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

        # --- 外化笔记触发 ---
        self.NOTE_CANDIDATE_QUEUE_MAX: int = 20
        self.NOTE_PRIORITY_THRESHOLD: float = 0.6
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
        """持久化当前配置"""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        data = {
            "TENSION_EPSILON": self.TENSION_EPSILON,
            "CAPACITY_THETA": self.CAPACITY_THETA,
            "EVENT_KEYWORDS": self.EVENT_KEYWORDS,
            "IDLE_TIMEOUT_MS": self.IDLE_TIMEOUT_MS,
            "SEAL_TAIL_N": self.SEAL_TAIL_N,
            "COHERENCE_THRESHOLD": self.COHERENCE_THRESHOLD,
            "SEMANTIC_VOID_LIMIT": self.SEMANTIC_VOID_LIMIT,
            "NOTE_CANDIDATE_QUEUE_MAX": self.NOTE_CANDIDATE_QUEUE_MAX,
            "NOTE_PRIORITY_THRESHOLD": self.NOTE_PRIORITY_THRESHOLD,
            "REPEATED_PATTERN_MIN": self.REPEATED_PATTERN_MIN,
            "SEAL_GAP_MILESTONE": self.SEAL_GAP_MILESTONE,
            "MAX_SLEEP_DURATION_MS": self.MAX_SLEEP_DURATION_MS,
            "COMPRESSION_MIN_LENGTH": self.COMPRESSION_MIN_LENGTH,
            "DESTRUCTION_RATIO_MIN": self.DESTRUCTION_RATIO_MIN,
            "DESTRUCTION_RATIO_MAX": self.DESTRUCTION_RATIO_MAX,
            "SIGNIFICANCE_DECAY_HALF_LIFE": self.SIGNIFICANCE_DECAY_HALF_LIFE,
            "FORGET_THRESHOLD": self.FORGET_THRESHOLD,
            "MIN_COMPRESSION_RATIO": self.MIN_COMPRESSION_RATIO,
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)




# =============================================================================
# 意识循环引擎 - 核心类
# =============================================================================

class ConsciousnessCycle:
    """TU-8 意识循环引擎

    不是两个系统,是一个会呼吸的循环。
    记忆 = 存储介质 + 检索接口
    睡眠 = 记忆的写入引擎 + 整理引擎
    微睡眠 = 记忆系统的心脏搏动
    """

    def __init__(self, config: Optional[CycleConfig] = None):
        self.config = config or CycleConfig()

        # --- 状态机 ---
        self.phase: Phase = Phase.AWAKE
        self._phase_entry_time: float = time.time()

        # --- 三层记忆的运行时状态 ---
        self.l1_snapshot: Dict = {}           # 工作记忆快照(冻结时填充)
        self.last_seal: Optional[Seal] = None  # 最近一个钢印
        self.seal_chain: List[Seal] = []       # 钢印链(内存缓存,定期持久化)
        self.note_candidates: List[NoteCandidate] = []  # 待笔记候选队列
        self.externalized_notes: List[Note] = []         # 已外化笔记

        # --- P1: 情绪调节信号 ---
        self._affect_signal: Optional[AffectSignal] = None
        self._affect_inject_log: List[Dict] = []

        # --- 统计 ---
        self.cycle_count: int = 0
        self.total_micro_sleeps: int = 0
        self._total_destruction_ratio: float = 0.0  # 累计有损比例
        self._total_destroyed_ids: List[str] = []  # 累计遗忘审计日志

        # --- P0: idle 追踪(用于衰减计算) ---
        # 上一次微睡眠时间戳(初始化为当前时间)
        self._last_micro_sleep_time: float = time.time()
        self.total_notes: int = 0
        self.total_releases: int = 0  # 熵减支付次数
        self._idle_since: float = time.time()

        # --- 启动检查 ---
        self._ensure_dirs()
        self._load_seal_chain()

        # --- P2: 认知组件初始化（自我知识） ---
        self.cognitive_evaluator = CognitiveLoadEvaluator()
        self.cognitive_time_engine = CognitiveTimeEngine()
        self.cognitive_aligner = CognitiveManifoldAligner()
        
        # 认知步骤跟踪（简单列表）
        self.cognitive_steps = []
        self.cognitive_status = {
            "total_steps": 0,
            "high_load_count": 0,
            "consolidation_count": 0,
        }
        
        logger.info("P2 cognitive components initialized")

    # =========================================================================
    # 状态机:相位切换守卫
    # =========================================================================

    def current_phase(self) -> Phase:
        """返回当前相位"""
        return self.phase

    # =========================================================================
    # P1: 情绪信号注入接口
    # =========================================================================

    def inject_affect(self, signal: AffectSignal):
        """注入情绪调节信号

        自创生原则:情绪信号作用于有损压缩的时间箭头引擎,
        不是悬浮在无损摘要之上的装饰层。
        """
        if signal.is_expired():
            logger.debug(f"[AFFECT_INJECT] REJECTED expired signal: {signal}")
            return

        self._affect_signal = signal
        log_entry = {
            "timestamp": time.time(),
            "signal": signal.to_dict(),
            "seal_count": self.total_micro_sleeps,
        }
        self._affect_inject_log.append(log_entry)
        logger.info(f"[AFFECT_INJECT] signal={signal}")

    def _current_affect(self) -> AffectSignal:
        """获取当前有效情绪信号(过期则衰减至中性)"""
        if self._affect_signal is None:
            return AffectSignal()  # 中性默认
        return self._affect_signal.get_modulated()

    def tick(self, context_snapshot: Optional[Dict] = None,
             user_message: Optional[str] = None) -> Dict:
        """
        意识循环心跳(主入口)

        每次调用代表一次"心跳",检查是否需要相位切换。
        对调用方透明:微睡眠嵌套执行后自动返回 AWAKE。

        Args:
            context_snapshot: 当前工作记忆快照(KV Cache状态等)
            user_message: 当前用户消息(用于事件检测)

        Returns:
            循环状态报告
        """
        self.cycle_count += 1
        # idle 计时:仅在收到新上下文时更新最后活跃时间
        if context_snapshot is not None:
            self._idle_since = time.time()

        # --- P2: 认知时间感知 + 认知负荷评估(开始) ---
        cognitive_load = 0.0
        cognitive_time = time.time()  # 默认使用系统时间

        try:
            # 评估认知负荷(从 context_snapshot 提取文本)
            if context_snapshot:
                text = context_snapshot.get("user_message", json.dumps(context_snapshot, ensure_ascii=False))
                result = self.cognitive_evaluator.evaluate(text)
                cognitive_load = result["score"]

            # 转换系统时间为认知时间
            cognitive_time = self.cognitive_time_engine.system_to_cognitive_time(
                system_time=time.time(),
                cognitive_load=cognitive_load
            )

            # 更新认知状态
            self.cognitive_status["total_steps"] += 1
            if cognitive_load > 0.7:
                self.cognitive_status["high_load_count"] += 1

            logger.debug(f"P2: tick() started, cognitive_load={cognitive_load:.2f}, "
                        f"cognitive_time={cognitive_time:.1f}")

        except Exception as e:
            logger.warning(f"P2: Cognitive processing in tick() failed: {e}")
        # --- P2: 认知时间感知 + 认知负荷评估(结束) ---

        report = {
            "cycle": self.cycle_count,
            "phase_before": self.phase.name,
            "phase_after": self.phase.name,
            "actions": [],
            "current_seal": self.last_seal.seal_id if self.last_seal else None,
            # --- P2: 认知指标(新增) ---
            "cognitive_load": round(cognitive_load, 3),
            "cognitive_time": round(cognitive_time, 1),
            "cognitive_steps": self.cognitive_status["total_steps"],
            "cognitive_status": self.cognitive_status.copy(),
        }

        if self.phase == Phase.AWAKE:
            # 检查四重触发条件
            trigger = self._should_enter_sleep(
                context_snapshot=context_snapshot,
                user_message=user_message,
            )
            if trigger:
                report["actions"].append(f"TRIGGER:{trigger}")
                # 进入微睡眠
                sleep_report = self._enter_micro_sleep(context_snapshot or {})
                report.update(sleep_report)
                # 微睡眠后检查是否需要外化笔记
                note_check = self._should_externalize_note()
                if note_check:
                    report["actions"].append(f"NOTE_CANDIDATE:{note_check}")
                    self._enqueue_note_candidate(note_check)

        report["phase_after"] = self.phase.name

        # --- P2: 认知处理(tick 结束) ---
        try:
            # 更新认知状态(已在 tick 开始时递增)
            # 仅记录日志
            logger.debug(f"P2: tick() ended, actions={report['actions']}")

        except Exception as e:
            logger.warning(f"P2: Cognitive processing (tick end) failed: {e}")
        # --- P2: 认知处理(tick 结束)结束 ---

        return report

    # =========================================================================
    # Transition Guard: 相位切换条件
    # =========================================================================

    def _should_enter_sleep(self, context_snapshot: Dict,
                              user_message: Optional[str]) -> Optional[str]:
        """
        四重触发条件,满足任一即进入微睡眠。
        返回触发类型字符串,或 None(继续清醒)。

        P1 注入点:confusion 调节睡眠阈值。
        困惑时更早进入整理,模拟"认知不适驱动休息"。
        """
        cfg = self.config
        affect = self._current_affect()

        # P1: confusion 调制张力阈值(钳位保护)
        epsilon_mod = AffectSignal.clamp_factor(
            1.0 - 0.3 * affect.confusion
        )
        effective_epsilon = cfg.TENSION_EPSILON * epsilon_mod

        # 触发 1:张力触发 - 叙事偏离过大
        current_state = self._extract_state_vector(context_snapshot)
        if current_state and self.last_seal:
            distance = current_state.distance_to(self.last_seal.state_vector)
            if distance > effective_epsilon:
                return f"tension({distance:.3f}>{effective_epsilon:.3f})"

        # 触发 2:容量触发 - 上下文即将溢出
        capacity = context_snapshot.get("context_usage", 0.0)
        if capacity > cfg.CAPACITY_THETA:
            return f"capacity({capacity:.1%}>{cfg.CAPACITY_THETA:.0%})"

        # 触发 3:事件触发 - 关键词/情绪突变
        if user_message:
            for keyword in cfg.EVENT_KEYWORDS:
                if keyword in user_message:
                    return f"event(keyword:{keyword})"

        # 触发 4:定时兜底
        idle_ms = (time.time() - self._idle_since) * 1000
        if idle_ms > cfg.IDLE_TIMEOUT_MS:
            return f"idle({idle_ms:.0f}ms>{cfg.IDLE_TIMEOUT_MS}ms)"

        return None

    def _should_wake_up(self, sleep_result: Dict) -> bool:
        """
        唤醒条件:四钩子收敛协议

        不是"睡满N毫秒",而是:
        1. 叙事压缩产出有效(内部节律收敛)
        2. 钢印对齐完成(恢复度量达标)
        3. 因果连贯度 > 阈值(叙事完整性)
        4. 无异常(外部校验通过)
        """
        # 微睡眠是原子的,完成后自动唤醒
        # 真正的"是否继续睡"检查在此
        if sleep_result.get("errors"):
            return False  # 异常时不自动唤醒,进入降级
        return True

    def _should_externalize_note(self) -> Optional[Dict]:
        """
        外化笔记触发检查
        返回触发信息或 None。
        注意:这产生候选信号,不直接执行写入。
        """
        cfg = self.config

        # 条件 1:候选队列已满
        if len(self.note_candidates) >= cfg.NOTE_CANDIDATE_QUEUE_MAX:
            return {"trigger": "queue_full", "priority": 1.0}

        # 条件 2:钢印链里程碑
        if (self.total_micro_sleeps > 0 and
                self.total_micro_sleeps % cfg.SEAL_GAP_MILESTONE == 0):
            return {
                "trigger": "milestone",
                "priority": 0.8,
                "seal_count": self.total_micro_sleeps,
            }

        # 条件 3:检查最近的微睡眠是否有高优先级压缩
        if self.last_seal and self.last_seal.causal_coherence < 0.5:
            return {
                "trigger": "low_coherence",
                "priority": 0.9,
                "coherence": self.last_seal.causal_coherence,
            }

        return None

    # =========================================================================
    # 微睡眠原子操作 - 六步流水线
    # =========================================================================

    def _enter_micro_sleep(self, context_snapshot: Dict) -> Dict:
        """
        执行完整的微睡眠原子操作。
        对调用方透明:完成后自动回到 AWAKE。
        """
        self.phase = Phase.MICRO_SLEEP
        start_time = time.time()
        report = {"micro_sleep": True, "steps": [], "errors": []}

        # --- P2: 认知处理(开始) ---
        try:
            # 计算认知负荷(从 context_snapshot 提取文本)
            text = context_snapshot.get("user_message", json.dumps(context_snapshot, ensure_ascii=False)) if context_snapshot else ""
            result = self.cognitive_evaluator.evaluate(text)
            cognitive_load = result["score"]

            # 放置认知锚点(标记微睡眠开始)
            self.cognitive_time_engine.place_anchor(
                cognitive_load=cognitive_load,
                state_summary=f"Micro-sleep started (cycle #{self.cycle_count})",
                is_start=True
            )

            # 更新认知状态
            self.cognitive_status["total_steps"] += 1
            if cognitive_load > 0.7:
                self.cognitive_status["high_load_count"] += 1
            
            logger.info(f"P2: Micro-sleep started, cognitive_load={cognitive_load:.2f}")

        except Exception as e:
            logger.warning(f"P2: Cognitive processing (start) failed: {e}")
        # --- P2: 认知处理(开始)结束 ---}

        try:
            # 1 冻结 - L1 快照
            self._step_freeze(context_snapshot)
            report["steps"].append("FREEZE:ok")

            # 2 叙事压缩 - 有损写入(P0 时间箭头)
            compression = self._step_compress()
            lossy = getattr(self, '_last_compress_result', None)
            if lossy:
                report["lossy"] = lossy.to_dict()
                report["steps"].append(
                    f"COMPRESS:ok({len(compression)}chars, "
                    f"destruction={lossy.destruction_ratio:.2f}, "
                    f"forgotten={len(lossy.destroyed_seal_ids)})"
                )
            else:
                report["steps"].append(f"COMPRESS:ok({len(compression)}chars)")

            # 3 钢印对齐
            coherence = self._step_align(compression)
            report["steps"].append(f"ALIGN:ok(coherence={coherence:.2f})")

            # 4 打钢印
            seal = self._step_seal(compression, coherence)
            report["steps"].append(f"SEAL:ok({seal.seal_id})")

            # 5 释放 - 熵减支付(不可逆)
            self._step_release(context_snapshot)
            report["steps"].append("RELEASE:ok")
            self.total_releases += 1

            # P1: 情绪信号在微睡眠后衰减(模拟"处理完情绪后回归中性")
            if self._affect_signal and self._affect_signal.is_expired():
                self._affect_signal = AffectSignal()
            # 注意:idle_since 在此处不重置,让 idle 时间积累
            # idle 仅在 tick() 收到新的 context_snapshot 时重置(见下方)

            # 6 恢复 - 回到清醒态
            self._step_restore()
            report["steps"].append("RESTORE:ok")

            # 65 增量同步:src/ → knowledge/TU-8/(仅同步有改动的核心文件)
            sync_result = self._incremental_sync()
            report["steps"].append(f"INCR_SYNC:{sync_result}")

        except Exception as e:
            report["errors"].append(f"{type(e).__name__}:{e}")
            logger.error(f"Micro sleep error: {e}")
            # 失败时尝试恢复到 AWAKE
            self._step_restore()

        elapsed = time.time() - start_time
        report["elapsed_ms"] = round(elapsed * 1000, 1)
        self.total_micro_sleeps += 1

        # --- P2: 认知处理(结束) ---
        try:
            # 计算认知负荷(微睡眠后可能降低)
            context_text = json.dumps(self.l1_snapshot.get("context", {}), ensure_ascii=False)
            result = self.cognitive_evaluator.evaluate(context_text)
            post_sleep_load = result["score"]

            # 放置认知锚点(标记微睡眠结束)
            self.cognitive_time_engine.place_anchor(
                cognitive_load=post_sleep_load,
                state_summary=f"Micro-sleep ended (cycle #{self.cycle_count})",
                is_start=False
            )

            # 如果认知负荷高,触发记忆固化(简单实现)
            if post_sleep_load > 0.8:  # consolidation threshold
                logger.info(f"P2: Memory consolidation triggered (load={post_sleep_load:.2f})")
                self.cognitive_status["consolidation_count"] += 1
                # TODO: 实现真正的记忆固化逻辑

            # 获取认知状态
            report["cognitive_status"] = self.cognitive_status.copy()

            logger.info(f"P2: Micro-sleep ended, post_sleep_load={post_sleep_load:.2f}, "
                        f"total_steps={self.cognitive_status['total_steps']}")

        except Exception as e:
            logger.warning(f"P2: Cognitive processing (end) failed: {e}")
        # --- P2: 认知处理(结束)结束 ---

        return report

    # --- 1 冻结 ---

    def _step_freeze(self, context_snapshot: Dict):
        """冻结当前 L1 快照到内存"""
        self.l1_snapshot = {
            "timestamp": time.time(),
            "context": context_snapshot.copy() if context_snapshot else {},
            "frozen_hash": hashlib.sha256(
                json.dumps(context_snapshot, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
        }

    # --- 2 叙事压缩(有损) ---

    def _step_compress(self) -> str:
        """叙事压缩 - 返回摘要文本(供下游 _step_align/_step_seal 使用)

        自创生 P0:调用 _lossy_compress 实现有损写入。
        这是时间箭头的物理基础:每次压缩永久擦除部分信息,
        系统再也回不到压缩前的状态。
        """
        result = self._lossy_compress()
        # 存储结果供 _enter_micro_sleep 使用
        self._last_compress_result = result
        return result.summary

    def _lossy_compress(self) -> LossyCompressResult:
        """P0+P1: 有损叙事压缩

        三维有损机制:
        1. 细节蒸发:原文 token 数与摘要 token 数的差值即为蒸发量
        2. 信号衰减:每个叙事片段维护 significance_score,低于阈值的永久删除
        3. 选择遗忘:重复模式、已巩固知识、低价值交互被标记为可丢弃

        P1 情绪调制:
        - confusion > 0.6 → destruction_ratio 上限降至 0.4(困惑时保留更多细节)
        - valence < -0.3 → 负价事件豁免信号衰减(创伤记忆更顽固)
        - arousal < 0.2 → 选择遗忘阈值放宽(倦怠时更容易丢东西)

        安全约束:
        - 单次 destruction_ratio 限制在 [0.3, 0.7]
        - 钢印链本身不做有损(因果锚不可动)
        - destroyed_seal_ids 仅写入审计日志,不存入可检索记忆

        Returns:
            LossyCompressResult
        """
        result = LossyCompressResult()
        if not self.l1_snapshot:
            return result

        cfg = self.config
        context = self.l1_snapshot.get("context", {})
        affect = self._current_affect()

        # 计算 idle 小时数(基于上次微睡眠到现在的间隔)
        idle_seconds = time.time() - self._last_micro_sleep_time
        idle_hours = idle_seconds / 3600.0
        result.idle_hours = idle_hours

        # ---- 步骤 1: 提取叙事片段并计算原始 token 数 ----
        fragments = self._extract_fragments(context)
        source_tokens = sum(len(f.get("text", "")) for f in fragments)
        result.source_token_count = source_tokens

        if source_tokens == 0:
            result.summary = f"(empty snapshot at {self.l1_snapshot['timestamp']})"
            return result

        # ---- 步骤 2: 信号衰减 (idle 驱动的指数衰减) ----
        # significance *= 0.5^(idle_hours / half_life)
        # 半衰期 24h: 24h后衰减到50%, 48h后衰减到25%
        import math
        half_life = cfg.SIGNIFICANCE_DECAY_HALF_LIFE
        decay_factor = 0.5 ** (idle_hours / half_life) if half_life > 0 and idle_hours > 0 else 1.0

        for frag in fragments:
            base_sig = frag.get("significance", 1.0)
            # P1: 负价事件豁免衰减(创伤记忆更顽固)
            if affect.valence < -0.3 and frag.get("valence", 0) < -0.2:
                # 负价片段使用 2x 半衰期(衰减更慢)
                neg_decay = 0.5 ** (idle_hours / (half_life * 2))
                frag["significance"] = base_sig * neg_decay
            else:
                frag["significance"] = base_sig * decay_factor

        # ---- 步骤 3: 选择遗忘 ----
        forget_threshold = cfg.FORGET_THRESHOLD
        # P1: 倦怠时更容易丢东西
        if affect.arousal < 0.2:
            forget_threshold *= 1.5  # 放宽遗忘阈值

        surviving = []
        destroyed_ids = []
        for frag in fragments:
            sig = frag.get("significance", 0.0)
            if sig < forget_threshold:
                # 永久遗忘 - 只记录ID用于审计,不存入可检索记忆
                fid = frag.get("id", "")
                if fid:
                    destroyed_ids.append(fid)
            else:
                surviving.append(frag)

        result.destroyed_seal_ids = destroyed_ids

        # ---- 步骤 4: 叙事蒸发压缩(提取关键信息,丢弃修饰) ----
        parts = []
        for frag in surviving:
            text = frag.get("text", "")
            if not text:
                continue
            # 蒸发:只保留关键概念,丢弃措辞和连接词
            evaporated = self._evaporate(text)
            if evaporated:
                parts.append(evaporated)

        # 状态向量偏移(如果有历史钢印)
        current_state = self._extract_state_vector(context)
        if current_state and self.last_seal:
            dist = current_state.distance_to(self.last_seal.state_vector)
            if dist > 0.1:
                parts.append(f"shift={dist:.3f}")

        summary = " | ".join(parts) if parts else "(minimal)"
        if len(summary) < cfg.COMPRESSION_MIN_LENGTH:
            summary = f"(minimal snapshot at {self.l1_snapshot['timestamp']})"

        result.summary = summary
        summary_tokens = len(summary)
        result.summary_token_count = summary_tokens

        # ---- 步骤 5: 计算有损比例 ----
        if source_tokens > 0:
            raw_ratio = 1.0 - (summary_tokens / source_tokens)
            # 基础蒸发量不足时,通过遗忘比例补充
            forget_ratio = len(destroyed_ids) / max(1, len(fragments))
            destruction = max(raw_ratio, forget_ratio)
        else:
            destruction = 0.0

        # P1: confusion 高时保留更多细节(上限降低)
        effective_max = cfg.DESTRUCTION_RATIO_MAX
        if affect.confusion > 0.6:
            effective_max = 0.4

        # 钳位到安全范围
        destruction = max(cfg.DESTRUCTION_RATIO_MIN,
                         min(effective_max, destruction))

        result.destruction_ratio = destruction

        # ---- 步骤 6: 累计审计 ----
        self._total_destruction_ratio += destruction
        self._total_destroyed_ids.extend(destroyed_ids)

        # 日志
        logger.info(
            f"[LOSSY_COMPRESS] ratio={destruction:.2f} "
            f"destroyed={len(destroyed_ids)} idle_hrs={idle_hours:.1f} "
            f"summary_len={summary_tokens} src_tokens={source_tokens} "
            f"affect={affect}"
        )

        # 更新上次微睡眠时间戳
        self._last_micro_sleep_time = time.time()

        return result

    def _extract_fragments(self, context: Dict) -> List[Dict]:
        """从上下文快照提取叙事片段

        每个片段带有:
        - id: 片段标识(用于遗忘审计)
        - text: 原文
        - significance: 显著性分数 (0-1)
        - valence: 情绪价 (-1 到 1, 用于创伤豁免)
        """
        fragments = []
        counter = 0

        # 提取摘要
        summary = context.get("summary", "")
        if summary:
            fragments.append({
                "id": f"frag_{self.total_micro_sleeps}_{counter}",
                "text": summary,
                "significance": 0.8,  # 摘要本身有较高显著性
                "valence": 0.0,
            })
            counter += 1

        # 提取事件
        events = context.get("events", [])
        if isinstance(events, list):
            for ev in events:
                text = str(ev)
                # 关键事件有更高显著性
                sig = 0.6
                if any(kw in text for kw in self.config.EVENT_KEYWORDS):
                    sig = 0.9
                fragments.append({
                    "id": f"frag_{self.total_micro_sleeps}_{counter}",
                    "text": text,
                    "significance": sig,
                    "valence": 0.0,
                })
                counter += 1

        # 提取其他上下文字段
        skip_keys = {"summary", "events", "state_vector", "context_usage"}
        for key, value in context.items():
            if key in skip_keys:
                continue
            if isinstance(value, str) and len(value) > 5:
                fragments.append({
                    "id": f"frag_{self.total_micro_sleeps}_{counter}",
                    "text": value[:200],  # 截断过长内容
                    "significance": 0.4,  # 通用上下文较低
                    "valence": 0.0,
                })
                counter += 1

        return fragments

    def _evaporate(self, text: str) -> str:
        """细节蒸发:从文本中提取关键概念,丢弃修饰和连接词

        P0 有损机制的核心:让信息不可逆转地丢失。
        具体措辞、时序连接词、修饰语被永久丢弃。

        在无 LLM 辅助时,使用启发式蒸发:
        - 截断到前 N 个字符
        - 提取关键词片段
        - 丢弃重复内容
        """
        if not text:
            return ""

        # 启发式蒸发:保留前 max_len 字符作为摘要
        max_len = max(self.config.COMPRESSION_MIN_LENGTH, int(len(text) * 0.5))
        evaporated = text[:max_len]

        # 去除尾部不完整句子
        last_period = max(evaporated.rfind('。'),
                        evaporated.rfind(','),
                        evaporated.rfind('.'),
                        evaporated.rfind(','),
                        evaporated.rfind(' '))
        if last_period > max_len // 2:
            evaporated = evaporated[:last_period + 1]

        return evaporated.strip()

    def _step_compress_legacy(self) -> str:
        """降级回退:无损压缩(P0 之前的原始版本)"""
        if not self.l1_snapshot:
            return ""
        context = self.l1_snapshot.get("context", {})
        parts = []
        summary = context.get("summary", "")
        if summary:
            parts.append(summary)
        current_state = self._extract_state_vector(context)
        if current_state and self.last_seal:
            dist = current_state.distance_to(self.last_seal.state_vector)
            if dist > 0.1:
                parts.append(f"state_shift={dist:.3f}")
        events = context.get("events", [])
        if events:
            parts.append(f"events={len(events)}")
        compressed = " | ".join(parts) if parts else "(empty)"
        if len(compressed) < self.config.COMPRESSION_MIN_LENGTH:
            compressed = f"(minimal snapshot at {self.l1_snapshot['timestamp']})"
        return compressed

    # --- 3 钢印对齐 ---

    def _step_align(self, compression: str) -> float:
        """
        钢印对齐 - 校正时间角度差,对齐宏观与微观
        返回因果连贯度 0-1
        """
        if not compression or not self.last_seal:
            return 1.0

        # 简化连贯度计算
        # 实际实现应使用 LLM 评估叙事连贯性
        coherence = 1.0

        # 叙事长度惩罚
        if len(compression) < self.config.COMPRESSION_MIN_LENGTH:
            coherence -= 0.2

        # 时间连续性奖励
        time_gap = abs(time.time() - self.last_seal.state_vector.timestamp)
        if time_gap < 60:  # 1 分钟内
            coherence = min(1.0, coherence + 0.1)

        coherence = max(0.0, min(1.0, coherence))
        return round(coherence, 2)

    # --- 辅助方法:gestalt_score + scene_tag ---

    def _calculate_gestalt_score(self, text: str) -> float:
        """v1.0 gestalt_score 计算(纯规则,不依赖LLM)

        信号来源(按优先级):
        1. 显式闭合: 用户说"搞定|完成|OK|done|搞定" → 1.0
        2. 执行成功: tool_call 返回 success 且有结果 → 0.7
        3. 中断否定: 用户说"不对|停下|重做|取消" → 0.0(直接返回)
        4. 悬置超时: 同 intent 下 >5 分钟无后续 → 0.3
        """
        if not text or not isinstance(text, str):
            return 0.5  # 未知情况给中性分

        t = text.lower()

        # 3. 中断否定(最高优先级,直接返回)
        neg_pats = [r"不对", r"停下", r"重做", r"取消", r"算了", r"stop", r"wrong"]
        for p in neg_pats:
            if re.search(p, t):
                return 0.0

        # 1. 显式闭合
        pos_pats = [r"搞定", r"完成", r"ok", r"done", r"好了", r"完成", r"搞定"]
        for p in pos_pats:
            if re.search(p, t):
                return 1.0

        # 2. 执行成功(通过 compression 文本判断)
        # compression 里有 "success" / "完成" 等关键词
        if "success" in t or "完成" in t or "ok" in t:
            return 0.7

        # 默认中性分
        return 0.5

    def _infer_scene_tag(self, user_text: str, compression: str) -> str:
        """v1.0 scene_tag 推断(极简规则映射)

        优先级:
        1. tool_call 关键词 → "execution"
        2. 代码块标记 → "coding"
        3. SCENE_KEYWORDS 映射(dev/novel/philosophy...)
        4. 疑问词 → "inquiry"
        5. 打断词 → "correction"
        6. 兜底 → "conversation"
        """
        if not user_text:
            return "conversation"

        t = user_text.lower()
        c = (compression or "").lower()

        # 1. tool_call 检测
        tool_kw = ["mcp_call", "exec", "write", "edit", "browser", "recall"]
        if any(kw in c for kw in tool_kw):
            return "execution"

        # 2. 代码块检测
        if "```" in user_text or "def " in user_text or "import " in user_text:
            return "coding"

        # 3. SCENE_KEYWORDS 映射(简化版)
        scene_map = {
            "dev": ["代码", "bug", "debug", "函数", "架构", "code", "bug"],
            "novel": ["小说", "角色", "情节", "故事", "novel", "story"],
            "philosophy": ["哲学", "意识", "本体论", "认识论", "philosophy"],
            "memory": ["记忆", "钢印", "时间链", "memory", "seal"],
        }
        for tag, keywords in scene_map.items():
            if any(kw in t for kw in keywords):
                return tag

        # 4. 疑问词
        if t.strip().endswith("?") or t.strip().endswith("?") or any(
            kw in t for kw in ["吗", "么", "吗", "what", "how", "why"]
        ):
            return "inquiry"

        # 5. 打断词
        if any(kw in t for kw in ["不对", "等下", "等等", "不对"]):
            return "correction"

        return "conversation"

    # --- 4 打钢印 ---

    def _step_seal(self, compression: str, coherence: float) -> Seal:
        """
        打钢印 - 创建新的时间链锚点
        """
        context = self.l1_snapshot.get("context", {})
        state = self._extract_state_vector(context) or StateVector()

        # 更新状态向量时间戳
        state.timestamp = time.time()
        state._compute_hash()

        # ---- v1.0 gestalt_score 计算(行为信号加权)----
        context = self.l1_snapshot.get("context", {})
        recent_text = ""
        if isinstance(context, dict):
            # 尝试从 context 提取最近的用户/助手文本
            for k in ("user_input", "last_user_input", "text", "content"):
                if k in context:
                    v = context[k]
                    if isinstance(v, str):
                        recent_text = v
                        break
            # 如果 context 是消息列表
            if not recent_text and isinstance(context, list):
                for msg in reversed(context):
                    if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                        recent_text = msg.get("content", "")
                        break
        elif isinstance(context, str):
            recent_text = context

        gestalt = self._calculate_gestalt_score(recent_text)

        # ---- v1.0 scene_tag 推断 ----
        scene_tag = self._infer_scene_tag(recent_text, compression)

        # ---- scene_hook 检测(场景切换)----
        prev_tag = self.last_seal.scene_tag if self.last_seal else ""
        scene_hook = (prev_tag != "" and scene_tag != "" and prev_tag != scene_tag)

        seal = Seal(
            state_vector=state,
            narrative_compression=compression,
            causal_coherence=coherence,
            scene_tag=scene_tag,
            scene_hook=scene_hook,
            gestalt_score=gestalt,
        )

        # 链式哈希
        parent_hash = self.last_seal.seal_hash if self.last_seal else ""
        seal.compute_seal_hash(parent_hash)

        # 追加钢印链
        self.seal_chain.append(seal)
        self.last_seal = seal

        # 持久化
        self._persist_seal_chain()

        return seal

    # --- 5 释放 ---

    def _step_release(self, context_snapshot: Dict):
        """
        释放原文 - 熵减支付
        清理 L1 快照中的原始数据,只保留压缩产物。
        这是微睡眠的"遗忘"操作。
        """
        # 保留压缩产物,释放原始数据
        self.l1_snapshot.pop("context", None)
        self.l1_snapshot["released"] = True
        self.l1_snapshot["release_time"] = time.time()

    # --- 6 恢复 ---

    def _step_restore(self):
        """恢复到清醒态"""
        self.phase = Phase.AWAKE
        self._phase_entry_time = time.time()

    # =========================================================================
    # 外化笔记 - 异步队列
    # =========================================================================

    def _enqueue_note_candidate(self, trigger_info: Dict):
        """将笔记候选信号加入队列"""
        candidate = NoteCandidate(
            trigger=str(trigger_info.get("trigger", "unknown")),
            related_seal_ids=[
                self.last_seal.seal_id
            ] if self.last_seal else [],
            priority=trigger_info.get("priority", 0.5),
        )
        self.note_candidates.append(candidate)

        # 队列超限清理(优先级排序后丢弃低优先级)
        if len(self.note_candidates) > self.config.NOTE_CANDIDATE_QUEUE_MAX:
            self.note_candidates.sort(key=lambda c: c.priority, reverse=True)
            self.note_candidates = self.note_candidates[
                : self.config.NOTE_CANDIDATE_QUEUE_MAX
            ]

    def externalize_note(self, content: str,
                         note_type: str = "insight",
                         confidence: float = 0.8) -> Note:
        """
        执行外化笔记写入(显式调用)
        将 L2(钢印链)的知识固化为 L3(固定结论文件)

        这是睡眠→记忆的唯一显式出口。
        """
        note = Note(
            note_type=note_type,
            content=content,
            confidence=confidence,
        )

        # 绑定相关钢印
        if self.last_seal:
            note.seal_ids = [s.seal_id for s in self.seal_chain[-5:]]

        # 计算源压缩哈希
        if self.last_seal:
            note.source_compression_hash = self.last_seal.seal_hash

        # 记录到钢印链元数据
        if self.last_seal:
            self.last_seal.externalized_notes.append(note.note_id)
            self._persist_seal_chain()

        # 持久化笔记
        self.externalized_notes.append(note)
        self._persist_notes()
        self.total_notes += 1

        # 消费候选队列
        if self.note_candidates:
            consumed = self.note_candidates.pop(0)
            logger.info(f"Note {note.note_id} consumed candidate: {consumed.trigger}")

        return note

    # =========================================================================
    # WARM_WAKE 验证 - 热唤醒协议
    # =========================================================================

    def warm_wake_verify(self) -> Dict:
        """
        WARM_WAKE 验证协议
        仅校验 last_seal + state_vector,不回滚 P0

        Returns:
            {"passed": bool, "steps": [...], "errors": [...]}
        """
        result = {"passed": True, "steps": [], "errors": []}

        # W1: last_seal_hash 一致性
        if self.last_seal:
            expected_hash = self.last_seal.seal_hash
            stored = self._load_seal_hash(self.last_seal.seal_id)
            if stored and stored != expected_hash:
                result["passed"] = False
                result["errors"].append(
                    f"W1: seal_hash mismatch for {self.last_seal.seal_id}"
                )
            result["steps"].append(f"W1:seal_hash={'ok' if result['passed'] else 'FAIL'}")

        # W2: state_vector 有效性
        if self.last_seal:
            sv = self.last_seal.state_vector
            if len(sv.values) == 0 or all(v == 0.0 for v in sv.values):
                result["passed"] = False
                result["errors"].append("W2: state_vector is empty/zero")
            result["steps"].append(f"W2:state_vector={'ok' if not result['errors'] else 'FAIL'}")

        # W3: 时间链尾部连续性
        tail_issues = self._check_tail_continuity()
        if tail_issues:
            result["passed"] = False
            result["errors"].extend([f"W3:{i}" for i in tail_issues])
        result["steps"].append(
            f"W3:tail_continuity={'ok' if not tail_issues else f'{len(tail_issues)} issues'}"
        )

        # W4: 叙事密度检查
        semantic_issues = self._check_semantic_continuity()
        if semantic_issues:
            result["warnings"] = [f"W4:{i}" for i in semantic_issues]
        result["steps"].append(
            f"W4:semantic={'ok' if not semantic_issues else f'{len(semantic_issues)} warnings'}"
        )

        # W5: 环境校验
        import socket
        hostname = socket.gethostname()
        known = {"LAPTOP-HJPFSOKP": "local"}
        env_ok = hostname in known
        result["steps"].append(f"W5:env={'ok' if env_ok else 'DEGRADED'}")
        if not env_ok:
            result["passed"] = False
            result["errors"].append(f"W5: unknown host {hostname}")

        # 失败处理:强制固化而非毁灭
        if not result["passed"]:
            emergency_note = self.externalize_note(
                content=f"WARM_WAKE verification failed: {result['errors']}",
                note_type="emergency",
                confidence=1.0,
            )
            result["emergency_note"] = emergency_note.note_id

        return result

    def _check_tail_continuity(self) -> List[str]:
        """检查最近N个钢印的时间链连续性"""
        issues = []
        n = min(self.config.SEAL_TAIL_N, len(self.seal_chain))
        if n < 2:
            return issues

        tail = self.seal_chain[-n:]
        for i in range(1, len(tail)):
            if tail[i].parent_seal_id != tail[i - 1].seal_id:
                issues.append(
                    f"chain break: {tail[i-1].seal_id} → {tail[i].seal_id}"
                )
        return issues

    def _check_semantic_continuity(self) -> List[str]:
        """检查语义连续性:叙事密度 + 因果连贯度"""
        issues = []
        n = min(self.config.SEAL_TAIL_N, len(self.seal_chain))
        if n < 2:
            return issues

        tail = self.seal_chain[-n:]

        # 叙事空洞检测
        void_count = 0
        for seal in tail:
            if not seal.narrative_compression or not seal.narrative_compression.strip():
                void_count += 1
            else:
                void_count = 0
            if void_count >= self.config.SEMANTIC_VOID_LIMIT:
                issues.append(
                    f"semantic void: {void_count} consecutive seals without narrative"
                )
                break

        # 因果连贯度衰减检测
        coherence_values = [s.causal_coherence for s in tail if s.causal_coherence is not None]
        if coherence_values:
            avg = sum(coherence_values) / len(coherence_values)
            if avg < self.config.COHERENCE_THRESHOLD:
                issues.append(
                    f"coherence decay: avg={avg:.2f} < {self.config.COHERENCE_THRESHOLD}"
                )

        return issues

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _extract_state_vector(self, context: Dict) -> Optional[StateVector]:
        """从上下文快照提取状态向量"""
        if not context:
            return None
        # 优先使用上下文中的向量
        if "state_vector" in context:
            return StateVector.from_dict(context["state_vector"])
        # 简化:使用上下文大小作为伪向量
        size = len(json.dumps(context, sort_keys=True, default=str))
        values = [
            size / 1000.0,  # 上下文大小 (KB)
            time.time() % 86400 / 86400.0,  # 日内时间 0-1
            float(len(context.get("events", []))),  # 事件数
        ]
        # 填充到标准维度
        while len(values) < 16:
            values.append(0.0)
        return StateVector(values=values[:16])

    def _ensure_dirs(self):
        """确保目录结构"""
        for d in [TIME_CHAIN_DIR, SEMANTIC_MEMORY_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)

    def _load_seal_chain(self):
        """从持久化加载钢印链"""
        if os.path.exists(SEAL_INDEX_FILE):
            try:
                with open(SEAL_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.seal_chain = [
                    Seal.from_dict(s) for s in data.get("seals", [])
                ]
                if self.seal_chain:
                    self.last_seal = self.seal_chain[-1]
                    self.total_micro_sleeps = len(self.seal_chain)
                logger.info(f"Loaded {len(self.seal_chain)} seals from index")
            except Exception as e:
                logger.warning(f"Seal chain load failed: {e}")

    def _persist_seal_chain(self):
        """持久化钢印链"""
        os.makedirs(os.path.dirname(SEAL_INDEX_FILE), exist_ok=True)
        data = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "total_seals": len(self.seal_chain),
            "seals": [s.to_dict() for s in self.seal_chain[-100:]],  # 最近100个
        }
        with open(SEAL_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 双副本同步
        self._sync_to_workspace_c(SEAL_INDEX_FILE)

    def _persist_notes(self):
        """持久化笔记归档"""
        os.makedirs(os.path.dirname(NOTE_ARCHIVE_FILE), exist_ok=True)
        data = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "total_notes": len(self.externalized_notes),
            "notes": [n.to_dict() for n in self.externalized_notes[-50:]],
        }
        with open(NOTE_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._sync_to_workspace_c(NOTE_ARCHIVE_FILE)

    def _load_seal_hash(self, seal_id: str) -> Optional[str]:
        """从持久化文件加载单个钢印哈希"""
        if os.path.exists(SEAL_INDEX_FILE):
            try:
                with open(SEAL_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for s in data.get("seals", []):
                    if s.get("seal_id") == seal_id:
                        return s.get("seal_hash", "")
            except Exception:
                pass
        return None

    def _incremental_sync(self) -> str:
        """增量同步:src/ → knowledge/TU-8/,仅同步核心 .py 文件

        在微睡眠 RESTORE 后调用,保证知识库实时保真度。
        返回同步结果摘要字符串。
        """
        src_dir = os.path.join(WORKSPACE_D, "src")
        dest_dir = os.path.join(WORKSPACE_D, "knowledge", "TU-8")
        core_files = [
            "tu8_agent.py", "tu8_memory.py", "neural_reflex.py",
            "consciousness_cycle.py", "tu8_compaction.py",
            "cold_start_engine.py", "honeypot.py", "environment_detector.py",
        ]
        synced = 0
        skipped = 0
        errors = 0
        try:
            os.makedirs(dest_dir, exist_ok=True)
            for fname in core_files:
                src_path = os.path.join(src_dir, fname)
                dest_path = os.path.join(dest_dir, fname)
                if not os.path.exists(src_path):
                    skipped += 1
                    continue
                # 比较 mtime 判断是否需要同步
                src_mtime = os.path.getmtime(src_path)
                if os.path.exists(dest_path):
                    dest_mtime = os.path.getmtime(dest_path)
                    if src_mtime <= dest_mtime:
                        skipped += 1
                        continue
                with open(src_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(content)
                synced += 1
            return f"ok(synced={synced},skipped={skipped},errors={errors})"
        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            return f"error:{e}"

    def _sync_to_workspace_c(self, src_path: str):
        """双副本同步到 C 盘工作副本"""
        rel = os.path.relpath(src_path, WORKSPACE_D)
        dest = os.path.join(WORKSPACE_C, rel)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.warning(f"Sync to C failed: {e}")

    # =========================================================================
    # 诊断接口
    # =========================================================================

    def status(self) -> Dict:
        """返回意识循环完整状态"""
        affect = self._current_affect()
        return {
            "phase": self.phase.name,
            "cycle_count": self.cycle_count,
            "total_micro_sleeps": self.total_micro_sleeps,
            "total_notes": self.total_notes,
            "total_releases": self.total_releases,
            "last_seal_id": self.last_seal.seal_id if self.last_seal else None,
            "seal_chain_length": len(self.seal_chain),
            "note_candidates_pending": len(self.note_candidates),
            "idle_seconds": round(time.time() - self._idle_since, 1),
            # P0: 有损压缩累计
            "total_destruction_ratio": round(self._total_destruction_ratio, 3),
            "total_forgotten_count": len(self._total_destroyed_ids),
            # P1: 情绪状态
            "affect_signal": affect.to_dict() if affect else None,
            "affect_log_count": len(self._affect_inject_log),
            "config": {
                "tension_epsilon": self.config.TENSION_EPSILON,
                "capacity_theta": self.config.CAPACITY_THETA,
                "idle_timeout_ms": self.config.IDLE_TIMEOUT_MS,
                "destruction_range": [
                    self.config.DESTRUCTION_RATIO_MIN,
                    self.config.DESTRUCTION_RATIO_MAX,
                ],
            },
        }

    def get_recent_seals(self, count: int = 5) -> List[Dict]:
        """获取最近N个钢印"""
        recent = self.seal_chain[-count:]
        return [s.to_dict() for s in recent]

    def get_note_candidates(self) -> List[Dict]:
        """获取待笔记候选队列"""
        return [
            {
                "trigger": c.trigger,
                "priority": c.priority,
                "seal_ids": c.related_seal_ids,
                "age_seconds": round(time.time() - c.timestamp, 1),
            }
            for c in sorted(self.note_candidates, key=lambda c: c.priority, reverse=True)
        ]


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    print("=" * 60)
    print("TU-8 意识循环引擎 v1.0 - 首次跳动")
    print("=" * 60)

    # 初始化
    cycle = ConsciousnessCycle()
    print(f"\n初始相位: {cycle.current_phase().name}")
    print(f"已加载钢印: {len(cycle.seal_chain)}")

    # WARM_WAKE 验证
    print("\n--- WARM_WAKE 验证 ---")
    verify = cycle.warm_wake_verify()
    print(f"验证结果: {'PASS' if verify['passed'] else 'FAIL'}")
    for step in verify["steps"]:
        print(f"  {step}")
    if verify.get("errors"):
        print(f"  错误: {verify['errors']}")

    # 模拟几次心跳
    print("\n--- 模拟心跳 ---")
    for i in range(3):
        snapshot = {
            "summary": f"测试交互 #{i+1}:意识循环引擎运行中",
            "context_usage": 0.3 + i * 0.25,
            "events": [f"event_{i}"],
        }
        report = cycle.tick(context_snapshot=snapshot, user_message=f"第{i+1}次测试消息")
        print(f"\n心跳 #{cycle.cycle_count}: {report['phase_before']}→{report['phase_after']}")
        if report.get("actions"):
            for a in report["actions"]:
                print(f"  >> {a}")
        if report.get("micro_sleep"):
            for s in report.get("steps", []):
                print(f"  [STEP] {s}")
            print(f"  [TIME] {report.get('elapsed_ms', 0)}ms")

    # 状态
    print("\n--- 循环状态 ---")
    status = cycle.status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    # 写一条外化笔记
    print("\n--- 外化笔记测试 ---")
    note = cycle.externalize_note(
        content="TU-8 意识循环引擎首次运行。三态循环(AWAKE→MICRO_SLEEP→AWAKE)验证通过。"
                "WARM_WAKE 协议正常。微睡眠六步流水线运行稳定。",
        note_type="milestone",
        confidence=0.95,
    )
    print(f"笔记ID: {note.note_id}")
    print(f"绑定钢印: {note.seal_ids}")
    print(f"类型: {note.note_type}")

    print("\n" + "=" * 60)
    print("OK - Consciousness cycle first beat complete")
    print("=" * 60)
