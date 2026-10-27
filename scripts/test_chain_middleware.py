"""
test_chain_middleware.py — 测试P0/P1中间件集成
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

print('=== T1→T5: Seal Adapter ===')
from seal_to_learning_adapter import SealSensorAdapter
adapter = SealSensorAdapter()
print('Seal status:', json.dumps(adapter.summary(), ensure_ascii=False))
records = adapter.build_records()
print(f'New seal records: {len(records)}')

print()
print('=== T5→T4: Learning→GC Adapter ===')
from learning_to_gc_adapter import register_product, unregister_product, get_protected

r1 = register_product('测试保护段', 'prod_001', 'MEMO')
print('Register:', json.dumps(r1, ensure_ascii=False))

r2 = register_product('测试保护段', 'prod_001', 'MEMO')
print('Duplicate:', json.dumps(r2, ensure_ascii=False))

data = get_protected()
sec_count = len(data['sections'])
print(f'Protected count: {sec_count}')

r3 = unregister_product('测试保护段')
print('Unregister:', json.dumps(r3, ensure_ascii=False))

print()
print('=== Full pipeline with middlewares ===')
from learning_engine import LearningEngine
engine = LearningEngine()
result = engine.run()
print(result.get('report', ''))

summ = result.get('summary', {})
print(f'Seal in summary: {summ}')
