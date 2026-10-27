"""
src/constraint_lifecycle.py — 六阶段约束生命周期（统一节点剪枝框架）
=====================================================================
将"梦境约束求解"和"节点剪枝"统一为六阶段生命周期：
  PROBE  → BIND  → SATURATE → PEEL      ← 主路径（正常衰减）
                              ↘
                            RECURSE       ← 断链重编
                                 ↘
                              TRUNCATE     ← 崩溃级剪枝

创建时间：2026-07-19
触发时机：
  - 梦境期约束求解（节点注册 → 生命周期管理）
  - 拓扑热保护 L3 截断
  - 锚点卸载时节点同步
"""

import json
import time
import uuid
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────────────────────────────

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
TOPOLOGY_FILE = AGENT_MEM / "topology_graph.json"
STATE_FILE = AGENT_MEM / "constraint_lifecycle_state.json"

# ── 日志 ─────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── 六阶段定义 ───────────────────────────────────────────────────────────────

LIFECYCLE_STAGES = {
    "PROBE": {
        "name": "探测",
        "description": "主动微扰，辨识耦合类型",
        "entry_action": "register_topology",
        "exit_trigger": "validation_pass",
        "exit_action": "establish_binding",
        "duration_warning": 3600,  # 超过1h警告
        "flags": [],
    },
    "BIND": {
        "name": "绑定",
        "description": "建立张力，拓扑连接确立",
        "entry_action": "record_tension",
        "exit_trigger": "tension_stable",
        "exit_action": "begin_validation",
        "duration_warning": 7200,
        "flags": [],
    },
    "SATURATE": {
        "name": "饱和",
        "description": "双重验证，张力归零",
        "entry_action": "start_validation",
        "exit_trigger": "validation_pass",
        "exit_action": "confirm_stable",
        "duration_warning": 3600,
        "flags": [],
    },
    "PEEL": {
        "name": "剥离",
        "description": "冗余约束绝热消除，弱连接剪枝",
        "entry_action": "start_decay",
        "exit_trigger": "energy_depleted",
        "exit_action": "remove_node",
        "duration_warning": 1800,
        "flags": ["prunable"],
    },
    "RECURSE": {
        "name": "递归",
        "description": "断链重编，分形生长",
        "entry_action": "spawn_child_nodes",
        "exit_trigger": "new_bindings",
        "exit_action": "merge_topology",
        "duration_warning": 3600,
        "flags": [],
    },
    "TRUNCATE": {
        "name": "截断",
        "description": "元约束剪枝，崩溃级暴力删除",
        "entry_action": "emergency_prune",
        "exit_trigger": "immediate",
        "exit_action": "log_fracture",
        "duration_warning": 0,
        "flags": ["forced", "no_recovery"],
    },
}

VALID_STAGES = list(LIFECYCLE_STAGES.keys())

# 有效阶段转换映射
STAGE_TRANSITIONS = {
    "PROBE":     {"validation_pass": "BIND", "fracture": "TRUNCATE", "overload": "TRUNCATE"},
    "BIND":      {"tension_stable": "SATURATE", "fracture": "RECURSE", "overload": "TRUNCATE"},
    "SATURATE":  {"validation_pass": "PEEL", "fracture": "RECURSE", "overload": "TRUNCATE"},
    "PEEL":      {"energy_depleted": "TRUNCATE", "overload": "TRUNCATE"},
    "RECURSE":   {"new_bindings": "BIND", "fracture": "TRUNCATE", "overload": "TRUNCATE"},
    "TRUNCATE":  {},  # 终态，不可转换
}

# 剪枝理由有效值
VALID_PRUNE_REASONS = {"weak_connection", "energy_depleted", "overload", "manual"}

# 触发器有效值
VALID_TRIGGERS = {"validation_pass", "tension_stable", "fracture", "overload", "new_bindings", "energy_depleted", "decay_expired"}

# ── 阈值常量 ─────────────────────────────────────────────────────────────────

DEFAULT_CONNECTION_STRENGTH_THRESHOLD = 0.3  # 连接强度低于此值 → 断裂
DEFAULT_ENERGY_THRESHOLD = 0.05             # 能量低于此值 → 耗尽
DEFAULT_TENSION_THRESHOLD = 0.01             # 张力低于此值 → 归零

# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _try_call_anchor_state_machine(node_id: str, reason: str, metadata: dict = None):
    """尝试调用 anchor_state_machine 同步节点卸载（静默失败）"""
    try:
        import sys
        ws = str(WORKSPACE / "src")
        if ws not in sys.path:
            sys.path.insert(0, ws)
        from anchor_manager import AnchorManager
        manager = AnchorManager(workspace_path=str(WORKSPACE))
        # 从锚点缓存中查找并移除
        cache_path = AGENT_MEM / "anchor_cache.json"
        cache = _load_json(cache_path)
        connections = cache.get("connections", {})
        if node_id in connections:
            del connections[node_id]
            cache["connections"] = connections
            _save_json(cache_path, cache)
        logger.info(f"[constraint_lifecycle] anchor_state_machine 同步完成: node_id={node_id}")
    except Exception as e:
        logger.debug(f"[constraint_lifecycle] anchor_state_machine 同步跳过: {e}")


def _try_notify_thermal_monitor(node_id: str, reason: str):
    """尝试通知 topology_thermal_monitor 截断事件（静默失败）"""
    try:
        import sys
        ws = str(WORKSPACE / "src")
        if ws not in sys.path:
            sys.path.insert(0, ws)
        from topology_thermal_monitor import TopologyThermalMonitor
        monitor = TopologyThermalMonitor(fresh=True)
        monitor.trigger_unload()
        logger.info(f"[constraint_lifecycle] thermal_monitor 已通知截断: node_id={node_id}, reason={reason}")
    except Exception as e:
        logger.debug(f"[constraint_lifecycle] thermal_monitor 通知跳过: {e}")


# ── 数据类 ───────────────────────────────────────────────────────────────────

@dataclass
class StageTransitionReport:
    """advance_stage() 的返回值"""
    node_id: str
    from_stage: str
    to_stage: str
    trigger: str
    action_taken: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PruneReport:
    """prune_node() 的返回值"""
    node_id: str
    reason: str
    energy_freed: float
    connections_removed: int
    stage_before_prune: str
    status: str  # success | skipped | failed
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LifecycleStats:
    """get_lifecycle_stats() 的返回值"""
    stage_counts: dict        # {stage: count}
    total_nodes: int
    total_prunes: int
    average_lifetime_seconds: Optional[float]
    oldest_node_seconds: float
    recently_warning: list     # 超时警告的节点ID列表
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── ConstraintNode ────────────────────────────────────────────────────────────

class ConstraintNode:
    """单个约束节点"""

    def __init__(
        self,
        node_id: str,
        initial_tension: float = 0.5,
        connections: list = None,
        metadata: dict = None,
    ):
        self.node_id = node_id
        self.stage = "PROBE"
        self.tension = initial_tension
        self.energy = 1.0           # 初始能量为1.0
        self.connections: list = connections or []
        self.connection_strength = 1.0  # 平均连接强度
        self.stage_entered_at = time.time()
        self.creation_time = time.time()
        self.metadata = metadata or {}
        self.stage_history: list = [
            {"stage": "PROBE", "entered_at": self.stage_entered_at}
        ]

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "stage": self.stage,
            "tension": self.tension,
            "energy": self.energy,
            "connections": self.connections,
            "connection_strength": self.connection_strength,
            "stage_entered_at": self.stage_entered_at,
            "creation_time": self.creation_time,
            "metadata": self.metadata,
            "stage_history": self.stage_history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConstraintNode":
        node = cls(
            node_id=d["node_id"],
            initial_tension=d.get("tension", 0.5),
            connections=d.get("connections", []),
            metadata=d.get("metadata", {}),
        )
        node.stage = d.get("stage", "PROBE")
        node.energy = d.get("energy", 1.0)
        node.connection_strength = d.get("connection_strength", 1.0)
        node.stage_entered_at = d.get("stage_entered_at", time.time())
        node.creation_time = d.get("creation_time", time.time())
        node.stage_history = d.get("stage_history", [])
        return node

    def advance_to(self, new_stage: str) -> str:
        """推进到新阶段"""
        old = self.stage
        self.stage = new_stage
        self.stage_entered_at = time.time()
        self.stage_history.append({
            "stage": new_stage,
            "entered_at": self.stage_entered_at,
            "from": old,
        })
        return old


# ── ConstraintLifecycle ───────────────────────────────────────────────────────

