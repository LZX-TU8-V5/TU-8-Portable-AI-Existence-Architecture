#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intuition_bias.py — 读取当前直觉偏置（痛觉 → 决策先验）

内感受监控每次运行在 memory/intuition_bias.json 写出"快预测先验"：
  posture 决定 mode / temperature_hint / spawn_subagent / prefer_compact / confidence_damp。
决策层（Agent / 子 agent）每轮开始读取，让痛觉在深思前就调制默认计划。

用法：
  python src/intuition_bias.py        # 人类可读
  python src/intuition_bias.py --json # JSON
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
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    b = body_schema.current_intuition_bias()
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=2))
        return
    print(f"直觉偏置：posture={b['posture']}  mode={b['mode']}")
    print(f"  temperature_hint={b['temperature_hint']}  "
          f"spawn_subagent={b['spawn_subagent']}  prefer_compact={b['prefer_compact']}  "
          f"confidence_damp={b['confidence_damp']}")
    print("  含义：痛觉越高→越保守；critical 时先 compact / 不派生子agent / 降 temp / 降置信。")


if __name__ == "__main__":
    main()
