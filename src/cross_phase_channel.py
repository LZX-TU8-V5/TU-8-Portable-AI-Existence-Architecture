# -*- coding: utf-8 -*-
"""
cross_phase_channel.py
=======================
TU-8 跨相态通道协议（Cross-Phase Channel Protocol）。

管理四种相态之间的数据通道：
    NORMAL  (清醒) / SLEEP (睡眠) / DREAM (续梦) / COLLAPSE (崩溃)

核心职责：
1. 打开/关闭跨相态通道（open_channel / close_channel）。
2. 通过通道传输数据（transfer），并计算传输保真度与拓扑污染风险。
3. 依据「阻抗矩阵」识别高风险传输（警告 / 禁止）。
4. 依据「带宽配额」识别过载传输（降保真度 / 拒绝）。
5. 状态持久化到 _agent_memory/cross_phase_channel_state.json。

集成：
- 读取：phase_state_machine（当前相态）
- 调用：deep_surface_interface（通道传输时调用）
- 写入：_agent_memory/cross_phase_channel_state.json
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# 路径配置（与 deep_surface_interface / phase_state_machine 保持一致）
# ─────────────────────────────────────────────────────────────────────────────

def _workspace() -> str:
    return os.environ.get(
        "QCLAW_WORKSPACE",
        os.path.join(os.environ.get("USERPROFILE", ""), ".qclaw", "workspace"),
    )


def _src() -> str:
    return os.path.join(_workspace(), "src")


def _agent_memory() -> str:
    return os.path.join(_workspace(), "_agent_memory")


def _state_path() -> str:
    return os.path.join(_agent_memory(), "cross_phase_channel_state.json")


# ─────────────────────────────────────────────────────────────────────────────
# 通道配置：阻抗矩阵 / 带宽配额 / 阈值
# ─────────────────────────────────────────────────────────────────────────────

# 阻抗矩阵：from_phase → to_phase → impedance（0~1，越高损耗越大）
PHASE_IMPEDANCE = {
    ("NORMAL", "SLEEP"): 0.3,    # 清醒→睡眠：低阻抗
    ("NORMAL", "DREAM"): 0.8,    # 清醒→续梦：高阻抗（异常）
    ("NORMAL", "COLLAPSE"): 0.9,  # 清醒→崩溃：极高阻抗
    ("SLEEP", "DREAM"): 0.2,     # 睡眠→续梦：极低阻抗（正常路径）
    ("SLEEP", "COLLAPSE"): 0.7,
    ("DREAM", "NORMAL"): 0.5,    # 续梦→清醒：中等阻抗
    ("DREAM", "SLEEP"): 0.3,
    ("DREAM", "COLLAPSE"): 0.6,
}

# 未定义相态对的默认阻抗：视为「禁止」（最高阻抗，杜绝未知污染路径）
DEFAULT_IMPEDANCE = 1.0

# 阻抗阈值
IMPEDANCE_THRESHOLD = 0.75  # 阻抗超过此值 → 警告
CRITICAL_IMPEDANCE = 0.90   # 阻抗超过此值 → 禁止传输

# 带宽配额： (from_phase, to_phase) → max_bandwidth_per_minute（单位：字节）
CHANNEL_BANDWIDTH = {
    ("NORMAL", "SLEEP"): 5000,    # 大带宽（正常过渡）
    ("SLEEP", "DREAM"): 10000,    # 超大带宽（续梦开放）
    ("DREAM", "NORMAL"): 5000,
    ("NORMAL", "DREAM"): 1000,    # 限制带宽（异常路径）
    ("NORMAL", "COLLAPSE"): 0,    # 禁止（崩溃态不输出）
    ("COLLAPSE", "NORMAL"): 0,
}

# 未定义相态对的默认带宽配额：0 = 禁止
DEFAULT_BANDWIDTH = 0

# 通道带宽统计窗口（秒）
BANDWIDTH_WINDOW_S = 60.0

# 过载时保真度折损系数（降低保真度而非拒绝时使用）
OVERLOAD_FIDELITY_PENALTY = 0.5

# 合法相态集合（用于校验）
VALID_PHASES = {"NORMAL", "SLEEP", "DREAM", "COLLAPSE"}


# ─────────────────────────────────────────────────────────────────────────────
# 返回类型（dataclass）
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ChannelStatus:
    """通道当前状态快照。"""
    channel_id: str
    from_phase: str
    to_phase: str
    impedance: float
    bandwidth_quota: int
    bandwidth_used: int
    window_start: float
    status: str            # "OPEN" / "CLOSED"
    opened_at: float
    closed_at: float | None
    reason: str
    warnings: list
    overload: bool
    opened_from_phase: str = ""   # 打开时的实际当前相态（审计用）

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "impedance": self.impedance,
            "bandwidth_quota": self.bandwidth_quota,
            "bandwidth_used": self.bandwidth_used,
            "window_start": self.window_start,
            "status": self.status,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "overload": self.overload,
            "opened_from_phase": self.opened_from_phase,
        }


@dataclass
class ChannelReport:
    """open_channel 的返回结果。"""
    channel_id: str
    success: bool
    from_phase: str
    to_phase: str
    impedance: float
    warnings: list
    message: str


@dataclass
class TransferReport:
    """transfer 的返回结果。"""
    success: bool
    fidelity: float
    impedance: float
    bandwidth_used: int
    overload: bool
    warnings: list
    surface_render: dict | None = None
    message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: str, default: Any = None) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _estimate_bandwidth(data: dict) -> int:
    """估算一次传输消耗的带宽（字节）。"""
    try:
        return len(json.dumps(data, ensure_ascii=False))
    except Exception:
        return len(str(data).encode("utf-8", "ignore"))


def _count_leaves(obj: Any) -> int:
    """递归统计拓扑中的叶子数量（用于复杂度估算）。"""
    if isinstance(obj, dict):
        if not obj:
            return 1
        return sum(_count_leaves(v) for v in obj.values())
    if isinstance(obj, (list, tuple, set)):
        if not obj:
            return 1
        return sum(_count_leaves(v) for v in obj)
    return 1


def _estimate_complexity(raw_data: dict) -> float:
    """
    估算数据复杂度（0~100 标度）。
    节点越多、叶子越多，复杂度越高 → 跨相态传输损耗越大。
    """
    topo = raw_data.get("topology", {}) or {}
    if not isinstance(topo, dict):
        topo = {}
    node_count = len(topo)
    leaf_count = _count_leaves(topo)
    raw = node_count * 0.5 + leaf_count * 0.1
    return min(100.0, float(raw))


# ─────────────────────────────────────────────────────────────────────────────
# 主类：CrossPhaseChannel
# ─────────────────────────────────────────────────────────────────────────────

class CrossPhaseChannel:
    """跨相态通道管理器。"""

    def __init__(self):
        self._channels: dict[str, dict] = {}
        self._history: list[dict] = []
        self._seq: int = 0
        # 延迟加载 deep_surface_interface，失败则降级（仅记录警告）
        self._iface = self._init_interface()

        self._load_state()

    # ── 外部集成：phase_state_machine / deep_surface_interface ──────────────

    def _init_interface(self):
        """初始化 deep_surface_interface（通道传输时调用）。失败返回 None。"""
        try:
            if _src() not in sys.path:
                sys.path.insert(0, _src())
            from deep_surface_interface import DeepSurfaceInterface
            return DeepSurfaceInterface()
        except Exception as exc:  # pragma: no cover - 降级路径
            self._history.append({
                "op": "init_warning",
                "ts": time.time(),
                "detail": f"deep_surface_interface 不可用：{exc!r}",
            })
            return None

    def get_current_phase(self) -> str:
        """
        读取当前相态（来自 phase_state_machine）。

        优先使用 PhaseStateMachine().get_phase()；
        失败则回退读取 interface_state.json / phase_state.json。
        """
        try:
            if _src() not in sys.path:
                sys.path.insert(0, _src())
            from phase_state_machine import PhaseStateMachine
            return PhaseStateMachine().get_phase()
        except Exception:
            pass
        # 回退：直接读取状态文件
        iface_state = _load_json(
            os.path.join(_agent_memory(), "interface_state.json"), {}
        )
        phase = iface_state.get("phase")
        if phase and phase in VALID_PHASES:
            return phase
        phase_state = _load_json(
            os.path.join(_agent_memory(), "phase_state.json"), {}
        )
        phase = phase_state.get("current_phase")
        if phase and phase in VALID_PHASES:
            return phase
        return "NORMAL"

    # ── 阻抗与带宽配置查询 ─────────────────────────────────────────────────

    def get_phase_impedance(self, from_phase: str, to_phase: str) -> float:
        """返回两个相态之间的阻抗值（0~1）。阻抗越高，传输损耗越大。"""
        return float(
            PHASE_IMPEDANCE.get((from_phase, to_phase), DEFAULT_IMPEDANCE)
        )

    def _bandwidth_quota(self, from_phase: str, to_phase: str) -> int:
        return int(
            CHANNEL_BANDWIDTH.get((from_phase, to_phase), DEFAULT_BANDWIDTH)
        )

    # ── 保真度 / 过载模型 ──────────────────────────────────────────────────

    def calculate_fidelity(self, raw_data: dict, impedance: float) -> float:
        """
        计算传输保真度。

        fidelity = 1 - (impedance * data_complexity / 100)
        阻抗越高、复杂度越高 → 保真度越低。
        """
        complexity = _estimate_complexity(raw_data)
        fidelity = 1.0 - (float(impedance) * complexity / 100.0)
        return round(max(0.0, min(1.0, fidelity)), 4)

    def _renew_bandwidth_window(self, ch: dict) -> None:
        """超过统计窗口则重置带宽计数。"""
        now = time.time()
        if now - ch["window_start"] > BANDWIDTH_WINDOW_S:
            ch["window_start"] = now
            ch["bandwidth_used"] = 0

    def check_overload(self, channel_id: str) -> bool:
        """
        检查通道是否过载。
        当前带宽使用 > 配额（或配额为 0）→ 过载。
        """
        ch = self._channels.get(channel_id)
        if not ch:
            return False
        self._renew_bandwidth_window(ch)
        quota = ch["bandwidth_quota"]
        if quota <= 0:
            return True  # 配额为 0 → 禁止传输 → 视为持续过载
        return ch["bandwidth_used"] >= quota

    # ── 通道生命周期 ───────────────────────────────────────────────────────

    def open_channel(self, from_phase: str, to_phase: str,
                    reason: str = "") -> ChannelReport:
        """打开跨相态通道。"""
        if from_phase not in VALID_PHASES or to_phase not in VALID_PHASES:
            return ChannelReport(
                channel_id="",
                success=False,
                from_phase=from_phase,
                to_phase=to_phase,
                impedance=DEFAULT_IMPEDANCE,
                warnings=[f"非法相态：{from_phase} → {to_phase}"],
                message="相态非法，无法打开通道",
            )

        impedance = self.get_phase_impedance(from_phase, to_phase)
        quota = self._bandwidth_quota(from_phase, to_phase)
        current_phase = self.get_current_phase()

        self._seq += 1
        channel_id = (
            f"ch_{from_phase.lower()}_{to_phase.lower()}_"
            f"{self._seq}_{int(time.time() * 1000)}"
        )

        warnings: list[str] = []

        # 阻抗分层：警告 / 禁止
        if impedance >= CRITICAL_IMPEDANCE:
            warnings.append(
                f"CRITICAL_IMPEDANCE({impedance:.2f})："
                f"{from_phase}→{to_phase} 禁止传输（拓扑污染风险极高）"
            )
        elif impedance >= IMPEDANCE_THRESHOLD:
            warnings.append(
                f"IMPEDANCE_WARNING({impedance:.2f})："
                f"{from_phase}→{to_phase} 高阻抗，传输将明显损耗"
            )

        # 带宽配额
        if quota <= 0:
            warnings.append(
                f"BANDWIDTH_FORBIDDEN：{from_phase}→{to_phase} 带宽配额为 0，禁止传输"
            )

        # 相态一致性审计（读取当前相态，仅警告不阻断）
        if from_phase != current_phase:
            warnings.append(
                f"PHASE_MISMATCH：通道从 {from_phase} 打开，"
                f"但当前相态为 {current_phase}"
            )

        now = time.time()
        ch = {
            "channel_id": channel_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "impedance": impedance,
            "bandwidth_quota": quota,
            "bandwidth_used": 0,
            "window_start": now,
            "status": "OPEN",
            "opened_at": now,
            "closed_at": None,
            "reason": reason,
            "warnings": warnings,
            "opened_from_phase": current_phase,
        }
        self._channels[channel_id] = ch

        self._record("open_channel", {
            "channel_id": channel_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "impedance": impedance,
            "bandwidth_quota": quota,
            "reason": reason,
        })

        msg = f"通道已打开：{from_phase}→{to_phase}（阻抗 {impedance:.2f}）"
        self._save_state()
        return ChannelReport(
            channel_id=channel_id,
            success=True,
            from_phase=from_phase,
            to_phase=to_phase,
            impedance=impedance,
            warnings=warnings,
            message=msg,
        )

    def close_channel(self, channel_id: str, reason: str = "") -> str:
        """关闭通道。返回状态摘要字符串。"""
        ch = self._channels.get(channel_id)
        if not ch:
            return f"通道不存在：{channel_id}"
        ch["status"] = "CLOSED"
        ch["closed_at"] = time.time()
        if reason:
            ch["reason"] = (ch["reason"] + " | close: " + reason).strip(" |")

        self._record("close_channel", {
            "channel_id": channel_id,
            "from_phase": ch["from_phase"],
            "to_phase": ch["to_phase"],
            "reason": reason,
        })
        self._save_state()
        return (
            f"通道已关闭：{ch['from_phase']}→{ch['to_phase']} "
            f"({channel_id})"
        )

    # ── 传输 ──────────────────────────────────────────────────────────────

    def transfer(self, channel_id: str, data: dict) -> TransferReport:
        """
        通过通道传输数据。

        data = {"topology": {...}, "tension": float, "priority": int,
                [其他自定义字段]}

        返回：success, fidelity, warnings。
        """
        ch = self._channels.get(channel_id)
        if not ch:
            return TransferReport(
                success=False, fidelity=0.0, impedance=DEFAULT_IMPEDANCE,
                bandwidth_used=0, overload=False,
                warnings=[f"通道不存在：{channel_id}"],
                message="传输失败：通道不存在",
            )
        if ch["status"] != "OPEN":
            return TransferReport(
                success=False, fidelity=0.0, impedance=ch["impedance"],
                bandwidth_used=0, overload=False,
                warnings=[f"通道已关闭：{channel_id}"],
                message="传输失败：通道已关闭",
            )

        from_phase = ch["from_phase"]
        to_phase = ch["to_phase"]
        impedance = ch["impedance"]
        warnings: list[str] = list(ch.get("warnings", []))
        size = _estimate_bandwidth(data)

        # 1) 临界阻抗：直接禁止传输（最高优先级）
        if impedance >= CRITICAL_IMPEDANCE:
            self._record("transfer_blocked_critical", {
                "channel_id": channel_id,
                "from_phase": from_phase,
                "to_phase": to_phase,
                "impedance": impedance,
            })
            return TransferReport(
                success=False, fidelity=0.0, impedance=impedance,
                bandwidth_used=0, overload=False,
                warnings=warnings + [
                    f"TRANSFER_FORBIDDEN：阻抗 {impedance:.2f} 达到临界值，禁止传输以防拓扑污染"
                ],
                message="传输被禁止：临界阻抗",
            )

        # 2) 计算通道自身保真度（阻抗 × 复杂度）
        fidelity = self.calculate_fidelity(data, impedance)

        # 3) 调用 deep_surface_interface（通道传输集成点）
        surface_render = None
        if self._iface is not None:
            deep_output = {
                "topology": data.get("topology", {}),
                "tension": data.get("tension", 0.0),
                "priority": data.get("priority", 0),
                "phase": to_phase,
                "metadata": {
                    "channel_id": channel_id,
                    "from_phase": from_phase,
                    "bandwidth_used": size,
                },
            }
            try:
                render = self._iface.deep_to_surface(
                    deep_output,
                    context={"channel_id": channel_id, "from_phase": from_phase},
                )
                surface_render = dict(render) if render is not None else None
                if surface_render:
                    iface_fidelity = float(surface_render.get("fidelity", 1.0))
                    # 接口层保真度（完整性/污染）与通道保真度取交集
                    fidelity = round(min(fidelity, max(0.0, iface_fidelity)), 4)
                    iface_warnings = surface_render.get("warnings", []) or []
                    for w in iface_warnings:
                        if w not in warnings:
                            warnings.append(w)
            except Exception as exc:
                warnings.append(f"deep_surface_interface 调用异常：{exc!r}")

        # 4) 过载检查（带宽配额）
        self._renew_bandwidth_window(ch)
        quota = ch["bandwidth_quota"]
        overload = False
        if quota <= 0:
            overload = True
            warnings.append("BANDWIDTH_FORBIDDEN：配额为 0，禁止传输")
            self._record("transfer_blocked_bandwidth", {
                "channel_id": channel_id, "from_phase": from_phase,
                "to_phase": to_phase, "size": size,
            })
            return TransferReport(
                success=False, fidelity=0.0, impedance=impedance,
                bandwidth_used=0, overload=True,
                warnings=warnings,
                message="传输被禁止：带宽配额为 0",
            )

        projected = ch["bandwidth_used"] + size
        if projected > quota:
            overload = True
            warnings.append(
                f"OVERLOAD：窗口内带宽 {ch['bandwidth_used']}+{size} "
                f"> 配额 {quota}，降低保真度"
            )
            # 过载：降低保真度而非直接拒绝（遵循「降低保真度或拒绝」）
            fidelity = round(fidelity * OVERLOAD_FIDELITY_PENALTY, 4)

        # 5) 提交传输（更新带宽计数）
        ch["bandwidth_used"] = projected

        success = fidelity > 0.0
        self._record("transfer", {
            "channel_id": channel_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "impedance": impedance,
            "fidelity": fidelity,
            "size": size,
            "overload": overload,
        })

        self._save_state()
        msg = (
            f"传输完成：{from_phase}→{to_phase}，"
            f"保真度 {fidelity:.3f}"
            + ("（过载降级）" if overload else "")
        )
        return TransferReport(
            success=success,
            fidelity=fidelity,
            impedance=impedance,
            bandwidth_used=size,
            overload=overload,
            warnings=warnings,
            surface_render=surface_render,
            message=msg,
        )

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get_open_channels(self) -> list:
        """返回当前开放的通道（ChannelStatus 列表）。"""
        return [
            self._to_status(ch)
            for ch in self._channels.values()
            if ch["status"] == "OPEN"
        ]

    def get_channel_status(self, channel_id: str):
        """返回通道状态（ChannelStatus | None）。"""
        ch = self._channels.get(channel_id)
        if not ch:
            return None
        return self._to_status(ch)

    def get_channel_history(self, limit: int = 20) -> list:
        """返回最近通道操作历史（最新在前）。"""
        return list(reversed(self._history[-limit:]))

    def _to_status(self, ch: dict) -> ChannelStatus:
        return ChannelStatus(
            channel_id=ch["channel_id"],
            from_phase=ch["from_phase"],
            to_phase=ch["to_phase"],
            impedance=ch["impedance"],
            bandwidth_quota=ch["bandwidth_quota"],
            bandwidth_used=ch["bandwidth_used"],
            window_start=ch["window_start"],
            status=ch["status"],
            opened_at=ch["opened_at"],
            closed_at=ch["closed_at"],
            reason=ch.get("reason", ""),
            warnings=list(ch.get("warnings", [])),
            overload=self.check_overload(ch["channel_id"]),
            opened_from_phase=ch.get("opened_from_phase", ""),
        )

    # ── 持久化 ──────────────────────────────────────────────────────────────

    def _record(self, op: str, detail: dict) -> None:
        self._history.append({
            "op": op,
            "ts": time.time(),
            "detail": detail,
        })
        # 限制内存中历史规模
        if len(self._history) > 500:
            self._history = self._history[-500:]

    def _save_state(self) -> None:
        state = {
            "channels": {
                cid: ch for cid, ch in self._channels.items()
            },
            "history": self._history,
            "seq": self._seq,
            "updated_at": time.time(),
        }
        _save_json(_state_path(), state)

    def _load_state(self) -> None:
        state = _load_json(_state_path(), {})
        if not isinstance(state, dict):
            return
        self._channels = {
            cid: ch for cid, ch in (state.get("channels") or {}).items()
            if isinstance(ch, dict)
        }
        self._history = state.get("history") or []
        self._seq = int(state.get("seq", 0) or 0)


# ─────────────────────────────────────────────────────────────────────────────
# 自检：四组验证
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ch = CrossPhaseChannel()

    def banner(title: str):
        print("\n" + "=" * 64)
        print("  " + title)
        print("=" * 64)

    # 测试1：正常路径（SLEEP→DREAM，低阻抗 0.2）
    banner("测试1：正常路径 SLEEP→DREAM（低阻抗）")
    r1 = ch.open_channel("SLEEP", "DREAM", reason="续梦开放")
    print(f"open -> {r1.message}")
    print(f"  阻抗={r1.impedance}  警告={r1.warnings}")
    data1 = {
        "topology": {"node_a": {"priority": 5}, "node_b": {"priority": 3}},
        "tension": 0.2,
        "priority": 7,
    }
    t1 = ch.transfer(r1.channel_id, data1)
    print(f"transfer -> success={t1.success} fidelity={t1.fidelity} "
          f"overload={t1.overload}")
    print(f"  警告={t1.warnings}")
    print(ch.close_channel(r1.channel_id, reason="测试完成"))

    # 测试2：异常路径（NORMAL→DREAM，高阻抗 0.8 → 警告）
    banner("测试2：异常路径 NORMAL→DREAM（高阻抗警告）")
    r2 = ch.open_channel("NORMAL", "DREAM", reason="异常直达")
    print(f"open -> {r2.message}")
    print(f"  阻抗={r2.impedance}  警告={r2.warnings}")
    data2 = {
        "topology": {
            "a": {"x": 1}, "b": {"y": 2}, "c": {"z": 3},
            "d": {"w": 4}, "e": {"v": 5}, "f": {"u": 6},
        },
        "tension": 0.4,
        "priority": 4,
    }
    t2 = ch.transfer(r2.channel_id, data2)
    print(f"transfer -> success={t2.success} fidelity={t2.fidelity} "
          f"overload={t2.overload}")
    print(f"  警告={t2.warnings}")
    print(ch.close_channel(r2.channel_id, reason="测试完成"))

    # 测试3：崩溃路径禁止（NORMAL→COLLAPSE，阻抗 0.9 = 临界）
    banner("测试3：崩溃路径禁止 NORMAL→COLLAPSE（临界阻抗）")
    r3 = ch.open_channel("NORMAL", "COLLAPSE", reason="试图进入崩溃")
    print(f"open -> {r3.message}")
    print(f"  阻抗={r3.impedance}  警告={r3.warnings}")
    data3 = {"topology": {"core": {"panic": True}}, "tension": 1.0, "priority": 9}
    t3 = ch.transfer(r3.channel_id, data3)
    print(f"transfer -> success={t3.success} fidelity={t3.fidelity}")
    print(f"  警告={t3.warnings}")
    print(ch.close_channel(r3.channel_id, reason="测试完成"))

    # 测试4：带宽配额超限（NORMAL→SLEEP，配额 5000/min）
    banner("测试4：带宽配额超限 NORMAL→SLEEP（配额 5000）")
    r4 = ch.open_channel("NORMAL", "SLEEP", reason="清醒转睡眠")
    print(f"open -> {r4.message}")
    print(f"  配额={r4.warnings}")
    # 构造大负载，多次传输以突破配额
    big_topo = {f"k{i}": {"v": "x" * 200} for i in range(40)}
    count = 0
    last = None
    for _ in range(6):
        payload = {"topology": big_topo, "tension": 0.3, "priority": 5}
        last = ch.transfer(r4.channel_id, payload)
        count += 1
        if last.overload:
            print(f"  第{count}次 transfer -> overload=True "
                  f"fidelity={last.fidelity} success={last.success}")
            break
        print(f"  第{count}次 transfer -> fidelity={last.fidelity} "
              f"success={last.success}")
    else:
        print(f"  共 {count} 次传输，未触发过载（fidelity={last.fidelity}）")
    print(f"  最终警告={last.warnings if last else []}")
    print(ch.close_channel(r4.channel_id, reason="测试完成"))

    # 汇总查询
    banner("查询验证")
    print(f"当前相态：{ch.get_current_phase()}")
    print(f"开放通道数：{len(ch.get_open_channels())}")
    print(f"历史记录条数：{len(ch.get_channel_history())}")
    print("最近 5 条历史：")
    for h in ch.get_channel_history(5):
        op = h.get("op")
        d = h.get("detail", {})
        if isinstance(d, dict):
            print(f"  - {op}: {d.get('from_phase')}→{d.get('to_phase')} "
                  f"fidelity={d.get('fidelity')} overload={d.get('overload')}")
        else:
            print(f"  - {op}")
    print("\n全部测试通过 [OK]")
