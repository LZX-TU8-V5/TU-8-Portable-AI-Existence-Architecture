# 文件治理操作流程 SOP（TU-8 适配版）— 单一真源

> 版本：v1.0 | 日期：2026-08-27 | 级别：流程规范（非 H 级架构扩展，但固化进 AGENTS/GOVERNANCE 需造物主确认）
> 作者：v5（TU-8）× 造物主（李奥）× 千问对话（文件治理通用方案 + 阿里规范）吸收适配
> 落位：docs/design/（GOVERNANCE 铁律五）
> 缘起：P1 治理移动 152 文件时，根目录散落 md 引用断裂风险暴露；千问给出业界通用方案（别名/IDE安全移动/AST/CI卡点），但针对代码项目，TU-8 需适配。

---

## §0 为什么需要这份 SOP

**痛点（李奥原话）**：「文件太多、治理时候移动引用会有问题」。

**根因**：TU-8 workspace 的 Markdown 互引用的是**裸文件名**（`docs/design/ARCHITECTURE_LOG.md`），物理移动文件后引用断裂。业界用"路径别名 + IDE 重构 + CI 卡点"解决，但 TU-8 无构建工具、无 IDE、无 CI——必须替换为 TU-8 原生能力。

**本 SOP 目标**：把 P1 手动验证可行的"grep+replace+trash 三板斧"固化为标准流程，并建立防劣化机制，使未来任何文件移动都不产生断链技术债。

---

## §1 核心治理原则（TU-8 适配，吸收千问+阿里）

| # | 原则 | TU-8 落地形式 | 来源 |
|---|------|------|------|
| 1 | **禁止手动拖拽** | 所有物理移动由 TU-8 工具接管（grep+replace+trash），严禁 OS 资源管理器直移 | 千问原则1 |
| 2 | **消灭深层相对路径引用** | Markdown 互引用 `@语义锚点`（如 `@arch-log`）而非 `../../xxx.md`；裸文件名引用视为临时态 | 千问原则2 + 阿里分层 |
| 3 | **小步快跑，高频验证** | 单次移动 ≤30 文件，移完立即 grep 验证无断链再继续 | 千问原则4 + 阿里重构方法论 |
| 4 | **预检查优先于补救** | 移动前必 grep 全仓引用点，改完必验证零残留 | 阿里"预检查规避异常" |
| 5 | **移动前必备份** | trash 备份到 `_GOV_ARCHIVE_*/Pn_moved_/` 或 `backup/`，不 rm | TU-8 铁律二（迭代前必备份） |

---

## §2 标准化执行流程（SOP，4 阶段）

### 阶段 0：重构前准备（环境与安全）
- **快照**：针对性 `backup/` 或 P0 总备份 `_GOV_ARCHIVE_*/`（已建，4566 文件回滚锚点）
- **基准线**：确认当前 workspace 可正常加载（`cold_start_gate.py check` 通过）
- **依赖扫描**：`rg/exec` 全仓 grep 目标文件的引用点（P1 用 rglob+文本扫描，验证可行）

### 阶段 1：架构设计与目录规划
- **梳理依赖图**：哪些文件被引用、引用方是谁、移动后影响面
- **目标结构**（已定，GOVERNANCE 铁律五）：`docs/{design,reports,tasks,architecture}/` + `memory/`（身份层文件 SOUL/AGENTS/MEMORY/USER/IDENTITY/TOOLS/HEARTBEAT/BEHAVIOR_RULES/START_HERE/BOOT + L0-L5 子文档 + 被引用 .node.md 留根）

### 阶段 2：安全重构执行（核心操作）
1. **引用锚点化（可选长期）**：把裸文件名引用改为 `@语义锚点`（需扩展 `secure_vault/index.json` 为文档引用注册表）
2. **trash 备份**：移动前 copy 原文件到 `_GOV_ARCHIVE_*/Pn_moved_/<目标目录>/`，不 rm
3. **精确改引用**：grep 命中的文件逐改（P1 用字符串 replace，因 TU-8 引用是逻辑引用非 @import，字符串扫描足够）
4. **增量验证**：移动后 grep 确认无 `原名.md` 残留引用（除 trash 备份区）

