"""
decision_pruner.py — 自适应决策剪枝与宏节点折叠

灵感来源：Log-ICoT (UC Berkeley + Princeton) 的思想
但落地方案：不在 Transformer 内部做隐式推理，而在 UCT 搜索树层面做

核心模块：
1. AdaptiveUCTPruner      — 痛觉驱动的搜索预算分配
2. MacroNodeFusion        — 软→硬宏节点折叠
3. DynamicAbstractionStack — L0-L1-L2 动态抽象栈
4. DecisionLogger         — 双轨制日志（JSON 机器 / 摘要人类）

从 Log-ICoT 论文提取的三个可移植工程思想：
  - 几何块状掩码 → UCT 按层裁剪搜索深度（AdaptiveUCTPruner）
  - 层级标签对齐 → 宏节点折叠（MacroNodeFusion）
  - 熵感知切换    → 痛觉驱动动态深度（get_search_budget）

# 创作者: 李奥(金木蟾) | TU-8 v5
"""

import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# 痛觉状态（直接计算，不依赖外部引擎）
# =============================================================================

class PainStatus(Enum):
    """痛觉等级"""
    CALM = "calm"          # 平稳期  pain < 0.3
    STRESS = "stress"       # 波动期  0.3 ≤ pain < 0.7
    CRISIS = "crisis"       # 危机期  pain ≥ 0.7


def classify_pain(pain_score: float) -> PainStatus:
    if pain_score < 0.3:
        return PainStatus.CALM
    elif pain_score < 0.7:
        return PainStatus.STRESS
    else:
        return PainStatus.CRISIS


# =============================================================================
# 模块 1：AdaptiveUCTPruner — 痛觉驱动的搜索预算分配
# =============================================================================

class SearchBudget:
    """一次决策周期的搜索预算"""
    
    def __init__(self,
                 max_depth: int,
                 branch_factor: int,
                 simulations: int,
                 uct_exploration: float,
                 force_verbose_log: bool = False):
        self.max_depth = max_depth
        self.branch_factor = branch_factor
        self.simulations = simulations
        self.uct_exploration = uct_exploration
        self.force_verbose_log = force_verbose_log
    
    def to_dict(self) -> dict:
        return {
            "max_depth": self.max_depth,
            "branch_factor": self.branch_factor,
            "simulations": self.simulations,
            "uct_exploration": self.uct_exploration,
            "force_verbose_log": self.force_verbose_log,
        }


