## T3 调度链功能

### 核心接口

```python
TaskScheduler.register(task)     # 登记任务
TaskScheduler.enqueue(task_id)   # 加入执行队列
TaskScheduler.next()             # 取最高优先级任务
TaskScheduler.record_result()    # 记录执行结果
TaskScheduler.get_execution_stats()  # 执行统计
```

### 中间件接口

```python
# T2↔T3
notify_seal_created(seal_id, scene_tag, summary)  # 铸印→调度
get_seal_context(seal_id)                          # 调度→钢印上下文

# T4↔T3
on_gc_completed(stats)    # GC完成→调度
get_gc_advice()           # 调度→GC建议（是否应推迟）

# T5↔T3
notify_learning_ready(products)     # 学习产物→调度
get_execution_stats_for_learning() # 调度→学习传感器
```

### 任务类型与优先级

| 类型 | 初始优先级 | 示例 |
|------|-----------|------|
| USER | 10 | 用户直接触发 |
| SYSTEM | 9 | 钢印复核、告警 |
| LEARNING | 6 | 学习产物验证 |
| METABOLIC | 5 | GC 复核 |
| DREAM | 3 | 梦境期任务 |

---




<!-- meta: last_accessed=1783325313.1035788, count=1 -->