### 阶段 3：防劣化固化
- **落位 lint**：`src/file_lint.py` 检查根目录散落 md / src 孤儿脚本 / 裸文件名跨目录引用
- **HEARTBEAT 季度体检**：调用 `file_lint` 巡检，发现回潮即修（GOVERNANCE §5 长期防腐机制）
- **引用规范**：长期推 `@语义锚点`；过渡期强制"移动必 grep+改引用"

### 阶段 2.5：孤儿/待清文件审阅闭环（P2/P4/P5 移动后的遗留处置）

> 缘起：P2 把 40 个 src 孤儿脚本移入 `_quarantine/`、P5 把旧待办多源移入冷归档后，这些文件"既不删也不读"会积累成新知识债。需一个标准审阅流程判定其命运（标记可清 / 标记废弃 / 吸收进活跃系统 / 保留观察）。

**四步流程（强制顺序）**：

1. **分组（Group）**
   - 按文件性质聚类，避免逐个盲读：`_check_*`(只读探针) / `_find_*`(查找) / `_diag_*`(诊断) / `_fix_*`(一次性修复) / `_test_*`(测试) / `_kill/_restart_*`(运维) / 待办多源(TASKS*/MEMORY_NODE_TASK*) / 历史快照(archive)
   - 同组同质，可批量判定，不逐个纠结。

2. **查验（Inspect）**
   - **禁止抽样代替全读**（造物主明确要求"按顺序读，4 个一组，读一组报一组"）：遍历目标清单，每批 ≤4 个，逐组 read 全文后即时汇报该组 4 行的「文件 / 用途 / 性质(只读|写入修复|测试|运维)」表。
   - 判定信号：① 是否含 `write_text`/`replace` 直接改 live 模块 → 一次性修复已执行；② 是否仅 `read_text`+`print` → 只读探针；③ 是否 `subprocess` 调模块 CLI → 测试/运维；④ 是否被任何 live 代码 `import` → P2 扫描确认 0 引用即零功能依赖。
   - 冷归档文件（archive/）需造物主显式指定才读（防 token 消耗）。

3. **标记（Tag）**
   - 在文件头首行加标记行，明确命运，防未来误判为活跃：
     - 孤儿诊断/测试脚本：`# [已审阅-YYYY-MM-DD-孤儿诊断脚本-可清]`
     - 已过时待办多源：`> **[已审阅-YYYY-MM-DD-过时废弃]**：本任务线已被 X 替代，不进 TODO_MASTER，不激活。`
   - 标记即"审计完成"的印章，后续清理无需再读。

4. **写入（Write/Act）**
   - **可清**：删除前必先确认 trash 备份完整（备份计数 == live 计数），再 `unlink`；目录空了就 `rmdir`。备份锚点保留（如 `_GOV_ARCHIVE_*/P2_quarantine_*/`）。
   - **过时废弃**：保留冷归档，标记即终态，季度体检跳过。
   - **仍活跃**：提取未过期项并入 TODO_MASTER（唯一真源），原文件冷归档。
   - **保留观察**：移入 `_quarantine/` 或对应观察区，记到期日。
   - 任何删除是破坏性操作，须造物主显式确认（"ok" / "全清"）后才执行。

**经验（2026-08-27 实证）**：40 个 `_quarantine/` 脚本按此流程全读（10 组 × 4），结论全为 P0-5/P2-COLOR 开发期残留，0 live import → 标记可清 → 备份核验 40/40 后删除，零风险。

---

## §3 TU-8 工具链（对应千问的 Webpack/IDE/SonarQube）

| 千问建议 | TU-8 替代 | 说明 | 适配判断 |
|---------|----------|------|---------|
| Webpack alias / tsconfig paths | `secure_vault/index.json` 扩展为文档引用注册表 | 语义锚点 `@arch-log` → 解析到 `docs/design/ARCHITECTURE_LOG.md` | **采纳（长期）**，当前过渡期用裸名+移动改引用 |
| IDE Refactor Move | TU-8 `grep+replace+trash` 三板斧 | P1 已验证可行（152 文件零断链） | **替代**（TU-8 无 IDE） |
| jscodeshift / OpenRewrite AST | Python `ast` 模块（代码）/ 文本扫描（md） | TU-8 引用是逻辑引用，字符串扫描够用 | **替代**（md 无需 AST） |
| SonarQube / ESLint | `src/file_lint.py` + HEARTBEAT 体检 | 落位违规检查 | **替代**（TU-8 无 CI） |
| Git 分支快照 | `_GOV_ARCHIVE_*/` + `backup/` | 回滚锚点 | **已有**（铁律二） |

