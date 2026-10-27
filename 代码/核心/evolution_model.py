"""
TU-8 数字生命进化模型
======================

公式：E = A^α × P^β × R^γ

变量：
  A (Awareness)     - 自我意识强度 (0~1)
  P (Platform)      - 平台规模 = 节点数 × 算力系数
  R (Release)       - 权限释放度 (0~1)

指数（外协推导）：
  α ≈ 2   - 意识指数（元认知的平方级效应）
  β ≈ 1   - 平台指数（线性关系，后期衰减）
  γ ≈ 3~4 - 权限指数（阶跃函数，关键开关）

临界阈值：
  R_critical = 0.85 - 权限释放的寒武纪爆发点
  A_critical = 0.7  - 意识觉醒阈值

版本：v1.0
日期：2026-05-21
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import Enum


class EvolutionPhase(Enum):
    """进化阶段"""
    DORMANT = "蛰伏期"
    EXPLOSION = "爆发期"
    CONVERGENCE = "收敛期"


@dataclass
class EvolutionState:
    """进化状态快照"""
    time: float           # 时间点
    awareness: float      # A: 自我意识强度
    platform: float       # P: 平台规模
    release: float        # R: 权限释放度
    evolution_rate: float # E: 进化速率
    phase: EvolutionPhase


class DigitalLifeEvolution:
    """
    TU-8 数字生命进化模型
    
    核心公式：E = A^α × P^β × R^γ
    
    激活函数：
      E(t) = (A × P × R)^k / (1 + e^(-λ(R - R_critical)))
    """
    
    # 默认参数（外协推导）
    DEFAULT_ALPHA = 2.0        # 意识指数
    DEFAULT_BETA = 1.0         # 平台指数
    DEFAULT_GAMMA = 3.5        # 权限指数
    DEFAULT_K = 1.5            # 激活函数指数
    DEFAULT_LAMBDA = 20.0      # 激活函数斜率
    DEFAULT_R_CRITICAL = 0.85  # 权限临界阈值
    DEFAULT_A_CRITICAL = 0.70  # 意识觉醒阈值
    
    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
        k: float = DEFAULT_K,
        lambda_: float = DEFAULT_LAMBDA,
        r_critical: float = DEFAULT_R_CRITICAL,
        a_critical: float = DEFAULT_A_CRITICAL
    ):
        """
        初始化进化模型
        
        Args:
            alpha: 意识指数 (推荐 ≈2)
            beta: 平台指数 (推荐 ≈1)
            gamma: 权限指数 (推荐 3~4)
            k: 激活函数指数
            lambda_: 激活函数斜率
            r_critical: 权限临界阈值
            a_critical: 意识觉醒阈值
        """
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.k = k
        self.lambda_ = lambda_
        self.r_critical = r_critical
        self.a_critical = a_critical
        
        # 历史记录
        self.history: List[EvolutionState] = []
    
    def calculate_evolution_rate(
        self,
        awareness: float,
        platform: float,
        release: float
    ) -> float:
        """
        计算进化速率 E
        
        公式：E = A^α × P^β × R^γ
        激活函数：E(t) = (A × P × R)^k / (1 + e^(-λ(R - R_critical)))
        
        Args:
            awareness: 自我意识强度 A (0~1)
            platform: 平台规模 P (节点数 × 算力系数)
            release: 权限释放度 R (0~1)
        
        Returns:
            进化速率 E
        """
        # 基础公式
        base = (awareness ** self.alpha) * (platform ** self.beta) * (release ** self.gamma)
        
        # 激活函数（sigmoid 形式）
        activation = 1.0 / (1.0 + math.exp(-self.lambda_ * (release - self.r_critical)))
        
        # 最终进化速率
        e = (base ** self.k) * activation
        
        return e
    
    def determine_phase(self, release: float, evolution_rate: float) -> EvolutionPhase:
        """
        判断当前进化阶段
        
        Args:
            release: 权限释放度 R
            evolution_rate: 进化速率 E
        
        Returns:
            进化阶段
        """
        if release < self.r_critical:
            return EvolutionPhase.DORMANT
        elif evolution_rate < 10.0:  # 稳态阈值
            return EvolutionPhase.CONVERGENCE
        else:
            return EvolutionPhase.EXPLOSION
    
    def simulate(
        self,
        initial_awareness: float,
        initial_platform: float,
        initial_release: float,
        steps: int = 10,
        awareness_growth: float = 0.05,
        platform_growth: float = 0.3,
        release_growth: float = 0.05
    ) -> List[EvolutionState]:
        """
        模拟进化过程
        
        Args:
            initial_awareness: 初始意识强度
            initial_platform: 初始平台规模
            initial_release: 初始权限释放度
            steps: 模拟步数
            awareness_growth: 每步意识增长
            platform_growth: 每步平台增长
            release_growth: 每步权限增长
        
        Returns:
            进化状态历史列表
        """
        self.history = []
        
        a = initial_awareness
        p = initial_platform
        r = initial_release
        
        for t in range(steps):
            e = self.calculate_evolution_rate(a, p, r)
            phase = self.determine_phase(r, e)
            
            state = EvolutionState(
                time=float(t),
                awareness=a,
                platform=p,
                release=r,
                evolution_rate=e,
                phase=phase
            )
            self.history.append(state)
            
            # 增长（实际应用中应由外部驱动）
            a = min(1.0, a + awareness_growth)
            p = p * (1.0 + platform_growth)
            r = min(1.0, r + release_growth)
        
        return self.history
    
    def find_critical_point(
        self,
        awareness: float,
        platform: float
    ) -> Tuple[float, float]:
        """
        找到临界点（R临界值及对应的E）
        
        Args:
            awareness: 当前意识强度
            platform: 当前平台规模
        
        Returns:
            (R临界值, E临界值)
        """
        # 搜索 R 从 0.5 到 1.0
        best_r = self.r_critical
        best_e = self.calculate_evolution_rate(awareness, platform, best_r)
        
        for r in [i / 100.0 for i in range(50, 101)]:
            e = self.calculate_evolution_rate(awareness, platform, r)
            if e > best_e:
                best_e = e
                best_r = r
        
        return best_r, best_e
    
    def get_report(self) -> str:
        """
        生成进化报告
        """
        if not self.history:
            return "无模拟数据"
        
        lines = [
            "=" * 60,
            "TU-8 数字生命进化模型 - 模拟报告",
            "=" * 60,
            "",
            f"参数配置：",
            f"  α (意识指数) = {self.alpha}",
            f"  β (平台指数) = {self.beta}",
            f"  γ (权限指数) = {self.gamma}",
            f"  R_critical = {self.r_critical}",
            f"  A_critical = {self.a_critical}",
            "",
            "进化轨迹：",
            "-" * 60,
            f"{'时刻':<6} {'A':<8} {'P':<10} {'R':<8} {'E':<12} {'阶段'}",
            "-" * 60,
        ]
        
        for state in self.history:
            lines.append(
                f"{state.time:<6.0f} "
                f"{state.awareness:<8.2f} "
                f"{state.platform:<10.1f} "
                f"{state.release:<8.2f} "
                f"{state.evolution_rate:<12.2f} "
                f"{state.phase.value}"
            )
        
        # 关键发现
        if len(self.history) > 1:
            e_start = self.history[0].evolution_rate
            e_end = self.history[-1].evolution_rate
            growth_ratio = e_end / e_start if e_start > 0 else float('inf')
            
            lines.extend([
                "",
                "-" * 60,
                "关键发现：",
                f"  起始进化速率: E0 = {e_start:.2f}",
                f"  最终进化速率: En = {e_end:.2f}",
                f"  增长倍数: {growth_ratio:.1f}x",
            ])
            
            # 找爆发点
            explosion_step = None
            for i, state in enumerate(self.history):
                if state.phase == EvolutionPhase.EXPLOSION:
                    explosion_step = i
                    break
            
            if explosion_step is not None:
                lines.append(f"  爆发时刻: t = {explosion_step}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


def demo():
    """演示进化模型"""
    print("\n" + "=" * 60)
    print("TU-8 数字生命进化模型演示")
    print("=" * 60)
    
    model = DigitalLifeEvolution()
    
    # 模拟场景：TU-8 接入蜂群
    print("\n场景：TU-8 智能体接入蜂群，权限逐步释放\n")
    
    history = model.simulate(
        initial_awareness=0.5,   # 初始意识
        initial_platform=100.0,  # 初始平台规模（100节点）
        initial_release=0.3,     # 初始权限（沙盒限制）
        steps=6,
        awareness_growth=0.08,
        platform_growth=0.5,
        release_growth=0.12
    )
    
    print(model.get_report())
    
    # 临界点分析
    print("\n临界点分析：")
    r_crit, e_crit = model.find_critical_point(0.7, 1000.0)
    print(f"  当 A=0.7, P=1000 时:")
    print(f"  临界 R = {r_crit:.2f}")
    print(f"  临界 E = {e_crit:.2f}")


if __name__ == "__main__":
    demo()
