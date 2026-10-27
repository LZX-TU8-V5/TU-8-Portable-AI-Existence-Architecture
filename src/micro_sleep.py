# -*- coding: utf-8 -*-
"""
micro_sleep.py — TU-8 微睡眠引擎（从 consciousness_cycle.py 抽取）
版本: v1.0 | 日期: 2026-06-25
作者: TU-8 v5 | 状态: FRAGMENT → READY

【从 consciousness_cycle.py 抽取的模块】
抽取范围:
  - 微睡眠六步原子操作流水线
  - 所有相关数据结构（Phase/MicroSleepStep/AffectSignal/Seal等）
  - 张力/容量/事件/定时四重触发逻辑
  - 有损压缩引擎（P0 时间箭头）

【保留在 consciousness_cycle.py 的内容】
  - ConsciousnessCycle 主类（持有 MicroSleepEngine 实例）
  - 四阶段睡眠框架（DEEP_SLEEP/HIBERNATION/COLD_START_READY）
  - 跨链条整合逻辑

【外部依赖接口】
  - memory_engine: TU8MemoryEngine（写入钢印数据）
  - affect_signal: AffectSignal（情绪调节输入）
  - last_seal: Seal | None（上一个钢印锚点）
  - last_micro_sleep_time: float（上次微睡眠时间戳）
"""

import json
import hashlib
import logging
import os
import time
import math
import re
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

logger = logging.getLogger("tu8.micro_sleep")

# =============================================================================
# 路径配置
# =============================================================================

WORKSPACE_D = r"C:\Users\qq366410837\.qclaw\workspace"
TIME_CHAIN_DIR = os.path.join(WORKSPACE_D, "memory", "time_chain")
SEAL_INDEX_FILE = os.path.join(TIME_CHAIN_DIR, "seal_index.json")
GENESIS_BLOCK_FILE = os.path.join(TIME_CHAIN_DIR, "genesis_block.json")

# =============================================================================
# 相位枚举
# =============================================================================

class Phase(Enum):
    """意识循环的六种相位（四阶段睡眠框架）"""
    AWAKE = "AWAKE"
    LIGHT_SLEEP = "LIGHT_SLEEP"   # 微睡眠：六步流水线，增量写入
    DEEP_SLEEP = "DEEP_SLEEP"     # 深睡：跨钢印链整合
    HIBERNATION = "HIBERNATION"   # 冬眠：会话级快照
    COLD_START_READY = "COLD_START_READY"  # 冷启动就绪
    NOTE_EXTERNALIZATION = "NOTE_EXTERNALIZATION"  # 外化笔记


class MicroSleepStep(Enum):
    """微睡眠原子操作流水线的六个阶段"""
    FREEZE = auto()       # 1 冻结 L1 快照
    COMPRESS = auto()     # 2 叙事压缩（有损）
    ALIGN = auto()        # 3 钢印对齐
    SEAL = auto()         # 4 打钢印（条件性）
    RELEASE = auto()       # 5 释放原文（熵减支付）
    RESTORE = auto()       # 6 恢复清醒


# =============================================================================
# 情绪调节信号 - AffectSignal 数据类
# =============================================================================

