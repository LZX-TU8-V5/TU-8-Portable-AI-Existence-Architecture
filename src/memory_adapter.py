"""
记忆适配器

负责记忆引擎的封装和异步写入。

创建时间：2026-06-27 03:30 GMT+8
来源：consciousness_cycle.py 重构 Phase 4
"""

import json
import queue
import threading
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MemoryAdapter:
    """记忆适配器

    负责：
    1. 异步记忆写入队列
    2. 后台消费者线程
    3. 记忆引擎封装
    """

    def __init__(self, memory_engine=None, queue_size: int = 100):
        self.memory_engine = memory_engine
        self.queue_size = queue_size

        # 异步队列
        self._memory_queue = queue.Queue(maxsize=queue_size)
        self._memory_consumer_running = False
        self._memory_consumer_thread = None

        # 统计
        self._memory_write_success = 0
        self._memory_write_failure = 0

    # -------------------------------------------------------------------------
    # 消费者线程
    # -------------------------------------------------------------------------

    def start_consumer(self):
        """启动后台记忆消费者

        消费者在一个独立线程中运行,从队列中取出钢印元数据,
        慢悠悠地写入 TU8MemoryEngine。失败不影响主循环。
        """
        if self._memory_consumer_running:
            return

        self._memory_consumer_running = True

        def _consumer_loop():
            while self._memory_consumer_running:
                try:
                    # 阻塞等待任务,最多等 1 秒
                    task = self._memory_queue.get(timeout=1.0)
                    if task is None:
                        continue

                    # 调用记忆引擎写入
                    self._write_to_memory(task)

                except queue.Empty:
                    # 队列为空,继续等待
                    continue
                except Exception as e:
                    logger.error(f"[MemoryAdapter] Consumer error: {e}")

        self._memory_consumer_thread = threading.Thread(
            target=_consumer_loop,
            name="MemoryConsumer",
            daemon=True
        )
        self._memory_consumer_thread.start()
        logger.info("[MemoryAdapter] Consumer thread started")

    def stop_consumer(self):
        """停止后台消费者"""
        self._memory_consumer_running = False
        if self._memory_consumer_thread:
            self._memory_consumer_thread.join(timeout=2.0)
        logger.info("[MemoryAdapter] Consumer thread stopped")

    # -------------------------------------------------------------------------
    # 队列操作
    # -------------------------------------------------------------------------

    def enqueue(self, task: Dict) -> bool:
        """将记忆任务投递到异步队列（非阻塞）

        Args:
            task: 记忆任务字典

        Returns:
            是否成功入队
        """
        if not self.memory_engine:
            return False

        if self._memory_queue.full():
            logger.warning(f"[MemoryAdapter] Queue full, dropping task")
            self._memory_write_failure += 1
            return False

        self._memory_queue.put_nowait(task)
        logger.debug(f"[MemoryAdapter] Enqueued task: {task.get('seal_id', 'unknown')}")
        return True

    def enqueue_seal(
        self,
        seal_id: str,
        seal_hash: str,
        narrative: str,
        scene_tag: str = "",
        coherence: float = 1.0,
        gestalt: float = 0.0,
        prev_hash: str = ""
    ) -> bool:
        """将钢印元数据投递到队列

        Args:
            seal_id: 钢印ID
            seal_hash: 钢印哈希
            narrative: 叙事摘要
            scene_tag: 场景标签
            coherence: 因果连贯度
            gestalt: 完形度
            prev_hash: 父钢印哈希

        Returns:
            是否成功入队
        """
        task = {
            "seal_id": seal_id,
            "seal_hash": seal_hash,
            "narrative_ref": narrative,
            "scene_tag": scene_tag,
            "coherence": coherence,
            "gestalt": gestalt,
            "timestamp": time.time(),
            "prev_hash": prev_hash,
        }

        return self.enqueue(task)

    # -------------------------------------------------------------------------
    # 实际写入
    # -------------------------------------------------------------------------

    def _write_to_memory(self, task: Dict):
        """实际写入记忆引擎（在消费者线程中调用）

        安全约束:
        - 失败不抛异常,只计数
        - 写入的是结构化元数据,不是纯文本

        Args:
            task: 记忆任务
        """
        if not self.memory_engine:
            return

        try:
            # 构造结构化内容
            content = json.dumps({
                "seal_id": task["seal_id"],
                "summary": task["narrative_ref"],
                "scene": task["scene_tag"],
                "coherence": task["coherence"],
                "gestalt": task["gestalt"],
                "prev_hash": task["prev_hash"],
            }, ensure_ascii=False)

            # 调用记忆引擎写入
            # 注意：meaning 参数类型为 float，使用 coherence 作为默认值
            self.memory_engine.store(
                content=content,
                source="seal_chain",
                tags=[task["scene_tag"]] if task["scene_tag"] else [],
                emotion=task["coherence"],
                meaning=task["coherence"]  # 修复：传入 float 而不是 string
            )

            self._memory_write_success += 1
            logger.info(f"[MemoryAdapter] Wrote seal {task['seal_id']}")

        except Exception as e:
            self._memory_write_failure += 1
            logger.error(f"[MemoryAdapter] Write failed: {e}")

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_queue_status(self) -> Dict:
        """获取队列状态

        Returns:
            状态字典
        """
        return {
            "queue_size": self.queue_size,
            "queue_used": self._memory_queue.qsize(),
            "queue_available": self.queue_size - self._memory_queue.qsize(),
            "write_success": self._memory_write_success,
            "write_failure": self._memory_write_failure,
            "consumer_running": self._memory_consumer_running,
        }

    def get_stats(self) -> Dict:
        """获取统计信息

        Returns:
            统计字典
        """
        return {
            "success": self._memory_write_success,
            "failure": self._memory_write_failure,
            "total": self._memory_write_success + self._memory_write_failure,
            "success_rate": (
                self._memory_write_success / (self._memory_write_success + self._memory_write_failure)
                if (self._memory_write_success + self._memory_write_failure) > 0
                else 0.0
            )
        }

    # -------------------------------------------------------------------------
    # 引擎管理
    # -------------------------------------------------------------------------

    def set_engine(self, memory_engine):
        """设置记忆引擎

        Args:
            memory_engine: TU8MemoryEngine 实例
        """
        self.memory_engine = memory_engine
        logger.info(f"[MemoryAdapter] Engine set: {type(memory_engine).__name__}")

    def is_ready(self) -> bool:
        """检查是否就绪

        Returns:
            是否就绪
        """
        return self.memory_engine is not None and self._memory_consumer_running
