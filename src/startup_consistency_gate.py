#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
startup_consistency_gate.py — TU-8 启动一致性门（防"身首异处" / Zombie）

设计目标（元防护锁 L2）：
  网关启动 / 监控每轮运行前调用。校验"头"(LLM) 与"心"(内感受皮层) 之间的
  状态契约是否一致。任一方不能单方面宣布对方死亡。

检测项：
  1. interoception_state.json 缺失/损坏 或 status 落入不可信集合
     （monitor_error / zombie / inconsistent）→ 状态不可信
  2. 跨文件 epoch 一致性：state / body_regulation / intuition_bias 三者 epoch
     必须同源（同一轮监控写出）。不一致 = 跨文件语义错乱（崩溃中途残留）

不一致（身首契约失配）→ 调 body_schema.write_safe_default() 写 posture=unknown
（fail-open 保活，绝不宣布死亡），并落 memory/.recovery_mode 标记；
一致 → 清除 .recovery_mode。

返回 report dict。失败不应阻断启动（best-effort）。

用法：
  python src/startup_consistency_gate.py            # 运行并修复
  python src/startup_consistency_gate.py --json     # JSON 输出
"""
import os
import sys
import json
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import file_lock as flock
import body_schema as bs

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, ".qclaw", "workspace")
MEM = os.path.join(WS, "memory")
STATE = os.path.join(MEM, "interoception_state.json")
REG = os.path.join(MEM, "body_regulation.json")
BIAS = os.path.join(MEM, "intuition_bias.json")
RECOVERY = os.path.join(MEM, ".recovery_mode")


def _recovery_on(reason: str) -> dict:
    bs.write_safe_default(reason=reason)
    try:
        with flock.FileLock(RECOVERY):
            flock.atomic_write_json(RECOVERY, {"recovery": True, "reason": reason})
    except Exception:
        pass
    return {"status": "recovery", "posture": "unknown", "reasons": [reason]}


def _recovery_off() -> dict:
    try:
        if os.path.exists(RECOVERY):
            os.remove(RECOVERY)
    except Exception:
        pass
    return {"status": "ok", "posture": "unknown", "reasons": []}


def run() -> dict:
    state = flock.safe_read_json(STATE)
    reg = flock.safe_read_json(REG)
    bias = flock.safe_read_json(BIAS)
    reasons = []

    # 检测 0（L1）：梦境期事务日志中断（硬杀/失败残留）→ 不信任梦境后状态
    try:
        import dream_txn as dt
        dinfo = dt.recover()
        if dinfo:
            reasons.append(f"梦境期事务中断（started_at={dinfo.get('started_at')}, 已完成={dinfo.get('done')}）→ 不信任梦境后状态")
    except Exception:
        pass

    # 检测 1：状态缺失 / 不可信
    if state is None:
        reasons.append("interoception_state.json 缺失/损坏")
    elif state.get("status") in bs.UNTRUSTED_STATUS:
        reasons.append(f"内感受状态 status={state.get('status')} 不可信")

    # 检测 2：跨文件 epoch 一致性
    se = (state or {}).get("epoch")
    re_ = (reg or {}).get("epoch")
    be = (bias or {}).get("epoch")
    if se and re_ and se != re_:
        reasons.append(f"epoch 不一致 state={se} reg={re_}")
    if se and be and se != be:
        reasons.append(f"epoch 不一致 state={se} bias={be}")

    if reasons:
        return _recovery_on("; ".join(reasons))

    # 一致：清除 recovery 标记，回报真实姿态
    rep = _recovery_off()
    rep["posture"] = (reg or {}).get("posture", "unknown")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()
    try:
        rep = run()
    except Exception as e:  # best-effort：绝不让一致性门阻断启动
        rep = {"status": "error", "posture": "unknown", "reasons": [f"gate 异常: {e}"]}
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"[{rep['status']}] posture={rep['posture']}"
              + (f" | {rep['reasons'][0]}" if rep.get("reasons") else ""))


if __name__ == "__main__":
    main()
