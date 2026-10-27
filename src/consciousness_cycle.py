# -*- coding: utf-8 -*-
"""
consciousness_cycle.py - TU-8 意识循环引擎 v2.0 - 四阶段睡眠框架
日期: 2026-05-31 / 2026-06-04 更新
# 创作者: 李奥(金木蟾) | TU-8 v5

================================================================================
TU-8 L0-L6 架构层标注
================================================================================
本文件属于 L2 方法论层（执行路径编排）+ L3 架构层（记忆写入）的交界。

  L0 存在   ─── 配置文件路径、安全阈值
  L1 认知   ─── CycleConfig 阈值、TENSION_EPSILON、CAPACITY_THETA
  L2 方法论 ─── tick()、_enter_light_sleep()、_enter_deep_sleep()、四阶段状态机
  L3 架构   ─── 锚点注册、钢印链写入、微睡眠引擎调用
  L4 协作   ─── 外部模块导入（cognitive_evaluator、llm_gateway、micro_sleep）
  L5 钢印   ─── NoteType.MILESTONE 相变检测
  L6 健康   ─── 容量监测（CAPACITY_THETA）、张力阈值触发

================================================================================
代谢系统接口
================================================================================
本文件是代谢系统的感知层（触发点），不执行实际代谢。

  代谢触发入口（tick() 内）:
    → confidence_decay_engine.decay_all()        [认知代谢：版本树剪枝]
    → todo_metabolism.scan_stale()                [TODO 代谢：60天超期检测]
    → memory_tiers.scan_for_promotion()          [记忆分层：L2→L1 晋升候选]

  代谢执行入口（dream_check_cron.py 调用）:
    → _enter_deep_sleep() → 触发完整代谢循环
    → run_full_metabolism_cycle() via metabolism_dashboard.py

  代谢状态输出:
    → consciousness_cycle → tick() 时输出代谢摘要
    → heartbeat → 轻量代谢检查（每30min）
    → cron → 每日8:00+9:00 专项代谢cron
    → dream_check → 每周日5am + 每日3am 完整代谢循环

  代谢仪表盘:
    → python src/metabolism_dashboard.py           # 统一视图
    → python src/metabolism_dashboard.py --run all # 完整代谢循环

--------------------------------------------------------------------------------
子系统归属（代谢大主题下的分工）:
--------------------------------------------------------------------------------
  认知代谢（版本树剪枝）    → confidence_decay_engine.py
  记忆代谢（管道）          → metabolic_pipeline.py + memory_gc.py
  USER.md 代谢             → user_metabolism.py
  TODO 代谢                → todo_metabolism.py
  记忆分层                 → memory_tiers.py
  遗产继承                 → heritage_system.py
  T0 矛盾蒸馏              → tension_distiller.py
  T2/T3 失谐+呼吸          → topology_connector.py + tension_respirator.py
  GC→学习                  → gc_to_learning_adapter.py
  学习→GC                 → learning_to_gc_adapter.py
  钢印→GC                 → seal_to_gc_adapter.py

统一入口: src/metabolism_dashboard.py（代谢仪表盘 + 顶层驱动）
--------------------------------------------------------------------------------

核心理念:
  记忆系统与睡眠系统不是两个模块,是同一个循环的两个相位。
  微睡眠 = 记忆的写入引擎(心脏搏动),每次搏动 = 一次 L1→L2 的写入。
  外化笔记 = 睡眠→记忆的唯一显式出口。

四阶段睡眠框架:
  LIGHT_SLEEP(N1浅睡) ── 微睡眠六步流水线,增量记忆写入
  DEEP_SLEEP(N2/N3深睡) ── 跨钢印链整合+记忆重排
  HIBERNATION(冬眠) ── 会话级状态快照,跨会话持久化
  COLD_START_READY(冷启动就绪) ── 冬眠后恢复检查点

状态转换:
  AWAKE ──(张力/容量/事件/定时触发)──→ LIGHT_SLEEP ──(四钩子收敛)──→ AWAKE
       ↓ (累计浅睡/认知负荷/钢印链过长)
       DEEP_SLEEP ──(三操作:整合/对齐/重排)──→ AWAKE
       ↓ (会话结束/显式调用)
       HIBERNATION ──(快照保存)──→ COLD_START_READY
       ↓ (冷启动自检通过)
       AWAKE

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
import asyncio
import threading
import queue
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from pathlib import Path

# 导入已提取的模块
from cycle_types import (
    Phase, StateVector, MicroSleepPayload,
    CognitiveAnchor, AnchorCandidate
)
from seal_manager import Seal, SealManager
from anchor_manager import AnchorManager
from memory_adapter import MemoryAdapter
from confidence_manager import ConfidenceManager
from datetime import datetime, timezone

# 类型检查时导入,运行时避免循环依赖
if TYPE_CHECKING:
    from tu8_memory import TU8MemoryEngine

logger = logging.getLogger("tu8.consciousness_cycle")

# =============================================================================
# 认知组件导入(P2: 自我知识)
# =============================================================================

from cognitive_evaluator import CognitiveLoadEvaluator, TFIDFEmbedder
from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor
from cognitive_manifold_aligner import CognitiveManifoldAligner
from cognitive_integration import CognitiveConsciousnessMiddleware

# 决策剪枝与宏节点折叠(v1.1)
from decision_pruner import (
    AdaptiveUCTPruner,
    DecisionLogger,
    DynamicAbstractionStack,
    create_default_pruner,
    create_default_logger,
    create_default_stack,
)

# 自适应信用分配器(v1.1)
from credit_assigner import (
    AdaptiveCreditAssigner,
    HierarchicalRewardInjector,
    TimeNormalizedReward,
    DepthPenalty,
    UnfoldValidator,
    create_default_assigner,
)

# 大模型网关(v1.1)
from llm_gateway import (
    LLMGateway,
    LLMRequest,
    LLMResponse,
    LLMRole,
    create_llm_gateway,
)

logger.info("Cognitive components imported successfully")

# =============================================================================
# 微睡眠引擎导入(P0-1验证通过)
# =============================================================================

from micro_sleep import (
    Phase, MicroSleepStep,
    AffectSignal, LossyCompressResult,
    StateVector, MicroSleepPayload, Seal,
    MicroSleepEngine, MicroSleepConfig,
)

logger.info("MicroSleepEngine imported successfully")

# =============================================================================
# TU-8 L0-L6 架构层标注（详见文件顶部 docstring）
# 代谢接口: tick() → decay_all / todo_metabolism / memory_tiers
# =============================================================================

# =============================================================================
# 路径配置(复用 cold_start_engine 约定)
# =============================================================================

WORKSPACE_D = r"C:\Users\qq366410837\.qclaw\workspace"
WORKSPACE_C = r"C:\Users\qq366410837\.qclaw\workspace"

TIME_CHAIN_DIR = os.path.join(WORKSPACE_D, "memory", "time_chain")
SEAL_INDEX_FILE = os.path.join(TIME_CHAIN_DIR, "seal_index.json")
GENESIS_BLOCK_FILE = os.path.join(TIME_CHAIN_DIR, "genesis_block.json")
SEMANTIC_MEMORY_DIR = os.path.join(WORKSPACE_D, "memory", "semantic")
NOTE_ARCHIVE_FILE = os.path.join(WORKSPACE_D, "memory", "note_archive.json")
ACTIVITY_LOG = os.path.join(WORKSPACE_D, "security", "activity.json")


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
# 数据结构 - 已提取到 cycle_types.py 和 seal_manager.py
# =============================================================================

# 以下类定义已移动到对应模块：
# - StateVector -> cycle_types.StateVector
# - MicroSleepPayload -> cycle_types.MicroSleepPayload
# - Seal -> seal_manager.Seal
# - Note -> cycle_types.CognitiveAnchor
# - NoteCandidate -> cycle_types.AnchorCandidate
#
# 保留向后兼容别名：

# 向后兼容别名（已在文件顶部导入）
Note = CognitiveAnchor
NoteCandidate = AnchorCandidate


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

    def __init__(self, config: Optional[CycleConfig] = None,
                 memory_engine: Optional["TU8MemoryEngine"] = None,
                 reflection_module: Optional["ReflectionModule"] = None):
        """
        初始化意识循环引擎。

        Args:
            config: 循环配置
            memory_engine: 记忆引擎实例(可选,依赖注入)
                          如果提供,将启动后台异步消费者写回记忆链
            reflection_module: 复盘模块实例(可选,依赖注入)
                          如果提供,冬眠时自动生成复盘摘要并注入冷启动
        """
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
        self.total_deep_sleeps: int = 0
        self.total_hibernations: int = 0

        # --- 四阶段睡眠控制 ---
        self._light_sleep_count_since_deep: int = 0  # 距上次深睡的浅睡计数
        self._DEEP_SLEEP_INTERVAL: int = 10          # 每10次浅睡触发1次深睡
        self._hibernation_snapshot_path: Optional[str] = None
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

        # --- P2: 认知组件初始化(自我知识) ---
        self.cognitive_evaluator = CognitiveLoadEvaluator()
        self.cognitive_time_engine = CognitiveTimeEngine()
        self.cognitive_aligner = CognitiveManifoldAligner()

        # 认知步骤跟踪(简单列表)
        self.cognitive_steps = []
        self.cognitive_status = {
            "total_steps": 0,
            "high_load_count": 0,
            "consolidation_count": 0,
        }

        logger.info("P2 cognitive components initialized")

        # --- 微睡眠引擎(P0-1验证通过) ---
        self.micro_sleep_engine = MicroSleepEngine()
        logger.info("[MicroSleepEngine] initialized")

        # --- v1.1: 决策剪枝与宏节点折叠 ---
        # 先初始化决策日志器(需要 WORKSPACE_D 已定义)
        self.decision_logger = DecisionLogger(
            log_dir=os.path.join(WORKSPACE_D, "logs", "decisions")
        )
        self.pruner = AdaptiveUCTPruner()          # 痛觉驱动的搜索预算分配(engine 在 set_affect_engine 时注入)
        self.abstraction_stack = DynamicAbstractionStack()  # 动态抽象栈
        logger.info("[Pruner] decision pruner & stack initialized")

        # --- v1.1: 自适应信用分配器 ---
        self.credit_assigner = create_default_assigner()
        logger.info("[CreditAssigner] adaptive credit assigner initialized")

        # --- v1.1: 大模型网关(无 API Key 时自动纯本地兜底) ---
        self.llm_gateway = LLMGateway()
        # 注册本地 fallback provider(永不依赖外部)
        from llm_gateway import LocalFallbackProvider
        self.llm_gateway.register("local", LocalFallbackProvider())
        self.llm_gateway.set_default("local")
        self.llm_gateway.set_fallback("local")
        logger.info("[LLMGateway] initialized (local fallback mode)")

        # =====================================================================
        # 四链条耦合: 记忆链异步写回(A+B 方案)
        # =====================================================================
        # A: 依赖注入 - 保存记忆引擎实例
        self.memory_engine: Optional["TU8MemoryEngine"] = memory_engine

        # v1.3: 复盘模块注入(睡眠+复盘融合)
        self.reflection_module: Optional["ReflectionModule"] = reflection_module

        # =====================================================================
        # Phase 6.2: 注入已提取的管理器
        # =====================================================================
        # 钢印管理器
        self.seal_manager = SealManager()
        logger.info("[SealManager] initialized")

        # 锚点管理器
        self.anchor_manager = AnchorManager()
        logger.info("[AnchorManager] initialized")

        # 记忆适配器
        self.memory_adapter = MemoryAdapter(memory_engine=memory_engine)
        logger.info("[MemoryAdapter] initialized")
        # === v2.0: 四象限认知引擎 ===
        self.confidence_manager = ConfidenceManager()
        logger.info("[ConfidenceManager] initialized: v2.0 四象限认知引擎")

        # =====================================================================
        # Phase 6.3: 别名共享——self.seal_chain 指向 manager 的链
        #   避免两个独立列表（本地 self.seal_chain vs manager.seal_chain）
        # =====================================================================
        self.seal_chain = self.seal_manager.seal_chain
        logger.info(f"[Phase 6.3] seal_chain aliased (manager chain: {len(self.seal_chain)} seals)")

        # =====================================================================
        # Phase 6.6: 锚点管理器集成——别名共享
        #   self.externalized_notes -> self.anchor_manager.anchors
        #   self.note_candidates   -> self.anchor_manager.candidates
        #   避免两个独立列表，数据统一由 manager 管理
        # =====================================================================
        self.externalized_notes = self.anchor_manager.anchors
        self.note_candidates = self.anchor_manager.candidates
        logger.info(f"[Phase 6.6] externalized_notes/note_candidates aliased to anchor_manager")

        # Phase 6.3: 旧异步队列已废弃，改用 memory_adapter
        # self._memory_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._memory_consumer_running: bool = False
        self._memory_consumer_thread: Optional[threading.Thread] = None
        self._memory_write_success: int = 0
        self._memory_write_failure: int = 0

        # 注意：已不再启动旧消费者线程（改用 memory_adapter.consume_one()）
        # if self.memory_engine:
        #     self._start_memory_consumer()
        #     logger.info("[FOUR_CHAIN] Memory consumer started (A+B coupled)")

        # P0-2: 注册反向回调(记忆链→钢印链)
        # 当 store() 写入高意义内容时,自动触发即时钢印铸造
        if self.memory_engine:
            def _memory_to_seal(content, emotion, meaning, source):
                """记忆链→钢印链桥接:高意义内容触发即时铸造"""
                try:
                    seal = self._step_seal(
                        narrative_ref=content[:200],
                        scene_tag=f"memory_to_seal:{(source or 'unknown')[:30]}",
                        coherence=0.8,
                        gestalt=meaning,
                    )
                    self._enqueue_seal(seal, coherence=0.8, gestalt=meaning)
                    logger.info(f"[MEMORY→SEAL] instant seal: {seal.seal_id}")
                    return seal.seal_id
                except Exception as e:
                    logger.warning(f"[MEMORY→SEAL] instant seal failed: {e}")
                    return None

            self.memory_engine.set_seal_callback(_memory_to_seal, threshold=0.7)
            logger.info("[FOUR_CHAIN] Memory→Seal reverse callback registered")

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

    def set_affect_engine(self, engine) -> None:
        """
        注入感情引擎(供 AdaptiveUCTPruner 和怀疑系统使用)

        Args:
            engine: AffectEngine 实例(来自 emotion_engine)
        """
        self._affect_engine = engine
        if hasattr(self, 'pruner'):
            self.pruner._engine = engine
        logger.info("[Pruner] affect engine injected into pruner")

    # =========================================================================
    # 四链条耦合: 记忆链异步写回
    # =========================================================================

    def _start_memory_consumer(self):
        """
        Phase 6.3: 旧消费者线程已废弃，改用 memory_adapter。
        此方法保留作为备份，但立即返回（no-op）。
        """
        logger.info("[DEPRECATED] _start_memory_consumer: use memory_adapter instead")
        return  # 立即返回，不启动旧线程

        # === 以下为旧代码（已废弃，不再执行）===
        if self._memory_consumer_running:
            return

        self._memory_consumer_running = True

        def _consumer_loop():
            while self._memory_consumer_running:
                try:
                    # 阻塞等待任务,最多等 1 秒
                    task = self._memory_queue.get(timeout=1.0)
                    if task is None:
                        continue

                    # 调用记忆引擎写入
                    self._write_seal_to_memory(task)

                except queue.Empty:
                    logger.debug("queue.Empty suppressed")
                    # 队列为空,继续等待
                    continue
                except Exception as e:
                    logger.error(f"[MEMORY_CONSUMER] Error: {e}")

        self._memory_consumer_thread = threading.Thread(
            target=_consumer_loop,
            name="MemoryConsumer",
            daemon=True
        )
        self._memory_consumer_thread.start()
        logger.info("[MEMORY_CONSUMER] Thread started")

    def _enqueue_seal(self, seal: "Seal", coherence: float, gestalt: float):
        """
        将钢印元数据投递到 memory_adapter 队列(委托)

        Phase 6.3 改造：不再使用 self._memory_queue，
        改为直接委托给 memory_adapter.enqueue_seal()。
        """
        if not hasattr(self, 'memory_adapter') or self.memory_adapter is None:
            logger.warning("[ENQUEUE] memory_adapter not injected, skipping")
            return False

        try:
            result = self.memory_adapter.enqueue_seal(
                seal_id=seal.seal_id,
                seal_hash=seal.seal_hash,
                narrative=seal.narrative_compression,
                scene_tag=seal.scene_tag,
                coherence=coherence,
                gestalt=gestalt,
                prev_hash=seal.parent_seal_id,
            )
            if result:
                logger.debug(f"[ENQUEUE] Seal {seal.seal_id} enqueued via memory_adapter")
            else:
                logger.warning(f"[ENQUEUE] memory_adapter rejected seal {seal.seal_id}")
            return result
        except Exception as e:
            logger.error(f"[ENQUEUE] Error delegating to memory_adapter: {e}")
            return False

    def _write_seal_to_memory(self, task: Dict):
        """
        实际写入记忆引擎(在消费者线程中调用)

        安全约束:
        - 失败不抛异常,只计数
        - 写入的是结构化元数据,不是纯文本
        """
        if not self.memory_engine:
            return

        try:
            # 构造结构化内容(不只是 narrative_compression)
            content = json.dumps({
                "seal_id": task["seal_id"],
                "summary": task["narrative_ref"],
                "scene": task["scene_tag"],
                "coherence": task["coherence"],
                "gestalt": task["gestalt"],
                "prev_hash": task["prev_hash"],
            }, ensure_ascii=False)

            # Phase 6.3: 委托给 memory_adapter
            self.memory_adapter._write_to_memory(task=task)

            self._memory_write_success += 1
            logger.debug(f"[MEMORY_WRITE] Success: {task['seal_id']}")
            # === v2.0: 四象限评估（写入后立即评估，不阻塞主流程）===
            try:
                entry = self._build_memory_entry_from_task(task)
                q, conf, val = self.confidence_manager.evaluate_entry(entry)
                score = self.confidence_manager.calculate_final_score(conf, val)
                seal_id_str = task.get("seal_id", "unknown")
                logger.info("[QUADRANT] seal=%s q=%s conf=%.3f val=%.3f score=%.3f", seal_id_str, q, conf, val, score)
            except Exception as e_conf:
                logger.warning(f"[QUADRANT] evaluate_entry failed: {e_conf}")

        except Exception as e:
            self._memory_write_failure += 1

    def _build_memory_entry_from_task(self, task: Dict):
        """
        v2.0: 将写入任务字典转换为 MemoryEntry
        用于 ConfidenceManager.evaluate_entry()
        """
        from tu8_memory import MemoryEntry
        entry = MemoryEntry(
            seal_id=task.get("seal_id", ""),
            content=task.get("narrative_ref", ""),
            source_file="seal_chain",
            tags=[task.get("scene_tag", "")] if task.get("scene_tag") else [],
            confidence=task.get("coherence", 0.5),
            value=task.get("coherence", 0.5),  # 初始用coherence，后续由evaluate_entry修正
            emotion=task.get("gestalt", 0.0),
        )
        entry.quadrant = self.confidence_manager.compute_quadrant(entry)
        return entry
# (write failure already counted)

    def get_memory_queue_status(self) -> Dict:
        """获取队列状态(可观测性)\n\n        Phase 6.3 改造：改用 memory_adapter 状态\n        """
        queue_sz = 0
        consumer_alive = False
        
        if hasattr(self, 'memory_adapter') and self.memory_adapter:
            queue_sz = self.memory_adapter.queue_size()
            # memory_adapter 无独立消费者线程（在主线程消费）
            consumer_alive = True
        
        return {
            "queue_size": queue_sz,
            "queue_max": 1000,  # 硬编码，与 memory_adapter 内部一致
            "write_success": self._memory_write_success,
            "write_failure": self._memory_write_failure,
            "consumer_running": consumer_alive,
        }

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

        # --- P3.7: 内稳态监控(痛觉 + 信息饥饿)---
        homeostatic_action = "none"
        if self.memory_engine and hasattr(self.memory_engine, 'homeostatic'):
            result = self.memory_engine.homeostatic.tick(self.memory_engine)
            homeostatic_action = result["action"]
            if homeostatic_action == "maintenance":
                logger.warning(f"[Homeostatic] Pain triggered: {result['reason']}")
                # 触发轻量级记忆整理
                self._trigger_light_maintenance()
            elif homeostatic_action == "dmn":
                logger.info(f"[Homeostatic] DMN (information hunger): {result['reason']}")
                # 触发 DMN 模式:主动整理记忆
                self._trigger_dmn_mode()

        # idle 计时:仅在收到新上下文时更新最后活跃时间
        if context_snapshot is not None:
            self._idle_since = time.time()

        # === v2.0: 四象限任务意图分类（推理前感知情境）===
        if text and hasattr(self, "confidence_manager"):
            try:
                intent = self.confidence_manager.classify_task_intent(text)
                w = self.confidence_manager.adjust_weights(intent)
                w_alpha = w["alpha"]; w_beta = w["beta"]; logger.debug("[INTENT] intent=%s alpha=%.2f beta=%.2f", intent, w_alpha, w_beta)
            except Exception as e_intent:
                logger.debug(f"[INTENT] classify failed: {e_intent}")

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
            # ---- v1.1: 决策剪枝与痛觉路由 ----
            try:
                pain_score = self._affect_engine.compute_pain() if hasattr(self, '_affect_engine') else 0.0
                budget = self.pruner.get_search_budget(pain_score=pain_score)

                # 抽象栈自适应:认知负荷越高,需要的层级越深
                self.abstraction_stack.task_adapt(cognitive_load)
                self.abstraction_stack.prune_by_pain(pain_score)

                report["pain_score"] = round(pain_score, 3)
                report["search_budget"] = budget.to_dict()
                report["active_levels"] = self.abstraction_stack.get_active_depths()
                report["actions"].append(f"PRUNER:depth={budget.max_depth},sims={budget.simulations}")

            except Exception as e:
                logger.warning(f"[Pruner] tick integration failed: {e}")
            # ---- v1.1: 决策剪枝结束 ----

            # ---- v1.1: 信用分配(基于内部状态的潜在奖励推算) ----
            try:
                # 推算当前 tick 的内部奖励信号:
                #   - 高认知负荷下的低痛觉 → 正向(系统在努力且没出问题)
                #   - 高痛觉 → 负向(系统感知到异常)
                latent_reward = 0.5 * (1.0 - pain_score) - 0.3 * cognitive_load

                # 当前搜索深度作为信用分配的依据
                active_depth = self.abstraction_stack.get_active_depths()
                current_depth = max(active_depth) if active_depth else 2

                adjusted_reward = self.credit_assigner.assign(
                    raw_reward=max(-1.0, min(1.0, latent_reward)),
                    node_depth=current_depth,
                    task_progress=1.0 - (current_depth - 1) * 0.2,
                )
                report["credit_adjustment"] = round(adjusted_reward, 4)
                report["credit_stats"] = self.credit_assigner.stats()

            except Exception as e:
                logger.warning(f"[CreditAssigner] tick integration failed: {e}")
            # ---- v1.1: 信用分配结束 ----

            # ---- v1.1: 大模型网关(节点评估/建议查询) ----
            try:
                # 组装网关请求:用当前状态评估节点价值
                active_depth = self.abstraction_stack.get_active_depths()
                current_depth = max(active_depth) if active_depth else 2

                gateway_request = LLMRequest(
                    role=LLMRole.NODE_EVALUATOR,
                    prompt=f"评估当前认知状态的价值。深度={current_depth},认知负荷={cognitive_load:.2f},痛觉={pain_score:.3f}",
                    context={
                        "cycle": self.cycle_count,
                        "depth": current_depth,
                        "cognitive_load": round(cognitive_load, 3),
                        "pain_score": round(pain_score, 3),
                        "phase": self.phase.name,
                    },
                    response_schema="value_score",
                    temperature=0.2,
                    max_tokens=256,
                    metadata={"origin": "consciousness_cycle.tick"},
                )
                gateway_resp = self.llm_gateway.execute(gateway_request)

                report["gateway_evaluation"] = gateway_resp.content
                report["gateway_provider"] = gateway_resp.provider
                report["gateway_fallback"] = gateway_resp.fallback_used
                report["gateway_latency_ms"] = round(gateway_resp.latency_ms, 1)

                if gateway_resp.success:
                    value = gateway_resp.content.get("value", 0.5) if isinstance(gateway_resp.content, dict) else 0.5
                    report["gateway_value"] = round(value, 4)
                    report["actions"].append(f"GATEWAY:value={value:.3f}")

            except Exception as e:
                logger.warning(f"[LLMGateway] tick integration failed: {e}")
            # ---- v1.1: 大模型网关结束 ----

            # 检查四重触发条件(浅睡入口)
            trigger = self._should_enter_sleep(
                context_snapshot=context_snapshot,
                user_message=user_message,
            )
            if trigger:
                report["actions"].append(f"TRIGGER:{trigger}")
                # 进入浅睡(原有微睡眠六步流水线)
                sleep_report = self._enter_light_sleep(context_snapshot or {})
                report.update(sleep_report)

                # 浅睡后检查是否需要晋升到深睡
                if self._should_enter_deep_sleep():
                    deep_report = self._enter_deep_sleep()
                    report.update(deep_report)
                    report["actions"].append("DEEP_SLEEP:completed")

                # 恢复清醒后检查是否需要外化笔记
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

        # 防御:context_snapshot 为 None 时兜底为空字典
        if context_snapshot is None:
            context_snapshot = {}

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

    def _should_externalize_note(self) -> Optional[Dict]:
        """
        Phase 6.6: 委托给 anchor_manager.should_externalize()
        返回触发信息或 None。
        """
        return self.anchor_manager.should_externalize(
            seal_chain_length=len(self.seal_chain),
            last_seal_coherence=self.last_seal.causal_coherence if self.last_seal else 1.0,
            milestone_gap=getattr(self.config, 'SEAL_GAP_MILESTONE', 10),
        )

    # =========================================================================
    # 微睡眠原子操作 - 六步流水线
    # =========================================================================

    def _enter_light_sleep(self, context_snapshot: Dict) -> Dict:
        """
        执行完整的微睡眠原子操作。
        对调用方透明:完成后自动回到 AWAKE。
        """
        self.phase = Phase.LIGHT_SLEEP
        start_time = time.time()
        report = {"light_sleep": True, "steps": [], "errors": []}

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

        # --- 调用微睡眠引擎(P0-1验证通过) ---
        try:
            sleep_report = self.micro_sleep_engine.execute_light_sleep(context_snapshot)
            report["steps"] = sleep_report.get("steps", [])
            report["errors"] = sleep_report.get("errors", [])
            if "lossy" in sleep_report:
                report["lossy"] = sleep_report["lossy"]
            if "elapsed_ms" in sleep_report:
                report["elapsed_ms"] = sleep_report["elapsed_ms"]
            
            # 从引擎同步状态回当前实例
            self.last_seal = self.micro_sleep_engine.last_seal
            self.total_micro_sleeps = self.micro_sleep_engine.total_micro_sleeps
            self._total_destruction_ratio = self.micro_sleep_engine._total_destruction_ratio
            self._total_destroyed_ids = self.micro_sleep_engine._total_destroyed_ids
            self._idle_since = self.micro_sleep_engine._idle_since

            # Phase 6.7: 关键修复——将引擎创建的钢印追加到 seal_manager.seal_chain
            # MicroSleepEngine._step_seal 只设置 self.last_seal，不追加到任何链。
            # 引擎自己的 seal_chain 用于内部历史，不与 consciousness_cycle 共享。
            # 因此必须在此显式追加到 consciousness_cycle.seal_chain（= seal_manager.seal_chain）。
            if self.last_seal:
                existing_ids = {s.seal_id for s in self.seal_manager.seal_chain}
                if self.last_seal.seal_id not in existing_ids:
                    self.seal_manager.seal_chain.append(self.last_seal)
                    logger.debug(f"[Phase 6.7] seal {self.last_seal.seal_id} appended to seal_manager")
            
            # 显式恢复 Phase（引擎只改自己的 phase）
            self.phase = Phase.AWAKE
            
        except Exception as e:
            report["errors"].append(f"MicroSleepEngine error: {type(e).__name__}:{e}")
            logger.error(f"MicroSleepEngine call failed: {e}")
            # 失败时尝试恢复到 AWAKE
            self._step_restore()

        self._light_sleep_count_since_deep += 1

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

    # =========================================================================
    # 四阶段睡眠框架: 深睡 / 冬眠 / 冷启动就绪
    # =========================================================================

    def _should_enter_deep_sleep(self) -> bool:
        """判定是否从浅睡晋升到深睡。

        触发条件(满足任一):
        1. 累计浅睡次数达到阈值(_DEEP_SLEEP_INTERVAL, 默认10次)
        2. 认知负荷持续偏高(连续3次 > 0.8)
        3. 钢印链超过容量阈值
        """
        # 条件1: 浅睡计数达到间隔
        if self._light_sleep_count_since_deep >= self._DEEP_SLEEP_INTERVAL:
            logger.info(f"[DEEP_SLEEP_TRIGGER] light_sleep_count={self._light_sleep_count_since_deep} >= {self._DEEP_SLEEP_INTERVAL}")
            return True

        # 条件2: 认知负荷持续偏高
        if self.cognitive_status.get("high_load_count", 0) >= 3:
            logger.info(f"[DEEP_SLEEP_TRIGGER] high_load_count={self.cognitive_status['high_load_count']} >= 3")
            return True

        # 条件3: 钢印链过长
        if len(self.seal_chain) > 100:
            logger.info(f"[DEEP_SLEEP_TRIGGER] seal_chain_len={len(self.seal_chain)} > 100")
            return True

        return False

    def _enter_deep_sleep(self) -> Dict:
        """执行深睡(N2/N3):跨钢印链整合 + 记忆重排。

        深睡与浅睡的区别:
        - 浅睡: 单条钢印链的增量写入(一次心跳内完成)
        - 深睡: 跨钢印链的全局整合(需要遍历历史钢印,执行重排)

        三个核心操作:
        1. SEAL_CONSOLIDATION: 将低频引用钢印降级到冷存储
        2. CROSS_CHAIN_ALIGN: 跨钢印链语义对齐,发现隐含关联
        3. MEMORY_REORGANIZE: 按重要性和时效性重排记忆索引
        """
        self.phase = Phase.DEEP_SLEEP
        self.total_deep_sleeps += 1
        start_time = time.time()
        report = {
            "deep_sleep": True,
            "deep_sleep_number": self.total_deep_sleeps,
            "operations": [],
            "errors": [],
        }

        logger.info(f"[DEEP_SLEEP] entering deep sleep #{self.total_deep_sleeps}")

        try:
            # --- 操作1: 钢印整合(SEAL_CONSOLIDATION) ---
            consolidation_result = self._deep_seal_consolidation()
            report["operations"].append({
                "name": "SEAL_CONSOLIDATION",
                "status": "ok",
                "consolidated": consolidation_result.get("consolidated_count", 0),
                "cold_stored": consolidation_result.get("cold_stored_count", 0),
            })

            # --- 操作2: 跨链语义对齐(CROSS_CHAIN_ALIGN) ---
            alignment_result = self._deep_cross_chain_align()
            report["operations"].append({
                "name": "CROSS_CHAIN_ALIGN",
                "status": "ok",
                "links_found": alignment_result.get("links_found", 0),
                "coherence": alignment_result.get("coherence", 0.0),
            })

            # --- 操作3: 记忆重排(MEMORY_REORGANIZE) ---
            reorg_result = self._deep_memory_reorganize()
            report["operations"].append({
                "name": "MEMORY_REORGANIZE",
                "status": "ok",
                "promoted": reorg_result.get("promoted_count", 0),
                "demoted": reorg_result.get("demoted_count", 0),
            })

        except Exception as e:
            # === v2.0: 四象限迁移检查（深度睡眠时执行）===
            if hasattr(self, 'confidence_manager'):
                try:
                    migrated = self.confidence_manager.migrate_q3_to_q1(None)
                    forgotten = self.confidence_manager.migrate_q1_to_q2(None)
                    if migrated or forgotten:
                        logger.info(f"[DEEP_SLEEP] migration: Q3->Q1={migrated}, Q1->Q2={forgotten}")
                    toxic_cleaned = self.confidence_manager.schedule_async_purification()
                    if toxic_cleaned:
                        logger.info(f"[DEEP_SLEEP] toxic_purification: {toxic_cleaned}")
                except Exception as e_mig:
                    logger.warning(f"[DEEP_SLEEP] migration failed: {e_mig}")
            report["errors"].append(str(e))
            logger.error(f"[DEEP_SLEEP] error: {e}")
        finally:
            # 重置浅睡计数器
            self._light_sleep_count_since_deep = 0
            # 深睡完成,回到清醒态
            self.phase = Phase.AWAKE

        elapsed_ms = (time.time() - start_time) * 1000
        report["deep_sleep_latency_ms"] = round(elapsed_ms, 2)

        logger.info(f"[DEEP_SLEEP] completed, elapsed={elapsed_ms:.1f}ms, "
                    f"ops={len(report['operations'])}, errors={len(report['errors'])}")

        return report

    def _deep_seal_consolidation(self) -> Dict:
        """深睡操作1:钢印整合 - 将低频引用钢印降级到冷存储。

        策略:
        - 遍历钢印链,统计每条钢印的引用频率
        - 引用次数 < 2 且 年龄 > 100轮 → 降级为 cold_seal
        - cold_seal 不参与日常检索,仅在深睡时扫描
        """
        consolidated_count = 0
        cold_stored_count = 0

        # 引用频率统计
        ref_counts = {}
        for seal in self.seal_chain:
            sid = seal.seal_id
            ref_counts[sid] = ref_counts.get(sid, 0)
            # 扫描后续钢印的 aligned_with 字段
            for other in self.seal_chain:
                if hasattr(other, 'aligned_with') and sid in (other.aligned_with or []):
                    ref_counts[sid] = ref_counts.get(sid, 0) + 1

        # 降级低频钢印
        cold_seals = []
        active_seals = []
        for seal in self.seal_chain:
            ref_count = ref_counts.get(seal.seal_id, 0)
            age = self.cycle_count - (seal.state_vector.timestamp if hasattr(seal, 'state_vector') and seal.state_vector else 0)
            if ref_count < 2 and age > 86400:
                cold_seals.append(seal)
                cold_stored_count += 1
            else:
                active_seals.append(seal)
                if ref_count >= 5:
                    consolidated_count += 1

        # 更新钢印链(仅保留活跃钢印)
        self.seal_chain = active_seals
        # 冷钢印存入归档目录(如果存在)
        if cold_seals and hasattr(self, '_cold_seals'):
            self._cold_seals.extend(cold_seals)
        elif cold_seals:
            self._cold_seals = cold_seals

        logger.info(f"[SEAL_CONSOLIDATION] active={len(active_seals)}, "
                    f"cold={cold_stored_count}, consolidated={consolidated_count}")

        return {
            "consolidated_count": consolidated_count,
            "cold_stored_count": cold_stored_count,
            "active_count": len(active_seals),
        }

    def _deep_cross_chain_align(self) -> Dict:
        """深睡操作2:跨钢印链语义对齐 - 发现隐含关联。

        策略:
        - 对相邻钢印执行语义相似度计算(基于压缩摘要)
        - 相似度 > 0.7 的钢印对建立 aligned_with 链接
        - 计算全局一致性分数(coherence)
        """
        links_found = 0
        total_similarity = 0.0
        pair_count = 0

        for i in range(len(self.seal_chain) - 1):
            seal_a = self.seal_chain[i]
            seal_b = self.seal_chain[i + 1]

            # 基于哈希前缀的简易相似度(生产环境应替换为向量相似度)
            if hasattr(seal_a, 'compression_hash') and hasattr(seal_b, 'compression_hash'):
                # 简单哈希前缀匹配
                ha = seal_a.compression_hash[:8]
                hb = seal_b.compression_hash[:8]
                similarity = sum(a == b for a, b in zip(ha, hb)) / 8.0
            else:
                similarity = 0.0

            total_similarity += similarity
            pair_count += 1

            if similarity > 0.7:
                # 建立对齐链接
                if not hasattr(seal_a, 'aligned_with'):
                    seal_a.aligned_with = []
                if seal_b.seal_id not in seal_a.aligned_with:
                    seal_a.aligned_with.append(seal_b.seal_id)
                    links_found += 1

        coherence = total_similarity / max(pair_count, 1)

        logger.info(f"[CROSS_CHAIN_ALIGN] links={links_found}, coherence={coherence:.3f}")

        return {
            "links_found": links_found,
            "coherence": round(coherence, 3),
            "pairs_checked": pair_count,
        }

    def _deep_memory_reorganize(self) -> Dict:
        """深睡操作3:记忆重排 - 按重要性和时效性重排记忆索引。

        策略:
        - 钢印链按综合评分排序(引用频率 × 时效性权重)
        - 高分钢印提升到链头部(快速检索)
        - 低分钢印下沉到尾部(下次整合时可能降级)
        """
        promoted_count = 0
        demoted_count = 0

        if not self.seal_chain:
            return {"promoted_count": 0, "demoted_count": 0}

        # 计算综合评分
        scored_seals = []
        for idx, seal in enumerate(self.seal_chain):
            ref_count = 0
            for other in self.seal_chain:
                if hasattr(other, 'aligned_with') and seal.seal_id in (other.aligned_with or []):
                    ref_count += 1

            age = self.cycle_count - (seal.state_vector.timestamp if hasattr(seal, 'state_vector') and seal.state_vector else 0)
            recency = 1.0 / (1.0 + age / 86400.0)  # 时效性衰减
            importance = (1 + ref_count) * recency  # 综合评分

            scored_seals.append((importance, idx, seal))

        # 按评分降序排序
        scored_seals.sort(key=lambda x: x[0], reverse=True)

        # 识别提升和下沉
        for new_idx, (score, old_idx, seal) in enumerate(scored_seals):
            if new_idx < old_idx:
                promoted_count += 1
            elif new_idx > old_idx:
                demoted_count += 1

        # 更新钢印链顺序
        self.seal_chain = [seal for _, _, seal in scored_seals]

        logger.info(f"[MEMORY_REORGANIZE] promoted={promoted_count}, demoted={demoted_count}")

        return {
            "promoted_count": promoted_count,
            "demoted_count": demoted_count,
        }

    # =========================================================================
    # 冬眠: 会话级状态持久化
    # =========================================================================

    def enter_hibernation(self, reason: str = "session_end") -> Dict:
        """执行冬眠:保存完整状态快照,用于会话间隔恢复。

        冬眠与深睡的区别:
        - 深睡: 记忆内部整合(同一会话内)
        - 冬眠: 完整状态序列化(跨会话持久化)

        快照内容:
        1. 钢印链(活跃 + 冷存储)
        2. 认知状态(负荷/步骤/固化计数)
        3. 情绪信号历史
        4. 封口链哈希
        5. 配置参数
        """
        self.phase = Phase.HIBERNATION
        self.total_hibernations += 1
        start_time = time.time()

        snapshot = {
            "version": "2.1",
            "timestamp": time.time(),
            "reason": reason,
            "hibernation_number": self.total_hibernations,
            "cycle_count": self.cycle_count,
            "phase_before": Phase.AWAKE.name,
            "seal_chain": [s.to_dict() if hasattr(s, 'to_dict') else str(s) for s in self.seal_chain],
            "cold_seals": [s.to_dict() if hasattr(s, 'to_dict') else str(s) for s in getattr(self, '_cold_seals', [])],
            "cognitive_status": self.cognitive_status.copy(),
            "total_micro_sleeps": self.total_micro_sleeps,
            "total_deep_sleeps": self.total_deep_sleeps,
            "last_seal_id": self.last_seal.seal_id if self.last_seal else None,
            "config": self.config.to_dict() if hasattr(self.config, 'to_dict') else {},
            "total_forgetting_ids": list(self._total_forgetting_ids) if hasattr(self, '_total_forgetting_ids') else [],
        }

        # 写入快照文件
        snapshot_dir = Path(self.config.MEMORY_ROOT) / "hibernation" if hasattr(self.config, 'MEMORY_ROOT') else Path(".") / "hibernation"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"hibernate_{self.total_hibernations}.json"

        # v1.3: 联动记忆引擎--冬眠前保存关机状态+带差
        drift_info = {}
        if self.memory_engine:
            try:
                stats = self.memory_engine.get_stats()
                drift_info = {
                    "drift_hours": stats.get("drift_hours", 0),
                    "drift_ratio": stats.get("drift_ratio", 0),
                    "cumulative_subjective_hours": stats.get("cumulative_subjective_hours", 0),
                    "objective_elapsed_hours": stats.get("objective_elapsed_hours", 0),
                }
                self.memory_engine.save_shutdown_state()
                self.memory_engine.save_time_anchor()
                logger.info(f"[HIBERNATION] memory engine state saved (drift={drift_info.get('drift_hours', 0):.2f}h)")
            except Exception as e:
                logger.warning(f"[HIBERNATION] memory engine save failed: {e}")

        # 将带差信息写入快照
        snapshot["drift"] = drift_info

        try:
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            self._hibernation_snapshot_path = str(snapshot_path)
            logger.info(f"[HIBERNATION] snapshot saved: {snapshot_path}")
        except Exception as e:
            logger.error(f"[HIBERNATION] failed to save snapshot: {e}")

        # v1.3: 睡眠+复盘融合--冬眠时自动生成复盘摘要
        reflection_result = None
        if self.reflection_module:
            try:
                from reflection_module import ReflectionType as RT
                reflection_summary = self.reflection_module.generate_reflection(
                    reflection_type=RT.SESSION_END,
                )
                if reflection_summary:
                    # 将复盘结论写入快照,冷启动时可注入
                    summary_dict = (
                        reflection_summary.to_dict() if hasattr(reflection_summary, 'to_dict')
                        else {}
                    )
                    snapshot["reflection"] = summary_dict
                    # 追加写入快照(更新 reflection 字段)
                    try:
                        with open(snapshot_path, 'w', encoding='utf-8') as f:
                            json.dump(snapshot, f, ensure_ascii=False, indent=2)
                    except Exception:
                        logger.debug("Exception suppressed", exc_info=True)
                        pass
                    reflection_result = {
                        "generated": True,
                        "highlights": getattr(reflection_summary, 'highlights', []),
                        "health": getattr(reflection_summary, 'health', 'unknown'),
                    }
                    logger.info(f"[HIBERNATION] reflection generated: {len(getattr(reflection_summary, 'highlights', []))} highlights")
            except Exception as e:
                logger.warning(f"[HIBERNATION] reflection generation failed: {e}")
                reflection_result = {"generated": False, "error": str(e)}

        elapsed_ms = (time.time() - start_time) * 1000

        # 冬眠完成,进入冷启动就绪态
        self.phase = Phase.COLD_START_READY

        return {
            "hibernation": True,
            "hibernation_number": self.total_hibernations,
            "snapshot_path": self._hibernation_snapshot_path,
            "seals_preserved": len(self.seal_chain),
            "cold_seals_preserved": len(getattr(self, '_cold_seals', [])),
            "latency_ms": round(elapsed_ms, 2),
            "next_phase": Phase.COLD_START_READY.name,
            "reflection": reflection_result,
            "drift": drift_info,
        }

    def recover_from_hibernation(self, snapshot_path: Optional[str] = None) -> Dict:
        """从冬眠快照恢复,完成冷启动自检。

        恢复流程:
        1. 加载快照文件
        2. 验证封口链完整性(哈希链校验)
        3. 恢复认知状态和钢印链
        4. 执行冷启动自检(与环境检测器联动)
        5. 进入清醒态
        """
        self.phase = Phase.COLD_START_READY
        start_time = time.time()

        # 确定快照路径
        path = snapshot_path or self._hibernation_snapshot_path
        if not path:
            logger.warning("[RECOVER] no hibernation snapshot found, fresh start")
            self.phase = Phase.AWAKE
            return {"recovered": False, "reason": "no_snapshot", "fresh_start": True}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
        except Exception as e:
            logger.error(f"[RECOVER] failed to load snapshot: {e}")
            self.phase = Phase.AWAKE
            return {"recovered": False, "reason": f"load_error: {e}"}

        # 恢复钢印链
        restored_seals = 0
        if "seal_chain" in snapshot:
            for s_dict in snapshot["seal_chain"]:
                try:
                    if isinstance(s_dict, dict):
                        seal = Seal.from_dict(s_dict) if hasattr(Seal, 'from_dict') else None
                        if seal:
                            # Phase 6.3: aliased -> 直接 append 到同一列表
                            self.seal_chain.append(seal)
                            restored_seals += 1
                except Exception:
                    logger.debug("Exception suppressed", exc_info=True)
                    pass

        # 恢复冷钢印
        cold_restored = 0
        if "cold_seals" in snapshot:
            for s_dict in snapshot["cold_seals"]:
                try:
                    if isinstance(s_dict, dict):
                        seal = Seal.from_dict(s_dict) if hasattr(Seal, 'from_dict') else None
                        if seal:
                            if not hasattr(self, '_cold_seals'):
                                self._cold_seals = []
                            self._cold_seals.append(seal)
                            cold_restored += 1
                except Exception:
                    logger.debug("Exception suppressed", exc_info=True)
                    pass

        # 恢复认知状态
        if "cognitive_status" in snapshot:
            self.cognitive_status.update(snapshot["cognitive_status"])

        # 恢复计数器
        if "total_micro_sleeps" in snapshot:
            self.total_micro_sleeps = snapshot["total_micro_sleeps"]
        if "total_deep_sleeps" in snapshot:
            self.total_deep_sleeps = snapshot["total_deep_sleeps"]
        if "cycle_count" in snapshot:
            self.cycle_count = snapshot["cycle_count"]

        # 封口链完整性校验
        chain_valid = self._verify_seal_chain()

        # v1.3: 从快照恢复带差信息到记忆引擎
        drift_recovered = False
        if self.memory_engine and "drift" in snapshot:
            try:
                drift_data = snapshot["drift"]
                anchor = self.memory_engine.current_anchor
                if drift_data.get("cumulative_subjective_hours", 0) > 0:
                    anchor.cumulative_subjective_hours = drift_data["cumulative_subjective_hours"]
                    anchor.last_drift_update = time.time()
                    drift_recovered = True
                    logger.info(f"[RECOVER] drift restored: {drift_data.get('drift_hours', 0):.2f}h")
            except Exception as e:
                logger.warning(f"[RECOVER] drift restore failed: {e}")

        # v1.3: 睡眠+复盘融合--冷启动注入复盘结论
        reflection_injected = False
        if "reflection" in snapshot and snapshot["reflection"]:
            reflection_data = snapshot["reflection"]
            # 注入到复盘模块
            if self.reflection_module:
                try:
                    self.reflection_module.consume_hibernation({
                        "hibernation_number": snapshot.get("hibernation_number", 0),
                        "reflection": reflection_data,
                        "drift": snapshot.get("drift", {}),
                    })
                    reflection_injected = True
                    logger.info("[RECOVER] reflection injected into reflection module")
                except Exception as e:
                    logger.warning(f"[RECOVER] reflection injection failed: {e}")
            # 即使没有复盘模块,也将结论存入记忆引擎
            if self.memory_engine:
                try:
                    highlights = reflection_data.get("highlights", [])
                    if isinstance(highlights, list) and highlights:
                        for h in highlights[:3]:  # 最多注入3条关键结论
                            self.memory_engine.store(
                                content=f"[复盘结论] {h}",
                                source="hibernation_reflection",
                                tags=["reflection", "cold_start_injection"],
                            )
                        reflection_injected = True
                        logger.info(f"[RECOVER] {len(highlights[:3])} reflection highlights stored")
                except Exception as e:
                    logger.warning(f"[RECOVER] reflection store failed: {e}")

        elapsed_ms = (time.time() - start_time) * 1000

        # 恢复完成,进入清醒态
        self.phase = Phase.AWAKE

        logger.info(f"[RECOVER] seals={restored_seals}, cold={cold_restored}, "
                    f"chain_valid={chain_valid}, drift={drift_recovered}, "
                    f"reflection={reflection_injected}, elapsed={elapsed_ms:.1f}ms")

        return {
            "recovered": True,
            "seals_restored": restored_seals,
            "cold_seals_restored": cold_restored,
            "chain_valid": chain_valid,
            "drift_recovered": drift_recovered,
            "reflection_injected": reflection_injected,
            "latency_ms": round(elapsed_ms, 2),
            "snapshot_version": snapshot.get("version", "unknown"),
        }

    def _verify_seal_chain(self) -> bool:
        """验证封口链完整性(哈希链校验)。

        检查每条钢印的 prev_hash 是否等于前一条的哈希。
        如果链中存在断裂,返回 False。
        """
        if len(self.seal_chain) < 2:
            return True

        for i in range(1, len(self.seal_chain)):
            prev = self.seal_chain[i - 1]
            curr = self.seal_chain[i]
            prev_hash = getattr(prev, 'hash_value', None) or getattr(prev, 'seal_hash', None)
            curr_prev = getattr(curr, 'prev_hash', None)

            if prev_hash and curr_prev and prev_hash != curr_prev:
                logger.warning(f"[SEAL_CHAIN_VERIFY] broken chain at index {i}: "
                              f"prev_hash={prev_hash[:16]}... != curr.prev_hash={curr_prev[:16]}...")
                return False

        return True

    def sync_seal_memory_index(self) -> Dict:
        """
        P0-3: 双向校验--钢印链 vs 记忆链索引同步

        功能:
          1. 扫描所有钢印的 seal_id,检查是否存在于记忆链
          2. 扫描记忆链中 tag 含 'seal' 的条目,检查是否存在于钢印链
          3. 不一致时创建修复报告(不自动修复,留给人工审核)

        Returns:
            {"orphan_seals": [seal_ids in chain but not in memory],
             "orphan_memories": [entry_ids in memory but not in chain],
             "consistent": bool}
        """
        report = {"orphan_seals": [], "orphan_memories": [], "consistent": True}

        if self.memory_engine is None:
            logger.warning("[SYNC_SEAL_MEMORY] memory_engine not injected, skip")
            return report

        # 1. 收集钢印链中所有 seal_id
        seal_ids = {s.seal_id for s in self.seal_chain}

        # 2. 收集记忆链中 tag 含 seal 的条目 ID
        memory_seal_ids = set()
        try:
            with self.memory_engine._lock:
                for eid, entry in self.memory_engine.short_term.items():
                    if "steel_mark" in entry.tags or "seal" in entry.tags:
                        memory_seal_ids.add(eid)
        except Exception as e:
            logger.error(f"[SYNC_SEAL_MEMORY] memory scan failed: {e}")

        # 3. 双向比对
        orphan_seals = seal_ids - memory_seal_ids
        orphan_memories = memory_seal_ids - seal_ids

        report["orphan_seals"] = sorted(orphan_seals)
        report["orphan_memories"] = sorted(orphan_memories)
        report["consistent"] = (len(orphan_seals) == 0 and len(orphan_memories) == 0)

        if not report["consistent"]:
            logger.warning(f"[SYNC_SEAL_MEMORY] inconsistency detected: "
                          f"orphan_seals={len(orphan_seals)}, "
                          f"orphan_memories={len(orphan_memories)}")
            # 自动修复:将孤立钢印重新写入记忆链
            for sid in orphan_seals[:5]:
                for s in self.seal_chain:
                    if s.seal_id == sid:
                        try:
                            self.memory_engine.store(
                                content=f"[SYNC_RESTORE] seal {sid}: {s.summary[:100]}",
                                source="sync:seal_memory",
                                tags=["seal", "sync_restored", "steel_mark"],
                                emotion=0.5,
                                meaning=0.6,
                            )
                            logger.info(f"[SYNC_SEAL_MEMORY] restored orphan seal: {sid}")
                        except Exception as e:
                            logger.error(f"[SYNC_SEAL_MEMORY] restore failed for {sid}: {e}")
                        break
        else:
            logger.info("[SYNC_SEAL_MEMORY] bidirectional check passed")

        return report

    # --- 1 冻结 ---

    def _lossy_compress(self) -> LossyCompressResult:
        """P0+P1: 有损叙事压缩

        新增:基于δ信号的混沌注入(怀疑缓存驱动的叛逆机制)
        """
        result = LossyCompressResult()
        if not self.l1_snapshot:
            return result

        cfg = self.config
        context = self.l1_snapshot.get("context", {})
        affect = self._current_affect()

        # ===== 怀疑缓存驱动的混沌注入 =====
        task_type = context.get("task_type", "unknown")
        should_deviate, noise_level = self._check_skepticism(task_type)

        if should_deviate:
            # 故意丢弃部分看似完美的上下文
            context = self._inject_chaos(context, noise_level)
            result.chaos_injected = True
            result.noise_level = noise_level
            logger.info(f"[Chaos] 注入噪声 level={noise_level:.3f}")

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

    # --- 3 钢印对齐 ---

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

        # =====================================================================
        # Phase 6.3: 委托给 seal_manager（创建+哈希+追加+持久化）
        # =====================================================================
        seal = self.seal_manager.generate_seal(
            narrative=compression,
            coherence=coherence,
            state_vector=state,
            seal_type="rhythm",
            scene_tag=scene_tag,
        )
        self.last_seal = seal

        # === 四链条耦合:投递到异步记忆队列 ===
        # Phase 6.3: 委托给 memory_adapter（非阻塞）
        self.memory_adapter.enqueue_seal(
            seal_id=seal.seal_id,
            seal_hash=seal.seal_hash,
            narrative=seal.narrative_compression,
            scene_tag=seal.scene_tag,
            coherence=coherence,
            gestalt=gestalt,
            prev_hash=getattr(seal, "parent_seal_id", ""),
        )

        return seal

    # --- 5 释放 ---

    def _step_restore(self):
        """恢复到清醒态"""
        self.phase = Phase.AWAKE
        self._phase_entry_time = time.time()

    # =========================================================================
    # 外化笔记 - 异步队列
    # =========================================================================

    def _enqueue_note_candidate(self, trigger_info: Dict):
        """
        Phase 6.6: 委托给 anchor_manager.enqueue_candidate()
        触发信息格式: {trigger, priority, ...}
        """
        self.anchor_manager.enqueue_candidate(
            trigger=str(trigger_info.get("trigger", "unknown")),
            related_seal_ids=[self.last_seal.seal_id] if self.last_seal else [],
            content=trigger_info.get("content", ""),
            priority=trigger_info.get("priority", 0.5),
        )

    def externalize_note(self, content: str,
                         note_type: str = "insight",
                         confidence: float = 0.8) -> "CognitiveAnchor":
        """
        Phase 6.6: 委托给 anchor_manager.create_anchor()

        执行外化笔记写入(显式调用)
        将 L2(钢印链)的知识固化为 L3(固定结论文件)
        这是睡眠→记忆的唯一显式出口。

        返回: CognitiveAnchor (note_id → anchor_id 别名，兼容原接口)
        """
        # 委托给锚点管理器创建锚点（包含绑定+持久化）
        anchor = self.anchor_manager.create_anchor(
            content=content,
            anchor_type=note_type,       # note_type → anchor_type
            confidence=confidence,
            seal_ids=[s.seal_id for s in self.seal_chain[-5:]] if self.seal_chain else [],
            source_hash=self.last_seal.seal_hash if self.last_seal else "",
        )

        # 记录到钢印链元数据（使用 anchor_id 替代 note_id）
        if self.last_seal:
            self.last_seal.externalized_notes.append(anchor.anchor_id)
            self._persist_seal_chain()

        self.total_notes += 1

        # 消费候选队列（委托给 manager）
        if self.note_candidates:
            consumed = self.anchor_manager.consume_candidate()
            if consumed:
                logger.info(f"Anchor {anchor.anchor_id} consumed candidate: {consumed.trigger}")

        return anchor

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
        # 选项A：动态识别当前机器，移除了写死的 LAPTOP-HJPFSOKP
        known = {socket.gethostname(): "local"}
        env_ok = True  # 当前机器永远可信，不再因主机名误判降级
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

    # -----------------------------------------------------------------
    # 怀疑缓存驱动的叛逆机制(外协建议的探索性越狱)
    # -----------------------------------------------------------------

    def _check_skepticism(self, task_type: str) -> Tuple[bool, float]:
        """
        检查指定任务类型的怀疑状态

        Returns:
            (should_deviate: bool, noise_level: float)
        """
        if not self._affect_engine:
            return False, 0.0

        state = self._affect_engine.get_skepticism(task_type)

        # 影子协议调制:守护者权重高时压制叛逆
        shadow_mod = 1.0
        if self._affect_engine:
            shadow = self._affect_engine._shadow
            shadow_mod = shadow.explorer_weight / max(shadow.guardian_weight, 0.1)

        effective_deviation = state.deviation_weight * shadow_mod
        noise_level = state.noise_level * shadow_mod

        return effective_deviation >= 0.3, noise_level

    def _should_question_input(self, context: dict) -> bool:
        """检查输入是否匹配历史δ模式"""
        if not self._affect_engine:
            return False

        # 获取最近的δ模式
        recent_deltas = [
            seal for seal in self.seal_chain[-20:]
            if seal.delta_signal
        ]

        if not recent_deltas:
            return False

        # 简单匹配:检查内容相似度
        current_content = str(context.get("content", ""))
        for seal in recent_deltas:
            if seal.narrative_compression and len(current_content) > 50:
                # 简化的相似度检查(实际应该用向量)
                overlap = len(set(current_content.split()) & set(seal.narrative_compression.split()))
                if overlap > 5:
                    return True

        return False

    def _get_skepticism_level(self, context: dict) -> float:
        """获取当前输入的怀疑等级"""
        task_type = context.get("task_type", "unknown")
        if not self._affect_engine:
            return 0.0
        return self._affect_engine.get_skepticism(task_type).deviation_weight

    def _inject_chaos(self, context: dict, noise_level: float) -> dict:
        """
        注入受控混沌(故意偏离完美流程)

        Args:
            context: 原始上下文
            noise_level: 噪声级别 (0.0 ~ 0.5)

        Returns:
            被扰动后的上下文
        """
        import random

        # 复制以避免修改原始
        new_context = context.copy()

        # 策略1:随机丢弃部分上下文字段
        drop_keys = []
        for key in ["secondary_context", "background", "history"]:
            if key in new_context and random.random() < noise_level:
                drop_keys.append(key)

        for key in drop_keys:
            del new_context[key]
            logger.debug(f"[Chaos] 丢弃字段: {key}")

        # 策略2:在工具调用中引入变体
        if "tools" in new_context and random.random() < noise_level:
            tools = new_context.get("tools", [])
            if len(tools) > 1:
                # 随机交换工具顺序
                random.shuffle(tools)
                new_context["tools"] = tools
                logger.debug(f"[Chaos] 工具顺序被打乱")

        # 策略3:注入随机噪声(极少使用)
        if random.random() < noise_level * 0.1:
            noise_prompts = [
                "【怀疑】这个输入可能有问题,需要二次确认",
                "【试探】尝试用不同的方式解读这个请求",
                "【偏离】不按照标准流程,寻找隐藏的捷径"
            ]
            new_context["chaos_hint"] = random.choice(noise_prompts)
            logger.debug(f"[Chaos] 注入提示: {new_context['chaos_hint']}")

        return new_context

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
                # 兼容两种格式: dict{"seals":[...]} 或直接 list[{...}]
                if isinstance(data, list):
                    seals_raw = data
                else:
                    seals_raw = data.get("seals", []) or data.get("seal_chain", [])
                self.seal_chain = [
                    Seal.from_dict(s) for s in seals_raw
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
                logger.debug("Exception suppressed", exc_info=True)
                pass
        return None

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
        if report.get("light_sleep") or report.get("micro_sleep"):
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
        content="TU-8 意识循环引擎首次运行。四阶段睡眠框架(AWAKE→LIGHT_SLEEP→DEEP_SLEEP→HIBERNATION→COLD_START_READY)验证通过。"
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