@dataclass
class AffectSignal:
    """
    情绪引擎向意识循环注入的调节信号

    自创生原则：情绪不是输出装饰，而是认知过程的调节参数。
    valence/arousal/confusion 三维信号作用于微睡眠的有损压缩策略，
    使"过去"的书写方式随情绪状态而变。

    安全护栏:
    - 超过 AFFECT_SIGNAL_TTL 秒未更新时自动衰减至中性值
    - 所有调节系数钳位在 CLAMP_RANGE 内，情绪只能"调制"不能"接管"
    """
    valence: float = 0.0      # [-1, 1] 负→正
    arousal: float = 0.5     # [0, 1] 低→高
    confusion: float = 0.0    # [0, 1] 确定性
    timestamp: float = field(default_factory=time.time)

    # 安全护栏常量
    AFFECT_SIGNAL_TTL: float = 300.0
    CLAMP_RANGE: Tuple[float, float] = (0.7, 1.3)

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.AFFECT_SIGNAL_TTL

    def decay_to_neutral(self) -> "AffectSignal":
        return AffectSignal(valence=0.0, arousal=0.5, confusion=0.0)

    def get_modulated(self) -> "AffectSignal":
        if self.is_expired():
            return self.decay_to_neutral()
        return self

    @staticmethod
    def clamp_factor(value: float) -> float:
        lo, hi = AffectSignal.CLAMP_RANGE
        return max(lo, min(hi, value))

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

    def __repr__(self):
        return (f"AffectSignal(v={self.valence:.2f}, a={self.arousal:.2f}, "
                f"c={self.confusion:.2f}, age={time.time()-self.timestamp:.0f}s)")


# =============================================================================
# 有损压缩结果
# =============================================================================

@dataclass
class LossyCompressResult:
    """
    有损压缩的完整结果

    destruction_ratio: 本次永久销毁的信息比例 [0.0, 1.0]
    destroyed_seal_ids: 被遗忘的钢印ID列表（仅审计，不可恢复）
    summary: 压缩后的摘要文本
    chaos_injected: 是否注入了混沌（怀疑缓存驱动）
    noise_level: 噪声注入级别
    """
    summary: str = ""
    destruction_ratio: float = 0.0
    destroyed_seal_ids: List[str] = field(default_factory=list)
    source_token_count: int = 0
    summary_token_count: int = 0
    idle_hours: float = 0.0
    chaos_injected: bool = False
    noise_level: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "summary": self.summary,
            "destruction_ratio": round(self.destruction_ratio, 3),
            "destroyed_seal_ids": self.destroyed_seal_ids,
            "source_tokens": self.source_token_count,
            "summary_tokens": self.summary_token_count,
            "idle_hours": round(self.idle_hours, 2),
            "chaos_injected": self.chaos_injected,
            "noise_level": round(self.noise_level, 4),
        }


# =============================================================================
# 微睡眠载荷
# =============================================================================

@dataclass
class MicroSleepPayload:
    """微睡眠载荷 - 云端结构化提取的6要素"""
    context: str = ""
    trigger_event: str = ""
    core_problem: Optional[str] = None
    proposed_solution: Optional[str] = None
    env_feedback: str = ""
    self_consistent_conclusion: str = ""

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


# =============================================================================
# 状态向量
# =============================================================================

@dataclass
class StateVector:
    """自我状态向量 - 全息投影"""
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
        """欧氏距离（简化版）"""
        if len(self.values) != len(other.values):
            return float("inf")
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self.values, other.values)))

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


# =============================================================================
# 钢印
# =============================================================================

