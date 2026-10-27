# 孤儿文件审阅闭环流程固化 — 2026-08-27

## 落点
`docs/design/file_governance_sop_2026-08-27.md` 新增 **§2.5 孤儿/待清文件审阅闭环** + §6 补充孤儿审阅清单。

## 四步流程（强制顺序）
1. **分组（Group）**：按性质聚类（_check/_find/_diag/_fix/_test/_kill_restart/待办多源/历史快照），同组同质批量判定。
2. **查验（Inspect）**：按序 ≤4 个/组 逐组 read 全文 + 即时汇报（**禁抽样代替全读**，造物主明确要求）。判定信号：write_text?(一次性修复) / read-only?(探针) / subprocess?(测试运维) / 0-import?(零依赖)。冷归档需显式指定才读。
3. **标记（Tag）**：文件头加 `# [已审阅-日期-孤儿诊断脚本-可清]` 或 `> [已审阅-日期-过时废弃]`，作为审计完成印章。
4. **写入（Write/Act）**：可清→核验 trash 备份计数==live 后 unlink+rmdir；废弃→冷归档终态；活跃→提 TODO_MASTER；观察→_quarantine/ 记到期。删除须造物主显式确认。

## 实证来源
2026-08-27 当晚：4 个冷归档待办 + 40 个 src/_quarantine/ 孤儿脚本，按此流程全读（10 组×4）+ 标记 + 备份核验 40/40 后删除，零风险。

## 备份
`backup/file_governance_sop_2026-08-27.md.orphan_sop.bak`（7098B，修改前）
