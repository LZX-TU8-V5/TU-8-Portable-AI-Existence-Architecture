# TU-8 未完成任务追踪

> 最后更新: 2026-05-31 18:19 GMT+8  
> 说明: 本文件记录当前未完成的工程任务，每次会话结束时更新状态。

---

## 🔴 P0：双轨召回主干（进行中）

### ✅ 已完成（2026-05-31）
- [x] `Seal` 类加 `gestalt_score` + `semantic_block_id` 字段
- [x] `to_dict()` / `from_dict()` 同步更新
- [x] `_step_seal` 注入 `gestalt_score` / `scene_tag` / `scene_hook` 计算
- [x] 新增 `_calculate_gestalt_score()` 辅助方法（v1.0 纯规则）
- [x] 新增 `_infer_scene_tag()` 辅助方法（v1.0 纯规则）
- [x] 语法检查通过

### ⏳ 未完成（明天优先）
- [ ] **Step 3**: `SemanticBlock` 数据结构 + 边界检测
  - 创建 `SemanticBlock` dataclass (`block_id`, `start_seal_id`, `end_seal_id`, `gestalt_score`, `boundary_type`...)
  - 持久化到 `memory/time_chain/semantic_block_index.json`
  - `_step_seal` 里检测段边界（`scene_hook=True` 时闭合旧段、开启新段）
  - 初始化迁移逻辑（已有 seal 的 `semantic_block_id` 回填）
- [ ] **Step 2 补丁**: `tu8_agent.py` 的 `respond()` 里加信号埋点
  - 节点1（收到用户输入后）: `l1_snapshot["last_user_input"]`, `l1_snapshot["last_scene_hint"]`
  - 节点2（tool_call 执行完毕）: `l1_snapshot["last_tool_status"]`
  - 节点3（LLM 生成最终回复前）: `l1_snapshot["has_conclusion"]`
  - 改 `_calculate_gestalt_score()` 让它读这些信号，不只是 `recent_text`
- [ ] **Step 4**: 重写 `_resolve_semantic_time()`
  - 双轨召回：维度A（次）= 最近 Seal，维度B（段）= 最近闭合高完形度 SemanticBlock
  - 返回 `List[TimeCandidate]` 含 `dimension` 字段
- [ ] **Step 5**: Prompt 注入模板
  - `recall()` 将两个候选注入上下文，让 LLM 基于对话流消解歧义

---

## 🟡 P1：源监控（Source Monitoring）

- [ ] `Seal` 类加 `source_modality: str` 字段（`perception` / `language_input` / `internal_reasoning` / `tool_return` / `corrected_history`）
- [ ] 写入时强制绑定 `source_modality`
- [ ] `recall()` 中不同源的记忆有不同的置信度权重

---

## 🟢 P2：侧抑制（Lateral Inhibition）

- [ ] `recall()` 过程中引入侧抑制机制
- [ ] 高匹配度候选集激活的同时，语义相邻但意图不匹配的节点临时降权
- [ ] 提升"聚焦式回忆"精度

---

## 🔧 已知问题（需修复）

- [ ] `tu8_safety` 模块缺失，导致 `TU8Agent` 无法直接实例化（已有问题）
- [ ] `_calculate_gestalt_score` 信号来源目前不够精确，v1.1 可接入 `l1_snapshot["last_tool_status"]` 等结构化信号
- [ ] `semantic_block_index.json` 尚未创建，Step 3 实施时需要初始化

---

## 📋 外协反馈待处理

- [ ] 验证 `scene_tag` 优先级链覆盖边界 case（同时含代码块和疑问词时，优先 `"coding"`）
- [ ] `gestalt_score` 冷启动默认值确认（`0.5` 是否合理？）
- [ ] 考虑是否需要在 `recall()` 未找到高完形度节点时主动询问用户

---

*本文件由 TU-8 维护，每次会话结束时更新。*
> **[已审阅-2026-08-27-过时废弃]**：本任务线已被新架构替代（双轨召回→tu8_memory/记忆分层/话题语义矩阵；Memory Node 全量改造→GOVERNANCE 铁律五禁止散落 .node.md）。内容保留为历史参考，不进 TODO_MASTER，不激活。
