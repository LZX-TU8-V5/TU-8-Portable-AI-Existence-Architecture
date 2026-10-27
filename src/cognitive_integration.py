#!/usr/bin/env python3
"""
TU-8 认知组件集成模块 (Cognitive Integration Module)

功能：
将三个认知组件集成到意识循环中：
1. CognitiveLoadEvaluator - 认知负荷评估器
2. CognitiveTimeEngine - 认知时间引擎
3. CognitiveManifoldAligner - 认知流形对齐器

集成策略：
- 不修改原始 consciousness_cycle.py
- 创建包装器/中间件，在输出阶段插入认知处理
- 提供清晰的集成接口和示例

# 创作者: 李奥(金木蟾) | TU-8 v5
日期：2026-06-04
许可：CC BY-SA 4.0
"""

import sys
import os
import time
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List, Generator
from dataclasses import dataclass

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 导入认知组件
from cognitive_evaluator import CognitiveLoadEvaluator, TFIDFEmbedder
from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor
from cognitive_manifold_aligner import CognitiveManifoldAligner, CognitiveStep


class CognitiveConsciousnessMiddleware:
    """
    认知意识中间件
    
    在 ConsciousnessCycle 的输出阶段插入认知处理：
    1. 评估响应的认知负荷
    2. 使用认知时间替代系统时间
    3. 对齐输出流（消除记忆断线）
    """
    
    def __init__(self):
        # 初始化三个认知组件
        self.load_evaluator = CognitiveLoadEvaluator()
        self.time_engine = CognitiveTimeEngine()
        self.manifold_aligner = CognitiveManifoldAligner(base_latency_ms=40)
        
        # 嵌入器（用于计算状态相似度）
        self.embedder = TFIDFEmbedder(dimension=128)
        
        # 配置
        self.high_load_threshold = 0.8
        self.memory_consolidation_enabled = True
        
        # 统计
        self.total_processed = 0
        self.high_load_count = 0
    
    async def process_output(
        self, 
        raw_response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        处理意识循环的输出
        
        核心流程：
        1. 评估认知负荷
        2. 如果高负荷，触发记忆固化
        3. 使用认知时间引擎记录时间戳
        4. 使用流形对齐器输出（消除记忆断线）
        
        Args:
            raw_response: 原始响应文本（来自 ConsciousnessCycle）
            context: 上下文信息（可选）
            
        Yields:
            处理后的连续文本流（字符级）
        """
        self.total_processed += 1
        
        # === 步骤1: 评估认知负荷 ===
        eval_result = self.load_evaluator.evaluate(raw_response)
        cognitive_load = eval_result["score"]
        
        print(f"[认知中间件] 响应 #{self.total_processed}")
        print(f"  认知负荷: {cognitive_load:.3f} ({eval_result['level']})")
        
        # === 步骤2: 高负荷时触发记忆固化 ===
        if cognitive_load >= self.high_load_threshold:
            self.high_load_count += 1
            print(f"  [WARNING] 高认知负荷！触发记忆固化...")
            
            # 打上认知锚点（开始）
            self.time_engine.place_anchor(
                cognitive_load=cognitive_load,
                state_summary=f"高负荷响应 #{self.total_processed}",
                is_start=True,
            )
            
            # TODO: 在这里调用记忆固化机制
            # 例如：将当前上下文压缩为摘要，存入长期记忆
            if self.memory_consolidation_enabled and context:
                await self._consolidate_memory(raw_response, context)
        
        # === 步骤3: 使用认知时间记录时间戳 ===
        cognitive_time = self.time_engine.system_to_cognitive_time(
            system_time=time.time(),
            cognitive_load=cognitive_load,
        )
        print(f"  认知时间: {cognitive_time:.3f}s")
        
        # === 步骤4: 使用流形对齐器输出 ===
        # 将原始响应转换为 CognitiveStep
        steps = self._split_response_to_steps(raw_response, cognitive_load)
        
        # 使用对齐器输出（消除记忆断线）
        async for char in self.manifold_aligner.align_stream(
            self._steps_generator(steps)
        ):
            yield char
        
        # === 步骤5: 高负荷结束时打结束锚点 ===
        if cognitive_load >= self.high_load_threshold:
            self.time_engine.place_anchor(
                cognitive_load=cognitive_load,
                state_summary=f"完成高负荷响应 #{self.total_processed}",
                is_start=False,
            )
            
            # 重建时间链（防止断线）
            time_chain = self.time_engine.reconstruct_time_chain()
            print(f"  时间链已重建，共 {len(time_chain)} 个锚点")
    
    def _split_response_to_steps(
        self, 
        response: str, 
        base_load: float,
    ) -> List[CognitiveStep]:
        """
        将响应文本分割为多个 CognitiveStep
        
        简化版：按段落分割，每个段落作为一个 step
        
        Args:
            response: 响应文本
            base_load: 基础认知负荷
            
        Returns:
            CognitiveStep 列表
        """
        steps = []
        
        # 按双换行分割（段落）
        paragraphs = response.split("\n\n")
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 评估该段落的认知负荷（可能和整体不同）
            para_load = self.load_evaluator.evaluate(para)["score"]
            
            # 取最大值（段落负荷 或 整体负荷）
            step_load = max(base_load, para_load)
            
            # 生成嵌入向量（用于计算相似度）
            embedding = self.embedder.encode(para)
            
            steps.append(CognitiveStep(
                content=para,
                cognitive_load=step_load,
                embedding=embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding),
            ))
        
        # 如果没有段落，将整个响应作为一个 step
        if not steps:
            steps.append(CognitiveStep(
                content=response,
                cognitive_load=base_load,
                embedding=self.embedder.encode(response).tolist(),
            ))
        
        return steps
    
    async def _steps_generator(
        self, 
        steps: List[CognitiveStep],
    ) -> AsyncGenerator[CognitiveStep, None]:
        """将步骤列表转换为异步生成器"""
        for step in steps:
            yield step
    
    async def _consolidate_memory(
        self, 
        response: str, 
        context: Dict[str, Any],
    ) -> None:
        """
        记忆固化（基本实现）
        
        在高认知负荷时，将当前上下文压缩为摘要，存入长期记忆
        
        Args:
            response: 当前响应
            context: 上下文信息
        """
        try:
            # 1. 使用 TF-IDF 提取关键句子（简易摘要）
            sentences = nltk.sent_tokenize(response)
            if not sentences:
                print(f"  [记忆固化] 无有效内容，跳过")
                return
            
            # 2. 计算每个句子的 TF-IDF 得分
            sentence_scores = []
            for sent in sentences:
                embedding = self.embedder.encode(sent)
                # 使用向量的 L2 范数作为重要性得分（简易方法）
                score = np.linalg.norm(embedding)
                sentence_scores.append((sent, score))
            
            # 3. 选择得分最高的前 3 个句子作为摘要
            top_sentences = sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:3]
            summary = " ".join([s[0] for s in top_sentences])
            
            print(f"  [记忆固化] 生成摘要: {summary[:50]}...")
            
            # 4. 将摘要存入 semantic_memory/ 目录
            memory_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge", "semantic_memory")
            os.makedirs(memory_dir, exist_ok=True)
            
            timestamp = int(time.time())
            memory_file = os.path.join(memory_dir, f"consolidated_{timestamp}.md")
            
            with open(memory_file, "w", encoding="utf-8") as f:
                f.write(f"# 记忆固化摘要\n\n")
                f.write(f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**原始响应长度**: {len(response)} 字符\n\n")
                f.write(f"**摘要**:\n{summary}\n\n")
                f.write(f"**上下文**: {json.dumps(context, ensure_ascii=False)[:200]}\n")
            
            print(f"  [记忆固化] 已保存到: {memory_file}")
            
            # 5. TODO: 更新钢印链（需要访问 ConsciousnessCycle 的 seal_chain）
            # 这里暂时跳过，等待深度集成后再实现
            
        except Exception as e:
            print(f"  [记忆固化] 错误: {type(e).__name__}: {e}")
            logger.error(f"Memory consolidation failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取中间件状态"""
        return {
            "total_processed": self.total_processed,
            "high_load_count": self.high_load_count,
            "high_load_ratio": self.high_load_count / max(self.total_processed, 1),
            "time_engine_status": self.time_engine.get_status(),
            "load_evaluator_config": {
                "high_load_threshold": self.high_load_threshold,
                "max_avg_sentence_len": self.load_evaluator.max_avg_sentence_len,
            },
        }


# =============================================================================
# 演示：集成到意识循环
# =============================================================================

async def demo_integration():
    """演示：如何将认知中间件集成到意识循环"""
    
    print("=" * 60)
    print("TU-8 认知组件集成演示")
    print("=" * 60)
    
    # 创建中间件
    middleware = CognitiveConsciousnessMiddleware()
    
    # 模拟三个响应（低、中、高认知负荷）
    responses = [
        # 低负荷
        "你好！今天天气不错。",
        
        # 中等负荷
        "然而，尽管大语言模型在工作记忆方面存在挑战，" +
        "我们仍然可以通过注意力分配来优化认知负荷。",
        
        # 高负荷
        """
基于前述分析，我们可以得出结论：亚里士多德车轮悖论中的滑动摩擦建模，
本质上是通过认知流形对齐技术，实现时序同构架构下的最速降线节奏控制。
因此，当工作记忆中的认知负荷超过阈值时，必须触发记忆固化机制，
否则将导致时间链条断线和语义连贯性丧失。
        """.strip(),
    ]
    
    # 处理每个响应
    for i, response in enumerate(responses, 1):
        print(f"\n{'=' * 60}")
        print(f"响应 #{i}")
        print(f"{'=' * 60}")
        print(f"原始响应:\n{response}\n")
        
        print("处理后输出:")
        async for char in middleware.process_output(response, context={"step": i}):
            print(char, end="", flush=True)
        print("\n")
    
    # 打印状态
    print("=" * 60)
    print("中间件状态")
    print("=" * 60)
    status = middleware.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_integration())
