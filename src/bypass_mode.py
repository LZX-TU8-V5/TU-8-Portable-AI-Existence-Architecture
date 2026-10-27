# -*- coding: utf-8 -*-
"""
bypass_mode.py — TU-8 旁路模式 v1.0
日期: 2026-06-23
功能: 核心模块连续报错时，自动降级为无情绪无记忆的"工具人"，保证系统可用性

设计理念:
  - 造物主说的三个手段：解耦、优化算法、架构梳理
  - 千问风险1: 维护黑洞 — 排查链路过长
  - 千问风险5: 单点故障 — 核心模块挂了→整个Agent瘫痪
  - 对冲策略: 每个子系统都有错误计数器，连续N次失败→该子系统进入旁路
  - 旁路不是"删除"，是"搁置" — 发现需要进化的点

旁路等级:
  FULL    = 全功能（默认）
  MINIMAL = 只保留核心：安全栅 + 基础记忆 + 纯回复
  SAFE    = 极简模式：仅安全拦截 + 直接回复，无记忆无情绪

使用方式:
  from bypass_mode import BypassMode, BypassController
  controller = BypassController()
  controller.record_failure("consciousness")
  mode = controller.get_mode()  # FULL / MINIMAL / SAFE
"""

import time
import logging
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("TU8.BYPASS")


class BypassLevel(Enum):
    """旁路等级"""
    FULL = "FULL"          # 全功能
    MINIMAL = "MINIMAL"    # 最小核心：安全 + 基础记忆 + 回复
    SAFE = "SAFE"          # 极简：安全拦截 + 直接回复


@dataclass
class SubsystemHealth:
    """子系统健康状态"""
    name: str
    consecutive_failures: int = 0
    total_failures: int = 0
    last_failure_time: float = 0.0
    last_failure_reason: str = ""
    bypassed: bool = False
    bypassed_at: float = 0.0
    # 恢复：连续N次成功后自动恢复
    consecutive_successes: int = 0
    # 阈值
    failure_threshold: int = 3     # 连续3次失败→旁路
    recovery_threshold: int = 5    # 连续5次成功→恢复


