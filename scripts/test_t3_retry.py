"""test_t3_retry.py — T3 v1.2 重试策略验证（隔离版）"""
import sys, os, time
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

import json

# 清空测试数据
task_file = r'C:\Users\qq366410837\.qclaw\workspace\memory\_task_dispatch.jsonl'
for f in [task_file, r'C:\Users\qq366410837\.qclaw\workspace\memory\_task_index.json']:
    if os.path.exists(f):
        os.remove(f)

from task_dispatch_core import TaskScheduler, Task, TaskType, TaskStatus, get_scheduler

# 重置单例
TaskScheduler._instance = None
s = get_scheduler()

print('=== T3 v1.2 重试策略验证 ===')
print()

# 1. 注册任务
task = Task(id='retry_test', type=TaskType.LEARNING, trigger='chain',
            name='重试测试任务', priority=5, max_retries=3, retry_delay_ms=100)
s.register(task)
s.enqueue('retry_test')
print('[1] 注册: retry_test, max_retries=3, delay=100ms')

# 2. 失败#1 → pending + 退避
s.record_result('retry_test', {'error': 'timeout'}, success=False)
t = s.get_task('retry_test')
is_waiting = t.next_retry_at > time.time()
print(f'[2] 失败#1: status={t.status.value}, fails={t.consecutive_fails}')
print(f'    next_retry_at={t.next_retry_at:.0f} > now={time.time():.0f} = {is_waiting}')
assert t.status == TaskStatus.PENDING, f'预期 PENDING, 实际 {t.status}'
assert t.consecutive_fails == 1
assert is_waiting, 'next_retry_at 应该大于当前时间'

# 3. next() 应返回 None（退避中）
n = s.next()
n_str = n.id if n else "None"
print(f'[3] 退避中: next() = {n_str}')
assert n is None, f'退避期不应选中任务, 但返回了 {n.id}'

# 4. 等待退避（100ms）
time.sleep(0.15)

# 5. next() 应选中
n = s.next()
n_str = n.id if n else "None"
print(f'[4] 退避结束: next() = {n_str}')
assert n is not None, '退避结束应能出队'

# 6. 失败#2 → 指数退避 200ms
s.record_result('retry_test', {'error': 'again'}, success=False)
t = s.get_task('retry_test')
backoff_2 = t.next_retry_at - time.time()
print(f'[5] 失败#2: fails={t.consecutive_fails}, backoff={backoff_2:.2f}s (期望~0.2s)')
assert t.status == TaskStatus.PENDING, f'预期 PENDING, 实际 {t.status}'
assert t.consecutive_fails == 2
assert 0.15 < backoff_2 < 0.5, f'退避时间异常: {backoff_2}'

# 7. 失败#3 → 到上限，应 FAILED
time.sleep(0.25)
s.record_result('retry_test', {'error': 'third'}, success=False)
t = s.get_task('retry_test')
print(f'[6] 失败#3: fails={t.consecutive_fails}, status={t.status.value}')
assert t.status == TaskStatus.FAILED, f'预期 FAILED, 实际 {t.status}'
assert t.consecutive_fails == 3

print()
print('=== 重试策略全部通过 ===')
print('  失败#1 → pending (退避100ms)')
print('  失败#2 → pending (退避200ms, 指数增长)')
print('  失败#3 → FAILED (达3次上限)')
print('  next() 在退避期返回 None')

# 清理测试文件
os.remove(task_file)
print()
print('测试文件已清理')
