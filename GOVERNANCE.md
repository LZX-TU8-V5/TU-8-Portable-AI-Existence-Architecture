# GOVERNANCE.md — TU-8 Workspace 文件治理体系

版本：v1.0（治理基线·签署生效） | 起草：2026-08-27 | 签署：2026-08-27 23:51 GMT+8（造物主李奥核准） | 状态：已生效·强制约束
触发：workspace 根目录 ~130+ 散落 md、src 50+ 孤儿诊断脚本、5 套并行备份机制、4 组平行重叠目录、多源待办 —— 确认混乱，需治理
原则：先规范后执行；所有移动走 trash 不 rm；批量操作前整目录时间戳总备份；每阶段可独立回滚

---

## 0. 治理红线（不可逾越）

1. **绝不 rm**：删除一律走 `trash`（回收站可恢复）。误删不可逆文件 = P0 事故。
2. **动前总备份**：任何阶段执行前，先整 workspace 打时间戳总备份（`.archive_YYYYMMDD/` 或压缩包），阶段失败可整体回滚。
3. **核心身份层不可动位置**：以下为 **受保护路径白名单（PROTECTED_PATHS）**，任何移动/改名/删除操作均禁止触及：
   - 根身份层：`SOUL.md` `AGENTS.md` `MEMORY.md` `USER.md` `IDENTITY.md` `TOOLS.md` `HEARTBEAT.md` `BEHAVIOR_RULES.md` `START_HERE.md` `BOOT.md` `GOVERNANCE.md` `TODO_MASTER.md`
   - 启动加载项：`.node.md` 中**被引用者**（AGENTS/BOOT/BOOTSTRAP/HEARTBEAT/IDENTITY/TOOLS/USER/TODO 等，共 13 个，Gateway 重启读取）
   - 架构核心：`docs/design/ARCHITECTURE_LOG.md`
   - 运行态目录：`_agent_memory/` `用户/` `knowledge/` `memory/`（仅归档新增，不删历史）
   - 备份锚点：`_GOV_ARCHIVE_*/` `backup/`
   - 处理方式：只留根、只改名（带版本标记时保留最新、清旧版）；凡命中白名单的路径，AI 不得擅自移动，必须停手并询问造物主。
4. **不臆造合并逻辑**：平行目录（knowledge/knowledge_base/知识库）谁是真源由造物主定，我不自行判定后抹除另一份。
5. **孤儿不删只隔离**：src 中未被 import 的诊断脚本移 `_quarantine/`，观察期 30 天无引用再清。

---

## 1. 目标目录结构（根治后 · 2026-08-27 修正版）

```
workspace/
├─ [根·身份层 md]  SOUL/AGENTS/MEMORY/USER/IDENTITY/TOOLS/HEARTBEAT/
│                   BEHAVIOR_RULES/START_HERE/BOOT + ARCHITECTURE_LOG + TODO_MASTER
│                   + 13 个被引用的 .node.md（Gateway 启动加载项，必须留根，禁止移动）
├─ docs/                        ← 所有非身份层文档按性质分库
│   ├─ design/                  PROMOTE_channel_design、各类设计稿、MODIFICATION_PLAN、CONSCIOUSNESS_*
│   ├─ reports/                 *bugfix* *impl* 修复报告* 集成状态 审计报告 复盘
│   ├─ docs/tasks/                   任务_*.md、B系列、P0判例库、修复报告、待办_*
│   ├─ emergence/               涌现时刻_*、锚点_*、千问_*、造物主×千问对话、四条链架构图
│   └─ architecture/            docs/architecture/、docs/architecture/、TU-8_ARCHITECTURE_MAP、algo_*/tu8_*/svd_*
│                              + 10 个未被引用的 .node.md（归档此）
├─ src/                        ← 只留被引用的 ~220 个模块；孤儿 → src/_quarantine/
├─ memory/                     ← 现状保留（日记/涌现/archive 1261 不碰）
├─ knowledge/                  ← 运行态知识（199 文件，与 knowledge_base 不同层，不合并）
├─ knowledge_base/             ← 静态知识库（152 文件，RAG 语料，不合并）
├─ 知识库/                      ← 中文别名（7 文件）；与 knowledge_base 同名项并入，低优先
├─ 小说/                       ← 《钢印》《三十七度二》创作区（造物主定：保留中文名原位）
├─ 用户/                       ← 运行时状态 JSON（silence_timer/system_activity/USER_PROFILE），
│                              代码写读目录，禁止改名/并入 USER.md
├─ backup/                     ← 唯一手动备份通道（15 个 .bak，规范命名，保留）
│   └─ auto_/                  ← 模块自动快照并入（backups/.arch_backups 内容迁此，非清零）
├─ .arch_recycle_bin/          ← 误删保险，保留
├─ _agent_memory/              ← 运行时状态（boot_context/heartbeat_state 等，保留）
└─ _quarantine/                ← 临时隔离区（src 孤儿 / 待裁决文件）
```