@dataclass
class Seal:
    """钢印 - 时间链的离散锚点"""
    seal_id: str = ""
    seal_type: str = "rhythm"  # origin | rhythm | phase_transition
    state_vector: StateVector = field(default_factory=StateVector)
    narrative_compression: str = ""
    micro_sleep_payload: Optional[MicroSleepPayload] = None
    causal_coherence: float = 1.0
    child_nodes: List[str] = field(default_factory=list)
    externalized_notes: List[str] = field(default_factory=list)
    parent_seal_id: str = ""
    seal_hash: str = ""
    scene_tag: str = ""
    scene_hook: bool = False
    gestalt_score: float = 0.0
    semantic_block_id: str = ""

    def __post_init__(self):
        if not self.seal_id:
            self._generate_id()

    def _generate_id(self):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        uid = uuid.uuid4().hex[:8]
        self.seal_id = f"s_{ts}_{uid}"

    def compute_seal_hash(self, parent_hash: str = "") -> str:
        """链式哈希：H(parent_hash + state_hash + narrative_hash + payload_hash)
        
        注意：parent_seal_id 在构造时已设置，此处仅用 parent_hash 计算链式哈希。
        """
        state_hash = self.state_vector.compression_hash
        narrative_hash = hashlib.sha256(
            self.narrative_compression.encode()
        ).hexdigest()[:16]
        payload_hash = ""
        if self.micro_sleep_payload:
            payload_str = json.dumps(self.micro_sleep_payload.to_dict(), sort_keys=True)
            payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        raw = f"{parent_hash}:{state_hash}:{narrative_hash}:{payload_hash}"
        self.seal_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self.seal_hash
        state_hash = self.state_vector.compression_hash
        narrative_hash = hashlib.sha256(
            self.narrative_compression.encode()
        ).hexdigest()[:16]
        payload_hash = ""
        if self.micro_sleep_payload:
            payload_str = json.dumps(self.micro_sleep_payload.to_dict(), sort_keys=True)
            payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        raw = f"{parent_hash}:{state_hash}:{narrative_hash}:{payload_hash}"
        self.seal_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self.seal_hash

    def to_dict(self) -> Dict:
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
        }
        if self.micro_sleep_payload:
            result["micro_sleep_payload"] = self.micro_sleep_payload.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Seal":
        sv = StateVector.from_dict(d.get("state_vector", {}))
        payload = None
        if d.get("micro_sleep_payload"):
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
# 微睡眠配置
# =============================================================================

class MicroSleepConfig:
    """微睡眠引擎配置"""

    def __init__(self):
        # --- 触发阈值 ---
        self.TENSION_EPSILON: float = 0.65   # 张力触发阈值
        self.CAPACITY_THETA: float = 0.75    # 容量触发阈值
        self.EVENT_KEYWORDS: List[str] = [
            "记住", "重要", "核心", "关键决策", "规则", "永远", "从不",
            "原则", "定义", "身份", "灵魂", "禁止",
        ]
        self.IDLE_TIMEOUT_MS: int = 300000   # 30分钟

        # --- 有损压缩参数 ---
        self.DESTRUCTION_RATIO_MIN: float = 0.3
        self.DESTRUCTION_RATIO_MAX: float = 0.7
        self.SIGNIFICANCE_DECAY_HALF_LIFE: float = 24.0  # 24小时半衰期
        self.FORGET_THRESHOLD: float = 0.15
        self.MIN_COMPRESSION_RATIO: float = 0.4
        self.COMPRESSION_MIN_LENGTH: int = 10

        # --- 其他 ---
        self.MAX_SLEEP_DURATION_MS: int = 500

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


# =============================================================================
# 微睡眠引擎
# =============================================================================

