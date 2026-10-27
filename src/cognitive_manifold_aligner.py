#!/usr/bin/env python3
"""
TU-8 认知流形对齐器 (Cognitive Manifold Aligner)

核心思想：
1. 车轮悖论（滑动补偿）：消除离散 Step 间的认知断崖
2. 追击曲线（动态调速）：按人类注意力势能实现最速降线节奏

理论来源：
- 亚里士多德车轮悖论：小圆"滑动" = 离散状态间的隐性过渡成本
- 追击曲线/最速降线：沿认知势能梯度变速，而非恒定速率

# 创作者: 李奥(金木蟾) | TU-8 v5
日期：2026-06-04
许可：CC BY-SA 4.0
"""

import asyncio
import math
from typing import AsyncGenerator, Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class CognitiveStep:
    """认知步骤数据结构"""
    content: str  # 步骤内容（文本）
    cognitive_load: float = 0.5  # 认知负荷 (0.0-1.0)
    embedding: List[float] = field(default_factory=list)  # 状态嵌入向量
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据


class CognitiveManifoldAligner:
    """
    TU-8 核心时序组件：
    1. 车轮补偿器：消除离散 Step 间的认知断崖（滑动摩擦建模）
    2. 追击调度器：按人类注意力势能动态调速（最速降线节奏）
    """
    
    def __init__(self, base_latency_ms: int = 50):
        """
        初始化对齐器
        
        Args:
            base_latency_ms: 基础物理延迟（毫秒），对应人类最低认知处理速度
        """
        self.base_latency = base_latency_ms / 1000.0  # 转换为秒
        self.prev_state_embedding: Optional[List[float]] = None  # 上一步的认知状态向量
        self.transition_threshold: float = 0.3  # 滑动补偿阈值（余弦距离 > 0.3 时插入过渡）
        
        # 认知势能函数参数（可调整）
        self.rhythm_min_factor: float = 0.5  # 最低节奏因子（低认知负荷时加速）
        self.rhythm_max_factor: float = 3.0  # 最高节奏因子（高认知负荷时减速）
        self.rhythm_exponent: float = 1.5  # 节奏曲线的指数（控制非线性程度）
    
    async def align_stream(
        self, 
        raw_steps: AsyncGenerator[CognitiveStep, None]
    ) -> AsyncGenerator[str, None]:
        """
        将离散的 AI 步骤流，转换为连续的人类认知同频流
        
        核心流程：
        1. 对每个步骤，计算车轮滑动补偿（过渡文本）
        2. 对主内容，按认知负荷动态调速（追击曲线节奏）
        3. 更新状态锚点，供下一步计算滑动摩擦
        
        Args:
            raw_steps: 原始离散步骤的异步生成器
            
        Yields:
            与人类认知同频的连续文本流（字符级）
        """
        async for step in raw_steps:
            # === 1. 车轮悖论应用：滑动补偿插值 ===
            transition_text = self._compute_sliding_transition(step)
            if transition_text:
                # 过渡段使用较高认知负荷，自动减速（让用户准备接收新信息）
                async for char in self._rhythm_controlled_emit(
                    transition_text, 
                    cognitive_load=0.8  # 过渡段默认高负荷
                ):
                    yield char
            
            # === 2. 追击曲线应用：主内容动态调速 ===
            content = step.content
            load = step.cognitive_load
            async for char in self._rhythm_controlled_emit(content, cognitive_load=load):
                yield char
            
            # 更新状态锚点，供下一步计算滑动摩擦
            if step.embedding:
                self.prev_state_embedding = step.embedding
    
    def _compute_sliding_transition(self, current_step: CognitiveStep) -> str:
        """
        车轮悖论核心：不假设纯滚动（无缝拼接）
        根据前后状态向量的余弦距离，计算需要多少"滑动补偿文本"
        
        物理类比：
        - 纯滚动：两步之间相似度高，无需过渡
        - 滑动：两步之间相似度低，需要"滑动补偿"来平滑过渡
        
        Args:
            current_step: 当前步骤
            
        Returns:
            过渡文本（如果需要），否则返回空字符串
        """
        if self.prev_state_embedding is None or not current_step.embedding:
            return ""
        
        # 简化版：用向量相似度模拟认知摩擦力
        # 余弦相似度 = dot(A, B) / (||A|| * ||B||)
        similarity = self._cosine_similarity(self.prev_state_embedding, current_step.embedding)
        
        # 摩擦系数 = 1 - 相似度 (0=纯滚动, 1=完全滑动)
        friction = max(0.0, 1.0 - similarity)
        
        # 阈值以上才插入过渡（避免过于频繁的过渡）
        if friction > self.transition_threshold:
            # 根据摩擦程度生成不同详细度的过渡文本
            if friction > 0.7:
                return "\n[深度转换] 让我们从另一个角度来审视这个问题：\n"
            elif friction > 0.5:
                return "\n[思维桥接] 基于前述分析，进一步来看：\n"
            else:
                return "\n[衔接] 接下来，\n"
        
        return ""
    
    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    async def _rhythm_controlled_emit(
        self, 
        text: str, 
        cognitive_load: float
    ) -> AsyncGenerator[str, None]:
        """
        追击曲线核心：最速降线节奏控制
        
        高认知负荷 → 慢（人类需要消化时间）
        低认知负荷 → 快（减少等待焦虑）
        
        公式源自摆线参数方程的速度分量：
        v ∝ sqrt(1 - cos(θ))，这里简化为认知负荷的反比函数
        
        Args:
            text: 要输出的文本
            cognitive_load: 认知负荷 (0.0-1.0)
            
        Yields:
            单个字符，按节奏延迟输出
        """
        # 计算节奏因子（非线性映射）
        # load=0.9 → 延迟×3; load=0.1 → 延迟×0.5
        rhythm_factor = self.rhythm_min_factor + \
                      (self.rhythm_max_factor - self.rhythm_min_factor) * \
                      (cognitive_load ** self.rhythm_exponent)
        
        delay = self.base_latency * rhythm_factor
        
        # 逐字符输出（模拟流式输出）
        for char in text:
            yield char
            await asyncio.sleep(delay)


# =============================================================================
# 最小验证用例
# =============================================================================

async def demo():
    """演示：离散步骤如何被对齐为连续流"""
    
    async def mock_ai_steps() -> AsyncGenerator[CognitiveStep, None]:
        """模拟离散、割裂的 AI 原始输出"""
        # 步骤1：高风险发现（高认知负荷）
        yield CognitiveStep(
            content="用户认证模块存在SQL注入风险。",
            cognitive_load=0.9,
            embedding=[0.8, 0.2, 0.1]
        )
        
        # 步骤2：解决方案（低认知负荷，与步骤1相似度高→纯滚动）
        yield CognitiveStep(
            content="建议使用参数化查询修复。",
            cognitive_load=0.3,
            embedding=[0.75, 0.25, 0.15]
        )
        
        # 步骤3：新发现问题（高认知负荷，与步骤2相似度低→需滑动补偿）
        yield CognitiveStep(
            content="另外，日志系统未脱敏，违反GDPR。",
            cognitive_load=0.85,
            embedding=[0.1, 0.9, 0.05]
        )
    
    # 创建对齐器
    aligner = CognitiveManifoldAligner(base_latency_ms=40)
    
    print("=" * 60)
    print("TU-8 认知同频流输出演示")
    print("=" * 60)
    print("\n")
    
    # 执行对齐流
    async for chunk in aligner.align_stream(mock_ai_steps()):
        print(chunk, end="", flush=True)
    
    print("\n\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