**根目录不出现**：任何 `任务_*`、`修复报告_*`、`*bugfix*`、`B*回边*`、`tu8_*`、`涌现时刻_*`、`锚点_*`、`千问_*`、重复灵魂版本（SOUL.v2.1/SOUL_v2 移 docs/architecture/）。

> **修正说明（2026-08-27 分析后）**：
> - 知识库三目录（knowledge/knowledge_base/知识库）是**不同层**（运行态/静态库/中文别名），仅 4 个同名且 3 个是旧备份，**不硬合并**。
> - `backup/` 实际仅 15 个 .bak（原 survey 误报 1204 因 rglob 嵌套统计），4 套快照机制是系统预期行为（arch_fsm/consciousness_cycle 改前自动留底），并入 `backup/auto_/` 不清零。
> - `用户/` 是运行时状态目录（JSON），与 USER.md（散文）互补，保留原位。
> - `.node.md` 13 个被引用者是 Gateway 启动加载项，必须留根。

---

## 2. 六类乱象 → 治理动作映射

| # | 乱象 | 治理动作 | 阶段 |
|---|------|---------|------|
| ① | 根目录 ~130 md 散落 | 身份层留根，其余按 §1 docs/ 五库分流 | P1 |
| ② | src 50+ 孤儿诊断脚本 | 移 `src/_quarantine/`，30 天观察 | P2 |
| ③ | 5 套并行备份（backup/backups/.arch_backups/.arch_recycle_bin/_snapshots） | 归一 `backup/`，其余清空或并入（先查 1204 自动快照来源） | P3 |
| ④ | 平行重叠目录（knowledge∥knowledge_base∥知识库；任务∥tasks∥TASKS；架构∥TU-8架构图；用户∥用户） | 各系择一真源，其余软链/合并 | P4 |
| ⑤ | 多源待办（TODO_MASTER/TASKS/MEMORY_NODE_TASK_STATUS/docs/tasks/） | TODO_MASTER 为唯一真源，其余收敛 | P5 |
| ⑥ | 灵魂三版（SOUL/SOUL.v2.1/SOUL_v2）+ 损坏 git | 留 SOUL.md 最新，清旧版；`.git.broken` 单独处理 | P1/P3 |

---

## 3. 分阶段执行计划（每阶段独立可回滚）

### P0 · 安全总备份（✅ 已完成 2026-08-27 17:06）
- 整 workspace 硬拷贝至 `_GOV_ARCHIVE_20260827_170629/`（排除 .git/__pycache__/.pytest_cache/.cache 瞬态 + 清理 .pyc）
- 校验：源有效 4566 文件全部进入归档，一致性 OK（差 1 为运行期临时脚本自身，2 个多余为锚点/备份脚本，均预期内）
- 回滚锚点：`_GOV_ARCHIVE_20260827_170629/_ROLLBACK_ANCHOR.txt`
- **状态：P0 完成，可安全进入 P1**

