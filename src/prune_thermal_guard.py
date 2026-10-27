"""
prune_thermal_guard.py - 剪枝热保护
====================================
将"拓扑热保护"(TopologyThermalMonitor) 的分级张力信号转译为
"节点剪枝"(ConstraintLifecycle) 的保护动作,防止过热状态下盲目接入/堆积节点。

分级响应(来源:TODO_MASTER.md → 全系统深层-表层架构升级 → 节点剪枝优化 P1):
  NORMAL      → 正常通行,无干预
  L1_WARNING  → 警告 + 减速新节点接入(标记 admission_paused,记入日志)
  L2_OVERLOAD → 触发卸载:对弱连接节点执行 prune_node(reason="thermal_unload")
  L3_CRITICAL → 强制切断:对所有活跃节点 trigger_truncate(reason="thermal_emergency")

依赖: topology_thermal_monitor / constraint_lifecycle
本地化: _agent_memory/prune_thermal_guard_state.json

层级: P1(节点剪枝优化)
创建: 2026-07-21
"""

import json
import sys
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────────────────────────────

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
STATE_FILE = AGENT_MEM / "prune_thermal_guard_state.json"

SRC = WORKSPACE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

logger = logging.getLogger(__name__)


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


# ── 数据类 ───────────────────────────────────────────────────────────────────

@dataclass
class GuardReport:
    """guard_once() 的返回值"""
    level: str = "NORMAL"
    tension_integral: float = 0.0
    action_taken: str = "正常通行"
    admission_paused: bool = False
    unloaded: list = field(default_factory=list)     # L2 卸载的弱连接节点
    truncated: list = field(default_factory=list)     # L3 强制切断的节点
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 主类 ─────────────────────────────────────────────────────────────────────

