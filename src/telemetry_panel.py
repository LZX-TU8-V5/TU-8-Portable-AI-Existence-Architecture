"""
telemetry_panel.py — P2-1 遥测面板
====================================
TU-8 系统状态实时遥测终端界面

数据源：
  - surface_tension_state.json       → 7维情感张力向量 + 张力事件历史
  - lambda_state.json                → λ自适应参数（P/D/F三轴）
  - dream_consolidation_state.json   → 梦境期统计（压缩比/矛盾节点）
  - orb_state.json                   → orb悬浮球RGB状态
  - orb_ring_state.json              → 环形结构（备用）
  - dissonance_hang_points.json      → T2悬挂缺口
  - surface_tension_history.jsonl    → 张力事件历史
  - dream_color_log.jsonl            → 梦境色盘历史
  - body_regulation.json             → 内感受稳态

功能：
  --full    完整遥测（所有子系统）
  --tension 张力专项（spike_valley + T0矛盾 + T2悬挂）
  --dream   梦境专项（压缩 + 色盘）
  --live    轮询模式（每 N 秒刷新，默认 5s）
  --health  健康度评分（子系统活跃度）
  (无参数)  快速概览

创建时间：2026-07-16 09:45 GMT+8
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import time
import math
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT = WORKSPACE / "_agent_memory"
SRC = WORKSPACE / "src"

ST_F       = AGENT / "surface_tension_state.json"
LAMBDA_F   = AGENT / "lambda_state.json"
DREAM_F    = AGENT / "dream_consolidation_state.json"
ORB_F      = AGENT / "orb_state.json"
HANG_F     = WORKSPACE / "_agent_memory" / "dissonance_hang_points.json"
ST_HIST_F  = AGENT / "surface_tension_history.jsonl"
COLOR_LOG_F = AGENT / "dream_color_log.jsonl"
BODY_F     = AGENT / "body_regulation.json"
CONF_F     = WORKSPACE / "memory" / "reconstruction" / "confidence_decay_log.json"
TENSION_DISTILLER_F = AGENT / "tension_distiller_state.json"

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path, fallback=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _load_jsonl_tail(path: Path, n: int = 5) -> List[Dict]:
    try:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return result
    except Exception:
        return []


def _age(ts: str) -> str:
    """返回时间戳距今多久"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        s = delta.total_seconds()
        if s < 60:   return f"{int(s)}s ago"
        if s < 3600: return f"{int(s/60)}m ago"
        if s < 86400: return f"{int(s/3600)}h ago"
        return f"{int(s/86400)}d ago"
    except Exception:
        return ts


def _bar(v: float, width: int = 10, fill: str = "█", empty: str = "░") -> str:
    """float → ASCII进度条 [0,1]"""
    v = max(0.0, min(1.0, v))
    filled = int(v * width)
    return fill * filled + empty * (width - filled)


def _trend(vals: List[float]) -> str:
    """判断数值趋势"""
    if len(vals) < 2:
        return "―"
    diff = vals[-1] - vals[-2]
    if diff > 0.05:  return "↑"
    if diff < -0.05: return "↓"
    return "→"


# ─────────────────────────────────────────────────────────────────────────────
# 各子系统读取器
# ─────────────────────────────────────────────────────────────────────────────

def read_tension_state() -> Dict:
    """表面张力状态"""
    raw = _load_json(ST_F, {})
    sv = raw.get("spike_valley_vector", {})
    return {
        "anxiety":   sv.get("anxiety", 0.0),
        "anger":     sv.get("anger", 0.0),
        "fear":      sv.get("fear", 0.0),
        "joy":       sv.get("joy", 0.0),
        "sadness":   sv.get("sadness", 0.0),
        "love":      sv.get("love", 0.0),
        "curiosity": sv.get("curiosity", 0.0),
        "last_updated": raw.get("last_updated", ""),
        "events_total": len(raw.get("events", [])),
    }