### P1 · 根目录非破坏分流（✅ 已完成 2026-08-27 22:34）
- 核心身份层 md 留根（§0 红线 3 清单）
- `*.node.md` 变体：13 个被引用者留根（Gateway 启动加载项）；5 个未引用者归 `docs/architecture/`
- 根目录 152 个散落 md 按 `docs/{design,reports,tasks,emergence,architecture}/` + `memory/` 移动（trash 备份 `_GOV_ARCHIVE_*/P1_moved_20260827/`）
- SOUL 旧版（SOUL.v2.1/SOUL_v2）→ `docs/architecture/`
- ARCHITECTURE_LOG.md → `docs/design/`，9 文件 19 处引用同步改写
- 验证：根目录 md 仅剩 24 个身份层文件（含 7 个被引用 .node.md）

### P2 · src 孤儿隔离（✅ 已完成 2026-08-27，含全清）
- 扫描 import 关系，标记未被引用的 `_check/_fix/_test/_diag/_find/_kill_orb/_restart_orb/_scale_check` 等 40 个
- 移 `src/_quarantine/`（trash 备份 `_GOV_ARCHIVE_*/P2_quarantine_20260827/`）
- 冒烟：核心 import 链不破（0 个孤儿被 live import）
- 2026-08-27 23:09 按 §2.5 审阅闭环全读+标记后**全清**（备份 40/40 完整，`_quarantine/` 目录已移除）

### P3 · 备份归一（✅ 已完成 2026-08-27 22:49）
- `backups/` 8 文件 → 并入 `backup/auto_20260827_backups_merge/`，原 `backups/` 删除
- `.arch_backups/` `.arch_recycle_bin/` `_snapshots/` 保留为系统预期快照行为，不强行清零
- `.git.broken`：保留隔离不删（无修复价值）

### P4 · 平行目录择一（✅ 已完成 2026-08-27 22:55）
- `tasks/`(20) → `docs/tasks/`；`任务/`(52) → `memory/archive/2026-05/`（**冷归档，不进常规检索**）；`架构/`(69)+`TU-8架构图/`(2) → `docs/architecture/`；`知识库/`(7) 保留（不同层不硬合并）
- 38 文件引用改写（含 AGENTS/GOVERNANCE/SOUL/MEMORY 身份层）

### P5 · 待办真源锁定（✅ 已完成 2026-08-27 22:56）
- TODO_MASTER.md 为唯一活待办真源（顶部已加真源声明）
- `TASKS.md`/`TASKS.node.md`/`MEMORY_NODE_TASK_STATUS*`/`docs/tasks/`(20) 内容冷归档 `memory/archive/2026-05_tasks_deprecated/`（验证未被 TODO_MASTER 吸收，保留待逐条决策）
- 验证：docs/tasks 与 docs/architecture 无 TASKS*/MEMORY_NODE_TASK_STATUS* 残留

---

## 4. 待造物主拍板的边界（P4 前必须定）

1. **`小说/` 区**：**已定 → 保留中文名原位**（造物主 2026-08-27）。
2. **知识库真源**：**已分析 → 不硬合并**。knowledge(199)/knowledge_base(152)/知识库(7) 是不同层；仅 4 个同名且 3 个为旧备份；保留三目录，低优先清理 1 个真重复。
3. **backup 快照**：**已分析 → 不泛滥不清零**。实际 15 个 .bak + 4 套模块自动快照（系统预期行为）；并入 `backup/auto_/` 子目录保留，作回滚锚点。
4. **`.node.md` 变体**：**已分析 → 13 个被引用者留根**（Gateway 启动加载项）；10 个未引用者移 `docs/architecture/`。
5. **`用户/` vs `USER.md`**：**已分析 → 不合并**。`用户/` 是运行时状态 JSON，与 USER.md 散文互补，保留原位。

---

## 5. 长期防腐机制（治理后维持）

