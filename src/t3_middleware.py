# -*- coding: utf-8 -*-
"""
t3_middleware.py — T3 调度链中间件：T2/T4/T5 ↔ T3 双向桥接
日期: 2026-07-06
依赖: task_dispatch_core.py
"""

import sys, os
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')
os.environ['TU8_WORKSPACE'] = r'C:\Users\qq366410837\.qclaw\workspace'

from task_dispatch_core import get_scheduler
import logging

logger = logging.getLogger("tu8.t3_middleware")

# =============================================================================
# T2→T3: 钢印链 → 调度链
# =============================================================================

def on_seal_created(seal_id: str, scene_tag: str, summary: str = ''):
    """
    钩子：钢印铸造完成后调用。
    已在 learning_to_seal_adapter 中通过 learning_apply 间接调用。
    """
    scheduler = get_scheduler()
    task_id = scheduler.notify_seal_created(seal_id, scene_tag, summary)
    logger.info(f"[T2→T3] seal={seal_id} → task={task_id}")
    return task_id


# =============================================================================
# T4→T3: GC链 → 调度链
# =============================================================================

def on_gc_completed(stats: dict):
    """
    钩子：GC 执行完成后调用。
    注入到 memory_gc.run_gc() 末尾。
    """
    scheduler = get_scheduler()
    task_id = scheduler.notify_gc_completed(stats)
    logger.info(f"[T4→T3] GC completed → task={task_id}")
    return task_id


# =============================================================================
# T3→T4: 调度链 → GC链
# =============================================================================

def get_gc_advice() -> dict:
    """
    返回 GC 是否应该执行的建议。
    T3 调度器判断是否有高优先级任务正在运行。
    """
    scheduler = get_scheduler()
    ctx = scheduler.get_gc_context()
    return {
        'defer_gc': ctx['high_priority_running'],
        'reason': '高优先级任务运行中' if ctx['high_priority_running'] else '可执行GC',
        'pending_count': ctx['pending_count'],
    }


# =============================================================================
# T5→T3: 学习链 → 调度链
# =============================================================================

def on_learning_products_ready(products: list):
    """
    钩子：学习引擎产生候选后调用。
    注入到 learning_engine.py 的 Phase 5 之后。
    """
    scheduler = get_scheduler()
    task_ids = scheduler.notify_learning_ready(products)
    logger.info(f"[T5→T3] {len(task_ids)} tasks scheduled")
    return task_ids


# =============================================================================
# T3→T5: 调度链 → 学习链
# =============================================================================

def get_execution_stats_for_learning() -> dict:
    """
    返回执行统计数据供学习传感器使用。
    注入到 learning_collector.py 的 SENSOR_PATHS。
    """
    scheduler = get_scheduler()
    return scheduler.get_execution_stats()


# =============================================================================
# T3→T2: 调度链 → 钢印链（查询接口）
# =============================================================================

def get_seal_context(seal_id: str) -> dict:
    """
    为钢印提供调度上下文（相关任务、系统状态）。
    """
    scheduler = get_scheduler()
    return scheduler.get_context_for_seal(seal_id)


# =============================================================================
# T3 记忆注册：dream_check 任务登记
# =============================================================================

def ensure_dream_task(dream_id: int, name: str = None) -> str:
    """
    确保梦境期任务已登记到 T3 调度器。
    dream_check_cron.py 启动时调用：登记或取出现有任务。
    返回 task_id。
    """
    scheduler = get_scheduler()
    task_id = f'task_dream_{dream_id}'
    existing = scheduler.get_task(task_id)
    if not existing:
        from task_dispatch_core import Task, TaskType
        task = Task(
            id=task_id,
            type=TaskType.DREAM,
            trigger='cron',
            name=name or f'深睡梦境 #{dream_id}',
            payload={'dream_id': dream_id},
            priority=3,
        )
        return scheduler.register(task)
    return task_id


def record_dream_result(dream_id: int, stage: str, success: bool, detail: dict = None):
    """
    记录梦境期某一阶段的执行结果。
    dream_check_cron.py 每次阶段完成后调用。
    """
    scheduler = get_scheduler()
    task_id = f'task_dream_{dream_id}'
    existing = scheduler.get_task(task_id)
    if not existing:
        task_id = ensure_dream_task(dream_id)

    # 记录总任务结果
    detail = detail or {}
    detail['stage'] = stage
    scheduler.record_result(task_id, detail, success=success)
    logger.info(f"[T3] dream #{dream_id} stage={stage} success={success}")
