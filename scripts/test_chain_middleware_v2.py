"""
test_chain_middleware_v2.py — 干净测试P0/P1集成
"""
import sys, os, json

sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

print('=== Reset all progress ===')
from seal_to_learning_adapter import SealSensorAdapter
adapter = SealSensorAdapter()
adapter._save_progress(None)  # reset to read all seals

# Also reset learning offsets to read everything fresh
offset_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_learning_collector_offsets.json')
if os.path.exists(offset_path):
    os.remove(offset_path)
    print('Reset collector offsets')

# Clean learning pending
pending_path = os.path.join(os.environ['TU8_WORKSPACE'], 'memory', '_learning_pending.json')
if os.path.exists(pending_path):
    os.remove(pending_path)
    print('Reset pending store')

print()
print('=== Run learning engine ===')
from learning_engine import LearningEngine
engine = LearningEngine()
result = engine.run()
print(result.get('report', ''))
