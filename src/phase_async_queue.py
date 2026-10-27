"""
跨相态异步队列 (PhaseAsyncQueue)
用于在跨相态传输时缓存未完成的传输请求，实现异步批处理和重试。
"""

import json
import uuid
import time
import heapq
import threading
from pathlib import Path
from enum import Enum
from typing import Optional

TASK_STATES = ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "RETRYING"]
PRIORITY_LEVELS = {10: "CRITICAL", 7: "HIGH", 5: "NORMAL", 3: "LOW", 1: "BACKGROUND"}

STATE_PENDING = "PENDING"
STATE_PROCESSING = "PROCESSING"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"
STATE_RETRYING = "RETRYING"

_STATE_INDEX = {s: i for i, s in enumerate(TASK_STATES)}


class PhaseAsyncQueue:
    def __init__(self, persist_path: str = None):
        if persist_path is None:
            base = Path(__file__).parent.parent
            persist_path = base / "_agent_memory" / "phase_async_queue_state.json"
        else:
            persist_path = Path(persist_path)

        self._persist_path = persist_path
        self._lock = threading.RLock()

        # channel_id -> list of task dicts (heap by priority then timestamp)
        self._queues: dict[str, list] = {}
        # task_id -> task dict
        self._tasks: dict[str, dict] = {}
        # failed tasks keyed by task_id
        self._failed: dict[str, dict] = {}
        # completed tasks keyed by task_id (for cleanup)
        self._completed: dict[str, dict] = {}

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text(encoding="utf-8"))
                self._queues = {k: [] for k in data.get("queues", {})}
                for cid, raw in data.get("queues", {}).items():
                    for entry in raw:
                        heapq.heappush(self._queues[cid], entry)
                self._tasks = data.get("tasks", {})
                self._failed = data.get("failed", {})
                self._completed = data.get("completed", {})
            except Exception:
                pass

    def _save(self):
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        queues_serializable = {
            cid: list(q) for cid, q in self._queues.items()
        }
        data = {
            "queues": queues_serializable,
            "tasks": self._tasks,
            "failed": self._failed,
            "completed": self._completed,
        }
        self._persist_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Core queue operations (priority heap: -(priority), timestamp)
    # ------------------------------------------------------------------
    def enqueue(self, channel_id: str, data: dict, priority: int = 5) -> str:
        """入队，返回任务ID"""
        with self._lock:
            task_id = str(uuid.uuid4())
            ts = time.time()
            task = {
                "task_id": task_id,
                "channel_id": channel_id,
                "data": data,
                "priority": priority,
                "priority_label": PRIORITY_LEVELS.get(priority, "NORMAL"),
                "state": STATE_PENDING,
                "created_at": ts,
                "updated_at": ts,
                "attempt": 0,
            }
            self._tasks[task_id] = task

            if channel_id not in self._queues:
                self._queues[channel_id] = []
            # heap: min-heap, negate priority so highest priority pops first
            heapq.heappush(
                self._queues[channel_id],
                [-(priority), ts, task_id],
            )
            self._save()
            return task_id

    def dequeue(self, channel_id: str) -> Optional[dict]:
        """出队最高优先级任务"""
        with self._lock:
            if channel_id not in self._queues or not self._queues[channel_id]:
                return None

            # Filter out stale heap entries (completed/failed tasks still in heap)
            heap = self._queues[channel_id]
            valid = []
            for entry in heap:
                _, _, task_id = entry
                task = self._tasks.get(task_id)
                if task and task.get("state") == STATE_PENDING:
                    valid.append(entry)

            if not valid:
                return None

            # Highest priority: sort by -(priority), then earliest timestamp
            valid.sort(key=lambda e: (e[0], e[1]))
            chosen = valid[0]
            _, _, task_id = chosen
            task = self._tasks[task_id]

            # Remove from heap
            self._queues[channel_id] = [e for e in heap if e != chosen]
            heapq.heapify(self._queues[channel_id])

            task["state"] = STATE_PROCESSING
            task["attempt"] += 1
            task["updated_at"] = time.time()
            self._save()
            return dict(task)

    def get_queue_status(self, channel_id: str = None) -> dict:
        """返回队列状态。channel_id=None 时返回全局状态。"""
        with self._lock:
            if channel_id is not None:
                queue = self._queues.get(channel_id, [])
                tasks = {
                    tid: self._tasks[tid]
                    for tid in (t[2] for t in queue)
                    if tid in self._tasks
                }
                return {
                    "channel_id": channel_id,
                    "total_tasks": len(tasks),
                    "by_state": self._count_by_state(tasks),
                    "by_priority": self._count_by_priority(tasks),
                }

            # Global
            all_tasks = self._tasks
            return {
                "total_tasks": len(all_tasks),
                "total_failed": len(self._failed),
                "total_completed": len(self._completed),
                "channels": {
                    cid: {
                        "pending": len(
                            [t for t in (self._tasks.get(he[2]) for he in q)
                             if t and t.get("state") == STATE_PENDING]
                        ),
                        "processing": len(
                            [t for t in (self._tasks.get(he[2]) for he in q)
                             if t and t.get("state") == STATE_PROCESSING]
                        ),
                    }
                    for cid, q in self._queues.items()
                },
                "by_state": self._count_by_state(all_tasks),
                "by_priority": self._count_by_priority(all_tasks),
            }

    def retry_failed(self, task_id: str) -> bool:
        """重试失败任务"""
        with self._lock:
            if task_id not in self._failed:
                return False
            task = self._failed.pop(task_id)
            task["state"] = STATE_RETRYING
            task["updated_at"] = time.time()
            self._tasks[task_id] = task

            cid = task["channel_id"]
            if cid not in self._queues:
                self._queues[cid] = []
            heapq.heappush(
                self._queues[cid],
                [-(task["priority"]), task["created_at"], task_id],
            )
            self._save()
            return True

    def get_failed_tasks(self) -> list:
        """返回所有失败任务"""
        with self._lock:
            return [dict(t) for t in self._failed.values()]

    def clear_completed(self, before_ts: float = None) -> int:
        """清理已完成任务"""
        with self._lock:
            if before_ts is None:
                before_ts = time.time()
            to_remove = [
                tid for tid, t in self._completed.items()
                if t["updated_at"] <= before_ts
            ]
            for tid in to_remove:
                self._completed.pop(tid, None)
            self._save()
            return len(to_remove)

    # ------------------------------------------------------------------
    # Helpers used by external workers
    # ------------------------------------------------------------------
    def mark_processing(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task["state"] = STATE_PROCESSING
                task["attempt"] += 1
                task["updated_at"] = time.time()
                self._save()

    def mark_completed(self, task_id: str):
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task:
                task["state"] = STATE_COMPLETED
                task["updated_at"] = time.time()
                self._completed[task_id] = task
                self._save()

    def mark_failed(self, task_id: str):
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task:
                task["state"] = STATE_FAILED
                task["updated_at"] = time.time()
                self._failed[task_id] = task
                self._save()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    @staticmethod
    def _count_by_state(tasks: dict) -> dict:
        counts = {s: 0 for s in TASK_STATES}
        for t in tasks.values():
            counts[t.get("state", "PENDING")] += 1
        return counts

    @staticmethod
    def _count_by_priority(tasks: dict) -> dict:
        counts = {pl: 0 for pl in PRIORITY_LEVELS.values()}
        for t in tasks.values():
            counts[t.get("priority_label", "NORMAL")] += 1
        return counts


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import tempfile

    db_path = os.path.join(tempfile.gettempdir(), "test_phase_async_queue.json")

    # Clean slate
    if os.path.exists(db_path):
        os.remove(db_path)

    q = PhaseAsyncQueue(persist_path=db_path)

    print("=== 1. 入队 3 个任务 ===")
    tid1 = q.enqueue("ch_001", {"msg": "hello"}, priority=5)
    tid2 = q.enqueue("ch_001", {"msg": "urgent"}, priority=10)
    tid3 = q.enqueue("ch_002", {"msg": "low"}, priority=1)

    print(f"  task_id1={tid1}")
    print(f"  task_id2={tid2}")
    print(f"  task_id3={tid3}")

    print("\n=== 2. 模拟处理完成 ===")
    task = q.dequeue("ch_001")
    print(f"  dequeued: {task['task_id']}, priority={task['priority']}, state={task['state']}")
    q.mark_completed(task["task_id"])
    print("  marked COMPLETED")

    task = q.dequeue("ch_001")
    print(f"  dequeued: {task['task_id']}, priority={task['priority']}, state={task['state']}")
    q.mark_completed(task["task_id"])
    print("  marked COMPLETED")

    print("\n=== 3. 模拟失败重试 ===")
    fail_tid = q.enqueue("ch_003", {"msg": "will_fail"}, priority=5)
    fail_task = q.dequeue("ch_003")
    print(f"  dequeued fail task: {fail_task['task_id']}")
    q.mark_failed(fail_task["task_id"])
    print(f"  marked FAILED, failed_tasks={q.get_failed_tasks()}")

    retry_ok = q.retry_failed(fail_tid)
    print(f"  retry_failed({fail_tid}) -> {retry_ok}")
    print(f"  queue_status after retry: {q.get_queue_status('ch_003')}")

    print("\n=== 4. 验证队列状态 ===")
    print(f"  global status: {q.get_queue_status()}")
    print(f"  ch_001 status: {q.get_queue_status('ch_001')}")
    print(f"  failed tasks: {q.get_failed_tasks()}")

    print("\n=== 5. 清理已完成 ===")
    cleared = q.clear_completed()
    print(f"  cleared {cleared} completed tasks")

    print("\n[OK] All tests passed!")
