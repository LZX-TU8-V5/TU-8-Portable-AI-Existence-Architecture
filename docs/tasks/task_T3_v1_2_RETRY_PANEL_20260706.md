# T3 v1.2 — 失败重试策略 + 执行面板

> 2026-07-06 01:45 GMT+8

## 改动

**`src/task_dispatch_core.py`**：
- Task 新增 3 字段：`max_retries`, `retry_delay_ms`, `next_retry_at`
- `record_result(success=False)` 自动指数退避重回 PENDING
- `next()` 跳过仍在退避期的任务
- `get_execution_stats()` 新增 `retry_pending` / `retry_total` 字段

**`scripts/t3_panel.py`**（新）：
- 面板、精简、JSON、单任务详情 4 种输出模式
- 等待队列按优先级排列，显示 age 和退避剩余时间

## 验证

重试策略 6 项断言全部通过：
- 失败#1 → PENDING + 退避 100ms
- next() 在退避期返回 None
- 退避结束后 next() 正常返回
- 失败#2 → PENDING + 指数退避 200ms
- 失败#3 → FAILED（达 3 次上限）

面板 3 种输出格式均验证通过。

## 文件

| 文件 | 版本 | 说明 |
|------|------|------|
| `src/task_dispatch_core.py` | v1.2 | 重试 + 退避 + 统计 |
| `scripts/t3_panel.py` | v1.0 | 执行面板 |
| `scripts/test_t3_retry.py` | — | 重试测试 |
