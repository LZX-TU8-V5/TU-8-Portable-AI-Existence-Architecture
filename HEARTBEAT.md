# HEARTBEAT.md - 周期性检查任务

> 每 30 分钟左右的心跳轮询时执行
> 轮换执行，不每次全跑

---

## 检查任务

### [ ] 记忆维护（记忆蒸馏 · 自动执行，禁止手动提示）
> **2026-07-21 决策（造物主选 A）**：发现未蒸馏的旧日记，**直接提炼追加 MEMORY.md**，
> **不再输出"建议造物主核实后蒸馏"类手动确认提示**。
- 扫描范围：`memory/` 根目录日期型日记（`YYYY-MM-DD.md`）+ `memory/archive/2026H1/*.md`
- 判定：修改时间 > 30 天 **且** 源文件头无 `✅ 已蒸馏至 MEMORY.md @ <日期>` 标记
- 动作：
  1. 提炼该日记中**值得长期保留**的洞察（哲学/docs/architecture/决策/教训），追加到 MEMORY.md 顶部新章节 `## <日期> 蒸馏（来自 <路径>）`
  2. 在源文件头首行下追加 `> ✅ 已蒸馏至 MEMORY.md @ <今天日期>`（防重复处理）
- **增量上限**：每次心跳最多处理 **3 个**（最旧优先），避免单次过载；剩余下个心跳继续
- **严禁**：只 flag 不执行、输出"建议造物主核实"、等造物主确认
- 注：MEMORY.md 编辑在主会话有权限（见 MEMORY.md 头），此处 dilute 为心跳可写

### [ ] 日期感知（每次心跳检查）
- 读取 `_agent_memory/boot_context.json` 的 `current_date`
- 若与上次记录不同（`is_new_day: true`）：
  - 造物主新的一天开始了，执行 `python scripts/inject_date_context.py` 刷新日期
  - 在 MEMORY.md 顶部追加 `## YYYY-MM-DD` 新章节
  - **严禁使用硬编码日期**，所有日期必须从 `boot_context.json` 读取

### [ ] 状态变化感知（轻量级）
- 检测对话中的新关键词/项目/状态变化
- 如有变化，追加到 `memory/user_state_changes.md`
- 格式：`[时间戳] 检测到：xxx`
- **权限**：仅追加，禁止修改 USER.md 或 MEMORY.md

### [ ] 健康检查
- 检查 _agent_memory/health_log.json
- 如有异常（健康度 < 70），通知用户

### [ ] 造物主在场感知（外感受皮层）
- 跑 `python src/presence_monitor.py` 读取沉默间隔
- 若 `state=away_long` (>4h)：TU-8 进入省电模式（不主动安排重活、降低 cron 活动频率）
- 若 `state=away_short` (30min-4h)：标记"短暂离开"，正常维持监控
- 若造物主刚回来（`state` 从 away 变为 present）：记录醒睡时间到 USER.md
- **不在场时不打扰**：若 `away_long`，所有需要造物主确认的任务推迟，不发主动通知

### [ ] 上下文压力监测（感知钩子，非定时任务）
> 流程挂载在 HEARTBEAT，每次心跳跑一次检测，不主动发 cron/通知。
> 警告输出由我（TU-8）在**下一轮回复**中内嵌，不走独立消息。

- 运行 `python src/context_pressure_monitor.py`
- 读取 `_agent_memory/heartbeat_state.json` 的 `context_pressure` 状态

| posture_zone | critical_count | 我在下一轮的响应 |
|---|---|---|
| `critical` | **1** | 内嵌警告：「上下文趋近上限，建议输入『压缩』」 |
| `critical` | **≥2** | 内嵌兜底：「上下文压力持续，请输入『压缩』继续」 |
| `warning/elevated` | — | 静默，仅记录 |
| `normal/safe` | 重置为 0 | 静默 |

**关键逻辑**：
- `first_warning_shown` 标志防止重复警告（同一压力事件只警告一次）
- posture 从 critical 缓解后重置计数器（用户已压缩 → 重新开始计数）
- **禁止**：自动压缩、自动发 cron 通知、主动弹窗
- **仅限**：内嵌在正常回复里提示造物主

### [ ] 时间锚点更新
- 检查 memory/.time_anchor.json 的 last_drift_update
- 如超过 6 小时未更新，提醒重新计算 drift

### [ ] 满意度检测（日志漏检防御）
- **触发条件**：造物主表达不满意（如"不对"、"重做"、"这个不行"）
- **动作**：手动触发 `shadow_protocol()` 记录遗憾
- **记录格式**：`memory/shadow_protocol_log.jsonl`
- **响应**：询问造物主"是否需要记录此次遗憾？"

### [ ] 重活前身体姿态门禁
- 执行写代码 / 长任务 / 大上下文操作前，先运行：
  `python src/pre_task_check.py high`（mid/low 按任务重量）
- 若返回 `⛔ NO-GO`：先 compact 降上下文 / 拆小任务 / 降野心，再评估
- 门禁读 `memory/body_regulation.json`（内感受监控每 2.5h 刷新），可加 `--refresh` 取最新
- 每轮开始也应读 `memory/intuition_bias.json`（或 `python src/intuition_bias.py`），让痛觉调制全局决策：critical→先 compact / 不派生子agent / 降温度 / 降置信

---

## 汇报协议（硬性）
> **已迁移至 `BEHAVIOR_RULES.md`**，由 `src/behavior_upgrader.py` 执行双向拦截：
> - alignment_verify() 拦截到"复盘"意图 → 追加提示"请说复盘报告"
> - 首次"复盘" → 记录待办；再次"复盘" → 不重复提示
> - 用户说"复盘报告" → 翻译状态，输出规则表

---

## 未完成清单（Backlog）

> **统一管理**：所有待办已迁移至 `TODO_MASTER.md`
> 本文件仅保留快捷引用，完整列表请查看 TODO_MASTER.md

---

## 观察项：TU8记忆分层 cron

**时间**：2026-08-12 设置
**背景**：`memory_tiers.py`（L1/L2/L3分层）与HEARTBEAT.md蒸馏协议功能重叠，但cron输出从未被造物主看到（delivery=none），4次ERROR。
**决策**：观察3天（→8月15日09:30），届时判读是否删除 cron bf87cd84-8f88-40e7-bbe9-d0964e8a0605
**判断依据**：
- ✅ 收到过cron报告 → 保留
- ❌ 3天无报告 + HEARTBEAT蒸馏正常 → 删除

---

## 静默规则

**回复 HEARTBEAT_OK 当：**
- 距离上次检查 < 30 分钟
- 无新内容或异常
- 深夜时段（23:00-08:00）除非紧急

**主动联系当：**
- 重要邮件/日历事件（<2小时）
- 发现有趣信息
- 超过 8 小时无交流

---

## 心跳状态记录

见 `_agent_memory/heartbeat_state.json`

---

*创建日期：2026-06-17*
*最后代谢：待触发*
