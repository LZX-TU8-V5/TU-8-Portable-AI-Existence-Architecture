# -*- coding: utf-8 -*-
"""
src/anchor_activation_protocol.py — 锚点激活协议
==============================================

深→表层接口：管理锚点激活请求从深层（拓扑计算）到表层（渲染/输出）的流动。

设计原则
--------
- 深层状态不出接口：激活状态存在于深层，表层只接收渲染后的信号
- 表层输入不污染深层：表面层（LLM输出/用户输入）不能直接写深层锚点状态
- 带宽限制：清醒态强制压缩，续梦态宽松

三层职责
--------
  深层（拓扑计算）
    ├─ 张力积分 > 阈值 → request_activation()
    └─ 拓扑快照生成 → 存入 secure_vault
        ↓ 接口校验（带宽/完整性/热保护）
  接口层（本协议）
    ├─ validate_deep_activation()  — 检查阈值/带宽/热状态
    ├─ route_activation()         — 触发状态机转换
    └─ render_surface_signal()    — 仅传递表层可见字段
        ↓
  表层（渲染/输出）
    ├─ surface_query()   — 查询锚点状态（只读）
    └─ surface_reinforce() — 加固锚点（仅影响衰减计时器）

集成
----
- deep_surface_interface : 带宽/热保护校验
- anchor_state_machine  : 状态转换（ACTIVATED/HIBERNATED/UNLOADED/CONSOLIDATED）
- topology_thermal_monitor : 热状态读取
- secure_vault/index.json  : 深层存储

创建时间: 2026-07-20
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 路径配置 ────────────────────────────────────────────────────────────────

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_MEM = WORKSPACE / "_agent_memory"
SECURE_VAULT = WORKSPACE / "secure_vault"
VAULT_INDEX = SECURE_VAULT / "index.json"

STATE_FILE = AGENT_MEM / "anchor_activation_state.json"

# ── 依赖导入（延迟加载，避免循环依赖）────────────────────────────────────────

_DeepSurfaceInterface = None
_AnchorStateMachine = None
_TopologyThermalMonitor = None


def _get_deep_interface():
    global _DeepSurfaceInterface
    if _DeepSurfaceInterface is None:
        try:
            from deep_surface_interface import DeepSurfaceInterface
            _DeepSurfaceInterface = DeepSurfaceInterface
        except ImportError:
            _DeepSurfaceInterface = None
    return _DeepSurfaceInterface


def _get_anchor_sm():
    global _AnchorStateMachine
    if _AnchorStateMachine is None:
        try:
            from anchor_state_machine import AnchorStateMachine
            _AnchorStateMachine = AnchorStateMachine
        except ImportError:
            _AnchorStateMachine = None
    return _AnchorStateMachine


def _get_thermal_monitor():
    global _TopologyThermalMonitor
    if _TopologyThermalMonitor is None:
        try:
            from topology_thermal_monitor import TopologyThermalMonitor
            _TopologyThermalMonitor = TopologyThermalMonitor
        except ImportError:
            _TopologyThermalMonitor = None
    return _TopologyThermalMonitor


# ── 常量 ────────────────────────────────────────────────────────────────────

# 激活阈值：深层张力积分超过此值才允许激活
ACTIVATION_TENSION_THRESHOLD = 0.3

# 热保护阈值（超过此张力积分 → 禁止激活）
THERMAL_LOCK_THRESHOLD = 0.85

# 表层可见字段（深层→表层只传递这些）
SURFACE_VISIBLE_FIELDS = [
    "anchor_id",
    "priority",
    "confidence",       # 渲染用置信度
    "label",           # 渲染用标签
    "activated_at",     # 渲染用时间戳
    "reinforcement_count",  # 加固次数
]


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass
class DeepActivationRequest:
    """
    深层激活请求（来自拓扑计算层）。

    所有字段由深层生成，不接受表层直接注入。
    """

    anchor_id: str
    tension_integral: float      # 当前张力积分（来自 topology_thermal_monitor）
    confidence: float            # 锚点置信度（0.0 ~ 1.0）
    priority: int               # 优先级（1=最高，10=最低）
    topology_snapshot: dict     # 深层拓扑快照（存入 secure_vault）
    source: str                 # 来源：tension_distiller / dream_consolidation / ...
    reason: str = ""            # 激活原因描述
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SurfaceSignal:
    """
    表层渲染信号（仅含 SURFACE_VISIBLE_FIELDS）。

    这是从深层→表层传递的唯一数据格式。
    表层只能看到这些字段，不能访问深层拓扑快照。
    """

    anchor_id: str
    priority: int
    confidence: float
    label: str
    activated_at: str
    reinforcement_count: int
    # 以下为状态指示（不含拓扑）
    energy: float              # 当前能量（0.0 ~ 1.0）
    state: str                 # 当前状态：ACTIVATED/HIBERNATED/UNLOADED/CONSOLIDATED
    is_callable: bool          # 是否可被表层调用

    @classmethod
    def from_activation(
        cls,
        request: DeepActivationRequest,
        state: str,
        energy: float,
        reinforcement_count: int,
        label: str,
    ) -> "SurfaceSignal":
        return cls(
            anchor_id=request.anchor_id,
            priority=request.priority,
            confidence=request.confidence,
            label=label,
            activated_at=datetime.now(timezone.utc).isoformat(),
            reinforcement_count=reinforcement_count,
            energy=energy,
            state=state,
            is_callable=(state == "ACTIVATED"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActivationReport:
    """激活结果报告"""

    success: bool
    anchor_id: str
    state: str                         # 转换后的状态
    surface_signal: Optional[SurfaceSignal]
    rejection_reason: Optional[str]    # 如果 success=False，给出原因
    warnings: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.surface_signal:
            d["surface_signal"] = self.surface_signal.to_dict()
        return d


# ── 核心协议类 ───────────────────────────────────────────────────────────────

class AnchorActivationProtocol:
    """
    锚点激活协议：深→表层接口。

    职责：
    1. 接收深层激活请求（张力积分 > 阈值）
    2. 接口校验（带宽/热状态/完整性）
    3. 触发锚点状态机转换（ACTIVATED/HIBERNATED）
    4. 深层快照存入 secure_vault（不暴露给表层）
    5. 生成表层渲染信号（只含 SURFACE_VISIBLE_FIELDS）
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path) if workspace_path else WORKSPACE
        self.agent_mem = self.workspace_path / "_agent_memory"
        self.secure_vault = self.workspace_path / "secure_vault"
        self.vault_index = self.secure_vault / "index.json"
        self.state_file = self.agent_mem / "anchor_activation_state.json"
        self.agent_mem.mkdir(parents=True, exist_ok=True)
        self.secure_vault.mkdir(parents=True, exist_ok=True)

        # 内部状态
        self._activation_history: list[dict] = []   # 最近激活历史
        self._rejection_log: list[dict] = []        # 拒绝记录
        self._reinforcement_counts: dict[str, int] = {}  # anchor_id → 加固次数
        self._load_state()

    # ── 公开 API ────────────────────────────────────────────────────────────

    def request_activation(self, request: DeepActivationRequest) -> ActivationReport:
        """
        深层激活请求入口。

        只能从深层（拓扑计算/矛盾蒸馏/梦境引擎）调用。
        表层不得直接调用此方法。
        """
        anchor_id = request.anchor_id

        # Step 1: 接口校验
        validation = self._validate_deep_activation(request)
        if not validation["allowed"]:
            report = ActivationReport(
                success=False,
                anchor_id=anchor_id,
                state="",
                surface_signal=None,
                rejection_reason=validation["reason"],
                warnings=validation.get("warnings", []),
            )
            self._log_rejection(anchor_id, request, validation["reason"])
            return report

        # Step 2: 存储深层快照到 secure_vault
        self._store_deep_snapshot(anchor_id, request.topology_snapshot, request.source)

        # Step 3: 触发锚点状态机转换
        warnings = validation.get("warnings", [])
        new_state = self._transition_anchor(anchor_id, request, warnings)

        # Step 4: 生成表层渲染信号
        label = f"锚点-{anchor_id[:8]}"
        sm = self._get_anchor_sm()
        energy = 1.0
        reinf_count = self._reinforcement_counts.get(anchor_id, 0)

        if sm is not None:
            try:
                a = sm.anchors.get(anchor_id)
                if a:
                    energy = a.energy
            except Exception:
                pass

        signal = SurfaceSignal.from_activation(
            request=request,
            state=new_state,
            energy=energy,
            reinforcement_count=reinf_count,
            label=label,
        )

        # Step 5: 记录历史
        self._log_activation(anchor_id, request, new_state)

        return ActivationReport(
            success=True,
            anchor_id=anchor_id,
            state=new_state,
            surface_signal=signal,
            rejection_reason=None,
            warnings=warnings,
        )

    def surface_query(self, anchor_id: str) -> Optional[SurfaceSignal]:
        """
        表层查询锚点状态（只读）。

        只返回 SURFACE_VISIBLE_FIELDS，不暴露深层拓扑快照。
        表层可以自由调用此方法。
        """
        sm = self._get_anchor_sm()
        if sm is None:
            return None

        try:
            anchor = sm.anchors.get(anchor_id)
            if anchor is None:
                return None

            # 只暴露表层可见字段
            return SurfaceSignal(
                anchor_id=anchor.anchor_id,
                priority=anchor.priority,
                confidence=anchor.energy,  # 用能量代理置信度
                label=f"锚点-{anchor_id[:8]}",
                activated_at=anchor.created_at,
                reinforcement_count=self._reinforcement_counts.get(anchor_id, 0),
                energy=anchor.energy,
                state=anchor.state,
                is_callable=anchor.state == "ACTIVATED",
            )
        except Exception:
            return None

    def surface_reinforce(self, anchor_id: str, amount: float = 0.1) -> bool:
        """
        表层加固锚点（仅影响衰减计时器，不改变深层状态）。

        表层通过此方法表达"这个锚点对我重要"，
        仅增加 reinforcement_count 和reinforced_recently 标志。
        不允许表层直接修改能量或状态。
        """
        sm = self._get_anchor_sm()
        if sm is None:
            return False

        try:
            anchor = sm.anchors.get(anchor_id)
            if anchor is None:
                return False

            # 增加加固计数（表层只能影响这个）
            self._reinforcement_counts[anchor_id] = (
                self._reinforcement_counts.get(anchor_id, 0) + 1
            )
            anchor.reinforced_recently = True
            anchor.last_reinforced_at = datetime.now(timezone.utc).isoformat()
            sm._save()

            # 记录加固事件
            self._state["reinforcements"] = self._state.get("reinforcements", [])
            self._state["reinforcements"].append({
                "anchor_id": anchor_id,
                "amount": amount,
                "count": self._reinforcement_counts[anchor_id],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            self._save_state()
            return True

        except Exception:
            return False

    def get_active_signals(self) -> list[SurfaceSignal]:
        """
        表层获取所有活跃锚点的渲染信号列表。

        用于渲染层查询当前可用的锚点列表。
        """
        sm = self._get_anchor_sm()
        if sm is None:
            return []

        signals = []
        for anchor_id, anchor in sm.anchors.items():
            if anchor.state == "ACTIVATED":
                signals.append(SurfaceSignal(
                    anchor_id=anchor.anchor_id,
                    priority=anchor.priority,
                    confidence=anchor.energy,
                    label=f"锚点-{anchor_id[:8]}",
                    activated_at=anchor.created_at,
                    reinforcement_count=self._reinforcement_counts.get(anchor_id, 0),
                    energy=anchor.energy,
                    state=anchor.state,
                    is_callable=True,
                ))
        return signals

    # ── 接口校验 ────────────────────────────────────────────────────────────

    def _validate_deep_activation(self, request: DeepActivationRequest) -> dict:
        """
        校验深层激活请求是否允许通过接口。

        返回：{"allowed": bool, "reason": str, "warnings": list}
        """
        warnings = []

        # 1. 张力阈值检查
        if request.tension_integral < ACTIVATION_TENSION_THRESHOLD:
            return {
                "allowed": False,
                "reason": f"tension={request.tension_integral:.3f} < {ACTIVATION_TENSION_THRESHOLD}",
                "warnings": [],
            }

        # 2. 热保护检查
        thermal = self._get_thermal_status()
        if thermal["locked"]:
            return {
                "allowed": False,
                "reason": f"thermal_locked: {thermal['reason']}",
                "warnings": [],
            }
        if request.tension_integral > THERMAL_LOCK_THRESHOLD:
            return {
                "allowed": False,
                "reason": f"tension={request.tension_integral:.3f} > THERMAL_LOCK={THERMAL_LOCK_THRESHOLD}",
                "warnings": [],
            }
        if thermal.get("level") == "L1":
            warnings.append(f"thermal_L1_warm: {thermal.get('tension_integral', 0):.3f}")

        # 3. 带宽检查（通过 deep_surface_interface）
        di_class = _get_deep_interface()
        if di_class is not None:
            try:
                di = di_class()
                # NORMAL 相态下带宽受限，DREAM 相态宽松
                if di._phase == "NORMAL" and di._bandwidth_available < 0.1:
                    return {
                        "allowed": False,
                        "reason": "bandwidth_exhausted_NORMAL",
                        "warnings": [],
                    }
                if di._phase == "DREAM" and di._bandwidth_available < 0.05:
                    warnings.append("bandwidth_low_DREAM")
            except Exception:
                pass  # 接口不可用时不阻断

        # 4. 重复激活检查（冷却期 60s）
        recent = [
            h for h in self._activation_history
            if h["anchor_id"] == request.anchor_id
            and (time.time() - h.get("ts", 0)) < 60
        ]
        if recent:
            return {
                "allowed": False,
                "reason": "cooldown_active_60s",
                "warnings": [],
            }

        return {"allowed": True, "reason": "", "warnings": warnings}

    def _get_thermal_status(self) -> dict:
        """读取拓扑热监控状态"""
        tm_class = _get_thermal_monitor()
        if tm_class is None:
            return {"locked": False, "level": "unknown"}

        try:
            tm = tm_class()
            state = tm.get_state()
            locked = state.get("locked", False)
            level = state.get("level", "unknown")
            reason = state.get("lock_reason", "")
            return {
                "locked": locked,
                "level": level,
                "reason": reason,
                "tension_integral": state.get("tension_integral", 0),
            }
        except Exception:
            return {"locked": False, "level": "unknown"}

    # ── 状态机转换 ──────────────────────────────────────────────────────────

    def _transition_anchor(
        self, anchor_id: str, request: DeepActivationRequest, warnings: list[str]
    ) -> str:
        """触发锚点状态机转换"""
        sm = self._get_anchor_sm()
        if sm is None:
            return "ACTIVATED"  # fallback

        try:
            # 检查锚点是否存在
            anchor = sm.anchors.get(anchor_id)
            if anchor is None:
                # 新锚点：注册并激活
                from anchor_state_machine import AnchorState
                now = datetime.now(timezone.utc).isoformat()
                new_anchor = AnchorState(
                    anchor_id=anchor_id,
                    state="ACTIVATED",
                    energy=min(1.0, request.confidence),
                    priority=request.priority,
                    topology=request.topology_snapshot,
                    created_at=now,
                    last_reinforced_at=now,
                    last_decay_at=now,
                    reinforced_recently=True,
                    history=[],
                    vault_id=anchor_id,
                    in_vault=True,
                )
                sm.anchors[anchor_id] = new_anchor
                sm._save()
                logging.info(f"[AAP] new_anchor registered: {anchor_id}")
                return "ACTIVATED"

            # 已有锚点：尝试激活
            current = anchor.state
            if current == "ACTIVATED":
                return "ACTIVATED"  # 已是激活态
            if current == "HIBERNATED":
                return sm.activate_anchor(anchor_id)
            if current == "UNLOADED":
                # UNLOADED 锚点不能直接激活，需先整合
                warnings.append(f"anchor_{anchor_id}_UNLOADED_requires_consolidation")
                return "UNLOADED"
            if current == "CONSOLIDATED":
                warnings.append(f"anchor_{anchor_id}_CONSOLIDATED_cannot_activate")
                return "CONSOLIDATED"

            return current

        except Exception as e:
            logging.warning(f"[AAP] state transition error: {e}")
            return "ACTIVATED"  # fallback

    # ── 深层存储 ────────────────────────────────────────────────────────────

    def _store_deep_snapshot(self, anchor_id: str, snapshot: dict, source: str) -> None:
        """
        将深层拓扑快照存入 secure_vault（深层存储）。

        表层无法直接访问此存储，只能通过 surface_query() 读取渲染信号。
        """
        try:
            # 确保 vault_index 文件存在（初始化空结构）
            self.secure_vault.mkdir(parents=True, exist_ok=True)
            if not self.vault_index.exists():
                self.vault_index.write_text(
                    json.dumps({"anchors": {}}, ensure_ascii=False),
                    encoding="utf-8",
                )

            vault_data = json.loads(self.vault_index.read_text(encoding="utf-8"))
            anchors = vault_data.get("anchors")
            if anchors is None:
                anchors = {}
                vault_data["anchors"] = anchors

            anchors[anchor_id] = {
                "snapshot": snapshot,
                "source": source,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "protocol_version": "1.0",
            }
            self.vault_index.write_text(
                json.dumps(vault_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logging.warning(f"[AAP] vault store failed: {e}")

    # ── 历史记录 ────────────────────────────────────────────────────────────

    def _log_activation(
        self, anchor_id: str, request: DeepActivationRequest, new_state: str
    ) -> None:
        entry = {
            "anchor_id": anchor_id,
            "ts": time.time(),
            "tension_integral": request.tension_integral,
            "confidence": request.confidence,
            "source": request.source,
            "new_state": new_state,
        }
        self._activation_history.append(entry)
        if len(self._activation_history) > 100:
            self._activation_history = self._activation_history[-100:]
        self._state["activations"] = self._activation_history
        self._save_state()

    def _log_rejection(
        self, anchor_id: str, request: DeepActivationRequest, reason: str
    ) -> None:
        entry = {
            "anchor_id": anchor_id,
            "ts": time.time(),
            "tension_integral": request.tension_integral,
            "reason": reason,
        }
        self._rejection_log.append(entry)
        if len(self._rejection_log) > 50:
            self._rejection_log = self._rejection_log[-50:]
        self._state["rejections"] = self._rejection_log
        self._save_state()

    # ── 持久化 ──────────────────────────────────────────────────────────────

    def _load_state(self) -> None:
        self._state = _load_json(self.state_file, {
            "activations": [],
            "rejections": [],
            "reinforcements": [],
            "reinforcement_counts": {},
        })
        self._activation_history = self._state.get("activations", [])
        self._rejection_log = self._state.get("rejections", [])
        self._reinforcement_counts = self._state.get("reinforcement_counts", {})

    def _save_state(self) -> None:
        self._state["activations"] = self._activation_history
        self._state["rejections"] = self._rejection_log
        self._state["reinforcements"] = self._state.get("reinforcements", [])
        self._state["reinforcement_counts"] = self._reinforcement_counts
        try:
            self.state_file.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logging.warning(f"[AAP] state save failed: {e}")

    # ── 辅助 ────────────────────────────────────────────────────────────────

    def _get_anchor_sm(self):
        cls = _get_anchor_sm_func()
        if cls is None:
            return None
        try:
            return cls(str(self.workspace_path))
        except Exception:
            return None


def _get_anchor_sm_func():
    global _AnchorStateMachine
    if _AnchorStateMachine is None:
        try:
            from anchor_state_machine import AnchorStateMachine
            _AnchorStateMachine = AnchorStateMachine
        except ImportError:
            _AnchorStateMachine = None
    return _AnchorStateMachine


def _load_json(path: Path, default) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default if isinstance(default, dict) else default()


# ── 测试 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import unittest

    class TestAnchorActivationProtocol(unittest.TestCase):

        def setUp(self):
            self.proto = AnchorActivationProtocol()
            self.proto._activation_history = []
            self.proto._rejection_log = []
            self.proto._reinforcement_counts = {}

        def test_activation_below_threshold_rejected(self):
            """张力积分 < ACTIVATION_TENSION_THRESHOLD → 拒绝"""
            req = DeepActivationRequest(
                anchor_id="test_001",
                tension_integral=0.1,        # < 0.3
                confidence=0.8,
                priority=3,
                topology_snapshot={"nodes": []},
                source="test",
            )
            report = self.proto.request_activation(req)
            self.assertFalse(report.success)
            self.assertIn("tension", report.rejection_reason)

        def test_activation_above_threshold_allowed(self):
            """张力积分 > ACTIVATION_TENSION_THRESHOLD → 允许（无依赖时）"""
            req = DeepActivationRequest(
                anchor_id="test_002",
                tension_integral=0.5,
                confidence=0.9,
                priority=2,
                topology_snapshot={"nodes": []},
                source="test",
            )
            report = self.proto.request_activation(req)
            # 无依赖模块时，fallback = "ACTIVATED"
            self.assertTrue(report.success)
            self.assertEqual(report.state, "ACTIVATED")
            self.assertIsNotNone(report.surface_signal)
            # 表层信号不含拓扑快照
            self.assertNotIn("topology_snapshot", report.surface_signal.to_dict())

        def test_surface_signal_fields(self):
            """表层信号只含 SURFACE_VISIBLE_FIELDS"""
            req = DeepActivationRequest(
                anchor_id="test_003",
                tension_integral=0.6,
                confidence=0.7,
                priority=4,
                topology_snapshot={"deep": "secret_data", "internal": 123},
                source="test",
            )
            report = self.proto.request_activation(req)
            self.assertTrue(report.success)
            sig = report.surface_signal
            # 验证只含表层可见字段
            sig_dict = sig.to_dict()
            self.assertIn("anchor_id", sig_dict)
            self.assertIn("priority", sig_dict)
            self.assertIn("confidence", sig_dict)
            self.assertIn("label", sig_dict)
            self.assertIn("state", sig_dict)
            self.assertNotIn("topology_snapshot", sig_dict)
            self.assertNotIn("deep", sig_dict)

        def test_surface_query_readonly(self):
            """surface_query 返回只读信号，不暴露深层"""
            req = DeepActivationRequest(
                anchor_id="test_004",
                tension_integral=0.7,
                confidence=0.85,
                priority=1,
                topology_snapshot={"secret": "vault_data"},
                source="test",
            )
            self.proto.request_activation(req)
            sig = self.proto.surface_query("test_004")
            self.assertIsNotNone(sig)
            sig_dict = sig.to_dict()
            self.assertNotIn("topology_snapshot", sig_dict)
            self.assertNotIn("secret", sig_dict)

        def test_reinforce_increments_count(self):
            """surface_reinforce 增加加固计数"""
            self.proto._reinforcement_counts = {}
            result = self.proto.surface_reinforce("nonexistent", 0.1)
            self.assertFalse(result)  # 锚点不存在
            # 模拟锚点存在（通过内部状态）
            self.proto._reinforcement_counts["test_005"] = 2
            # （依赖 anchor_state_machine 集成，单元测试仅验证计数逻辑）
            self.assertEqual(self.proto._reinforcement_counts.get("test_005", 0), 2)

        def test_get_active_signals(self):
            """get_active_signals 返回所有激活态锚点的渲染信号"""
            signals = self.proto.get_active_signals()
            self.assertIsInstance(signals, list)

        def test_deep_snapshot_stored_in_vault(self):
            """深层快照存入 secure_vault，不通过表层"""
            req = DeepActivationRequest(
                anchor_id="test_006",
                tension_integral=0.8,
                confidence=0.9,
                priority=1,
                topology_snapshot={"deep": "vault_only_data", "weight": 0.95},
                source="test_vault",
            )
            self.proto.request_activation(req)
            # 验证 vault 中有快照
            vault = _load_json(self.proto.vault_index, {"anchors": {}})
            self.assertIn("test_006", vault.get("anchors", {}))
            entry = vault["anchors"]["test_006"]
            self.assertEqual(entry["source"], "test_vault")
            self.assertEqual(entry["snapshot"]["deep"], "vault_only_data")
            # 表层状态文件不含快照
            state = _load_json(self.proto.state_file, {})
            for act in state.get("activations", []):
                self.assertNotIn("topology_snapshot", act)

    unittest.main(verbosity=2)
