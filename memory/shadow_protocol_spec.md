# shadow_protocol_log.jsonl 格式规范

> 用途：记录遗憾（执行结果与预期不符）
> 触发：造物主不满意时手动调用

---

## 记录格式

```json
{
  "timestamp": "2026-07-03T00:40:00+08:00",
  "trigger": "造物主不满意",
  "context": "具体情境描述",
  "expected": "预期结果",
  "actual": "实际结果",
  "gap": "差距分析",
  "lesson": "教训提炼",
  "action": "改进措施"
}
```

---

## 示例

```json
{
  "timestamp": "2026-07-03T00:40:00+08:00",
  "trigger": "造物主说'不对'",
  "context": "P2任务执行顺序错误",
  "expected": "按依赖关系排序执行",
  "actual": "随意顺序执行",
  "gap": "未分析任务依赖",
  "lesson": "执行前必须分析任务依赖关系",
  "action": "创建任务依赖分析模板"
}
```

---

## 调用方式

在对话中检测到不满意信号时：

```python
from shadow_protocol import log_regret

log_regret(
    trigger="造物主不满意",
    context="...",
    expected="...",
    actual="...",
    gap="...",
    lesson="...",
    action="..."
)
```

---

*创建时间：2026-07-03 00:40 GMT+8*
