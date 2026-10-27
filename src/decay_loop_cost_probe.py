"""
decay_loop_cost_probe.py — decay_loop 心跳资源成本评估 [P0-2, 2026-08-29]

实测 surface_tension_history.jsonl：
  - 总行数 / 体积
  - decay_tick 类型占比（后台常驻心跳）
  - 时间跨度 + 实际频率（条/分钟）
  - 限频建议（记忆量上升时防隐性负担）

只读分析，不修改任何文件。
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def main() -> dict:
    ws = Path(r"C:\Users\qq366410837\.qclaw\workspace")
    hist = ws / "_agent_memory" / "surface_tension_history.jsonl"
    if not hist.exists():
        return {"error": "MISSING"}
    lines = hist.read_text(encoding="utf-8", errors="ignore").splitlines()
    total = len(lines)
    size_kb = hist.stat().st_size / 1024

    types = {}
    ts_min, ts_max = None, None
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        t = o.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
        ts = o.get("ts")
        if isinstance(ts, (int, float)):
            ts_min = ts if ts_min is None else min(ts_min, ts)
            ts_max = ts if ts_max is None else max(ts_max, ts)

    decay = types.get("decay_tick", 0)
    span_s = (ts_max - ts_min) if (ts_min and ts_max) else 0
    span_min = span_s / 60 if span_s else 0
    freq = decay / span_min if span_min else 0

    # 预估：按当前频率，1 年后体量
    per_day = decay / (span_min / (60 * 24)) if span_min else 0
    year_mb = (per_day * 365 * 80) / 1024 / 1024  # 估算每条 ~80B

    return {
        "total_lines": total,
        "size_kb": round(size_kb, 1),
        "type_breakdown": types,
        "decay_tick_count": decay,
        "decay_ratio": round(decay / total, 3) if total else 0,
        "span_minutes": round(span_min, 1),
        "freq_per_min": round(freq, 2),
        "est_per_day": round(per_day, 1),
        "est_year_mb": round(year_mb, 1),
        "recommendation": (
            "当前 decay_tick 约 %.1f 条/分钟（~%.0f 条/天），体量 %.0f KB。"
            "记忆量上升时建议：① 限频至每 10-15min 一次（降 2-3x）；"
            "② 异步批量写入（累积 N 条 flush 一次）；"
            "③ history.jsonl 按月滚动归档（防单文件无限增长）。"
            % (freq, per_day, size_kb)
        ),
    }


if __name__ == "__main__":
    r = main()
    for k, v in r.items():
        print(f"  {k}: {v}")