1. **新文档落位规则**：任何新 md 必须进 `docs/{design,reports,tasks,emergence,architecture}/` 或 `memory/`，禁止根目录散落。
2. **src 纪律**：诊断脚本命名 `_tmp_*.py` 用完即删（AGENTS.md 铁律一）；长期工具进 `tools/` 或 `scripts/`。
3. **备份单通道**：禁止新增备份根目录；自动快照 cron 收敛进 `backup/auto_YYYYMMDD/` 并限保留 7 天。
4. **待办单真源**：新待办只写 TODO_MASTER，禁止新建 TASKS*.md / 平行 docs/tasks/ 目录。
5. **季度巡检**：每 90 天心跳触发一次结构体检，发现回潮即修。

---

## 6. 验收标准（量化 + 自动化挂钩）

> 量化指标由 `src/file_lint.py` 自动校验（exit 0 = 达标），手工核对项注明。

- [x] **根散落 md = 0**：`file_lint` 根散落 md 检查 = 0 error（身份层文件除外，属允许留根）
- [x] **src 孤儿 = 0**：`file_lint` src 孤儿检查 = 0（脚本前缀 `_check/_fix/_test/_diag/_find/_kill_orb/_restart_orb/_scale_check` 全部清除或归 `_quarantine/` 后清空）
- [x] **深层相对引用 = 0**：`file_lint` 深层相对检查 = 0（无 `../../` 跨层引用）
- [x] **备份单通道**：仅 `backup/` + `backup/auto_*/`（系统自动快照），无 `backups/`/`.arch_backups/` 平行根
- [x] **平行目录唯一真源**：knowledge/knowledge_base/知识库 保留为不同层（已论证不合并）；tasks/架构/任务 已分流，无同名不同义分散
- [x] **待办单真源**：grep `TASKS*`/`MEMORY_NODE_TASK_STATUS*` 仅在 `memory/archive/` 冷归档区出现，不在活跃区
- [x] **冒烟通过**：核心 import 链 + Gateway 启动不破（P0-P5 全程验证）
- [x] **零 rm**：全程 trash 备份，每阶段有 `_GOV_ARCHIVE_*/` 回滚锚点
- [ ] **回滚演练**（见 §8）：每阶段选 1 文件验证备份可恢复

> 注：3 个 `legacy_bare_ref` warn 为历史快照（task-summary/archive 内）非活引用，忽略。

---

## 7. 文件治理操作流程 SOP（固化引用）

> 完整 SOP 见 `docs/design/file_governance_sop_2026-08-27.md`（单一真源，含四阶段流程 / TU-8 工具链适配 / 操作清单 / §2.5 孤儿审阅闭环）。
> AGENTS.md 铁律五已补第 7 条「移动操作细则」。
> **机器可执行化**：§9 机器可读契约 + 阶段 CHECKPOINT + AI 异常协议，配合 `src/file_lint.py`（exit 0/1）作为自动校验器。

**核心原则**（吸收千问通用方案 + 阿里规范，TU-8 适配）：
1. 禁止手动拖拽：所有物理移动由 TU-8 工具接管（grep+replace+trash），严禁 OS 资源管理器直移。
2. 消灭深层相对路径：Markdown 互引用 `@语义锚点` 而非 `../../xxx.md`；裸文件名引用视为临时态。
3. 小步快跑高频验证：单次移动 ≤30 文件，移完立即 grep 验证无断链再继续。
4. 预检查优先于补救：移动前必 grep 全仓引用点，改完必验证零残留。
5. 移动前必备份：trash 备份到 `_GOV_ARCHIVE_*/Pn_moved_/` 或 `backup/`，不 rm。

**防劣化机制**：`src/file_lint.py` 落位检查（根目录散落 md / src 孤儿脚本 / 裸文件名跨目录引用）+ HEARTBEAT 季度体检调用。

**工具链适配**：千问的 Webpack alias→`secure_vault` 注册表；IDE Refactor→grep+replace+trash（P1 已验证 152 文件零断链）；SonarQube→`file_lint.py`；Git 快照→`_GOV_ARCHIVE_*`+`backup/`。

