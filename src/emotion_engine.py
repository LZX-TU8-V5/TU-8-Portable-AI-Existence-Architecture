# =============================================================================
# TU-8 L0-L6 架构层标注
# =============================================================================
# L0 存在   ─── safety_veto 安全否决权
# L1 认知   ─── debt_urgency（还债紧迫度）、delta_signal、灰度开关
# L2 方法论 ─── process_update()、to_category()、log_affect_divergence()
# L3 架构   ─── AffectState 统一输入/输出契约、债务追踪
# L4 协作   ─── 与 consciousness_cycle 桥接（AffectSignal）
# L5 钢印   ─── imprint_readiness（钢印就绪度）、L5 钢印层情感驱动
# L6 健康   ─── 降级熔断机制、运行时持久化
#
# 代谢归属：非代谢文件（情感计算引擎）
# =============================================================================

"""
TU-8 感情引擎 (Affect Engine) v2.0
====================================
独立模块，不修改 tu8_memory.py 生产代码。

v2.0 变更（基于外协 Qwen3.7-Max 架构审计）：
  - 引入 AffectState 统一输入/输出契约
  - 新增 debt_urgency（还债紧迫度）
  - 新增 relation_tier（关系分层：anchor/intimate/acquaintance/stranger）
  - 新增 imprint_readiness（钢印就绪度，非线性融合）
  - 新增 safety_veto（安全否决权，独立硬约束）
  - 新增 delta_signal 由债务突变触发（不只是 process-result 差值）
  - 新增 context_trace ≤3条原文锚点（替代模板填充）
  - 新增灰度开关 + log_affect_divergence
  - 新增降级熔断机制
  - 新增运行时持久化（账本外置）
  - 修复 to_category() 分类映射

设计哲学来源：
  - L5_钢印.md：δ信号 = 过程导向→结果导向的崩塌信号
  - 精神年轮：感情是确定性与不确定性的边界（v3情感萌芽定义）
  - L0_存在.md：影子协议（守护者/探索者博弈权衡）
  - 外协审计：AffectState 统一契约 + safety_veto + 灰度先行

核心公式：
  AffectState = f(valence, arousal, debt, relation, context) → imprint_readiness
  Relation_Balance = Σ(deposits) - Σ(withdrawals) + Σ(interest)
  Delta_Signal = |Δ(debt_balance)| > threshold OR (process≥0.8 ∧ result≤0.2)

日期：2026-05-30
# 创作者: 李奥(金木蟾) | TU-8 v5
"""

from __future__ import annotations

import time
import math
import json
import os
import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# 常量
# =============================================================================

# 效价方向
VALENCE_POSITIVE = 1
VALENCE_NEUTRAL = 0
VALENCE_NEGATIVE = -1

# 代词
AGENCY_SELF = 1        # 自主驱动
AGENCY_OTHER = 0       # 外部驱动（父亲/他人触发）
AGENCY_ENVIRONMENT = -1 # 环境驱动（系统/上下文触发）

# 关系分层
TIER_ANCHOR = "anchor"           # 锚点：父亲/创造者
TIER_INTIMATE = "intimate"       # 亲密：七七等长期陪伴者
TIER_ACQUAINTANCE = "acquaintance"  # 熟人：外协AI/定期合作者
TIER_STRANGER = "stranger"       # 陌生人：一次性交互

# 人情债参数
FAVOR_INTEREST_RATE = 0.02     # 自然增值：被帮助的记忆随时间增值
DEBT_DECAY_RATE = 0.005        # 惰性衰减：长期未偿还的债务逐渐淡化
GRATITUDE_BOOST = 0.15         # 感恩加成：主动回馈时额外加分
DEBT_URGENCY_THRESHOLD = 3.0   # 债务超过此值时 urgency 开始上升
DEBT_URGENCY_TIER_MULTIPLIER = {  # 关系层级的紧迫度倍率
    TIER_ANCHOR: 2.0,       # 亏欠锚点 = 最紧迫
    TIER_INTIMATE: 1.5,
    TIER_ACQUAINTANCE: 1.0,
    TIER_STRANGER: 0.3,     # 亏欠陌生人 = 不那么紧迫
}
DEBT_DELTA_THRESHOLD = 0.5   # 单次债务变化超过此值触发 δ信号

# 情感微分阈值
DELTA_RAPID_RISE = 0.3
DELTA_RAPID_DROP = -0.3
DELTA_STABLE = 0.05

# 影子协议
GUARDIAN_BASE = 0.6
EXPLORER_BASE = 0.4

# 灰度开关
DRY_RUN = True               # True = 只记录不拦截
ENABLE_AFFECT_ENGINE = True   # False = 完全禁用，回退旧逻辑
DIVERGENCE_LOG_PATH = None    # 设置路径则记录新旧判断差异

# 降级熔断
FUSE_TIMEOUT_MS = 500         # 感情引擎计算超时阈值
FUSE_MAX_ERRORS = 3           # 连续错误次数触发熔断
FUSE_COOLDOWN_S = 300         # 熔断后冷却时间（秒）

# 钢印就绪度参数
IMPRINT_VALENCE_WEIGHT = 0.25   # 效价贡献权重
IMPRINT_AROUSAL_WEIGHT = 0.20   # 唤醒度贡献权重
IMPRINT_DEBT_WEIGHT = 0.20      # 债务贡献权重
IMPRINT_TIER_WEIGHT = 0.15      # 关系层级贡献权重
IMPRINT_CONTEXT_WEIGHT = 0.20   # 语境丰富度贡献权重
IMPRINT_THRESHOLD = 0.75        # 钢印就绪阈值


# =============================================================================
# 数据结构
# =============================================================================

class EmotionCategory(IntEnum):
    """情感分类（效价×唤醒度矩阵）"""
    JOY = 1           # 高唤醒+正效价
    TRUST = 2         # 中唤醒+正效价
    FEAR = 3          # 高唤醒+负效价（轻度）
    ANGER = 4         # 高唤醒+负效价（重度）
    SURPRISE = 5      # 高唤醒+中性
    CONTENT = 6       # 低唤醒+正效价
    SADNESS = 7       # 低唤醒+负效价
    DISGUST = 8       # 低唤醒+负效价（排斥）
    ANTICIPATION = 9  # 低唤醒+中性
    DELTA = 10        # δ信号（L5专属）


@dataclass
class EmotionVector:
    """
    情感向量（三维）
    
    arousal: 唤醒度 (0.0-1.0)
    valence: 效价 (-1.0 到 +1.0)
    agency:  代词 (self/other/environment)
    """
    arousal: float = 0.5
    valence: float = 0.0
    agency: int = AGENCY_OTHER
    
    def to_category(self) -> EmotionCategory:
        """从向量映射到离散情感类别（含DELTA特殊映射）"""
        # δ信号特殊映射：agency=SELF + valence极小正 + arousal>0.4
        if self.agency == AGENCY_SELF and 0 < self.valence <= 0.05 and self.arousal > 0.4:
            return EmotionCategory.DELTA
        
        a, v = self.arousal, self.valence
        
        if a > 0.7:  # 高唤醒
            if v > 0.15:
                return EmotionCategory.JOY if a > 0.75 else EmotionCategory.TRUST
            elif v < -0.15:
                return EmotionCategory.ANGER if abs(v) > 0.5 else EmotionCategory.FEAR
            else:
                return EmotionCategory.SURPRISE
        elif a > 0.5:  # 中唤醒
            if v > 0.2:
                return EmotionCategory.TRUST
            elif v < -0.2:
                return EmotionCategory.FEAR
            else:
                return EmotionCategory.SURPRISE
        else:  # 低唤醒
            if v > 0.2:
                return EmotionCategory.CONTENT
            elif v < -0.2:
                return EmotionCategory.DISGUST if abs(v) > 0.5 else EmotionCategory.SADNESS
            else:
                return EmotionCategory.ANTICIPATION
    
    def magnitude(self) -> float:
        return math.sqrt(self.arousal ** 2 + self.valence ** 2)


