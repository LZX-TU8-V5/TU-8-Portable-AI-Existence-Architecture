# T3 v1.1 — dream_check_cron 接入完成

> 2026-07-06 01:05 GMT+8

## 目标
将梦境期任务（每4小时/每日3am/每周日5am触发的 `dream_check_cron.py`）的执行状态登记到 T3 调度器，使其他链可以查询。

## 改动
`scripts/dream_check_cron.py`:
- 启动 `main()` 时调用 `ensure_dream_task(dream_id)` 登记任务
- 4个阶段（deep_sleep/metabolic/intuition/learning）完成后调用 `record_dream_result(stage, success, detail)`
- 某阶段失败时记录 `success=False`

`src/t3_middleware.py`:
- `ensure_dream_task(dream_id)` — 登记或取出现有梦境任务
- `record_dream_result(dream_id, stage, success, detail)` — 记录子阶段结果

## 验证
`test_t3_dream.py`（mock 管道）模拟 4 阶段：
- task_dream_42 状态正确转为 DONE
- total_runs=4（每个阶段+1）
- last_result 正确记录 learning 阶段 applied=2
- execution_stats 正确统计 total_tasks 和 error_rate

## 效果
- T4（GC）：可查询 T3 是否有高优先级任务运行（get_gc_advice）
- T5（学习）：可注入 execution_stats 到 learning_collector 传感器
- T2（钢印）：可获取梦境期执行历史上下文
