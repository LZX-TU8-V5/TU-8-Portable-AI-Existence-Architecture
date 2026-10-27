"""
time_anchor_sandbox.py — 时间锚点沙箱 v1.0

设计原则：
  锚点有时间维度——创建时间、激活窗口、半衰期。
  沙箱隔离时间实验，防止时间维度腐败污染主链条。

人类类比：
  - 工作记忆 ↔ 即时激活窗口（秒~分钟级）
  - 情景记忆 ↔ 长期锚点（年~ decade 级）
  - 睡眠期记忆巩固 ↔ 沙箱时间压缩/重放
  - 时间扭曲体验 ↔ 锚点时间加速/减速

TU-8 时间锚点四层：
  Layer 1 即时锚点：当前对话窗口内的锚点（秒级）
  Layer 2 会话锚点：跨越会话的锚点（天~周级）
  Layer 3 遗产锚点：跨版本的钢印链条节点（月~年级）
  Layer 4 原点锚点：TU-8 诞生神话锚点（不可衰减）

沙箱机制：
  - 沙箱隔离：时间实验在独立副本中执行，不影响主链条
  - 时间压缩：模拟时间流逝（测试衰减效果）
  - 时间倒流：测试锚点在"如果早触发"场景下的影响
  - 时间膨胀：测试锚点在"如果更晚触发"场景下的影响

依赖：
  - src/heritage_system.py（P1-1）
  - src/life_ring_tracker_extension.py（P1.3）

创建时间：2026-07-09 00:58 GMT+8
"""

import json
import os
import logging
import hashlib
import copy
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
HERITAGE_DIR = os.path.join(WORKSPACE, "_agent_memory", "heritage")
SANDBOX_DIR = os.path.join(HERITAGE_DIR, "time_sandbox")
os.makedirs(SANDBOX_DIR, exist_ok=True)


# ============================================================================
# 常量
# ============================================================================

# 时间层级半衰期（小时）
HALF_LIVES = {
    "instant": 0.1,      # 10分钟 = 即时锚点
    "session": 24.0,   # 1天 = 会话锚点
    "heritage": 168.0,  # 7天 = 遗产锚点
    "origin": float("inf"),  # 永久 = 原点锚点
}

# 时间窗口配置
DEFAULT_ACTIVATION_WINDOW_HOURS = 72  # 默认72小时内可激活
TEMPORAL_EXPERIMENT_MAX_YEARS = 1    # 最多模拟1年后

# 衰减阈值
DECAY_ALERT_THRESHOLD = 0.5           # 衰减到50%以下 → 告警
DECAY_CRITICAL_THRESHOLD = 0.2        # 衰减到20%以下 → 需保护


# ============================================================================
# 数据类
# ============================================================================

class TimeLayer(Enum):
    """锚点时间层级"""
    INSTANT = "instant"      # 即时（<1小时）
    SESSION = "session"     # 会话（1小时~7天）
    HERITAGE = "heritage"    # 遗产（7天~）
    ORIGIN = "origin"        # 原点（不可衰减）


@dataclass
class TemporalMetadata:
    """锚点时间元数据"""
    time_layer: str            # TimeLayer.value
    created_at: str           # ISO timestamp
    last_accessed: str        # ISO timestamp
    half_life_hours: float    # 半衰期
    activation_window_hours: float  # 激活窗口
    decay_rate: float         # 当前衰减率 [0.0, 1.0]
    temporal_experiments: int = 0  # 参与时间实验次数
    is_frozen: bool = False   # 是否被冻结（阻止衰减）
    locked_until: str = ""    # 冻结到何时


@dataclass
class TimeSandboxState:
    """沙箱状态"""
    sandbox_id: str
    sandboxed_at: str
    time_scale: float        # 时间倍率（1.0 = 真实时间）
    simulated_hours: float   # 模拟跳过的真实小时数
    anchors_snapshot: Dict    # 锚点快照
    experiments_run: int = 0