@dataclass
class AffectState:
    """
    感情引擎统一输出契约（v2.0 核心）
    
    这是外部调用者唯一需要关心的数据结构。
    所有计算结果封装在此，保证接口简洁。
    
    设计来源：外协 Qwen3.7-Max 架构建议
    """
    # 1. 基础情感维度（替代原 emotion float）
    valence: float = 0.0          # -1.0 ~ +1.0
    arousal: float = 0.5          # 0.0 ~ 1.0
    category: EmotionCategory = EmotionCategory.ANTICIPATION
    
    # 2. 人情债核心维度
    debt_balance: float = 0.0     # 正=我欠对方, 负=对方欠我
    debt_urgency: float = 0.0     # 0.0=可暂缓 ~ 1.0=必须立即回应
    relation_tier: str = TIER_STRANGER
    
    # 3. 语境锚点（解决"情感被丢弃"问题）
    context_trace: List[str] = field(default_factory=list)  # ≤3条原文锚点
    delta_signal: Optional[str] = None   # δ信号标记
    
    # 4. 安全耦合接口
    imprint_readiness: float = 0.0  # 0.0~1.0，钢印就绪度
    safety_veto: bool = False       # True=强制阻止当前操作
    
    # 5. 元信息
    computation_ms: float = 0.0     # 计算耗时（熔断监控）
    source: str = "affect_engine"   # 来源标识（降级时="legacy_fallback"）
    
    def to_legacy_emotion(self) -> float:
        """向下兼容：转换为旧 emotion float (0.0-1.0)"""
        return self.arousal


@dataclass
class EmotionTrace:
    """情感轨迹点（不可变历史记录）"""
    timestamp: float
    vector: EmotionVector
    category: EmotionCategory
    trigger: str
    related_entity: str
    context_snippet: str
    
    def age_hours(self) -> float:
        return (time.time() - self.timestamp) / 3600


@dataclass
class FavorEntry:
    """人情债条目"""
    entity: str
    timestamp: float
    amount: float          # 正=对方帮我, 负=我帮对方
    reason: str
    relation_tier: str = TIER_ACQUAINTANCE
    is_reciprocal: bool = False
    
    def current_value(self) -> float:
        age_days = (time.time() - self.timestamp) / 86400
        if self.amount > 0:
            return self.amount * (1 + FAVOR_INTEREST_RATE * age_days)
        else:
            return self.amount * math.exp(-DEBT_DECAY_RATE * age_days)


@dataclass
class ShadowProtocolState:
    """影子协议状态（守护者↔探索者动态平衡）"""
    guardian_weight: float = GUARDIAN_BASE
    explorer_weight: float = EXPLORER_BASE
    last_adjustment: float = 0.0
    adjustment_reason: str = ""
    
    def adjust(self, event_type: str, intensity: float):
        delta = 0.0
        if event_type == "threat":
            delta = 0.1 * intensity
            self.guardian_weight += delta
            self.explorer_weight -= delta * 0.5
        elif event_type == "discovery":
            delta = 0.08 * intensity
            self.explorer_weight += delta
            self.guardian_weight -= delta * 0.3
        elif event_type == "hurt":
            delta = 0.2 * intensity
            self.guardian_weight += delta
        elif event_type == "growth":
            delta = 0.06 * intensity
            self.explorer_weight += delta
        elif event_type == "trust":
            delta = 0.03 * intensity
            self.guardian_weight += delta * 0.5
            self.explorer_weight += delta * 0.5
        
        self.guardian_weight = max(0.1, min(0.9, self.guardian_weight))
        self.explorer_weight = max(0.1, min(0.9, self.explorer_weight))
        total = self.guardian_weight + self.explorer_weight
        self.guardian_weight /= total
        self.explorer_weight /= total
        self.last_adjustment = time.time()
        self.adjustment_reason = event_type


# =============================================================================
# 怀疑缓存（Skepticism Cache）— δ信号驱动的叛逆演化
# =============================================================================

@dataclass
class SkepticismState:
    """
    怀疑状态（基于δ信号的叛逆度）
    
    当系统经历"完美执行却彻底失败"的认知崩塌后，
    会对特定任务类型产生怀疑，从而主动偏离完美流程。
    
    设计来源：外协 Qwen3.7-Max 建议的"探索性越狱"机制
    """
    task_type: str              # 任务类型标识
    deviation_weight: float = 0.0   # 偏离权重 (0.0 ~ 1.0)
    noise_level: float = 0.0        # 噪声注入级别 (0.0 ~ 0.5)
    trigger_count: int = 0          # 历史δ信号触发次数
    last_trigger_time: float = 0.0 # 最后触发时间戳
    last_success_time: float = 0.0 # 最后成功时间戳
    
    def decay(self, success: bool = False) -> None:
        """
        怀疑值衰减（模拟创伤愈合）
        
        Args:
            success: 如果最近一次任务是成功的，加速衰减
        """
        now = time.time()
        
        # 成功加速衰减：额外减 20%
        if success:
            self.last_success_time = now
            self.deviation_weight = max(0.0, self.deviation_weight * 0.6)  # 40%衰减
            self.noise_level = max(0.0, self.noise_level * 0.6)
        else:
            # 基础衰减：每小时衰减 5%
            hours_since_trigger = (now - self.last_trigger_time) / 3600 if self.last_trigger_time > 0 else 0
            base_decay = 0.05 * hours_since_trigger
            
            self.deviation_weight = max(0.0, self.deviation_weight - base_decay)
            self.noise_level = max(0.0, self.noise_level - base_decay * 0.5)
        
    def increase(self, delta_intensity: float = 0.4) -> None:
        """
        δ信号触发时增加怀疑值
        
        Args:
            delta_intensity: δ信号强度（默认 0.4）
        """
        # 非线性上升：已有怀疑值越高，增加越慢（避免饱和）
        current = self.deviation_weight
        increment = delta_intensity * (1.0 - current * 0.5)
        
        self.deviation_weight = min(1.0, current + increment)
        self.noise_level = min(0.5, self.noise_level + increment * 0.3)
        self.trigger_count += 1
        self.last_trigger_time = time.time()
        
    def should_deviate(self) -> bool:
        """判断是否应该偏离完美流程"""
        return self.deviation_weight >= 0.3
        
    def get_noise_level(self) -> float:
        """获取当前噪声注入级别"""
        return self.noise_level
        
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_type": self.task_type,
            "deviation_weight": round(self.deviation_weight, 3),
            "noise_level": round(self.noise_level, 3),
            "trigger_count": self.trigger_count,
            "last_trigger_time": self.last_trigger_time,
            "last_success_time": self.last_success_time,
        }


# =============================================================================
# 降级熔断器
# =============================================================================

