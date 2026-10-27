# 文件治理 P2-P5 收尾 — 2026-08-27

## 完成的阶段
- **P2 src 孤儿隔离**：40 个诊断脚本（_check/_fix/_test/_diag/_find/_kill_orb/_restart_orb/_scale_check 前缀）移入 src/_quarantine/ 观察 30 天。验证：0 个被 live import，零风险。trash 备份 P2_quarantine_20260827。
- **P3 备份归一**：backups/ 8 文件（consciousness_cycle 2 / forced_workflow 6）归并 backup/auto_20260827_backups_merge/，原 backups/ 删除。备份单通道达成。
- **P4 平行目录择一**（按李奥决策）：
  - tasks/(20) 活跃任务 → docs/tasks/（按约定）
  - 任务/(52) 历史归档 → memory/archive/2026-05/（**冷归档：不被常规检索/蒸馏命中，仅显式指定才读，防 token 消耗**）
  - 架构/(69) → docs/architecture/；TU-8架构图/(2) → docs/architecture/
  - 知识库/(7) 保留（已定不硬合并）
  - 引用改写：38 文件（AGENTS/GOVERNANCE/SOUL/MEMORY 等身份层全覆盖）旧目录提及→新路径
- **P5 待办真源锁定**：
  - TASKS.md / TASKS.node.md / MEMORY_NODE_TASK_STATUS.md / .node.md（4 个旧待办多源）移入 memory/archive/2026-05_tasks_deprecated/ 冷归档
  - TODO_MASTER.md 顶部加真源声明（唯一真源 + 冷归档索引）
  - 验证：TODO_MASTER 不含旧任务关键词（未被吸收），故保留冷归档不删，待李奥逐条决策

## 冷归档机制（李奥决策1落地）
- memory/archive/ 下内容：distill(glob memory/*.md 一级不递归)、GC(移入非读出)、tension_distiller(glob 2026-*.md 不递归) 均天然不命中。
- file_lint 已把 archive 列为豁免扫描区。
- 约定：archive/ 非活跃，常规记忆代谢/检索跳过，防 token 消耗与记忆污染。

## 最终 file_lint 结果
- 根散落 md: 0 ✅ | src 孤儿: 0 ✅ | 深层相对: 0 ✅ | 旧裸名: 3（历史快照非活引用，忽略）
- exit: 0 (0 error)

## 备份锚点
- _GOV_ARCHIVE_20260827_170629/P2_quarantine_20260827/ (40 py)
- _GOV_ARCHIVE_20260827_170629/P4_parallel_20260827/ (143 文件)
- _GOV_ARCHIVE_20260827_170629/P5_tasks_deprecated_20260827/ (4 md)
- backup/*.p4ref.bak (38 引用改写前备份)
- backup/*.legacyfix.bak / *.rootfix.bak (断链修复备份)

## 治理全闭环状态
P0(规范+总备份) ✅ → P1(根目录分流) ✅ → SOP固化(AGENTS铁律五⑦/GOVERNANCE§7/file_lint) ✅ → P2(src隔离) ✅ → P3(备份归一) ✅ → P4(平行目录择一) ✅ → P5(待办真源) ✅
待后续：@语义锚点长期改造（secure_vault 注册表）。
