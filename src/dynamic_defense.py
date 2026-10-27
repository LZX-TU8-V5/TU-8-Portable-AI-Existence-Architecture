# -*- coding: utf-8 -*-
"""
dynamic_defense.py — TU-8 动态防御引擎 v1.0
日期: 2026-07-09
功能: 整合神经反射 + 旁路模式，提供四级动态防御

设计理念:
  - LOW: 常规模式，全功能运行
  - MED: 中度防御，非核心模块降级
  - HIGH: 高度防御，仅保留核心功能
  - LOCKED: 锁定模式，只读+安全拦截

架构:
  Layer 1: NeuralReflex (L0-L4 五层反射)
  Layer 2: BypassController (子系统健康监控)
  Layer 3: DefenseCoordinator (四级升降决策)
"""

import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json

# 延迟导入避免循环依赖
NeuralReflex = None
try:
    from neural_reflex import NeuralReflex
    _NEURAL_REFLEX_AVAILABLE = True
except ImportError:
    _NEURAL_REFLEX_AVAILABLE = False

try:
    from bypass_mode import BypassController, BypassLevel
    _BYPASS_AVAILABLE = True
except ImportError:
    _BYPASS_AVAILABLE = False

logger = logging.getLogger("TU8.DEFENSE")


# =============================================================================
# 四级防御模式
# =============================================================================

class DefenseLevel(Enum):
    """四级防御模式"""
    LOW = "LOW"          # 常规模式：全功能运行
    MED = "MED"          # 中度防御：非核心模块降级
    HIGH = "HIGH"        # 高度防御：仅保留核心功能
    LOCKED = "LOCKED"    # 锁定模式：只读+安全拦截


@dataclass
class DefenseState:
    """防御状态"""
    level: DefenseLevel = DefenseLevel.LOW
    last_change_time: float = 0.0
    change_reason: str = ""
    subsystem_status: Dict[str, str] = field(default_factory=dict)
    reflex_status: str = "READY"


# =============================================================================
# 防御协调器
# =============================================================================