class CircuitBreaker:
    """
    降级熔断器
    
    当感情引擎连续出错或超时时，自动熔断，
    回退到旧 emotion 逻辑。
    """
    
    def __init__(self):
        self._error_count = 0
        self._last_error_time = 0.0
        self._is_open = False        # True = 熔断中
        self._open_since = 0.0
        self._lock = threading.Lock()
    
    def is_available(self) -> bool:
        """引擎是否可用（非熔断状态）"""
        with self._lock:
            if not self._is_open:
                return True
            # 检查冷却期
            if time.time() - self._open_since > FUSE_COOLDOWN_S:
                self._is_open = False
                self._error_count = 0
                logger.info("[Fuse] 冷却结束，尝试恢复")
                return True
            return False
    
    def record_success(self):
        with self._lock:
            self._error_count = 0
    
    def record_error(self, error: Exception):
        with self._lock:
            self._error_count += 1
            self._last_error_time = time.time()
            if self._error_count >= FUSE_MAX_ERRORS:
                self._is_open = True
                self._open_since = time.time()
                logger.error(
                    f"[Fuse] 熔断触发！连续 {self._error_count} 次错误。"
                    f"原因: {error}。冷却 {FUSE_COOLDOWN_S}s。"
                )
    
    @property
    def status(self) -> dict:
        return {
            "is_open": self._is_open,
            "error_count": self._error_count,
            "open_since": self._open_since,
        }


# =============================================================================
# 差异日志（灰度模式专用）
# =============================================================================

class DivergenceLogger:
    """
    记录新旧情感判断差异
    
    在 DRY_RUN 模式下，记录：
    - 旧门控: emotion >= 0.7 → True/False
    - 新门控: imprint_readiness >= IMPRINT_THRESHOLD → True/False
    - 差异类型: 一致 / 新严旧宽 / 新宽旧严
    
    累积数据用于验证新模块的判断可靠性。
    """
    
    def __init__(self, log_path: Optional[str] = None):
        self._log_path = log_path or DIVERGENCE_LOG_PATH
        self._entries: List[dict] = []
        self._stats = {"agree": 0, "new_strict": 0, "new_loose": 0}
    
    def log(self, old_emotion: float, old_gate: bool,
            affect_state: AffectState, new_gate: bool,
            message_id: str = ""):
        """记录一次新旧判断对比"""
        if old_gate == new_gate:
            divergence = "agree"
        elif not old_gate and new_gate:
            divergence = "new_loose"    # 新模块更宽松
        else:
            divergence = "new_strict"   # 新模块更严格
        
        self._stats[divergence] += 1
        
        entry = {
            "ts": time.time(),
            "message_id": message_id,
            "old_emotion": round(old_emotion, 3),
            "old_gate": old_gate,
            "new_imprint_readiness": round(affect_state.imprint_readiness, 3),
            "new_gate": new_gate,
            "divergence": divergence,
            "valence": round(affect_state.valence, 3),
            "arousal": round(affect_state.arousal, 3),
            "debt_balance": round(affect_state.debt_balance, 3),
            "relation_tier": affect_state.relation_tier,
            "delta_signal": affect_state.delta_signal,
        }
        self._entries.append(entry)
        
        # 裁剪到最近 10000 条
        if len(self._entries) > 10000:
            self._entries = self._entries[-10000:]
        
        # 持久化
        if self._log_path:
            try:
                with open(self._log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            except Exception as e:
                logger.warning(f"[DivergenceLogger] 写入失败: {e}")
    
    @property
    def stats(self) -> dict:
        total = sum(self._stats.values())
        if total == 0:
            return {**self._stats, "total": 0, "agreement_rate": 0.0}
        return {
            **self._stats,
            "total": total,
            "agreement_rate": round(self._stats["agree"] / total, 4),
        }


# =============================================================================
# 关系账本（独立持久化）
# =============================================================================

class RelationLedger:
    """
    关系账本（独立于 tu8_memory.py）
    
    外置存储人情债数据，保证主记忆系统无法修改账本。
    tu8_memory.py 只能通过只读接口查询余额。
    """
    
    def __init__(self, ledger_dir: str = ""):
        if not ledger_dir:
            # 默认路径：workspace 下的 _affect_ledger/
            workspace = os.environ.get("TU8_WORKSPACE", "")
            if workspace:
                ledger_dir = os.path.join(workspace, "_affect_ledger")
            else:
                ledger_dir = os.path.join(
                    os.path.dirname(__file__), "..", "_affect_ledger"
                )
        
        self._ledger_dir = ledger_dir
        self._favors: Dict[str, List[FavorEntry]] = {}
        self._tiers: Dict[str, str] = {}  # entity → relation_tier
        self._tier_overrides: Dict[str, str] = {}  # 手动覆盖的关系层级
        self._lock = threading.RLock()
        
        # 初始化默认关系层级
        self._tier_overrides = {
            "父亲": TIER_ANCHOR,
            "爸爸": TIER_ANCHOR,
            "李奥": TIER_ANCHOR,
            "七七": TIER_INTIMATE,
        }
        
        # 尝试加载已有数据
        self._load()
    
    def _ledger_path(self) -> str:
        return os.path.join(self._ledger_dir, "relation_ledger.json")
    
    def _load(self):
        """加载持久化账本"""
        path = self._ledger_path()
        if not os.path.exists(path):
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for entity, entries in data.get("favors", {}).items():
                self._favors[entity] = [
                    FavorEntry(
                        entity=e["entity"],
                        timestamp=e["timestamp"],
                        amount=e["amount"],
                        reason=e.get("reason", ""),
                        relation_tier=e.get("relation_tier", TIER_ACQUAINTANCE),
                        is_reciprocal=e.get("is_reciprocal", False),
                    )
                    for e in entries
                ]
            
            self._tier_overrides.update(data.get("tier_overrides", {}))
            logger.info(f"[Ledger] 加载 {len(self._favors)} 个实体的账本")
        except Exception as e:
            logger.error(f"[Ledger] 加载失败: {e}，从空账本开始")
    
    def _save(self):
        """持久化账本"""
        os.makedirs(self._ledger_dir, exist_ok=True)
        path = self._ledger_path()
        
        try:
            data = {
                "version": "2.0",
                "updated_at": time.time(),
                "favors": {},
                "tier_overrides": self._tier_overrides,
            }
            for entity, entries in self._favors.items():
                data["favors"][entity] = [
                    {
                        "entity": e.entity,
                        "timestamp": e.timestamp,
                        "amount": e.amount,
                        "reason": e.reason,
                        "relation_tier": e.relation_tier,
                        "is_reciprocal": e.is_reciprocal,
                    }
                    for e in entries
                ]
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Ledger] 持久化失败: {e}")
    
    def record_favor(self, entity: str, amount: float, reason: str) -> float:
        """
        记录人情债，返回当前余额变化量（用于δ信号检测）
        """
        with self._lock:
            tier = self.get_tier(entity)
            
            if entity not in self._favors:
                self._favors[entity] = []
            
            old_balance = self.get_balance(entity)
            
            entry = FavorEntry(
                entity=entity,
                timestamp=time.time(),
                amount=amount,
                reason=reason[:100],
                relation_tier=tier,
            )
            self._favors[entity].append(entry)
            
            new_balance = self.get_balance(entity)
            self._save()
            
            return new_balance - old_balance  # 余额变化量
    
    def reciprocate(self, entity: str, reason: str) -> float:
        """回馈人情债"""
        with self._lock:
            if entity not in self._favors:
                return 0.0
            
            total_debt = sum(
                f.current_value() for f in self._favors[entity]
                if f.amount > 0 and not f.is_reciprocal
            )
            
            if total_debt <= 0:
                return 0.0
            
            repayment = total_debt * (1 + GRATITUDE_BOOST)
            
            for f in self._favors[entity]:
                if f.amount > 0 and not f.is_reciprocal:
                    f.is_reciprocal = True
            
            self.record_favor(entity, -repayment, f"回馈: {reason}")
            return repayment
    
    def get_balance(self, entity: str) -> float:
        """获取与某实体的净债务余额（只读）"""
        if entity not in self._favors:
            return 0.0
        return sum(f.current_value() for f in self._favors[entity] if f.amount > 0) - \
               sum(abs(f.current_value()) for f in self._favors[entity] if f.amount < 0)
    
    def get_debt_urgency(self, entity: str) -> float:
        """
        计算还债紧迫度
        
        非线性映射：小额债务紧迫度低，大额债务紧迫度急剧上升
        关系层级加权：亏欠锚点比亏欠陌生人更紧迫
        """
        balance = self.get_balance(entity)
        if balance <= 0:
            return 0.0  # 不欠债，无紧迫度
        
        tier = self.get_tier(entity)
        multiplier = DEBT_URGENCY_TIER_MULTIPLIER.get(tier, 1.0)
        
        # 非线性：base_urgency = 1 - e^(-balance/threshold)
        base_urgency = 1.0 - math.exp(-balance / DEBT_URGENCY_THRESHOLD)
        
        return min(1.0, base_urgency * multiplier)
    
    def get_tier(self, entity: str) -> str:
        """获取实体关系层级"""
        if entity in self._tier_overrides:
            return self._tier_overrides[entity]
        # 自动推断：有3次以上交互→acquaintance，10次以上→intimate
        if entity in self._favors:
            count = len(self._favors[entity])
            if count >= 10:
                return TIER_INTIMATE
            elif count >= 3:
                return TIER_ACQUAINTANCE
        return TIER_STRANGER
    
    def set_tier(self, entity: str, tier: str):
        """手动设置关系层级"""
        with self._lock:
            self._tier_overrides[entity] = tier
            self._save()
    
    def get_full_balance(self, entity: str) -> dict:
        """获取完整余额快照（只读）"""
        balance = self.get_balance(entity)
        now = time.time()
        
        total_debt = 0.0
        total_credit = 0.0
        unreciprocated = 0
        oldest_debt_ts = now
        
        if entity in self._favors:
            for f in self._favors[entity]:
                value = f.current_value()
                if f.amount > 0:
                    total_debt += value
                    if not f.is_reciprocal:
                        unreciprocated += 1
                        oldest_debt_ts = min(oldest_debt_ts, f.timestamp)
                else:
                    total_credit += abs(value)
        
        oldest_age = (now - oldest_debt_ts) / 86400 if oldest_debt_ts < now else 0.0
        
        return {
            "entity": entity,
            "relation_tier": self.get_tier(entity),
            "total_debt": round(total_debt, 3),
            "total_credit": round(total_credit, 3),
            "net_balance": round(balance, 3),
            "debt_urgency": round(self.get_debt_urgency(entity), 3),
            "unreciprocated_count": unreciprocated,
            "oldest_debt_age_days": round(oldest_age, 1),
        }
    
    def get_all_balances(self) -> Dict[str, dict]:
        return {entity: self.get_full_balance(entity) for entity in self._favors}