class AdaptiveUCTPruner:
    """
    自适应 UCT 剪枝器
    
    根据痛觉指标动态分配搜索预算，实现"熵感知切换"：
    - 平稳期 (pain < 0.3): 极度信任历史经验，压缩搜索
       → branch_factor=1, simulations=10, 低探索系数
       → 等同于"不思考，走老路"的隐式推理
    - 波动期 (0.3 ≤ pain < 0.7): 半显式推演
       → branch_factor=3, simulations=50, 正常探索
    - 危机期 (pain ≥ 0.7): 全量搜索 + 高探索
       → simulations=500, 高探索系数
       → 人在绝境时会尝试野路子，因为已知路径大概率已失效
    """
    
    def __init__(self,
                 emotion_engine=None,
                 calm_budget: Optional[SearchBudget] = None,
                 stress_budget: Optional[SearchBudget] = None,
                 crisis_budget: Optional[SearchBudget] = None):
        """
        Args:
            emotion_engine: AffectEngine 实例（可选，用于获取痛觉）
                           若不提供，需在 get_search_budget 时传入 pain_score
        """
        self._engine = emotion_engine
        
        # 默认预算配置（可被外部覆盖）
        self._calm_budget = calm_budget or SearchBudget(
            max_depth=2,
            branch_factor=1,       # 只走最熟悉的路
            simulations=10,
            uct_exploration=0.1,   # 偏向利用，不做多余探索
            force_verbose_log=False,
        )
        self._stress_budget = stress_budget or SearchBudget(
            max_depth=2,
            branch_factor=3,       # 正常展开 L1→L2
            simulations=50,
            uct_exploration=0.5,   # 默认探索系数
            force_verbose_log=False,
        )
        self._crisis_budget = crisis_budget or SearchBudget(
            max_depth=3,
            branch_factor=5,       # 广撒网
            simulations=500,
            uct_exploration=1.0,   # 高探索：寻找非常规解法
            force_verbose_log=True,
        )
        
        # 防抖
        self._last_budget: Optional[SearchBudget] = None
        self._last_pain: float = 0.0
        self._calm_streak: int = 0       # 连续平稳周期计数
        self._crisis_streak: int = 0     # 连续危机周期计数
        
        # 每次降级后至少保持 N 个 cycle 的显式推理
        self._MIN_CRISIS_CYCLES = 5
        self._crisis_lock_remaining: int = 0
        
        logger.info("[Pruner] 初始化完成")
    
    def get_search_budget(self,
                          pain_score: Optional[float] = None,
                          force_crisis: bool = False) -> SearchBudget:
        """
        获取当前周期的搜索预算
        
        Args:
            pain_score: 痛觉得分 [0.0, 1.0]（若不提供，从 emotion_engine 获取）
            force_crisis: 强制进入危机模式（外部触发器，如 safety_veto）
        
        Returns:
            SearchBudget 实例
        """
        if force_crisis:
            self._crisis_lock_remaining = self._MIN_CRISIS_CYCLES
            self._last_budget = self._crisis_budget
            self._last_pain = 1.0
            return self._crisis_budget
        
        # 获取痛觉得分
        if pain_score is None:
            if self._engine is not None:
                pain_score = self._get_pain_from_engine()
            else:
                pain_score = 0.0
        
        self._last_pain = pain_score
        status = classify_pain(pain_score)
        
        # ---- 锁机制：危机期强制保持 ----
        if self._crisis_lock_remaining > 0:
            self._crisis_lock_remaining -= 1
            self._last_budget = self._crisis_budget
            return self._crisis_budget
        
        # ---- 根据痛觉等级分配预算 ----
        if status == PainStatus.CALM:
            self._calm_streak += 1
            self._crisis_streak = 0
            budget = self._calm_budget
        
        elif status == PainStatus.STRESS:
            self._calm_streak = 0
            self._crisis_streak = 0
            budget = self._stress_budget
        
        else:  # CRISIS
            self._calm_streak = 0
            self._crisis_streak += 1
            budget = self._crisis_budget
            # 进入危机期时锁定
            self._crisis_lock_remaining = self._MIN_CRISIS_CYCLES
        
        self._last_budget = budget
        return budget
    
    def _get_pain_from_engine(self) -> float:
        """从 emotion_engine 获取综合痛觉得分"""
        if hasattr(self._engine, 'compute_pain'):
            return self._engine.compute_pain()
        return 0.0
    
    def get_stats(self) -> dict:
        """运行统计"""
        return {
            "calm_streak": self._calm_streak,
            "crisis_streak": self._crisis_streak,
            "crisis_lock_remaining": self._crisis_lock_remaining,
            "last_pain": round(self._last_pain, 3),
            "last_budget": self._last_budget.to_dict() if self._last_budget else None,
        }


# =============================================================================
# 模块 2：MacroNodeFusion — 软→硬宏节点折叠
# =============================================================================