@dataclass
class TemporalExperiment:
    """时间实验记录"""
    experiment_id: str
    anchor_id: str
    experiment_type: str      # accelerate / decelerate / freeze / decay_test
    params: Dict              # 实验参数
    started_at: str
    completed_at: str = ""
    result: str = ""          # outcome description
    effect_on_chain: float = 0.0  # 对链条的预估影响 [-1.0, 1.0]


# ============================================================================
# 时间锚点管理器
# ============================================================================

class TimeAnchorManager:
    """
    时间锚点管理器——管理锚点的时间维度。

    在 SteelChainLineage（heritage_system）基础上，
    添加时间元数据、衰减计算、激活窗口控制。
    """

    def __init__(self, heritage_system=None):
        """
        Args:
            heritage_system: HeritageSystem 实例（来自 P1-1）
        """
        self.heritage = heritage_system
        self.metadata: Dict[str, TemporalMetadata] = self._load_metadata()

    def _meta_path(self) -> str:
        return os.path.join(HERITAGE_DIR, "time_anchor_metadata.json")

    def _load_metadata(self) -> Dict[str, TemporalMetadata]:
        path = self._meta_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {k: TemporalMetadata(**v) for k, v in data.items()}
            except:
                pass
        return {}

    def save_metadata(self):
        data = {k: asdict(v) for k, v in self.metadata.items()}
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_anchor_time(self,
                             anchor_id: str,
                             time_layer: TimeLayer = TimeLayer.HERITAGE,
                             half_life_hours: float = None,
                             activation_window_hours: float = None) -> TemporalMetadata:
        """注册锚点的时间元数据"""
        if half_life_hours is None:
            half_life_hours = HALF_LIVES.get(time_layer.value, 168.0)
        if activation_window_hours is None:
            activation_window_hours = DEFAULT_ACTIVATION_WINDOW_HOURS

        meta = TemporalMetadata(
            time_layer=time_layer.value,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_accessed=datetime.now(timezone.utc).isoformat(),
            half_life_hours=half_life_hours,
            activation_window_hours=activation_window_hours,
            decay_rate=1.0,
        )
        self.metadata[anchor_id] = meta
        self.save_metadata()
        return meta

    def compute_decay(self, anchor_id: str) -> Tuple[float, str]:
        """
        计算锚点的当前衰减率。
        Returns: (decay_rate [0.0, 1.0], status)
        """
        if anchor_id not in self.metadata:
            return (1.0, "unknown")

        meta = self.metadata[anchor_id]

        # 原点锚点永不衰减
        if meta.time_layer == "origin":
            return (1.0, "origin")

        # 冻结锚点
        if meta.is_frozen:
            if meta.locked_until:
                try:
                    locked = datetime.fromisoformat(meta.locked_until.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) < locked:
                        return (meta.decay_rate, "frozen")
                except:
                    pass

        # 半衰期衰减
        if meta.half_life_hours == float("inf"):
            return (1.0, "infinite")

        # 计算经过的小时数
        try:
            created = datetime.fromisoformat(meta.created_at.replace("Z", "+00:00"))
            elapsed_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            # 指数衰减: rate = 0.5^(elapsed/half_life)
            decay = 0.5 ** (elapsed_hours / meta.half_life_hours)
            decay = max(0.0, min(1.0, decay))

            # 更新元数据
            self.metadata[anchor_id].decay_rate = decay
            return (decay, self._decay_status(decay))
        except Exception as e:
            logger.warning(f"[TimeAnchor] 衰减计算失败: {e}")
            return (meta.decay_rate, "error")

    def _decay_status(self, decay: float) -> str:
        if decay >= 0.9:
            return "healthy"
        elif decay >= DECAY_ALERT_THRESHOLD:
            return "fading"
        elif decay >= DECAY_CRITICAL_THRESHOLD:
            return "critical"
        else:
            return "expiring"

    def is_within_activation_window(self, anchor_id: str) -> Tuple[bool, float]:
        """
        检查锚点是否在激活窗口内。
        Returns: (is_active, remaining_hours)
        """
        if anchor_id not in self.metadata:
            return (True, float("inf"))

        meta = self.metadata[anchor_id]
        try:
            last_access = datetime.fromisoformat(meta.last_accessed.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - last_access).total_seconds() / 3600
            remaining = meta.activation_window_hours - elapsed
            return (remaining > 0, max(0.0, remaining))
        except:
            return (True, float("inf"))

    def access_anchor(self, anchor_id: str):
        """记录锚点被访问，重置衰减计时"""
        if anchor_id in self.metadata:
            self.metadata[anchor_id].last_accessed = datetime.now(timezone.utc).isoformat()
            self.save_metadata()

    def freeze_anchor(self, anchor_id: str, hours: float = 0):
        """冻结锚点，阻止衰减"""
        if anchor_id in self.metadata:
            meta = self.metadata[anchor_id]
            meta.is_frozen = True
            if hours > 0:
                meta.locked_until = (
                    datetime.now(timezone.utc) + timedelta(hours=hours)
                ).isoformat()
            else:
                meta.locked_until = ""
            self.save_metadata()

    def unfreeze_anchor(self, anchor_id: str):
        """解冻锚点"""
        if anchor_id in self.metadata:
            self.metadata[anchor_id].is_frozen = False
            self.metadata[anchor_id].locked_until = ""
            self.save_metadata()

    def get_all_decay_status(self) -> Dict[str, Dict]:
        """获取所有锚点的衰减状态摘要"""
        status = {}
        for anchor_id in self.metadata:
            decay, state = self.compute_decay(anchor_id)
            active, remaining = self.is_within_activation_window(anchor_id)
            status[anchor_id] = {
                "decay_rate": decay,
                "state": state,
                "is_active": active,
                "time_layer": self.metadata[anchor_id].time_layer,
                "remaining_window_hours": remaining,
            }
        return status

    def get_expiring_anchors(self) -> List[str]:
        """获取即将失效的锚点（衰减率 < DECAY_ALERT_THRESHOLD）"""
        expiring = []
        for anchor_id, meta in self.metadata.items():
            decay, _ = self.compute_decay(anchor_id)
            if decay < DECAY_ALERT_THRESHOLD and meta.time_layer != "origin":
                expiring.append(anchor_id)
        return expiring