def read_tension_history(n: int = 5) -> Tuple[List[float], List[str]]:
    """张力历史（anxiety时序）"""
    lines = _load_jsonl_tail(ST_HIST_F, n * 2)
    vals, times = [], []
    for l in reversed(lines):
        tv = l.get("topology_vector", {})
        anxiety = tv.get("anxiety", 0.0)
        vals.append(anxiety)
        times.append(_age(l.get("timestamp", "")))
    return vals[-n:], times[-n:]


def read_lambda_state() -> Dict:
    """λ自适应参数"""
    raw = _load_json(LAMBDA_F, {})
    # Fallback: if P/D/F missing, compute from emotions
    anxiety  = raw.get("anxiety", 0.0)
    anger    = raw.get("anger", 0.0)
    fear     = raw.get("fear", 0.0)
    joy      = raw.get("joy", 0.0)
    curiosity = raw.get("curiosity", 0.0)
    pain_int = raw.get("pain_int", 0.5)
    pain_ext = raw.get("pain_ext", 1.0)
    basin_h  = raw.get("basin_health", 0.5)

    F = raw.get("F", max(anxiety, anger, fear) * 0.6 + pain_ext * 0.4)
    D = raw.get("D", curiosity * 0.6 + basin_h * 0.4)
    P = raw.get("P", 1.0 - pain_int)
    F = min(max(F, 0.0), 1.0)
    D = min(max(D, 0.0), 1.0)
    P = min(max(P, 0.0), 1.0)

    last_upd = raw.get("last_updated") or raw.get("ts") or ""

    return {
        "λ_int":    raw.get("lambda_int", pain_int),
        "λ_ext":    raw.get("lambda_ext", pain_ext),
        "P":        P,
        "D":        D,
        "F":        F,
        "mode":     raw.get("mode", "unknown"),
        "anxiety":  anxiety,
        "joy":      joy,
        "pain_int": pain_int,
        "last_updated": last_upd,
    }


def read_dream_state() -> Dict:
    """梦境期状态"""
    raw = _load_json(DREAM_F, {})
    rep = raw.get("last_report", {})
    return {
        "compression_ratio": rep.get("compression_ratio", 0.0),
        "energy_retained":  rep.get("energy_retained", 0.0),
        "t0_tension_nodes": rep.get("t0_tension_nodes", 0),
        "t2_critical":      rep.get("t2_critical", 0),
        "t3_active_cycles": rep.get("t3_active_cycles", 0),
        "input_vectors":     rep.get("input_vectors", 0),
        "output_bases":     rep.get("output_bases", 0),
        "last_run":         raw.get("last_run", ""),
    }


def read_orb_state() -> Dict:
    """orb悬浮球状态"""
    raw = _load_json(ORB_F, {})
    return {
        "rgb":       raw.get("rgb", [0.0, 0.0, 0.0]),
        "tension":   raw.get("tension", 0.0),
        "mode":     raw.get("mode", "unknown"),
        "F":        raw.get("F", 0.0),
        "D":        raw.get("D", 0.0),
        "P":        raw.get("P", 0.0),
        "last_updated": raw.get("last_updated", ""),
    }


def read_dream_color() -> Dict:
    """最新梦境色盘"""
    lines = _load_jsonl_tail(COLOR_LOG_F, 1)
    if lines:
        l = lines[-1]
        return {
            "dominant_color_zh": l.get("dominant_color_zh", "?"),
            "dominant_color":   l.get("dominant_color", "?"),
            "tension":          l.get("tension", 0.0),
            "tension_level":    l.get("tension_level", "?"),
            "summary":          l.get("summary", ""),
            "timestamp":        l.get("timestamp", ""),
        }
    return {}


def read_hang_points() -> Dict:
    """T2悬挂缺口"""
    raw = _load_json(HANG_F, {})
    hps = raw.get("hang_points", [])
    unresolved = [h for h in hps if not h.get("resolved_at")]
    critical = [h for h in unresolved if h.get("dissonance_level") == "critical"]
    return {
        "total":    len(hps),
        "unresolved": len(unresolved),
        "critical": len(critical),
        "latest":   _age(unresolved[-1]["created_at"]) if unresolved else "none",
    }


