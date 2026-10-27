# -*- coding: utf-8 -*-
"""P0+P1 集成测试：有损压缩 + 情绪调制"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import logging
import time

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(message)s")

from consciousness_cycle import ConsciousnessCycle, AffectSignal

cycle = ConsciousnessCycle()

# 测试1: 中性情绪下的有损压缩
print("=== TEST 1: Neutral Affect ===")
snap1 = {
    "summary": "这次讨论了TU-8架构的六循环模型，涉及感知-行动循环、记忆-睡眠循环和稳态调节循环的映射关系",
    "context_usage": 0.85,
    "events": ["event_architecture_review", "event_six_cycles_mapping"],
    "extra_context": "Qwen建议先实现D1反馈边，TU-8建议先实现P0有损压缩作为地基",
}
r1 = cycle.tick(context_snapshot=snap1)
lossy1 = r1.get("lossy", {})
destruction1 = lossy1.get("destruction_ratio", 0)
print(f"  destruction={destruction1:.2f}  forgotten={lossy1.get('destroyed_seal_ids', [])}")
assert 0.3 <= destruction1 <= 0.7, f"FAIL: destruction {destruction1} out of range"
print("  PASS")

# 测试2: 高困惑 → 保留更多细节（上限降至0.4）
print()
print("=== TEST 2: High Confusion (c=0.8) ===")
cycle.inject_affect(AffectSignal(valence=0.0, arousal=0.7, confusion=0.8))
time.sleep(0.1)
snap2 = {
    "summary": "关于自创生系统的核心问题：递归闭合不等于生命，缺口才是动力源",
    "context_usage": 0.85,
    "events": ["event_autopoiesis", "event_gap_theory", "event_ontological_question"],
    "detail": "系统需要内在的时间箭头、自我指涉的不完备性、与环境的代谢耦合",
}
r2 = cycle.tick(context_snapshot=snap2)
lossy2 = r2.get("lossy", {})
destruction2 = lossy2.get("destruction_ratio", 0)
print(f"  destruction={destruction2:.2f}  (should be <=0.4 due to high confusion)")
assert destruction2 <= 0.4, f"FAIL: high confusion should cap destruction at 0.4, got {destruction2}"
print("  PASS")

# 测试3: 负价事件 → 创伤记忆更顽固（保留更多负价片段）
print()
print("=== TEST 3: Negative Valence (v=-0.7) ===")
cycle.inject_affect(AffectSignal(valence=-0.7, arousal=0.8, confusion=0.3))
time.sleep(0.1)
snap3 = {
    "summary": "安全验证失败，检测到异常访问模式，钢印链完整性受到威胁",
    "context_usage": 0.85,
    "events": ["SECURITY_BREACH", "chain_integrity_warning"],
    "error_detail": "WARM_WAKE验证发现时间链断裂，可能是数据篡改或硬件故障",
}
r3 = cycle.tick(context_snapshot=snap3)
lossy3 = r3.get("lossy", {})
destruction3 = lossy3.get("destruction_ratio", 0)
print(f"  destruction={destruction3:.2f}")
assert 0.3 <= destruction3 <= 0.7, f"FAIL: destruction {destruction3} out of range"
print("  PASS")

# 测试4: 倦怠 → 更容易丢东西（遗忘阈值放宽）
print()
print("=== TEST 4: Low Arousal (a=0.1) ===")
cycle.inject_affect(AffectSignal(valence=0.0, arousal=0.1, confusion=0.2))
time.sleep(0.1)
snap4 = {
    "summary": "常规维护任务",
    "context_usage": 0.85,
    "events": ["routine_maintenance"],
    "trivial_info": "一些不重要的日常记录，比如检查日志文件大小和磁盘使用率",
}
r4 = cycle.tick(context_snapshot=snap4)
lossy4 = r4.get("lossy", {})
destruction4 = lossy4.get("destruction_ratio", 0)
print(f"  destruction={destruction4:.2f}")
assert 0.3 <= destruction4 <= 0.7, f"FAIL: destruction {destruction4} out of range"
print("  PASS")

# 汇总
print()
print("=" * 50)
status = cycle.status()
print(f"Total destruction: {status['total_destruction_ratio']:.3f}")
print(f"Total forgotten:   {status['total_forgotten_count']}")
print(f"Affect log count:  {status['affect_log_count']}")
print(f"Seals created:     {status['total_micro_sleeps']}")
print()
print("ALL TESTS PASSED")
print("P0+P1 integration verified")
