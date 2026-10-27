"""demo_t3_panel.py — 生成测试数据供面板展示"""
import sys, os, time
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

import json
# 清空
for f in [r'C:\Users\qq366410837\.qclaw\workspace\memory\_task_dispatch.jsonl',
          r'C:\Users\qq366410837\.qclaw\workspace\memory\_task_index.json']:
    if os.path.exists(f): os.remove(f)

from task_dispatch_core import TaskScheduler, Task, TaskType
TaskScheduler._instance = None

s = TaskScheduler()

# 注册几个不同类型的任务
tasks = [
    Task(id='dream_01', type=TaskType.DREAM, trigger='cron', name='梦境期 07-06', priority=3),
    Task(id='seal_alert', type=TaskType.SYSTEM, trigger='chain', name='钢印告警: conflict#12', priority=9),
    Task(id='gc_v2', type=TaskType.METABOLIC, trigger='chain', name='GC 结果复核: 5降级', priority=6),
    Task(id='learn_01', type=TaskType.LEARNING, trigger='chain', name='学习产物: INTUITION', priority=7,
         payload={}, max_retries=2, retry_delay_ms=5000, consecutive_fails=1),
    Task(id='user_task', type=TaskType.USER, trigger='manual', name='用户手动任务', priority=10),
]

for t in tasks:
    s.register(t)
    s.enqueue(t.id)

# 记录一些结果
s.record_result('dream_01', {'duration_ms': 1200}, success=True)
s.record_result('seal_alert', {'duration_ms': 350}, success=True)
s.record_result('gc_v2', {'error': 'disk full'}, success=False)  # 将重试

now = time.time()
print(f'生成 {len(tasks)} 个测试任务')
print(f'当前时间: {time.strftime("%H:%M:%S")}')
print(f'参考命令: python t3_panel.py')
