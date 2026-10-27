"""
test_middleware_p2.py — 验证 P2 中间件 T5→T2 和 T2→T4
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

print('=== T5→T2: 学习产物→铸印 ===')
from learning_to_seal_adapter import cast_learning_seal

# 铸印测试
products = [
    {'id': 'lp_alert_co2', 'type': 'ALERT', 'content': '用户检测到情绪低落',
     'confidence': 0.85, 'action': 'notify_creator', 'track': 'palace'},
    {'id': 'lp_intu_x1', 'type': 'INTUITION', 'content': '用户偏好极简确认回复',
     'confidence': 0.72, 'action': 'inject_intuition', 'track': 'palace'},
    {'id': 'lp_low_c3', 'type': 'MEMO', 'content': '不确定的猜测',
     'confidence': 0.45, 'action': 'append_memory', 'track': 'palace'},
]

for p in products:
    r = cast_learning_seal(p)
    print(f"  {p['id']} (conf={p['confidence']}): {json.dumps(r, ensure_ascii=False)}")

# 验证 seal_index.json
seal_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', 'time_chain', 'seal_index.json')
seals = json.loads(open(seal_path, encoding='utf-8').read()) if os.path.exists(seal_path) else []
print(f'\nTotal seals now: {len(seals)}')
for s in seals:
    if 'learning' in s.get('scene_tag', ''):
        print(f'  [{s["scene_tag"]}] {s["summary"][:40]}')

print()
print('=== T2→T4: 钢印→GC加权 ===')
from seal_to_gc_adapter import compute_seal_bonus, hook_metabolic_score

titles = [
    '2026-07-01 千问对话',
    '2026-07-05 学习链',
    '旧日志 6月',
    '2026-06-30 诊断',
    'AI 架构设计原理',
]

for t in titles:
    b = compute_seal_bonus(t, t)
    print(f"  '{t[:40]}': bonus={b:.3f}")
