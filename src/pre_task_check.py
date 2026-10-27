#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_task_check.py — 重活前身体姿态门禁（body_schema.can_afford 封装）

把"身体层"接进实际决策：重活前先查姿态，NO-GO 就不要硬上。

用法：
  python src/pre_task_check.py high     # 写代码/长任务/大上下文操作前查
  python src/pre_task_check.py mid
  python src/pre_task_check.py low
  python src/pre_task_check.py --json

退出码：0 = GO，1 = NO-GO（可接入脚本/流水线做硬门禁）。
行为约定：NO-GO 时先 compact 降上下文 / 拆小任务 / 降野心，再评估。
说明：姿态读 memory/body_regulation.json（由内感受监控每 2.5h 刷新）。
      需更实时可加 --refresh 重跑监控取最新姿态。
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
import body_schema


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weight", nargs="?", default="mid", choices=["low", "mid", "high"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="重跑内感受监控取最新姿态")
    args = ap.parse_args()

    if args.refresh:
        try:
            import interoceptive_cortex
            interoceptive_cortex.main()
        except Exception as e:
            print(f"⚠️ refresh 失败: {e}（用缓存姿态）")

    ok, reason = body_schema.can_afford(args.weight)
    reg = body_schema.current_regulation()
    bias = body_schema.current_intuition_bias()
    posture = reg.get("posture")
    actions = reg.get("recommended_actions", [])

    if args.json:
        print(json.dumps({"weight": args.weight, "posture": posture, "allow": ok,
                          "reason": reason, "recommended_actions": actions,
                          "intuition_bias": bias}, ensure_ascii=False, indent=2))
        return

    sym = "✅ GO" if ok else "⛔ NO-GO"
    print(f"{sym} [{args.weight}] 身体姿态={posture} | 直觉偏置={bias.get('mode')}")
    print(f"  原因：{reason}")
    print(f"  直觉：temp≤{bias.get('temperature_hint')} 派生子agent={bias.get('spawn_subagent')} "
          f"优先compact={bias.get('prefer_compact')} 置信阻尼={bias.get('confidence_damp')}")
    if not ok and actions:
        print("  建议：")
        for a in actions:
            print(f"    - {a}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
