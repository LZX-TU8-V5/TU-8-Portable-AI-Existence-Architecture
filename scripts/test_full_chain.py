"""
test_full_chain.py — 验证三条中间件串联的全链条
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

# Reset progress
from seal_to_learning_adapter import SealSensorAdapter
adapter = SealSensorAdapter()
adapter._save_progress(None)
print('Seal adapter: reset')

offset_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_learning_collector_offsets.json')
if os.path.exists(offset_path):
    os.remove(offset_path)
    print('Collector offsets: cleared')

pending_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_learning_pending.json')
if os.path.exists(pending_path):
    os.remove(pending_path)
    print('Pending store: cleared')

print()
print('=== Full chain run ===')
from learning_engine import LearningEngine
engine = LearningEngine()
result = engine.run()
print(result.get('report', ''))

# Verify GC feedback was available to Phase 1
collector = result.get('_collector')
if collector:
    summ = collector.sensor_data
    print()
    print('Sensor breakdown:')
    for key, val in summ.items():
        if key.startswith('_'):
            continue
        count = len(val) if isinstance(val, list) else (1 if val else 0)
        print(f'  {key}: {count}')

print()
print('Protected list:')
prot_file = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_learning_protected.json')
if os.path.exists(prot_file):
    prot = json.loads(open(prot_file, encoding='utf-8').read())
    print(f'  sections: {prot.get("sections", [])}')
