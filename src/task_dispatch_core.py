# -*- coding: utf-8 -*-
"""
task_dispatch_core.py — T3 调度链核心 v1.0
日期: 2026-07-06
功能: 统一任务队列、执行状态跟踪、T2/T4/T5 双向接口

核心理念:
  T3 = 任务编排与执行管理
  不替代 cron，而是 cron 任务与主动任务的统一调度总线

T2/T4/T5 中间件通过本模块对接。
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger("tu8.dispatch")

# =============================================================================
# 路径配置
# =============================================================================
WORKSPACE = Path(os.environ.get('TU8_WORKSPACE', r'C:\Users\qq366410837\.qclaw\workspace'))
TASK_DB = WORKSPACE / 'memory' / '_task_dispatch.jsonl'
TASK_INDEX = WORKSPACE / 'memory' / '_task_index.json'

# =============================================================================
# 任务类型与状态
# =============================================================================

class TaskType(str, Enum):
    DREAM = 'dream'          # 梦境期任务
    USER = 'user'            # 用户触发任务
    SYSTEM = 'system'        # 系统任务（异常告警等）
    LEARNING = 'learning'    # 学习链任务
    METABOLIC = 'metabolic'  # GC 代谢任务


class TaskStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


# =============================================================================
# 任务数据模型
# =============================================================================

@dataclass
class Task:
    id: str
    type: TaskType
    trigger: str          # 'cron' | 'manual' | 'event' | 'chain'
    name: str             # 可读名称
    payload: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5     # 1-10
    created_at: float = 0.0
    last_run_at: float = 0.0
    last_result: dict = field(default_factory=dict)
    consecutive_fails: int = 0
    total_runs: int = 0
    # v1.2: 重试策略
    max_retries: int = 3
    retry_delay_ms: int = 60000  # 初始重试间隔
    next_retry_at: float = 0.0   # unix ts，在此之前不选中

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        # 确保枚举序列化为字符串（from_dict 后也调用）
        if isinstance(self.type, str):
            try:
                self.type = TaskType(self.type)
            except ValueError:
                self.type = TaskType.SYSTEM
        if isinstance(self.status, str):
            try:
                self.status = TaskStatus(self.status)
            except ValueError:
                self.status = TaskStatus.PENDING

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'Task':
        # 反序列化时还原枚举
        if 'type' in d and isinstance(d['type'], str):
            try:
                d['type'] = TaskType(d['type'])
            except ValueError:
                d['type'] = TaskType.SYSTEM
        if 'status' in d and isinstance(d['status'], str):
            try:
                d['status'] = TaskStatus(d['status'])
            except ValueError:
                d['status'] = TaskStatus.PENDING
        return cls(**d)


# =============================================================================
# TaskScheduler — T3 核心调度器
# =============================================================================

class TaskScheduler:
    """
    T3 调度链核心。

    使用 JSONL 文件持久化，每个任务一行。
    内存中维护 task_index（id → 行号），避免全量扫描。

    主要接口：
      register()      登记任务
      enqueue()       加入执行队列
      next()          取最高优先级任务
      record_result() 记录执行结果
      get_status()    查询状态
      get_execution_stats() 返回执行统计

    T3 中间件接口：
      notify_seal_created()   T2→T3
      notify_gc_completed()   T4→T3
      notify_learning_ready() T5→T3
      get_context_for_seal() T3→T2
      get_execution_stats()   T3→T5
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        # 单例模式，确保全局唯一调度器实例
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, workspace: Optional[Path] = None):
        if self._initialized:
            return
        self.workspace = workspace or WORKSPACE
        self.tasks_file = self.workspace / 'memory' / '_task_dispatch.jsonl'
        self.index_file = self.workspace / 'memory' / '_task_index.json'
        self._ensure_dirs()
        self._load_index()
        self._initialized = True
        logger.info(f"[T3] TaskScheduler initialized, {len(self._index)} tasks loaded")

    # ------------------------------------------------------------------ #
    #  基础设施
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self):
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """加载任务索引（id → 行号映射）"""
        self._index: dict[str, int] = {}  # task_id → line_number
        self._tasks: dict[str, Task] = {}  # task_id → Task (内存缓存)
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding='utf-8'))
                self._index = data.get('index', {})
            except (json.JSONDecodeError, OSError):
                self._index = {}
        # 内存中缓存所有 pending/running 任务
        if self.tasks_file.exists():
            for line in self.tasks_file.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    task = Task.from_dict(d)
                    self._tasks[task.id] = task
                except Exception:
                    pass

    def _save_index(self):
        """持久化索引"""
        self.index_file.write_text(
            json.dumps({'index': self._index}, ensure_ascii=False),
            encoding='utf-8'
        )

    def _get_line_number(self, task_id: str) -> int:
        """从索引获取任务所在行号"""
        return self._index.get(task_id, -1)

    # ------------------------------------------------------------------ #
    #  核心接口
    # ------------------------------------------------------------------ #

    def register(self, task: Task) -> str:
        """
        登记新任务。
        如果 task_id 重复，自动追加时间戳后缀。
        """
        # 确保唯一 ID
        base_id = task.id
        counter = 1
        while task.id in self._index:
            task.id = f"{base_id}_{int(time.time())}_{counter}"
            counter += 1

        self._index[task.id] = None  # 行号待分配
        self._tasks[task.id] = task
        line_num = self._append_task(task)
        self._index[task.id] = line_num
        self._save_index()
        logger.info(f"[T3] Registered: {task.id} ({task.type}) priority={task.priority}")
        return task.id

    def enqueue(self, task_id: str, priority: int = None) -> bool:
        """
        将任务状态改为 pending（加入执行队列）。
        可选调整优先级。
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"[T3] enqueue: task {task_id} not found")
            return False
        if priority is not None:
            task.priority = max(1, min(10, priority))
        task.status = TaskStatus.PENDING
        task.created_at = time.time()
        self._update_task(task)
        logger.info(f"[T3] Enqueued: {task_id} priority={task.priority}")
        return True

    def next(self) -> Optional[Task]:
        """
        取最高优先级的 pending 任务。
        v1.2: 跳过仍在退避期的重试任务（next_retry_at > now）。
        返回 None 表示队列为空。
        """
        now = time.time()
        pending = [
            t for tid, t in self._tasks.items()
            if t.status == TaskStatus.PENDING
            and (t.next_retry_at <= 0.0 or t.next_retry_at <= now)
        ]
        if not pending:
            return None
        # 最高优先级 → 最老创建时间（FIFO tie-break）
        pending.sort(key=lambda t: (-t.priority, t.created_at))
        chosen = pending[0]
        chosen.status = TaskStatus.RUNNING
        chosen.last_run_at = time.time()
        self._update_task(chosen)
        logger.info(f"[T3] Dispatching: {chosen.id} ({chosen.name})")
        return chosen

    def record_result(
        self,
        task_id: str,
        result: dict,
        success: bool = True
    ) -> bool:
        """
        记录任务执行结果。
        由执行方（cron callback / 脚本）调用。
        v1.2: 失败时自动指数退避重试。
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"[T3] record_result: task {task_id} not found")
            return False

        task.last_result = result
        task.last_run_at = time.time()
        task.total_runs += 1

        if success:
            task.status = TaskStatus.DONE
            task.consecutive_fails = 0
            task.next_retry_at = 0.0
            logger.info(f"[T3] Completed: {task_id} success")
        else:
            task.consecutive_fails += 1
            if task.consecutive_fails >= task.max_retries:
                task.status = TaskStatus.FAILED
                logger.warning(f"[T3] Failed: {task_id} fail #{task.consecutive_fails}/{task.max_retries} — 达上限")
            else:
                # 指数退避: delay_ms * 2^(fails-1)
                backoff_ms = task.retry_delay_ms * (2 ** (task.consecutive_fails - 1))
                task.next_retry_at = time.time() + (backoff_ms / 1000.0)
                task.status = TaskStatus.PENDING
                logger.info(f"[T3] Retry: {task_id} #{task.consecutive_fails}/{task.max_retries} "
                            f"backoff={backoff_ms}ms 下次≥{task.next_retry_at:.0f}")

        self._update_task(task)
        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """根据 ID 查询任务"""
        return self._tasks.get(task_id)

    def get_execution_stats(self) -> dict:
        """
        返回执行统计数据，供 T5 学习链使用。
        v1.2: 增加重试统计。
        """
        tasks = list(self._tasks.values())
        if not tasks:
            return {'total': 0, 'avg_duration_ms': 0, 'error_rate': 0, 'by_type': {}}

        now = time.time()
        by_type = {}
        retry_pending = 0  # 处于退避期的重试任务
        retry_total = 0    # 有重试历史的任务数
        for t in tasks:
            t_type = t.type.value if isinstance(t.type, TaskType) else t.type
            if t_type not in by_type:
                by_type[t_type] = {'count': 0, 'fails': 0, 'durations': [], 'retries': 0}
            by_type[t_type]['count'] += 1
            if t.consecutive_fails > 0:
                by_type[t_type]['fails'] += 1
                by_type[t_type]['retries'] += t.consecutive_fails
            if t.consecutive_fails > 0 and t.status == TaskStatus.PENDING:
                retry_pending += 1
            if t.consecutive_fails > 0:
                retry_total += 1

            dur = t.last_result.get('duration_ms', 0)
            if dur:
                by_type[t_type]['durations'].append(dur)

        total_runs = sum(v['count'] for v in by_type.values())
        total_fails = sum(v['fails'] for v in by_type.values())
        all_durations = [d for v in by_type.values() for d in v['durations']]

        return {
            'total_tasks': len(tasks),
            'total_runs': total_runs,
            'total_fails': total_fails,
            'error_rate': total_fails / max(total_runs, 1),
            'avg_duration_ms': sum(all_durations) / max(len(all_durations), 1),
            'retry_pending': retry_pending,       # v1.2
            'retry_total': retry_total,            # v1.2
            'by_type': {
                k: {
                    'count': v['count'],
                    'fails': v['fails'],
                    'retries': v['retries'],
                    'error_rate': v['fails'] / max(v['count'], 1),
                    'avg_duration_ms': sum(v['durations']) / max(len(v['durations']), 1) if v['durations'] else 0,
                }
                for k, v in by_type.items()
            },
            'updated_at': time.time(),
        }

    # ------------------------------------------------------------------ #
    #  T3 中间件接口（供 adapter 调用）
    # ------------------------------------------------------------------ #

    def notify_seal_created(self, seal_id: str, scene_tag: str, summary: str = '') -> str:
        """
        T2→T3: 钢印铸造后通知调度器。
        自动创建关联的"钢印回顾"任务，优先级根据场景标签决定。
        """
        priority_map = {
            'alert': 8,
            'conflict': 9,
            'error': 9,
            'intuition': 6,
            'preference': 5,
            'memo': 4,
            'learning': 6,
        }
        scene_key = scene_tag.split(':')[0] if ':' in scene_tag else scene_tag
        priority = priority_map.get(scene_key, 5)

        task = Task(
            id=f'task_seal_{seal_id}',
            type=TaskType.SYSTEM,
            trigger='chain',
            name=f'钢印回顾: {scene_tag}',
            payload={'seal_id': seal_id, 'scene_tag': scene_tag, 'summary': summary},
            priority=priority,
        )
        task_id = self.register(task)
        self.enqueue(task_id, priority=priority)
        logger.info(f"[T3] Seal notify: created task {task_id} priority={priority}")
        return task_id

    def notify_gc_completed(self, stats: dict) -> str:
        """
        T4→T3: GC 执行完成后通知。
        创建"GC 结果复核"任务（低优先级，非紧急）。
        """
        actions = stats.get('action_counts', {})
        degraded = actions.get('DEGRADE', 0)
        evicted = actions.get('EVICT', 0)

        # 如果 GC 淘汰过多，提高复核优先级
        priority = 5 + min(3, degraded // 5)  # 每5个降级 +1 优先级，最高8

        task = Task(
            id=f'task_gc_{int(time.time())}',
            type=TaskType.METABOLIC,
            trigger='chain',
            name=f'GC 结果复核: DEGRADE={degraded} EVICT={evicted}',
            payload={'gc_stats': stats},
            priority=priority,
        )
        task_id = self.register(task)
        self.enqueue(task_id)
        logger.info(f"[T3] GC notify: created task {task_id} priority={priority}")
        return task_id

    def notify_learning_ready(self, products: list) -> list[str]:
        """
        T5→T3: 学习产物就绪，调度验证任务。
        为每个高置信产物创建验证任务。
        """
        task_ids = []
        for p in products:
            conf = p.get('confidence', 0)
            if conf < 0.7:
                continue  # 低置信不调度
            priority = 5 + int((conf - 0.7) * 20)  # 0.7→7, 0.9→9

            task = Task(
                id=f"task_learn_{p.get('id', 'unk')}_{int(time.time())}",
                type=TaskType.LEARNING,
                trigger='chain',
                name=f'学习产物验证: {p.get("type","?")}',
                payload={'product': p},
                priority=min(priority, 8),
            )
            tid = self.register(task)
            self.enqueue(tid)
            task_ids.append(tid)

        logger.info(f"[T3] Learning notify: {len(task_ids)} tasks enqueued")
        return task_ids

    def get_context_for_seal(self, seal_id: str) -> dict:
        """
        T3→T2: 为钢印链提供调度上下文。
        返回与该钢印相关的待办任务和执行历史。
        """
        # 找关联任务
        related = [
            t.to_dict() for tid, t in self._tasks.items()
            if 'seal_id' in t.payload and t.payload.get('seal_id') == seal_id
        ]
        stats = self.get_execution_stats()
        return {
            'seal_id': seal_id,
            'related_tasks': related,
            'system_stats': stats,
        }

    def get_gc_context(self) -> dict:
        """
        T3→T4: 为 GC 提供调度上下文。
        返回当前是否有高优先级任务在执行（可能需要避开 GC）。
        """
        running = [t for tid, t in self._tasks.items() if t.status == TaskStatus.RUNNING]
        pending = [t for tid, t in self._tasks.items() if t.status == TaskStatus.PENDING]

        high_priority_running = [t for t in running if t.priority >= 8]

        return {
            'high_priority_running': len(high_priority_running) > 0,
            'pending_count': len(pending),
            'pending_by_priority': {
                str(p): sum(1 for t in pending if t.priority == p)
                for p in range(1, 11)
            },
            'current_stats': self.get_execution_stats(),
        }

    # ------------------------------------------------------------------ #
    #  内部方法
    # ------------------------------------------------------------------ #

    def _append_task(self, task: Task) -> int:
        """追加任务到文件末尾，返回行号（从1起）"""
        line_num = 0
        if self.tasks_file.exists():
            line_num = sum(1 for _ in open(self.tasks_file, encoding='utf-8'))
        with open(self.tasks_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')
        return line_num + 1

    def _update_task(self, task: Task):
        """更新任务（先删后写）"""
        lines = []
        updated = False
        if self.tasks_file.exists():
            for line in self.tasks_file.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    existing_id = d.get('id')
                    if existing_id == task.id:
                        lines.append(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')
                        updated = True
                    else:
                        lines.append(line + '\n')
                except Exception:
                    pass

        if not updated:
            lines.append(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')

        self.tasks_file.write_text(''.join(lines), encoding='utf-8')
        self._tasks[task.id] = task


# =============================================================================
# 快捷工厂函数
# =============================================================================

def get_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    return TaskScheduler()


def register_dream_task(name: str, payload: dict = None) -> str:
    """快捷注册梦境期任务"""
    scheduler = get_scheduler()
    task = Task(
        id=f"dream_{name}_{int(time.time())}",
        type=TaskType.DREAM,
        trigger='cron',
        name=name,
        payload=payload or {},
        priority=3,
    )
    task_id = scheduler.register(task)
    scheduler.enqueue(task_id)
    return task_id