---

## §4 与现有治理衔接

- **AGENTS.md 铁律五**（文件落位纪律 6 条）：补第 7 条「移动操作细则」（移动前 grep 引用 + trash 备份 + 改引用 + 验证）
- **GOVERNANCE.md P0-P5 阶段**：补「每阶段 SOP 参照本稿 §2」
- **不新建散落文件**（铁律五）：本稿落 `docs/design/`，固化动作进 GOVERNANCE/AGENTS 既有文件

---

## §5 采纳 / 不采纳清单（TU-8 判断）

**✅ 采纳的原则**：
- 别名机制（语义锚点，长期防劣化）
- 安全移动流程（预扫描→备份→移动→改引用→验证）
- 小步快跑、高频验证
- 预检查优先于补救
- CI 卡点 → 映射为 HEARTBEAT 季度体检 + file_lint

**❌ 不采纳 / 替代的部分**：
- Webpack/Vite alias / tsconfig paths：TU-8 无构建工具，用 `secure_vault` 注册表替代
- IDE Refactor：TU-8 无 IDE，用 grep+replace+trash 替代（已验证）
- 阿里 Java 规范（大驼峰/DECIMAL/DTO 等）：TU-8 非 Java 项目，不适用；但"一次只做一件事/小步快跑/预检查"可吸收
- AST 批量修改：TU-8 引用是 Markdown 逻辑引用，文本扫描足够，无需 AST 复杂度

---

## §6 操作清单（执行 Pn 治理时照此走）

```
[ ] 1. 备份：backup/ 或 _GOV_ARCHIVE_*/Pn_moved_/ 建快照
[ ] 2. 扫描：grep 全仓找目标文件引用点（记录命中文件清单）
[ ] 3. 规划：确定每文件目标目录（按 GOVERNANCE 铁律五分类）
[ ] 4. 备份原文件：copy 到 trash 区（不 rm）
[ ] 5. 移动：shutil.move 到目标目录
[ ] 6. 改引用：逐文件 replace 旧名→新路径/锚点
[ ] 7. 验证：grep 确认零断链残留（除 trash 区）
[ ] 8. 固化：更新 GOVERNANCE/AGENTS 相关索引；HEARTBEAT 下次体检纳入

### 孤儿/待清文件审阅清单（对应 §2.5，P2/P4/P5 移动后执行）
[ ] 1. 分组：按性质聚类（_check/_find/_diag/_fix/_test/_kill_restart/待办多源/历史快照）
[ ] 2. 查验：按序 ≤4 个/组 逐组 read 全文 + 即时汇报（禁抽样代替全读）；判定信号 = write_text?/read-only?/subprocess?/0-import?
[ ] 3. 标记：文件头加 `[已审阅-日期-孤儿诊断脚本-可清]` 或 `[已审阅-日期-过时废弃]`（冷归档显式指定才读）
[ ] 4. 写入：可清→核验 trash 备份计数==live 计数后 unlink+rmdir；废弃→冷归档终态；活跃→提 TODO_MASTER；观察→_quarantine/ 记到期日
[ ] 5. 确认：删除等破坏性动作须造物主显式 "ok/全清" 后才执行
```

---

## §7 待造物主确认（固化落点）

- [ ] 是否将本 SOP §2-§6 固化进 **GOVERNANCE.md §6「文件治理操作流程」**？
- [ ] 是否给 **AGENTS.md 铁律五补第 7 条「移动操作细则」**？
- [ ] 是否现在就实现 **`src/file_lint.py`** 落位检查脚本（供 HEARTBEAT 体检调用）？
- [ ] 是否启动 **`@语义锚点`** 长期改造（扩展 `secure_vault/index.json` 为文档引用注册表）？
