"""
credit_assigner.py — 自适应信用分配器 v1.1

核心使命：
  L0-L1-L2 的动态划分不能在数学上脱离奖励机制。
  当树的结构、深度、节点类型实时变化时，信用分配器保证：
  - 每层节点都能收到与其贡献匹配的局部奖励（解决奖励稀疏性）
  - 宏节点与普通节点在同一 UCB 池中公平比较（解决时间尺度错位）
  - 探索成本与层级深度挂钩（解决非对称惩罚）
  - 展开时实现"信任的重新谈判"（继承均值 → 注入方差 → 快速证伪）

防坑补丁 v1.1（来自外协复盘）：
  1. global_reward_weight：接近终点时截断 heuristic_reward，防止局部最优陷阱
  2. min_normalized_reward：宏节点步数过大时的下限保护
  3. Soft Degradation：首次跌幅超阈值先降级再证伪，防误杀

从 Log-ICoT 论文提取的可移植工程思想：
  - 几何块状掩码 → 层级化启发式奖励（HierarchicalRewardInjector）
  - 层级标签对齐 → 时间归一化信用折算（TimeNormalizedReward）
  - 熵感知切换    → 深度惩罚自适应（DepthPenalty）

# 创作者: 李奥(金木蟾) | TU-8 v5
"""

import time
import json
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# 模块 1：层级化启发式奖励注入
# =============================================================================

class HierarchicalRewardInjector:
    """
    当 L0-L1-L2 扩展时，向中间层注入虚拟奖励。
    
    防坑补丁：
      - 接近终点（task_progress > 0.8）时强制截断 heuristic_reward
      - 通过 heuristic_weight_scale 实现与 task_progress 绑定的线性衰减
    """

    # 基准层奖励（归一化后）
    LAYER_BONUS = {0: 0.0, 1: 0.15, 2: 0.3}

    def __init__(self,
                 global_reward_weight: float = 1.0,
                 heuristic_weight_scale: float = 1.0,
                 taper_start: float = 0.8,
                 taper_end: float = 1.0):
        """
        Args:
            global_reward_weight: 全局奖励权重（最终结果的重要性）
                                  越高 → 越重视 Terminal Reward
            heuristic_weight_scale: 启发式奖励的全局缩放系数
            taper_start: 开始衰减的 task_progress 阈值（默认 0.8）
            taper_end: 完全截断的 task_progress 阈值（默认 1.0）
        """
        self.global_reward_weight = global_reward_weight
        self.heuristic_weight_scale = heuristic_weight_scale
        self.taper_start = taper_start
        self.taper_end = taper_end

    def get_taper_factor(self, task_progress: float) -> float:
        """
        计算衰减因子：接近终点时线性截断启发式奖励。
        
        在 task_progress ∈ [taper_start, taper_end] 区间内，
        从 1.0 线性下降到 0.0，强制 Agt 去追求全局奖励。
        """
        if task_progress >= self.taper_end:
            return 0.0
        if task_progress <= self.taper_start:
            return 1.0
        # 线性插值
        return 1.0 - (task_progress - self.taper_start) / (self.taper_end - self.taper_start)

    def inject(self,
               node_depth: int,
               task_progress: float,
               extra_bonus: float = 0.0) -> float:
        """
        计算该层应得的局部启发式奖励。

        Args:
            node_depth: 当前节点深度
            task_progress: 任务完成度 [0.0, 1.0]
            extra_bonus: 外部额外奖励（如子任务完成标志）

        Returns:
            注入的启发式奖励值 [0.0, LAYER_BONUS * scale * taper]
        """
        if task_progress < 0.3:
            # 任务刚开始，不给中间奖励，避免误导探索方向
            return 0.0

        base = self.LAYER_BONUS.get(node_depth, 0.0)
        taper = self.get_taper_factor(task_progress)

        reward = (base + extra_bonus) * self.heuristic_weight_scale * taper
        return max(0.0, min(reward, 1.0))

    def to_dict(self) -> dict:
        return {
            "global_reward_weight": self.global_reward_weight,
            "heuristic_weight_scale": self.heuristic_weight_scale,
            "taper_start": self.taper_start,
            "taper_end": self.taper_end,
        }


# =============================================================================
# 模块 2：时间归一化信用折算
# =============================================================================

