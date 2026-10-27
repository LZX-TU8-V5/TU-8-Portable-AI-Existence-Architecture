#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
t3_panel.py — T3 调度链执行面板

用法:
  python t3_panel.py          完整面板
  python t3_panel.py --brief  精简版
  python t3_panel.py --json   JSON 输出（供其他程序读取）
  python t3_panel.py --id <task_id>  查看单个任务详情
"""

import sys, os, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path.home() / ".qclaw" / "workspace" / "src"))
os.environ.setdefault('TU8_WORKSPACE', str(Path.home() / ".qclaw" / "workspace"))

from task_dispatch_core import get_scheduler, Task, TaskStatus, TaskType

def _fmt_ts(ts: float) -> str:
    if not ts:
        return '—'
    return datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S')

def _fmt_dur(ms: float) -> str:
    if not ms:
        return '—'
    if ms < 1000:
        return f'{ms:.0f}ms'
    return f'{ms/1000:.1f}s'

def _status_icon(status: TaskStatus) -> str:
    return {
        TaskStatus.PENDING: '⏳',
        TaskStatus.RUNNING: '▶️',
        TaskStatus.DONE: '✅',
        TaskStatus.FAILED: '❌',
        TaskStatus.CANCELLED: '⛔',
    }.get(status, '❓')

def _type_icon(ttype) -> str:
    t = ttype.value if isinstance(ttype, TaskType) else ttype
    return {
        'dream': '💤',
        'user': '👤',
        'system': '⚙️',
        'learning': '🧠',
        'metabolic': '♻️',
    }.get(t, '📦')


def show_panel(brief=False):
    s = get_scheduler()
    tasks = list(s._tasks.values())
    stats = s.get_execution_stats()

    print('╔══════════════════════════════════════════╗')
    print('║        T3 调度链执行面板 v1.2            ║')
    print('╚══════════════════════════════════════════╝')
    print()

    # ─── 概览
    pending_cnt = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    running_cnt = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
    done_cnt = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    failed_cnt = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    # 退避中的重试
    now = time.time()
    retry_waiting = sum(1 for t in tasks
                        if t.status == TaskStatus.PENDING
                        and t.next_retry_at > now)

    print(f'  📊 总任务: {len(tasks):4d}')
    print(f'     ⏳ 等待: {pending_cnt:4d}   (其中退避中: {retry_waiting})')
    print(f'     ▶️ 运行: {running_cnt:4d}')
    print(f'     ✅ 完成: {done_cnt:4d}')
    print(f'     ❌ 失败: {failed_cnt:4d}  (含重试超限)')
    print()

    # ─── 执行统计
    print('  ── 执行统计 ──')
    for t_type, info in sorted(stats.get('by_type', {}).items(), key=lambda x: -x[1]['count']):
        icon = _type_icon(t_type)
        retries = info.get('retries', 0)
        print(f'    {icon} {t_type:10s}  total={info["count"]:3d}'
              f'  fail={info["fails"]:2d} ({info["error_rate"]*100:.0f}%)'
              f'  avg_dur={_fmt_dur(info["avg_duration_ms"])}'
              f'  retries={retries}')
    print()

    # ─── 等待队列（按优先级排列）
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    pending.sort(key=lambda t: (-t.priority, t.created_at))

    if pending and not brief:
        print('  ── 等待队列 ──')
        print(f'  {"PRI":>3s}  {"ID":>30s}  {"NAME":<20s}  {"AGE":>8s}  {"RETRY":>8s}')
        print(f'  {"─"*3}  {"─"*30}  {"─"*20}  {"─"*8}  {"─"*8}')
        for t in pending[:20]:
            age = int(time.time() - t.created_at)
            age_str = f'{age//3600}h{(age%3600)//60}m' if age > 60 else f'{age}s'
            retry_str = ''
            if t.consecutive_fails > 0:
                rm = max(0, int(t.next_retry_at - time.time()))
                retry_str = f'{rm//60}m{rm%60}s'
            print(f'  {t.priority:3d}  {t.id[:30]:>30s}  {t.name[:20]:<20s}  {age_str:>8s}  {retry_str:>8s}')
        if len(pending) > 20:
            print(f'  ... 还有 {len(pending)-20} 个')

    # ─── 最近失败
    failed = [t for t in tasks if t.status == TaskStatus.FAILED]
    failed.sort(key=lambda t: -t.last_run_at)

    if failed and not brief:
        print()
        print('  ── 最近失败 ──')
        for t in failed[:10]:
            fail_time = _fmt_ts(t.last_run_at)
            print(f'    ❌ {t.id[:35]:>35s}  fails={t.consecutive_fails}/{t.max_retries}  上次={fail_time}')
            err = t.last_result.get('error', '')
            if err:
                print(f'       error: {err[:100]}')

    # ─── 正在运行
    running = [t for t in tasks if t.status == TaskStatus.RUNNING]
    if running:
        print()
        print('  ── 运行中 ──')
        for t in running:
            dur = int(time.time() - t.last_run_at)
            print(f'    ▶️ {t.id[:35]:>35s}  {dur}s')

    print()
    stats_time = _fmt_ts(stats.get('updated_at', 0))
    print(f'  📎 更新时间: {stats_time}')


def show_task(task_id: str):
    s = get_scheduler()
    t = s.get_task(task_id)
    if not t:
        print(f'❌ 任务 {task_id} 未找到')
        return

    print(f'=== 任务详情: {t.id} ===')
    print(f'  name:        {t.name}')
    print(f'  type:        {_type_icon(t.type)} {t.type.value}')
    print(f'  trigger:     {t.trigger}')
    print(f'  status:      {_status_icon(t.status)} {t.status.value}')
    print(f'  priority:    {t.priority}')
    print(f'  created:     {_fmt_ts(t.created_at)}')
    print(f'  last_run:    {_fmt_ts(t.last_run_at)}')
    print(f'  runs:        {t.total_runs}')
    print(f'  fails:       {t.consecutive_fails}')
    print(f'  max_retries: {t.max_retries}')
    print(f'  retry_delay: {t.retry_delay_ms}ms')
    if t.next_retry_at > 0:
        rm = max(0, int(t.next_retry_at - time.time()))
        print(f'  next_retry:  {_fmt_ts(t.next_retry_at)} (还剩 {rm//60}m{rm%60}s)')
    if t.last_result:
        print(f'  last_result: {json.dumps(t.last_result, ensure_ascii=False)[:200]}')
    if t.payload:
        print(f'  payload:     {json.dumps(t.payload, ensure_ascii=False)[:200]}')


def show_json():
    s = get_scheduler()
    tasks = list(s._tasks.values())
    stats = s.get_execution_stats()

    data = {
        'stats': stats,
        'tasks': [{
            'id': t.id,
            'type': t.type.value if isinstance(t.type, TaskType) else t.type,
            'trigger': t.trigger,
            'name': t.name,
            'status': t.status.value if isinstance(t.status, TaskStatus) else t.status,
            'priority': t.priority,
            'created_at': t.created_at,
            'last_run_at': t.last_run_at,
            'total_runs': t.total_runs,
            'consecutive_fails': t.consecutive_fails,
            'max_retries': t.max_retries,
            'next_retry_at': t.next_retry_at,
            'last_result': t.last_result,
        } for t in tasks],
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import time

    args = sys.argv[1:]

    if '--json' in args:
        show_json()
    elif '--id' in args:
        idx = args.index('--id')
        if idx + 1 < len(args):
            show_task(args[idx + 1])
        else:
            print('缺少 task_id')
    else:
        brief = '--brief' in args
        show_panel(brief=brief)
