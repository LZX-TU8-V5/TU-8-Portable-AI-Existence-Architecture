# metabolic_pipeline 去重缺陷修复 · 任务 artifact

日期：2026-08-17 19:49 GMT+8
执行者：TU-8（经 QClaw 接口，造物主「继续吧」授权）
来源指令：tu8_t5_self_repair_directive_2026-08-17.md

## 目标
指令书主目标（glob 硬编码）已先于本任务确认修复。本任务在其上继续：修复 dry-run 暴露的**去重失效**缺陷。

## 根因（实证）
- 旧去重键只收集 `## ` 二级标题：`existing_titles={l for l in ... if l.startswith("## ")}`
- 但 distill 提取出的段标题全是 `# 2026-08-xx 每日复盘` **一级标题**
- `# ` ≠ `## ` → 键永远不匹配 → 7 段全部逃脱去重、进入 APPEND
- 退一步：即使标题不同，**内容已在 MEMORY.md** 的段也无人拦截

## 修复内容（live: src/metabolic_pipeline.py）
1. 去重键同时收集 `# ` 与 `## ` 标题
2. 新增内容指纹去重：段内最长非标题/注释行 lower 后在 MEMORY.md 做包含检查，命中跳过
3. 新增机械复盘摘要拦截：`覆盖率`/`钢印链条共`/`生命年轮处于`/`待办` 且标题为 `# ` 的段跳过（HEARTBEAT 已处理，勿二次污染）

## 验证（dry-run，对 live 零写入）
| 阶段 | 修复前 | 修复后 |
|------|--------|--------|
| distill sections_extracted | 7 | 1 |
| 实际 APPEND 数 | 7 | 1 |
| 跳过原因分布 | — | 标题去重 4 / 内容已存在 1 / 机械摘要 3 |

唯一幸存段：`[2026-08-12] # 2026-08-12 日志` 欧拉vs流水线架构洞察（边界case：其最长行是表格行，未命中内容指纹；但该洞察确属新，保留追加无害）。

## 备份
- `backup/metabolic_pipeline.py.20260817.bak`（改前副本，8944 bytes）

## 遗留
- **§4 真实代谢未执行**：门禁 NO-GO + 源文件已带 `✅ 已蒸馏` 标记，无追加必要；待造物主确认或自然触发。
- **内感受监控读数陈旧**：body_regulation/intuition_bias 卡在 18:01（context 100%），但 gateway 实测 0%；--refresh 未重算。已记入 2026-08-17.md，待心跳检修。

## 结论
glob bug 根除 + 去重补强，distill 现可安全运行而不污染 MEMORY.md。
