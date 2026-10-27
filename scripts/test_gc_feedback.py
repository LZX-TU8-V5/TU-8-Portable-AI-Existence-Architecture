"""
test_gc_feedback.py — 验证 T4→T5 GC 反馈闭环
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

print('=== 1. 模拟一次 GC 执行并记录反馈 ===')
from gc_to_learning_adapter import record_gc_result, get_feedback_history, summarize_patterns

mock_report = {
    "mode": "deep",
    "timestamp": "2026-07-05T22:00:00",
    "total_sections": 8,
    "actions": {"KEEP": 5, "DEGRADE": 2, "EVICT": 0, "WATCH": 1},
    "details": [
        {"section": "2026-07-01 千问对话", "score": 0.72, "action": "KEEP"},
        {"section": "2026-07-02 空间语言", "score": 0.65, "action": "KEEP"},
        {"section": "旧日志 6月", "score": 0.25, "action": "DEGRADE"},
        {"section": "旧实验数据", "score": 0.18, "action": "DEGRADE"},
        {"section": "2026-07-05 学习链", "score": 0.78, "action": "KEEP"},
        {"section": "2026-07-04 代谢", "score": 0.55, "action": "KEEP"},
        {"section": "2026-06-30 诊断", "score": 0.45, "action": "WATCH"},
        {"section": "2026-07-03 感知", "score": 0.60, "action": "KEEP"},
    ],
}

r = record_gc_result(mock_report)
print('GC feedback recorded:', json.dumps(r, ensure_ascii=False))

print()
print('=== 2. 验证 collector 能读到 ===')
from learning_collector import LearningCollector
collector = LearningCollector(dream_cycle_id=999)
data = collector.collect()
gc_key = 'gc_feedback'
gc_data = data.get(gc_key, [])
print('GC feedback records read:', len(gc_data))

print()
print('=== 3. 模式摘要 ===')
history = get_feedback_history(5)
patterns = summarize_patterns(history)
print(json.dumps(patterns, ensure_ascii=False, indent=2))
