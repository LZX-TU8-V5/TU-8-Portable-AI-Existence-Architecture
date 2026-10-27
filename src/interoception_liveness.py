#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interoception_liveness.py — TU-8 监测存活检查（监控监控者）

【v1.2】新增 --degraded-ok：遇到 status=degraded（上游LLM不可用导致的体感环降级）
        时，不报警（认为是预期状态）。仅当 status=monitor_error 或文件缺失时报警。
【v1.3】修正路径拼写：interopertion_* → interoception_*（2026-09-24）

内感受皮层每轮写 memory/interoception_state.json（含 timestamp）。
本脚本是**独立的元监控**：只检查该输出是否新鲜 + 是否自报错。
  - 输出文件缺失 / 超过 stale-min 未更新 → 监控疑似死亡
  - 状态 status == "monitor_error" → 监控自身崩溃（self-fail-loud 已暴露）
  - 状态 status == "degraded"（+ --degraded-ok）→ 上游LLM降级，体感环降级运行，不报警

设计：本脚本极简（仅读文件 mtime/字段），自身崩溃概率远低于被监控者；
     平台级 cron 调度器为信任根（系统内无法从内部监控调度器本身）。
边沿触发：仅当问题签名变化或恢复时才打印/落 alert，避免刷屏。

用法：
  python src/interoception_liveness.py                 # 检查（变化才告警）
  python src/interoception_liveness.py --stale-min 360 # 自定义新鲜度窗口(分钟)
  python src/interoception_liveness.py --degraded-ok   # degraded状态不报警（体感环降级=预期）
  python src/interoception_liveness.py --json          # JSON 诊断
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import file_lock as flock

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
TZ = timezone(timedelta(hours=8))

# 【v1.3 修正】原路径拼写错误 interopertion_* → 实际文件为 interoception_*
#              （typo 导致误报 missing/stale，2026-09-24 修正）
STATE = os.path.join(MEM, "interoception_state.json")
LIVE_LOG = os.path.join(MEM, "interoception_liveness_alerts.jsonl")
LAST = os.path.join(MEM, "interoception_liveness_last.json")


def check(stale_min, degraded_ok=False):
    now = datetime.now(TZ)
    problems = []
    if not os.path.exists(STATE):
        problems.append(("missing", "interoception_state.json 不存在（监控从未运行或已死）"))
        return problems, now
    try:
        st = flock.safe_read_json(STATE)
    except Exception:
        st = None
    if st is None:
        problems.append(("unreadable", "监控状态文件无法解析/缺失"))
        return problems, now
    ts_str = st.get("timestamp")
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except Exception:
        problems.append(("bad_ts", f"监控状态 timestamp 非法: {ts_str}"))
        return problems, now
    age_min = (now - ts).total_seconds() / 60
    if age_min > stale_min:
        problems.append(("stale", f"监控输出已 {age_min:.0f} 分钟未更新（>{stale_min}min，疑似死亡）"))
    
    # 【v1.2】状态检查：区分崩溃 vs 降级
    status = st.get("status", "unknown")
    if status == "monitor_error":
        problems.append(("self_error", f"监控自身报错: {st.get('error', 'unknown')}"))
    elif status == "degraded":
        if degraded_ok:
            # degraded = 上游LLM不可用，体感环降级运行，不报警
            pass
        else:
            problems.append(("degraded", f"体感环降级运行: {st.get('degraded_reason', '上游LLM不可用')}"))
    elif status == "ok":
        pass  # 健康
    else:
        # 未知状态
        problems.append(("unknown_status", f"未知状态: {status}"))
    
    return problems, now


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-min", type=int, default=12)
    ap.add_argument("--degraded-ok", action="store_true",
                    help="degraded状态不报警（上游LLM不可用时体感环降级=预期状态）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    problems, now = check(args.stale_min, degraded_ok=args.degraded_ok)

    if args.json:
        print(json.dumps({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                          "problems": [{"type": k, "message": m} for k, m in problems]},
                         ensure_ascii=False, indent=2))
        return

    # 边沿触发
    sig = tuple(sorted(problems))
    prev = ()
    prev_raw = flock.safe_read_json(LAST, {})
    if prev_raw:
        prev = tuple(tuple(x) for x in prev_raw.get("sig", []))
    if sig == prev:
        return  # 静默
    with flock.FileLock(LAST):
        flock.atomic_write_json(LAST, {"sig": [list(s) for s in sig],
                                    "ts": now.strftime("%Y-%m-%d %H:%M:%S")})
    if problems:
        for k, m in problems:
            flock.append_jsonl(LIVE_LOG, {"ts": now.strftime("%Y-%m-%d %H:%M:%S"),
                                          "type": k, "message": m})
        print(f"⚠️ TU-8 监测存活告警 @ {now.strftime('%Y-%m-%d %H:%M:%S')}")
        for k, m in problems:
            print(f"  [{k}] {m}")
    else:
        print(f"✅ TU-8 监测存活正常 @ {now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
