#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interoceptive_cortex.py — TU-8 内感受皮层 v1.1（自适应基线阈值）

v1.1 升级：阈值从硬编码改为**自适应基线**。
  - 滚动历史 memory/interoception_history.json（每指标最近 200 样本）
  - 基线 = 稳健中位数；离散度 = MAD×1.4826（抗离群）
  - 双层告警：
      ① 偏差告警：当前 > 基线 + DEV_K·σ → 相对基线偏移（真正的新异常）
      ② 绝对天花板：当前 ≥ *CEILING → 始终告警（防温水煮青蛙，慢性危险不被静音）
  - 慢性高水位 → 稳定中等 severity（边沿触发后静默），新尖峰 → 高 severity

复用 session_watchdog 的会话扫描（freeze 子感）。
设计纪律：每轮写 interoception_state.json（遥测始终新鲜）；告警边沿触发（签名变化才打印）。
self-fail-loud：异常也写 status=monitor_error 保活+暴露。

用法：
  python src/interoceptive_cortex.py            # 扫描+自适应体感+驱动身体层
  python src/interoceptive_cortex.py --json     # JSON 诊断
"""
import os
import sys
import json
import glob
import argparse
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import session_watchdog as wd  # 复用会话扫描（freeze 子感）
import file_lock as flock  # 跨进程锁 + 原子写

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
AGENT = os.path.join(WS, "_agent_memory")
TZ = timezone(timedelta(hours=8))
LAMBDA_F = os.path.join(AGENT, "lambda_state.json")  # orb 数据源

RECENT_DAYS = 7
PAIN_THRESHOLD = 0.30
DEV_K = 2.0                  # 偏差 = 基线 + 2·稳健σ
CONTEXT_CEILING = 98        # 上下文绝对天花板（%）：≥此值始终告警
ABORT_CEILING = 0.15        # abort 率绝对天花板：≥此值始终告警
HISTORY_CAP = 200

LAST_ALERT = os.path.join(MEM, "interoception_last_alert.json")
STATE_PATH = os.path.join(MEM, "interoception_state.json")
ALERTS_LOG = os.path.join(MEM, "interoception_alerts.jsonl")
HISTORY_PATH = os.path.join(MEM, "interoception_history.json")


# ---------- 稳健统计 ----------
def robust_stats(samples):
    if not samples:
        return 0.0, 0.0
    s = sorted(samples)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    devs = sorted(abs(x - med) for x in s)
    mad = devs[n // 2] if n % 2 else (devs[n // 2 - 1] + devs[n // 2]) / 2.0
    sigma = 1.4826 * mad
    if sigma < 1e-9:
        sigma = 1e-9  # 全相等（慢性稳态）→ 无偏差可分，防除零
    return med, sigma


# ---------- 滚动历史 ----------
def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            d = json.load(open(HISTORY_PATH, encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception as e:
            try:
                import health_log
                health_log.log_event("interop_cortex", "ERROR",
                    f"历史加载失败: {e}")
            except Exception:
                pass
    return {"context_load_pct": [], "recent_abort_rate": []}


def update_history(hist, ctx_pct, abort_rate):
    hist.setdefault("context_load_pct", []).append(ctx_pct)
    hist.setdefault("recent_abort_rate", []).append(abort_rate)
    for k in ("context_load_pct", "recent_abort_rate"):
        if len(hist[k]) > HISTORY_CAP:
            hist[k] = hist[k][-HISTORY_CAP:]
    with flock.FileLock(HISTORY_PATH):
        flock.atomic_write_json(HISTORY_PATH, hist)


# ---------- 遥测采集 ----------
def compute_failure_and_freeze(index):
    total = aborted = empty = recent_total = recent_aborted = 0
    freeze_list = []
    now = datetime.now(TZ)
    if not os.path.isdir(wd.SESS_DIR):
        return dict(total=0, aborted=0, empty=0, recent_total=0, recent_aborted=0,
                    abort_rate=0.0, recent_abort_rate=0.0, freeze_list=[])
    for fp in glob.glob(os.path.join(wd.SESS_DIR, "*.jsonl")):
        r = wd.scan_session(fp, index)
        if r:
            freeze_list.append(r)
        try:
            lines = open(fp, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for ln in lines:
            try:
                o = json.loads(ln)
            except Exception:
                continue
            m = o.get("message", {})
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            total += 1
            ts = o.get("timestamp") or o.get("ts")
            recent = False
            if isinstance(ts, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, TZ)
                    recent = (now - dt).days <= RECENT_DAYS
                except Exception:
                    recent = False
            if recent:
                recent_total += 1
            bad, _ = wd.is_failed_turn(m)
            if bad:
                aborted += 1
                if recent:
                    recent_aborted += 1
            else:
                c = m.get("content")
                if c in (None, "", []) or (isinstance(c, list) and len(c) == 0):
                    empty += 1
    abort_rate = (aborted / total) if total else 0.0
    recent_abort_rate = (recent_aborted / recent_total) if recent_total else 0.0
    return dict(total=total, aborted=aborted, empty=empty,
                recent_total=recent_total, recent_aborted=recent_aborted,
                abort_rate=abort_rate, recent_abort_rate=recent_abort_rate,
                freeze_list=freeze_list)


def compute_context(index):
    """上下文负载估算。

    修复 (2026-08-19)：sessions.json 的 contextTokens 字段实为【上下文窗口容量】
    （running=262144、done=250000… 均为固定占位值），并非真实已用 token 数。
    gateway 实测运行会话仅 2%（4k/262k）。原逻辑取所有会话的 MAX → 永远 262144
    → load_pct 恒为 100% → body_posture 永为 critical → 误杀所有任务。

    新逻辑：>= CONTEXT_CAP_PLACEHOLDER 视为占位、排除；仅用 < 该阈值的真实读数
    计算负载；若全部都是占位（无真实读数），fallback 到 0%（不误报）。
    """
    CONTEXT_CAP_PLACEHOLDER = 200_000   # >= 此值判定为窗口容量占位，非 usage
    genuine = []          # 真实已用 token（子阈值读数）
    big = 0               # 占位/高位会话数（仅统计用，不再参与 MAX）
    for v in index.values():
        ctx = v.get("contextTokens", 0) or 0
        if ctx >= CONTEXT_CAP_PLACEHOLDER:
            big += 1
        else:
            genuine.append(ctx)
    if genuine:
        # 真实负载取真实读数的高水位（反映实际最满会话）
        max_ctx = max(genuine)
    else:
        # 无任何真实读数：合理 fallback——取占位中最小的（最接近真实窗口占用），
        # 但更保守地直接判 0%，避免误报 critical 误杀任务
        max_ctx = 0
    pct = min(100, int(max_ctx / 200_000 * 100)) if max_ctx else 0
    return dict(max_ctx=max_ctx, load_pct=pct, big_ctx_sessions=big)


def derive_pains(fr, ctx, hist, now=None):
    """自适应痛觉：偏差(相对基线) + 绝对天花板。"""
    now = now or datetime.now(TZ)
    pains = []
    base_ctx, sig_ctx = robust_stats(hist.get("context_load_pct", []))
    base_ab, sig_ab = robust_stats(hist.get("recent_abort_rate", []))

    # freeze（事件型，保持）
    stuck = fr["freeze_list"]
    if stuck:
        sev = min(1.0, 0.5 + 0.1 * sum(s["swallowed_count"] for s in stuck))
        labels = ", ".join(f"{s['label']}(吞{s['swallowed_count']})" for s in stuck[:3])
        pains.append(dict(type="freeze", severity=round(sev, 2),
                          message=f"{len(stuck)} 个会话卡死/吞输入：{labels}"))

    # context（自适应）
    cl = ctx["load_pct"]
    if cl >= CONTEXT_CEILING:
        msg = f"上下文水位 {cl}%（≥{CONTEXT_CEILING}绝对天花板；基线{round(base_ctx)}）"
        pains.append(dict(type="context", severity=0.5, message=msg, mode="ceiling"))
    elif sig_ctx > 0 and cl > base_ctx + DEV_K * sig_ctx:
        sev = min(1.0, (cl - base_ctx) / (3 * sig_ctx))
        pains.append(dict(type="context", severity=round(sev, 2),
                          message=f"上下文水位 {cl}%，偏离基线{round(base_ctx)}+{DEV_K}σ", mode="deviation"))

    # reliability（自适应）
    ra = fr["recent_abort_rate"]
    if ra >= ABORT_CEILING:
        msg = f"近期 abort 率 {ra*100:.0f}%（≥{ABORT_CEILING}绝对天花板；基线{round(base_ab,3)}）"
        pains.append(dict(type="reliability", severity=0.5, message=msg, mode="ceiling"))
    elif sig_ab > 0 and ra > base_ab + DEV_K * sig_ab:
        sev = min(1.0, (ra - base_ab) / (3 * sig_ab))
        pains.append(dict(type="reliability", severity=round(sev, 2),
                          message=f"近期 abort 率 {ra*100:.0f}%，偏离基线{round(base_ab,3)}+{DEV_K}σ", mode="deviation"))

    return pains


def write_telemetry(state):
    os.makedirs(MEM, exist_ok=True)
    flock.atomic_write_json(STATE_PATH, state)


def write_lambda_state(state):
    """
    将体感数据映射为 orb 的 lambda_state.json（完整版）。
    orb 需要：anxiety/anger/fear/curiosity → F(红)，
              basin_health → D(绿)，
              pain_int → P(蓝)
    全部聚合到 lambda_state.json，从此单一数据源。
    """
    pains = state.get("pain_signals", [])
    ctx_pct = state.get("context_load_pct", 0)
    posture = state.get("body_posture", "neutral")
    abort_rate = state.get("recent_abort_rate", 0)
    ts = state.get("timestamp", "")

    # 从 pain_signals 提取 severity
    if pains:
        severities = [p.get("severity", 0) for p in pains]
        max_sev = max(severities)
        avg_sev = sum(severities) / len(severities)
    else:
        max_sev = 0.0
        avg_sev = 0.0

    pain_int = min(avg_sev * 0.8 + max_sev * 0.2, 1.0)
    pain_ext = min(ctx_pct / 100.0, 1.0)

    # anxiety/anger/fear ← 从 pain_signals 类型推断（归一化 0-1）
    anxiety = pain_ext   # 上下文负载 → 焦虑
    anger   = pain_int   # 体感压力 → 愤怒（内部挫败感）
    fear    = max_sev * 0.5  # 急性告警 → 恐惧

    # ── P0-2c: 合并 surface_tension 对话张力（归一化到[0,1]）──────────
    # 功能：让 orb 显示同时反映体感压力 + 对话张力，两者取最大
    try:
        import json as _json, sys as _sys
        _sys.path.insert(0, str(pathlib.Path(__file__).parent))
        ST_F = pathlib.Path(__file__).parent.parent / "_agent_memory" / "surface_tension_state.json"
        if ST_F.exists():
            st_data = _json.loads(ST_F.read_text(encoding="utf-8"))
            sv = st_data.get("spike_valley_vector", {})
            ST_MAX = 5.0
            # surface_tension 归一化 + 取最大（体感与对话张力谁高显示谁）
            anxiety = max(anxiety, min(sv.get("anxiety", 0) / ST_MAX, 1.0))
            anger   = max(anger,   min(sv.get("anger",   0) / ST_MAX, 1.0))
            fear    = max(fear,    min(sv.get("fear",    0) / ST_MAX, 1.0))
            joy     = min(sv.get("joy", 0) / ST_MAX, 1.0)
    except Exception:
        pass  # 非致命：不阻断体感环

    # curiosity ← 稳态时的活跃度（abort_rate 低 → 好奇活跃）
    curiosity = max(0.0, 0.6 - abort_rate * 5)

    # basin_health ← 从 pain_int 推导（高痛觉 → 低盆地健康）
    basin_health = max(0.3, 1.0 - pain_int * 1.5)

    # mode 映射
    if posture == "critical":
        mode = "stress"
    elif posture == "warning":
        mode = "conserve"
    elif posture == "healthy":
        mode = "relax"
    else:
        mode = "neutral"

    os.makedirs(AGENT, exist_ok=True)
    # [P3-3a fix] read-modify-write：读原文件，合并 IC 的 key，保留 LT/ST 的字段
    prev = flock.safe_read_json(LAMBDA_F, {})
    prev.update({
        # orb 三轴（IC 写体感版本）
        "anxiety":        anxiety,
        "anger":          anger,
        "fear":           fear,
        "curiosity":      curiosity,
        "basin_health":   basin_health,
        "pain_int_raw":   pain_int,   # [P3-3c] IC写raw版本，LT读后做EMA平滑再写smoothed版本
        "pain_ext_raw":   pain_ext,   # [P3-3c] ORB只读smoothed版本，两层隔离
        # orb 元数据
        "mode":           mode,
        "ts":             ts,
        "body_posture":   posture,
        "context_load_pct": ctx_pct,
    })
    flock.atomic_write_json(LAMBDA_F, prev)


def edge_trigger(alerting, ts):
    sig = tuple(sorted((p["type"], round(p["severity"], 1)) for p in alerting))
    prev = ()
    prev_raw = flock.safe_read_json(LAST_ALERT, {})
    if prev_raw:
        prev = tuple(tuple(x) for x in prev_raw.get("sig", []))
    if sig == prev:
        return "silent", sig
    with flock.FileLock(LAST_ALERT):
        flock.atomic_write_json(LAST_ALERT, {"sig": list(sig), "ts": ts})
    if alerting:
        for p in alerting:
            flock.append_jsonl(ALERTS_LOG, {"ts": ts, **p})
        return "alert", sig
    return "recover", sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        # 启动一致性门（L2 防护，best-effort）：每轮运行前先对账，愈合历史残留的不一致
        try:
            import startup_consistency_gate as scg
            scg.run()
        except Exception:
            pass
        index = wd.load_sessions_index()
        fr = compute_failure_and_freeze(index)
        ctx = compute_context(index)
        now = datetime.now(TZ)
        hist = load_history()
        pains = derive_pains(fr, ctx, hist, now)
        alerting = [p for p in pains if p["severity"] >= PAIN_THRESHOLD]

        state = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ok",
            "context_load_pct": ctx["load_pct"],
            "max_context_tokens": ctx["max_ctx"],
            "big_ctx_sessions": ctx["big_ctx_sessions"],
            "assistant_turns_total": fr["total"],
            "abort_rate": round(fr["abort_rate"], 4),
            "recent_abort_rate": round(fr["recent_abort_rate"], 4),
            "freeze_sessions": len(fr["freeze_list"]),
            "swallowed_total": sum(s["swallowed_count"] for s in fr["freeze_list"]),
            "baseline": {
                "context_load_pct": round(robust_stats(hist.get("context_load_pct", []))[0], 1),
                "recent_abort_rate": round(robust_stats(hist.get("recent_abort_rate", []))[0], 4),
            },
            "pain_signals": pains,
        }
        state["epoch"] = state["timestamp"]

        try:
            import body_schema
            reg = body_schema.regulate_from_state(state, pains)
            state["body_posture"] = reg.get("posture")
        except Exception as e:
            state["body_posture"] = f"body_schema 错误: {e}"

        update_history(hist, ctx["load_pct"], fr["recent_abort_rate"])
        write_telemetry(state)
        write_lambda_state(state)   # orb 实时数据源

        # 上下文阀门动态调节器（副效应，不阻断主流程）
        try:
            import context_controller
            context_controller.compute(state.get("context_load_pct", 0) / 100.0)
        except Exception:
            pass

        try:
            import body_schema as _bs
            _bs.mark_healthy()
        except Exception:
            pass

        if args.json:
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return

        kind, _ = edge_trigger(alerting, state["timestamp"])
        if kind == "alert":
            lines = [f"⚠️ TU-8 体感告警 @ {state['timestamp']}"]
            for p in alerting:
                lines.append(f"  [{p['type']}/{p.get('mode','')} sev={p['severity']}] {p['message']}")
            lines.append(f"  身体姿态：{state.get('body_posture')}")
            print("\n".join(lines))
        elif kind == "recover":
            print(f"✅ TU-8 体感恢复 @ {state['timestamp']}：此前告警已清除")
    except Exception as e:
        ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        err_state = {
            "timestamp": ts,
            "status": "monitor_error",
            "error": str(e),
            "pain_signals": [{"type": "monitor_self", "severity": 0.9,
                              "message": f"内感受脚本异常: {e}"}],
        }
        write_telemetry(err_state)
        flock.append_jsonl(ALERTS_LOG, {"ts": ts, **err_state["pain_signals"][0]})
        print(f"⚠️ 内感受脚本自身异常: {e}")


if __name__ == "__main__":
    main()