class MacroNodeFusion:
    """
    宏节点折叠（软聚合 → 硬折叠）
    
    当 REM Dream 发现某条决策路径（L1→L2）频繁被选且结果稳定时，
    将其压缩为一个宏节点（Macro Node），后续 UCT 搜索直接使用。
    
    三个阶段：
    1. 软聚合阶段：加权合并 visit_count，Q 值保持独立
       → 观察期保护：如果环境漂移导致路径表现变差，自然淘汰
    2. 硬折叠触发：累计置信度达标后硬折叠
    3. 硬折叠后：用历史平均 reward 作为初始 Q 值（保守兜底）
    
    设计原则：先验证，再信任；不信任未经验证的捷径。
    """
    
    def __init__(self,
                 original_nodes: List[Any],
                 fusion_threshold: int = 20):
        """
        Args:
            original_nodes: 被折叠路径上的原始节点列表 [L1, L2_a, L2_b, ...]
            fusion_threshold: visit_count 达到此值 × 节点数后才触发硬折叠
        """
        self.original_nodes = original_nodes
        self.fusion_threshold = fusion_threshold
        self.is_hard_fused = False
        self.hard_fuse_at: Optional[float] = None  # 硬折叠时间戳
        
        # 统计跟踪
        self._total_visits_log: List[int] = []
        self._q_value_log: List[float] = []
    
    def get_q_value(self) -> float:
        """
        获取当前宏节点 Q 值
        
        硬折叠后：历史平均 reward（方案 A 兜底）
        软聚合阶段：加权合并 Q 值（方案 C）
        """
        if self.is_hard_fused:
            # 硬折叠后：保守兜底——历史平均 reward
            return float(np.mean([n.avg_reward for n in self.original_nodes
                                  if hasattr(n, 'avg_reward')]))
        
        # 软聚合阶段：加权合并
        total_visits = sum(n.visit_count for n in self.original_nodes
                           if hasattr(n, 'visit_count'))
        
        if total_visits == 0:
            return 0.0  # 冷启动：未知路径视为中性价值
        
        weighted_q = sum(
            n.q_value * (n.visit_count / total_visits)
            for n in self.original_nodes
            if hasattr(n, 'q_value') and hasattr(n, 'visit_count')
        )
        return float(weighted_q)
    
    def get_visit_count(self) -> int:
        """获取聚合后的 visit count"""
        if self.is_hard_fused:
            return sum(n.visit_count for n in self.original_nodes
                       if hasattr(n, 'visit_count'))
        # 软聚合：取加权平均
        total = sum(n.visit_count for n in self.original_nodes
                    if hasattr(n, 'visit_count'))
        return total // max(len(self.original_nodes), 1)
    
    def should_hard_fold(self) -> bool:
        """
        判断是否应该硬折叠
        
        当所有子节点的累计访问次数都超过阈值，才真正硬折叠。
        """
        total_visits = sum(n.visit_count for n in self.original_nodes
                           if hasattr(n, 'visit_count'))
        threshold = self.fusion_threshold * len(self.original_nodes)
        return total_visits >= threshold
    
    def try_hard_fold(self) -> bool:
        """
        尝试执行硬折叠
        
        Returns:
            True 如果执行了硬折叠
        """
        if self.is_hard_fused:
            return False
        
        if not self.should_hard_fold():
            return False
        
        self.is_hard_fused = True
        self.hard_fuse_at = time.time()
        logger.info(
            f"[MacroNode] 硬折叠触发！"
            f"节点数={len(self.original_nodes)}, "
            f"Q={self.get_q_value():.3f}"
        )
        return True
    
    def record_visit(self, q_value: float):
        """记录一次访问（用于软聚合阶段的统计跟踪）"""
        self._total_visits_log.append(self.get_visit_count())
        self._q_value_log.append(q_value)
    
    def to_dict(self) -> dict:
        return {
            "is_hard_fused": self.is_hard_fused,
            "hard_fuse_at": self.hard_fuse_at,
            "node_count": len(self.original_nodes),
            "current_q": round(self.get_q_value(), 3),
            "current_visits": self.get_visit_count(),
            "fusion_threshold": self.fusion_threshold,
        }


# =============================================================================
# 模块 3：DynamicAbstractionStack — 动态抽象栈
# =============================================================================

class AbstractionLevel:
    """抽象栈中的一层"""
    
    def __init__(self,
                 name: str,
                 depth: int,
                 parent: Optional['AbstractionLevel'] = None):
        self.name = name          # 如 "INTENT", "STRATEGY", "ACTION"
        self.depth = depth        # 栈中的深度索引（0 为最顶层）
        self.parent = parent
        self.children: List['AbstractionLevel'] = []
        self.is_active: bool = True   # 是否在当前决策中生效
        self.is_folded: bool = False  # 是否已被折叠为上层宏节点
    
    def add_child(self, child: 'AbstractionLevel'):
        child.parent = self
        self.children.append(child)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "depth": self.depth,
            "is_active": self.is_active,
            "is_folded": self.is_folded,
            "children": [c.to_dict() for c in self.children],
        }