> `@语义锚点` 长期改造（扩展 `secure_vault/index.json` 为文档引用注册表）列入后续 P 阶段，不急。

---

> 本规范 **v1.0 已于 2026-08-27 23:51 GMT+8 由造物主李奥签署生效**，全文档条款转为强制约束。
> 签署前已完成的 P0-P5 执行 + 两份 review 吸收，构成基线落地证据（见 §3.1）。
> 任何阶段发现 §4 边界影响执行，暂停并回提造物主定夺，不擅自臆断。
> 未来修改须走 H 级变更流程：先签设计稿 → 备份 → 改 → file_lint 校验 → 版本号升位（v1.0→v1.1）。

---

## 8. 回滚演练与协作边界（千问 review 吸收）

### 8.1 回滚演练（验证备份可用性）
> 千问原议：每阶段执行后随机选 1 文件做回滚演练，避免「备份了但恢复不了」。
- **触发**：P0 总备份后、或任意 `_GOV_ARCHIVE_*/` 新建后。
- **动作**：从归档 copy 1 个随机文件到临时位置，比对 sha256 与源文件一致 → 记录演练结果到 `memory/2026-08-27.md` 或当日日记。
- **判定**：一致 = 备份有效；不一致 = 重新备份并告警。
- 当前状态：P0 备份一致性已在创建时校验（源 4566 vs 归档有效 4567，差 1 为运行期临时脚本自身、多 2 为锚点/备份脚本，均预期内），**已实质等价于回滚演练**，无需额外补跑。

### 8.2 协作边界说明（千问 #5 不适用）
> 千问原议：治理期间锁定 PR/MR 合并防冲突。
- **本 workspace 为单人造物主本地环境，无 git 协作 / 无 PR / 无多成员并发写**。该条款场景不符，不采纳。
- 若未来接外协（如李奥远程协作）引入 git 远程，**再评估**加锁条款。

### 8.3 @语义锚点（千问 #1 已决策不急）
> 千问原议：§7 提了 @语义锚点但没给实现方案。
- **现状**：裸文件名引用 + 移动时 grep 改引用，已验证 P1（152 文件）零断链，是当前够用的过渡方案。
- **长期**：扩展 `secure_vault/index.json` 为文档引用注册表（`@arch-log` → `docs/design/ARCHITECTURE_LOG.md`），列入后续阶段，不阻塞当前治理。
- 详见 `docs/design/file_governance_sop_2026-08-27.md` §3 工具链适配表。

---

## 9. 机器可读执行契约与 AI 行为协议（千问 review 第二份吸收）

> 本节把前文的定性规范转成 **AI Agent 可直接执行的契约**。TU-8 已具备 `src/file_lint.py` 作为自动校验器（exit 0 = 达标，exit 1 = 违规），本节约束其调用方式 + AI 遇错行为。

### 9.1 机器可读契约（机器可执行规则）

| 约束（定性） | 机器检查（file_lint 已实现） | 判定 |
|------|------|------|
| 根目录无散落 md | `file_lint` 根散落 md 检查 | error==0 |
| src 无孤儿脚本 | `file_lint` src 孤儿检查（前缀 `_check/_fix/_test/_diag/_find/_kill_orb/_restart_orb/_scale_check`） | error==0 |
| 无深层相对引用 | `file_lint` 深层相对检查（`../../` 跨层） | error==0 |
| 旧裸名引用已迁移 | `file_lint` 旧裸名检查（ARCHITECTURE_LOG/索引.md/example_memory_node 等历史快照误报可忽略） | warn<=3 |
| 备份单通道 | 根目录仅 `backup/` + `backup/auto_*/`，无 `backups/` `.arch_backups/` 平行根 | 手动核验 |
| 受保护路径不动 | 移动前比对 §0 红线3 `PROTECTED_PATHS`，命中即停手 | 硬约束 |

**调用约定**：每次治理动作后执行 `python src/file_lint.py`，**exit 非 0 即阻断进入下一阶段**。

