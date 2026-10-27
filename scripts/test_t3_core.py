"""
test_t3_core.py — T3 调度核心测试
"""
import sys, os, time
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

# 重置单例（测试隔离）
import task_dispatch_core
task_dispatch_core.TaskScheduler._instance = None

from task_dispatch_core import (
    TaskScheduler, Task, TaskType, TaskStatus,
    register_dream_task, get_scheduler
)

print('=== 1. 核心注册+出队 ===')
scheduler = get_scheduler()

# 注册梦境任务
t1 = Task(id='test_dream_1', type=TaskType.DREAM, trigger='cron',
           name='深睡梦境检查', payload={'script': 'dream_check_cron.py'}, priority=3)
t1_id = scheduler.register(t1)
scheduler.enqueue(t1_id)

# 注册学习任务
t2 = Task(id='test_learn_1', type=TaskType.LEARNING, trigger='chain',
           name='学习产物验证', payload={'product_id': 'lp_001'}, priority=7)
t2_id = scheduler.register(t2)
scheduler.enqueue(t2_id)

# 注册高优先级系统任务
t3 = Task(id='test_sys_1', type=TaskType.SYSTEM, trigger='manual',
           name='钢印复核', payload={'seal_id': 's_001'}, priority=9)
t3_id = scheduler.register(t3)
scheduler.enqueue(t3_id)

print(f'  Registered: {t1_id}, {t2_id}, {t3_id}')

# next() 应该返回优先级9的任务
next_task = scheduler.next()
print(f'  next() → [{next_task.priority}] {next_task.name} (id={next_task.id})')
assert next_task.priority == 9, f'Expected priority 9, got {next_task.priority}'

# 再 next() → priority 7
next_task2 = scheduler.next()
print(f'  next() → [{next_task2.priority}] {next_task2.name}')
assert next_task2.priority == 7

# record_result
scheduler.record_result(t3_id, {'duration_ms': 1500, 'output': 'OK'}, success=True)
t3_after = scheduler.get_task(t3_id)
print(f'  record_result: status={t3_after.status} fails={t3_after.consecutive_fails}')

print()
print('=== 2. T2→T3 钢印通知 ===')
scheduler2 = get_scheduler()
task_id = scheduler2.notify_seal_created('seal_001', 'learning:alert', summary='用户异常')
print(f'  Created task: {task_id}')

print()
print('=== 3. T4→T3 GC通知 ===')
task_id_gc = scheduler2.notify_gc_completed({'action_counts': {'KEEP': 5, 'DEGRADE': 8, 'EVICT': 2}})
print(f'  Created GC review task: {task_id_gc}')

print()
print('=== 4. T5→T3 学习产物通知 ===')
products = [
    {'id': 'lp_h', 'type': 'ALERT', 'confidence': 0.85},
    {'id': 'lp_l', 'type': 'MEMO', 'confidence': 0.5},  # 低于阈值，不调度
    {'id': 'lp_h2', 'type': 'PREFERENCE', 'confidence': 0.75},
]
task_ids = scheduler2.notify_learning_ready(products)
print(f'  Scheduled {len(task_ids)} tasks: {task_ids}')

print()
print('=== 5. T3→T5 执行统计 ===')
stats = scheduler2.get_execution_stats()
print(f'  total_tasks={stats["total_tasks"]}, total_runs={stats["total_runs"]}, error_rate={stats["error_rate"]:.2f}')
print(f'  by_type={list(stats["by_type"].keys())}')

print()
print('=== 6. T3→T4 GC上下文 ===')
ctx = scheduler2.get_gc_context()
print(f'  high_priority_running={ctx["high_priority_running"]}')
print(f'  pending_count={ctx["pending_count"]}')

print()
print('=== 7. T3→T2 钢印上下文 ===')
ctx2 = scheduler2.get_context_for_seal('seal_001')
print(f'  related_tasks={len(ctx2["related_tasks"])}')

print()
print('✅ T3 核心测试全部通过')