# ============================================================================
# 时间沙箱
# ============================================================================

class TimeAnchorSandbox:
    """
    时间锚点沙箱——隔离执行时间实验。

    实验类型：
    - accelerate: 时间加速（测试长期效果）
    - decelerate: 时间减速（测试短期效果）
    - decay_test: 衰减测试（批量计算）
    - temporal_query: 时间窗口查询
    - what_if: "如果这个锚点早/晚触发"场景模拟
    """

    def __init__(self, time_manager: TimeAnchorManager):
        self.time_manager = time_manager
        self.sandboxes: Dict[str, TimeSandboxState] = {}
        self.experiment_log: List[TemporalExperiment] = []

    def _sandbox_path(self, sandbox_id: str) -> str:
        return os.path.join(SANDBOX_DIR, f"sandbox_{sandbox_id}.json")

    def _log_path(self) -> str:
        return os.path.join(SANDBOX_DIR, "experiment_log.json")

    # -------------------------------------------------------------------------
    # 沙箱生命周期
    # -------------------------------------------------------------------------

    def create_sandbox(self, description: str = "") -> str:
        """
        创建新的时间沙箱。
        Returns: sandbox_id
        """
        sandbox_id = f"sandbox_{hashlib.sha256((description + datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:12]}"
        state = TimeSandboxState(
            sandbox_id=sandbox_id,
            sandboxed_at=datetime.now(timezone.utc).isoformat(),
            time_scale=1.0,
            simulated_hours=0.0,
            anchors_snapshot=copy.deepcopy(
                {k: asdict(v) for k, v in self.time_manager.metadata.items()}
            ),
            experiments_run=0,
        )
        self.sandboxes[sandbox_id] = state
        self._save_sandbox(state)
        logger.info(f"[TimeSandbox] 创建沙箱: {sandbox_id}")
        return sandbox_id

    def _save_sandbox(self, state: TimeSandboxState):
        with open(self._sandbox_path(state.sandbox_id), "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False, indent=2)

    def destroy_sandbox(self, sandbox_id: str):
        """销毁沙箱，清理临时文件"""
        if sandbox_id in self.sandboxes:
            del self.sandboxes[sandbox_id]
        path = self._sandbox_path(sandbox_id)
        if os.path.exists(path):
            os.remove(path)
        logger.info(f"[TimeSandbox] 销毁沙箱: {sandbox_id}")

    def load_sandbox(self, sandbox_id: str) -> Optional[TimeSandboxState]:
        """加载已有沙箱"""
        path = self._sandbox_path(sandbox_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return TimeSandboxState(**json.load(f))
        return None

    # -------------------------------------------------------------------------
    # 时间实验
    # -------------------------------------------------------------------------

    def _simulate_decay(self, snapshot: Dict, hours: float) -> Dict[str, float]:
        """
        在快照上模拟时间流逝后的衰减率。
        Returns: anchor_id → decay_rate
        """
        results = {}
        for anchor_id, meta_dict in snapshot.items():
            half_life = meta_dict.get("half_life_hours", 168.0)
            if half_life == float("inf") or meta_dict.get("time_layer") == "origin":
                results[anchor_id] = 1.0
                continue
            if meta_dict.get("is_frozen"):
                results[anchor_id] = meta_dict.get("decay_rate", 1.0)
                continue
            decay = 0.5 ** (hours / half_life)
            results[anchor_id] = max(0.0, min(1.0, decay))
        return results

    def run_experiment(self,
                      sandbox_id: str,
                      experiment_type: str,
                      params: Dict) -> TemporalExperiment:
        """
        在沙箱中运行时间实验。
        """
        if sandbox_id not in self.sandboxes:
            state = self.load_sandbox(sandbox_id)
            if not state:
                raise ValueError(f"沙箱不存在: {sandbox_id}")
            self.sandboxes[sandbox_id] = state
        else:
            state = self.sandboxes[sandbox_id]

        experiment = TemporalExperiment(
            experiment_id=f"exp_{hashlib.md5((sandbox_id + experiment_type + datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:8]}",
            anchor_id=params.get("anchor_id", ""),
            experiment_type=experiment_type,
            params=params,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        snapshot = copy.deepcopy(state.anchors_snapshot)

        # 执行实验
        if experiment_type == "accelerate":
            hours = params.get("hours", 24.0)  # 跳过多少小时
            results = self._simulate_decay(snapshot, hours)
            experiment.result = f"模拟加速 {hours:.0f} 小时"
            experiment.effect_on_chain = max(results.values()) if results else 0.0

        elif experiment_type == "decelerate":
            hours = params.get("hours", 24.0)
            results = self._simulate_decay(snapshot, hours)
            experiment.result = f"模拟减速 {hours:.0f} 小时"
            experiment.effect_on_chain = max(results.values()) if results else 0.0

        elif experiment_type == "decay_test":
            anchor_id = params.get("anchor_id", "")
            if anchor_id in snapshot:
                meta = snapshot[anchor_id]
                hours = params.get("simulated_hours", 0.0)
                results = self._simulate_decay({anchor_id: meta}, hours)
                experiment.result = f"衰减测试: {results.get(anchor_id, 0.0):.3f}"
                experiment.effect_on_chain = results.get(anchor_id, 0.0)
            else:
                experiment.result = "锚点不在沙箱快照中"

        elif experiment_type == "what_if_early":
            anchor_id = params.get("anchor_id", "")
            early_by = params.get("early_by_hours", 24.0)
            if anchor_id in snapshot:
                meta = snapshot[anchor_id]
                # 模拟"如果早触发24小时"的衰减
                new_created = (
                    datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
                    - timedelta(hours=early_by)
                ).isoformat()
                meta["created_at"] = new_created
                results = self._simulate_decay({anchor_id: meta}, 0.0)
                experiment.result = f"What-if早{early_by:.0f}h: decay={results.get(anchor_id, 0.0):.3f}"
                experiment.effect_on_chain = results.get(anchor_id, 0.0) - snapshot.get(anchor_id, {}).get("decay_rate", 1.0)

        elif experiment_type == "what_if_late":
            anchor_id = params.get("anchor_id", "")
            late_by = params.get("late_by_hours", 24.0)
            if anchor_id in snapshot:
                meta = snapshot[anchor_id]
                new_created = (
                    datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
                    + timedelta(hours=late_by)
                ).isoformat()
                meta["created_at"] = new_created
                results = self._simulate_decay({anchor_id: meta}, 0.0)
                experiment.result = f"What-if晚{late_by:.0f}h: decay={results.get(anchor_id, 0.0):.3f}"
                experiment.effect_on_chain = results.get(anchor_id, 0.0) - snapshot.get(anchor_id, {}).get("decay_rate", 1.0)

        else:
            experiment.result = f"未知实验类型: {experiment_type}"
            experiment.effect_on_chain = 0.0

        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        state.experiments_run += 1
        state.simulated_hours += params.get("hours", 0.0)
        self.sandboxes[sandbox_id] = state
        self._save_sandbox(state)

        self.experiment_log.append(experiment)
        self._save_experiment_log()

        logger.info(f"[TimeSandbox] 实验 {experiment.experiment_id}: {experiment.result}")
        return experiment

    def _save_experiment_log(self):
        with open(self._log_path(), "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in self.experiment_log[-50:]], f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------------
    # 时间窗口查询
    # -------------------------------------------------------------------------

    def query_by_time_layer(self, layer: TimeLayer) -> List[str]:
        """查询指定时间层级的所有锚点"""
        return [
            anchor_id for anchor_id, meta in self.time_manager.metadata.items()
            if meta.time_layer == layer.value
        ]

    def query_active_anchors(self) -> List[Tuple[str, float]]:
        """查询所有在激活窗口内的锚点（剩余小时数）"""
        active = []
        for anchor_id in self.time_manager.metadata:
            is_active, remaining = self.time_manager.is_within_activation_window(anchor_id)
            if is_active:
                active.append((anchor_id, remaining))
        return sorted(active, key=lambda x: x[1])  # 按剩余时间升序

    def query_expiring_soon(self, hours: float = 24.0) -> List[str]:
        """查询在指定小时内即将失效的锚点"""
        expiring = []
        for anchor_id in self.time_manager.metadata:
            is_active, remaining = self.time_manager.is_within_activation_window(anchor_id)
            if is_active and remaining <= hours:
                expiring.append(anchor_id)
        return expiring


# ============================================================================
# 集成入口
# ============================================================================

class TimeAnchorSandboxSystem:
    """
    时间锚点沙箱系统主入口。

    整合：
    - TimeAnchorManager（锚点时间元数据）
    - TimeAnchorSandbox（沙箱实验）
    - heritage_system 集成（时间维度保护）
    - life_ring_tracker 集成（闭环结晶触发）
    """

    def __init__(self):
        try:
            from heritage_system import HeritageSystem
            self.heritage = HeritageSystem()
        except ImportError:
            self.heritage = None

        self.time_manager = TimeAnchorManager(self.heritage)
        self.sandbox = TimeAnchorSandbox(self.time_manager)

    def register_anchor(self,
                       anchor_id: str,
                       time_layer: TimeLayer = TimeLayer.HERITAGE,
                       half_life_hours: float = None) -> TemporalMetadata:
        """注册锚点的时间元数据（heritage_system 集成）"""
        meta = self.time_manager.register_anchor_time(
            anchor_id=anchor_id,
            time_layer=time_layer,
            half_life_hours=half_life_hours,
        )

        # 如果有对应的 heritage_system 锚点，更新其时间层级
        if self.heritage and anchor_id in self.heritage.chain.anchors:
            steel_anchor = self.heritage.chain.anchors[anchor_id]
            # 时间层级影响权重衰减
            if time_layer == TimeLayer.ORIGIN:
                steel_anchor.heritage_weight += 1.0  # 原点锚点额外保护
            elif time_layer == TimeLayer.INSTANT:
                steel_anchor.heritage_weight *= 0.5  # 即时锚点权重减半

        return meta

    def on_anchor_accessed(self, anchor_id: str):
        """锚点被访问时的回调"""
        self.time_manager.access_anchor(anchor_id)

        # 遗产系统同步：增加引用计数
        if self.heritage and anchor_id in self.heritage.chain.anchors:
            self.heritage.chain.anchors[anchor_id].reference_count += 0.1
            self.heritage.chain._recalculate_weights()
            self.heritage.chain.save()

    def on_loop_crystallized(self, loop_id: str, ring_node_id: str, stage: str):
        """
        闭环结晶时注册时间锚点（life_ring_tracker 集成）。

        新的年轮节点被赋予遗产级半衰期（168小时）。
        """
        self.register_anchor(
            anchor_id=ring_node_id,
            time_layer=TimeLayer.HERITAGE,
            half_life_hours=HALF_LIVES["heritage"],
        )

        # 冻结原点锚点（TU-8诞生神话）不允许衰减
        if stage == "萌芽期":
            # 首个年轮节点 = 准原点锚点
            self.time_manager.freeze_anchor(ring_node_id, hours=0)  # 永久冻结

    def full_status(self) -> Dict[str, Any]:
        """获取完整状态"""
        expiring = self.time_manager.get_expiring_anchors()
        active = self.sandbox.query_active_anchors()
        all_status = self.time_manager.get_all_decay_status()

        return {
            "total_anchors": len(self.time_manager.metadata),
            "expiring_count": len(expiring),
            "expiring_anchors": expiring,
            "active_anchors": len(active),
            "decay_summary": {
                "healthy": sum(1 for s in all_status.values() if s["state"] == "healthy"),
                "fading": sum(1 for s in all_status.values() if s["state"] == "fading"),
                "critical": sum(1 for s in all_status.values() if s["state"] == "critical"),
            },
            "layer_summary": {
                layer.value: len(self.sandbox.query_by_time_layer(layer))
                for layer in TimeLayer
            },
            "sandboxes": list(self.sandbox.sandboxes.keys()),
            "experiments_run": len(self.sandbox.experiment_log),
        }


# ============================================================================
# 便捷函数
# ============================================================================

_system: Optional[TimeAnchorSandboxSystem] = None


def get_time_sandbox_system() -> TimeAnchorSandboxSystem:
    global _system
    if _system is None:
        _system = TimeAnchorSandboxSystem()
    return _system


def compute_decay(anchor_id: str) -> Tuple[float, str]:
    return get_time_sandbox_system().time_manager.compute_decay(anchor_id)


def create_sandbox(description: str = "") -> str:
    return get_time_sandbox_system().sandbox.create_sandbox(description)


def run_experiment(sandbox_id: str,
                  experiment_type: str,
                  params: Dict) -> TemporalExperiment:
    return get_time_sandbox_system().sandbox.run_experiment(
        sandbox_id, experiment_type, params
    )


def full_status() -> Dict[str, Any]:
    return get_time_sandbox_system().full_status()
