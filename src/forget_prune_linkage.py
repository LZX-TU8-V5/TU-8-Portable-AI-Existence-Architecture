"""
forget_prune_linkage.py — 遗忘-剪枝联动协议
============================================
将"自然遗忘衰减"(DreamDecay) 与 "节点剪枝"(ConstraintLifecycle) 联动，
使"被遗忘的拓扑碎片"在确认无新连接后自动从约束生命周期中删除，
并在"崩溃级张力"出现时强制剪枝并留痕。

联动规则（来源：TODO_MASTER.md → 全系统深层-表层架构升级 → 节点剪枝优化 P1）：
  1. 能量=0 + 无新连接 → 自动删除
     （DreamDecay 衰减到 prune_ready 且对应生命周期节点已无活跃连接
      → 调用 ConstraintLifecycle.prune_node(reason="energy_depleted")）
  2. 崩溃级张力 → 强制剪枝 + 日志
     （surface_tension_state.json 的 tension ≥ CRASH_TENSION_THRESHOLD
      → 对所有 prune_ready / 弱连接 / PEEL 阶段节点调用 trigger_truncate）

依赖: dream_decay / constraint_lifecycle / surface_tension_state.json
本地化: _agent_memory/forget_prune_linkage_state.json

层级: P1（节点剪枝优化）
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
STATE_FILE = AGENT_MEM / "forget_prune_linkage_state.json"
SURFACE_TENSION_FILE = AGENT_MEM / "surface_tension_state.json"

# 把 src 加入导入路径（用于 import constraint_lifecycle / dream_decay）
SRC = WORKSPACE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────

# 崩溃级张力阈值（基于 surface_tension_state.json 的 tension 字段，0-1 尺度）
# 当前数据 tension≈0.75，崩溃级设定在 0.85（高于常态、低于理论上限）
CRASH_TENSION_THRESHOLD = 0.85

# prune_ready 快照映射到生命周期节点的元数据键
NODE_ID_KEY = "node_id"


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
class LinkageReport:
    """link_once() 的返回值"""
    checked_snapshots: int = 0
    auto_pruned: list = field(default_factory=list)      # 能量=0+无连接 自动删除
    crash_triggered: bool = False
    crash_pruned: list = field(default_factory=list)      # 崩溃级张力强制剪枝
    skipped: list = field(default_factory=list)           # 未达删除条件，保留
    tension_value: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 主类 ─────────────────────────────────────────────────────────────────────

class ForgetPruneLinkage:
    """
    遗忘-剪枝联动协议。

    把 DreamDecay（遗忘）的 prune_ready 信号转译为 ConstraintLifecycle（剪枝）的
    实际节点删除动作；并在崩溃级张力出现时强制截断并留痕。
    """

    def __init__(
        self,
        decay_state_path: Optional[str] = None,
        lifecycle: Optional[object] = None,
        crash_threshold: float = CRASH_TENSION_THRESHOLD,
        fresh: bool = False,
    ):
        """
        参数:
          decay_state_path: DreamDecay 状态文件路径；None 用默认
          lifecycle:         ConstraintLifecycle 实例；None 则内部新建
          crash_threshold:   崩溃级张力阈值 [0,1]
          fresh:             True 时清空本地联动状态
        """
        from dream_decay import DreamDecay, STATE_FILE as DECAY_STATE
        from constraint_lifecycle import ConstraintLifecycle

        self._decay = DreamDecay(path=decay_state_path or DECAY_STATE)
        # 注意：ConstraintLifecycle 定义了 __len__，空实例 bool() 为 False，
        # 故必须用 `is not None` 判断，不能用 `or`（否则空生命周期会被误替换为新实例）。
        self._lifecycle = lifecycle if lifecycle is not None else ConstraintLifecycle()
        self._crash_threshold = crash_threshold

        self._session_start = time.time()
        self._total_auto_pruned = 0
        self._total_crash_pruned = 0
        self._crash_events: list[dict] = []

        if fresh:
            self._load_state(clear=True)
        else:
            self._load_state()

    # ── 持久化 ──────────────────────────────────────────────────────────────

    def _load_state(self, clear: bool = False):
        if clear:
            self._total_auto_pruned = 0
            self._total_crash_pruned = 0
            self._crash_events = []
            self._save_state()
            return
        data = _load_json(STATE_FILE)
        self._total_auto_pruned = data.get("total_auto_pruned", 0)
        self._total_crash_pruned = data.get("total_crash_pruned", 0)
        self._crash_events = data.get("crash_events", [])
        self._session_start = data.get("session_start", time.time())

    def _save_state(self):
        _save_json(STATE_FILE, {
            "total_auto_pruned": self._total_auto_pruned,
            "total_crash_pruned": self._total_crash_pruned,
            "crash_events": self._crash_events[-100:],
            "session_start": self._session_start,
            "saved_at": time.time(),
        })

    # ── 张力读取 ─────────────────────────────────────────────────────────────

    def get_current_tension(self) -> float:
        """读取 surface_tension_state.json 的 tension 字段"""
        st = _load_json(SURFACE_TENSION_FILE)
        return float(st.get("tension", 0.0))

    # ── 核心: 联动一次 ─────────────────────────────────────────────────────

    def link_once(self) -> LinkageReport:
        """
        执行一次完整联动：
          1. 推进 DreamDecay 衰减，获取 prune_ready 快照
          2. 对每个 prune_ready 快照：能量=0 且无新连接 → 自动删除对应节点
          3. 检测崩溃级张力 → 强制剪枝 + 日志

        返回: LinkageReport
        """
        report = LinkageReport()
        report.tension_value = self.get_current_tension()

        # ── 步骤1: 推进衰减 ──────────────────────────────────────────────
        decay_result = self._decay.apply_decay()
        prune_ready = self._decay.get_prune_ready()
        report.checked_snapshots = len(prune_ready)

        # ── 步骤2: 能量=0 + 无新连接 → 自动删除 ───────────────────────────
        for sid in prune_ready:
            snap = self._decay.get(sid)
            if not snap:
                continue
            energy = snap.get("energy", 1.0)
            node_id = snap.get("metadata", {}).get(NODE_ID_KEY, sid)

            # 无新连接判定：生命周期节点不存在 或 节点的 connections 为空
            has_connections = True
            if node_id in self._lifecycle._nodes:
                node = self._lifecycle._nodes[node_id]
                has_connections = len(node.connections) > 0

            if energy <= 0.0 and not has_connections:
                # 自动删除
                pr = self._lifecycle.prune_node(node_id, reason="energy_depleted")
                if pr.status == "success":
                    self._total_auto_pruned += 1
                    report.auto_pruned.append(node_id)
                    # 同步删除 decay 快照（遗忘完成）
                    self._decay._d.pop(sid, None)
                    self._decay._save()
                    logger.info(
                        f"[forget_prune] 自动删除: snapshot={sid} → node={node_id} "
                        f"(energy={energy:.3f}, 无新连接)"
                    )
            else:
                report.skipped.append({
                    "snapshot": sid,
                    "node": node_id,
                    "energy": round(energy, 3),
                    "has_connections": has_connections,
                })

        # ── 步骤3: 崩溃级张力 → 强制剪枝 + 日志 ───────────────────────────
        if report.tension_value >= self._crash_threshold:
            report.crash_triggered = True
            pruned = self._force_prune_crash()
            report.crash_pruned = pruned
            self._total_crash_pruned += len(pruned)
            self._crash_events.append({
                "tension": report.tension_value,
                "threshold": self._crash_threshold,
                "pruned": pruned,
                "ts": time.time(),
            })
            self._save_state()
            logger.warning(
                f"[forget_prune] ⚡ 崩溃级张力 {report.tension_value:.3f} ≥ "
                f"{self._crash_threshold}：强制剪枝 {len(pruned)} 个节点"
            )

        self._save_state()
        return report

    def _force_prune_crash(self) -> list:
        """
        崩溃级张力下的强制剪枝：
        对所有处于 PEEL / RECURSE 阶段，或已被标记 prune_ready 的节点执行 trigger_truncate。
        """
        targets = []
        for node in list(self._lifecycle._nodes.values()):
            if node.stage in ("PEEL", "RECURSE") or node.metadata.get("prune_ready"):
                targets.append(node.node_id)

        pruned = []
        for nid in targets:
            self._lifecycle.trigger_truncate(nid, reason="crash_tension")
            pruned.append(nid)
        return pruned

    # ── 便捷查询 ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """返回联动统计"""
        return {
            "total_auto_pruned": self._total_auto_pruned,
            "total_crash_pruned": self._total_crash_pruned,
            "crash_events": len(self._crash_events),
            "current_tension": self.get_current_tension(),
            "crash_threshold": self._crash_threshold,
            "lifecycle_nodes": len(self._lifecycle),
            "decay_snapshots": len(self._decay._d),
        }

    def __repr__(self) -> str:
        return (
            f"ForgetPruneLinkage(auto_pruned={self._total_auto_pruned}, "
            f"crash_pruned={self._total_crash_pruned}, "
            f"threshold={self._crash_threshold})"
        )


# ── 验证 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("ForgetPruneLinkage 测试")
    print("=" * 60)

    # 用临时 state 文件避免污染真实状态
    tmp = Path(tempfile.mkdtemp())
    decay_path = str(tmp / "dream_decay_state.json")

    # 准备 constraint_lifecycle（fresh）
    from constraint_lifecycle import ConstraintLifecycle
    lc = ConstraintLifecycle(fresh=True)

    link = ForgetPruneLinkage(
        decay_state_path=decay_path,
        lifecycle=lc,
        crash_threshold=0.85,
        fresh=True,
    )
    print(f"[初始化] {link}")

    # ── 测试1: 能量=0 + 无连接 → 自动删除 ──────────────────────────────────
    print("\n── 测试1：能量=0 + 无连接 → 自动删除 ──")
    # 注册一个生命周期节点（无任何连接）
    lc.register_node("node_auto_1", initial_tension=0.5, connections=[])
    # 注册一个对应的 decay 快照，能量=0，映射 node_id
    link._decay.register(
        "snap_auto_1", "topology_fragment", tension=0.0, energy=0.0,
        metadata={"node_id": "node_auto_1"},
    )
    # 直接把快照能量打到 0 且标记 prune_ready（模拟衰减完成）
    link._decay._d["snap_auto_1"]["energy"] = 0.0
    link._decay._d["snap_auto_1"]["prune_ready"] = True

    r = link.link_once()
    print(f"[联动] checked={r.checked_snapshots}, auto_pruned={r.auto_pruned}")
    print(f"[联动] skipped={r.skipped}")
    assert "node_auto_1" in r.auto_pruned, "node_auto_1 应被自动删除"
    assert "node_auto_1" not in lc._nodes, "节点应从生命周期中移除"
    print("  ✓ 通过")

    # ── 测试2: 能量=0 但有连接 → 保留 ───────────────────────────────────────
    print("\n── 测试2：能量=0 但有连接 → 保留（跳过） ──")
    lc.register_node("node_conn_1", initial_tension=0.5, connections=["node_other"])
    link._decay.register(
        "snap_conn_1", "topology_fragment", tension=0.0, energy=0.0,
        metadata={"node_id": "node_conn_1"},
    )
    link._decay._d["snap_conn_1"]["energy"] = 0.0
    link._decay._d["snap_conn_1"]["prune_ready"] = True

    r = link.link_once()
    print(f"[联动] auto_pruned={r.auto_pruned}")
    assert "node_conn_1" not in r.auto_pruned, "有连接的节点不应被删除"
    assert "node_conn_1" in lc._nodes, "节点应保留"
    print("  ✓ 通过")

    # ── 测试3: 崩溃级张力 → 强制剪枝 + 日志 ─────────────────────────────────
    print("\n── 测试3：崩溃级张力 → 强制剪枝 + 日志 ──")
    # 放一个 PEEL 阶段节点
    lc.register_node("node_peel_1", initial_tension=0.5)
    lc.advance_stage("node_peel_1", "validation_pass")
    lc.advance_stage("node_peel_1", "tension_stable")
    lc.advance_stage("node_peel_1", "validation_pass")  # → PEEL
    assert lc.get_node_stage("node_peel_1") == "PEEL"

    # 临时把 surface_tension 张力写到崩溃级
    fake_st = {"tension": 0.9, "components": {"residual": 0.4, "active": 0.5}}
    _save_json(SURFACE_TENSION_FILE, fake_st)

    r = link.link_once()
    print(f"[联动] crash_triggered={r.crash_triggered}, crash_pruned={r.crash_pruned}")
    assert r.crash_triggered is True, "应触发崩溃级剪枝"
    assert "node_peel_1" in r.crash_pruned, "PEEL 节点应被强制剪枝"
    assert "node_peel_1" not in lc._nodes, "节点应被截断移除"
    assert len(link._crash_events) >= 1, "应记录崩溃事件日志"
    print("  ✓ 通过")

    # 恢复 surface_tension（避免污染）
    _save_json(SURFACE_TENSION_FILE, {"tension": 0.75, "components": {"residual": 0.3, "active": 0.45}})

    # ── 测试4: 统计 ──────────────────────────────────────────────────────────
    print("\n── 测试4：统计 ──")
    stats = link.get_stats()
    print(f"[统计] {stats}")
    assert stats["total_auto_pruned"] >= 1
    assert stats["total_crash_pruned"] >= 1
    print("  ✓ 通过")

    print(f"\n[最终] {link}")
    print("\n[OK] 所有测试通过")