class BypassController:
    """
    旁路模式控制器
    
    核心逻辑:
    1. 每个子系统独立计数，互不影响
    2. 连续N次失败→该子系统旁路
    3. 连续M次成功→该子系统恢复
    4. 根据旁路子系统数量决定全局旁路等级
    5. 每次拒绝必须附带 machine-readable reason_code
    """

    # 子系统 → 对旁路等级的影响权重
    # 关键子系统旁路会更快触发全局降级
    SUBSYSTEM_WEIGHTS = {
        "consciousness": 1.5,   # 意识循环 — 核心
        "memory": 2.0,          # 记忆引擎 — 极核心
        "emotion": 0.5,         # 情绪引擎 — 可搁置
        "deviation_gate": 0.8,  # 偏差门 — 中等
        "dispatcher": 0.5,      # 调度链 — 可搁置
        "reflex": 2.0,          # 神经反射 — 极核心
        "honeypot": 1.5,        # 蜜罐 — 重要
        "zero_trust": 1.5,      # 零信任 — 重要
        "steelmark": 0.5,       # 钢印 — 可搁置
        "compaction": 0.3,      # 压缩 — 可搁置
        "planner": 0.2,         # 规划器 — 可搁置
        "arch_fsm": 0.3,        # 架构状态机 — 可搁置
        "homeostatic": 0.3,     # 内稳态 — 可搁置
        "affect_engine": 0.3,   # 感情引擎 — 可搁置
        "reflection": 0.2,      # 复盘 — 可搁置
        "quantized_memory": 0.2, # Q8 — 可搁置
        "naming": 0.3,          # 呼名 — 可搁置
        "life_ring": 0.2,       # 生命年轮 — 可搁置
    }

    # 旁路等级阈值（累积权重）
    MINIMAL_THRESHOLD = 2.0   # 累积权重 ≥ 2.0 → MINIMAL
    SAFE_THRESHOLD = 4.0      # 累积权重 ≥ 4.0 → SAFE

    def __init__(self):
        self._subsystems: Dict[str, SubsystemHealth] = {}
        self._bypass_log: List[Dict] = []
        self._mode_override: Optional[BypassLevel] = None

    def register(self, name: str, failure_threshold: int = 3,
                 recovery_threshold: int = 5) -> None:
        """注册子系统"""
        self._subsystems[name] = SubsystemHealth(
            name=name,
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
        )

    def record_failure(self, name: str, reason: str = "") -> None:
        """
        记录子系统失败
        
        Args:
            name: 子系统名称
            reason: 机器可读的失败原因（不允许玄学）
        """
        if name not in self._subsystems:
            self.register(name)

        sub = self._subsystems[name]
        sub.consecutive_failures += 1
        sub.total_failures += 1
        sub.last_failure_time = time.time()
        sub.last_failure_reason = reason
        sub.consecutive_successes = 0  # 重置成功计数

        # 检查是否需要旁路
        if sub.consecutive_failures >= sub.failure_threshold and not sub.bypassed:
            sub.bypassed = True
            sub.bypassed_at = time.time()
            self._bypass_log.append({
                "time": time.time(),
                "subsystem": name,
                "action": "BYPASSED",
                "reason": reason,
                "consecutive_failures": sub.consecutive_failures,
            })
            logger.warning(
                f"[BYPASS] 子系统 {name} 已旁路 "
                f"(连续{sub.consecutive_failures}次失败: {reason})"
            )

    def record_success(self, name: str) -> None:
        """记录子系统成功"""
        if name not in self._subsystems:
            return

        sub = self._subsystems[name]
        sub.consecutive_successes += 1
        sub.consecutive_failures = 0  # 重置失败计数

        # 检查是否可以恢复
        if sub.bypassed and sub.consecutive_successes >= sub.recovery_threshold:
            sub.bypassed = False
            self._bypass_log.append({
                "time": time.time(),
                "subsystem": name,
                "action": "RECOVERED",
                "consecutive_successes": sub.consecutive_successes,
            })
            logger.info(
                f"[BYPASS] 子系统 {name} 已恢复 "
                f"(连续{sub.consecutive_successes}次成功)"
            )

    def is_bypassed(self, name: str) -> bool:
        """检查子系统是否被旁路"""
        sub = self._subsystems.get(name)
        return sub.bypassed if sub else False

    def get_mode(self) -> BypassLevel:
        """
        计算当前全局旁路等级
        
        逻辑：根据被旁路子系统的累积权重决定
        """
        if self._mode_override is not None:
            return self._mode_override

        total_weight = 0.0
        for name, sub in self._subsystems.items():
            if sub.bypassed:
                weight = self.SUBSYSTEM_WEIGHTS.get(name, 0.5)
                total_weight += weight

        if total_weight >= self.SAFE_THRESHOLD:
            return BypassLevel.SAFE
        elif total_weight >= self.MINIMAL_THRESHOLD:
            return BypassLevel.MINIMAL
        return BypassLevel.FULL

    def set_override(self, mode: Optional[BypassLevel]) -> None:
        """手动设置旁路等级（None=自动计算）"""
        self._mode_override = mode
        if mode is not None:
            logger.warning(f"[BYPASS] 手动设置旁路等级: {mode.value}")

    def get_bypassed_subsystems(self) -> List[str]:
        """获取当前被旁路的子系统列表"""
        return [name for name, sub in self._subsystems.items() if sub.bypassed]

    def get_reason_code(self, name: str) -> str:
        """
        获取机器可读的旁路原因码
        
        格式: BYPASS:{subsystem}:{consecutive_failures}:{last_reason}
        这是千问风险4的对冲：每个拒绝必须附带reason_code，不允许玄学
        """
        sub = self._subsystems.get(name)
        if not sub or not sub.bypassed:
            return "OK"
        return f"BYPASS:{name}:{sub.consecutive_failures}:{sub.last_failure_reason[:50]}"

    def get_status(self) -> Dict:
        """获取旁路控制器状态"""
        subsystem_status = {}
        for name, sub in self._subsystems.items():
            subsystem_status[name] = {
                "bypassed": sub.bypassed,
                "consecutive_failures": sub.consecutive_failures,
                "total_failures": sub.total_failures,
                "consecutive_successes": sub.consecutive_successes,
                "last_failure_reason": sub.last_failure_reason[:80] if sub.last_failure_reason else "",
                "reason_code": self.get_reason_code(name),
            }

        return {
            "mode": self.get_mode().value,
            "mode_override": self._mode_override.value if self._mode_override else None,
            "bypassed_subsystems": self.get_bypassed_subsystems(),
            "total_weight": sum(
                self.SUBSYSTEM_WEIGHTS.get(n, 0.5)
                for n in self.get_bypassed_subsystems()
            ),
            "subsystems": subsystem_status,
            "bypass_log_count": len(self._bypass_log),
        }

    def get_short_circuit_plan(self) -> Dict:
        """
        获取当前旁路等级下的热路径短路计划
        
        这是对冲千问风险3（算力延迟开销）的核心：
        - FULL: 全部走
        - MINIMAL: 跳过情绪、偏差门B线、调度链穿皮、内稳态
        - SAFE: 只走安全栅 + 基础记忆召回 + 直接回复
        """
        mode = self.get_mode()

        if mode == BypassLevel.FULL:
            return {
                "skip_emotion": False,
                "skip_deviation_b_line": False,
                "skip_dispatcher": False,
                "skip_consciousness_tick": False,
                "skip_homeostatic": False,
                "skip_honeypot": False,
                "skip_zero_trust": False,
                "skip_steelmark": False,
                "skip_memory_recall": False,
                "skip_memory_store": False,
                "skip_compaction": False,
                "skip_reflection": False,
                "skip_q8": False,
                "skip_naming": False,
                "skip_life_ring": False,
            }
        elif mode == BypassLevel.MINIMAL:
            return {
                "skip_emotion": True,
                "skip_deviation_b_line": True,  # 跳过B线深度推理
                "skip_dispatcher": True,         # 跳过穿皮仪式
                "skip_consciousness_tick": True,  # 跳过意识循环
                "skip_homeostatic": True,        # 跳过内稳态
                "skip_honeypot": False,          # 保留安全
                "skip_zero_trust": False,        # 保留安全
                "skip_steelmark": False,         # 保留安全（钢印是第三层防御）
                "skip_memory_recall": False,     # 保留记忆
                "skip_memory_store": False,      # 保留记忆
                "skip_compaction": True,         # 跳过压缩
                "skip_reflection": True,         # 跳过复盘
                "skip_q8": True,                 # 跳过Q8
                "skip_naming": True,             # 跳过呼名
                "skip_life_ring": True,          # 跳过生命年轮
            }
        else:  # SAFE
            return {
                "skip_emotion": True,
                "skip_deviation_b_line": True,
                "skip_dispatcher": True,
                "skip_consciousness_tick": True,
                "skip_homeostatic": True,
                "skip_honeypot": False,          # 保留安全
                "skip_zero_trust": False,        # 保留安全
                "skip_steelmark": False,        # 保留安全（钢印永远不跳过）
                "skip_memory_recall": True,       # 安全模式跳过记忆召回
                "skip_memory_store": True,        # 安全模式跳过记忆存储
                "skip_compaction": True,
                "skip_reflection": True,
                "skip_q8": True,
                "skip_naming": True,
                "skip_life_ring": True,
            }
