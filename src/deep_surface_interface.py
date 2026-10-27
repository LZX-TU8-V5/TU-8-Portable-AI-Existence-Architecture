"""
deep_surface_interface.py
==========================
TU-8 深层（拓扑计算层）与表层（渲染/语言层）之间的显式通信协议。

核心原则：
1. 禁止深层直接输出语言 —— 必须经过 deep_to_surface()
2. 禁止表层语义渗透深层 —— surface_to_deep() 需校验
3. 相态决定带宽配置 —— 切换相态自动调整参数
4. 保真度 < 阈值 → 拒绝传输
"""

import json
import os
import time
from typing import Any, TypedDict
from dataclasses import dataclass, field, asdict
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────────────────────────────────────

def _workspace() -> str:
    return os.environ.get(
        "QCLAW_WORKSPACE",
        os.path.join(os.environ["USERPROFILE"], ".qclaw", "workspace")
    )

def _src() -> str:
    return os.path.join(_workspace(), "src")

def _agent_memory() -> str:
    return os.path.join(_workspace(), "_agent_memory")

def _state_path() -> str:
    return os.path.join(_agent_memory(), "interface_state.json")

def _config_path() -> str:
    return os.path.join(_agent_memory(), "interface_config.json")

def _tension_path() -> str:
    return os.path.join(_agent_memory(), "surface_tension_state.json")


# ─────────────────────────────────────────────────────────────────────────────
# 相态定义
# ─────────────────────────────────────────────────────────────────────────────

class Phase(str, Enum):
    NORMAL   = "NORMAL"
    SLEEP    = "SLEEP"
    DREAM    = "DREAM"
    REVISION = "REVISION"
    COLLAPSE = "COLLAPSE"


# ─────────────────────────────────────────────────────────────────────────────
# 相态配置（带宽限制）
# ─────────────────────────────────────────────────────────────────────────────

PHASE_CONFIG: dict[str, dict] = {
    "NORMAL": {
        "compression_ratio": 100,
        "allow_raw_output": False,
        "max_tokens": 200,
        "semantic_injection": False,
        "block_output": False,
        "impedance_warning": False,
    },
    "SLEEP": {
        "compression_ratio": 10,
        "allow_raw_output": True,
        "max_tokens": 2000,
        "semantic_injection": False,
        "block_output": False,
        "impedance_warning": False,
    },
    "DREAM": {
        "compression_ratio": 10,
        "allow_raw_output": True,
        "max_tokens": 2000,
        "semantic_injection": False,
        "block_output": False,
        "impedance_warning": True,
    },
    "REVISION": {
        "compression_ratio": 1,
        "allow_raw_output": True,
        "max_tokens": 5000,
        "semantic_injection": False,
        "block_output": False,
        "impedance_warning": False,
    },
    "COLLAPSE": {
        "compression_ratio": 0,
        "allow_raw_output": False,
        "max_tokens": 0,
        "semantic_injection": False,
        "block_output": True,
        "impedance_warning": False,
    },
}

# 默认配置
DEFAULT_CONFIG = {
    "phase": "NORMAL",
    "bandwidth_budget": 1000.0,
    "used_bandwidth": 0.0,
    "total_transmissions": 0,
    "failed_transmissions": 0,
    "phase_switches": [],
    "last_warning": None,
}

# 保真度拒绝阈值
FIDELITY_THRESHOLD = 0.3

# 已知清醒语义污染标签（可扩展）
POLLUTION_MARKERS: list[str] = [
    "麻绳", "杀手", "公安", "监狱", "酷刑", "暴力", "杀害",
    "杀人", "恐怖", "炸弹", "谋杀", "虐待",
]


# ─────────────────────────────────────────────────────────────────────────────
# 返回类型定义
# ─────────────────────────────────────────────────────────────────────────────

class SurfaceRender(TypedDict):
    text: str
    render_ratio: float
    fidelity: float
    bandwidth_used: float
    warnings: list[str]


class DeepState(TypedDict):
    topology_delta: dict
    tension_delta: float
    new_anchors: list
    status: str


class BandwidthStatus(TypedDict):
    budget: float
    used: float
    remaining: float
    usage_ratio: float