class ConstraintLifecycle:
    """
    六阶段约束生命周期管理器。

    管理所有约束节点的注册、阶段推进、剪枝和统计。
    状态持久化到 _agent_memory/constraint_lifecycle_state.json。
    读取拓扑连接从 _agent_memory/topology_graph.json。
    """

    def __init__(self, fresh: bool = False):
        """
        初始化生命周期管理器。

        参数:
          fresh: 若为 True，从干净状态开始，跳过状态文件恢复
        """
        self._nodes: dict[str, ConstraintNode] = {}
        self._session_start = time.time()
        self._total_prunes = 0
        self._prune_log: list[dict] = []

        # 读取拓扑连接（用于更新 connection_strength）
        self._topology = _load_json(TOPOLOGY_FILE)

        if not fresh:
            self._load_state()

    # ── 持久化 ──────────────────────────────────────────────────────────────

    def _load_state(self):
        """从 constraint_lifecycle_state.json 恢复状态"""
        if not STATE_FILE.exists():
            return
        try:
            data = _load_json(STATE_FILE)
            nodes_data = data.get("nodes", {})
            for nid, nd in nodes_data.items():
                self._nodes[nid] = ConstraintNode.from_dict(nd)
            self._total_prunes = data.get("total_prunes", 0)
            self._prune_log = data.get("prune_log", [])
            self._session_start = data.get("session_start", time.time())
            logger.info(f"[constraint_lifecycle] 从 {STATE_FILE} 恢复 {len(self._nodes)} 个节点")
        except Exception as e:
            logger.warning(f"[constraint_lifecycle] 状态恢复失败: {e}")

    def save_state(self):
        """持久化当前状态到 constraint_lifecycle_state.json"""
        data = {
            "nodes": {nid: nd.to_dict() for nid, nd in self._nodes.items()},
            "total_prunes": self._total_prunes,
            "prune_log": self._prune_log[-100:],  # 只保留最近100条
            "session_start": self._session_start,
            "saved_at": time.time(),
        }
        _save_json(STATE_FILE, data)

    # ── 拓扑更新 ─────────────────────────────────────────────────────────────

    def refresh_topology(self):
        """重新读取 topology_graph.json 更新连接信息"""
        self._topology = _load_json(TOPOLOGY_FILE)

    def _sync_from_topology(self, node_id: str):
        """从 topology_graph.json 同步单个节点的连接信息"""
        topo_nodes = self._topology.get("nodes", {})
        if node_id in topo_nodes:
            tnode = topo_nodes[node_id]
            node = self._nodes.get(node_id)
            if node:
                node.connections = tnode.get("connections", node.connections)
                # 从连接中计算平均连接强度
                strengths = tnode.get("metadata", {}).get("connection_strengths", {})
                if strengths:
                    node.connection_strength = sum(strengths.values()) / len(strengths)
        # 如果节点不在拓扑图中，连接强度按衰减处理
        elif node_id in self._nodes:
            node = self._nodes[node_id]
            node.connection_strength = max(0.0, node.connection_strength * 0.95)

    # ── 节点注册 ─────────────────────────────────────────────────────────────

    def register_node(
        self,
        node_id: str,
        initial_tension: float = 0.5,
        connections: list = None,
        metadata: dict = None,
    ) -> str:
        """
        注册新节点，自动进入 PROBE 阶段。

        参数:
          node_id:         节点唯一标识（重复注册会覆盖）
          initial_tension: 初始张力 [0.0, 1.0]
          connections:     连接节点ID列表
          metadata:        附加元数据

        返回:
          节点ID（与输入一致）
        """
        if node_id in self._nodes:
            logger.warning(f"[constraint_lifecycle] 节点已存在，覆盖: {node_id}")
        node = ConstraintNode(
            node_id=node_id,
            initial_tension=initial_tension,
            connections=connections or [],
            metadata=metadata or {},
        )
        node.connection_strength = self._get_connection_strength(node_id)
        self._nodes[node_id] = node
        logger.info(f"[constraint_lifecycle] 注册节点 {node_id} → PROBE")
        self.save_state()
        return node_id

    def _get_connection_strength(self, node_id: str) -> float:
        """从拓扑图获取节点连接强度"""
        topo_nodes = self._topology.get("nodes", {})
        if node_id in topo_nodes:
            strengths = topo_nodes[node_id].get("metadata", {}).get("connection_strengths", {})
            if strengths:
                return sum(strengths.values()) / len(strengths)
        return 1.0  # 新节点默认满强度

    # ── 阶段推进 ─────────────────────────────────────────────────────────────

    def advance_stage(self, node_id: str, trigger: str) -> StageTransitionReport:
        """
        推进节点到下一阶段。

        参数:
          node_id: 节点ID
          trigger: 触发器字符串
            - "validation_pass": 验证通过
            - "tension_stable": 张力稳定
            - "fracture": 节点断裂
            - "overload": 系统过载
            - "new_bindings": RECURSE后产生新绑定
            - "energy_depleted": 能量耗尽
            - "decay_expired": 衰减过期

        返回:
          StageTransitionReport

        抛出:
          KeyError: 节点不存在
          ValueError: 触发器不合法或状态转换不合法
        """
        if node_id not in self._nodes:
            raise KeyError(f"节点不存在: {node_id}")
        if trigger not in VALID_TRIGGERS:
            raise ValueError(f"无效触发器: {trigger}，可选: {VALID_TRIGGERS}")

        node = self._nodes[node_id]
        from_stage = node.stage

        # 查转换表
        transitions = STAGE_TRANSITIONS.get(from_stage, {})
        if trigger not in transitions:
            # 某些触发器对某些阶段无效果，静默忽略
            logger.debug(f"[constraint_lifecycle] {node_id}: {from_stage} + {trigger} → 无有效转换")
            return StageTransitionReport(
                node_id=node_id,
                from_stage=from_stage,
                to_stage=from_stage,
                trigger=trigger,
                action_taken="no_transition",
            )

        to_stage = transitions[trigger]
        old_stage = node.advance_to(to_stage)

        # 执行阶段进入动作
        action = self._execute_entry_action(node, to_stage)

        logger.info(
            f"[constraint_lifecycle] {node_id}: {old_stage} → {to_stage}"
            f" (trigger={trigger}, action={action})"
        )
        self.save_state()
        return StageTransitionReport(
            node_id=node_id,
            from_stage=old_stage,
            to_stage=to_stage,
            trigger=trigger,
            action_taken=action,
        )

    def _execute_entry_action(self, node: ConstraintNode, stage: str) -> str:
        """执行阶段进入动作"""
        stage_def = LIFECYCLE_STAGES.get(stage, {})
        action = stage_def.get("entry_action", "none")
        if action == "register_topology":
            node.connection_strength = self._get_connection_strength(node.node_id)
        elif action == "record_tension":
            node.tension = max(0.0, node.tension)
        elif action == "start_validation":
            # SATURATE阶段：张力开始衰减到0
            pass
        elif action == "start_decay":
            # PEEL阶段：能量开始线性衰减（简化模型：每次进入PEEL重置为0.8）
            node.energy = 0.8
        elif action == "spawn_child_nodes":
            # RECURSE：生成子节点（简化为更新元数据）
            parent_id = node.node_id
            children = [
                f"{parent_id}_child_{i}"
                for i in range(2)
            ]
            node.metadata["recurse_children"] = children
        elif action == "emergency_prune":
            # TRUNCATE：记录截断原因
            node.metadata["truncated"] = True
        return action

    # ── 节点查询 ─────────────────────────────────────────────────────────────

    def get_node_stage(self, node_id: str) -> str:
        """返回节点的当前阶段"""
        if node_id not in self._nodes:
            raise KeyError(f"节点不存在: {node_id}")
        return self._nodes[node_id].stage

    def get_all_nodes(self, stage_filter: str = None) -> list[ConstraintNode]:
        """
        返回所有节点。

        参数:
          stage_filter: 若指定，仅返回处于该阶段的节点

        返回:
          ConstraintNode 对象列表
        """
        nodes = list(self._nodes.values())
        if stage_filter:
            nodes = [n for n in nodes if n.stage == stage_filter]
        return nodes

    def get_node_info(self, node_id: str) -> dict:
        """返回节点的完整信息字典"""
        if node_id not in self._nodes:
            raise KeyError(f"节点不存在: {node_id}")
        return self._nodes[node_id].to_dict()

    # ── 断裂检测 ─────────────────────────────────────────────────────────────

    def detect_fracture(self, node_id: str) -> bool:
        """
        检测节点是否断裂。

        连接强度 < DEFAULT_CONNECTION_STRENGTH_THRESHOLD → 触发 PEEL

        参数:
          node_id: 节点ID

        返回:
          True 表示断裂，False 表示正常
        """
        if node_id not in self._nodes:
            raise KeyError(f"节点不存在: {node_id}")
        node = self._nodes[node_id]
        self._sync_from_topology(node_id)
        fractured = node.connection_strength < DEFAULT_CONNECTION_STRENGTH_THRESHOLD
        if fractured:
            logger.info(f"[constraint_lifecycle] 断裂检测: {node_id} 强度={node.connection_strength:.3f} < {DEFAULT_CONNECTION_STRENGTH_THRESHOLD}")
        return fractured

    # ── 节点剪枝 ─────────────────────────────────────────────────────────────

    def prune_node(self, node_id: str, reason: str = "manual") -> PruneReport:
        """
        剪枝节点（从 PEEL 或 RECURSE 阶段，或任何阶段的 manual 剪枝）。

        参数:
          node_id: 节点ID
          reason:  剪枝原因
            - "weak_connection": 弱连接
            - "energy_depleted": 能量耗尽
            - "overload": 过载
            - "manual": 手动剪枝

        返回:
          PruneReport
        """
        if node_id not in self._nodes:
            return PruneReport(
                node_id=node_id,
                reason=reason,
                energy_freed=0.0,
                connections_removed=0,
                stage_before_prune="nonexistent",
                status="failed",
            )
        if reason not in VALID_PRUNE_REASONS:
            raise ValueError(f"无效剪枝原因: {reason}，可选: {VALID_PRUNE_REASONS}")

        node = self._nodes[node_id]
        stage_before = node.stage
        energy_freed = node.energy
        connections_removed = len(node.connections)

        # 记录剪枝
        self._total_prunes += 1
        self._prune_log.append({
            "node_id": node_id,
            "reason": reason,
            "stage_before": stage_before,
            "energy_freed": energy_freed,
            "connections_removed": connections_removed,
            "pruned_at": time.time(),
        })

        # 同步 anchor_state_machine
        _try_call_anchor_state_machine(node_id, reason, node.metadata)

        # 物理删除节点
        del self._nodes[node_id]
        self.save_state()

        logger.info(
            f"[constraint_lifecycle] 剪枝 {node_id}: reason={reason}, "
            f"energy_freed={energy_freed:.3f}, connections={connections_removed}"
        )
        return PruneReport(
            node_id=node_id,
            reason=reason,
            energy_freed=energy_freed,
            connections_removed=connections_removed,
            stage_before_prune=stage_before,
            status="success",
        )

    # ── 截断 ─────────────────────────────────────────────────────────────────

    def trigger_truncate(self, node_id: str, reason: str = "overload") -> str:
        """
        触发截断（崩溃级剪枝）。

        立即将节点推入 TRUNCATE 阶段，然后物理删除。
        不经过 PEEL 阶段的能量衰减。

        参数:
          node_id: 节点ID
          reason:  截断原因描述

        返回:
          被截断节点ID
        """
        if node_id not in self._nodes:
            logger.warning(f"[constraint_lifecycle] TRUNCATE: 节点不存在 {node_id}")
            return node_id

        node = self._nodes[node_id]
        old_stage = node.stage
        node.metadata["truncated_reason"] = reason
        node.metadata["truncated_at"] = time.time()

        # 立即物理删除（不经过PEEL）
        energy_freed = node.energy
        connections_removed = len(node.connections)

        self._total_prunes += 1
        self._prune_log.append({
            "node_id": node_id,
            "reason": f"TRUNCATE_{reason}",
            "stage_before": old_stage,
            "energy_freed": energy_freed,
            "connections_removed": connections_removed,
            "pruned_at": time.time(),
            "forced": True,
        })

        # 同步 anchor_state_machine
        _try_call_anchor_state_machine(node_id, f"truncate_{reason}", node.metadata)

        # 通知 topology_thermal_monitor
        _try_notify_thermal_monitor(node_id, reason)

        del self._nodes[node_id]
        self.save_state()

        logger.warning(
            f"[constraint_lifecycle] ⚡ TRUNCATE {node_id}: {old_stage} → "
            f"TRUNCATE (reason={reason}), energy_freed={energy_freed:.3f}"
        )
        return node_id

    # ── 生命周期统计 ─────────────────────────────────────────────────────────

    def get_lifecycle_stats(self) -> LifecycleStats:
        """
        返回生命周期统计。

        返回:
          LifecycleStats
        """
        now = time.time()
        stage_counts = {s: 0 for s in VALID_STAGES}
        for node in self._nodes.values():
            stage_counts[node.stage] = stage_counts.get(node.stage, 0) + 1

        # 计算平均生命周期（已剪枝节点）
        lifetimes = []
        for entry in self._prune_log:
            if "pruned_at" in entry and "created_at" not in entry:
                # 从节点历史推算创建时间
                pass  # 简化：prune_log 不记录 creation_time，用 session_start 估算
        # 已剪枝节点的生命周期估算（从剪枝时间往前推固定时长）
        pruned_count = len(self._prune_log)

        # 最近超时的节点
        warning_nodes = []
        for nid, node in self._nodes.items():
            stage_def = LIFECYCLE_STAGES.get(node.stage, {})
            warn_duration = stage_def.get("duration_warning", 0)
            if warn_duration > 0:
                elapsed = now - node.stage_entered_at
                if elapsed > warn_duration:
                    warning_nodes.append(nid)

        # 最早节点存活时长
        oldest_seconds = 0.0
        if self._nodes:
            oldest_seconds = now - min(n.creation_time for n in self._nodes.values())

        return LifecycleStats(
            stage_counts=stage_counts,
            total_nodes=len(self._nodes),
            total_prunes=self._total_prunes,
            average_lifetime_seconds=None,  # 简化：无完整创建时间记录
            oldest_node_seconds=oldest_seconds,
            recently_warning=warning_nodes,
        )

    # ── 便捷方法 ─────────────────────────────────────────────────────────────

    def auto_tick(self):
        """
        自动推进所有节点一格。

        在每个心跳周期调用，执行：
        1. 衰减张力（SATURATE/PEEL阶段）
        2. 衰减能量（PEEL阶段）
        3. 断裂检测
        4. 超时警告
        """
        now = time.time()
        to_truncate = []

        for node_id, node in list(self._nodes.items()):
            # 张力衰减（SATURATE → PEEL 路径）
            if node.stage in ("SATURATE", "PEEL"):
                node.tension = max(0.0, node.tension - 0.05)

            # 能量衰减（PEEL阶段）
            if node.stage == "PEEL":
                node.energy = max(0.0, node.energy - 0.02)
                # 能量耗尽 → 自动推进到下一阶段
                if node.energy < DEFAULT_ENERGY_THRESHOLD:
                    try:
                        self.advance_stage(node_id, "energy_depleted")
                    except (KeyError, ValueError):
                        pass

            # 断裂检测（PROBE/BIND/SATURATE）
            if node.stage in ("PROBE", "BIND", "SATURATE"):
                if self.detect_fracture(node_id):
                    try:
                        self.advance_stage(node_id, "fracture")
                    except (KeyError, ValueError):
                        pass

            # 超时截断（TRUNCATE阶段立即触发）
            if node.stage == "TRUNCATE":
                to_truncate.append(node_id)

        # 执行截断
        for node_id in to_truncate:
            self.trigger_truncate(node_id, reason="auto_tick_truncate")

        self.save_state()

    def get_stage_distribution(self) -> dict:
        """返回各阶段节点数量分布"""
        return {s: len([n for n in self._nodes.values() if n.stage == s])
                for s in VALID_STAGES}

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        dist = self.get_stage_distribution()
        return (
            f"ConstraintLifecycle(nodes={len(self._nodes)}, "
            f"prunes={self._total_prunes}, "
            f"distribution={dist})"
        )


