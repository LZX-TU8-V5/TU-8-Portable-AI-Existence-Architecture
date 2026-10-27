#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 tu8_toolchain.py
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
sys.path.insert(0, '.')

from tu8_toolchain import TU8Toolchain, TaskContext

print('=' * 60)
print('TU-8 Toolchain 测试')
print('=' * 60)

tc = TU8Toolchain()

# 测试1：文件读取任务
print('\n[测试1] 文件读取任务')
ctx1 = TaskContext(
    task_id='test_001',
    description='读取 SOUL.md 文件',
    tags=['file_read', '读取'],
    params={'path': 'C:/Users/qq366410837/.openclaw/workspace/SOUL.md'}
)
result1 = tc.dispatch(ctx1)
print(f'  成功: {result1.success}')
print(f'  适配器: {result1.metadata.get("tool")}')
print(f'  参数: {result1.metadata.get("params")}')

# 测试2：Shell执行任务
print('\n[测试2] Shell执行任务')
ctx2 = TaskContext(
    task_id='test_002',
    description='执行 Python 版本检查',
    tags=['shell', 'exec'],
    params={'command': 'python --version'}
)
result2 = tc.dispatch(ctx2)
print(f'  成功: {result2.success}')
print(f'  适配器: {result2.metadata.get("tool")}')
print(f'  参数: {result2.metadata.get("params")}')

# 测试3：记忆检索任务
print('\n[测试3] 记忆检索任务')
ctx3 = TaskContext(
    task_id='test_003',
    description='检索 TU-8 规划器相关信息',
    tags=['memory', 'search'],
    params={'query': 'TU-8 规划器'}
)
result3 = tc.dispatch(ctx3)
print(f'  成功: {result3.success}')
print(f'  适配器: {result3.metadata.get("tool")}')
print(f'  参数: {result3.metadata.get("params")}')

# 测试4：标签匹配（无params，靠标签猜测）
print('\n[测试4] 标签匹配（无参数）')
ctx4 = TaskContext(
    task_id='test_004',
    description='读取某个文件',
    tags=['读取文件', 'file']
)
result4 = tc.dispatch(ctx4)
print(f'  成功: {result4.success}')
print(f'  适配器: {result4.metadata.get("tool") if result4.success else "匹配失败"}')

# 测试5：错误情况（缺少参数）
print('\n[测试5] 错误情况（缺少参数）')
ctx5 = TaskContext(
    task_id='test_005',
    description='读取文件',
    tags=['file_read'],
    params={}  # 缺少 path
)
result5 = tc.dispatch(ctx5)
print(f'  成功: {result5.success}')
print(f'  错误: {result5.error}')

# 执行日志
print('\n[执行日志]')
log = tc.get_execution_log()
for entry in log:
    status = '[OK]' if entry['success'] else '[X]'
    print(f'  {entry["timestamp"]} | {entry["task_id"]} | {entry["adapter"]} | {status}')

print('\n' + '=' * 60)
print('测试完成')
print('=' * 60)