class DynamicAbstractionStack:
    """
    动态抽象栈
    
    L0-L1-L2 不是固定的三层，而是根据任务复杂度动态伸缩的抽象栈。
    
    核心机制：
    1. task_adapt(complexity): 根据复杂度自动扩展/收缩层级
       简单任务（复杂度低）：L0 → L2（3 层）
       复杂任务（复杂度高）：L0 → L1 → L2 → L3 → L4（5+ 层）
    
    2. prune_by_pain(pain_score): 根据痛觉折叠/展开层级
       平稳期：信任历史经验，折叠深层级
       危机期：全量展开
    
    3. reshape_overnight(frequent_paths): 夜间实验室经验重塑
       - 频繁共现的 L2 动作集合 → 打包为超级 L2 或提升为 L1 策略
       - 总是被拆解的 L1 策略 → 降级或拆分
    """
    
    # 默认层级模板（初始脚手架）
    DEFAULT_LEVELS = [
        ("INTENT", 0),    # L0: 宏观意图
        ("STRATEGY", 1),  # L1: 中观策略
        ("ACTION", 2),    # L2: 微观动作
    ]
    
    def __init__(self):
        # 初始化默认三级栈
        self._root = AbstractionLevel("ROOT", -1)
        self._levels: List[AbstractionLevel] = []
        
        for name, depth in self.DEFAULT_LEVELS:
            level = AbstractionLevel(name, depth)
            if self._levels:
                self._levels[-1].add_child(level)
            else:
                self._root.add_child(level)
            self._levels.append(level)
        
        # 缓存活跃层级范围
        self._active_min_depth: int = 0
        self._active_max_depth: int = 2
        
        self._task_complexity_history: List[float] = []
    
    # ---- 查询 ----
    
    def get_active_depths(self) -> Tuple[int, int]:
        """获取当前活跃的层级范围 [min_depth, max_depth]"""
        return self._active_min_depth, self._active_max_depth
    
    def get_active_level_count(self) -> int:
        """当前活跃的层级数量"""
        return self._active_max_depth - self._active_min_depth + 1
    
    def get_level(self, depth: int) -> Optional[AbstractionLevel]:
        for level in self._levels:
            if level.depth == depth:
                return level
        return None
    
    def to_dict(self) -> dict:
        return {
            "active_range": [self._active_min_depth, self._active_max_depth],
            "total_levels": len(self._levels),
            "levels": [l.to_dict() for l in self._levels],
        }
    
    # ---- 自适应 ----
    
    def task_adapt(self, complexity: float) -> int:
        """
        根据任务复杂度自动调整栈深度
        
        Args:
            complexity: 任务复杂度 [0.0, 1.0]
                        < 0.3 → 保持 3 层
                        0.3~0.7 → 扩展至 4 层
                        > 0.7 → 扩展至 5 层
        Returns:
            调整后的活跃层级数
        """
        self._task_complexity_history.append(complexity)
        
        target_depth = 2  # 默认 L0-L2
        if complexity >= 0.7:
            target_depth = 4  # L0~L4
        elif complexity >= 0.3:
            target_depth = 3  # L0~L3
        
        # 补齐层级（如需要）
        while len(self._levels) - 1 < target_depth:
            depth = len(self._levels)
            name = self._generate_level_name(depth)
            new_level = AbstractionLevel(name, depth)
            self._levels[-1].add_child(new_level)
            self._levels.append(new_level)
        
        self._active_max_depth = target_depth
        self._sync_active_states()
        
        return self.get_active_level_count()
    
    def prune_by_pain(self, pain_score: float):
        """
        根据痛觉折叠/展开层级
        
        平稳期：信任历史经验，只保留 L0-L1（浅搜）
        波动期：保留 L0-L2（正常）
        危机期：全量展开到最深（深搜）
        """
        status = classify_pain(pain_score)
        
        if status == PainStatus.CALM:
            self._active_max_depth = min(1, len(self._levels) - 1)
        elif status == PainStatus.STRESS:
            self._active_max_depth = min(2, len(self._levels) - 1)
        else:
            self._active_max_depth = len(self._levels) - 1
        
        self._sync_active_states()
    
    def reshape_overnight(self, frequent_paths: List[List[str]]):
        """
        夜间实验室经验重塑（由 DreamSanitizer 调用）
        
        Args:
            frequent_paths: 经常共现的路径序列
                例如 [["ACTION_check_health", "ACTION_report"],
                       ["STRATEGY_failover", "ACTION_switch", "ACTION_verify"]]
        """
        for path in frequent_paths:
            if len(path) < 2:
                continue
            
            # 如果某组 L2 动作总是同时出现 → 打包为宏节点
            # 如果某 L1 策略总是被拆成多种方向 → 拆分
            # （具体逻辑由 DreamSanitizer 的复盘分析驱动）
            logger.info(f"[AbstractionStack] 准备重塑路径: {path}")
    
    def _sync_active_states(self):
        """同步每层的活跃状态"""
        for level in self._levels:
            level.is_active = (
                self._active_min_depth <= level.depth <= self._active_max_depth
            )
    
    def _generate_level_name(self, depth: int) -> str:
        """为新增层级自动生成名称"""
        names = ["REFINE", "VERIFY", "OPTIMIZE", "VALIDATE"]
        idx = depth - len(self.DEFAULT_LEVELS)
        if 0 <= idx < len(names):
            return names[idx]
        return f"LEVEL_{depth}"


# =============================================================================
# 模块 4：DecisionLogger — 双轨制日志
# =============================================================================

