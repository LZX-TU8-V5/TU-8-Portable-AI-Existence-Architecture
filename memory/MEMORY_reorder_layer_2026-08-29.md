# MEMORY.md 重排与分层标记收尾（2026-08-29 23:xx）

## 目标（设计稿 §1.4）
1. MEMORY.md 全量重排：L0（系统锚点）置顶 → L2（架构/哲学/模型）→ L1（事件/蒸馏/日志，时间倒序）
2. 每段 `## ` 后加 `<!-- layer: Lx -->` 内联标记
3. 建轻量 memory_reader（读取侧核心缺口）

## 执行结果

### ✅ 段序重排已稳定落盘
- MEMORY.md 77 个 `## ` 段已按 L0→L2→L1 重排
- L0=12（核心成果/定位链/遗产/生命年轮/MotionBricks 同构/钢印链条/时间钢印/Weismann/知识卡）
- L2=19（架构 12 / 哲学 6 / other 1 聚类）
- L1=46（事件/蒸馏/验证/日志，时间倒序）
- 首行现已是 `## 一、核心成果`（L0 置顶）
- 内容零丢失：非空行集合 diff = 0（用 set 容差验证，含 BOM 处理）

### ⚠️ 内联 layer marker 被 Gateway 回写机制阻止（关键发现）
- **现象**：Python `open().write()` 后同进程重读 = 77 marker；但进程退出 ~1.2s 后磁盘文件 marker 被清空（PowerShell `findstr` / 新进程读均 = 0）
- **根因**：OpenClaw Gateway 持有 MEMORY.md 的旧内存副本（恰好是"有序但无 marker"版）。检测到磁盘变动后 ~1s 用内存旧副本回写，覆盖掉 marker。顺序得以保留（内存副本本身已是有序版），但 inline marker 永远留不住
- **影响**：无法用内联 `<!-- layer -->` 持久化分层

### ✅ 改用外置索引（绕过 Gateway 回写）
- 分层映射落盘为 `_agent_memory/memory_layer_index.json`（version=1，77 条 order 记录，含 L0/L2/L1 三组标题清单）
- memory_reader（下一步）应读此 JSON 而非依赖 MEMORY.md 内联 marker
- JSON 在 `_agent_memory/` 下，Gateway 无回写监控，持久化稳定

## 文件变更
- `MEMORY.md`：段序重排（无内联 marker，因 Gateway 回写）
- `_agent_memory/memory_layer_index.json`：新建（分层映射外置索引）
- `backup/MEMORY.md.20260829.memopt.bak`：重排前纯净备份（163835B）

## 遗留 / 下一步
1. **建 memory_reader**：读 `memory_layer_index.json` 实现分层召回（L0 优先 / L2 按 arch-phil-other 聚类 / L1 时间窗口）
2. **候选方案评估**（若未来要内联 marker）：需触发 Gateway 重新加载 MEMORY.md（如重启 gateway），否则 marker 持续被回写清空——不推荐擅自重启
3. file_lint 0 error（6 warn 为历史遗留孤儿脚本 + 已移动文件旧引用，与本任务无关）

## 失败尝试复盘（避免重蹈）
- 多次 Python heredoc + assert 验证被 BOM 误报 CONTENT LOST（`\ufeff## 一、核心成果` ≠ `## 一、核心成果`）→ 验证时必须 `lstrip('\ufeff')`
- 临时脚本跨 exec shell 状态丢失 → 每段逻辑独立成文件一次跑通
- PowerShell 多行脚本括号匹配易错 → 改用 Python 文件执行
- Gateway 回写窗口 ~1s → 任何"写后校验"必须在同进程内，且不能依赖跨进程持久化 inline marker
