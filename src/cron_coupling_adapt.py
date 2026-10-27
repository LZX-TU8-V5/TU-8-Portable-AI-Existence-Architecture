# -*- coding: utf-8 -*-
"""
cron_coupling_adapt.py — B11 + B10 耦合适配
每 600s 运行一次：
  1. 读取所有引擎当前状态，record_tick() 写入 RingBuffer
  2. 用历史延迟上下文驱动 evaluate() + adapt()

B11: RingBuffer 历史快照，delay_ticks 显式生效
B10: 蛛丝弹性权重更新，Δw=α·(1-w²)·pre·post
"""
import sys, os, json, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QCLAW_WORKSPACE", str(Path(__file__).parent.parent))

WS = Path(os.environ["QCLAW_WORKSPACE"])
AGENT = WS / "_agent_memory"
OUT = AGENT / "cron_coupling_adapt_last.json"

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("coupling_adapt")


def safe_read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default if default is not None else {}


def anxiety_freq_and_mag(recent_events):
    """焦虑类事件综合激活"""
    if not recent_events:
        return 0.0, 0.0
    evts = [e for e in recent_events if isinstance(e, dict) and
            e.get("type", "").lower().lstrip() in ("anxiety", "fear", "dissonance", "conflict", "pressure")]
    if not evts:
        return 0.0, 0.0
    n = len(evts)
    freq = min(n / max(len(recent_events), 1) / 0.5, 1.0)
    mag = min(sum(e.get("intensity", 0) for e in evts) / n / 0.4, 1.0)
    return freq, mag


def main():
    ts = datetime.now().isoformat()
    start = datetime.now()

    results = {"adapted": [], "skipped": [], "errors": []}

    # ── 读取所有引擎状态 ─────────────────────────────────────
    states = {
        "surface_tension": safe_read_json(AGENT / "surface_tension_state.json", {}),
        "orb_state_writer": safe_read_json(AGENT / "orb_state.json", {}),
        "lambda_state": safe_read_json(AGENT / "lambda_state.json", {}),
        "attractor_basin": safe_read_json(AGENT / "attractor_basin_state.json", {}),
        "alignment_verify": safe_read_json(AGENT / "alignment_verify_state.json", {}),
    }

    # ── 加载 coupling_graph ─────────────────────────────────
    try:
        from coupling_graph import get_coupling_graph
        cg = get_coupling_graph()
    except Exception as e:
        results["errors"].append(f"import: {e}")
        _write(OUT, {"ok": False, "ts": ts, "errors": results["errors"]})
        return

    # ── B11: record_tick 写入 RingBuffer ─────────────────────
    tick = cg.record_tick(states)

    # ── B11: 用延迟上下文 evaluate ───────────────────────────
    # 注意：evaluate() 会自动按 delay_ticks 读历史（首次无历史时 fallback 当前）
    try:
        orb_results = cg.evaluate("orb_state_writer", states)
        llm_results = cg.evaluate("LLM", states)
    except Exception as e:
        results["errors"].append(f"evaluate: {e}")
        _write(OUT, {"ok": False, "ts": ts, **results})
        return

    # ── B10: 蛛丝弹性适配 ───────────────────────────────────
    st = states["surface_tension"]
    orb = states["orb_state_writer"]
    recent = st.get("recent_events", [])
    anxiety_f, anxiety_m = anxiety_freq_and_mag(recent)
    orb_red_prev = orb.get("rgb", [0, 0, 0])[0] if isinstance(orb.get("rgb"), list) else 0.0

    # C1: surface_tension→orb.red
    pre_c1 = anxiety_f * 0.7 + anxiety_m * 0.3
    r = cg.adapt("C1", pre_c1, orb_red_prev)
    if r:
        results["adapted"].append({"edge": "C1", "pre": round(pre_c1, 3), "post": round(orb_red_prev, 3), "w_new": r["w_new"]})

    # C6: affect_modulation→LLM.temperature
    anxiety_val = st.get("spike_valley_vector", {}).get("anxiety", 0.0)
    fear_val = st.get("spike_valley_vector", {}).get("fear", 0.0)
    joy_val = st.get("spike_valley_vector", {}).get("joy", 0.0)
    love_val = st.get("spike_valley_vector", {}).get("love", 0.0)
    tension = (anxiety_val + fear_val) / 2.0
    resonance = (joy_val + love_val) / 2.0
    temp_delta = tension * 0.3 - resonance * 0.2
    r = cg.adapt("C6", tension, abs(temp_delta) / 0.9)
    if r:
        results["adapted"].append({"edge": "C6", "pre": round(tension, 3), "post": round(abs(temp_delta) / 0.9, 3), "w_new": r["w_new"]})

    # C10: alignment_verify→surface_tension
    meta = states["alignment_verify"]
    insight = float(meta.get("deviation_gate", {}).get("passed", False))
    r = cg.adapt("C10", insight, anxiety_m * 0.3)
    if r:
        results["adapted"].append({"edge": "C10", "pre": round(insight, 3), "post": round(anxiety_m * 0.3, 3), "w_new": r["w_new"]})

    elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)

    # 保存：权重 + RingBuffer 元数据（快照内容不入文件）
    cg.save()

    summary = {
        "ok": True,
        "ts": ts,
        "elapsed_ms": elapsed_ms,
        "tick": cg.get_tick(),
        "ring_info": cg.get_ring_info(),
        **results,
    }
    _write(OUT, summary)

    adapted_str = ", ".join(f"{a['edge']}(w={a['w_new']:.3f})" for a in results["adapted"])
    log.warning(f"[coupling_adapt] tick={cg.get_tick()} adapted={len(results['adapted'])} [{adapted_str}]")


def _write(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
