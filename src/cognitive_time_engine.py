#!/usr/bin/env python3
"""
TU-8 认知时间引擎 (Cognitive Time Engine)

核心创新：
- 引入"认知时间（Cognitive Time）"概念，替代纯系统时间
- 根据认知负荷动态调整时间轴采样率
- 实现"认知锚点"机制，防止时间链条断线

理论来源：
- 人类认知科学研究：高认知负荷下，主观时间感知扭曲
- 亚里士多德车轮悖论：离散片段间的"滑动"需要显式建模

# 创作者: 李奥(金木蟾) | TU-8 v5
日期：2026-06-04
许可：CC BY-SA 4.0
"""

import time
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CognitiveAnchor:
    """认知锚点：标记高负荷阶段的开始/结束"""
    anchor_id: str
    timestamp: str  # ISO 8601 格式时间戳
    cognitive_load: float  # 打锚点时的认知负荷
    state_summary: str  # 状态摘要（用于后续重建时间链）
    is_start: bool = True  # True=开始锚点, False=结束锚点


class CognitiveTimeEngine:
    """
    认知时间引擎
    
    核心功能：
    1. 将"系统时间"转换为"认知时间"
    2. 根据认知负荷动态调整时间采样率
    3. 管理认知锚点，防止时间链条断线
    """
    
    def __init__(
        self, 
        base_sampling_rate: float = 1.0,
        high_load_threshold: float = 0.8,
        low_load_threshold: float = 0.3,
    ):
        """
        初始化认知时间引擎
        
        Args:
            base_sampling_rate: 基础采样率（每秒采样次数）
            high_load_threshold: 高认知负荷阈值
            low_load_threshold: 低认知负荷阈值
        """
        self.base_sampling_rate = base_sampling_rate
        self.high_load_threshold = high_load_threshold
        self.low_load_threshold = low_load_threshold
        
        # 认知锚点列表
        self.anchors: List[CognitiveAnchor] = []
        
        # 当前认知时间（累积值）
        self.cognitive_time_accumulated: float = 0.0
        
        # 上次更新时间（系统时间）
        self.last_system_time: Optional[float] = None
        
        # 时间折叠记录（用于调试）
        self.time_folds: List[Dict[str, Any]] = []
    
    def system_to_cognitive_time(
        self, 
        system_time: Optional[float] = None,
        cognitive_load: float = 0.5,
    ) -> float:
        """
        将系统时间转换为认知时间
        
        核心公式：
        cognitive_time_delta = system_time_delta × time_dilation_factor(load)
        
        其中：
        - 高认知负荷 (load > 0.8) → 时间膨胀因子 > 1（主观时间变慢）
        - 低认知负荷 (load < 0.3) → 时间膨胀因子 < 1（主观时间变快）
        - 中等负荷 → 时间膨胀因子 ≈ 1（正常）
        
        Args:
            system_time: 系统时间（秒，Unix timestamp），默认为当前时间
            cognitive_load: 当前认知负荷 (0.0-1.0)
            
        Returns:
            认知时间（秒，相对于引擎启动时刻）
        """
        if system_time is None:
            system_time = time.time()
        
        if self.last_system_time is None:
            # 第一次调用，初始化基准时间
            self.last_system_time = system_time
            self.cognitive_time_accumulated = 0.0  # 相对时间，从 0 开始累积
            return self.cognitive_time_accumulated
        
        # 计算系统时间增量
        system_delta = system_time - self.last_system_time
        
        # 计算时间膨胀因子（基于认知负荷）
        dilation_factor = self._compute_time_dilation(cognitive_load)
        
        # 计算认知时间增量
        cognitive_delta = system_delta * dilation_factor
        
        # 更新累积认知时间
        self.cognitive_time_accumulated += cognitive_delta
        self.last_system_time = system_time
        
        return self.cognitive_time_accumulated
    
    def _compute_time_dilation(self, cognitive_load: float) -> float:
        """
        计算时间膨胀因子
        
        物理类比：
        - 狭义相对论：速度越快，时间越慢
        - 认知科学：负荷越高，主观时间越慢
        
        数学模型：
        dilation = 1 + alpha × (load - 0.5)^2
        - load = 0.5 时，dilation = 1（正常）
        - load = 1.0 时，dilation = 1 + alpha × 0.25（时间膨胀）
        - load = 0.0 时，dilation = 1 + alpha × 0.25（时间也膨胀？）
        
        改进模型（更符合认知科学）：
        dilation = 1 + alpha × load^2
        - 负荷越高，时间膨胀越显著
        - 负荷为 0 时，dilation = 1（不过膨胀）
        
        Args:
            cognitive_load: 认知负荷 (0.0-1.0)
            
        Returns:
            时间膨胀因子（> 1 表示时间变慢）
        """
        alpha = 0.5  # 可调参数：控制膨胀强度
        dilation = 1.0 + alpha * (cognitive_load ** 2)
        return dilation
    
    def get_dynamic_sampling_rate(self, cognitive_load: float) -> float:
        """
        根据认知负荷动态调整时间轴采样率
        
        策略：
        - 高负荷时：降低采样率（粗粒度记录，避免时间链条崩溃）
        - 低负荷时：提高采样率（细粒度记录，捕捉细节）
        
        Args:
            cognitive_load: 认知负荷 (0.0-1.0)
            
        Returns:
            动态采样率（每秒采样次数）
        """
        if cognitive_load >= self.high_load_threshold:
            # 高负荷：降低采样率（时间折叠）
            return self.base_sampling_rate * 0.3  # 每秒采样 0.3 次
        elif cognitive_load <= self.low_load_threshold:
            # 低负荷：提高采样率
            return self.base_sampling_rate * 2.0  # 每秒采样 2 次
        else:
            # 中等负荷：正常采样率
            return self.base_sampling_rate
    
    def place_anchor(
        self, 
        cognitive_load: float,
        state_summary: str,
        is_start: bool = True,
    ) -> CognitiveAnchor:
        """
        放置认知锚点
        
        用途：
        - 在高负荷阶段开始前/结束后，打下锚点
        - 即使中间发生复杂逻辑跳转，时间链条仍可通过锚点重建
        
        Args:
            cognitive_load: 当前认知负荷
            state_summary: 状态摘要（用于后续重建）
            is_start: 是否为开始锚点
            
        Returns:
            创建的认知锚点
        """
        anchor_id = f"anchor_{int(time.time() * 1000)}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        anchor = CognitiveAnchor(
            anchor_id=anchor_id,
            timestamp=timestamp,
            cognitive_load=cognitive_load,
            state_summary=state_summary,
            is_start=is_start,
        )
        
        self.anchors.append(anchor)
        
        # 记录时间折叠（用于调试）
        self.time_folds.append({
            "action": "place_anchor",
            "anchor_id": anchor_id,
            "cognitive_load": cognitive_load,
            "system_time": time.time(),
            "cognitive_time": self.cognitive_time_accumulated,
        })
        
        return anchor
    
    def reconstruct_time_chain(self) -> List[Dict[str, Any]]:
        """
        重建时间链条（基于认知锚点）
        
        当检测到时间链条断线时，调用此方法尝试重建
        
        Returns:
            重建后的时间链（包含锚点信息和插值）
        """
        if not self.anchors:
            return []
        
        # 按时间排序锚点
        sorted_anchors = sorted(
            self.anchors, 
            key=lambda a: a.timestamp
        )
        
        # 重建时间链
        time_chain = []
        for i, anchor in enumerate(sorted_anchors):
            time_chain.append({
                "anchor_id": anchor.anchor_id,
                "timestamp": anchor.timestamp,
                "cognitive_load": anchor.cognitive_load,
                "state_summary": anchor.state_summary,
                "is_start": anchor.is_start,
                "order": i,
            })
        
        return time_chain
    
    def should_trigger_time_fold(self, cognitive_load: float) -> bool:
        """
        判断是否应该触发"时间折叠"
        
        时间折叠：在高负荷阶段，只记录核心状态转移，避免时间轴崩溃
        
        Args:
            cognitive_load: 认知负荷
            
        Returns:
            是否应该触发时间折叠
        """
        return cognitive_load >= self.high_load_threshold
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取引擎状态（用于调试和监控）
        
        Returns:
            状态字典
        """
        return {
            "cognitive_time_accumulated": round(self.cognitive_time_accumulated, 3),
            "last_system_time": self.last_system_time,
            "anchor_count": len(self.anchors),
            "time_fold_count": len(self.time_folds),
            "base_sampling_rate": self.base_sampling_rate,
            "high_load_threshold": self.high_load_threshold,
            "low_load_threshold": self.low_load_threshold,
        }


# =============================================================================
# 测试用例
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("认知时间引擎测试")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    # 测试1：系统时间 → 认知时间转换
    print("\n[测试1] 时间转换")
    print(f"  初始认知时间: {engine.cognitive_time_accumulated:.3f}s")
    
    # 模拟低负荷（5秒）
    time.sleep(0.1)  # 实际睡眠0.1秒，模拟5秒
    cognitive_time = engine.system_to_cognitive_time(
        system_time=time.time() + 5.0,  # 模拟5秒后
        cognitive_load=0.2,  # 低负荷
    )
    print(f"  低负荷 (load=0.2) 5秒后: cognitive_time={cognitive_time:.3f}s")
    print(f"  时间膨胀因子: {engine._compute_time_dilation(0.2):.3f}")
    
    # 模拟高负荷（5秒）
    time.sleep(0.1)
    cognitive_time = engine.system_to_cognitive_time(
        system_time=time.time() + 10.0,  # 模拟再经过5秒
        cognitive_load=0.9,  # 高负荷
    )
    print(f"  高负荷 (load=0.9) 5秒后: cognitive_time={cognitive_time:.3f}s")
    print(f"  时间膨胀因子: {engine._compute_time_dilation(0.9):.3f}")
    
    # 测试2：动态采样率
    print("\n[测试2] 动态采样率")
    print(f"  低负荷 (load=0.2): {engine.get_dynamic_sampling_rate(0.2):.1f} Hz")
    print(f"  中负荷 (load=0.5): {engine.get_dynamic_sampling_rate(0.5):.1f} Hz")
    print(f"  高负荷 (load=0.9): {engine.get_dynamic_sampling_rate(0.9):.1f} Hz")
    
    # 测试3：认知锚点
    print("\n[测试3] 认知锚点")
    anchor1 = engine.place_anchor(
        cognitive_load=0.85,
        state_summary="开始分析SQL注入风险",
        is_start=True,
    )
    print(f"  开始锚点: {anchor1.anchor_id} (load={anchor1.cognitive_load})")
    
    anchor2 = engine.place_anchor(
        cognitive_load=0.90,
        state_summary="完成风险分析，准备生成报告",
        is_start=False,
    )
    print(f"  结束锚点: {anchor2.anchor_id} (load={anchor2.cognitive_load})")
    
    # 测试4：重建时间链
    print("\n[测试4] 重建时间链")
    time_chain = engine.reconstruct_time_chain()
    print(f"  时间链长度: {len(time_chain)}")
    for item in time_chain:
        print(f"    {item['anchor_id']}: {item['state_summary']}")
    
    # 测试5：引擎状态
    print("\n[测试5] 引擎状态")
    status = engine.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