class PruneThermalGuard:
    """
    剪枝热保护。

    轮询 TopologyThermalMonitor.check() 的分级结果,对照 ConstraintLifecycle
    执行对应的保护动作。L1 减速接入、L2 卸载弱连接、L3 强制切断。
    """

    def __init__(
        self,
        lifecycle: Optional[object] = None,
        monitor: Optional[object] = None,
        fresh: bool = False,
    ):
        """
        参数:
          lifecycle: ConstraintLifecycle 实例;None 则内部新建
          monitor:   TopologyThermalMonitor 实例;None 则内部新建
          fresh:     True 时清空本地保护状态
        """
        from constraint_lifecycle import ConstraintLifecycle
        from topology_thermal_monitor import TopologyThermalMonitor

        # 注意:ConstraintLifecycle 定义了 __len__,空实例 bool() 为 False,
        # 故必须用 `is not None` 判断,不能用 `or`。
        self._lifecycle = lifecycle if lifecycle is not None else ConstraintLifecycle()
        self._monitor = monitor if monitor is not None else TopologyThermalMonitor()

        self._admission_paused = False
        self._session_start = time.time()
        self._total_unloaded = 0
        self._total_truncated = 0
        self._guard_log: list[dict] = []

        if fresh:
            self._load_state(clear=True)
        else:
            self._load_state()

    # ── 持久化 ──────────────────────────────────────────────────────────────

    def _load_state(self, clear: bool = False):
        if clear:
            self._admission_paused = False
            self._total_unloaded = 0
            self._total_truncated = 0
            self._guard_log = []
            self._save_state()
            return
        data = _load_json(STATE_FILE)
        self._admission_paused = data.get("admission_paused", False)
        self._total_unloaded = data.get("total_unloaded", 0)
        self._total_truncated = data.get("total_truncated", 0)
        self._guard_log = data.get("guard_log", [])
        self._session_start = data.get("session_start", time.time())

    def _save_state(self):
        _save_json(STATE_FILE, {
            "admission_paused": self._admission_paused,
            "total_unloaded": self._total_unloaded,
            "total_truncated": self._total_truncated,
            "guard_log": self._guard_log[-100:],
            "session_start": self._session_start,
            "saved_at": time.time(),
        })

    # ── 准入闸门 ─────────────────────────────────────────────────────────────

    def can_admit_node(self) -> bool:
        """查询当前是否允许接入新节点(L1 及以上减速接入)"""
        return not self._admission_paused

    # ── 核心: 保护一次 ─────────────────────────────────────────────────────

    def guard_once(self) -> GuardReport:
        """
        执行一次热保护检查,根据分级结果采取动作。

        返回: GuardReport
        """
        report = GuardReport()
        thermal = self._monitor.check()
        report.level = thermal.level
        report.tension_integral = thermal.tension_integral

        if thermal.level == "NORMAL":
            # 恢复正常接入
            if self._admission_paused:
                self._admission_paused = False
                logger.info("[prune_thermal_guard] 张力回落 NORMAL,恢复节点接入")
            report.action_taken = "正常通行"
            self._save_state()
            return report

        if thermal.level == "L1_WARNING":
            # 减速新节点接入(不删节点,仅标记)
            self._admission_paused = True
            report.admission_paused = True
            report.action_taken = "L1 警告 + 减速新节点接入"
            self._log_guard(report, "L1_WARNING")
            logger.info(
                f"[prune_thermal_guard] L1_WARNING (tension={thermal.tension_integral:.3f}):"
                f"减速新节点接入"
            )
            self._save_state()
            return report

        if thermal.level == "L2_OVERLOAD":
            # 卸载弱连接节点
            self._admission_paused = True
            report.admission_paused = True
            unloaded = self._unload_weak_nodes()
            report.unloaded = unloaded
            report.action_taken = f"L2 卸载 {len(unloaded)} 个弱连接节点"
            self._log_guard(report, "L2_OVERLOAD")
            logger.warning(
                f"[prune_thermal_guard] L2_OVERLOAD (tension={thermal.tension_integral:.3f}):"
                f"卸载弱连接节点 {unloaded}"
            )
            self._save_state()
            return report

        if thermal.level == "L3_CRITICAL":
            # 强制切断所有活跃节点
            self._admission_paused = True
            report.admission_paused = True
            truncated = self._emergency_truncate_all()
            report.truncated = truncated
            report.action_taken = f"L3 强制切断 {len(truncated)} 个节点"
            self._log_guard(report, "L3_CRITICAL")
            logger.error(
                f"[prune_thermal_guard] ⚡ L3_CRITICAL (tension={thermal.tension_integral:.3f}):"
                f"强制切断所有活跃节点 {truncated}"
            )
            self._save_state()
            return report

        # 未知级别兜底
        report.action_taken = "未知级别,无动作"
        self._save_state()
        return report

    # ── L2: 卸载弱连接 ───────────────────────────────────────────────────────

    def _unload_weak_nodes(self) -> list:
        """
        L2 级：卸载弱连接节点。
        连接强度 < 0.3 或 处于 PEEL 阶段且无连接 → prune_node(reason="weak_connection")
        （reason 必须用 ConstraintLifecycle 合法枚举，见 VALID_PRUNE_REASONS）
        """
        targets = []
        for node in list(self._lifecycle._nodes.values()):
            weak = node.connection_strength < 0.3
            peel_no_conn = node.stage == "PEEL" and len(node.connections) == 0
            if weak or peel_no_conn:
                targets.append(node.node_id)

        unloaded = []
        for nid in targets:
            pr = self._lifecycle.prune_node(nid, reason="weak_connection")
            if pr.status == "success":
                unloaded.append(nid)
        self._total_unloaded += len(unloaded)
        return unloaded

    # ── L3: 强制切断 ─────────────────────────────────────────────────────────

    def _emergency_truncate_all(self) -> list:
        """
        L3 级:强制切断所有活跃节点。
        对所有仍在生命周期中的节点执行 trigger_truncate(reason="thermal_emergency")。
        """
        targets = [n.node_id for n in list(self._lifecycle._nodes.values())]
        truncated = []
        for nid in targets:
            self._lifecycle.trigger_truncate(nid, reason="thermal_emergency")
            truncated.append(nid)
        self._total_truncated += len(truncated)
        return truncated

    # ── 日志 ─────────────────────────────────────────────────────────────────

    def _log_guard(self, report: GuardReport, level: str):
        self._guard_log.append({
            "level": level,
            "tension_integral": report.tension_integral,
            "action": report.action_taken,
            "unloaded": report.unloaded,
            "truncated": report.truncated,
            "ts": time.time(),
        })

    # ── 便捷查询 ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """返回热保护统计"""
        return {
            "admission_paused": self._admission_paused,
            "total_unloaded": self._total_unloaded,
            "total_truncated": self._total_truncated,
            "guard_events": len(self._guard_log),
            "current_level": self._monitor.check().level if hasattr(self._monitor, "check") else "unknown",
            "lifecycle_nodes": len(self._lifecycle),
        }

    def __repr__(self) -> str:
        return (
            f"PruneThermalGuard(paused={self._admission_paused}, "
            f"unloaded={self._total_unloaded}, truncated={self._total_truncated})"
        )


