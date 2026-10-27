# memory_reader 修复与验证（2026-08-29 夜）

## 背景
主会话卡住前，架构/记忆结构优化线已完成：设计稿 `docs/design/memory_structure_optimization_2026-08-29.md`（§0.0~§0.0.11）、MEMORY.md 77段重排（L0→L2→L1）、外置 `_agent_memory/memory_layer_index.json`。reorder artifact 与 TODO_MASTER 标注的**唯一遗留下一步** = 建 `src/memory_reader.py` 做分层读取。

`src/memory_reader.py` 探针版其实已存在（5600B），但**未做 §1.4 step5 的 3 场景验证**。本会话补做验证，发现它不是"探针够用"，而是**有真实失效 bug**。

## 缺陷（实测定位，非猜测）
1. **ranking 失效（严重）**：原 `read_for_task` 只比较查询与段的 `sem` 轴粗标签（二值 1.0），丢弃查询↔段向量相似度。结果：所有查询都返回文档顺序前 8 段（与查询无关 → 等于没检索）。
2. **estimate_compression 仪表 bug**：按 `"\n\n"` 段数统计，谎报"召回 2261 段"。
3. **根因：共享 embedder 中文缺陷**：`cognitive_evaluator.TFIDFEmbedder._tokenize` 用 `re.findall(r'[\w]+')` 把中文切成单字，再被 `len(t)>1` 过滤全丢掉，只剩 raw-text 2gram 兜底 → MEMORY.md 段向量中位余弦 0.0（近正交）。该模块被多处共用，**不能动**。

## 修复
重写 `src/memory_reader.py`（7350B），自洽、零 blast radius：
- 主排序信号改为**查询-段连续余弦**（真正的读时投影，对应设计稿 §1.3）。
- 内嵌 CJK-aware 向量器 `_cjk_tokenize`（单字 unigram + 2gram）+ `_vectorize`（哈希 TF，维度 256），不依赖共享 embedder。
- 接入 `memory_layer_index.json`：L0 系统锚点 ×1.15 轻微加权（符合"系统锚点优先"设计）。
- 余弦全 0 时回退 ASCII 关键词重叠兜底。
- 修正 `estimate_compression`/`validate` 的段计数与标题提取。

## 验证结果（4 场景，文件级跑，规避 GBK 管道污染）
| 查询 | 全文 | 投影 | 比 | recalled | top 命中 |
|---|---|---|---|---|---|
| 钢印冲突怎么处理 | 84KB | 11.6KB | 0.137 | 8 | 钢印链条节律 / 钢印锚点系统 / 身份钢印 |
| 代谢通道优化 | 84KB | 12.8KB | 0.152 | 8 | 实现路线图 / 待办任务状态 / 钢印锚点 |
| 千问对话关于架构 | 84KB | 10.8KB | 0.128 | 8 | 关键决策 / 验证批次1+2 / 千问对话蒸馏 |
| 七七两岁成长小说 | 84KB | 11.5KB | 0.136 | 8 | 对话12记忆capstone / 根因分析 |

- 召回**查询相关且彼此区分**（不再是文档顺序前 8 段）。
- 降维 ~13%（满足 §1.4 "≤20KB / 降维有效" 验收）。
- `import` 正常，无新依赖。

## 落盘
- `src/memory_reader.py`：重写（修复版）
- `TODO_MASTER.md`：memory_reader 项打勾 [x]
- 临时诊断文件已清理

## 结论
记忆结构优化线的"读取侧"缺口已闭合。下一步可选：①Gateway 加载改造（H级，接 memory_reader 替代 MEMORY.md 全载）→ 待李奥签字；②分类侧目录归位（§1.2 tasks_deprecated/planning/logs）→ 尚未执行，属另一子任务。
