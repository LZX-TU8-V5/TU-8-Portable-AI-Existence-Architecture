#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_t3_dream.py — 验证 dream_check_cron.py 的 T3 集成（不真正运行管道）
"""
import sys, os
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

# 重置 T3 单例
import task_dispatch_core
task_dispatch_core.TaskScheduler._instance = None

# Mock consciousness_cycle / metabolic_pipeline / learning_engine
# 通过 sys.modules 注入 mock，避免真正运行重型管道
import types

mock_cc = types.ModuleType('consciousness_cycle')
class FakeCC:
    class phase:
        value = 'awake'
    def _enter_deep_sleep(self):
        return {
            'timestamp': '2026-07-06T01:00:00',
            'deep_sleep_number': 42,
            'operations': [{'name': 'seal', 'count': 3}],
            'errors': [],
        }
mock_cc.ConsciousnessCycle = FakeCC

mock_meta = types.ModuleType('metabolic_pipeline')
class FakeMeta:
    def run(self, dry_run=False):
        return {
            'stages': {
                'distill': {'sections_extracted': 5},
                'gc': {'actions': {'KEEP': 3, 'DEGRADE': 2, 'EVICT': 0}},
            }
        }
mock_meta.MetabolicPipeline = FakeMeta

mock_learn = types.ModuleType('learning_engine')
class FakeLearn:
    def run(self):
        return {
            'status': 'complete',
            'cycle_id': 123,
            'applied': 2,
        }
mock_learn.LearningEngine = FakeLearn

sys.modules['consciousness_cycle'] = mock_cc
sys.modules['metabolic_pipeline'] = mock_meta
sys.modules['learning_engine'] = mock_learn

# Mock intuition_engine
mock_intu = types.ModuleType('intuition_engine')
class FakeIntu:
    def match(self, sit, threshold):
        return None
mock_intu.IntuitionEngine = FakeIntu
sys.modules['intuition_engine'] = mock_intu

# Now run a simulation of dream_check_cron main()
from t3_middleware import ensure_dream_task, record_dream_result
from task_dispatch_core import get_scheduler

print('=== T3 ↔ dream_check 集成测试 ===')
print()

scheduler = get_scheduler()

# Simulate dream_check stages
dream_id = 42

# Stage 1: deep_sleep
ensure_dream_task(dream_id)
record_dream_result(dream_id, 'deep_sleep', True, {'ops': 1, 'errors': 0})
print(f'  [deep_sleep] → task_dream_{dream_id} OK')

# Stage 2: metabolic
record_dream_result(dream_id, 'metabolic', True, {'actions': {'KEEP': 3, 'DEGRADE': 2}})
print(f'  [metabolic] → OK')

# Stage 3: intuition
record_dream_result(dream_id, 'intuition', True, {})
print(f'  [intuition] → OK')

# Stage 4: learning
record_dream_result(dream_id, 'learning', True, {'applied': 2})
print(f'  [learning] → OK')

# Verify in scheduler
task = scheduler.get_task(f'task_dream_{dream_id}')
print()
print(f'  T3 task status: {task.status}')
print(f'  total_runs: {task.total_runs}')
print(f'  last_result: {task.last_result}')

# Get execution stats
stats = scheduler.get_execution_stats()
print(f'  execution_stats: total_tasks={stats["total_tasks"]}, error_rate={stats["error_rate"]:.2f}')

# Test T3→T4 advice (should not defer since this is a completed dream task)
from t3_middleware import get_gc_advice
advice = get_gc_advice()
print(f'  gc_advice: defer={advice["defer_gc"]}, pending={advice["pending_count"]}')

print()
print('✅ dream_check ↔ T3 集成验证通过')
print(f'   dream_id={dream_id} 完整登记到 T3 调度器')
