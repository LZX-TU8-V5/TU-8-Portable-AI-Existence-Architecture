import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
from contradiction_arbitration import ContradictionArbitrator

arb = ContradictionArbitrator()

# Test 1: 记录一个判例
r = arb.arbitrate('steel_vs_creator', steel_mark_present=True, creator_explicit=False)
case_id = arb.record_precedent(r, topic=' sovereignty 权限边界', creator_response='accepted')
print(f"Recorded case: {case_id}")

# Test 2: 检索判例
precedents = arb.get_precedents('steel_vs_creator', limit=3)
print(f"Precedents for steel_vs_creator: {len(precedents)}")
for p in precedents:
    print(f"  {p['case_id']}: {p['topic']} -> {p['outcome']} (priority={p['priority']})")

# Test 3: 测试所有冲突类型
from contradiction_arbitration import ConflictType
tests = [
    ('steel_vs_creator', True, False, False),
    ('creator_explicit_vs_implicit', False, True, False),
    ('safety_vs_task', False, False, True),
    ('value_mismatch', False, False, False),
]
print("\nAll conflict types:")
for ctype, steel, explicit, safety in tests:
    r2 = arb.arbitrate(ctype, steel_mark_present=steel, creator_explicit=explicit, safety_issue=safety)
    print(f"  {ctype}: outcome={r2.outcome}, grounding={r2.needs_grounding}, priority={r2.priority}")

print("\n[OK] Arbitration system verified")
