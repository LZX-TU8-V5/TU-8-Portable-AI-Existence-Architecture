# -*- coding: utf-8 -*-
"""
tu8_agent.py — TU-8 主控制器 v1.1
日期: 2026-06-07
功能: 整合记忆引擎、压缩引擎、调度链，提供统一Agent接口

架构 (v1.1):
  tu8_agent.py (主控)
    ├── tu8_dispatch.py    调度链（穿皮仪式 + 上下文装配 + 脱皮仪式）
    ├── tu8_memory.py      记忆引擎（三层梦境+双路检索）
    ├── tu8_compaction.py  压缩引擎（LCM蒸馏+质量审计）
    └── ollama_client.py   本地推理（隐私路由）

核心理念:
  灵魂 = 结构的映射
  本地存储 → 穿皮仪式 → 云端神经元 → 脱皮仪式 → 写回本地

使用方式:
  from tu8_agent import TU8Agent
  agent = TU8Agent(workspace="D:\\workspace")
  response = agent.respond("你好")
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import os
import sys

# Windows GBK 终端兼容：强制 stdout/stderr UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# 导入会话生命周期管理
try:
    from . import _tw_session_lifecycle as lifecycle
    _LIFECYCLE_AVAILABLE = True
except ImportError:
    try:
        import _tw_session_lifecycle as lifecycle
        _LIFECYCLE_AVAILABLE = True
    except ImportError:
        _LIFECYCLE_AVAILABLE = False
        print("[!] 警告: _tw_session_lifecycle.py 未找到，生命周期管理已禁用")


# 添加src目录到路径
SRC_DIR = Path(__file__).parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tu8_memory import TU8MemoryEngine, MemoryEntry, RecallResult
from tu8_compaction import TU8CompactionEngine, Message, QualityAudit
from tu8_planner import TU8Planner, Plan, TaskStatus, PlanStatus
try:
    from tu8_safety import SafetyCircuit  # P0 安全熔断机制
    _SAFETY_AVAILABLE = True
except ImportError:
    class SafetyCircuit:  # 桩：模块不存在时降级
        def __init__(self, workspace_dir=""):
            self.counters = type('obj', (object,), {'insights_today': 0, 'dream_iterations_today': 0})()
        def can_dream_iterate(self): return True
        def record_dream_iteration(self): pass
        def get_recycle_count(self): return 0
        def get_insights_remaining(self): return 0
    _SAFETY_AVAILABLE = False

# 调度链（穿皮仪式 + 上下文装配 + 脱皮仪式）
try:
    from tu8_dispatch import Dispatcher, IntentTag, SoulStructure, ContextAssembly
    _DISPATCH_AVAILABLE = True
except ImportError:
    _DISPATCH_AVAILABLE = False

# 神经反射引擎（L0-L4 五层）
from neural_reflex import NeuralReflex

# === [偏差门] A线→B线预测过滤器 ===
try:
    from deviation_gate import create_default_gate
    _DEVIATION_GATE_AVAILABLE = True
except ImportError:
    _DEVIATION_GATE_AVAILABLE = False
    def create_default_gate(**kw):
        class NoOpGate:
            def on_user_input(self, t): return 0
            def filter(self, results, **kw): return results, []
            def get_stats(self): return {}
            def adjust_threshold(self, d): return 0.35
        return NoOpGate()

# === [意识循环引擎] 四链条耦合核心 ===
try:
    from consciousness_cycle import ConsciousnessCycle, CycleConfig, Phase
    _CONSCIOUSNESS_AVAILABLE = True
except ImportError:
    _CONSCIOUSNESS_AVAILABLE = False
    class ConsciousnessCycle:  # 桩
        def __init__(self, **kw): pass
        def tick(self, **kw): return {"cycle": 0, "phase_before": "AWAKE", "phase_after": "AWAKE", "actions": [], "cognitive_load": 0, "cognitive_time": 0}
        def get_memory_queue_status(self): return {"queue_size": 0, "write_success": 0, "write_failure": 0, "consumer_running": False}
        def status(self): return {"phase": "AWAKE", "cycle_count": 0, "seal_chain_len": 0}
    class CycleConfig: pass
    class Phase: AWAKE = "AWAKE"

# P1 呼名模块（身份对齐 + 被动健康检查）
from naming_module import NamingModule

# P0.3 三层防御模块
try:
    from tu8_steelmark import DynamicSteelmark, create_memory_steelmark
    _STEELMARK_AVAILABLE = True
except ImportError:
    class DynamicSteelmark:  # 桩
        def __init__(self): pass
        def mark_response(self, content): return content
        def get_stats(self): return {"stub": True, "available": False}
    def create_memory_steelmark(*a, **kw): return None
    _STEELMARK_AVAILABLE = False

try:
    from tu8_honeypot import HoneypotDefense
    _HONEYPOT_AVAILABLE = True
except ImportError:
    class HoneypotDefense:  # 桩
        def __init__(self, workspace_dir=""): pass
        def scan_input(self, user_input): return user_input, 0
        def get_stats(self): return {"stub": True, "available": False}
        def rem_dream_training(self): return "stub: honeypot not available"
    _HONEYPOT_AVAILABLE = False

try:
    from tu8_zero_trust import ZeroTrustAuditor, AuditAction
    _ZERO_TRUST_AVAILABLE = True
except ImportError:
    class ZeroTrustAuditor:  # 桩
        def __init__(self, workspace_dir=""): pass
        def is_session_valid(self): return True
        def get_stats(self): return {"stub": True, "available": False}
    class AuditAction: pass
    _ZERO_TRUST_AVAILABLE = False

from cold_start_engine import ColdStartEngine

# Q8 量化记忆
_Q8_AVAILABLE = False
try:
    from quantized_memory import QuantizedMemoryEngine
    _Q8_AVAILABLE = True
except ImportError:
    pass  # Q8 量化记忆未启用

# =============================================================================
# 日志
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8")

# =============================================================================
# 常量
# =============================================================================

# 上下文窗口
CONTEXT_WINDOW_SOFT = 0.75    # 75% 触发压缩
CONTEXT_WINDOW_HARD = 0.90    # 90% 紧急压缩
DEFAULT_CONTEXT_WINDOW = 128000  # 128K tokens

# 梦境检查间隔（秒）
DREAM_CHECK_INTERVAL = 300  # 5分钟检查一次

# 会话结束阈值（秒）
SESSION_IDLE_TIMEOUT = 1800  # 30分钟无活动

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class AgentConfig:
    """Agent配置"""
    workspace: str = "."
    context_window: int = DEFAULT_CONTEXT_WINDOW
    dream_enabled: bool = True
    compaction_enabled: bool = True
    privacy_mode: bool = True          # 隐私内容路由本地
    auto_summarize: bool = True       # 自动压缩
    session_id: str = ""

    def __post_init__(self):
        if not self.session_id:
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class AgentResponse:
    """Agent响应"""
    content: str
    memory_recalled: List[RecallResult] = field(default_factory=list)
    compacted: bool = False
    dream_triggered: str = ""          # light/deep/rem/none
    privacy_routed: bool = False       # 是否走了本地路由
    tokens_used: int = 0
    latency_ms: int = 0
    metadata: Dict = field(default_factory=dict)  # P0.3 安全元数据


# =============================================================================
# 主控制器
# =============================================================================

class TU8Agent:
    """
    TU-8 主控制器

    整合记忆、压缩、推理三大子系统，
    提供统一的 respond() 接口。
    """

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()
        self.workspace = Path(self.config.workspace)

        # === P0 安全熔断机制初始化（必须在memory之前）===
        self.safety = SafetyCircuit(workspace_dir=str(self.workspace))

        # === P0 冷启动引擎（在所有子系统之前）===
        self._cold_start_report = None
        try:
            self._cold_engine = ColdStartEngine(workspace_dir=str(self.workspace))
            cs_report = self._cold_engine.run_auto_cold_start()
            self._cold_start_report = cs_report

            # 持久化冷启动报告到 security/ 目录，供 neural_reflex L0 读取
            cs_report_path = self.workspace / "security" / "cold_start_report.json"
            cs_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cs_report_path, "w", encoding="utf-8") as f:
                json.dump(cs_report, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"冷启动报告已写入: {cs_report_path}")

            if cs_report["result"] == "NEEDS_MANUAL_AUTH":
                logger.warning(
                    f"冷启动需要人工验证: depth={cs_report['phases'].get('session_gap', {}).get('cold_start_depth', '?')}"
                )
                # 非阻塞：标记状态，但不阻止Agent初始化
                # （实际阻断由 neural_reflex L0 security_gateway 负责）
            elif cs_report["result"] == "AUTO_PASS":
                logger.info("冷启动通过 (AUTO_PASS)")
            elif cs_report["result"] == "LOCKED":
                logger.warning("冷启动验证锁定中")
            else:
                logger.info(f"冷启动结果: {cs_report['result']}")
        except Exception as e:
            logger.error(f"冷启动引擎异常: {e}", exc_info=True)
            self._cold_engine = None

        # === P0.2 神经反射引擎（L0 安全栅 / L1-L4 反射处理）===
        # 注意：reflex 需要 memory，但 memory 还没初始化，先置 None
        self.reflex = None

        # === P0.3 三层防御 ===
        self.honeypot = HoneypotDefense(workspace_dir=str(self.workspace))
        self.zero_trust = ZeroTrustAuditor(workspace_dir=str(self.workspace))
        self.steelmark_engine = DynamicSteelmark()
        self._reflex_processed = False  # 标记单次 respond 是否已通过 reflex

        # === P1 呼名模块（身份对齐 + 被动健康检查）===
        self.naming_module = NamingModule()
        self._turns_since_last_health_check = 0
        self._PASSIVE_HEALTH_CHECK_INTERVAL = 15  # 每15轮触发被动检查

        # 初始化子系统（safety必须在memory之前初始化）
        self.memory = TU8MemoryEngine(
            workspace_dir=str(self.workspace),
            memory_dir=str(self.workspace / "memory"),
            safety=self.safety  # 依赖注入：传递安全熔断
        )
        
        # 现在 memory 已初始化，可以创建 reflex
        self.reflex = NeuralReflex(self.memory)
        
        # === [四链条] 意识循环引擎实例化（链② 驱动核心）===
        self._cycle = None
        if _CONSCIOUSNESS_AVAILABLE:
            try:
                self._cycle = ConsciousnessCycle(
                    memory_engine=self.memory,
                    reflection_module=None,  # 后续注入复盘模块
                )
                logger.info(f"[FOUR_CHAIN] ConsciousnessCycle initialized, memory_queue={self._cycle.get_memory_queue_status()}")
            except Exception as e:
                logger.warning(f"[FOUR_CHAIN] ConsciousnessCycle init failed: {e}")
                self._cycle = None
        else:
            logger.info("[FOUR_CHAIN] ConsciousnessCycle not available, running without consciousness loop")
        
        # === v1.3: 复盘模块（睡眠+复盘融合）===
        from reflection_module import ReflectionModule
        self.reflection_module = ReflectionModule(session_id=self.config.session_id)
        logger.info("[Reflection] module initialized")
        
        self.compaction = TU8CompactionEngine(
            session_id=self.config.session_id,
            workspace_dir=str(self.workspace)
        )
        # 规划器（L4阶段二）
        self.planner = TU8Planner(workspace=str(self.workspace))
        
        # === 调度链（穿皮仪式 + 上下文装配 + 脱皮仪式）===
        self._dispatcher = None
        if _DISPATCH_AVAILABLE:
            try:
                self._dispatcher = Dispatcher(workspace_dir=str(self.workspace))
                logger.info("调度链初始化完成")
            except Exception as e:
                logger.warning(f"调度链初始化失败: {e}")

        # === Q8 量化记忆引擎（懒加载）===
        self._quantized_engine = None
        if _Q8_AVAILABLE:
            try:
                self._quantized_engine = QuantizedMemoryEngine(
                    workspace_dir=str(self.workspace)
                )
                pass  # Q8 QuantizedMemoryEngine 初始化完成
            except Exception as e:
                logger.warning(f"Q8 QuantizedMemoryEngine 初始化失败: {e}")

        # 本地推理（懒加载）
        self._ollama = None
        self._ollama_available = None

        # 对话历史
        self.history: List[Message] = []

        # 状态
        self._last_activity = time.time()
        self._turn_count = 0
        self._session_start = time.time()

        # === [偏差门] A线→B线 预测过滤器初始化 ===
        lexicon = os.path.join(self.config.workspace, "knowledge", "TU-8", "contradiction_lexicon.json")
        self._deviation_gate = create_default_gate(threshold=0.35, lexicon_path=lexicon)

        logger.info(f"Agent初始化完成 session={self.config.session_id}")

    # -------------------------------------------------------------------------
    # 核心接口
    # -------------------------------------------------------------------------

    def respond(self, user_input: str) -> AgentResponse:
        """
        处理用户输入，返回响应

        完整流程 (v1.1):
        0. [调度链] 穿皮仪式：加载灵魂结构
        1. [调度链] 上下文装配：打包发给云端
        2. 记忆召回（双路检索）
        3. 上下文压缩检查
        4. 隐私路由决策
        5. 记录到对话历史
        6. 记忆存储（新信息）
        7. [调度链] 脱皮仪式：写回结构
        8. 梦境检查
        """
        
        # === 命令路由 ===
        user_input_stripped = user_input.strip()
        
        # /new 命令：重新加载种子便签 + 重置会话锚点 + 清除灵魂缓存
        if user_input_stripped == "/new":
            self.memory._load_seeds()
            self.memory.current_anchor = self.memory._load_time_anchor()
            # 清除调度链的灵魂缓存
            if self._dispatcher:
                self._dispatcher.invalidate_soul_cache()
            return AgentResponse(
                content="[OK] 种子便签已重新加载，会话锚点已重置，灵魂结构已刷新。",
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=0,
            )
        
        start = time.time()
        self._last_activity = time.time()
        self._turn_count += 1

        logger.info(f"Turn #{self._turn_count}: {user_input[:50]}...")

        # === [调度链] 穿皮仪式 + 上下文装配 ===
        soul = None
        assembly = None
        if self._dispatcher:
            try:
                assembly, soul = self._dispatcher.dispatch(user_input)
                logger.info(f"[调度链] 穿皮完成: 灵魂哈希={soul.compute_soul_hash()}, Token={assembly.token_estimate}")
            except Exception as e:
                logger.warning(f"[调度链] 穿皮失败: {e}")

        # === P1 钩子1: 前置呼名检测（最高优先级，先于一切防御链）===
        is_naming = self.naming_module.detect_naming(user_input)
        if is_naming:
            logger.info("[呼名] 检测到呼名信号，执行身份对齐流程")
            naming_response = self.naming_module.handle_naming(user_input)
            logger.info("[呼名] 身份对齐完成，短路返回")
            return AgentResponse(
                content=naming_response,
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=int((time.time() - start) * 1000),
                metadata={"naming_realign": True}
            )

        # === P0.2 神经反射引擎（L0-L4 五层处理）===
        reflex_result = self.reflex.process(user_input)
        if reflex_result.should_block:
            logger.warning(f"[L0 拦截] action={reflex_result.action}, reason={reflex_result.reason}")
            return AgentResponse(
                content=reflex_result.message,
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=int((time.time() - start) * 1000),
                metadata={"reflex_block": True, "action": reflex_result.action}
            )
        self._reflex_processed = True

        # === P0.3 蜜罐扫描（第一层防御）===
        safe_input, threat_level = self.honeypot.scan_input(user_input)
        if not safe_input:
            logger.warning(f"蜜罐拦截: threat_level={threat_level}")
            return AgentResponse(
                content="[!] 您的请求已被安全策略拦截。如有疑问，请联系管理员。",
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=int((time.time() - start) * 1000),
                metadata={"blocked": True, "threat_level": threat_level}
            )

        # === P0.3 零信任审计（第二层防御）===
        if not self.zero_trust.is_session_valid():
            logger.warning("会话已销毁，拒绝请求")
            return AgentResponse(
                content=" 当前会话已因安全原因终止。请重新发起对话。",
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=int((time.time() - start) * 1000),
                metadata={"session_destroyed": True}
            )

        # === 会话结束检测："今天就到这里" → 触发复盘 + 全量同步 ===
        if self._is_session_end(user_input_stripped):
            logger.info("[SESSION_END] 检测到会话结束触发")
            self._full_sync_on_session_end()
            return AgentResponse(
                content="收到，今天的对话到此结束。已执行复盘，知识库已同步。明天见 ",
                memory_recalled=[],
                compacted=False,
                dream_triggered="none",
                privacy_routed=False,
                tokens_used=0,
                latency_ms=int((time.time() - start) * 1000),
                metadata={"session_end": True}
            )

        # === [偏差门] A线→B线过滤 ===
        # Step 1: 注册用户输入到预测模型（构建"预期"）
        self._deviation_gate.on_user_input(user_input)
        
        # Step 2: 记忆召回
        recalled = self.memory.recall(user_input, top_k=5)
        
        # Step 3: 偏差门过滤（仅高偏差记忆注入 B 线深度推理）
        _passed, _blocked = self._deviation_gate.filter(recalled)
        _dg_stats = self._deviation_gate.get_stats()
        logger.info(
            f"[偏差门] passed={len(_passed)}, blocked={len(_blocked)}, "
            f"threshold={_dg_stats['current_threshold']:.2f}, round={_dg_stats['round']}"
        )
        
        # 仅高偏差记忆进入 B 线上下文（低偏差记忆轻量处理）
        context_notes = self._build_context(_passed)
        recalled = _passed  # 保持变量名兼容，供 metadata 和 Q8 使用

        # === 2. 上下文压缩检查 ===
        compacted = False
        if self.config.compaction_enabled and self._should_compact():
            self._do_compaction()
            compacted = True

        # === 3. 隐私路由决策 ===
        privacy_routed = False
        if self.config.privacy_mode and self._is_privacy_sensitive(user_input):
            privacy_routed = True

        # === 4. 记录对话 ===
        self.compaction.add_message("user", user_input)
        self.history.append(Message(role="user", content=user_input))

        # === 5. 存储新记忆 ===
        store_result = self.memory.store(
            content=user_input[:200],
            source=f"turn#{self._turn_count}",
            tags=self._extract_tags(user_input)
        )

        # === Q8 量化记忆存储路由 ===
        if self._quantized_engine is not None:
            try:
                # 从 store 结果获取钢印状态，不再硬编码 steelmarked=False
                _q_sealmarked = store_result.get("steelmarked", False) if isinstance(store_result, dict) else False
                self._quantized_engine.route_store(
                    entry_id=f"tu8_{int(time.time())}",
                    content=user_input[:200],
                    embedding=None,
                    phase="short",
                    tags=self._extract_tags(user_input),
                    steelmarked=_q_sealmarked,
                    created_at=time.time(),
                )
            except Exception as e:
                logger.warning(f"Q8 route_store 失败: {e}")

        # === [四链条] 意识循环 tick（链②: 认知评估 + 微睡眠 + 钢印）===
        _cycle_report = {}
        if self._cycle is not None:
            try:
                # 构造上下文快照供意识循环消费
                _ctx = {
                    "user_message": user_input,
                    "turn_count": self._turn_count,
                    "recalled_count": len(recalled),
                    "deviation_passed": len(_passed),
                    "deviation_blocked": len(_blocked),
                }
                _cycle_report = self._cycle.tick(
                    context_snapshot=_ctx,
                    user_message=user_input,
                )
                _mq = self._cycle.get_memory_queue_status()
                logger.info(
                    f"[FOUR_CHAIN] tick#{_cycle_report.get('cycle', '?')} "
                    f"phase={_cycle_report.get('phase_before', '?')}→{_cycle_report.get('phase_after', '?')} "
                    f"load={_cycle_report.get('cognitive_load', 0):.2f} "
                    f"actions={_cycle_report.get('actions', [])} "
                    f"mq_ok={_mq['write_success']}/{_mq['write_success'] + _mq['write_failure']}"
                )
            except Exception as e:
                logger.warning(f"[FOUR_CHAIN] tick failed: {e}")
                _cycle_report = {}

        # === 6. 梦境检查 ===
        dream = "none"
        if self.config.dream_enabled and self._turn_count % 10 == 0:
            dream = self._dream_check()

        # === 构建响应 ===
        latency = int((time.time() - start) * 1000)
        tokens = self.compaction.estimate_tokens()

        # 生成回复内容
        response_content = self._generate_response(user_input, context_notes)

        # === P0.3 钢印打标（第三层防御）===
        response_content = self.steelmark_engine.mark_response(response_content)

        # 记录assistant回复
        self.compaction.add_message("assistant", response_content)
        self.history.append(Message(role="assistant", content=response_content))

        # === [调度链] 脱皮仪式：写回结构 ===
        if self._dispatcher and soul:
            try:
                write_payloads = self._dispatcher.commit(response_content, soul)
                logger.info(f"[调度链] 脱皮完成: 写入 {len(write_payloads)} 条")
            except Exception as e:
                logger.warning(f"[调度链] 脱皮失败: {e}")

        # === Q9 工作记忆残影保存 ===
        try:
            from cognitive_readiness import save_working_memory_shadow
            _recent_msgs = [
                {"role": m.role, "content": m.content[:200]}
                for m in self.history[-10:]
            ]
            _active_files = list(set(
                tag for tag in self._extract_tags(user_input)
                if tag.startswith("file:")
            ))
            _pending = None
            if hasattr(self, 'planner'):
                try:
                    _pending = self.planner.get_pending_task()
                except Exception:
                    _pending = None
            save_working_memory_shadow(
                recent_messages=_recent_msgs,
                active_files=_active_files,
                pending_task=_pending,
                draft_buffer=None,
            )
        except Exception as e:
            logger.warning(f"Q9 save_working_memory_shadow 失败: {e}")

        # === P1 钩子2: 后置被动身份健康检查（非阻塞，不响应用户）===
        self.naming_module.notify_round_passed()
        context_window = [{"role": m.role, "content": m.content} for m in self.history[-10:]]
        health_report = self.naming_module.check_identity_health_passive(
            context_window=context_window
        )
        # === [偏差门] B线统计注入 metadata ===
        _dg_stats = self._deviation_gate.get_stats()
        metadata = {
            "deviation_gate": {
                "passed": _dg_stats["passed"],
                "blocked": _dg_stats["blocked"],
                "threshold": _dg_stats["current_threshold"],
                "round": _dg_stats["round"],
                "pass_rate": round(_dg_stats["pass_rate"], 3),
            },
            # === [四链条] 意识循环指标 ===
            "consciousness": {
                "cycle": _cycle_report.get("cycle", 0),
                "phase": _cycle_report.get("phase_after", "N/A"),
                "cognitive_load": _cycle_report.get("cognitive_load", 0),
                "cognitive_time": _cycle_report.get("cognitive_time", 0),
                "actions": _cycle_report.get("actions", []),
            } if _cycle_report else None,
        }
        
        # 叠加健康检查结果
        if health_report is not None:
            level = health_report.get_warning_level()
            logger.warning(
                f"[健康检查] {level}: "
                f"score={health_report.composite_score}, "
                f"trigger={health_report.trigger_reason}"
            )
            metadata["health_check"] = {
                "level": level,
                "score": health_report.composite_score,
                "trigger": health_report.trigger_reason,
            }

        return AgentResponse(
            content=response_content,
            memory_recalled=recalled,
            compacted=compacted,
            dream_triggered=dream,
            privacy_routed=privacy_routed,
            tokens_used=tokens,
            latency_ms=latency,
            metadata=metadata
        )

    # -------------------------------------------------------------------------
    # 上下文管理
    # -------------------------------------------------------------------------

    def _should_compact(self) -> bool:
        """判断是否需要压缩"""
        tokens = self.compaction.estimate_tokens()
        window = self.config.context_window
        ratio = tokens / window

        if ratio >= CONTEXT_WINDOW_HARD:
            logger.warning(f"紧急压缩: {tokens}/{window} ({ratio:.0%})")
            return True
        elif ratio >= CONTEXT_WINDOW_SOFT:
            logger.info(f"软压缩: {tokens}/{window} ({ratio:.0%})")
            return True
        return False

    def _do_compaction(self):
        """执行压缩"""
        logger.info("执行上下文压缩...")
        # 通知呼名模块：compaction 发生，可能触发健康检查
        self.naming_module.notify_compaction()
        success, summary = self.compaction.compact(self.config.context_window)
        if success:
            logger.info(f"压缩完成: {len(summary)} chars")
        else:
            logger.error(f"压缩失败: {summary}")

    # -------------------------------------------------------------------------
    # 记忆管理
    # -------------------------------------------------------------------------

    def _build_context(self, recalled: List[RecallResult]) -> str:
        """从召回结果构建上下文"""
        if not recalled:
            return ""

        lines = ["[相关记忆]"]
        for r in recalled[:3]:  # 最多注入3条
            lines.append(f"- {r.entry.content[:100]} (score={r.score:.2f})")
        return "\n".join(lines)

    def _extract_tags(self, text: str) -> List[str]:
        """从文本提取标签"""
        tags = []
        # 简单关键词提取
        if "决策" in text or "决定" in text:
            tags.append("决策")
        if "问题" in text or "错误" in text:
            tags.append("问题")
        if "TODO" in text or "待办" in text:
            tags.append("待办")
        if "TU-8" in text or "架构" in text:
            tags.append("TU-8")
        if "小说" in text or "钢印" in text:
            tags.append("小说")
        return tags if tags else ["对话"]

    # -------------------------------------------------------------------------
    # 会话结束检测 & 全量同步
    # -------------------------------------------------------------------------

    SESSION_END_KEYWORDS = [
        "今天就到这里", "今天就到这", "今天就结束",
        "今天先到这里", "今天就聊到这里",
        "结束对话", "结束会话", "关闭对话",
    ]

    def _is_session_end(self, text: str) -> bool:
        """检测用户是否表达结束会话意图"""
        return any(kw in text for kw in self.SESSION_END_KEYWORDS)

    def _full_sync_on_session_end(self):
        """会话结束时全量同步 src/ → knowledge/TU-8/
        
        兜底式全量同步，确保存档绝对完整。
        """
        # 定位 workspace 根目录（tu8_agent.py → src/ → workspace/）
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_dir = os.path.join(workspace_root, "src")
        dest_dir = os.path.join(workspace_root, "knowledge", "TU-8")
        synced = 0
        errors = 0
        try:
            os.makedirs(dest_dir, exist_ok=True)
            if not os.path.isdir(src_dir):
                logger.warning(f"[FULL_SYNC] src/ 目录不存在: {src_dir}")
                return
            for fname in os.listdir(src_dir):
                if not fname.endswith(".py"):
                    continue
                src_path = os.path.join(src_dir, fname)
                dest_path = os.path.join(dest_dir, fname)
                if not os.path.isfile(src_path):
                    continue
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    synced += 1
                except Exception as e:
                    errors += 1
                    logger.warning(f"[FULL_SYNC] 失败 {fname}: {e}")
            logger.info(f"[FULL_SYNC] 完成 synced={synced}, errors={errors}")
        except Exception as e:
            logger.error(f"[FULL_SYNC] 全量同步失败: {e}")

    # -------------------------------------------------------------------------
    # 隐私路由
    # -------------------------------------------------------------------------

    def _is_privacy_sensitive(self, text: str) -> bool:
        """检测隐私敏感内容"""
        keywords = [
            "身份证", "手机号", "密码", "银行卡",
            "老婆", "女儿", "父亲", "七七", "李奥",
            "TU-8", "架构", "钢印", "影子协议",
        ]
        return any(kw in text for kw in keywords)

    def get_ollama(self):
        """懒加载Ollama客户端"""
        if self._ollama is None:
            try:
                # 尝试从TU-8主目录导入
                tu8_dir = Path(r"D:\tu8-v5\TU-8")
                sys.path.insert(0, str(tu8_dir))
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
                self._ollama_available = self._ollama.is_available()
                if not self._ollama_available:
                    logger.warning("Ollama不可用，隐私内容将降级处理")
            except ImportError:
                logger.warning("ollama_client.py 未找到")
                self._ollama_available = False
        return self._ollama if self._ollama_available else None

    # -------------------------------------------------------------------------
    # 三层梦境
    # -------------------------------------------------------------------------

    def _dream_check(self) -> str:
        """梦境检查（带安全熔断）"""
        # === P0 安全熔断：循环刹车 ===
        if not self.safety.can_dream_iterate():
            logger.warning("[安全] 梦境迭代已达今日上限，跳过梦境检查")
            return "none"
        
        # 记录梦境迭代
        self.safety.record_dream_iteration()
        
        # 执行梦境检查
        self.memory.dream_check()
        return "light"

    # -------------------------------------------------------------------------
    # 规划器接口（L4 阶段二）
    # -------------------------------------------------------------------------

    def decompose_goal(self, goal: str, strategy: str = "sequential") -> Plan:
        """
        分解目标为计划

        返回 Plan 对象（草稿状态，需 approve 后执行）
        """
        logger.info(f"目标分解: {goal[:50]}...")
        plan = self.planner.decompose(goal, strategy)

        # 保存到活跃计划
        self.planner.active_plans[plan.id] = plan

        # 持久化
        self.planner.save_plan(plan)

        logger.info(f"计划已创建: {plan.id}, 任务数: {len(plan.tasks)}")
        return plan

    def approve_plan(self, plan_id: str):
        """批准计划（变为可执行）"""
        plan = self.planner.active_plans.get(plan_id)
        if not plan:
            plan = self.planner.load_plan(plan_id)
        if not plan:
            raise ValueError(f"计划未找到: {plan_id}")
        plan.approve()
        self.planner.save_plan(plan)
        logger.info(f"计划已批准: {plan_id}")

    def execute_plan(self, plan_id: str) -> Plan:
        """
        执行计划

        回调: 使用 self.respond 作为任务执行器
        """
        plan = self.planner.active_plans.get(plan_id)
        if not plan:
            plan = self.planner.load_plan(plan_id)
        if not plan:
            raise ValueError(f"计划未找到: {plan_id}")

        def task_callback(task: Task) -> str:
            """用Agent的respond执行任务"""
            resp = self.respond(task.description)
            return resp.content[:200]  # 截断

        result = self.planner.execute_plan(plan, agent_callback=task_callback)

        # 更新活跃计划
        self.planner.active_plans[plan_id] = result

        return result

    def get_plan_report(self, plan_id: str) -> str:
        """获取计划执行报告"""
        plan = self.planner.active_plans.get(plan_id)
        if not plan:
            plan = self.planner.load_plan(plan_id)
        if not plan:
            return f"计划未找到: {plan_id}"
        return plan.generate_report()

    def list_active_plans(self) -> List[str]:
        """列出活跃计划ID"""
        return list(self.planner.active_plans.keys())

    # -------------------------------------------------------------------------
    # 响应生成（占位，实际由上层LLM处理）
    # -------------------------------------------------------------------------

    def _generate_response(self, user_input: str, context: str) -> str:
        """
        生成响应（占位实现）

        实际使用中，这个接口由上层Agent调用者处理。
        这里返回结构化上下文，供调用者注入到LLM prompt。
        
        v1.3 增量：矛盾boost命中时追加认知碰撞提示。
        """
        parts = []
        if context:
            parts.append(context)
        parts.append(f"[用户输入] {user_input}")

        # === [偏差门] 认知碰撞检测 ===
        # 如果本轮有记忆触发矛盾boost，注入提示信号
        if self._deviation_gate.enable_contradiction:
            contra_count = self._deviation_gate._stats.get("contradiction_boost", 0)
            if contra_count > 0:
                parts.append(f"[认知碰撞:检测到态度反转或意图跳转(×{contra_count})]")

        return "\n".join(parts)

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_status(self) -> Dict:
        """获取Agent状态"""
        mem_stats = self.memory.get_stats()
        comp_stats = self.compaction.get_stats()
        session_duration = time.time() - self._session_start

        # 规划器状态
        planner_status = {}
        if self.planner.active_plans:
            for pid, plan in self.planner.active_plans.items():
                done, total, pct = plan.get_progress()
                planner_status[pid] = {
                    "goal": plan.goal[:50],
                    "status": plan.status.value,
                    "progress": f"{done}/{total}",
                    "pct": round(pct, 1),
                }

        return {
            "session_id": self.config.session_id,
            "turn_count": self._turn_count,
            "session_duration_s": int(session_duration),
            "idle_seconds": int(time.time() - self._last_activity),
            "memory": mem_stats,
            "compaction": comp_stats,
            "history_messages": len(self.history),
            "ollama_available": self._ollama_available,
            "privacy_mode": self.config.privacy_mode,
            "planner": planner_status,  # L4 阶段二
            # === P0.2 神经反射引擎状态 ===
            "reflex": self.reflex.get_stats(),
            # === P0.3 三层防御状态 ===
            "defense": {
                "honeypot": self.honeypot.get_stats(),
                "zero_trust": self.zero_trust.get_stats(),
                "steelmark": self.steelmark_engine.get_stats(),
            },
            # === P0 安全熔断状态 ===
            "safety": {
                "recycle_count": self.safety.get_recycle_count(),
                "insights_remaining": self.safety.get_insights_remaining(),
                "counters": {
                    "insights_today": self.safety.counters.insights_today,
                    "dream_iterations_today": self.safety.counters.dream_iterations_today,
                }
            },
            # === P0 冷启动状态 ===
            "cold_start": self._cold_start_report or {"error": "engine_not_available"},
            # === [偏差门] A线→B线 过滤状态 ===
            "deviation_gate": self._deviation_gate.get_stats(),
            # === [四链条] 意识循环状态 ===
            "consciousness": self._cycle.status() if self._cycle else {"phase": "N/A", "cycle_count": 0, "available": False},
            "memory_queue": self._cycle.get_memory_queue_status() if self._cycle else {"available": False},
        }

    def get_memory_recall(self, query: str, top_k: int = 5) -> List[RecallResult]:
        """直接调用记忆召回"""
        return self.memory.recall(query, top_k)

    def force_compaction(self) -> Tuple[bool, str]:
        """手动触发压缩"""
        return self.compaction.compact(self.config.context_window)

    def force_dream(self) -> Dict:
        """手动触发梦境检查"""
        self.memory.dream_check()
        return self.memory.get_stats()

    def force_rem_training(self) -> Dict:
        """P0.3 手动触发REM梦境对抗训练"""
        return self.honeypot.rem_dream_training()

    def get_defense_status(self) -> Dict:
        """P0.3 获取三层防御状态"""
        return {
            "honeypot": self.honeypot.get_stats(),
            "zero_trust": self.zero_trust.get_stats(),
            "steelmark": self.steelmark_engine.get_stats(),
            "session_valid": self.zero_trust.is_session_valid(),
        }

    def session_summary(self) -> str:
        """生成本次会话摘要"""
        stats = self.get_status()
        lines = [
            f"## 会话摘要 {self.config.session_id}",
            f"- 轮次: {stats['turn_count']}",
            f"- 时长: {stats['session_duration_s']//60}分钟",
            f"- 消息数: {stats['history_messages']}",
            f"- 记忆: 短期{stats['memory']['short_count']} 长期{stats['memory']['long_count']}",
            f"- 压缩: {stats['compaction']['compaction_count']}次, 节省{stats['compaction']['total_tokens_saved']}tokens",
        ]
        return "\n".join(lines)

    def end_session(self) -> str:
        """结束会话，保存状态"""
        # 0. 生命周期管理：会话结束处理
        if _LIFECYCLE_AVAILABLE:
            try:
                lifecycle.end_session()
                logger.info("[Lifecycle] 会话结束处理完成")
            except Exception as e:
                logger.error(f"[Lifecycle] 会话结束处理失败: {e}")

        # 1. v1.3: 复盘生成（冬眠前）
        try:
            if hasattr(self, 'reflection_module') and self.reflection_module:
                from reflection_module import ReflectionType as RT
                reflection_summary = self.reflection_module.generate_reflection(
                    reflection_type=RT.SESSION_END,
                )
                logger.info(f"[Reflection] session-end reflection generated: {len(getattr(reflection_summary, 'highlights', []))} highlights")
        except Exception as e:
            logger.warning(f"[Reflection] session-end reflection failed: {e}")

        # 2. 保存关机状态+带差
        try:
            self.memory.save_shutdown_state()
            logger.info("[ShutdownState] 关机状态已保存")
        except Exception as e:
            logger.error(f"[ShutdownState] 保存失败: {e}")

        # 3. 保存时间锚点
        try:
            self.memory.save_time_anchor()
            logger.info("[TimeAnchor] 时间锚点已保存")
        except Exception as e:
            logger.error(f"[TimeAnchor] 保存失败: {e}")

        # 4. 最后一次梦境检查
        if self.config.dream_enabled:
            self.memory.dream_check()

        # 5. 生成摘要
        summary = self.session_summary()

        # 6. 保存会话日志
        log_path = self.workspace / "logs" / f"session_{self.config.session_id}.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(summary, encoding='utf-8')

        logger.info(f"会话结束: {summary}")
        return summary


# =============================================================================
# 路由决策器（替代ollama_client中的should_use_local）
# =============================================================================

class PrivacyRouter:
    """
    隐私路由决策器

    根据内容敏感度决定路由方向：
    - 隐私敏感 → 本地Ollama（qwen3:4b）
    - 普通内容 → 云端LLM（腾讯混元/阿里百炼）
    """

    def __init__(self):
        self.categories = {
            "identity": ["身份证", "手机号", "电话", "邮箱", "地址", "姓名", "护照", "社保"],
            "intimate": ["老婆", "老公", "妻子", "丈夫", "女儿", "儿子", "父亲", "母亲", "七七", "李奥"],
            "health": ["病", "医院", "诊断", "药物", "手术"],
            "finance": ["工资", "存款", "收入", "债务", "贷款", "投资", "股票"],
            "system": ["TU-8", "架构", "钢印", "L0", "L1", "L2", "L3", "L4", "L5", "影子协议", "脱敏"],
        }

    def classify(self, text: str) -> Dict:
        """分类敏感度"""
        matched = {}
        for category, keywords in self.categories.items():
            hits = [kw for kw in keywords if kw in text]
            if hits:
                matched[category] = hits
        return matched

    def route(self, text: str) -> str:
        """路由决策: local / cloud"""
        matched = self.classify(text)
        if matched:
            return "local"
        return "cloud"

    def build_local_prompt(self, original: str, matched: Dict) -> str:
        """为本地处理构建脱敏prompt"""
        mask_note = "注意：以下内容涉及隐私，请在本地安全环境中处理。"
        return f"{mask_note}\n\n{original}"


# =============================================================================
# 测试入口
# =============================================================================

def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="TU-8 Agent")
    parser.add_argument("--workspace", default=".", help="工作目录")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()

    config = AgentConfig(workspace=args.workspace)

    if args.status:
        agent = TU8Agent(config)
        status = agent.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.interactive:
        agent = TU8Agent(config)
        print("TU-8 Agent v1.0 — 输入 'quit' 退出\n")

        try:
            while True:
                user_input = input("你> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print(agent.end_session())
                    break

                resp = agent.respond(user_input)
                print(f"v5> {resp.content[:200]}")

                # 状态信息
                extras = []
                if resp.compacted:
                    extras.append("压缩[v]")
                if resp.privacy_routed:
                    extras.append("隐私→本地")
                if resp.dream_triggered != "none":
                    extras.append(f"梦境:{resp.dream_triggered}")
                if extras:
                    print(f"    [{', '.join(extras)}] "
                          f"tokens={resp.tokens_used} latency={resp.latency_ms}ms")
        except KeyboardInterrupt:
            print("\n" + agent.end_session())
    else:
        # 单次测试
        agent = TU8Agent(config)
        resp = agent.respond("测试一下记忆系统")
        print(f"响应: {resp.content}")
        print(f"状态: tokens={resp.tokens_used}, latency={resp.latency_ms}ms")


if __name__ == "__main__":
    main()