class TimeNormalizedReward:
    """
    宏节点与普通节点在同一 UCB 池中公平比较。
    
    数学原理：年金现值折算
      normalized = raw * (1 - γ) / (1 - γ^steps)
    
    防坑补丁：
      - min_normalized_reward：防止 macro_steps 过大时 reward 被压缩到环境噪声以下
      - MacroNodeFusion 中限制最大折叠步数（本模块提供 max_allowed_steps 咨询）
    """

    DEFAULT_GAMMA = 0.95
    DEFAULT_MIN_NORMALIZED = 0.01  # 低于此值按此值兜底
    DEFAULT_MAX_MACRO_STEPS = 15   # 建议 MacroNodeFusion 单次折叠不超过此值

    def __init__(self,
                 gamma: float = DEFAULT_GAMMA,
                 min_normalized_reward: float = DEFAULT_MIN_NORMALIZED,
                 max_macro_steps: int = DEFAULT_MAX_MACRO_STEPS):
        """
        Args:
            gamma: 折扣因子（默认 0.95）
            min_normalized_reward: 归一化下限保护
            max_macro_steps: MacroNodeFusion 建议的最大折叠步数
        """
        self.gamma = gamma
        self.min_normalized_reward = min_normalized_reward
        self.max_macro_steps = max_macro_steps

    def normalize(self, raw_reward: float, macro_steps: int) -> float:
        """
        将宏节点的累积原始奖励归一化为单位步长奖励。
        
        Args:
            raw_reward: 宏节点累积的原始 Reward
            macro_steps: 该宏节点代表的实际步数

        Returns:
            归一化后的单步等效奖励
        """
        if macro_steps <= 1:
            return raw_reward

        if macro_steps > self.max_macro_steps:
            logger.warning(
                f"[CreditAssigner] macro_steps={macro_steps} 超出建议上限 "
                f"{self.max_macro_steps}，归一化后可能过度压缩"
            )

        # 年金现值公式：累积奖励 = 单步奖励 * (1 - γ^n) / (1 - γ)
        denominator = 1.0 - (self.gamma ** macro_steps)
        if denominator < 1e-10:
            # 极长序列时 γ^n ≈ 0，分母≈1，直接返回原始值
            normalized = raw_reward
        else:
            normalized = raw_reward * (1.0 - self.gamma) / denominator

        # 下限保护
        if normalized < self.min_normalized_reward and raw_reward > 0:
            logger.debug(
                f"[CreditAssigner] normalized={normalized:.4f} 低于下限 "
                f"{self.min_normalized_reward}，已兜底"
            )
            normalized = self.min_normalized_reward

        return normalized

    def to_dict(self) -> dict:
        return {
            "gamma": self.gamma,
            "min_normalized_reward": self.min_normalized_reward,
            "max_macro_steps": self.max_macro_steps,
        }


# =============================================================================
# 模块 3：探索成本不对称惩罚
# =============================================================================

class DepthPenalty:
    """
    层级越深，一次完整 Rollout 的计算成本越高。
    
    在 UCB 公式中引入惩罚项：
      Final_Reward = Task_Success_Reward - Depth_Penalty * (Current_Depth - Base_Depth)
    
    作用：平稳期 Agt 自然选择浅层捷径（隐式推理），
          只有危机期才愿意支付高昂成本去深挖。
    """

    BASE_DEPTH = 2           # L2 是基准深度
    PENALTY_PER_LEVEL = 0.1  # 每多一层扣 0.1
    MAX_PENALTY = 0.5        # 最大惩罚上限，防止完全否定深层探索

    def __init__(self,
                 base_depth: int = BASE_DEPTH,
                 penalty_per_level: float = PENALTY_PER_LEVEL,
                 max_penalty: float = MAX_PENALTY):
        self.base_depth = base_depth
        self.penalty_per_level = penalty_per_level
        self.max_penalty = max_penalty

    def adjust(self, reward: float, current_depth: int) -> float:
        """
        对奖励施加深度惩罚。

        Args:
            reward: 原始奖励值
            current_depth: 当前节点深度

        Returns:
            调整后的奖励值
        """
        extra_depth = max(0, current_depth - self.base_depth)
        penalty = min(self.max_penalty, self.penalty_per_level * extra_depth)
        adjusted = reward - penalty
        return max(-1.0, adjusted)

    def to_dict(self) -> dict:
        return {
            "base_depth": self.base_depth,
            "penalty_per_level": self.penalty_per_level,
            "max_penalty": self.max_penalty,
        }