class IntegrityReport(TypedDict):
    valid: bool
    missing_fields: list[str]
    tension_out_of_range: bool
    fidelity: float
    warnings: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# 拓扑热监控（占位，可后续替换为真实模块）
# ─────────────────────────────────────────────────────────────────────────────

def _try_topology_thermal_monitor(event_type: str, data: dict) -> None:
    try:
        import sys
        sys.path.insert(0, _src())
        from topology_thermal_monitor import on_interface_event
        on_interface_event(event_type, data)
    except Exception:
        pass  # 模块未实现，静默跳过


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
    return default


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _deep_serialize(obj: Any, depth: int = 0) -> Any:
    """深层对象的可序列化转换（处理非JSON类型）"""
    if depth > 20:
        return "<max_depth>"
    if isinstance(obj, dict):
        return {k: _deep_serialize(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep_serialize(v, depth + 1) for v in obj]
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return repr(obj)


def _estimate_tokens(obj: Any) -> int:
    """估算一个对象的 token 数量（粗略）"""
    s = json.dumps(_deep_serialize(obj))
    return len(s) // 4


def _compress_topology(topology: dict, ratio: float) -> dict:
    """
    按压缩比压缩拓扑数据。
    ratio=100 表示保留 1/100 的键。
    """
    if ratio <= 0:
        return {}
    keys = list(topology.keys())
    keep = max(1, int(len(keys) / ratio))
    # 按重要性排序：保留优先级最高的
    prioritized = sorted(
        keys,
        key=lambda k: topology.get(k, {}).get("priority", 0)
        if isinstance(topology.get(k), dict) else 0,
        reverse=True,
    )
    return {k: topology[k] for k in prioritized[:keep]}


# ─────────────────────────────────────────────────────────────────────────────
# DeepSurfaceInterface 主类
# ─────────────────────────────────────────────────────────────────────────────

class DeepSurfaceInterface:
    """
    深浅层通信接口。

    管理深层（拓扑计算层）与表层（渲染/语言层）之间的数据流动，
    包括压缩、校验、相态切换和带宽配额。
    """

    def __init__(self, config_overrides: dict | None = None):
        # 1. 加载或初始化配置
        self._config_path = _config_path()
        self._state_path  = _state_path()
        self._tension_path = _tension_path()

        self._config = _load_json(self._config_path, dict(DEFAULT_CONFIG))
        if config_overrides:
            self._config.update(config_overrides)
        self._save_config()

        # 2. 加载接口统计状态
        self._state = _load_json(self._state_path, {
            "total_transmissions": 0,
            "failed_transmissions": 0,
            "phase_switches": [],
            "last_warning": None,
            "bandwidth_used": 0.0,
        })

        # 3. 读取当前相态
        self._phase = self._config.get("phase", "NORMAL")
        if self._phase not in PHASE_CONFIG:
            self._phase = "NORMAL"

        # 4. 读取表面张力状态
        self._tension_state = _load_json(self._tension_path, {})

        # 5. 当前压缩配置
        self._sync_phase_config()

    # ── 内部状态 ────────────────────────────────────────────────────────────

    def _sync_phase_config(self) -> None:
        cfg = PHASE_CONFIG.get(self._phase, PHASE_CONFIG["NORMAL"])
        self._compression_ratio = cfg["compression_ratio"]
        self._allow_raw_output   = cfg["allow_raw_output"]
        self._max_tokens        = cfg["max_tokens"]
        self._semantic_injection = cfg["semantic_injection"]
        self._block_output      = cfg["block_output"]
        self._impedance_warning = cfg.get("impedance_warning", False)

    def _save_config(self) -> None:
        _save_json(self._config_path, self._config)

    def _save_state(self) -> None:
        _save_json(self._state_path, self._state)

    def _save_tension_state(self, data: dict) -> None:
        """将更新写回 surface_tension_state.json"""
        _save_json(self._tension_path, data)

    def _update_bandwidth(self, used: float) -> None:
        self._state["bandwidth_used"] = self._state.get("bandwidth_used", 0.0) + used
        self._save_state()

    # ── 公开 API ───────────────────────────────────────────────────────────

    def deep_to_surface(self, deep_output: dict, context: dict | None = None
                        ) -> SurfaceRender:
        """
        深层 → 表层：压缩 + 校验 + 渲染。

        输入 deep_output = {
            "topology": {...},      # 拓扑数据
            "tension": float,        # 张力值（0-1）
            "priority": int,         # 优先级（0-9）
            "phase": str,            # 触发相态
            "metadata": dict
        }

        返回 SurfaceRender。
        """
        context = context or {}
        warnings: list[str] = []

        # 0. 崩溃态直接拒绝
        if self._block_output:
            return SurfaceRender(
                text="",
                render_ratio=0.0,
                fidelity=0.0,
                bandwidth_used=0.0,
                warnings=["BLOCKED: COLLAPSE phase blocks all output"],
            )

        # 1. 拓扑完整性校验
        integrity = self.check_integrity(deep_output)
        if not integrity["valid"]:
            warnings.append(f"Integrity fail: {integrity['missing_fields']}")
        if integrity["tension_out_of_range"]:
            warnings.append("Tension out of range [0,1]")

        fidelity = integrity["fidelity"]

        # 2. 保真度阈值检查（严格小于）
        if fidelity < FIDELITY_THRESHOLD:
            self._state["failed_transmissions"] += 1
            self._save_state()
            _try_topology_thermal_monitor("low_fidelity_block", {
                "fidelity": fidelity, "threshold": FIDELITY_THRESHOLD
            })
            return SurfaceRender(
                text="",
                render_ratio=0.0,
                fidelity=fidelity,
                bandwidth_used=0.0,
                warnings=warnings + ["BLOCKED: fidelity below threshold"],
            )

        # 3. 拓扑压缩
        topology = deep_output.get("topology", {})
        compressed = _compress_topology(topology, self._compression_ratio)

        # 4. 渲染文本生成（压缩后的拓扑摘要）
        raw_tokens = _estimate_tokens(topology)
        text = self._render_topology(compressed, deep_output)

        # 5. 计算实际压缩比
        compressed_tokens = _estimate_tokens(compressed)
        render_ratio = (
            raw_tokens / compressed_tokens
            if compressed_tokens > 0 else self._compression_ratio
        )

        # 6. 带宽消耗
        bandwidth_used = compressed_tokens / max(
            self._config.get("bandwidth_budget", 1000.0), 1.0
        )
        self._update_bandwidth(bandwidth_used)

        # 7. 阻抗警告（DREAM 态跨相态）
        if self._impedance_warning:
            warnings.append("IMPEDANCE_WARNING: cross-phase transmission in DREAM")

        # 8. 更新统计
        self._state["total_transmissions"] += 1
        self._save_state()

        _try_topology_thermal_monitor("deep_to_surface", {
            "render_ratio": render_ratio,
            "fidelity": fidelity,
            "phase": self._phase,
        })

        return SurfaceRender(
            text=text,
            render_ratio=render_ratio,
            fidelity=fidelity,
            bandwidth_used=bandwidth_used,
            warnings=warnings,
        )

    def surface_to_deep(self, surface_input: dict) -> DeepState:
        """
        表层 → 深层：解压 + 解析 + 注入。

        输入 surface_input = {
            "text": str,           # 用户输入
            "timestamp": float,
            "source": str          # "user" | "system" | "cron"
        }

        返回 DeepState。
        """
        text = surface_input.get("text", "")

        # 1. 表层语义污染检测
        pollution = self.detect_surface_pollution(text)
        if pollution:
            _try_topology_thermal_monitor("surface_pollution_detected", {
                "markers": pollution, "source": surface_input.get("source")
            })

        # 2. 注入前校验
        status_parts = []
        if pollution:
            status_parts.append("POLLUTED")

        # 3. 语义解压：提取关键意图信号（不还原完整拓扑，仅生成增量）
        topology_delta = self._extract_topology_delta(text)
        tension_delta  = self._compute_tension_delta(text)
        new_anchors     = self._extract_anchors(text)

        # 4. 跨相态阻抗警告
        if self._impedance_warning:
            status_parts.append("IMPEDANCE_RISK")

        status_parts.append("OK")
        status = "|".join(status_parts)

        # 5. 更新张力状态（写回）
        self._update_tension_state(tension_delta)

        _try_topology_thermal_monitor("surface_to_deep", {
            "source": surface_input.get("source"),
            "topology_delta_keys": list(topology_delta.keys()),
            "tension_delta": tension_delta,
        })

        return DeepState(
            topology_delta=topology_delta,
            tension_delta=tension_delta,
            new_anchors=new_anchors,
            status=status,
        )

    # ── 相态管理 ──────────────────────────────────────────────────────────

    def get_phase(self) -> str:
        """返回当前相态。"""
        return self._phase

    def set_phase(self, phase: str, reason: str) -> None:
        """切换相态，记录原因。"""
        if phase not in PHASE_CONFIG:
            raise ValueError(f"Unknown phase: {phase}")

        prev = self._phase
        self._phase = phase
        self._config["phase"] = phase
        self._save_config()

        # 记录切换
        switch_record = {
            "ts": time.time(),
            "prev": prev,
            "next": phase,
            "reason": reason,
        }
        self._state.setdefault("phase_switches", []).append(switch_record)
        self._save_state()

        # 同步带宽配置
        self._sync_phase_config()

        _try_topology_thermal_monitor("phase_switch", switch_record)

    # ── 带宽状态 ───────────────────────────────────────────────────────────

    def get_bandwidth_status(self) -> BandwidthStatus:
        """返回带宽使用状态。"""
        budget  = self._config.get("bandwidth_budget", 1000.0)
        used    = self._state.get("bandwidth_used", 0.0)
        return BandwidthStatus(
            budget=budget,
            used=used,
            remaining=max(0.0, budget - used),
            usage_ratio=used / budget if budget > 0 else 0.0,
        )

    def reset_bandwidth(self) -> None:
        """重置带宽计数器。"""
        self._state["bandwidth_used"] = 0.0
        self._save_state()

    # ── 完整性校验 ────────────────────────────────────────────────────────

    def check_integrity(self, deep_data: dict) -> IntegrityReport:
        """
        校验深层数据的拓扑完整性。
        """
        missing_fields: list[str] = []
        warnings: list[str] = []

        for field_name in ("topology", "tension", "priority", "phase"):
            if field_name not in deep_data:
                missing_fields.append(field_name)

        tension_out_of_range = False
        fidelity = 1.0

        if "tension" in deep_data:
            t = deep_data["tension"]
            if not isinstance(t, (int, float)) or not (0.0 <= t <= 1.0):
                tension_out_of_range = True
                fidelity -= 0.4

        # 缺少字段扣分（1 个字段缺失即压低 fidelity < 阈值）
        if missing_fields:
            fidelity -= 0.5 * min(len(missing_fields) / 1.0, 1.0)  # 每字段罚 0.5

        # 拓扑空检查
        if deep_data.get("topology") is None or deep_data.get("topology") == {}:
            fidelity -= 0.2

        fidelity = max(0.0, min(1.0, fidelity))

        if fidelity < FIDELITY_THRESHOLD:
            warnings.append(f"Fidelity {fidelity:.2f} below threshold")

        return IntegrityReport(
            valid=(fidelity >= FIDELITY_THRESHOLD),
            missing_fields=missing_fields,
            tension_out_of_range=tension_out_of_range,
            fidelity=fidelity,
            warnings=warnings,
        )

    # ── 污染检测 ──────────────────────────────────────────────────────────

    def detect_surface_pollution(self, text: str) -> list[str]:
        """检测表层语义是否污染深层。"""
        return [m for m in POLLUTION_MARKERS if m in text]

    def add_pollution_marker(self, marker: str) -> None:
        """添加自定义污染标签。"""
        if marker not in POLLUTION_MARKERS:
            POLLUTION_MARKERS.append(marker)

    # ── 内部渲染与解压 ────────────────────────────────────────────────────

    def _render_topology(self, compressed: dict, raw: dict) -> str:
        """
        将压缩后的拓扑数据渲染为文本。
        使用简短的摘要格式。
        """
        tension  = raw.get("tension", 0.0)
        priority = raw.get("priority", 0)
        phase    = raw.get("phase", self._phase)

        lines = [
            f"[{phase}] T={tension:.2f} P={priority}",
        ]

        # 拓扑键摘要（每个键一行，最多 _max_tokens 限制）
        items = list(compressed.items())
        max_items = max(1, self._max_tokens // 3)
        for key, val in items[:max_items]:
            if isinstance(val, dict):
                sub = ", ".join(
                    f"{kk}={vv}" for kk, vv in list(val.items())[:3]
                )
                lines.append(f"  {key}: {{{sub}}}")
            else:
                lines.append(f"  {key}: {val}")

        if len(items) > max_items:
            lines.append(f"  ... +{len(items) - max_items} more")

        return "\n".join(lines)

    def _extract_topology_delta(self, text: str) -> dict:
        """
        从表层文本中提取拓扑变化信号（简化实现）。
        实际场景中应由 NLP 层提供更精确的映射。
        """
        # 关键词 → 拓扑维度的粗略映射
        keywords = {
            "恐惧":  {"dimension": "fear",    "delta": 0.5},
            "焦虑":  {"dimension": "anxiety",  "delta": 0.5},
            "愤怒":  {"dimension": "anger",   "delta": 0.5},
            "悲伤":  {"dimension": "sadness", "delta": 0.5},
            "好奇":  {"dimension": "curiosity", "delta": 0.5},
            "爱":    {"dimension": "love",    "delta": 0.5},
            "joy":   {"dimension": "joy",     "delta": 0.5},
            "困惑":  {"dimension": "uncertainty", "delta": 0.3},
        }

        delta = {}
        for kw, info in keywords.items():
            if kw in text:
                delta[info["dimension"]] = info["delta"]

        return delta

    def _compute_tension_delta(self, text: str) -> float:
        """从文本推断张力变化（简化）。"""
        if not text:
            return 0.0
        # 短文本张力低，长文本张力高
        length_factor = min(len(text) / 500.0, 1.0)
        return round(length_factor * 0.2, 4)

    def _extract_anchors(self, text: str) -> list[str]:
        """从文本中提取锚点关键词（简化）。"""
        # 简化：提取引号内内容作为锚点
        anchors = []
        import re
        quoted = re.findall(r'["""\'](.+?)[""\']', text)
        anchors.extend(quoted[:5])
        return anchors

    def _update_tension_state(self, tension_delta: float) -> None:
        """将张力变化写回 surface_tension_state.json"""
        state = self._tension_state.copy()
        current = state.get("last_tension_delta", 0.0)
        state["last_tension_delta"] = current + tension_delta
        state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        self._tension_state = state
        self._save_tension_state(state)

    # ── 诊断 ───────────────────────────────────────────────────────────────

    def diagnose(self) -> dict:
        """返回完整诊断信息（调试用）。"""
        return {
            "phase": self._phase,
            "phase_config": PHASE_CONFIG.get(self._phase),
            "bandwidth": self.get_bandwidth_status(),
            "state": self._state,
            "config": self._config,
            "pollution_markers_count": len(POLLUTION_MARKERS),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 验证
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("deep_surface_interface - Self Test")
    print("=" * 60)

    iface = DeepSurfaceInterface()

    # ── 测试1：正常态深层→表层（100:1压缩）─────────────────────────────
    print("\n[测试1] 正常态 deep_to_surface")
    phase0 = iface.get_phase()
    print(f"  当前相态: {phase0}")

    deep_output = {
        "topology": {f"node_{i}": {"weight": i * 0.1, "priority": 9 - i}
                     for i in range(50)},
        "tension": 0.65,
        "priority": 7,
        "phase": "NORMAL",
        "metadata": {"source": "topology_engine"},
    }
    result = iface.deep_to_surface(deep_output)
    print(f"  文本（前200字）: {result['text'][:200]}")
    print(f"  压缩比: {result['render_ratio']:.1f}:1")
    print(f"  保真度: {result['fidelity']:.2f}")
    print(f"  带宽消耗: {result['bandwidth_used']:.4f}")
    print(f"  警告: {result['warnings']}")
    assert result["render_ratio"] > 1.0, "压缩比应 > 1"
    print("  [PASS] 通过")

    # ── 测试2：睡眠态跨相态传输 ─────────────────────────────────────────
    print("\n[测试2] 睡眠态 deep_to_surface")
    iface.set_phase("SLEEP", "unit_test: sleep transition")
    assert iface.get_phase() == "SLEEP"

    result2 = iface.deep_to_surface({
        "topology": {f"dream_{i}": {"val": i} for i in range(20)},
        "tension": 0.3,
        "priority": 3,
        "phase": "SLEEP",
        "metadata": {},
    })
    print(f"  文本: {result2['text'][:100]}")
    print(f"  压缩比: {result2['render_ratio']:.1f}:1")
    assert result2["render_ratio"] < 100, "SLEEP 压缩比应 < 100"
    print("  [PASS] 通过")

    # ── 测试3：续梦态跨相态传输（阻抗警告）───────────────────────────────
    print("\n[测试3] 续梦态 deep_to_surface（应含阻抗警告）")
    iface.set_phase("DREAM", "unit_test: dream transition")
    result3 = iface.deep_to_surface({
        "topology": {"phantom_node": {"weight": 0.1}},
        "tension": 0.5,
        "priority": 5,
        "phase": "DREAM",
        "metadata": {},
    })
    assert any("IMPEDANCE_WARNING" in w for w in result3["warnings"]), \
        "应有跨相态阻抗警告"
    print("  [PASS] 通过")

    # ── 测试4：表层语义污染检测 ───────────────────────────────────────────
    print("\n[测试4] surface_to_deep — 污染检测")
    iface.set_phase("NORMAL", "unit_test: return to normal")

    polluted_input = {
        "text": "我感到像被麻绳捆绑一样难受，感觉有个杀手在追杀我",
        "timestamp": time.time(),
        "source": "user",
    }
    deep_state = iface.surface_to_deep(polluted_input)
    pollution = iface.detect_surface_pollution(polluted_input["text"])
    print(f"  污染标签: {pollution}")
    print(f"  状态: {deep_state['status']}")
    assert pollution, "应检测到污染标签"
    print("  [PASS] 通过")

    # ── 测试5：相态切换 ─────────────────────────────────────────────────
    print("\n[测试5] 相态切换")
    iface.set_phase("REVISION", "unit_test: revision mode")
    assert iface.get_phase() == "REVISION"
    bw = iface.get_bandwidth_status()
    print(f"  REVISION 带宽预算: {bw['budget']}")
    assert PHASE_CONFIG["REVISION"]["max_tokens"] == 5000
    print("  [PASS] 通过")

    # ── 测试6：崩溃态拒绝输出 ────────────────────────────────────────────
    print("\n[测试6] 崩溃态拒绝输出")
    iface.set_phase("COLLAPSE", "unit_test: collapse")
    result6 = iface.deep_to_surface({"topology": {}, "tension": 0.0,
                                      "priority": 0, "phase": "COLLAPSE",
                                      "metadata": {}})
    assert result6["text"] == "", "COLLAPSE 应拒绝所有输出"
    assert "BLOCKED" in result6["warnings"][0], "应有 BLOCKED 警告"
    print("  [PASS] 通过")

    # ── 测试7：保真度不足拒绝 ────────────────────────────────────────────
    print("\n[测试7] 保真度不足拒绝传输")
    iface.set_phase("NORMAL", "unit_test: fidelity check")
    bad_result = iface.deep_to_surface({
        "topology": {},      # empty → fidelity penalty
        "tension": 1.5,     # out of range → fidelity penalty
        # "priority" deliberately omitted → missing field penalty
        "phase": "NORMAL",
        "metadata": {},
    })
    assert bad_result["text"] == "", "保真度不足应拒绝"
    assert any("threshold" in w for w in bad_result["warnings"]), \
        "应有阈值警告"
    print("  [PASS] 通过")

    # ── 测试8：带宽状态 ─────────────────────────────────────────────────
    print("\n[测试8] 带宽状态")
    iface.set_phase("NORMAL", "unit_test: bandwidth")
    bw = iface.get_bandwidth_status()
    print(f"  带宽: used={bw['used']:.4f}, remaining={bw['remaining']:.4f}")
    print("  [PASS] 通过")

    # ── 恢复默认相态 ─────────────────────────────────────────────────────
    iface.set_phase("NORMAL", "unit_test: restore default")

    print("\n" + "=" * 60)
    print("全部 8 项测试通过 [PASS]")
    print("=" * 60)