# ── 验证 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PruneThermalGuard 测试")
    print("=" * 60)

    from constraint_lifecycle import ConstraintLifecycle
    from topology_thermal_monitor import TopologyThermalMonitor, ThermalReport

    lc = ConstraintLifecycle(fresh=True)
    monitor = TopologyThermalMonitor(fresh=True)

    guard = PruneThermalGuard(lifecycle=lc, monitor=monitor, fresh=True)
    print(f"[初始化] {guard}")

    # 用 fake check 驱动分级(直接验证 guard 的响应逻辑,
    # 避免依赖 surface_tension_state.json 实时值)
    def make_check(level, integral):
        def _fake():
            return ThermalReport(
                level=level, tension_integral=integral,
                threshold_l1=0.6, threshold_l2=0.8, threshold_l3=1.0,
                recommended_action="fake", cooldown_until=None,
            )
        return _fake

    # ── 测试1: NORMAL → 正常通行 ─────────────────────────────────────────────
    print("\n── 测试1:NORMAL → 正常通行 ──")
    monitor.check = make_check("NORMAL", 0.3)
    r = guard.guard_once()
    print(f"[保护] level={r.level}, action={r.action_taken}")
    assert r.level == "NORMAL"
    assert r.action_taken == "正常通行"
    assert guard.can_admit_node() is True
    print("  ✓ 通过")

    # ── 测试2: L1_WARNING → 减速接入 ─────────────────────────────────────────
    print("\n── 测试2:L1_WARNING → 减速接入 ──")
    monitor.check = make_check("L1_WARNING", 0.65)
    r = guard.guard_once()
    print(f"[保护] level={r.level}, action={r.action_taken}, paused={r.admission_paused}")
    assert r.level == "L1_WARNING"
    assert r.admission_paused is True
    assert guard.can_admit_node() is False
    print("  ✓ L1 减速接入生效")

    # ── 测试3: L2_OVERLOAD → 卸载弱连接 ──────────────────────────────────────
    print("\n── 测试3:L2_OVERLOAD → 卸载弱连接 ──")
    # 注册强连接节点 + 弱连接节点
    lc.register_node("node_strong", initial_tension=0.5, connections=["a", "b"])
    lc._nodes["node_strong"].connection_strength = 0.8
    lc.register_node("node_weak", initial_tension=0.5, connections=["x"])
    lc._nodes["node_weak"].connection_strength = 0.1  # 弱连接

    monitor.check = make_check("L2_OVERLOAD", 0.85)
    r = guard.guard_once()
    print(f"[保护-L2] level={r.level}, action={r.action_taken}, unloaded={r.unloaded}")
    assert r.level == "L2_OVERLOAD"
    assert "node_weak" in r.unloaded, "弱连接节点应被卸载"
    assert "node_strong" not in r.unloaded, "强连接节点应保留"
    print("  ✓ L2 弱连接卸载生效")

    # ── 测试4: L3_CRITICAL → 强制切断 ────────────────────────────────────────
    print("\n── 测试4:L3_CRITICAL → 强制切断 ──")
    # 重新注册一些节点
    lc.register_node("node_a", initial_tension=0.5, connections=["p"])
    lc.register_node("node_b", initial_tension=0.5, connections=["q"])
    monitor.check = make_check("L3_CRITICAL", 1.0)
    r = guard.guard_once()
    print(f"[保护-L3] level={r.level}, action={r.action_taken}, truncated={r.truncated}")
    assert r.level == "L3_CRITICAL"
    assert len(r.truncated) >= 2, "应强制切断所有活跃节点"
    assert "node_a" in r.truncated and "node_b" in r.truncated
    print("  ✓ L3 强制切断生效")

    # ── 测试5: 统计 ──────────────────────────────────────────────────────────
    print("\n── 测试5:统计 ──")
    stats = guard.get_stats()
    print(f"[统计] {stats}")
    print(f"[最终] {guard}")
    print("\n[OK] 所有测试通过")
