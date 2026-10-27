"""
test_all_p2_middleware.py — 验证全部三个 P2 中间件在全链条中的表现
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

print('===== P2 中间件全链条验证 =====')
print()

# 1. 验证 seal 数量
seal_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', 'time_chain', 'seal_index.json')
seals = json.loads(open(seal_path, encoding='utf-8').read()) if os.path.exists(seal_path) else []
print(f'1. T5→T2 铸印: seal_index.json 当前 {len(seals)} 条')
learning_seals = [s for s in seals if 'learning' in s.get('scene_tag', '')]
print(f'   其中学习产物铸印: {len(learning_seals)} 条')

# 2. 验证 T2→T4 加权
from seal_to_gc_adapter import compute_seal_bonus, _load_seal_keywords
kw = _load_seal_keywords()
print(f'\n2. T2→T4 钢印加权: {len(kw)} 个主题关键词')

# 3. 验证 GC 分析中 T2→T4 环节
print(f'\n3. GC analyze_memory T2→T4 环节')
from memory_gc import MemoryGC
gc = MemoryGC()
analysis = gc.analyze_memory()
for item in analysis:
    section = item['section'][:50]
    score = item['score']
    action = item['action']
    print(f'   [{action:10s}] score={score:.3f}  {section}')

# 4. 验证 GC run_gc T4→T5 反馈记录
print(f'\n4. GC feedback (T4→T5):')
gc_feedback_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_gc_feedback.jsonl')
if os.path.exists(gc_feedback_path):
    feedbacks = [json.loads(l) for l in open(gc_feedback_path, encoding='utf-8') if l.strip()]
    print(f'   {len(feedbacks)} 条反馈记录')
    if feedbacks:
        latest = feedbacks[-1]
        print(f'   最新: mode={latest.get("mode")}, actions={latest.get("action_counts")}')