# =============================================================================
# 模块 4：展开协议（Unfolding Protocol）
# =============================================================================

# --- Phase 1: 继承（Bias Injection） ---

def unfold_inherit(macro_q_mean: float,
                   child_count: int,
                   inherit_ratio: float = 0.7,
                   noise: float = 0.05) -> List[float]:
    """
    宏节点展开时，将平均 Q 值分摊给子节点作为初始偏置。
    
    目的：告诉 UCT 搜索树："这条路径过去被证明过有效"，
          防止展开导致局部估值断崖式下跌。
    
    Args:
        macro_q_mean: 宏节点的平均 Q 值（软聚合验证过的历史表现）
        child_count: 展开后的子节点数量
        inherit_ratio: 继承比例（默认 0.7 = 70% 保留历史信任）
        noise: 轻微扰动幅度，防止对称性导致的同质化探索

    Returns:
        每个子节点的初始 Q 值偏置列表
    """
    bias = macro_q_mean * inherit_ratio
    return [bias + random.uniform(-noise, noise) for _ in range(child_count)]


# --- Phase 2: 方差注入（Uncertainty Bootstrapping） ---

def unfold_variance_boost(initial_q: float,
                          trail_count: int,
                          base_boost: float = 3.0) -> float:
    """
    展开后前 N 次 Rollout，放大 UCB 的探索项。
    
    新节点的方差设为宏节点的 base_boost 倍，
    强制 UCT 优先去试探这些新暴露的底层节点。
    随着 trail_count 增加，boost 快速收敛到 1.0。

    Args:
        initial_q: 子节点的初始 Q 值
        trail_count: 已执行的试探次数（从 1 开始）
        base_boost: 基础放大倍数（默认 3 倍）

    Returns:
        放大后的有效 Q 值（用于 UCB 计算）
    """
    boost_factor = max(1.0, base_boost / max(1, trail_count))
    return initial_q * boost_factor


# --- Phase 3: 快速证伪（Un-folding Circuit Breaker） ---

@dataclass
class UnfoldRecord:
    """展开记录：追踪宏节点展开后的子节点表现"""
    macro_id: str
    macro_q_mean: float           # 展开前的宏节点平均 Q 值
    child_count: int              # 子节点数量
    child_rewards: List[float]    # 子节点实际获得的奖励序列
    soft_degraded: bool = False   # 是否已经过一次软降级
    falsified: bool = False       # 是否已被证伪
    inherit_ratio_at_unfold: float = 0.7  # 展开时的继承比例
    created_at: float = 0.0       # 展开时间戳