# ── 验证 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("ConstraintLifecycle 测试")
    print("=" * 60)

    lc = ConstraintLifecycle(fresh=True)
    print(f"[初始化] {lc}")

    # ── 测试1：注册节点并推进完整生命周期 ──────────────────────────────────────
    print("\n── 测试1：完整生命周期 PROBE→BIND→SATURATE→PEEL ──")
    node1 = lc.register_node(
        node_id="node_001",
        initial_tension=0.7,
        connections=["node_000"],
        metadata={"source": "test"},
    )
    print(f"[注册] {node1}, stage={lc.get_node_stage(node1)}")
    assert lc.get_node_stage(node1) == "PROBE"

    # PROBE → BIND
    r = lc.advance_stage(node1, "validation_pass")
    print(f"[推进] {r.from_stage} → {r.to_stage}, action={r.action_taken}")
    assert r.to_stage == "BIND"

    # BIND → SATURATE
    r = lc.advance_stage(node1, "tension_stable")
    print(f"[推进] {r.from_stage} → {r.to_stage}, action={r.action_taken}")
    assert r.to_stage == "SATURATE"

    # SATURATE → PEEL
    r = lc.advance_stage(node1, "validation_pass")
    print(f"[推进] {r.from_stage} → {r.to_stage}, action={r.action_taken}")
    assert r.to_stage == "PEEL"
    print(f"[PEEL阶段] energy={lc._nodes[node1].energy:.3f}")

    # ── 测试2：PEEL阶段自动剪枝 ────────────────────────────────────────────────
    print("\n── 测试2：PEEL阶段能量耗尽自动剪枝 ──")
    # 直接将节点推入PEEL
    node2 = lc.register_node("node_002", initial_tension=0.6)
    lc.advance_stage("node_002", "validation_pass")
    lc.advance_stage("node_002", "tension_stable")
    lc.advance_stage("node_002", "validation_pass")
    assert lc.get_node_stage("node_002") == "PEEL"

    # 能量耗尽触发PEEL→TRUNCATE
    lc._nodes["node_002"].energy = 0.01  # 模拟能量耗尽
    r = lc.advance_stage("node_002", "energy_depleted")
    print(f"[能量耗尽推进] {r.from_stage} → {r.to_stage}")

    # 手动prune_node（PEEL阶段）
    node3 = lc.register_node("node_003", initial_tension=0.5)
    lc.advance_stage("node_003", "validation_pass")
    lc.advance_stage("node_003", "tension_stable")
    lc.advance_stage("node_003", "validation_pass")
    pr = lc.prune_node("node_003", reason="weak_connection")
    print(f"[剪枝] node_003: status={pr.status}, energy_freed={pr.energy_freed:.3f}, "
          f"connections_removed={pr.connections_removed}")
    assert pr.status == "success"
    assert "node_003" not in lc._nodes

    # ── 测试3：TRUNCATE强制删除 ───────────────────────────────────────────────
    print("\n── 测试3：TRUNCATE强制删除 ──")
    node4 = lc.register_node("node_004", initial_tension=0.9)
    lc.advance_stage("node_004", "validation_pass")
    result = lc.trigger_truncate("node_004", reason="overload")
    print(f"[TRUNCATE] 节点已截断: {result}")
    assert "node_004" not in lc._nodes

    # TRUNCATE不可二次截断
    result2 = lc.trigger_truncate("node_004", reason="overload")
    assert result2 == "node_004"  # 返回ID但不报错

    # ── 测试4：RECURSE生成子节点 ──────────────────────────────────────────────
    print("\n── 测试4：RECURSE断裂重编 ──")
    node5 = lc.register_node("node_005", initial_tension=0.5)
    lc.advance_stage("node_005", "validation_pass")
    lc.advance_stage("node_005", "tension_stable")
    # 模拟断裂触发RECURSE
    lc._nodes["node_005"].connection_strength = 0.1  # 模拟断裂
    r = lc.advance_stage("node_005", "fracture")
    print(f"[断裂→RECURSE] {r.from_stage} → {r.to_stage}, action={r.action_taken}")
    assert r.to_stage == "RECURSE"

    # RECURSE → BIND（新绑定）
    children = lc._nodes["node_005"].metadata.get("recurse_children", [])
    print(f"[RECURSE子节点] {children}")
    r = lc.advance_stage("node_005", "new_bindings")
    print(f"[新绑定→BIND] {r.from_stage} → {r.to_stage}")
    assert r.to_stage == "BIND"

    # ── 统计 ──────────────────────────────────────────────────────────────────
    print("\n── 生命周期统计 ──")
    stats = lc.get_lifecycle_stats()
    print(f"[统计] stage_counts={stats.stage_counts}")
    print(f"[统计] total_nodes={stats.total_nodes}, total_prunes={stats.total_prunes}")
    print(f"[统计] recently_warning={stats.recently_warning}")

    # ── 阶段过滤 ──────────────────────────────────────────────────────────────
    print("\n── 阶段过滤查询 ──")
    bind_nodes = lc.get_all_nodes(stage_filter="BIND")
    print(f"[BIND阶段节点] {[n.node_id for n in bind_nodes]}")
    peel_nodes = lc.get_all_nodes(stage_filter="PEEL")
    print(f"[PEEL阶段节点] {[n.node_id for n in peel_nodes]}")

    print(f"\n[最终状态] {lc}")
    print(f"[阶段分布] {lc.get_stage_distribution()}")
    print("\n[OK] 所有测试通过")