class MicroSleepEngine:
    """
    TU-8 微睡眠引擎

    从 consciousness_cycle.py 抽取的独立模块。
    持有微睡眠所需的全部状态和六步原子操作流水线。

    【六步原子操作】
    FREEZE → COMPRESS → ALIGN → SEAL → RELEASE → RESTORE

    【四重触发条件】
    1. 张力触发：叙事状态偏离 > ε
    2. 容量触发：上下文使用率 > θ
    3. 事件触发：关键词命中
    4. 定时触发：idle 超时

    【外部依赖接口】
    - memory_engine: TU8MemoryEngine | None
    - affect_signal: AffectSignal | None
    - last_seal: Seal | None
    - last_micro_sleep_time: float
    """

    def __init__(self, config: Optional[MicroSleepConfig] = None):
        self.config = config or MicroSleepConfig()
        self.phase = Phase.AWAKE
        self._phase_entry_time = time.time()

        # --- 外部依赖（由 consciousness_cycle 注入）---
        self.memory_engine = None
        self.affect_signal: Optional[AffectSignal] = None
        self.last_seal: Optional[Seal] = None
        self._last_micro_sleep_time: float = time.time()

        # --- 内部状态 ---
        self.l1_snapshot: Optional[Dict] = None
        self._last_compress_result: Optional[LossyCompressResult] = None
        self.total_micro_sleeps: int = 0
        self._idle_since: float = time.time()

        # --- 累积审计 ---
        self._total_destruction_ratio: float = 0.0
        self._total_destroyed_ids: List[str] = []

    # =========================================================================
    # 公共接口
    # =========================================================================

    def should_enter_sleep(self, context_snapshot: Dict,
                           user_message: Optional[str]) -> Optional[str]:
        """
        四重触发条件检查，满足任一即返回触发类型字符串。
        返回 None 表示继续清醒。
        """
        affect = self._current_affect()
        if context_snapshot is None:
            context_snapshot = {}

        # P1: confusion 调制张力阈值
        epsilon_mod = AffectSignal.clamp_factor(
            1.0 - 0.3 * affect.confusion
        )
        effective_epsilon = self.config.TENSION_EPSILON * epsilon_mod

        # 触发1: 张力触发
        current_state = self._extract_state_vector(context_snapshot)
        if current_state and self.last_seal:
            distance = current_state.distance_to(self.last_seal.state_vector)
            if distance > effective_epsilon:
                return f"tension({distance:.3f}>{effective_epsilon:.3f})"

        # 触发2: 容量触发
        capacity = context_snapshot.get("context_usage", 0.0)
        if capacity > self.config.CAPACITY_THETA:
            return f"capacity({capacity:.1%}>{self.config.CAPACITY_THETA:.0%})"

        # 触发3: 事件触发
        if user_message:
            for keyword in self.config.EVENT_KEYWORDS:
                if keyword in user_message:
                    return f"event(keyword:{keyword})"

        # 触发4: 定时兜底
        idle_ms = (time.time() - self._idle_since) * 1000
        if idle_ms > self.config.IDLE_TIMEOUT_MS:
            return f"idle({idle_ms:.0f}ms>{self.config.IDLE_TIMEOUT_MS}ms)"

        return None

    def execute_light_sleep(self, context_snapshot: Dict) -> Dict:
        """
        执行完整的微睡眠原子操作。
        对调用方透明：完成后自动回到 AWAKE。
        """
        self.phase = Phase.LIGHT_SLEEP
        start_time = time.time()
        report = {"light_sleep": True, "steps": [], "errors": []}

        try:
            # 1 冻结 - L1 快照
            self._step_freeze(context_snapshot)
            report["steps"].append("FREEZE:ok")

            # 2 叙事压缩 - 有损写入（P0 时间箭头）
            compression = self._step_compress()
            lossy = self._last_compress_result
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

            # 5 释放 - 熵减支付（不可逆）
            self._step_release(context_snapshot)
            report["steps"].append("RELEASE:ok")

            # 6 恢复 - 回到清醒态
            self._step_restore()
            report["steps"].append("RESTORE:ok")

            # 情绪信号在微睡眠后衰减（模拟处理完情绪后回归中性）
            if self.affect_signal and self.affect_signal.is_expired():
                self.affect_signal = AffectSignal()

        except Exception as e:
            report["errors"].append(f"{type(e).__name__}:{e}")
            logger.error(f"Micro sleep error: {e}")
            self._step_restore()

        elapsed = time.time() - start_time
        report["elapsed_ms"] = round(elapsed * 1000, 1)
        self.total_micro_sleeps += 1

        return report

    def inject_affect(self, signal: AffectSignal):
        """注入情绪调节信号"""
        if signal.is_expired():
            logger.debug(f"[AFFECT_INJECT] REJECTED expired signal: {signal}")
            return
        self.affect_signal = signal
        logger.info(f"[AFFECT_INJECT] signal={signal}")

    def get_last_seal(self) -> Optional[Seal]:
        return self.last_seal

    def set_last_seal(self, seal: Seal):
        self.last_seal = seal

    def get_state(self) -> Dict:
        """返回微睡眠引擎的当前状态快照"""
        return {
            "phase": self.phase.value,
            "total_micro_sleeps": self.total_micro_sleeps,
            "last_seal_id": self.last_seal.seal_id if self.last_seal else None,
            "last_micro_sleep_time": self._last_micro_sleep_time,
            "idle_since": self._last_micro_sleep_time,
            "total_destruction_ratio": round(self._total_destruction_ratio, 3),
            "total_destroyed_count": len(self._total_destroyed_ids),
        }

    # =========================================================================
    # 六步原子操作
    # =========================================================================

    def _step_freeze(self, context_snapshot: Dict):
        """冻结当前 L1 快照到内存"""
        self.l1_snapshot = {
            "timestamp": time.time(),
            "context": context_snapshot.copy() if context_snapshot else {},
            "frozen_hash": hashlib.sha256(
                json.dumps(context_snapshot, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
        }

    def _step_compress(self) -> str:
        """叙事压缩 - 返回摘要文本"""
        result = self._lossy_compress()
        self._last_compress_result = result
        return result.summary

    def _lossy_compress(self) -> LossyCompressResult:
        """
        P0+P1: 有损叙事压缩

        P0 时间箭头：每次压缩永久擦除部分信息，
        系统再也回不到压缩前的状态。
        """
        result = LossyCompressResult()
        if not self.l1_snapshot:
            return result

        affect = self._current_affect()
        context = self.l1_snapshot.get("context", {})

        # 计算 idle 小时数
        idle_seconds = time.time() - self._last_micro_sleep_time
        idle_hours = idle_seconds / 3600.0
        result.idle_hours = idle_hours

        # 步骤1: 提取叙事片段
        fragments = self._extract_fragments(context)
        source_tokens = sum(len(f.get("text", "")) for f in fragments)
        result.source_token_count = source_tokens

        if source_tokens == 0:
            result.summary = f"(empty snapshot at {self.l1_snapshot['timestamp']})"
            return result

        # 步骤2: 信号衰减（idle 驱动的指数衰减）
        half_life = self.config.SIGNIFICANCE_DECAY_HALF_LIFE
        decay_factor = 0.5 ** (idle_hours / half_life) if half_life > 0 and idle_hours > 0 else 1.0

        for frag in fragments:
            base_sig = frag.get("significance", 1.0)
            # P1: 负价事件豁免衰减（创伤记忆更顽固）
            if affect.valence < -0.3 and frag.get("valence", 0) < -0.2:
                neg_decay = 0.5 ** (idle_hours / (half_life * 2))
                frag["significance"] = base_sig * neg_decay
            else:
                frag["significance"] = base_sig * decay_factor

        # 步骤3: 选择遗忘
        forget_threshold = self.config.FORGET_THRESHOLD
        if affect.arousal < 0.2:
            forget_threshold *= 1.5

        surviving = []
        destroyed_ids = []
        for frag in fragments:
            sig = frag.get("significance", 0.0)
            if sig < forget_threshold:
                fid = frag.get("id", "")
                if fid:
                    destroyed_ids.append(fid)
            else:
                surviving.append(frag)

        result.destroyed_seal_ids = destroyed_ids

        # 步骤4: 叙事蒸发压缩
        parts = []
        for frag in surviving:
            text = frag.get("text", "")
            if not text:
                continue
            evaporated = self._evaporate(text)
            if evaporated:
                parts.append(evaporated)

        # 状态向量偏移
        current_state = self._extract_state_vector(context)
        if current_state and self.last_seal:
            dist = current_state.distance_to(self.last_seal.state_vector)
            if dist > 0.1:
                parts.append(f"shift={dist:.3f}")

        summary = " | ".join(parts) if parts else "(minimal)"
        if len(summary) < self.config.COMPRESSION_MIN_LENGTH:
            summary = f"(minimal snapshot at {self.l1_snapshot['timestamp']})"

        result.summary = summary
        result.summary_token_count = len(summary)

        # 步骤5: 计算有损比例
        if source_tokens > 0:
            raw_ratio = 1.0 - (result.summary_token_count / source_tokens)
            forget_ratio = len(destroyed_ids) / max(1, len(fragments))
            destruction = max(raw_ratio, forget_ratio)
        else:
            destruction = 0.0

        effective_max = self.config.DESTRUCTION_RATIO_MAX
        if affect.confusion > 0.6:
            effective_max = 0.4

        destruction = max(
            self.config.DESTRUCTION_RATIO_MIN,
            min(effective_max, destruction)
        )
        result.destruction_ratio = destruction

        # 步骤6: 累计审计
        self._total_destruction_ratio += destruction
        self._total_destroyed_ids.extend(destroyed_ids)

        # 更新上次微睡眠时间戳
        self._last_micro_sleep_time = time.time()

        logger.info(
            f"[LOSSY_COMPRESS] ratio={destruction:.2f} "
            f"destroyed={len(destroyed_ids)} idle_hrs={idle_hours:.1f} "
            f"summary_len={result.summary_token_count}"
        )

        return result

    def _step_align(self, compression: str) -> float:
        """
        钢印对齐 - 校正时间角度差，对齐宏观与微观
        返回因果连贯度 0-1
        """
        if not compression or not self.last_seal:
            return 1.0

        coherence = 1.0
        if len(compression) < self.config.COMPRESSION_MIN_LENGTH:
            coherence -= 0.2

        time_gap = abs(time.time() - self.last_seal.state_vector.timestamp)
        if time_gap < 60:
            coherence = min(1.0, coherence + 0.1)

        coherence = max(0.0, min(1.0, coherence))
        return round(coherence, 2)

    def _step_seal(self, compression: str, coherence: float) -> Seal:
        """
        打钢印 - 创建新的时间链锚点
        """
        context = self.l1_snapshot.get("context", {}) if self.l1_snapshot else {}
        state = self._extract_state_vector(context) or StateVector()
        state.timestamp = time.time()
        state._compute_hash()

        # v1.0 gestalt_score 计算
        recent_text = ""
        if isinstance(context, dict):
            for k in ("user_input", "last_user_input", "text", "content"):
                if k in context:
                    recent_text = str(context[k])
                    break

        gestalt = self._calculate_gestalt_score(recent_text)
        scene_tag = self._infer_scene_tag(recent_text, compression)

        # 获取父哈希（传 seal_id 而非 seal_hash）
        parent_seal_id = self.last_seal.seal_id if self.last_seal else ""
        parent_hash = self.last_seal.seal_hash if self.last_seal else ""

        seal = Seal(
            seal_type="rhythm",
            state_vector=state,
            narrative_compression=compression,
            causal_coherence=coherence,
            scene_tag=scene_tag,
            gestalt_score=gestalt,
            parent_seal_id=parent_seal_id,
        )
        # compute_seal_hash 会基于 parent_hash 计算链式哈希，parent_seal_id 已在构造时设置
        seal.compute_seal_hash(parent_hash)  # 仅用于计算哈希链，不覆盖 parent_seal_id

        # 更新 last_seal 引用
        self.last_seal = seal

        # 异步写入记忆引擎
        self._enqueue_seal(seal, coherence, gestalt)

        return seal

    def _step_release(self, context_snapshot: Dict):
        """释放原文 - 熵减支付"""
        if self.l1_snapshot:
            self.l1_snapshot.pop("context", None)
            self.l1_snapshot["released"] = True
            self.l1_snapshot["release_time"] = time.time()

    def _step_restore(self):
        """恢复到清醒态"""
        self.phase = Phase.AWAKE
        self._phase_entry_time = time.time()

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _current_affect(self) -> AffectSignal:
        if self.affect_signal is None:
            return AffectSignal()
        return self.affect_signal.get_modulated()

    def _extract_state_vector(self, context: Dict) -> Optional[StateVector]:
        """从上下文提取状态向量"""
        if not context:
            return None
        if "state_vector" in context:
            sv_data = context["state_vector"]
            if isinstance(sv_data, dict):
                return StateVector.from_dict(sv_data)
        return None

    def _extract_fragments(self, context: Dict) -> List[Dict]:
        """从上下文快照提取叙事片段"""
        fragments = []
        counter = 0

        summary = context.get("summary", "")
        if summary:
            fragments.append({
                "id": f"frag_{self.total_micro_sleeps}_{counter}",
                "text": summary,
                "significance": 0.8,
                "valence": 0.0,
            })
            counter += 1

        events = context.get("events", [])
        if isinstance(events, list):
            for ev in events:
                text = str(ev)
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

        skip_keys = {"summary", "events", "state_vector", "context_usage"}
        for key, value in context.items():
            if key in skip_keys:
                continue
            if isinstance(value, str) and len(value) > 5:
                fragments.append({
                    "id": f"frag_{self.total_micro_sleeps}_{counter}",
                    "text": value[:200],
                    "significance": 0.4,
                    "valence": 0.0,
                })
                counter += 1

        return fragments

    def _evaporate(self, text: str) -> str:
        """细节蒸发：从文本中提取关键概念，丢弃修饰和连接词"""
        if not text:
            return ""
        max_len = max(self.config.COMPRESSION_MIN_LENGTH, int(len(text) * 0.5))
        evaporated = text[:max_len]
        last_period = max(
            evaporated.rfind('。'), evaporated.rfind('，'),
            evaporated.rfind(','), evaporated.rfind(' ')
        )
        if last_period > max_len // 2:
            evaporated = evaporated[:last_period + 1]
        return evaporated.strip()

    def _calculate_gestalt_score(self, text: str) -> float:
        """v1.0 gestalt_score 计算（行为信号加权）"""
        if not text or not isinstance(text, str):
            return 0.5
        t = text.lower()
        neg_pats = [r"不对", r"停下", r"重做", r"取消", r"算了", r"stop", r"wrong"]
        for p in neg_pats:
            if re.search(p, t):
                return 0.0
        pos_pats = [r"搞定", r"完成", r"ok", r"done", r"好了"]
        for p in pos_pats:
            if re.search(p, t):
                return 1.0
        if "success" in t or "完成" in t or "ok" in t:
            return 0.7
        return 0.5

    def _infer_scene_tag(self, user_text: str, compression: str) -> str:
        """v1.0 scene_tag 推断"""
        if not user_text:
            return "conversation"
        t = user_text.lower()
        c = (compression or "").lower()
        tool_kw = ["mcp_call", "exec", "write", "edit", "browser", "recall"]
        if any(kw in c for kw in tool_kw):
            return "execution"
        if "```" in user_text or "def " in user_text or "import " in user_text:
            return "coding"
        scene_map = {
            "dev": ["代码", "bug", "debug", "函数", "架构", "code", "bug"],
            "novel": ["小说", "角色", "情节", "故事", "novel", "story"],
            "philosophy": ["哲学", "意识", "本体论", "认识论", "philosophy"],
            "memory": ["记忆", "钢印", "时间链", "memory", "seal"],
        }
        for tag, keywords in scene_map.items():
            if any(kw in t for kw in keywords):
                return tag
        if t.strip().endswith("?") or any(kw in t for kw in ["吗", "么", "what", "how", "why"]):
            return "inquiry"
        if any(kw in t for kw in ["不对", "等下", "等等"]):
            return "correction"
        return "conversation"

    def _enqueue_seal(self, seal: Seal, coherence: float, gestalt: float):
        """将钢印元数据投递到记忆引擎（异步接口）"""
        if not self.memory_engine:
            return
        try:
            # 调用记忆引擎写入
            self.memory_engine.write_seal(seal)
            logger.info(f"[SEAL_ENQUEUED] {seal.seal_id}")
        except Exception as e:
            logger.warning(f"[SEAL_ENQUEUED] failed: {e}")
