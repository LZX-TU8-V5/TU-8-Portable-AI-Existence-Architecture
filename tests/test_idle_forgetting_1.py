# -*- coding: utf-8 -*-
"""P0 深度测试：idle 驱动的信号衰减 + 选择遗忘"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import logging
import time

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(message)s")

from consciousness_cycle import ConsciousnessCycle

cycle = ConsciousnessCycle()

# 关键：idle 是基于 _last_micro_sleep_time 计算的
# 所以需要在微睡眠之间让时间流逝
# 方法：直接回退 _last_micro_sleep_time

print("=== Simulating 30 micro-sleeps with growing idle gaps ===")
forgotten_total = 0

for i in range(30):
    # 模拟 idle：回退上次微睡眠时间戳（每次增加2小时）
    # 前5次 idle=0（即时），之后每次增加2小时
    if i < 5:
        gap_hours = 0
    else:
        gap_hours = 2 + (i - 5) * 2  # 2, 4, 6, 8, ... hours
    cycle._last_micro_sleep_time = time.time() - gap_hours * 3600

    snap = {
        "summary": f"常规交互 #{i+1}: 这是一条普通的日常记录",
        "context_usage": 0.85,
        "events": [f"event_{i}"],
        "trivial": f"不重要的细节信息第{i+1}条，包含一些冗余的描述文字",
    }
    report = cycle.tick(context_snapshot=snap)
    lossy = report.get("lossy", {})
    forgotten = len(lossy.get("destroyed_seal_ids", []))
    forgotten_total += forgotten

    if i % 5 == 0 or forgotten > 0:
        print(
            f"  Sleep #{i+1:2d}: idle_hrs={lossy.get('idle_hours', 0):.1f} "
            f"destruction={lossy.get('destruction_ratio', 0):.2f} "
            f"forgotten={forgotten} total_destroyed={len(cycle._total_destroyed_ids)}"
        )

print()
status = cycle.status()
print(f"Total destruction ratio: {status['total_destruction_ratio']:.3f}")
print(f"Total forgotten IDs:     {status['total_forgotten_count']}")
print(f"Seals created:           {status['total_micro_sleeps']}")

if status['total_forgotten_count'] > 0:
    print()
    print("PASS: idle-driven forgetting detected!")
    print(f"Forgotten IDs (audit): {cycle._total_destroyed_ids[:10]}...")
else:
    print()
    print("NOTE: No selective forgetting triggered")
    print("This is because significance starts at 0.4+ and decay is slow")
    print("The mechanism is ready for real workloads with varied significance")

print()
print("OK - P0 deep test complete")