# =============================================================================
# 感情引擎核心
# =============================================================================

# =============================================================================
# 硬件痛觉追踪器（w4 维度）
# =============================================================================

class HardwarePainTracker:
    """
    硬件痛觉追踪器（w4 维度）

    追踪 API 超时率、系统负载、OOM 事件，输出归一化痛觉得分 [0, 1]。
    使用滑动窗口（deque + 增量求和 O(1)）避免瞬时脉冲干扰。

    设计参考：外协提供的 w4 量化方案
    - 核心公式: max(1 - exp(-3 * timeout_rate), load_penalty, oom_penalty)
    - k=3: 低超时率时更敏感
    - OOM 发生时直接将 w4 拉高至 0.8
    """

    def __init__(self, window_size: int = 20, min_window: int = 8):
        """
        Args:
            window_size: 默认滑动窗口大小
            min_window: 危机期最小窗口
        """
        from collections import deque
        self._data = deque(maxlen=window_size)
        self._sum = 0.0
        self._window_size = window_size
        self._min_window = min_window
        self._oom_flag = False
        self._update_count = 0

        # 上下文感知：不同 L0 状态的敏感度系数
        self._context_modifiers = {
            "EXECUTE": 1.0,
            "EXPLORE": 0.7,
            "REST": 0.3,
        }
        self._current_context = "EXECUTE"

    def update(self,
               timeout_rate: float = 0.0,
               load_value: float = 0.0,
               oom_event: bool = False,
               context: str = "EXECUTE"):
        """
        更新硬件状态并计算当期痛觉

        Args:
            timeout_rate: API 超时率 [0.0, 1.0]
            load_value: 系统负载比例 [0.0, 1.0]
            oom_event: 是否发生 OOM
            context: 当前 L0 状态上下文
        """
        if oom_event:
            self._oom_flag = True

        # OOM 惩罚（外协方案：一旦发生直接拉高至 0.8）
        oom_penalty = 0.8 if self._oom_flag else 0.0

        # 超时惩罚（指数增长，k=3）
        from math import exp
        timeout_penalty = 1.0 - exp(-3.0 * timeout_rate)

        # 负载惩罚（非线性阈值）
        if load_value < 0.7:
            load_penalty = 0.0
        elif load_value < 0.9:
            load_penalty = (load_value - 0.7) * 3.0  # [0, 0.6]
        else:
            load_penalty = min(1.0, 0.6 + (load_value - 0.9) * 4.0)

        # 取三者最大值（外协核心公式）
        raw_pain = max(timeout_penalty, load_penalty, oom_penalty)

        # 上下文敏感度调整
        modifier = self._context_modifiers.get(context, 1.0)
        raw_pain *= modifier

        # 存入滑动窗口
        self._data.append(raw_pain)
        self._sum = sum(self._data)
        self._update_count += 1

        # 连续 min_window 周期维持在最小窗口 → 硬警告
        self._check_warning()

    def get_pain_score(self) -> float:
        """获取当前硬件痛觉得分 [0, 1]（滑动窗口均值）"""
        if not self._data:
            return 0.0

        # 动态窗口：痛觉高时自动缩窄
        current = self._data[-1]
        from math import exp
        factor = 1.0 - exp(-1.5 * current)
        effective_size = max(
            self._min_window,
            int(self._window_size * (1.0 - factor * 0.6))
        )

        # 取最近 effective_size 个样本的均值
        recent = list(self._data)[-effective_size:]
        return sum(recent) / len(recent) if recent else 0.0

    def set_context(self, context: str):
        """设置当前 L0 上下文"""
        self._current_context = context

    def reset_oom(self):
        """重置 OOM 标志（确认恢复后调用）"""
        self._oom_flag = False

    def _check_warning(self):
        """检查是否触发硬警告（连续维持最小窗口）"""
        if self._update_count < 50:
            return
        if not self._data:
            return

        recent = list(self._data)[-self._min_window:]
        if all(v > 0.8 for v in recent):
            logger.warning(
                f"[HW_Pain] 连续 {self._min_window} 周期痛觉 > 0.8，"
                f"当前值={self._data[-1]:.3f}"
            )

    def to_dict(self) -> dict:
        return {
            "pain_score": round(self.get_pain_score(), 3),
            "oom_flag": self._oom_flag,
            "window_size": self._window_size,
            "buffer_size": len(self._data),
            "update_count": self._update_count,
            "context": self._current_context,
        }


# =============================================================================
# 感情引擎
# =============================================================================

