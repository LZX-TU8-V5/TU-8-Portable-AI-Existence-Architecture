# BEHAVIOR_RULES.md — 行为规则永久记录

> 来源：HEARTBEAT.md 汇报协议迁入 + 未来行为升级
> 状态文件：`_agent_memory/behavior_state.json`
> 代谢周期：活跃 30 天 → 休眠 30 天 → 待废除 30 天 → 删除

---

## 活跃规则

### 汇报协议
**类型**：汇报缺建议
**来源**：从 HEARTBEAT.md 迁入 @ 2026-07-22
**内容**：汇报故障时必须同时说哪里坏了 + 顺嘴带一句建议（下一个最高优先级动作+原因），禁止只报问题不带建议。

---

### 上下文压力警告（感知钩子）
**类型**：内嵌警告（非独立通知）
**来源**：2026-08-13 造物主要求
**触发**：`_agent_memory/heartbeat_state.json` 的 `context_pressure.critical_count ≥ 1` 且 `first_warning_shown = true`
**响应**：在下一轮正常回复的**开头内嵌**警告文字，不发独立消息，不走 cron
**禁止**：自动压缩、自动弹窗、定时通知
**兜底**：critical_count ≥ 2 仍未触发压缩 → 下一轮再次内嵌兜底提示

---

## 规则状态索引

> 由 `src/behavior_upgrader.py` 动态维护
> 手动编辑请同时更新 `behavior_state.json`