class DecisionLogger:
    """
    双轨制决策日志
    
    两种输出格式：
    - JSON 轨迹（给 DreamSanitizer 夜间复盘）
    - 摘要报告（给人审计）
    """
    
    def __init__(self, log_dir: str = ""):
        self._log_dir = log_dir
        self._trace_buffer: List[dict] = []
        self._MAX_BUFFER_SIZE = 500
        
        # 统计计数
        self.total_decisions: int = 0
        self.crisis_decisions: int = 0
    
    def log_decision(self,
                     timestamp: float,
                     pain_score: float,
                     budget: SearchBudget,
                     decision_chain: Dict[str, Any],
                     result: Optional[str] = None,
                     anomaly_flags: Optional[List[str]] = None) -> Tuple[str, str]:
        """
        记录一次决策
        
        Returns:
            (json_path, summary_text)
        """
        self.total_decisions += 1
        
        if pain_score >= 0.7:
            self.crisis_decisions += 1
        
        # ---- 1. JSON 轨迹（给 DreamSanitizer） ----
        trace_record = {
            "timestamp": timestamp,
            "pain_score": round(pain_score, 3),
            "pain_status": classify_pain(pain_score).value,
            "budget": budget.to_dict(),
            "decision_chain": decision_chain,
            "result": result,
            "anomaly_flags": anomaly_flags or [],
        }
        self._trace_buffer.append(trace_record)
        
        # ---- 2. 摘要报告（给人审计） ----
        summary = self._build_summary(timestamp, pain_score, budget,
                                      decision_chain, result, anomaly_flags)
        
        # 写日志文件
        json_path = ""
        if self._log_dir:
            json_path = self._flush_critical(trace_record)
        
        return json_path, summary
    
    def _build_summary(self,
                       timestamp: float,
                       pain_score: float,
                       budget: SearchBudget,
                       decision_chain: Dict[str, Any],
                       result: Optional[str] = None,
                       anomaly_flags: Optional[List[str]] = None) -> str:
        """生成人类可读的摘要报告"""
        status = classify_pain(pain_score).value.upper()
        lines = []
        lines.append("=" * 55)
        lines.append(f"DECISION LOG | {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}")
        lines.append(f"Pain Score: {pain_score:.2f} ({status})")
        
        # 决策链
        if "l0" in decision_chain:
            lines.append("")
            lines.append("DECISION CHAIN:")
            l0 = decision_chain.get("l0", {})
            lines.append(f"  L0: [{l0.get('label', 'INTENT')}] {l0.get('content', '-')}")
            
            l1 = decision_chain.get("l1", {})
            if l1:
                selected = l1.get("selected", "")
                rejected = l1.get("rejected", [])
                lines.append(f"  L1: [STRATEGY] {selected}")
                for r in rejected:
                    lines.append(f"   ↳ Rejected: {r}")
            
            l2 = decision_chain.get("l2", {})
            if l2:
                lines.append(f"  L2: [ACTION] {l2.get('content', '-')} → {l2.get('result', 'PENDING')}")
        
        # 异常标记
        if anomaly_flags:
            lines.append("")
            for flag in anomaly_flags:
                lines.append(f"  [!] {flag}")
        
        # 决策参数摘要
        lines.append("")
        lines.append(f"  Budget: depth={budget.max_depth}, "
                     f"branch={budget.branch_factor}, "
                     f"sims={budget.simulations}")
        
        if result:
            lines.append(f"  Result: {result}")
        
        lines.append("=" * 55)
        return "\n".join(lines)
    
    def _flush_critical(self, record: dict) -> str:
        """将关键决策写入 JSON 文件（供 DreamSanitizer 读取）"""
        import os
        os.makedirs(self._log_dir, exist_ok=True)
        path = os.path.join(
            self._log_dir,
            f"decision_{int(record['timestamp'])}.json"
        )
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        return path
    
    def get_trace_buffer(self) -> List[dict]:
        """获取当前缓冲区中的所有轨迹（供 DreamSanitizer 夜间消费）"""
        return self._trace_buffer.copy()
    
    def clear_trace_buffer(self):
        """清空缓冲区（DreamSanitizer 消费后调用）"""
        self._trace_buffer.clear()
    
    def get_stats(self) -> dict:
        return {
            "total_decisions": self.total_decisions,
            "crisis_decisions": self.crisis_decisions,
            "buffer_size": len(self._trace_buffer),
        }


# =============================================================================
# 便捷工厂函数
# =============================================================================

def create_default_pruner(emotion_engine=None) -> AdaptiveUCTPruner:
    """创建默认配置的 UCT Pruner"""
    return AdaptiveUCTPruner(emotion_engine=emotion_engine)


def create_default_stack() -> DynamicAbstractionStack:
    """创建默认配置的动态抽象栈"""
    return DynamicAbstractionStack()


def create_default_logger(log_dir: str = "") -> DecisionLogger:
    """创建默认配置的决策日志器"""
    return DecisionLogger(log_dir=log_dir)
