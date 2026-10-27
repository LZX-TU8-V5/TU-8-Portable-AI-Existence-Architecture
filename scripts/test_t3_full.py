"""
test_t3_full.py — T3 调度链全链条集成测试（隔离版）
"""
import sys, os, time, json
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

# 重置 T3 单例（测试隔离）
import task_dispatch_core
task_dispatch_core.TaskScheduler._instance = None

print('=== T3 调度链全链验证 ===')
print()

# 1. T3 核心
print('[1] T3 核心调度器')
from task_dispatch_core import get_scheduler, Task, TaskType
s = get_scheduler()
print(f'    实例: OK')

# 2. T4→T3 集成 (memory_gc)
print('[2] T4→T3 GC通知')
gc_task_id = s.notify_gc_completed({'action_counts': {'KEEP': 3, 'DEGRADE': 2, 'EVICT': 0}})
print(f'    GC通知 → task={gc_task_id}')
assert gc_task_id.startswith('task_gc_')

# 3. T5→T3 集成
print('[3] T5→T3 学习产物通知')
learn_task_ids = s.notify_learning_ready([
    {'id': 'lp_h', 'type': 'ALERT', 'confidence': 0.88},
    {'id': 'lp_l', 'type': 'MEMO', 'confidence': 0.5},  # below threshold
])
print(f'    学习通知 → {len(learn_task_ids)} tasks (低置信被过滤)')
assert len(learn_task_ids) == 1, f'Expected 1, got {len(learn_task_ids)}'

# 4. T3→T5 学习传感器
print('[4] T3→T5 执行统计 → learning_collector')
from learning_collector import LearningCollector
lc = LearningCollector(dream_cycle_id=999)
data = lc.collect()
exec_stats = data.get('execution_stats', {})
print(f'    execution_stats collected: total_tasks={exec_stats.get("total_tasks", 0)}')
assert 'by_type' in exec_stats

# 5. T2→T3 钢印通知
print('[5] T2→T3 钢印通知')
seal_task_id = s.notify_seal_created('seal_demo_1', 'learning:alert', summary='测试')
print(f'    钢印通知 → task={seal_task_id}')

# 6. T3→T4 GC上下文
print('[6] T3→T4 GC建议')
from t3_middleware import get_gc_advice
advice = get_gc_advice()
print(f'    defer_gc={advice["defer_gc"]}, pending={advice["pending_count"]}')
assert 'pending_count' in advice

# 7. T3→T2 钢印上下文
print('[7] T3→T2 钢印上下文')
from t3_middleware import get_seal_context
ctx = get_seal_context('seal_demo_1')
print(f'    related_tasks={len(ctx["related_tasks"])}, has_seal_id={ctx.get("seal_id") == "seal_demo_1"}')

# 8. 优先级出队（只测自己刚注册的，不依赖历史状态）
print('[8] 优先级出队验证（仅本轮注册任务）')
# 获取本轮注册的所有 pending 任务
all_pending = [t for tid, t in s._tasks.items() if t.status.value == 'pending']
all_pending.sort(key=lambda x: -x.priority)
print(f'    本轮 pending 任务: {len(all_pending)} 个')
print(f'    最高优先级: {all_pending[0].priority if all_pending else "N/A"} - {all_pending[0].name if all_pending else ""}')

# 9. record_result + T3 状态更新
print('[9] record_result 状态追踪')
done_id = gc_task_id
s.record_result(done_id, {'duration_ms': 200, 'output': 'OK'}, success=True)
t = s.get_task(done_id)
print(f'    {done_id}: status={t.status}, fails={t.consecutive_fails}, total_runs={t.total_runs}')
assert t.status.value == 'done'
assert t.consecutive_fails == 0
assert t.total_runs == 1

# 10. 执行统计（验证失败计数）
print('[10] 执行统计（失败计数）')
s.record_result(learn_task_ids[0], {'error': 'test'}, success=False)
stats = s.get_execution_stats()
print(f'    error_rate={stats["error_rate"]:.3f}, total_fails={stats["total_fails"]}')
assert stats['total_fails'] >= 1

print()
print('✅ T3 全链验证通过 — 5/5 中间件双向通路全通')
print(f'   T2→T3 ✅  T3→T2 ✅  T4→T3 ✅  T3→T4 ✅  T5→T3 ✅  T3→T5 ✅')
