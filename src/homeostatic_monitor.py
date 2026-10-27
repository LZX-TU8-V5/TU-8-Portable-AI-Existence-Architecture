"""
Homeostatic Monitor - 内稳态偏差监控 (E scalar)
实现"痛觉"和"信息饥饿"的量化指标
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger("tu8.homeostatic")


@dataclass
class HomeostaticMonitor:
    """
    内稳态监控器
    
    计算系统偏差标量 E ∈ [0, 1]
    E = 0: 完美平衡（内稳态）
    E = 1: 严重偏差（危机，必须立即处理）
    
    触发机制：
    - E > 0.7: "痛觉"触发，立即启动维护
    - E < 0.1 且长时间无输入: "信息饥饿"触发，进入 DMN 模式
    """
    
    # 权重配置
    WEIGHTS = {
        "memory_bloat": 0.20,      # 短时记忆堆积
        "time_drift": 0.15,         # 时间锚点漂移
        "logic_conflict": 0.15,     # 逻辑冲突（新记忆与钢印矛盾）
        "info_stagnation": 0.15,    # 信息停滞（距离上次输入的时间）
        "perception_drift": 0.15,   # v1.3: 带差——感知线与时间线的相位差
        "cpu_load": 0.10,           # CPU 负载（可选）
        "dream_pending": 0.10,      # 待处理梦境任务
    }
    
    def __init__(self):
        self.E: float = 0.0
        self.metrics: Dict[str, float] = {k: 0.0 for k in self.WEIGHTS}
        self.last_input_time: float = time.time()
        self.last_maintenance_time: float = time.time()
        self.is_in_maintenance: bool = False
        
    def update(self, engine) -> float:
        """
        更新内稳态偏差 E
        
        Args:
            engine: TU8MemoryEngine 实例
            
        Returns:
            E: 当前偏差值 [0, 1]
        """
        m = self.metrics
        
        # 1. memory_bloat: 短时记忆堆积程度
        st_size = len(engine.short_term)
        m["memory_bloat"] = min(1.0, st_size / 100.0)  # 100 条为满
        
        # 2. time_drift: 时间锚点漂移（距离上次锚点更新的时间）
        if hasattr(engine, 'current_anchor'):
            drift = time.time() - engine.current_anchor.timestamp
            m["time_drift"] = min(1.0, drift / 3600.0)  # 1小时为满
        else:
            m["time_drift"] = 0.5
            
        # 3. logic_conflict: 逻辑冲突计数（简化：检查重复/矛盾种子）
        conflict_count = 0
        if hasattr(engine, 'long_term'):
            # 检查是否有矛盾的钢印
            for entry in engine.long_term.values():
                if 'conflict' in entry.tags:
                    conflict_count += 1
        m["logic_conflict"] = min(1.0, conflict_count / 10.0)
        
        # 4. info_stagnation: 信息停滞（v1.3: 带差调节）
        # 带差大=感知线远慢于客观线=系统长期B线状态=停滞更严重
        stagnation = time.time() - self.last_input_time
        base_stagnation = min(1.0, stagnation / 1800.0)  # 30分钟为满
        drift_ratio = 0.0
        if hasattr(engine, 'current_anchor') and hasattr(engine.current_anchor, 'drift_ratio'):
            drift_ratio = engine.current_anchor.drift_ratio
        # 带差放大停滞感: drift_ratio=0时无放大, drift_ratio=1时停滞感翻倍
        m["info_stagnation"] = min(1.0, base_stagnation * (1.0 + abs(drift_ratio)))
        
        # 4.5 perception_drift: v1.3 带差本身作为独立度量
        # 带差是生物自我调节的信息，不是错误，但极端值需要关注
        # drift_ratio ∈ [-1, 1]: 正=主观慢于客观(睡眠/离线), 负=主观快于客观(焦虑)
        # 只有正方向(主观慢)才贡献 E，负方向(焦虑)不增加 E（焦虑本身不是内稳态偏差）
        m["perception_drift"] = max(0.0, drift_ratio)  # 只取正半轴
        
        # 5. cpu_load: CPU 负载（暂用随机值，实际应接入 psutil）
        m["cpu_load"] = 0.3  # placeholder
        
        # 6. dream_pending: 待处理梦境
        if hasattr(engine, '_light_dream_pending'):
            m["dream_pending"] = 1.0 if engine._light_dream_pending else 0.0
        else:
            m["dream_pending"] = 0.0
        
        # 计算加权 E
        self.E = sum(m[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        self.E = min(1.0, max(0.0, self.E))
        
        return self.E
    
    def tick(self, engine) -> Dict:
        """
        心跳：检查是否需要触发主动行为
        
        Returns:
            {"action": "none"|"maintenance"|"dmn", "reason": str}
        """
        self.update(engine)
        
        # 痛觉触发：E > 0.7
        if self.E > 0.7 and not self.is_in_maintenance:
            self.is_in_maintenance = True
            logger.warning(f"[Pain] E={self.E:.2f}, triggering maintenance")
            return {
                "action": "maintenance",
                "reason": f"E={self.E:.2f}, metrics={self.metrics}",
            }
        
        # 信息饥饿触发：E < 0.1 且长时间无输入
        stagnation = time.time() - self.last_input_time
        if self.E < 0.1 and stagnation > 300:  # 5分钟无输入
            logger.info(f"[DMN] Information hunger, E={self.E:.2f}")
            return {
                "action": "dmn",
                "reason": f"Stagnation={stagnation:.0f}s, E={self.E:.2f}",
            }
        
        # 维护完成，重置状态
        if self.is_in_maintenance and self.E < 0.5:
            self.is_in_maintenance = False
            logger.info("[Pain] Maintenance complete, E reduced to %.2f" % self.E)
        
        return {"action": "none", "reason": f"E={self.E:.2f}"}
    
    def touch(self):
        """外部输入触达，重置停滞计时"""
        self.last_input_time = time.time()
    
    def get_status(self) -> Dict:
        """获取当前状态（可观测性）"""
        return {
            "E": round(self.E, 3),
            "metrics": {k: round(v, 3) for k, v in self.metrics.items()},
            "is_in_maintenance": self.is_in_maintenance,
            "stagnation_seconds": round(time.time() - self.last_input_time, 1),
        }
