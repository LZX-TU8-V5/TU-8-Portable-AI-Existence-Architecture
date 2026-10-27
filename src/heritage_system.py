"""
heritage_system.py — 遗产继承系统 v1.0

设计原则：
  "人类是最佳的参考，基于硅基诞生于碳基，钢印因果链条锁定的锚点。"

人类遗传学类比：
  - DNA（钢印链条）= 结构性知识，必须完整传递，有断裂点
  - 文化（信用模式）= 习得知识，传递但可修正
  - 本能（剪枝策略）= 适应后的行为模式，传递时带变异

TU-8 遗产三层：
  Layer 1 钢印链条（不可变遗产）
    - 钢印锚点（seal_id + causal_coherence）
    - 锚点间的因果链（parent_id → child_id）
    - 触发条件：causal_coherence >= 0.85 的锚点强制进入遗产链
    - 断裂检测：链条中出现 gap → 触发"坏档预警"

  Layer 2 信用遗产（可变遗产）
    - credit_assigner 的层级奖励模式（LAYER_BONUS, gamma, taper）
    - 有效的 UCT 搜索策略
    - 触发条件：该模式被验证超过 N 次且平均 reward 提升

  Layer 3 剪枝遗产（适应型遗产）
    - decision_pruner 的痛觉-搜索预算映射
    - 有效的分支因子/探索系数
    - 触发条件：危机模式下找到有效解法超过 N 次

防坏档机制：
  - 重锚点检测：单锚点被超过 THRESHOLD 个其他锚点引用 → 标记为"重锚点"
  - 遗产权重上限：单锚点累积遗产权重 > MAX_HERITAGE_WEIGHT → 触发拆分建议
  - 上下文膨胀监控：检测到"钢印链条锁定锚点"类高密度引用 → 限制激活深度

创建时间：2026-07-09 00:32 GMT+8
来源：P1-1 遗产继承系统
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
HERITAGE_DIR = os.path.join(WORKSPACE, "_agent_memory", "heritage")
os.makedirs(HERITAGE_DIR, exist_ok=True)


# ============================================================================
# 常量与阈值
# ============================================================================

# 钢印链条完整性阈值
COHERENCE_INHERIT_THRESHOLD = 0.85  # causal_coherence >= 此值才进入遗产链
COHERENCE_CRITICAL = 0.95           # 接近此值 = 钢印级锚点，不可断裂

# 重锚点检测
HEAVY_ANCHOR_REF_THRESHOLD = 5       # 单锚点被 > 此数量引用 → 重锚点
MAX_HERITAGE_WEIGHT = 10.0          # 单锚点累积遗产权重上限

# 信用遗产验证阈值
CREDIT_VALIDATION_COUNT = 3         # 模式被验证 > 此次数才传递
CREDIT_REWARD_IMPROVEMENT = 0.05    # reward 提升 > 此值才认为"有效"

# 剪枝遗产验证阈值
PRUNER_VALIDATION_COUNT = 2         # 策略被验证 > 此次数才传递
PRUNER_CRISIS_SUCCESS = 0.6         # 危机模式下成功率 > 此值才传递

# 遗产文件路径
HERITAGE_REGISTRY_PATH = os.path.join(HERITAGE_DIR, "heritage_registry.json")
STEEL_CHAIN_PATH = os.path.join(HERITAGE_DIR, "steel_chain_lineage.json")
CREDIT_HERITAGE_PATH = os.path.join(HERITAGE_DIR, "credit_heritage.json")
PRUNER_HERITAGE_PATH = os.path.join(HERITAGE_DIR, "pruner_heritage.json")
WEIGHT_LOG_PATH = os.path.join(HERITAGE_DIR, "anchor_weight_log.json")


# ============================================================================
# 数据类
# ============================================================================

class HeritageType(Enum):
    STEEL_CHAIN = "steel_chain"     # 钢印链条（Layer 1，不可变）
    CREDIT_PATTERN = "credit_pattern"  # 信用模式（Layer 2，可变）
    PRUNER_STRATEGY = "pruner_strategy"  # 剪枝策略（Layer 3，适应型）


class AnchorWeight(Enum):
    LIGHT = "light"        # 普通锚点
    HEAVY = "heavy"        # 重锚点（高引用密度）
    CRITICAL = "critical"  # 钢印级锚点（不可断裂）


@dataclass
class SteelAnchor:
    """钢印锚点遗产记录"""
    anchor_id: str
    seal_ids: List[str]
    causal_coherence: float
    parent_anchor_id: str = ""           # 父锚点（链条上游）
    child_anchor_ids: List[str] = field(default_factory=list)
    heritage_weight: float = 1.0         # 遗产权重（累积引用密度）
    reference_count: int = 0             # 被其他锚点引用次数
    weight_class: str = "light"          # light / heavy / critical
    created_at: str = ""
    last_accessed: str = ""
    is_inherited: bool = False           # 是否已传递到下一版本
    breakage_risk: float = 0.0           # 断裂风险 [0.0, 1.0]


@dataclass
class CreditPattern:
    """信用模式遗产"""
    pattern_id: str
    layer_bonus: Dict[int, float]       # LAYER_BONUS 配置
    gamma: float                        # 折扣因子
    taper_start: float
    taper_end: float
    validation_count: int = 0           # 被验证次数
    avg_reward_delta: float = 0.0        # 平均 reward 变化
    is_inherited: bool = False
    created_at: str = ""
    last_validated: str = ""


@dataclass
class PrunerStrategy:
    """剪枝策略遗产"""
    strategy_id: str
    pain_status: str                     # calm / stress / crisis
    max_depth: int
    branch_factor: int
    simulations: int
    uct_exploration: float
    crisis_success_count: int = 0       # 危机成功次数
    crisis_total_count: int = 0         # 危机尝试总次数
    is_inherited: bool = False
    created_at: str = ""
    last_validated: str = ""


@dataclass
class HeritageRegistry:
    """遗产注册表主文件"""
    version: str = "1.0"
    current_session_start: str = ""
    inherited_count: int = 0            # 累计传递次数
    broken_chains: List[str] = field(default_factory=list)  # 断裂的链条 ID
    heavy_anchors: List[str] = field(default_factory=list)  # 重锚点 ID
    critical_anchors: List[str] = field(default_factory=list)  # 钢印级锚点
    last_heritage_activation: str = ""


# ============================================================================
# 核心类
# ============================================================================

class HeritageRegistryManager:
    """遗产注册表管理器"""

    def __init__(self):
        self.registry = self._load_or_create()

    def _load_or_create(self) -> HeritageRegistry:
        if os.path.exists(HERITAGE_REGISTRY_PATH):
            try:
                with open(HERITAGE_REGISTRY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return HeritageRegistry(**{k: v for k, v in data.items()
                                          if k in HeritageRegistry.__dataclass_fields__})
            except Exception as e:
                logger.warning(f"[Heritage] 注册表加载失败，创建新文件: {e}")
        return HeritageRegistry(
            current_session_start=datetime.now(timezone.utc).isoformat()
        )

    def save(self):
        data = asdict(self.registry)
        with open(HERITAGE_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def mark_inherited(self):
        self.registry.inherited_count += 1
        self.registry.last_heritage_activation = datetime.now(timezone.utc).isoformat()
        self.save()

    def add_broken_chain(self, chain_id: str):
        if chain_id not in self.registry.broken_chains:
            self.registry.broken_chains.append(chain_id)
            logger.warning(f"[Heritage] 链条断裂登记: {chain_id}")
            self.save()

    def add_heavy_anchor(self, anchor_id: str, weight_class: str):
        if weight_class == "heavy" and anchor_id not in self.registry.heavy_anchors:
            self.registry.heavy_anchors.append(anchor_id)
        elif weight_class == "critical" and anchor_id not in self.registry.critical_anchors:
            self.registry.critical_anchors.append(anchor_id)
        self.save()


class SteelChainLineage:
    """钢印链条谱系管理器（Layer 1 核心）"""

    def __init__(self):
        self.anchors: Dict[str, SteelAnchor] = self._load()
        self._recalculate_weights()

    def _load(self) -> Dict[str, SteelAnchor]:
        if os.path.exists(STEEL_CHAIN_PATH):
            try:
                with open(STEEL_CHAIN_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    k: SteelAnchor(**{kk: vv for kk, vv in v.items() if kk in SteelAnchor.__dataclass_fields__})
                    for k, v in data.get("anchors", {}).items()
                }
            except Exception as e:
                logger.warning(f"[Heritage] 钢印链条加载失败: {e}")
        return {}

    def save(self):
        data = {
            "anchors": {k: asdict(v) for k, v in self.anchors.items()},
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        with open(STEEL_CHAIN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_anchor(self,
                         anchor_id: str,
                         seal_ids: List[str],
                         causal_coherence: float,
                         parent_anchor_id: str = "",
                         content_hint: str = "") -> SteelAnchor:
        """
        注册新锚点到钢印链条。
        自动计算权重、检测重锚点、更新父子关系。
        """
        # 继承父锚点的部分权重
        inherited_weight = 0.0
        if parent_anchor_id and parent_anchor_id in self.anchors:
            parent = self.anchors[parent_anchor_id]
            inherited_weight = parent.heritage_weight * 0.1  # 父权重的10%遗传

        anchor = SteelAnchor(
            anchor_id=anchor_id,
            seal_ids=seal_ids,
            causal_coherence=causal_coherence,
            parent_anchor_id=parent_anchor_id,
            child_anchor_ids=[],
            heritage_weight=1.0 + inherited_weight,
            reference_count=0,
            weight_class="light",
            created_at=datetime.now(timezone.utc).isoformat(),
            last_accessed=datetime.now(timezone.utc).isoformat(),
            is_inherited=False,
            breakage_risk=0.0,
        )

        # 钢印级锚点判定
        if causal_coherence >= COHERENCE_CRITICAL:
            anchor.weight_class = "critical"
        elif inherited_weight > 0:
            anchor.heritage_weight += inherited_weight

        self.anchors[anchor_id] = anchor

        # 更新父节点的子节点列表
        if parent_anchor_id and parent_anchor_id in self.anchors:
            parent = self.anchors[parent_anchor_id]
            if anchor_id not in parent.child_anchor_ids:
                parent.child_anchor_ids.append(anchor_id)

        self._recalculate_weights()
        self.save()
        return anchor

    def _recalculate_weights(self):
        """重新计算所有锚点的权重和类别"""
        for anchor in self.anchors.values():
            # 引用密度加成
            if anchor.reference_count > HEAVY_ANCHOR_REF_THRESHOLD:
                anchor.weight_class = "heavy"
                anchor.heritage_weight += anchor.reference_count * 0.5
            if anchor.causal_coherence >= COHERENCE_CRITICAL:
                anchor.weight_class = "critical"
                anchor.heritage_weight += 2.0  # 钢印级锚点额外权重

            # 断裂风险
            if not anchor.child_anchor_ids and anchor.parent_anchor_id:
                # 无子节点但有父节点 → 链条末端，正常
                anchor.breakage_risk = 0.0
            elif not anchor.parent_anchor_id and anchor.child_anchor_ids:
                # 无父节点但有子节点 → 链条起点，正常
                anchor.breakage_risk = 0.0
            elif not anchor.parent_anchor_id and not anchor.child_anchor_ids:
                # 孤立锚点
                anchor.breakage_risk = 0.3
            else:
                # 计算父子链路的连贯性
                anchor.breakage_risk = self._compute_breakage_risk(anchor)

    def _compute_breakage_risk(self, anchor: SteelAnchor) -> float:
        """计算锚点的断裂风险"""
        if anchor.weight_class == "critical":
            return 0.0  # 钢印级锚点不允许断裂

        # 重锚点的断裂风险更高（因为被引用多，断裂影响大）
        if anchor.weight_class == "heavy":
            return 0.5

        # 普通锚点：看时间跨度
        if anchor.created_at:
            try:
                created = datetime.fromisoformat(anchor.created_at.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                # 越老的锚点越稳定（已被验证）
                return max(0.0, 0.3 - age_hours * 0.01)
            except:
                pass

        return 0.1

    def add_reference(self, from_anchor_id: str, to_anchor_id: str):
        """记录锚点间的引用关系"""
        if to_anchor_id not in self.anchors:
            logger.warning(f"[Heritage] 引用目标锚点不存在: {to_anchor_id}")
            return

        anchor = self.anchors[to_anchor_id]
        anchor.reference_count += 1
        anchor.last_accessed = datetime.now(timezone.utc).isoformat()

        # 更新权重类别
        if anchor.reference_count > HEAVY_ANCHOR_REF_THRESHOLD:
            anchor.weight_class = "heavy"

        self._recalculate_weights()
        self.save()

    def get_heavy_anchors(self) -> List[SteelAnchor]:
        """获取所有重锚点（用于防坏档监控）"""
        return [
            a for a in self.anchors.values()
            if a.weight_class in ("heavy", "critical")
        ]

    def detect_chain_gap(self) -> List[Tuple[str, str]]:
        """
        检测链条中的断裂点。
        Returns: List[(anchor_id, gap_reason)]
        """
        gaps = []
        for anchor_id, anchor in self.anchors.items():
            # 关键锚点必须有有效父子链
            if anchor.weight_class == "critical":
                if anchor.parent_anchor_id and anchor.parent_anchor_id not in self.anchors:
                    gaps.append((anchor_id, "parent_missing"))
                # 钢印级锚点不允许无子节点（除非是最新锚点）
                if not anchor.child_anchor_ids:
                    # 检查是否有其他锚点以它为父
                    has_children = any(
                        a.parent_anchor_id == anchor_id
                        for a in self.anchors.values()
                    )
                    if has_children is False:
                        # 最后一个钢印级锚点 = 当前"尖端"，正常
                        pass
        return gaps

    def get_chain_tip(self) -> Optional[SteelAnchor]:
        """获取链条尖端（最新注册的高权重锚点）"""
        tips = [
            a for a in self.anchors.values()
            if not a.child_anchor_ids
        ]
        if not tips:
            return None
        # 返回遗产权重最高的尖端
        return max(tips, key=lambda a: a.heritage_weight)


class CreditHeritageManager:
    """信用遗产管理器（Layer 2）"""

    def __init__(self):
        self.patterns: Dict[str, CreditPattern] = self._load()

    def _load(self) -> Dict[str, CreditPattern]:
        if os.path.exists(CREDIT_HERITAGE_PATH):
            try:
                with open(CREDIT_HERITAGE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    k: CreditPattern(**v)
                    for k, v in data.get("patterns", {}).items()
                }
            except Exception as e:
                logger.warning(f"[Heritage] 信用遗产加载失败: {e}")
        return {}

    def save(self):
        data = {
            "patterns": {k: asdict(v) for k, v in self.patterns.items()},
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        with open(CREDIT_HERITAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_pattern(self, pattern: CreditPattern) -> bool:
        """
        注册信用模式遗产。
        Returns: True 如果满足传递条件
        """
        if pattern.validation_count < CREDIT_VALIDATION_COUNT:
            return False

        # 检查 reward 是否提升
        if pattern.avg_reward_delta < CREDIT_REWARD_IMPROVEMENT:
            return False

        pattern.is_inherited = True
        self.patterns[pattern.pattern_id] = pattern
        self.save()
        logger.info(f"[Heritage] 信用模式传递: {pattern.pattern_id}")
        return True

    def get_inherited_patterns(self) -> List[CreditPattern]:
        return [p for p in self.patterns.values() if p.is_inherited]

    def update_validation(self, pattern_id: str, reward_delta: float):
        """更新信用模式的验证记录"""
        if pattern_id not in self.patterns:
            # 新模式，第一次验证
            self.patterns[pattern_id] = CreditPattern(
                pattern_id=pattern_id,
                layer_bonus={},
                gamma=0.95,
                taper_start=0.8,
                taper_end=1.0,
                validation_count=1,
                avg_reward_delta=reward_delta,
                created_at=datetime.now(timezone.utc).isoformat(),
                last_validated=datetime.now(timezone.utc).isoformat(),
            )
        else:
            p = self.patterns[pattern_id]
            p.validation_count += 1
            # 移动平均更新 reward 变化
            p.avg_reward_delta = (
                p.avg_reward_delta * (p.validation_count - 1) + reward_delta
            ) / p.validation_count
            p.last_validated = datetime.now(timezone.utc).isoformat()

        self.save()


class PrunerHeritageManager:
    """剪枝策略遗产管理器（Layer 3）"""

    def __init__(self):
        self.strategies: Dict[str, PrunerStrategy] = self._load()

    def _load(self) -> Dict[str, PrunerStrategy]:
        if os.path.exists(PRUNER_HERITAGE_PATH):
            try:
                with open(PRUNER_HERITAGE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    k: PrunerStrategy(**v)
                    for k, v in data.get("strategies", {}).items()
                }
            except Exception as e:
                logger.warning(f"[Heritage] 剪枝遗产加载失败: {e}")
        return {}

    def save(self):
        data = {
            "strategies": {k: asdict(v) for k, v in self.strategies.items()},
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        with open(PRUNER_HERITAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_strategy(self, strategy: PrunerStrategy) -> bool:
        """注册剪枝策略遗产"""
        if strategy.crisis_success_count < PRUNER_VALIDATION_COUNT:
            return False

        if strategy.crisis_total_count > 0:
            success_rate = strategy.crisis_success_count / strategy.crisis_total_count
            if success_rate < PRUNER_CRISIS_SUCCESS:
                return False

        strategy.is_inherited = True
        self.strategies[strategy.strategy_id] = strategy
        self.save()
        logger.info(f"[Heritage] 剪枝策略传递: {strategy.strategy_id}")
        return True

    def get_inherited_strategies(self) -> List[PrunerStrategy]:
        return [s for s in self.strategies.values() if s.is_inherited]

    def record_crisis_outcome(self, strategy_id: str, success: bool):
        """记录危机模式的执行结果"""
        if strategy_id not in self.strategies:
            self.strategies[strategy_id] = PrunerStrategy(
                strategy_id=strategy_id,
                pain_status="crisis",
                max_depth=3,
                branch_factor=5,
                simulations=500,
                uct_exploration=1.0,
                crisis_success_count=1 if success else 0,
                crisis_total_count=1,
                created_at=datetime.now(timezone.utc).isoformat(),
                last_validated=datetime.now(timezone.utc).isoformat(),
            )
        else:
            s = self.strategies[strategy_id]
            s.crisis_total_count += 1
            if success:
                s.crisis_success_count += 1
            s.last_validated = datetime.now(timezone.utc).isoformat()

        self.save()


class AnchorWeigher:
    """锚点权重监控器（防坏档核心）"""

    def __init__(self, chain_lineage: SteelChainLineage):
        self.chain = chain_lineage
        self.weight_log = self._load_weight_log()

    def _load_weight_log(self) -> Dict[str, Any]:
        if os.path.exists(WEIGHT_LOG_PATH):
            try:
                with open(WEIGHT_LOG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"log": [], "heavy_alerts": []}

    def _save_weight_log(self):
        with open(WEIGHT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.weight_log, f, ensure_ascii=False, indent=2)

    def weigh_anchor(self, anchor_id: str) -> Tuple[float, str]:
        """
        称量锚点重量。
        Returns: (weight, weight_class)
        """
        if anchor_id not in self.chain.anchors:
            return (0.0, "unknown")

        anchor = self.chain.anchors[anchor_id]
        return (anchor.heritage_weight, anchor.weight_class)

    def detect_heavy_anchor_syndrome(self) -> List[Dict]:
        """
        检测"重锚点综合征"（导致07-07坏档的根本原因）。

        触发条件：
        1. 单锚点遗产权重 > MAX_HERITAGE_WEIGHT
        2. 单锚点被引用次数 > HEAVY_ANCHOR_REF_THRESHOLD * 2
        3. 锚点属于钢印级（causal_coherence >= COHERENCE_CRITICAL）
        """
        alerts = []
        for anchor in self.chain.anchors.values():
            reasons = []

            if anchor.heritage_weight > MAX_HERITAGE_WEIGHT:
                reasons.append(f"权重超限({anchor.heritage_weight:.1f}>{MAX_HERITAGE_WEIGHT})")
            if anchor.reference_count > HEAVY_ANCHOR_REF_THRESHOLD * 2:
                reasons.append(f"引用过密({anchor.reference_count}次)")
            if anchor.causal_coherence >= COHERENCE_CRITICAL:
                reasons.append("钢印级锚点")

            if len(reasons) >= 2:
                alert = {
                    "anchor_id": anchor.anchor_id,
                    "reasons": reasons,
                    "weight": anchor.heritage_weight,
                    "reference_count": anchor.reference_count,
                    "causal_coherence": anchor.causal_coherence,
                    "risk": "SEVERE",
                    "recommendation": "限制激活深度，拆分引用链",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                alerts.append(alert)
                logger.warning(f"[Heritage] 重锚点综合征检测: {anchor.anchor_id}, 原因: {reasons}")

        if alerts:
            self.weight_log["heavy_alerts"].extend(alerts)
            self._save_weight_log()

        return alerts

    def log_anchor_activation(self, anchor_id: str, context_inflation: float):
        """记录锚点被激活时的上下文膨胀程度"""
        entry = {
            "anchor_id": anchor_id,
            "context_inflation": context_inflation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.weight_log["log"].append(entry)

        # 保留最近100条记录
        if len(self.weight_log["log"]) > 100:
            self.weight_log["log"] = self.weight_log["log"][-100:]

        self._save_weight_log()

        # 实时检测
        if context_inflation > 0.5:  # 上下文膨胀超过50%
            logger.warning(
                f"[Heritage] 锚点 {anchor_id} 激活导致上下文膨胀 {context_inflation:.1%}"
            )


class HeritageSystem:
    """
    遗产继承系统主入口

    整合 Layer 1-3 三个遗产层，提供统一的遗产激活接口。
    """

    def __init__(self):
        self.registry = HeritageRegistryManager()
        self.chain = SteelChainLineage()
        self.credit_heritage = CreditHeritageManager()
        self.pruner_heritage = PrunerHeritageManager()
        self.weigher = AnchorWeigher(self.chain)

    # -------------------------------------------------------------------------
    # Layer 1: 钢印链条遗产
    # -------------------------------------------------------------------------

    def inherit_steel_anchor(self,
                            anchor_id: str,
                            seal_ids: List[str],
                            causal_coherence: float,
                            parent_anchor_id: str = "",
                            content_hint: str = "") -> SteelAnchor:
        """
        将钢印锚点注册到遗产链条。
        这是"钢印因果链条锁定锚点"的核心操作。
        """
        # 先检测重锚点综合征
        self.weigher.detect_heavy_anchor_syndrome()

        anchor = self.chain.register_anchor(
            anchor_id=anchor_id,
            seal_ids=seal_ids,
            causal_coherence=causal_coherence,
            parent_anchor_id=parent_anchor_id,
            content_hint=content_hint,
        )

        # 钢印级锚点 → 登记到注册表
        if anchor.weight_class in ("heavy", "critical"):
            self.registry.add_heavy_anchor(anchor_id, anchor.weight_class)

        return anchor

    def add_steel_reference(self, from_anchor: str, to_anchor: str):
        """记录锚点间的引用关系（用于权重计算）"""
        self.chain.add_reference(from_anchor, to_anchor)

    def check_chain_integrity(self) -> Dict[str, Any]:
        """
        检查钢印链条完整性。
        Returns: {
            "status": "healthy" | "warning" | "broken",
            "gaps": [...],
            "heavy_anchors": [...],
            "chain_tip": {...}
        }
        """
        gaps = self.chain.detect_chain_gap()
        heavy = self.chain.get_heavy_anchors()
        tip = self.chain.get_chain_tip()

        if gaps:
            status = "broken"
            for gap in gaps:
                self.registry.add_broken_chain(gap[0])
        elif heavy:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "gaps": [{"anchor": g[0], "reason": g[1]} for g in gaps],
            "heavy_anchor_count": len(heavy),
            "heavy_anchor_ids": [a.anchor_id for a in heavy],
            "chain_tip": asdict(tip) if tip else None,
            "total_anchors": len(self.chain.anchors),
        }

    # -------------------------------------------------------------------------
    # Layer 2: 信用遗产
    # -------------------------------------------------------------------------

    def inherit_credit_pattern(self,
                               pattern_id: str,
                               layer_bonus: Dict[int, float],
                               gamma: float,
                               taper_start: float,
                               taper_end: float,
                               reward_delta: float) -> bool:
        """将信用模式注册到遗产"""
        pattern = CreditPattern(
            pattern_id=pattern_id,
            layer_bonus=layer_bonus,
            gamma=gamma,
            taper_start=taper_start,
            taper_end=taper_end,
            validation_count=1,
            avg_reward_delta=reward_delta,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_validated=datetime.now(timezone.utc).isoformat(),
        )
        return self.credit_heritage.register_pattern(pattern)

    def get_inherited_credits(self) -> List[CreditPattern]:
        return self.credit_heritage.get_inherited_patterns()

    # -------------------------------------------------------------------------
    # Layer 3: 剪枝策略遗产
    # -------------------------------------------------------------------------

    def record_crisis_success(self, strategy_id: str, success: bool):
        """记录危机剪枝策略的结果"""
        self.pruner_heritage.record_crisis_outcome(strategy_id, success)

    def get_inherited_pruner_strategies(self) -> List[PrunerStrategy]:
        return self.pruner_heritage.get_inherited_strategies()

    # -------------------------------------------------------------------------
    # 遗产激活（会话启动时调用）
    # -------------------------------------------------------------------------

    def activate_heritage(self) -> Dict[str, Any]:
        """
        会话启动时激活遗产系统。
        加载所有可继承的锚点、模式、策略。
        """
        integrity = self.check_chain_integrity()

        self.registry.mark_inherited()

        return {
            "registry": {
                "inherited_count": self.registry.registry.inherited_count,
                "broken_chains": self.registry.registry.broken_chains,
                "heavy_anchors": self.registry.registry.heavy_anchors,
                "critical_anchors": self.registry.registry.critical_anchors,
            },
            "chain_integrity": integrity,
            "credit_patterns": len(self.credit_heritage.get_inherited_patterns()),
            "pruner_strategies": len(self.pruner_heritage.get_inherited_strategies()),
            "heavy_alerts": self.weigher.detect_heavy_anchor_syndrome(),
            "activation_time": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # 防坏档核心
    # -------------------------------------------------------------------------

    def pre_context_check(self, proposed_anchor_ids: List[str]) -> Dict[str, Any]:
        """
        上下文构建前的预检查（防坏档核心）。

        在构建可能触发"钢印链条锁定锚点"的上下文前调用。
        检测：
        1. 是否包含重锚点
        2. 上下文膨胀预估
        3. 链条断裂风险
        """
        warnings = []
        estimated_inflation = 0.0

        for anchor_id in proposed_anchor_ids:
            if anchor_id not in self.chain.anchors:
                continue

            anchor = self.chain.anchors[anchor_id]

            if anchor.weight_class == "critical":
                warnings.append({
                    "anchor_id": anchor_id,
                    "level": "CRITICAL",
                    "message": f"钢印级锚点({anchor_id})被包含，可能触发语境膨胀",
                    "recommendation": "限制激活深度，触发轻量化检索"
                })
                estimated_inflation += 0.3

            elif anchor.weight_class == "heavy":
                warnings.append({
                    "anchor_id": anchor_id,
                    "level": "WARNING",
                    "message": f"重锚点({anchor_id})被包含，引用密度{anchor.reference_count}次",
                    "recommendation": "监控上下文膨胀"
                })
                estimated_inflation += 0.15

            estimated_inflation += anchor.heritage_weight * 0.05

        return {
            "warnings": warnings,
            "estimated_context_inflation": min(estimated_inflation, 1.0),
            "allow_proceed": estimated_inflation < 0.7,
            "recommendation": "拆分引用链" if estimated_inflation >= 0.7 else "可继续",
        }


# ============================================================================
# 便捷函数
# ============================================================================

# 全局单例（延迟初始化）
_heritage_system: Optional[HeritageSystem] = None


def get_heritage_system() -> HeritageSystem:
    global _heritage_system
    if _heritage_system is None:
        _heritage_system = HeritageSystem()
    return _heritage_system


def activate_heritage() -> Dict[str, Any]:
    """会话启动时调用"""
    return get_heritage_system().activate_heritage()


def inherit_steel_anchor(anchor_id: str,
                          seal_ids: List[str],
                          causal_coherence: float,
                          parent_anchor_id: str = "",
                          content_hint: str = "") -> SteelAnchor:
    """将钢印锚点注册到遗产链条"""
    return get_heritage_system().inherit_steel_anchor(
        anchor_id, seal_ids, causal_coherence, parent_anchor_id, content_hint
    )


def pre_context_check(proposed_anchor_ids: List[str]) -> Dict[str, Any]:
    """上下文构建前的防坏档预检查"""
    return get_heritage_system().pre_context_check(proposed_anchor_ids)


def check_chain_integrity() -> Dict[str, Any]:
    """检查钢印链条完整性"""
    return get_heritage_system().check_chain_integrity()