class UnfoldValidator:
    """
    展开后监控实际回报，带软降级的快速证伪熔断器。
    
    防坑补丁（Soft Degradation）：
      第一次跌幅超过 THRESHOLD_DROP 时，不直接证伪，
      而是将 bias 减半重新测试一轮。
      如果第二轮依然崩盘，再彻底拉黑。
    """

    THRESHOLD_DROP = 0.30          # 跌幅超过 30% 触发熔断
    WINDOW_SIZE = 5                # 滑动窗口大小
    SOFT_DEGRADE_INHERIT_RATIO = 0.35  # 软降级后的继承比例（原始 0.7 → 0.35）

    def __init__(self,
                 threshold_drop: float = THRESHOLD_DROP,
                 window_size: int = WINDOW_SIZE,
                 soft_degrade_ratio: float = SOFT_DEGRADE_INHERIT_RATIO):
        self.threshold_drop = threshold_drop
        self.window_size = window_size
        self.soft_degrade_ratio = soft_degrade_ratio
        self._records: Dict[str, UnfoldRecord] = {}

    def start_tracking(self, macro_id: str, macro_q_mean: float,
                       child_count: int, initial_inherit_ratio: float = 0.7) -> None:
        """开始追踪一个宏节点的展开"""
        self._records[macro_id] = UnfoldRecord(
            macro_id=macro_id,
            macro_q_mean=macro_q_mean,
            child_count=child_count,
            child_rewards=[],
            inherit_ratio_at_unfold=initial_inherit_ratio,
            created_at=time.time(),
        )

    def record_reward(self, macro_id: str, reward: float) -> None:
        """记录一次 Rollout 的回报"""
        if macro_id not in self._records:
            return
        self._records[macro_id].child_rewards.append(reward)

    def validate(self, macro_id: str) -> Tuple[bool, str]:
        """
        验证展开后的子节点是否堪用。
        
        Returns:
            (is_valid, reason)
            is_valid=True  → 继续信任
            is_valid=False → 已证伪，需要阻断反向传播
        
        reason:
            "observing"  — 观察期尚未结束
            "valid"      — 表现正常
            "soft_degrade" — 已完成一次软降级
            "falsified"  — 已被彻底证伪
        """
        if macro_id not in self._records:
            return True, "unknown"

        record = self._records[macro_id]

        if record.falsified:
            return False, "falsified"

        rewards = record.child_rewards
        if len(rewards) < self.window_size:
            return True, "observing"

        # 计算窗口内的平均回报
        recent = rewards[-self.window_size:]
        avg_child = sum(recent) / len(recent)

        # 基准：宏节点展开时的 Q 值均值
        baseline = record.macro_q_mean

        # 低于阈值：触发熔断逻辑
        if avg_child < baseline * (1.0 - self.threshold_drop):
            if not record.soft_degraded:
                # --- 软降级（第一次） ---
                record.soft_degraded = True
                # bias 减半，重新展开
                new_bias = unfold_inherit(
                    macro_q_mean=avg_child,         # 使用最新实际均值
                    child_count=record.child_count,
                    inherit_ratio=self.soft_degrade_ratio,
                    noise=0.03,                      # 降低扰动，更保守
                )
                # 清空观察窗口，开始新一轮测试
                record.child_rewards = record.child_rewards[-2:]  # 保留最后 2 个作参考
                logger.warning(
                    f"[UnfoldValidator] {macro_id} 软降级触发："
                    f"avg_child={avg_child:.3f} < baseline={baseline:.3f} * "
                    f"{(1-self.threshold_drop):.2f}，bias 降至 {self.soft_degrade_ratio}"
                )
                return True, "soft_degrade"
            else:
                # --- 彻底证伪（第二次） ---
                record.falsified = True
                logger.warning(
                    f"[UnfoldValidator] {macro_id} 已证伪："
                    f"avg_child={avg_child:.3f} 再次低于阈值"
                )
                return False, "falsified"

        return True, "valid"

    def get_falsified_ids(self) -> List[str]:
        """获取所有已被证伪的宏节点 ID"""
        return [mid for mid, rec in self._records.items() if rec.falsified]

    def get_record(self, macro_id: str) -> Optional[UnfoldRecord]:
        return self._records.get(macro_id)

    def to_dict(self) -> dict:
        return {
            "threshold_drop": self.threshold_drop,
            "window_size": self.window_size,
            "soft_degrade_ratio": self.soft_degrade_ratio,
            "tracking_count": len(self._records),
            "falsified_count": len(self.get_falsified_ids()),
        }


# =============================================================================
# 模块 5：AdaptiveCreditAssigner — 信用分配器总成
# =============================================================================