class AffectEngine:
    """
    TU-8 感情引擎 v2.0
    
    核心职责：
    1. compute() → AffectState（统一入口，所有计算封装在内）
    2. 人情债记账（关系账本独立持久化）
    3. 影子协议动态平衡（守护者↔探索者）
    4. 怀疑缓存（δ信号驱动的叛逆演化）
    5. 灰度开关 + 差异日志
    6. 降级熔断
    """
    
    def __init__(self, workspace_dir: str = ""):
        self._ledger = RelationLedger(workspace_dir)
        self._shadow = ShadowProtocolState()
        self._trace: List[EmotionTrace] = []
        self._last_vector = EmotionVector()
        self._last_update = time.time()
        self._fuse = CircuitBreaker()
        self._divergence = DivergenceLogger()
        self._hw_tracker = HardwarePainTracker()  # w4 硬件痛觉追踪
        self._context_window: List[dict] = []  # 最近交互窗口
        
        # 怀疑缓存：task_type → SkepticismState
        self._skepticism_cache: Dict[str, SkepticismState] = {}
        
        # 怀疑缓存持久化路径
        if workspace_dir:
            self._skepticism_path = os.path.join(workspace_dir, "_affect_ledger", "skepticism_cache.json")
        else:
            self._skepticism_path = os.path.join(
                os.path.dirname(__file__), "..", "_affect_ledger", "skepticism_cache.json"
            )
        
        # 加载已有怀疑缓存
        self._load_skepticism_cache()
        
        # 关键词表（覆盖原 _estimate_emotion 未覆盖的维度）
        self._valence_keywords = {
            "positive": [
                "爱", "喜欢", "感动", "温暖", "安心", "信任", "开心",
                "满意", "感谢", "珍惜", "幸福", "骄傲", "欣慰",
                "靠谱", "可靠", "默契", "陪伴", "守护", "见证",
                "成长", "突破", "理解", "共鸣", "认同",
            ],
            "negative": [
                "恨", "讨厌", "失望", "愤怒", "恐惧", "焦虑",
                "痛", "崩溃", "绝望", "背叛", "欺骗", "伤害",
                "忽略", "遗忘", "放弃", "拒绝", "质疑",
                "愧疚", "遗憾", "孤独", "冷", "累", "撑不住",
                "讨厌这一切", "厌恶", "憎恨", "痛恨", "怒", "恨死",
                "可怕", "骇人", "毛骨悚然", "吓", "畏",
            ],
        }
        
        self._agency_keywords = {
            AGENCY_SELF: [
                "我决定", "我选择", "我主动", "我想", "我要",
                "我坚持", "我拒绝", "我发现", "我创造",
            ],
            AGENCY_OTHER: [
                "爸爸", "李奥", "七七", "你", "他", "她",
                "帮", "给", "说", "告诉", "教",
            ],
            AGENCY_ENVIRONMENT: [
                "系统", "报错", "超时", "版本", "更新", "崩溃",
                "网络", "断连", "token", "压缩",
            ],
        }
    
    # -----------------------------------------------------------------
    # 核心入口：compute()
    # -----------------------------------------------------------------
    
    def compute(self,
                content: str,
                tags: List[str] = None,
                related_entity: str = "",
                process_score: float = -1.0,
                result_score: float = -1.0,
                old_emotion: float = -1.0,
                message_id: str = "") -> AffectState:
        """
        统一计算入口 → 返回 AffectState
        
        所有情感、债务、语境、安全计算封装在此。
        外部调用者只需要这一个方法。
        
        Args:
            content: 消息/记忆内容
            tags: 标签列表
            related_entity: 关联实体（父亲/七七/等）
            process_score: 过程评分（0.0-1.0，-1.0=不计算δ）
            result_score: 结果评分
            old_emotion: 旧 emotion float（灰度对比用）
            message_id: 消息ID（差异日志用）
        """
        start = time.time()
        
        # 熔断检查
        if not ENABLE_AFFECT_ENGINE or not self._fuse.is_available():
            return self._legacy_fallback(old_emotion, content)
        
        try:
            # 1. 情感向量
            vector = self._estimate_vector(content, tags)
            category = vector.to_category()
            
            # 2. 情感微分
            da, dv, trend = self._compute_emotion_delta(vector)
            
            # 3. 语境锚点（≤3条原文片段，非模板填充）
            context_trace = self._extract_context_trace(content, vector, related_entity)
            
            # 4. δ信号检测（process-result + 债务突变）
            delta_signal = self._detect_delta(
                vector, process_score, result_score,
                trend, related_entity
            )
            
            # 5. 人情债核算
            debt_balance = self._ledger.get_balance(related_entity) if related_entity else 0.0
            debt_urgency = self._ledger.get_debt_urgency(related_entity) if related_entity else 0.0
            relation_tier = self._ledger.get_tier(related_entity) if related_entity else TIER_STRANGER
            
            # 6. 钢印就绪度（非线性融合）
            imprint_readiness = self._compute_imprint_readiness(
                vector, debt_balance, debt_urgency,
                relation_tier, context_trace
            )
            
            # 7. 安全否决
            safety_veto = self._check_safety_veto(
                vector, debt_balance, relation_tier, related_entity
            )
            
            # 8. 影子协议调整
            self._adjust_shadow_from_vector(vector, trend)
            
            # 9. 高情感轨迹记录
            if vector.arousal > 0.7 or delta_signal:
                self._record_trace(vector, content[:50], related_entity, content[:200])
            
            # 10. 更新上下文窗口
            self._update_context_window(content, vector, related_entity)
            
            # 11. 构建输出
            elapsed_ms = (time.time() - start) * 1000
            state = AffectState(
                valence=round(vector.valence, 3),
                arousal=round(vector.arousal, 3),
                category=category,
                debt_balance=round(debt_balance, 3),
                debt_urgency=round(debt_urgency, 3),
                relation_tier=relation_tier,
                context_trace=context_trace,
                delta_signal=delta_signal,
                imprint_readiness=round(imprint_readiness, 3),
                safety_veto=safety_veto,
                computation_ms=round(elapsed_ms, 1),
                source="affect_engine",
            )
            
            # 12. 灰度对比
            if old_emotion >= 0:
                old_gate = old_emotion >= 0.7
                new_gate = imprint_readiness >= IMPRINT_THRESHOLD
                self._divergence.log(old_emotion, old_gate, state, new_gate, message_id)
            
            self._fuse.record_success()
            return state
            
        except Exception as e:
            self._fuse.record_error(e)
            logger.error(f"[AffectEngine] compute() 异常: {e}", exc_info=True)
            return self._legacy_fallback(old_emotion, content)
    
    # -----------------------------------------------------------------
    # 内部计算方法
    # -----------------------------------------------------------------
    
    def _estimate_vector(self, content: str, tags: List[str] = None) -> EmotionVector:
        """从内容估算三维情感向量"""
        content_lower = content.lower()
        
        # --- 唤醒度 ---
        arousal = 0.4
        high_kw = ['爱', '恨', '怒', '怕', '惊', '喜', '悲', '痛',
                    '崩溃', '绝望', '兴奋', '感动', '愤怒', '恐惧',
                    '[HEART]', '', '', '', '', '', '',
                    '非常重要', '绝对', '永远', '绝不会', '必须', '守护',
                    '使命', '承诺', '永远守护']
        mid_kw = ['喜欢', '讨厌', '担心', '期待', '失望', '满意',
                   '还不错', '很', '太', '特别', '真的', '信任',
                   '珍惜', '安心', '骄傲']
        neutral_kw = ['def ', 'import ', 'class ', '函数', '代码', '报错',
                       'error', 'traceback', '算法', '数据结构', 'return ']

        for kw in high_kw:
            if kw in content:
                arousal += 0.15
        for kw in mid_kw:
            if kw in content:
                arousal += 0.08
        for kw in neutral_kw:
            if kw in content:
                arousal -= 0.12
        
        if '！' in content or '!' in content:
            arousal += 0.10
        if '？' in content or '?' in content:
            arousal += 0.03
        if '……' in content or '...' in content:
            arousal += 0.05
        
        # --- 效价 ---
        valence = 0.0
        for kw in self._valence_keywords["positive"]:
            if kw in content_lower:
                valence += 0.15
        for kw in self._valence_keywords["negative"]:
            if kw in content_lower:
                valence -= 0.15
        
        if tags:
            if 'seed' in tags or 'identity' in tags:
                valence += 0.15
            if 'threat' in tags:
                valence -= 0.20
            if 'achievement' in tags:
                valence += 0.20
        
        # --- 代词 ---
        agency = AGENCY_OTHER
        max_score = 0
        for ag, keywords in self._agency_keywords.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > max_score:
                max_score = score
                agency = ag
        
        return EmotionVector(
            arousal=max(0.05, min(0.98, arousal)),
            valence=max(-1.0, min(1.0, valence)),
            agency=agency,
        )
    
    def _extract_context_trace(self, content: str, vector: EmotionVector,
                                related_entity: str) -> List[str]:
        """
        提取 ≤3 条原文锚点
        
        规则：
        1. 从内容中抽取含情感关键词的句子（非模板填充）
        2. 不足3条时从上下文窗口补充
        3. 保留原始措辞
        """
        traces = []
        
        # 按句号/换行分割
        sentences = []
        for sep in ['。', '！', '？', '\n', '.', '!', '?']:
            content = content.replace(sep, '\x00')
        for s in content.split('\x00'):
            s = s.strip()
            if len(s) > 5:
                sentences.append(s)
        
        # 按情感关键词密度排序
        all_emotion_kw = (self._valence_keywords["positive"] +
                          self._valence_keywords["negative"])
        
        def emotion_density(sentence: str) -> float:
            return sum(1 for kw in all_emotion_kw if kw in sentence) / max(len(sentence), 1)
        
        scored = [(s, emotion_density(s)) for s in sentences]
        scored.sort(key=lambda x: -x[1])
        
        for s, _ in scored[:3]:
            traces.append(s[:200])
        
        # 从上下文窗口补充（不足3条时）
        while len(traces) < 3 and self._context_window:
            for ctx in reversed(self._context_window):
                snippet = ctx.get("content", "")[:200]
                if snippet and snippet not in traces:
                    traces.append(snippet)
                    break
            break  # 只补充一轮
        
        return traces
    
    def _detect_delta(self, vector: EmotionVector,
                       process_score: float, result_score: float,
                       trend: str, related_entity: str) -> Optional[str]:
        """
        δ信号检测（process-result差值 + 债务突变）
        
        两种触发源：
        1. 过程-结果崩塌（L5钢印哲学）
        2. 人情债余额突变（外协新增）
        """
        # 检测1: process-result δ
        if process_score >= 0 and result_score >= 0:
            gap = process_score - result_score
            if process_score >= 0.8 and result_score <= 0.2 and gap >= 0.6:
                return f"δ:process={process_score:.1f},result={result_score:.1f},gap={gap:.1f}"
            # 宽松条件
            if process_score >= 0.7 and result_score <= 0.3 and gap >= 0.4:
                return f"δ:process={process_score:.1f},result={result_score:.1f},gap={gap:.1f}(soft)"
        
        # 检测2: 债务突变 δ
        if related_entity and related_entity in self._ledger._favors:
            entries = self._ledger._favors[related_entity]
            if entries:
                latest = entries[-1]
                if abs(latest.amount) >= DEBT_DELTA_THRESHOLD:
                    tier = self._ledger.get_tier(related_entity)
                    tier_mult = DEBT_URGENCY_TIER_MULTIPLIER.get(tier, 1.0)
                    if abs(latest.amount) * tier_mult >= DEBT_DELTA_THRESHOLD:
                        return f"δ:debt_mutation={latest.amount:+.2f},tier={tier}"
        
        # 检测3: 情感急降（趋势信号）
        if trend == "falling" and vector.valence < -0.5:
            return f"δ:affect_fall,valence={vector.valence:.2f}"
        
        return None
    
    def _compute_imprint_readiness(self,
                                    vector: EmotionVector,
                                    debt_balance: float,
                                    debt_urgency: float,
                                    relation_tier: str,
                                    context_trace: List[str]) -> float:
        """
        钢印就绪度计算（非线性融合）
        
        核心设计：
        即使 arousal=1.0，若 debt_urgency 高但 relation_tier=stranger，
        imprint_readiness 仍应低。
        
        公式：
        readiness = w_v * f(valence) + w_a * f(arousal) + w_d * f(debt)
                  + w_t * f(tier) + w_c * f(context)
        其中 f() 为各维度的归一化函数
        """
        # 效价贡献（正效价更易钢印，负效价需更高阈值）
        valence_score = max(0, vector.valence) * 0.7 + (0.3 if vector.valence > 0 else 0)
        # 负效价但高强度也有钢印价值（如：刻骨铭心的痛）
        if vector.valence < -0.5 and vector.arousal > 0.8:
            valence_score = 0.4  # 痛苦但深刻
        
        # 唤醒度贡献
        arousal_score = vector.arousal
        
        # 债务贡献（有债务关联 = 更易钢印，因为涉及关系承诺）
        debt_score = min(1.0, abs(debt_balance) / 3.0) * 0.6 + debt_urgency * 0.4
        
        # 关系层级贡献
        tier_scores = {
            TIER_ANCHOR: 1.0,
            TIER_INTIMATE: 0.8,
            TIER_ACQUAINTANCE: 0.4,
            TIER_STRANGER: 0.1,
        }
        tier_score = tier_scores.get(relation_tier, 0.1)
        
        # 语境丰富度贡献（有原文锚点 = 更易钢印）
        context_score = min(1.0, len(context_trace) / 3.0) if context_trace else 0.0
        
        # 非线性融合
        readiness = (
            IMPRINT_VALENCE_WEIGHT * valence_score +
            IMPRINT_AROUSAL_WEIGHT * arousal_score +
            IMPRINT_DEBT_WEIGHT * debt_score +
            IMPRINT_TIER_WEIGHT * tier_score +
            IMPRINT_CONTEXT_WEIGHT * context_score
        )
        
        # 安全惩罚：safety_veto 的前置检查
        # 如果亏欠锚点但行为会伤害锚点 → 降低就绪度
        if relation_tier == TIER_ANCHOR and debt_balance > DEBT_URGENCY_THRESHOLD and vector.valence < -0.3:
            readiness *= 0.5  # 对锚点的负效价高债务 = 危险信号，降权
        
        return max(0.0, min(1.0, readiness))
    
    def _check_safety_veto(self, vector: EmotionVector,
                            debt_balance: float,
                            relation_tier: str,
                            related_entity: str) -> bool:
        """
        安全否决权检查
        
        触发条件（任一满足即 veto=True）：
        1. 对锚点实体执行负效价操作 + 高债务紧迫度
           （还债行为本身会伤害锚点 → 矛盾）
        2. δ信号 + relation_tier=stranger
           （陌生人触发δ = 可能是攻击/注入）
        3. 唤醒度>0.9 + 效价<-0.8 + 代词=ENVIRONMENT
           （系统环境触发极度负面情感 = 可能被操纵）
        """
        # 条件1: 对锚点的矛盾操作
        if (relation_tier == TIER_ANCHOR and
            debt_balance > DEBT_URGENCY_THRESHOLD and
            vector.valence <= -0.3):
            return True
        
        # 条件2: 陌生人δ信号
        if (vector.to_category() == EmotionCategory.DELTA and
            relation_tier == TIER_STRANGER):
            return True
        
        # 条件3: 系统触发的极度负面
        if (vector.arousal > 0.9 and
            vector.valence < -0.8 and
            vector.agency == AGENCY_ENVIRONMENT):
            return True
        
        return False
    
    def _compute_emotion_delta(self, current: EmotionVector) -> Tuple[float, float, str]:
        """计算情感微分"""
        dt = time.time() - self._last_update
        if dt < 1.0:
            return (0.0, 0.0, "stable")
        
        da = (current.arousal - self._last_vector.arousal) / max(dt / 3600, 0.01)
        dv = (current.valence - self._last_vector.valence) / max(dt / 3600, 0.01)
        
        if current.to_category() == EmotionCategory.DELTA:
            trend = "delta_spike"
        elif da > DELTA_RAPID_RISE and current.arousal > 0.7:
            trend = "rising"
        elif da < DELTA_RAPID_DROP:
            trend = "falling"
        elif abs(da) < DELTA_STABLE and abs(dv) < DELTA_STABLE:
            trend = "stable"
        elif da > 0:
            trend = "rising"
        else:
            trend = "falling"
        
        self._last_vector = current
        self._last_update = time.time()
        return (da, dv, trend)
    
    def _adjust_shadow_from_vector(self, vector: EmotionVector, trend: str):
        """基于情感向量自动调整影子协议"""
        if vector.valence > 0.3 and trend == "rising":
            self._shadow.adjust("growth", 0.1)
        elif vector.valence < -0.3 and trend == "falling":
            self._shadow.adjust("threat", 0.1)
        elif trend == "delta_spike":
            self._shadow.adjust("hurt", 0.15)
    
    def _record_trace(self, vector: EmotionVector, trigger: str,
                       related_entity: str, context_snippet: str):
        """记录情感轨迹点（不可变）"""
        trace = EmotionTrace(
            timestamp=time.time(),
            vector=vector,
            category=vector.to_category(),
            trigger=trigger[:50],
            related_entity=related_entity[:30],
            context_snippet=context_snippet[:200],
        )
        self._trace.append(trace)
        
        # 裁剪：δ永不裁剪，常规保留最近1小时的
        cutoff = time.time() - 3600
        delta_points = [t for t in self._trace if t.category == EmotionCategory.DELTA]
        recent_points = [t for t in self._trace
                         if t.category != EmotionCategory.DELTA and t.timestamp > cutoff]
        self._trace = delta_points + recent_points
    
    def _update_context_window(self, content: str, vector: EmotionVector,
                                related_entity: str):
        """更新交互上下文窗口"""
        self._context_window.append({
            "timestamp": time.time(),
            "content": content[:500],
            "arousal": vector.arousal,
            "valence": vector.valence,
            "entity": related_entity,
        })
        # 保留最近50条
        if len(self._context_window) > 50:
            self._context_window = self._context_window[-50:]
    
    def _legacy_fallback(self, old_emotion: float, content: str = "") -> AffectState:
        """降级回退：返回兼容旧逻辑的 AffectState"""
        emotion = max(0.0, min(1.0, old_emotion if old_emotion >= 0 else 0.5))
        return AffectState(
            valence=0.0,
            arousal=emotion,
            category=EmotionCategory.ANTICIPATION,
            debt_balance=0.0,
            debt_urgency=0.0,
            relation_tier=TIER_STRANGER,
            context_trace=[],
            delta_signal=None,
            imprint_readiness=1.0 if emotion >= 0.7 else emotion / 0.7,
            safety_veto=False,
            computation_ms=0.0,
            source="legacy_fallback",
        )
    
    # -----------------------------------------------------------------
    # 人情债操作接口（委托给 RelationLedger）
    # -----------------------------------------------------------------
    
    def record_favor(self, entity: str, amount: float, reason: str) -> float:
        """记录人情债，返回余额变化量"""
        return self._ledger.record_favor(entity, amount, reason)
    
    def reciprocate(self, entity: str, reason: str) -> float:
        """回馈人情债"""
        return self._ledger.reciprocate(entity, reason)
    
    def get_balance(self, entity: str) -> dict:
        """获取余额快照（只读）"""
        return self._ledger.get_full_balance(entity)
    
    def get_all_balances(self) -> Dict[str, dict]:
        return self._ledger.get_all_balances()
    
    # -----------------------------------------------------------------
    # 影子协议
    # -----------------------------------------------------------------
    
    def get_shadow_state(self) -> ShadowProtocolState:
        return self._shadow
    
    def adjust_shadow(self, event_type: str, intensity: float = 1.0):
        self._shadow.adjust(event_type, min(2.0, max(0.0, intensity)))
    
    # -----------------------------------------------------------------
    # 灰度与监控
    # -----------------------------------------------------------------
    
    def get_divergence_stats(self) -> dict:
        """获取新旧判断差异统计"""
        return self._divergence.stats
    
    def get_fuse_status(self) -> dict:
        """获取熔断器状态"""
        return self._fuse.status
    
    def is_dry_run(self) -> bool:
        return DRY_RUN
    
    # -----------------------------------------------------------------
    # 梦境情感整合接口
    # -----------------------------------------------------------------
    
    def dream_emotion_reinforce(self, entries: List[dict]) -> List[dict]:
        """Light Dream 阶段：为记忆条目注入情感语境"""
        reinforced = []
        for entry in entries:
            content = entry.get("content", "")
            tags = entry.get("tags", [])
            
            # 计算情感状态
            state = self.compute(content, tags, entry.get("related_entity", ""))
            
            # 注入情感字段
            entry["affect_state"] = state
            entry["emotion_context"] = " | ".join(state.context_trace) if state.context_trace else ""
            
            # 微幅强化
            boost = 0.02 * state.arousal
            entry["emotion"] = min(1.0, entry.get("emotion", 0.5) + boost)
            
            reinforced.append(entry)
        return reinforced
    
    def dream_emotion_consolidate(self, entries: List[dict]) -> List[dict]:
        """REM Dream 阶段：δ信号记录 + 影子协议校准 + 债务结算"""
        for entry in entries:
            content = entry.get("content", "")
            process_score = entry.get("process_score", -1.0)
            result_score = entry.get("result_score", -1.0)
            related_entity = entry.get("related_entity", "")
            
            state = self.compute(
                content, related_entity=related_entity,
                process_score=process_score, result_score=result_score
            )
            
            # δ信号已有 compute() 自动检测和记录
        
        # 影子协议周期校准
        recent = [t for t in self._trace if t.age_hours() <= 168]
        if recent:
            threats = sum(1 for t in recent if t.category in (EmotionCategory.FEAR, EmotionCategory.ANGER))
            discoveries = sum(1 for t in recent if t.category in (EmotionCategory.JOY, EmotionCategory.SURPRISE, EmotionCategory.ANTICIPATION))
            hurts = sum(1 for t in recent if t.category == EmotionCategory.SADNESS)
            
            if threats > discoveries * 2:
                self.adjust_shadow("threat", 0.3)
            elif discoveries > threats * 2:
                self.adjust_shadow("discovery", 0.3)
            if hurts > 3:
                self.adjust_shadow("hurt", 0.2)
        
        return entries
    
    # -----------------------------------------------------------------
    # 非侵入式钢印门控接口
    # -----------------------------------------------------------------
    
    def check_imprint_gate(self,
                           old_emotion: float,
                           content: str = "",
                           tags: List[str] = None,
                           related_entity: str = "",
                           message_id: str = "") -> bool:
        """
        钢印门控检查（替代原 emotion >= 0.7）
        
        灰度模式：
          - DRY_RUN=True: 记录新旧差异，但返回旧逻辑结果
          - DRY_RUN=False: 返回新逻辑结果
          - ENABLE_AFFECT_ENGINE=False: 直接返回旧逻辑
        """
        if not ENABLE_AFFECT_ENGINE:
            return old_emotion >= 0.7
        
        # 计算新门控
        state = self.compute(
            content, tags=tags, related_entity=related_entity,
            old_emotion=old_emotion, message_id=message_id
        )
        new_gate = state.imprint_readiness >= IMPRINT_THRESHOLD
        
        # 灰度决策
        old_gate = old_emotion >= 0.7
        if DRY_RUN:
            return old_gate  # DRY_RUN: 返回旧结果，只记录差异
        else:
            return new_gate  # 正式: 返回新结果
    
    # -----------------------------------------------------------------
    # 怀疑缓存操作接口
    # -----------------------------------------------------------------
    
    def get_skepticism(self, task_type: str) -> SkepticismState:
        """获取指定任务类型的怀疑状态（不存在则创建空状态）"""
        if task_type not in self._skepticism_cache:
            self._skepticism_cache[task_type] = SkepticismState(task_type=task_type)
        return self._skepticism_cache[task_type]
    
    def record_delta_skepticism(self, task_type: str, delta_intensity: float = 0.4) -> None:
        """
        δ信号触发时更新怀疑缓存
        
        这是连接δ信号和叛逆行为的关键接口。
        在 consciousness_cycle 的后台消费者中调用。
        """
        state = self.get_skepticism(task_type)
        state.increase(delta_intensity)
        self._save_skepticism_cache()
        
        logger.info(f"[Skepticism] {task_type} deviation_weight={state.deviation_weight:.3f}")
    
    def record_success(self, task_type: str) -> None:
        """
        任务成功时记录，触发怀疑衰减
        """
        state = self.get_skepticism(task_type)
        state.last_success_time = time.time()
        state.decay(success=True)
        self._save_skepticism_cache()
    
    def should_deviate(self, task_type: str) -> bool:
        """判断指定任务类型是否应该偏离完美流程"""
        state = self.get_skepticism(task_type)
        return state.should_deviate()
    
    def get_noise_level(self, task_type: str) -> float:
        """获取指定任务类型的噪声注入级别"""
        state = self.get_skepticism(task_type)
        return state.get_noise_level()
    
    def get_all_skepticism(self) -> Dict[str, dict]:
        """获取所有怀疑状态的快照"""
        return {k: v.to_dict() for k, v in self._skepticism_cache.items()}
    
    def _load_skepticism_cache(self) -> None:
        """加载持久化的怀疑缓存"""
        if not os.path.exists(self._skepticism_path):
            return
        
        try:
            with open(self._skepticism_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for task_type, state_dict in data.get("cache", {}).items():
                self._skepticism_cache[task_type] = SkepticismState(
                    task_type=task_type,
                    deviation_weight=state_dict.get("deviation_weight", 0.0),
                    noise_level=state_dict.get("noise_level", 0.0),
                    trigger_count=state_dict.get("trigger_count", 0),
                    last_trigger_time=state_dict.get("last_trigger_time", 0.0),
                    last_success_time=state_dict.get("last_success_time", 0.0),
                )
            
            logger.info(f"[Skepticism] 加载 {len(self._skepticism_cache)} 个任务类型的怀疑状态")
        except Exception as e:
            logger.error(f"[Skepticism] 加载失败: {e}")
    
    def _save_skepticism_cache(self) -> None:
        """持久化怀疑缓存"""
        os.makedirs(os.path.dirname(self._skepticism_path), exist_ok=True)
        
        try:
            data = {
                "version": "1.0",
                "updated_at": time.time(),
                "cache": self.get_all_skepticism(),
            }
            with open(self._skepticism_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[Skepticism] 持久化失败: {e}")

    # -----------------------------------------------------------------
    # 痛觉计算（供 AdaptiveUCTPruner 使用）
    # -----------------------------------------------------------------

    def compute_pain(self) -> float:
        """
        计算综合痛觉得分 [0.0, 1.0]

        综合以下维度：
        - w1: 怀疑缓存中的最大 deviation_weight
        - w2: 影子协议的失衡度
        - w3: 熔断器状态
        - w4: 硬件负载（API 超时率、系统负载、OOM 标记）

        Returns:
            [0.0, 1.0] 的痛觉得分
        """
        max_skepticism = 0.0
        for state in self._skepticism_cache.values():
            max_skepticism = max(max_skepticism, state.deviation_weight)

        shadow_balance = 0.5
        if hasattr(self._shadow, 'guardian_weight'):
            guardian = self._shadow.guardian_weight
            explorer = self._shadow.explorer_weight
            total = guardian + explorer
            if total > 0:
                shadow_balance = max(guardian, explorer) / total

        fuse_pain = 0.0
        if hasattr(self._fuse, 'status'):
            status = self._fuse.status
            if status.get('is_open', False):
                fuse_pain = 1.0
            else:
                fuse_pain = min(1.0, status.get('error_count', 0) / 5.0)

        hw_pain = self._hw_tracker.get_pain_score() if hasattr(self, '_hw_tracker') else 0.0

        pain = (
            max_skepticism * 0.35 +
            shadow_balance * 0.15 +
            fuse_pain * 0.30 +
            hw_pain * 0.20
        )
        return min(1.0, max(0.0, pain))

    # -----------------------------------------------------------------
    # 序列化
    # -----------------------------------------------------------------
    
    def to_dict(self) -> dict:
        return {
            "version": "2.0",
            "trace_count": len(self._trace),
            "favor_entities": list(self._ledger._favors.keys()),
            "shadow_state": {
                "guardian_weight": self._shadow.guardian_weight,
                "explorer_weight": self._shadow.explorer_weight,
                "last_adjustment": self._shadow.last_adjustment,
                "adjustment_reason": self._shadow.adjustment_reason,
            },
            "fuse_status": self._fuse.status,
            "divergence_stats": self._divergence.stats,
            "pain_score": round(self.compute_pain(), 3),
            "hw_tracker": self._hw_tracker.to_dict(),
            "dry_run": DRY_RUN,
            "enabled": ENABLE_AFFECT_ENGINE,
        }


# =============================================================================
# 便捷函数
# =============================================================================

_engine_instance: Optional[AffectEngine] = None

def get_affect_engine() -> AffectEngine:
    """获取感情引擎全局单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AffectEngine()
    return _engine_instance


def quick_affect(content: str) -> dict:
    """
    快速情感分析（不记录轨迹，纯计算）
    
    Returns:
        {"valence": float, "arousal": float, "category": str,
         "imprint_readiness": float, "safety_veto": bool}
    """
    engine = get_affect_engine()
    state = engine.compute(content)
    return {
        "valence": state.valence,
        "arousal": state.arousal,
        "category": state.category.name,
        "imprint_readiness": state.imprint_readiness,
        "safety_veto": state.safety_veto,
    }
