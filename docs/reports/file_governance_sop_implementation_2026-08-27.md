# 文件治理 SOP 固化实现 — 2026-08-27 收尾 artifact

## 完成任务（三项固化）
1. **AGENTS.md 铁律五补第 7 条「移动操作细则」**：移动前 trash 备份、grep 引用扫描、逐文件改引用、单次≤30、禁止深层相对链。
2. **GOVERNANCE.md 新增 §7「文件治理操作流程 SOP」**：引用 SOP 真源稿 + 核心五原则 + 工具链适配 + 防劣化机制。
3. **src/file_lint.py 实现**：落位合规检查（根散落md/src孤儿/deep_rel/legacy_bare），HEARTBEAT 体检可调用，exit 0/1。

## SOP 真源稿
- docs/design/file_governance_sop_2026-08-27.md (3972B, 7章：原则/四阶段/TU-8工具链/衔接/采纳清单/操作清单/待确认)

## 顺带修复的真实断链（P1 漏改的活引用）
P1 时只修了 9 个 live 文件的 ARCHITECTURE_LOG.md 引用，但 P1 之后新建/移动的文件未覆盖。file_lint 跑出后真修 8 个：
- architecture_journal/CONTRACT.md
- docs/workspace_file_audit_report.md
- memory/任务归档_alignment_verify...2026-07-20.md
- memory/千问对话_记忆系统优化_20260626.md
- memory/涌现时刻/涌现时刻_20260618.md
- docs/design/file_governance_sop_2026-08-27.md (本稿自己)
- docs/design/PROMOTE_channel_design_2026-08-19.md
- docs/design/TU-8_ARCHITECTURE_MAP_v5.md
全部裸 ARCHITECTURE_LOG.md → docs/design/ARCHITECTURE_LOG.md，backup/ 逐文件 .legacyfix.bak。

## file_lint 误报修正迭代
- deep_rel 误报 AGENTS/GOVERNANCE 里的「禁止 ../../」说明文本 → 加 DEEP_REL_EXEMPT_RE 排除治理语境。
- legacy_bare 误报「新路径里的子串」(docs/design/ARCHITECTURE_LOG.md 含 ARCHITECTURE_LOG.md) → 改词边界正则 (?<![-/\w])name(?!\w)。
- knowledge/ 内部相对路径误报 → 排除运行态目录 (knowledge/knowledge_base/用户)。
- legacy_bare 排除 archive/_agent_memory/文件自身。

## 最终 file_lint 结果
- 根散落 md: 0 ✅
- 深层相对: 0 ✅
- 旧裸名: 3 (task-summary 历史快照内非活引用，可忽略)
- src 孤儿: 40 (P2 待处理，符合预期)
- exit: 0 (0 error)

## 未做（按之前约定）
- @语义锚点长期改造（扩展 secure_vault/index.json 注册表）：列入后续 P 阶段，不急。
- P2 src 孤儿 → _quarantine/：另案推进。