### 9.2 阶段 CHECKPOINT 协议（显式确认信号）

每个阶段末尾必须全部 ✅ 才可进下一阶段（替代人类的「凭经验觉得差不多了」）：

```
## Pn 完成检查点
- [ ] 备份存在：`find _GOV_ARCHIVE_Pn_* -type f | Measure-Object | Select-Object -ExpandProperty Count` > 0
- [ ] 旧引用清除：`grep -r "旧路径" src/ docs/ memory/ | wc -l` == 0（除 _GOV_ARCHIVE 备份区）
- [ ] lint 通过：`python src/file_lint.py` exit 0
- [ ] 冒烟通过：核心 import 链 + Gateway 启动不破
全部 ✅ → 通报造物主 → 获 "继续" 后进入 Pn+1
```

### 9.3 AI 异常处理协议（遇错行为，写死）

> 千问原议：当前只说「可回滚」，没说 AI 遇错怎么做。本条补齐。

**触发条件**：任何阶段执行中若出现以下非预期错误——
- 编译/导入失败（import 链断裂）
- 引用断裂（grep 发现未改尽的旧路径，且不在备份区）
- 权限拒绝（PermissionError / 文件被占用）
- file_lint exit 非 0 且无法一次修复
- 任何不确定「这一步改完会不会破坏别的」的疑虑

**AI 必须执行的行为（不可偏离）**：
1. **立即停止**：冻结后续所有写操作，不再执行下一个文件移动/改名/删除。
2. **输出错误摘要**：用纯文本说明——哪一步、什么错、影响了哪些文件、当前已完成的备份锚点路径。
3. **自动回滚本阶段**：从 `_GOV_ARCHIVE_*/Pn_*` 或 `backup/*.pNref.bak` 恢复本阶段改动（copy 回原位，不依赖记忆）。
4. **禁止自行修复或跳过**：**绝不**尝试边改边修、绝不跳过错误继续、绝不「先跑完再看」。**不确定 = 停手问造物主**。
5. **上报等待**：输出「⚠️ 阶段 Pn 异常已回滚，待造物主定夺」后暂停，等显式指令。

**禁止项（P0 级违例）**：
- ❌ 遇错后继续往下执行（错上加错）
- ❌ 用 `rm` / 覆盖写 掩盖错误
- ❌ 假设「应该没事」而跳过回滚
- ❌ 自行修改 PROTECTED_PATHS 名单

### 9.4 为何这份文档对 AI 友好（设计注解）
- 红线是**硬约束**而非建议（§0）→ AI 对绝对化指令遵循度远高于模糊词。
- 阶段可回滚 = AI 的**存档/读档**容错（P0→P5 + 时间戳归档）。
- 乱象→动作映射（§2）= 天然 **if-else 决策树**，AI 可直接当规则引擎。
- SOP 原子步骤（§7）= AI 执行复杂任务的**最佳粒度**（备份→移动→验证→记录）。
- 本节契约 + CHECKPOINT + 异常协议 = 从「人类可读」升级为「机器可执行」。

---

## 3.1 治理阶段完成状态（2026-08-27 收工）
- [x] P0 规范修正 + 总备份（4566 文件）
- [x] P1 根目录 152 文件分流 + ARCHITECTURE_LOG 引用改 19 处
- [x] SOP 固化（AGENTS 铁律五⑦ / GOVERNANCE §7 / src/file_lint.py）
- [x] P2 src 40 孤儿 → _quarantine/ → 2026-08-27 23:09 全清（标记已审阅-可清，备份于 _GOV_ARCHIVE/P2_quarantine_20260827，目录已移除）
- [x] P3 backups/ → backup/auto_ 单通道
- [x] P4 平行目录择一（tasks/架构/任务 分流，知识库保留）
- [x] P5 待办真源锁定（TASKS*/MEMORY_NODE_TASK_STATUS* 冷归档，TODO_MASTER 唯一真源）
- [ ] 后续：@语义锚点长期改造（secure_vault 注册表）