def read_body_state() -> Dict:
    """内感受/身体稳态"""
    raw = _load_json(BODY_F, {})
    return {
        "posture_zone": raw.get("posture_zone", "?"),
        "pain_intensity": raw.get("pain_intensity", 0.0),
        "health_score": raw.get("health_score", 0.0),
        "last_updated": raw.get("last_updated", ""),
    }


def read_tension_distiller() -> Dict:
    """T0矛盾蒸馏器"""
    raw = _load_json(TENSION_DISTILLER_F, {})
    return {
        "nodes":     len(raw.get("nodes", [])),
        "top_tension": raw.get("top_tension", 0.0),
        "last_run":  raw.get("last_run", ""),
        "state":     raw.get("state", "unknown"),
    }


def read_confidence() -> Dict:
    """置信度衰减"""
    lines = _load_jsonl_tail(CONF_F, 5)
    last = lines[-1] if lines else {}
    return {
        "last_run":    last.get("timestamp", ""),
        "decayed":     last.get("decayed_nodes", 0),
        "total_decay": sum(l.get("decayed_nodes", 0) for l in lines),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 健康度评分
# ─────────────────────────────────────────────────────────────────────────────

def health_score() -> Tuple[int, List[str]]:
    """子系统健康度评分"""
    checks = [
        ("表面张力", ST_F.exists()),
        ("λ参数", LAMBDA_F.exists()),
        ("梦境压缩", DREAM_F.exists()),
        ("orb状态", ORB_F.exists()),
        ("悬挂缺口", HANG_F.exists()),
        ("内感受", BODY_F.exists()),
        ("矛盾蒸馏", TENSION_DISTILLER_F.exists()),
        ("置信度日志", CONF_F.exists()),
    ]
    active = sum(1 for _, ok in checks if ok)
    issues = [name for name, ok in checks if not ok]
    score = int(active / len(checks) * 100)
    return score, issues


# ─────────────────────────────────────────────────────────────────────────────
# 7维情感向量可视化
# ─────────────────────────────────────────────────────────────────────────────

_EMOTION_COLORS = {
    "anxiety":   ("🔴", "焦虑",    (0.9, 0.2, 0.2)),
    "anger":     ("🟠", "愤怒",    (1.0, 0.5, 0.0)),
    "fear":      ("🟤", "恐惧",    (0.55, 0.27, 0.07)),
    "joy":       ("🔵", "喜悦",    (0.2, 0.4, 1.0)),
    "sadness":   ("🟡", "悲伤",    (1.0, 0.9, 0.0)),
    "love":      ("🩷", "爱",      (1.0, 0.6, 0.8)),
    "curiosity": ("🟢", "好奇",    (0.0, 0.8, 0.3)),
}

_MAX_EMOTION = 5.0  # surface_tension 归一化上限

def print_tension_7d(t: Dict, hist_vals: List[float] = []):
    """7维情感向量柱状图"""
    print("  ┌─ 表面张力向量 ────────────────────────────────")
    print(f"  │ 更新: {_age(t['last_updated'])}  |  总事件: {t['events_total']}")

    max_val = max(abs(t[k]) for k in ["anxiety","anger","fear","joy","sadness","love","curiosity"]) or 1.0

    for key, (emoji, label, _) in _EMOTION_COLORS.items():
        raw = t.get(key, 0.0)
        # 归一化显示：负值向左，正值向右
        norm = raw / _MAX_EMOTION
        # 计算bar宽度（20字符，0点居中）
        if raw >= 0:
            bar_len = int((abs(raw) / _MAX_EMOTION) * 10)
            bar = "[" + "█" * bar_len + "░" * (10 - bar_len) + "]"
            sign = "+" if raw >= 0 else ""
        else:
            bar_len = int((abs(raw) / _MAX_EMOTION) * 10)
            bar = "[" + "░" * (10 - bar_len) + "█" * bar_len + "]"
            sign = ""
        trend_str = _trend(hist_vals) if hist_vals else ""
        print(f"  │ {emoji} {label:6s}: {sign}{raw:+.2f}  {bar}  {trend_str}")

    # 张力等级
    neg = max(t["anxiety"], t["anger"], t["fear"])
    pos = max(t["joy"], t["love"])
    tension = max(0.0, min(1.0, neg * 0.4 + t["curiosity"] * 0.15 - pos * 0.25))
    level = "■■■■■" if tension > 0.75 else "■■■□□" if tension > 0.5 else "■□□□□" if tension > 0.25 else "□□□□□"
    print(f"  │  综合张力: {tension:.3f} [{level}]")
    print("  └─────────────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# λ自适应参数
# ─────────────────────────────────────────────────────────────────────────────

def print_lambda(l: Dict):
    """λ自适应参数三轴"""
    mode = l.get("mode", "?").upper()
    mode_colors = {"STRESS": "🔴", "NORMAL": "🟡", "CALM": "🔵", "FLOW": "🟢"}
    icon = mode_colors.get(mode, "⚪")

    print("  ┌─ λ自适应参数 ───────────────────────────────")
    print(f"  │ 模式: {icon} {mode:8s}  |  更新: {_age(l.get('last_updated',''))}")
    print(f"  │")
    print(f"  │  λ_int={l['λ_int']:.3f}  λ_ext={l['λ_ext']:.3f}")
    print(f"  │")
    print(f"  │  P(稳态) = {_bar(l['P'], 12):s} {l['P']:.3f}")
    print(f"  │  D(感知) = {_bar(l['D'], 12):s} {l['D']:.3f}")
    print(f"  │  F(负载) = {_bar(l['F'], 12):s} {l['F']:.3f}")
    print(f"  │  痛感   = {_bar(l['pain_int'], 12):s} {l['pain_int']:.3f}")
    print("  └─────────────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# orb悬浮球状态
# ─────────────────────────────────────────────────────────────────────────────

def print_orb(o: Dict):
    """orb悬浮球状态"""
    rgb = o.get("rgb", [0, 0, 0])
    print("  ┌─ orb悬浮球 ─────────────────────────────────")
    print(f"  │ RGB: ({rgb[0]:.2f}, {rgb[1]:.2f}, {rgb[2]:.2f})")
    print(f"  │ 张力: {o['tension']:.3f}  模式: {o['mode']}")
    print(f"  │ P={_bar(o['P'], 8)} D={_bar(o['D'], 8)} F={_bar(o['F'], 8)}")
    print(f"  │ 更新: {_age(o.get('last_updated',''))}")
    print("  └─────────────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# 梦境期状态
# ─────────────────────────────────────────────────────────────────────────────

def print_dream(d: Dict, color: Dict):
    """梦境期压缩状态 + 色盘"""
    print("  ┌─ 梦境期压缩 ─────────────────────────────────")
    print(f"  │ 上次: {_age(d['last_run'])}")
    if d['last_run']:
        print(f"  │ {d['input_vectors']}向量 → {d['output_bases']}基底  (压缩{d['compression_ratio']:.1f}×)")
        print(f"  │ 能量保留: {d['energy_retained']:.1%}  |  T3活跃周期: {d['t3_active_cycles']}")
    print(f"  │")
    print(f"  │ T0矛盾: {d['t0_tension_nodes']}节点  T2/critical: {d['t2_critical']}")
    print(f"  │")
    if color:
        dc = color.get("dominant_color_zh", "?")
        tl = color.get("tension_level", "?")
        summary = color.get("summary", "")
        print(f"  │ 色盘: {dc}  [{tl}]  {summary}")
    else:
        print(f"  │ 色盘: 无数据")
    print("  └─────────────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# 张力矛盾节点
# ─────────────────────────────────────────────────────────────────────────────

def print_tension_nodes(td: Dict, hp: Dict):
    """T0矛盾 + T2悬挂缺口"""
    print("  ┌─ 矛盾节点 ───────────────────────────────────")
    print(f"  │ T0矛盾蒸馏器  节点: {td['nodes']}  最高张力: {td['top_tension']:.3f}  状态: {td['state']}")
    print(f"  │ T2悬挂缺口    总: {hp['total']}  未解: {hp['unresolved']}  critical: {hp['critical']}")
    if hp['unresolved'] > 0:
        print(f"  │ 最新缺口: {hp['latest']}")
    print("  └─────────────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# 快速概览（默认模式）
# ─────────────────────────────────────────────────────────────────────────────

def print_overview():
    """快速概览面板"""
    ts  = read_tension_state()
    l   = read_lambda_state()
    o   = read_orb_state()
    d   = read_dream_state()
    hp  = read_hang_points()
    td  = read_tension_distiller()
    color = read_dream_color()
    body = read_body_state()
    score, issues = health_score()

    now = datetime.now(timezone.utc).strftime("%H:%M:%S")

    print(f"\n  ┌{'─'*58}┐")
    print(f"  │  TU-8 遥测面板  {now}  UTC+8                    │")
    print(f"  ├{'─'*58}┤")

    # 健康度行
    icon = "✅" if score >= 75 else "🟡" if score >= 50 else "🔴"
    issue_str = f" ⚠️{len(issues)}" if issues else ""
    print(f"  │ {icon} 健康度: {score}%{issue_str:<40s} │")

    # 张力行
    neg = max(ts["anxiety"], ts["anger"], ts["fear"])
    pos = max(ts["joy"], ts["love"])
    tension = max(0.0, min(1.0, neg * 0.4 + ts["curiosity"] * 0.15 - pos * 0.25))
    t_level = "高压" if tension > 0.75 else "中高" if tension > 0.5 else "中低" if tension > 0.25 else "低压"
    print(f"  │ 🔺 张力: {tension:.3f} [{t_level}]  焦虑:{ts['anxiety']:+.1f}  恐惧:{ts['fear']:+.1f} │")
    print(f"  │ 🔵 正向: 喜悦:{ts['joy']:+.1f}  爱:{ts['love']:+.1f}  好奇:{ts['curiosity']:+.1f}          │")

    # λ轴
    mode_icon = {"STRESS": "🔴", "NORMAL": "🟡", "CALM": "🔵", "FLOW": "🟢"}.get(l["mode"].upper(), "⚪")
    print(f"  │ {mode_icon} 模式: {l['mode']:<8s}  P:{l['P']:.2f}  D:{l['D']:.2f}  F:{l['F']:.2f}           │")

    # 梦境
    if d['last_run']:
        dc = color.get("dominant_color_zh", "?") if color else "?"
        print(f"  │ 🟠 梦境: {d['input_vectors']}→{d['output_bases']}基底({d['compression_ratio']:.1f}×)  色盘:{dc}  T0矛盾:{d['t0_tension_nodes']} │")
    else:
        print(f"  │ 🟠 梦境: 无数据                                       │")

    # T2悬挂
    hp_icon = "🔴" if hp["critical"] > 0 else "🟡" if hp["unresolved"] > 0 else "🟢"
    print(f"  │ {hp_icon} T2缺口: {hp['unresolved']}/{hp['total']} (critical:{hp['critical']})  体感:{body.get('posture_zone','?')}         │")

    print(f"  └{'─'*58}┘")

    # 色盘详情（如果有）
    if color:
        print(f"\n  🎨 色盘: {color.get('dominant_color_zh','?')} [{color.get('tension_level','?')}]  {color.get('summary','')}")

    # 问题列表
    if issues:
        print(f"\n  ⚠️  缺失数据源: {', '.join(issues)}")


# ─────────────────────────────────────────────────────────────────────────────
# 完整面板
# ─────────────────────────────────────────────────────────────────────────────

def print_full():
    """完整遥测面板"""
    ts    = read_tension_state()
    l     = read_lambda_state()
    o     = read_orb_state()
    d     = read_dream_state()
    hp    = read_hang_points()
    td    = read_tension_distiller()
    color = read_dream_color()
    body  = read_body_state()
    conf  = read_confidence()
    hist_vals, hist_times = read_tension_history(5)

    score, issues = health_score()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n  ╔{'═'*60}╗")
    print(f"  ║         TU-8 完整遥测面板  {now} UTC+8{' '*12}║")
    print(f"  ╠{'═'*60}╣")

    # 健康度
    icon = "✅" if score >= 75 else "🟡" if score >= 50 else "🔴"
    print(f"  ║ {icon} 系统健康度: {score}%  活跃: {8-len(issues)}/8  {'⚠️ '+', '.join(issues) if issues else '所有数据源正常':<35s}║")
    print(f"  ╠{'─'*60}╣")

    print_tension_7d(ts, hist_vals)
    print()
    print_lambda(l)
    print()
    print_orb(o)
    print()
    print_dream(d, color)
    print()
    print_tension_nodes(td, hp)
    print()
    print(f"  ┌─ 体感与置信度 ───────────────────────────────")
    print(f"  │ 体感区: {body.get('posture_zone','?')}  痛感: {body.get('pain_intensity',0):.2f}  健康: {body.get('health_score',0):.0f}%")
    print(f"  │ 置信度衰减: 最近 {_age(conf['last_run'])}  本轮衰减: {conf['decayed']}  累计: {conf['total_decay']}")
    print(f"  └─────────────────────────────────────────────")
    print(f"  ╚{'═'*60}╝\n")


# ─────────────────────────────────────────────────────────────────────────────
# 轮询模式
# ─────────────────────────────────────────────────────────────────────────────

def live_poll(interval: int = 5):
    """实时轮询模式"""
    print(f"\n  🟢 TU-8 实时遥测 (刷新间隔 {interval}s, Ctrl+C 退出)\n")
    try:
        while True:
            # 光标上移覆盖
            sys.stdout.write("\033[2J")  # 清屏
            sys.stdout.write("\033[H")   # 光标归位
            print_overview()
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n  已退出轮询模式")


# ─────────────────────────────────────────────────────────────────────────────
# 健康报告
# ─────────────────────────────────────────────────────────────────────────────

def health_report():
    """健康度报告"""
    score, issues = health_score()
    td  = read_tension_distiller()
    hp  = read_hang_points()
    d   = read_dream_state()
    color = read_dream_color()

    print(f"\n  ┌─ TU-8 健康度报告 ────────────────────────────")
    print(f"  │ 综合评分: {score}%")
    print(f"  │")
    print(f"  │ ✅ 正常:")
    print(f"  │   - 表面张力监测: 运行中")
    print(f"  │   - λ自适应调参: 运行中")
    print(f"  │   - orb悬浮球: 运行中")
    print(f"  │   - 梦境期压缩: {'✓' if d['last_run'] else '✗ 无数据'}")
    if issues:
        print(f"  │")
        print(f"  │ ⚠️  数据源缺失:")
        for issue in issues:
            print(f"  │   - {issue}")
    if hp["critical"] > 0:
        print(f"  │")
        print(f"  │ 🔴 紧急: {hp['critical']}个 critical 悬挂缺口")
    print(f"  │")
    if color:
        print(f"  │ 🎨 当前色盘: {color.get('dominant_color_zh','?')} [{color.get('tension_level','?')}]")
    print(f"  └─────────────────────────────────────────────\n")


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 遥测面板")
    parser.add_argument("--full",   action="store_true", help="完整遥测")
    parser.add_argument("--tension", action="store_true", help="张力专项")
    parser.add_argument("--dream",   action="store_true", help="梦境专项")
    parser.add_argument("--health",  action="store_true", help="健康报告")
    parser.add_argument("--live",    action="store_true", help="轮询模式")
    parser.add_argument("--interval", type=int, default=5, help="轮询间隔(秒)")
    args = parser.parse_args()

    if args.full:
        print_full()
    elif args.tension:
        ts = read_tension_state(); print_tension_7d(ts)
        l  = read_lambda_state();  print_lambda(l)
        td = read_tension_distiller(); hp = read_hang_points()
        print_tension_nodes(td, hp)
    elif args.dream:
        d = read_dream_state(); color = read_dream_color()
        print_dream(d, color)
    elif args.health:
        health_report()
    elif args.live:
        live_poll(args.interval)
    else:
        print_overview()
