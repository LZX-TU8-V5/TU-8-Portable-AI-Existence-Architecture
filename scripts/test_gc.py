import sys
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
from memory_gc import MemoryGC

gc = MemoryGC()
print("=== Token Budget ===")
budget = gc.token_budget_status()
for k, v in budget.items():
    print("  %s: %s" % (k, v))

print()
print("=== 代谢分析（全量）===")
analysis = gc.analyze_memory()
for item in analysis:
    action = item['action']
    score = item['score']
    title = item['section']
    count = item['access_count']
    print("  [%s] %-40s score=%.3f  count=%d" % (action, title[:40], score, count))

print()
print("=== 推荐动作统计 ===")
actions = {}
for item in analysis:
    a = item['action']
    actions[a] = actions.get(a, 0) + 1
for a, cnt in actions.items():
    print("  %s: %d 段" % (a, cnt))
