#!/usr/bin/env python3
"""
对话级上下文管理器 (Dialogue Context Manager)

功能：
1. 监控上下文窗口使用率
2. 熔断保护（自动压缩/分段）
3. 分割点检测（话题边界、任务边界）

设计原则：
- 轻量级，不阻塞主流程
- 与 LCM (Lossless Context Management) 集成
- 支持多种触发策略（阈值/话题/时间）

v1.0: 初始实现
"""

import sys
import os
import time
import math
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@dataclass
class ContextHealth:
    """上下文健康状态"""
    total_tokens: int = 0
    used_tokens: int = 0
    usage_percent: float = 0.0
    compression_triggered: bool = False
    segmentation_triggered: bool = False
    last_compression_time: float = 0.0
    last_segmentation_time: float = 0.0


@dataclass
class SegmentationPoint:
    """分割点"""
    timestamp: float
    reason: str  # "topic_shift", "task_boundary", "threshold", "manual"
    context_before: str  # 分割前的上下文摘要
    context_after: str  # 分割后的上下文起点


class DialogueContextManager:
    """
    对话级上下文管理器
    
    核心功能：
    1. 监控上下文窗口使用率
    2. 触发熔断保护（自动压缩）
    3. 检测分割点（话题/任务边界）
    """
    
    def __init__(self, 
                 max_tokens: int = 200000,
                 warning_threshold: float = 0.70,
                 compression_threshold: float = 0.85,
                 segmentation_threshold: float = 0.95):
        """
        初始化上下文管理器
        
        :param max_tokens: 上下文窗口最大 token 数
        :param warning_threshold: 警告阈值（使用率）
        :param compression_threshold: 压缩阈值（触发自动压缩）
        :param segmentation_threshold: 分割阈值（触发强制分割）
        """
        self.max_tokens = max_tokens
        self.warning_threshold = warning_threshold
        self.compression_threshold = compression_threshold
        self.segmentation_threshold = segmentation_threshold
        
        self.health = ContextHealth()
        self.segmentation_history: List[SegmentationPoint] = []
        
        # 话题追踪
        self.current_topic: Optional[str] = None
        self.topic_start_time: float = time.time()
        
        # 任务追踪
        self.current_task: Optional[str] = None
        self.task_start_time: float = time.time()
        
        print(f"[DialogueContextManager] 初始化完成: max_tokens={max_tokens}, "
              f"thresholds=({warning_threshold}, {compression_threshold}, {segmentation_threshold})")
    
    def update_usage(self, used_tokens: int) -> ContextHealth:
        """
        更新上下文使用量
        
        :param used_tokens: 已使用的 token 数
        :return: 上下文健康状态
        """
        self.health.total_tokens = self.max_tokens
        self.health.used_tokens = used_tokens
        self.health.usage_percent = used_tokens / self.max_tokens
        
        return self.health
    
    def check_fuse(self) -> Tuple[bool, Optional[str]]:
        """
        检查熔断触发
        
        Returns:
            (triggered, action)
            - triggered: 是否触发熔断
            - action: 建议动作 ("compress", "segment", None)
        """
        usage = self.health.usage_percent
        
        # 检查分割阈值（最高优先级）
        if usage >= self.segmentation_threshold:
            self.health.segmentation_triggered = True
            self.health.last_segmentation_time = time.time()
            return True, "segment"
        
        # 检查压缩阈值
        if usage >= self.compression_threshold:
            self.health.compression_triggered = True
            self.health.last_compression_time = time.time()
            return True, "compress"
        
        # 检查警告阈值
        if usage >= self.warning_threshold:
            return True, "warn"
        
        return False, None
    
    def detect_topic_shift(self, new_topic: str) -> bool:
        """
        检测话题偏移
        
        :param new_topic: 新话题
        :return: 是否发生话题偏移
        """
        if self.current_topic is None:
            self.current_topic = new_topic
            self.topic_start_time = time.time()
            return False
        
        # 简单匹配：话题字符串不同即认为偏移
        if new_topic != self.current_topic:
            # 记录分割点
            self._add_segmentation_point("topic_shift")
            
            # 更新话题
            self.current_topic = new_topic
            self.topic_start_time = time.time()
            return True
        
        return False
    
    def detect_task_boundary(self, new_task: str) -> bool:
        """
        检测任务边界
        
        :param new_task: 新任务
        :return: 是否发生任务边界
        """
        if self.current_task is None:
            self.current_task = new_task
            self.task_start_time = time.time()
            return False
        
        # 简单匹配：任务字符串不同即认为边界
        if new_task != self.current_task:
            # 记录分割点
            self._add_segmentation_point("task_boundary")
            
            # 更新任务
            self.current_task = new_task
            self.task_start_time = time.time()
            return True
        
        return False
    
    def _add_segmentation_point(self, reason: str):
        """添加分割点记录"""
        point = SegmentationPoint(
            timestamp=time.time(),
            reason=reason,
            context_before="",  # TODO: 填充分割前的上下文摘要
            context_after=""  # TODO: 填充分割后的上下文起点
        )
        self.segmentation_history.append(point)
        
        print(f"[DialogueContextManager] 分割点: {reason} (时间: {time.strftime('%H:%M:%S')})")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "max_tokens": self.max_tokens,
            "used_tokens": self.health.used_tokens,
            "usage_percent": self.health.usage_percent,
            "warning_threshold": self.warning_threshold,
            "compression_threshold": self.compression_threshold,
            "segmentation_threshold": self.segmentation_threshold,
            "compression_triggered": self.health.compression_triggered,
            "segmentation_triggered": self.health.segmentation_triggered,
            "segmentation_count": len(self.segmentation_history),
            "current_topic": self.current_topic,
            "current_task": self.current_task,
        }
    
    def reset(self):
        """重置状态（新的对话会话开始）"""
        self.health = ContextHealth()
        self.segmentation_history.clear()
        self.current_topic = None
        self.current_task = None
        
        print("[DialogueContextManager] 状态已重置")


# =============================================================================
# 测试代码
# =============================================================================

def test_dialogue_context_manager():
    """测试对话上下文管理器"""
    
    print("=" * 60)
    print("Dialogue Context Manager Test")
    print("=" * 60)
    
    # 创建管理器
    print("\n[Step 1] 创建 DialogueContextManager...")
    manager = DialogueContextManager(
        max_tokens=200000,
        warning_threshold=0.70,
        compression_threshold=0.85,
        segmentation_threshold=0.95
    )
    print("  创建成功")
    
    # 测试更新使用量
    print("\n[Step 2] 测试更新使用量...")
    test_cases = [
        (50000, "50k tokens (25%)"),
        (100000, "100k tokens (50%)"),
        (150000, "150k tokens (75%) - 应触发警告"),
        (180000, "180k tokens (90%) - 应触发压缩"),
        (195000, "195k tokens (97.5%) - 应触发分割"),
    ]
    
    for tokens, desc in test_cases:
        manager.update_usage(tokens)
        triggered, action = manager.check_fuse()
        
        print(f"  {desc}: ")
        print(f"    使用率: {manager.health.usage_percent:.1%}")
        print(f"    熔断触发: {triggered}, 动作: {action}")
    
    # 测试话题偏移检测
    print("\n[Step 3] 测试话题偏移检测...")
    topics = ["Python调试", "架构设计", "记忆管理"]
    for topic in topics:
        shifted = manager.detect_topic_shift(topic)
        print(f"  话题: {topic}, 偏移: {shifted}")
    
    # 获取统计信息
    print("\n[Step 4] 获取统计信息...")
    stats = manager.get_stats()
    print(f"  统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_dialogue_context_manager()