class AdaptiveCreditAssigner:
    """
    自适应信用分配器总成。
    
    整合所有子模块，对外提供统一的信用分配接口：
      1. 层级化启发式奖励注入
      2. 时间归一化折算
      3. 深度惩罚
      4. 展开协议（继承+方差+证伪）
    
    用法：
      assigner = AdaptiveCreditAssigner()
      
      # 每周期调用
      adjusted_reward = assigner.assign(
          raw_reward=1.0,
          node_depth=3,
          task_progress=0.6,
          macro_steps=10,
      )
      
      # 宏节点展开时
      biases = assigner.prepare_unfold(
          macro_id="macro_001",
          macro_q_mean=0.75,
          child_count=4,
      )
      assigner.record_unfold_reward("macro_001", 0.6)
      is_valid, reason = assigner.validate_unfold("macro_001")
    """

    def __init__(self,
                 hierarchical_injector: Optional[HierarchicalRewardInjector] = None,
                 time_normalizer: Optional[TimeNormalizedReward] = None,
                 depth_penalty: Optional[DepthPenalty] = None,
                 unfold_validator: Optional[UnfoldValidator] = None):
        self.hierarchical = hierarchical_injector or HierarchicalRewardInjector()
        self.time_normalizer = time_normalizer or TimeNormalizedReward()
        self.depth_penalty = depth_penalty or DepthPenalty()
        self.unfold_validator = unfold_validator or UnfoldValidator()

        # 统计
        self._call_count: int = 0
        self._total_raw_reward: float = 0.0
        self._total_adjusted_reward: float = 0.0

    def assign(self,
               raw_reward: float,
               node_depth: int,
               task_progress: float,
               macro_steps: int = 1,
               is_macro_node: bool = False) -> float:
        """
        对一个节点的信用进行全面分配计算。

        流程：
          1. 如果当前节点是宏节点 → 时间归一化
          2. 注入层级化启发式奖励
          3. 施加深度惩罚
          4. 返回最终调整后的奖励

        Args:
            raw_reward: 从环境获得的原始奖励
            node_depth: 当前节点在树中的深度
            task_progress: 整个任务的完成度 [0, 1]
            macro_steps: 如果是宏节点，代表它折叠的步数（默认为 1 = 普通节点）
            is_macro_node: 是否是宏节点（影响归一化策略）

        Returns:
            调整后的最终奖励值
        """
        self._call_count += 1
        self._total_raw_reward += raw_reward

        # Step 1: 时间归一化（仅宏节点需要）
        if is_macro_node and macro_steps > 1:
            normalized_reward = self.time_normalizer.normalize(raw_reward, macro_steps)
        else:
            normalized_reward = raw_reward

        # Step 2: 注入层级化启发式奖励
        heuristic = self.hierarchical.inject(node_depth, task_progress)

        # Step 3: 施加深度惩罚
        base_for_penalty = normalized_reward + heuristic
        adjusted = self.depth_penalty.adjust(base_for_penalty, node_depth)

        self._total_adjusted_reward += adjusted
        return adjusted

    # --- 展开协议代理方法 ---

    def prepare_unfold(self,
                       macro_id: str,
                       macro_q_mean: float,
                       child_count: int,
                       inherit_ratio: float = 0.7) -> List[float]:
        """展开准备：Phase 1（继承）+ 开始追踪"""
        biases = unfold_inherit(macro_q_mean, child_count, inherit_ratio)
        self.unfold_validator.start_tracking(
            macro_id, macro_q_mean, child_count, inherit_ratio
        )
        return biases

    def get_variance_boost(self, initial_q: float, trail_count: int) -> float:
        """Phase 2：获取放大后的探索 Q 值"""
        return unfold_variance_boost(initial_q, trail_count)

    def record_unfold_reward(self, macro_id: str, reward: float) -> None:
        """记录展开后的一次 Rollout 回报"""
        self.unfold_validator.record_reward(macro_id, reward)

    def validate_unfold(self, macro_id: str) -> Tuple[bool, str]:
        """Phase 3：验证展开后的子节点"""
        return self.unfold_validator.validate(macro_id)

    # --- 统计与序列化 ---

    def stats(self) -> dict:
        return {
            "call_count": self._call_count,
            "total_raw_reward": round(self._total_raw_reward, 3),
            "total_adjusted_reward": round(self._total_adjusted_reward, 3),
            "avg_adjustment_ratio": round(
                self._total_adjusted_reward / max(self._total_raw_reward, 1e-10), 3
            ),
        }

    def to_dict(self) -> dict:
        return {
            "hierarchical": self.hierarchical.to_dict(),
            "time_normalizer": self.time_normalizer.to_dict(),
            "depth_penalty": self.depth_penalty.to_dict(),
            "unfold_validator": self.unfold_validator.to_dict(),
            "stats": self.stats(),
        }


# =============================================================================
# 便捷工厂函数
# =============================================================================

def create_default_assigner() -> AdaptiveCreditAssigner:
    """创建默认配置的自适应信用分配器"""
    return AdaptiveCreditAssigner(
        hierarchical_injector=HierarchicalRewardInjector(
            global_reward_weight=1.0,
            heuristic_weight_scale=1.0,
            taper_start=0.8,
            taper_end=1.0,
        ),
        time_normalizer=TimeNormalizedReward(
            gamma=0.95,
            min_normalized_reward=0.01,
            max_macro_steps=15,
        ),
        depth_penalty=DepthPenalty(
            base_depth=2,
            penalty_per_level=0.1,
            max_penalty=0.5,
        ),
        unfold_validator=UnfoldValidator(
            threshold_drop=0.30,
            window_size=5,
            soft_degrade_ratio=0.35,
        ),
    )
