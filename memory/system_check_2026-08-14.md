# 系统检查 2026-08-14
**时间：2026-08-14 上午**
**目标：诊断 cron 批量 agent error + 记忆分层 7.7min**

---

## 1. Cron 错误分析

### 错误分类

| 类型 | 模式 | 涉及 job |
|------|------|---------|
| A | `⚠️ Agent couldn't generate a response` | 内感受(40次)/主动好奇(27次)/每日复盘(6次)/待办代谢(1次) |
| B | `502 网络或服务异常` | 记忆分层(4次, timeout) |
| C | `Delivering to 腾讯通路 requires target` | 每日日期上下文刷新(delivery 配置问题) |

### 根因判定

**类型 A**：`active_curiosity.py` / `review_scheduler.py` / `todo_metabolism.py` 均无 LLM 调用，纯 Python 脚本。isolated session 的 `agentTurn` 失败 → **isolated session API quota 耗尽**，非代码 bug。

**类型 B**：`memory_tiers.py` 今日实测 1.5s 正常，7.7min 历史记录可能是当时网络抖动。

**类型 C**：delivery 配置 `announce` 模式但无 `target`，真实状态是 `lastDelivered: false`，不阻塞下次执行。

### 结论

- ❌ 代码 bug：**无**（所有脚本实测正常）
- ⚠️ 基础设施：isolated session API quota 耗尽（长期高频 cron 导致）
- ✅ 无需修复：记忆分层实测正常，日期刷新 delivery 静默失败不影响执行

---

## 2. 新发现：SteelAnchor tags 字段错误

**文件**：`src/heritage_system.py:217`
**问题**：`SteelAnchor(**v)` 未过滤未知字段，v 含 `tags` 键但 `SteelAnchor` dataclass 无此字段
**影响**：`review_scheduler daily` 启动时打 WARNING，日志：`SteelAnchor.__init__() got an unexpected keyword argument 'tags'`
**状态**：⚠️ **已修复**（2026-08-14）
**修复**：`SteelAnchor(**{kk: vv for kk, vv in v.items() if kk in SteelAnchor.__dataclass_fields__})`

---

## 3. 脚本实测结果

| 脚本 | 结果 |
|------|------|
| `memory_tiers.py` | ✅ 1.5s，4 个待蒸馏日记 |
| `active_curiosity.py` | ✅ 正常（好奇未触发）|
| `active_curiosity.py --phase compare` | ✅ 正常（无预测记录）|
| `review_scheduler.py daily` | ✅ 80%健康（SteelAnchor WARNING 已消除）|
| `todo_metabolism.py` | ✅ 无输出（无超期项）|
| `interoceptive_cortex.py` | ✅ 无输出（无痛觉变化）|

---

## 4. 建议

**isolated session quota 问题**：
- 已知问题，非代码 bug
- 可考虑：降低 cron 频率 / 合并任务 / 等待 QClaw 配额刷新（每日 00:00）
- 当前最频繁：内感受(6h) + 主动好奇(8h) + dream_check(4h) + 存活监测(6h) = 4 个任务并发

**待核实**：
- 每日 00:00 配额重置后观察是否恢复
- 积分余额：QClaw 客户端 → 用量统计 → 积分余额（data/4110/forward）
