# TODO 合并 + 代谢流程决策 (2026-07-06)

## 做了什么
- 把 11 个散落 TODO 文件合并为唯一真源 `TODO_MASTER.md`（3912B）。
- 集成 NEW 项（看门狗/ cron/ root cause/ 长会话compact/ 上游反馈）。
- 8 个旧文件移入 `backup/consolidated_TODO_20260706/`（保留不删，含 `_INDEX.json`）。
- 校正 master 虚报：版本树/状态机/调度链T3 实际已完成，已从待办划掉 → 真实活项远少于原报 ~33。

## 用户问题：有流程吗？会自己淘汰吗？
**答：有代谢流程，但覆盖面错了。**
- TU-8 有「代谢链条」（第4链）：`src/memory_gc.py` v2（TTL 30/60天保护 + KEEP/ARCHIVE/DELETE 推荐）+ `metabolic_pipeline.py` + HEARTBEAT.md「记忆维护」任务。
- 但它只覆盖 **MEMORY.md / USER.md / memory/*.md**，**不覆盖 TODO_*.md**。
- 结果：TODO 无自动淘汰，只堆积 → 11 个文件各自生长。这就是散落根因。

## 处理方案（已落地 + 待确认）
1. ✅ 单一真源（TODO_MASTER.md）。
2. ✅ 文件内写入「淘汰策略」：每项带 `[创建日期]`；DONE>7天→历史；>60天无进展→STALE 待核实（不自动删）。
3. ✅ 散落文件归档，不入真源。
4. ✅ 已接入代谢闭环（2026-07-06）：
   - `src/todo_metabolism.py`：扫 TODO_MASTER.md，标 STALE(>60天) + 重复项；健康静默。
   - cron「TU8待办代谢」(id `2a891f61-c73f-481e-9547-fdd9f174c1dc`) 每天 8:00 上海时区跑，mode:none（本地渲染）。
   - 已回填全部 26 项 `[创建]` 日期（按来源文件日期推算），否则代谢无法老化。
   - 验证：健康→静默；注入 2024 日期→正确报 STALE(917天)。
   - 修正：cron 默认 delivery=announce 无路由会丢告警，已改 mode:none。

## 当前真实活项（合并后，已全部带创建日期）
- P1 工程：GPU公式原型 + P0-3/4/5 + P1-1~6
- P2 长期：P2-1~5 + 标注A-1~6 + 删除D-1
- 运维NEW：长会话compact + 上游反馈腾讯
- 涌现子任务：版本树P1.2.x / 遗忘层联动 / 生命年轮 / 论战升级 / 认知差距容器 / BOOTSTRAP
- 旧文件待核实区（可能已完成，不删待确认）

---
*⅋ 2026-07-06 合并 artifact*