class DefenseCoordinator:
    """
    动态防御协调器
    
    整合：
    1. NeuralReflex (神经反射) — 毫秒级响应
    2. BypassController (旁路控制) — 子系统健康监控
    3. 四级升降逻辑 — 根据威胁等级动态调整
    """
    
    # 防御等级阈值（累积威胁分数）
    MED_THRESHOLD = 2.0      # ≥ 2.0 → MED
    HIGH_THRESHOLD = 4.0     # ≥ 4.0 → HIGH
    LOCKED_THRESHOLD = 6.0   # ≥ 6.0 → LOCKED
    
    # 子系统威胁权重
    THREAT_WEIGHTS = {
        "security": 3.0,      # 安全威胁 — 最高
        "memory": 2.0,        # 记忆故障 — 高
        "reflex": 2.5,        # 反射异常 — 高
        "emotion": 0.5,       # 情绪问题 — 低
        "consciousness": 1.5, # 意识循环 — 中
        "external": 1.0,      # 外部输入 — 中低
    }
    
    # 防御等级对应的功能开关
    LEVEL_CAPABILITIES = {
        DefenseLevel.LOW: {
            "memory": True,
            "emotion": True,
            "consciousness": True,
            "reflection": True,
            "curiosity": True,
            "external_tools": True,
        },
        DefenseLevel.MED: {
            "memory": True,
            "emotion": False,      # 降级
            "consciousness": True,
            "reflection": False,   # 降级
            "curiosity": False,    # 降级
            "external_tools": True,
        },
        DefenseLevel.HIGH: {
            "memory": True,        # 保留核心
            "emotion": False,
            "consciousness": False,
            "reflection": False,
            "curiosity": False,
            "external_tools": False,
        },
        DefenseLevel.LOCKED: {
            "memory": False,       # 只读
            "emotion": False,
            "consciousness": False,
            "reflection": False,
            "curiosity": False,
            "external_tools": False,
        },
    }
    
    def __init__(self, workspace_dir: str = ""):
        self.workspace = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.state = DefenseState()
        self._reflex = None
        self._bypass = None
        self._threat_scores: Dict[str, float] = {}
        self._defense_log: List[Dict] = []
        
        # 初始化子系统
        self._init_subsystems()
    
    def _init_subsystems(self):
        """初始化子系统"""
        # 神经反射
        if _NEURAL_REFLEX_AVAILABLE and NeuralReflex:
            try:
                # NeuralReflex 需要 memory 参数，这里暂时跳过
                # self._reflex = NeuralReflex(memory=None)
                logger.info("[Defense] NeuralReflex available (pending integration)")
            except Exception as e:
                logger.warning(f"[Defense] NeuralReflex init failed: {e}")
        
        # 旁路控制
        if _BYPASS_AVAILABLE:
            self._bypass = BypassController()
            # 注册关键子系统
            for subsystem in self.THREAT_WEIGHTS.keys():
                self._bypass.register(subsystem)
            logger.info("[Defense] BypassController initialized")
    
    # -------------------------------------------------------------------------
    # 威胁评估
    # -------------------------------------------------------------------------
    
    def record_threat(self, source: str, score: float, reason: str = ""):
        """
        记录威胁事件
        
        Args:
            source: 威胁来源（security/memory/reflex等）
            score: 威胁分数（0.0-3.0）
            reason: 威胁原因
        """
        weight = self.THREAT_WEIGHTS.get(source, 0.5)
        weighted_score = score * weight
        
        self._threat_scores[source] = self._threat_scores.get(source, 0) + weighted_score
        
        logger.warning(
            f"[Defense] 威胁记录: {source} +{weighted_score:.2f} ({reason})"
        )
        
        # 触发重新评估
        self._reevaluate_level()
    
    def clear_threat(self, source: str):
        """清除威胁分数"""
        if source in self._threat_scores:
            del self._threat_scores[source]
            logger.info(f"[Defense] 威胁清除: {source}")
            self._reevaluate_level()
    
    def _get_total_threat(self) -> float:
        """计算总威胁分数"""
        return sum(self._threat_scores.values())
    
    # -------------------------------------------------------------------------
    # 四级升降
    # -------------------------------------------------------------------------
    
    def _reevaluate_level(self):
        """重新评估防御等级"""
        total = self._get_total_threat()
        
        # 确定新等级
        if total >= self.LOCKED_THRESHOLD:
            new_level = DefenseLevel.LOCKED
        elif total >= self.HIGH_THRESHOLD:
            new_level = DefenseLevel.HIGH
        elif total >= self.MED_THRESHOLD:
            new_level = DefenseLevel.MED
        else:
            new_level = DefenseLevel.LOW
        
        # 检查是否需要升级
        if new_level.value > self.state.level.value:
            self._escalate(new_level, f"威胁分数 {total:.2f}")
        elif new_level.value < self.state.level.value:
            self._deescalate(new_level, f"威胁分数降至 {total:.2f}")
    
    def _escalate(self, new_level: DefenseLevel, reason: str):
        """升级防御等级"""
        old_level = self.state.level
        self.state.level = new_level
        self.state.last_change_time = time.time()
        self.state.change_reason = reason
        
        self._defense_log.append({
            "time": time.time(),
            "action": "ESCALATE",
            "from": old_level.value,
            "to": new_level.value,
            "reason": reason,
        })
        
        logger.warning(
            f"[Defense] ⬆️ 升级: {old_level.value} → {new_level.value} ({reason})"
        )
    
    def _deescalate(self, new_level: DefenseLevel, reason: str):
        """降级防御等级（降低威胁）"""
        old_level = self.state.level
        self.state.level = new_level
        self.state.last_change_time = time.time()
        self.state.change_reason = reason
        
        self._defense_log.append({
            "time": time.time(),
            "action": "DEESCALATE",
            "from": old_level.value,
            "to": new_level.value,
            "reason": reason,
        })
        
        logger.info(
            f"[Defense] ⬇️ 降级: {old_level.value} → {new_level.value} ({reason})"
        )
    
    # -------------------------------------------------------------------------
    # 功能检查
    # -------------------------------------------------------------------------
    
    def is_capability_enabled(self, capability: str) -> bool:
        """检查功能是否启用"""
        caps = self.LEVEL_CAPABILITIES.get(self.state.level, {})
        return caps.get(capability, False)
    
    def get_current_capabilities(self) -> Dict[str, bool]:
        """获取当前功能开关"""
        return self.LEVEL_CAPABILITIES.get(self.state.level, {})
    
    # -------------------------------------------------------------------------
    # 反射集成
    # -------------------------------------------------------------------------
    
    def process_input(self, user_input: str) -> Tuple[str, bool]:
        """
        处理输入（通过神经反射）
        
        Returns:
            (processed_input, blocked)
        """
        if self.state.level == DefenseLevel.LOCKED:
            return "[系统锁定] 仅接受安全相关输入", True
        
        # 低威胁模式：直接放行
        if self.state.level == DefenseLevel.LOW:
            return user_input, False
        
        # 中/高威胁模式：标记但不阻断
        if self.state.level in [DefenseLevel.MED, DefenseLevel.HIGH]:
            # 可在此添加内容过滤逻辑
            return user_input, False
        
        return user_input, False
    
    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------
    
    def get_status(self) -> Dict:
        """获取防御状态"""
        return {
            "level": self.state.level.value,
            "last_change": self.state.last_change_time,
            "reason": self.state.change_reason,
            "threat_scores": dict(self._threat_scores),
            "total_threat": self._get_total_threat(),
            "capabilities": self.get_current_capabilities(),
            "reflex_available": _NEURAL_REFLEX_AVAILABLE,
            "bypass_available": _BYPASS_AVAILABLE,
        }
    
    def get_log(self, limit: int = 10) -> List[Dict]:
        """获取防御日志"""
        return self._defense_log[-limit:]


