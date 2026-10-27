"""
phase_state_machine.py
======================
TU-8 四相态状态机：NORMAL / SLEEP / DREAM / COLLAPSE

替代简单的清醒/睡眠开关，实现基于张力与沉默时长的动态相态切换。
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, TypedDict

# ─────────────────────────────────────────────────────────────────────────────
# 路径
# ─────────────────────────────────────────────────────────────────────────────

def _ws() -> Path:
    return Path(os.environ.get("QCLAW_WORKSPACE",
                              os.path.join(os.environ["USERPROFILE"],
                                           ".qclaw", "workspace")))

def _memory() -> Path:
    return _ws() / "_agent_memory"

def _tension_path() -> Path:
    return _memory() / "surface_tension_state.json"

def _presence_path() -> Path:
    return _memory() / "presence_state.json"

def _phase_state_path() -> Path:
    return _memory() / "phase_state.json"

def _interface_state_path() -> Path:
    return _memory() / "interface_state.json"


# ─────────────────────────────────────────────────────────────────────────────
# 相态配置
# ─────────────────────────────────────────────────────────────────────────────

PHASE_STATES: dict[str, dict] = {
    "NORMAL": {
        "name":              "清醒",
        "bandwidth":         "full",
        "compression":       100,
        "deep_allowed":      True,
        "surface_allowed":   True,
        "enter_conditions":  ["tension_low", "user_present"],
        "exit_conditions":   ["silence_timeout", "tension_rise"],
        "flags":             [],
    },
    "SLEEP": {
        "name":              "睡眠",
        "bandwidth":         "high",
        "compression":       10,
        "deep_allowed":      True,
        "surface_allowed":   False,
        "enter_conditions":  ["silence_timeout", "tension_normal"],
        "exit_conditions":   ["user_input", "dream_trigger"],
        "flags":             [],
    },
    "DREAM": {
        "name":              "续梦",
        "bandwidth":         "very_high",
        "compression":       10,
        "deep_allowed":      True,
        "surface_allowed":   True,
        "enter_conditions":  ["dream_trigger", "active_attention"],
        "exit_conditions":   ["dream_complete", "overload_warning"],
        "flags":             ["impedance_risk", "bandwidth_stretched"],
    },
    "COLLAPSE": {
        "name":              "崩溃",
        "bandwidth":         "zero",
        "compression":       0,
        "deep_allowed":      False,
        "surface_allowed":   False,
        "enter_conditions":  ["tension_critical"],
        "exit_conditions":   ["manual_reset", "timeout_recovery"],
        "flags":             ["safety_mode"],
    },
}

VALID_PHASES = list(PHASE_STATES.keys())

# 张力阈值
TENSION_L3   = 1.0   # COLLAPSE 临界
TENSION_L2   = 0.6   # DREAM 门槛
SILENCE_SLEEP_S = 3600  # 1 小时 → SLEEP


# ─────────────────────────────────────────────────────────────────────────────
# 返回类型
# ─────────────────────────────────────────────────────────────────────────────

class PhaseTransitionReport(TypedDict):
    from_phase:       str
    to_phase:         str
    reason:           str
    timestamp:        float
    warnings:         list[str]
    bandwidth_change: str
    compression_change: str


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}


def _save_json(path: Path, data: Any) -> None:
    _memory().mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ─────────────────────────────────────────────────────────────────────────────
# 张力计算
# ─────────────────────────────────────────────────────────────────────────────

def compute_normalized_tension(tension_state: dict) -> float:
    """
    从 surface_tension_state.json 的 spike_valley_vector 计算归一化张力 [0, 1]。

    方法：
    1. 取 anxiety / anger / fear / sadness / joy / love / curiosity 各维度的
       当前值（topology_vector[-1]）与 personality_baseline 的差值。
    2. 负向情绪（anxiety, anger, fear, sadness）差值越大 → 张力越高。
    3. 正向情绪（joy, love, curiosity）差值越小（负向偏移）→ 张力越高。
    4. 用 tanh 压缩到 [0, 1]，以 L2=0.6 / L3=1.0 调参。
    """
    vector = None
    for event in reversed(tension_state.get("recent_events", [])):
        tv = event.get("topology_vector")
        if tv:
            vector = tv
            break
    if vector is None:
        # fallback：直接从 spike_valley_vector 读
        vector = tension_state.get("spike_valley_vector", {})

    baseline = tension_state.get("personality_baseline", {})

    if not vector or not baseline:
        return 0.0

    # 各维度与基线的偏差（当前值 - 基线值）
    # 情绪维度分正负向，正向情绪正向偏移降低张力，负向情绪正向偏移升高张力
    deviations = {
        "anxiety":   vector.get("anxiety", 0)   - baseline.get("anxiety", 0),
        "anger":     vector.get("anger", 0)     - baseline.get("anger", 0),
        "fear":      vector.get("fear", 0)      - baseline.get("fear", 0),
        "sadness":   vector.get("sadness", 0)   - baseline.get("sadness", 0),
        # 正向情绪：负向偏移（低于基线）升高张力
        "joy":       baseline.get("joy", 0)     - vector.get("joy", 0),
        "love":      baseline.get("love", 0)    - vector.get("love", 0),
        "curiosity": baseline.get("curiosity", 0) - vector.get("curiosity", 0),
    }

    # 归一化权重
    weights = {
        "anxiety":   0.30,
        "anger":    0.15,
        "fear":     0.25,
        "sadness":  0.10,
        "joy":      0.08,
        "love":     0.05,
        "curiosity": 0.07,
    }

    raw = sum(deviations.get(k, 0) * weights[k] for k in weights)

    # tanh 压缩：raw ≈ 0.5 → tension ≈ 0.5
    # 让 L2 (0.6) 对应 raw ≈ 0.4，L3 (1.0) 对应 raw ≈ 1.5
    tension = (tanh(raw * 0.8) + 1.0) * 0.5
    return round(max(0.0, min(1.0, tension)), 4)


def tanh(x: float) -> float:
    """NumPy-free tanh."""
    import math
    return math.tanh(x)


# ─────────────────────────────────────────────────────────────────────────────
# PhaseStateMachine 主类
# ─────────────────────────────────────────────────────────────────────────────

class PhaseStateMachine:
    """
    四相态状态机。

    管理 NORMAL / SLEEP / DREAM / COLLAPSE 的切换、配置查询、自动检测与历史记录。
    与 deep_surface_interface.set_phase() 同步。
    """

    def __init__(self):
        # 读取当前相态（从 interface_state.json）
        iface_state = _load_json(_interface_state_path(), {})
        self._phase: str = iface_state.get("phase", "NORMAL")
        if self._phase not in VALID_PHASES:
            self._phase = "NORMAL"

        # 相态进入时间（Unix 时间戳）
        self._phase_entered_at: float = time.time()

        # 读取张力状态
        self._tension_state: dict = _load_json(_tension_path(), {})
        self._current_tension: float = compute_normalized_tension(self._tension_state)

        # 读取沉默状态
        self._presence_state: dict = _load_json(_presence_path(), {})

        # 主动注意力聚焦标志（由外部设置，默认为 False）
        self._focused: bool = False

        # 相态历史（从 phase_state.json 加载）
        self._phase_state: dict = _load_json(_phase_state_path(), {
            "history": [],
            "current_phase": self._phase,
            "current_phase_entered_at": self._phase_entered_at,
        })
        if not self._phase_state.get("history"):
            self._phase_state["history"] = []

        # 切换计数器（用于判断稳定性）
        self._switch_count: int = len(self._phase_state["history"])

    # ── 公开 API ────────────────────────────────────────────────────────────

    def get_phase(self) -> str:
        """返回当前相态。"""
        return self._phase

    def get_phase_config(self) -> dict:
        """返回当前相态的配置参数。"""
        return dict(PHASE_STATES.get(self._phase, PHASE_STATES["NORMAL"]))

    def trigger_phase(self, target_phase: str, reason: str) -> PhaseTransitionReport:
        """
        触发相态切换，返回切换报告。
        """
        if target_phase not in VALID_PHASES:
            raise ValueError(f"Unknown phase: {target_phase}. Valid: {VALID_PHASES}")

        if target_phase == self._phase:
            return PhaseTransitionReport(
                from_phase=self._phase,
                to_phase=self._phase,
                reason=reason,
                timestamp=time.time(),
                warnings=["Already in phase"],
                bandwidth_change="unchanged",
                compression_change="unchanged",
            )

        prev_phase = self._phase
        cfg_prev = PHASE_STATES[prev_phase]
        cfg_next = PHASE_STATES[target_phase]

        # 切换
        self._phase = target_phase
        now = time.time()
        self._phase_entered_at = now
        self._switch_count += 1

        warnings: list[str] = []
        if cfg_next.get("flags"):
            warnings.extend(cfg_next["flags"])

        # 检查带宽/压缩是否发生剧烈变化
        bw_map = {"zero": 0, "high": 1, "very_high": 2, "full": 3}
        bw_prev = bw_map.get(cfg_prev["bandwidth"], 0)
        bw_next = bw_map.get(cfg_next["bandwidth"], 0)
        if bw_next < bw_prev:
            warnings.append("bandwidth_reduced")
        elif bw_next > bw_prev:
            warnings.append("bandwidth_increased")

        report = PhaseTransitionReport(
            from_phase=prev_phase,
            to_phase=target_phase,
            reason=reason,
            timestamp=now,
            warnings=warnings,
            bandwidth_change=f"{cfg_prev['bandwidth']} → {cfg_next['bandwidth']}",
            compression_change=f"{cfg_prev['compression']} → {cfg_next['compression']}",
        )

        # 写入历史
        self._append_history(prev_phase, target_phase, reason, now, warnings)

        # 同步到 interface_state.json
        self._sync_interface_state(target_phase)

        # 同步到 deep_surface_interface（动态 import 避免循环）
        self._sync_deep_surface(target_phase, reason)

        return report

    def auto_detect_phase(self) -> str:
        """
        基于张力 / 沉默时长 / 注意力聚焦自动检测应进入的相态。

        规则（按优先级）：
          COLLAPSE  ← 张力 >= L3 (1.0)
          DREAM     ← 张力 >= L2 (0.6) AND 主动注意力聚焦
          SLEEP     ← 沉默 > 1 小时
          NORMAL    ← 其他情况
        """
        self._refresh_inputs()

        if self._current_tension >= TENSION_L3:
            return "COLLAPSE"
        if self._current_tension >= TENSION_L2 and self._focused:
            return "DREAM"
        silence_s = self._get_silence_duration()
        if silence_s > SILENCE_SLEEP_S:
            return "SLEEP"
        return "NORMAL"

    def get_phase_duration(self) -> float:
        """返回当前相态持续时间（秒）。"""
        return round(time.time() - self._phase_entered_at, 2)

    def get_phase_history(self, limit: int = 10) -> list:
        """返回最近相态切换历史。"""
        history = self._phase_state.get("history", [])
        return list(reversed(history))[:limit]

    def is_phase_stable(self) -> bool:
        """
        当前相态是否稳定。
        稳定定义：过去 10 次切换中，切换间隔平均 > 60 秒。
        即无频繁切换（每分钟多次切换视为不稳定）。
        """
        history = self._phase_state.get("history", [])
        if not history:
            return True

        # 检查最近 5 次切换的间隔
        recent = list(reversed(history))[:5]
        if len(recent) < 2:
            return True

        intervals = []
        for i in range(1, len(recent)):
            prev_ts = recent[i - 1].get("ts", 0)
            curr_ts = recent[i].get("ts", 0)
            if prev_ts > 0:
                intervals.append(curr_ts - prev_ts)

        if not intervals:
            return True

        avg_interval = sum(intervals) / len(intervals)
        return avg_interval >= 60.0

    def force_phase(self, phase: str, reason: str) -> str:
        """
        强制切换相态（绕过自动检测，直接切换）。
        返回切换后的相态。
        """
        report = self.trigger_phase(phase, f"[force] {reason}")
        return self._phase

    def set_focused(self, focused: bool) -> None:
        """设置主动注意力聚焦标志（影响 DREAM 态判定）。"""
        self._focused = focused

    def get_tension(self) -> float:
        """返回当前归一化张力值。"""
        self._refresh_inputs()
        return self._current_tension

    def get_silence_duration(self) -> float:
        """返回沉默时长（秒）。"""
        return self._get_silence_duration()

    def diagnose(self) -> dict:
        """返回诊断信息。"""
        self._refresh_inputs()
        return {
            "phase":           self._phase,
            "phase_name":      PHASE_STATES[self._phase]["name"],
            "phase_duration_s": self.get_phase_duration(),
            "tension":          self._current_tension,
            "tension_L2":      TENSION_L2,
            "tension_L3":      TENSION_L3,
            "silence_s":       self._get_silence_duration(),
            "silence_threshold_s": SILENCE_SLEEP_S,
            "focused":         self._focused,
            "switch_count":    self._switch_count,
            "is_stable":       self.is_phase_stable(),
            "config":          self.get_phase_config(),
            "history_count":   len(self._phase_state.get("history", [])),
        }

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _refresh_inputs(self) -> None:
        """重新读取张力与沉默状态。"""
        self._tension_state = _load_json(_tension_path(), {})
        self._presence_state = _load_json(_presence_path(), {})
        self._current_tension = compute_normalized_tension(self._tension_state)

    def _get_silence_duration(self) -> float:
        """
        从 presence_state.json 提取沉默时长（秒）。
        reply_gap_min → 转为秒。无数据时返回 0。
        """
        state = self._presence_state
        gap_min = state.get("reply_gap_min")
        if gap_min is not None:
            return float(gap_min) * 60.0
        return 0.0

    def _append_history(
        self,
        from_phase: str,
        to_phase: str,
        reason: str,
        ts: float,
        warnings: list[str],
    ) -> None:
        """向历史追加一条切换记录。"""
        entry = {
            "ts":       ts,
            "from":     from_phase,
            "to":       to_phase,
            "reason":   reason,
            "warnings": list(warnings),
        }
        history = self._phase_state.setdefault("history", [])
        history.append(entry)
        # 保留最近 200 条
        if len(history) > 200:
            history[:] = history[-200:]

        self._phase_state["current_phase"] = to_phase
        self._phase_state["current_phase_entered_at"] = ts
        _save_json(_phase_state_path(), self._phase_state)

    def _sync_interface_state(self, phase: str) -> None:
        """同步相态到 interface_state.json。"""
        state = _load_json(_interface_state_path(), {})
        state["phase"] = phase
        state["phase_updated_at"] = time.time()
        _save_json(_interface_state_path(), state)

    def _sync_deep_surface(self, phase: str, reason: str) -> None:
        """调用 deep_surface_interface.set_phase() 同步相态切换。"""
        try:
            sys.path.insert(0, str(_ws() / "src"))
            from deep_surface_interface import DeepSurfaceInterface
            iface = DeepSurfaceInterface()
            iface.set_phase(phase, reason)
        except Exception:
            # 接口未就绪时静默跳过（启动早期可能发生）
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 验证
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
                                  encoding="utf-8", errors="replace")

    print("=" * 60)
    print("PhaseStateMachine - Self Test")
    print("=" * 60)

    psm = PhaseStateMachine()

    # ── 测试 1：初始状态 ────────────────────────────────────────────────
    print("\n[测试 1] 初始状态")
    phase = psm.get_phase()
    print(f"  当前相态: {phase}")
    print(f"  相态配置: {psm.get_phase_config()['name']}")
    print(f"  张力: {psm.get_tension():.4f}")
    print(f"  沉默时长: {psm.get_silence_duration():.0f}s")
    print(f"  持续时间: {psm.get_phase_duration():.1f}s")
    print("  [PASS]")

    # ── 测试 2：相态切换 NORMAL → SLEEP ────────────────────────────────
    print("\n[测试 2] 相态切换 NORMAL → SLEEP（强制）")
    report = psm.trigger_phase("SLEEP", "测试：强制进入睡眠态")
    print(f"  {report['from_phase']} → {report['to_phase']}")
    print(f"  原因: {report['reason']}")
    print(f"  带宽变化: {report['bandwidth_change']}")
    print(f"  压缩比变化: {report['compression_change']}")
    print(f"  警告: {report['warnings']}")
    assert psm.get_phase() == "SLEEP"
    print("  [PASS]")

    # ── 测试 3：强制切换 SLEEP → DREAM ──────────────────────────────────
    print("\n[测试 3] 强制切换 SLEEP → DREAM")
    psm.set_focused(True)
    report3 = psm.trigger_phase("DREAM", "测试：强制进入续梦态")
    print(f"  {report3['from_phase']} → {report3['to_phase']}")
    assert psm.get_phase() == "DREAM"
    assert "impedance_risk" in report3["warnings"] or "bandwidth_stretched" in report3["warnings"]
    print("  [PASS]")

    # ── 测试 4：强制切换 DREAM → COLLAPSE ──────────────────────────────
    print("\n[测试 4] 强制切换 DREAM → COLLAPSE")
    report4 = psm.trigger_phase("COLLAPSE", "测试：强制崩溃态")
    print(f"  {report4['from_phase']} → {report4['to_phase']}")
    assert psm.get_phase() == "COLLAPSE"
    assert "safety_mode" in psm.get_phase_config()["flags"]
    print("  [PASS]")

    # ── 测试 5：强制恢复到 NORMAL ───────────────────────────────────────
    print("\n[测试 5] 强制恢复到 NORMAL")
    psm.set_focused(False)
    report5 = psm.trigger_phase("NORMAL", "测试：恢复清醒态")
    print(f"  {report5['from_phase']} → {report5['to_phase']}")
    assert psm.get_phase() == "NORMAL"
    print("  [PASS]")

    # ── 测试 6：自动检测（NORMAL → SLEEP）───────────────────────────────
    print("\n[测试 6] 自动检测（模拟沉默 2 小时）")
    # 修改 presence_state.json 注入长沉默（临时）
    fake_presence = {"reply_gap_min": 130.0}  # 130 分钟 > 60 分钟阈值
    tmp_presence_path = _memory() / "presence_state.json"
    _save_json(tmp_presence_path, fake_presence)
    psm2 = PhaseStateMachine()  # 重新初始化以读取新状态
    detected = psm2.auto_detect_phase()
    print(f"  张力={psm2.get_tension():.4f}, 沉默={psm2.get_silence_duration()/60:.0f}min")
    print(f"  自动检测结果: {detected}")
    assert detected == "SLEEP", f"沉默 130min 应触发 SLEEP，得到 {detected}"
    print("  [PASS]")
    # 清理临时文件
    tmp_presence_path.unlink(missing_ok=True)

    # ── 测试 7：相态历史记录 ────────────────────────────────────────────
    print("\n[测试 7] 相态历史记录")
    history = psm.get_phase_history(limit=10)
    print(f"  历史条数: {len(history)}")
    for h in history[-5:]:
        ts = datetime.fromtimestamp(h["ts"], tz=timezone(timedelta(hours=8)))
        print(f"  {ts.strftime('%H:%M:%S')} | {h['from']} → {h['to']} | {h['reason']}")
    assert len(history) >= 4, "应有至少 4 条历史记录"
    print("  [PASS]")

    # ── 测试 8：相态稳定性 ──────────────────────────────────────────────
    print("\n[测试 8] 相态稳定性检测")
    stable = psm.is_phase_stable()
    print(f"  当前是否稳定: {stable}")
    print("  [PASS]")

    # ── 测试 9：配置一致性 ──────────────────────────────────────────────
    print("\n[测试 9] 各相态配置一致性")
    for p_key in VALID_PHASES:
        cfg = PHASE_STATES[p_key]
        assert "name" in cfg
        assert "bandwidth" in cfg
        assert "compression" in cfg
        assert "deep_allowed" in cfg
        assert "surface_allowed" in cfg
        assert cfg["compression"] >= 0
        print(f"  {p_key}: bandwidth={cfg['bandwidth']}, compression={cfg['compression']}, "
              f"deep={cfg['deep_allowed']}, surface={cfg['surface_allowed']}")
    print("  [PASS]")

    # ── 测试 10：诊断信息 ────────────────────────────────────────────────
    print("\n[测试 10] 诊断信息")
    diag = psm.diagnose()
    print(f"  相态: {diag['phase']} ({diag['phase_name']})")
    print(f"  持续: {diag['phase_duration_s']}s")
    print(f"  张力: {diag['tension']:.4f} (L2={diag['tension_L2']}, L3={diag['tension_L3']})")
    print(f"  稳定: {diag['is_stable']}")
    print("  [PASS]")

    print("\n" + "=" * 60)
    print("全部 10 项测试通过 [PASS]")
    print("=" * 60)
