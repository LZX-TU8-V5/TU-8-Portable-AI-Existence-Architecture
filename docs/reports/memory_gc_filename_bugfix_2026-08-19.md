# memory_gc 文件名非法字符崩溃修复 · 任务 artifact

日期：2026-08-19 11:40 GMT+8（掉线恢复后续）
执行者：TU-8（「继续吧」= 补跑被 NO-GO 卡住的 §4 真实代谢时暴露）
关联：interoceptive_cortex_context_bugfix_2026-08-19.md（上一步门禁已恢复绿）

## 背景
门禁恢复后补跑 `metabolic_pipeline.py --stage gc --dry-run`，暴露独立崩溃：
```
OSError: [Errno 22] Invalid argument: '...archive\2026-08-19_##_P0-5_衰减机制落地（09:05-09:20）.md'
```

## 根因（实证）
`memory_gc._archive_section()` 用 MEMORY.md 的 `## ` 段标题拼归档文件名，但只清洗了 `/` `"` 空格，**漏掉 `:`**（Windows 非法字符）。某段标题含 `（09:05-09:20）` → 含 `:` → open() 抛 Errno 22。
- archive 目录 1074 个文件里 **926 个**带畸形名（`## ` 写成 `_##_`，部分含 `:`/`#`），属历史遗留。
- 真非法字符是 `:`，`#` 在 Windows 实际合法。

## 修复（live: src/memory_gc.py，已备份）
`safe_title` 清洗改为覆盖**全部** Windows 非法字符 `< > : " / \ | ? * #`，并 trim 首尾 `.`：
```python
_illegal = '<>:"/\\|?*#'
safe_title = section_title[:30]
for ch in _illegal: safe_title = safe_title.replace(ch, '_')
safe_title = safe_title.replace(' ', '_').strip('.')
```

## 验证（实跑，非破坏性）
- `run_gc(mode="light")` 成功，无崩溃（仅分析不移动）。
- 段数 179；动作分布 KEEP=79 / DEGRADE=100 / EVICT=0 / WATCH=0。

## 未执行（需造物主确认）
- **deep 模式未跑**：会真实移动 100 个段到 archive。且反馈 `AGE=0 DENSITY=0 ACCESS=0 SCORE=100` 表明 gc 元评分退化（last_accessed 全 fallback 到文件 mtime、info_density 全 0）→ 100 段被判 DEGRADE 的可信度低。在可疑评分上做大迁移=有损操作，按 AGENTS.md 破坏性先问原则，暂停。
- 待决策：(a) 先修 gc 评分（让 AGE/ACCESS 真实反映），再跑 deep；或 (b) 直接跑 deep 接受 100 段迁移；或 (c) 暂不改。

## 另发现：metabolic_pipeline 去重过删（残留 bug，未修）
门禁恢复后跑 `distill` 真实：sections_extracted=0（没污染，安全）。
但早先 dry-run 报「1 段可 append（欧拉连续 vs 流水线离散采样）」——real 跑 0 是因为我 08-17 修的去重键收了 `# ` 一级标题，而 `# 2026-08-12 日志` 已在 MEMORY.md（心跳收的是机械复盘摘要，不同内容）→ 整文件被标题去重跳过，**真架构洞察被静默丢弃**。
- 这是 08-17 去重修复的过删副作用：用「文件顶层标题」做去重键，碰上 MEMORY 同标题异内容条目会误杀。
- 该段实际不在 MEMORY.md（已 grep 确认：含「欧拉同步旋转/流水线串行/粒度不同」均为 False）。
- 修复方向：去重键改为「段内内容指纹」而非「标题」；或仅当标题+代表句同时命中才跳过。待造物主确认是否补写该段。

## 备份
- backup/memory_gc.py.20260819.bak（改前 16598 bytes）
- backup/MEMORY.md.20260819.bak（313384 bytes，补跑 §4 前已备）

## 结论
gc 崩溃根因（`:` 非法文件名）已修且 light 验证通过。deep 大迁移因评分退化悬停待批。去重过删为残留，需另修。