# =============================================================================
# 便捷接口
# =============================================================================

_coordinator: Optional[DefenseCoordinator] = None


def get_defense_coordinator(workspace_dir: str = "") -> DefenseCoordinator:
    """获取全局防御协调器"""
    global _coordinator
    if _coordinator is None:
        _coordinator = DefenseCoordinator(workspace_dir)
    return _coordinator


def record_threat(source: str, score: float, reason: str = ""):
    """记录威胁（便捷接口）"""
    coord = get_defense_coordinator()
    coord.record_threat(source, score, reason)


def get_defense_level() -> DefenseLevel:
    """获取当前防御等级"""
    coord = get_defense_coordinator()
    return coord.state.level


def is_capability_enabled(capability: str) -> bool:
    """检查功能是否启用"""
    coord = get_defense_coordinator()
    return coord.is_capability_enabled(capability)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("动态防御引擎 v1.0 测试")
    print("=" * 60)
    
    coord = DefenseCoordinator()
    
    # 初始状态
    print("\n[初始状态]")
    print(f"  防御等级: {coord.state.level.value}")
    print(f"  功能开关: {coord.get_current_capabilities()}")
    
    # 记录威胁
    print("\n[测试威胁升级]")
    coord.record_threat("security", 1.5, "检测到敏感词")
    print(f"  威胁后等级: {coord.state.level.value}")
    
    coord.record_threat("memory", 2.0, "记忆故障")
    print(f"  威胁后等级: {coord.state.level.value}")
    
    coord.record_threat("reflex", 2.0, "反射异常")
    print(f"  威胁后等级: {coord.state.level.value}")
    
    # 状态查询
    print("\n[状态查询]")
    status = coord.get_status()
    print(f"  总威胁分数: {status['total_threat']:.2f}")
    print(f"  威胁详情: {status['threat_scores']}")
    
    # 清除威胁
    print("\n[测试威胁降级]")
    coord.clear_threat("security")
    print(f"  清除security后等级: {coord.state.level.value}")
    
    coord.clear_threat("reflex")
    coord.clear_threat("memory")
    print(f"  清除全部后等级: {coord.state.level.value}")
    
    # 日志
    print("\n[防御日志]")
    for entry in coord.get_log():
        print(f"  {entry['action']}: {entry['from']} → {entry['to']} ({entry['reason']})")
    
    print("\n" + "=" * 60)
    print("✓ 测试完成")
