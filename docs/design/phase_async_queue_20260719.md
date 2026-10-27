# PhaseAsyncQueue 实现笔记

## 任务
创建 `src/phase_async_queue.py` — 跨相态异步队列，支持异步批处理和重试。

## 关键设计决策

### 持久化
- 写入 `_agent_memory/phase_async_queue_state.json`
- 每次状态变更（enqueue/dequeue/mark_completed/mark_failed/retry）后自动保存
- 启动时自动从磁盘恢复状态

### 队列结构
- `self._queues[channel_id]`: 最小堆（heap），按 `-(priority)` + timestamp 排序
- `self._tasks[task_id]`: 任务详情字典（全局索引）
- `self._failed[task_id]`: 失败任务（从 tasks 中移除后归入此处）
- `self._completed[task_id]`: 已完成任务（用于按时间清理）

### dequeue 逻辑
堆中会残留已完成/失败任务的旧条目，dequeue 时先过滤出所有 PENDING 任务，再按优先级+时间戳排序取最优。避免无效 pop。

### 任务状态流转
```
PENDING → PROCESSING → COMPLETED
                      → FAILED → RETRYING → PROCESSING → ...
```

## 接口
| 方法 | 功能 |
|------|------|
| `enqueue(channel_id, data, priority)` | 入队，返回 task_id |
| `dequeue(channel_id)` | 出队最高优先级 PENDING 任务 |
| `get_queue_status(channel_id)` | 队列状态（支持全局/按 channel） |
| `retry_failed(task_id)` | 将失败任务重新入队 |
| `get_failed_tasks()` | 获取所有失败任务 |
| `clear_completed(before_ts)` | 按时间戳清理已完成任务 |
| `mark_processing/completed/failed(task_id)` | 外部 worker 调用的状态更新 |

## 验证结果
- 入队3个任务 ✓（优先级10的任务先出队）
- 模拟处理完成 ✓
- 模拟失败重试 ✓（FAILED → RETRYING 状态正确）
- 队列状态验证 ✓
- 清理已完成 ✓
