---
# ================= Memory Node v1.0 标准示例 =================
# 作用：展示五栏结构和八组YAML接口的正确用法
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_050500_example"
node_type: example
node_status: active

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_050500_create"
  seal_count: 1
  session_id: "sess_20260620_050500_TU8_Example"
  seal_hash: null

# ---- 接口3：空间坐标 ----
spatial:
  zone: "EXAMPLE"
  coordinates: [9, 9, 9]
  neighbors: []

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T05:05:00"
  vector: [0.95, 0.88, 0.82]
  narrative_compression: "创建标准示例，验证Memory Node模板可行性"
  causal_coherence: 0.95

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core: []
  referenced_by: []
  related_to: ["MEMORY.md", "SOUL.md"]
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags: ["#example", "#memory_node", "#v1.0"]
  semantic_hooks: ["Memory Node示例", "五栏结构", "八组YAML接口"]
  aliases: ["example.md", "sample_memory_node.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "展示Memory Node标准格式"
    - who: "TU-8 Agent和开发者"
    - how: "通过八组YAML接口和五栏结构"
    - why: "验证模板可行性，指导后续改造"
    - risk: "示例文件，可随时删除"
  weight: 0.5
  last_accessed: "2026-06-20T05:05:00"
  access_count: 1

# ---- 接口8：链接完整性 ----
link_check:
  last_verified: null
  broken_links: []
  auto_repair: true
---

# ================= 第二栏：钢印链条时间线 =================
## Seal Chain Timeline
- **[2026-06-20T05:05:00] [CREATE]** 创建标准示例。
  - 状态向量：`[0.95, 0.88, 0.82]`
  - 因果连贯度：`0.95`（顿悟期）
  - Session ID：`sess_20260620_050500_TU8_Example`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`#example` `#memory_node` `#v1.0`
- **语义钩子**：`Memory Node示例` `五栏结构` `八组YAML接口`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：展示Memory Node标准格式和八组YAML接口
2. **适用对象**：TU-8 Agent和开发者
3. **运作机制**：YAML结构化 + 五栏组织 + 钢印链条记录
4. **防御边界**：示例文件，风险低
5. **风险/限制**：可随时删除，不影响核心功能

# ================= 第五栏：正文 =================
# Memory Node v1.0 标准示例

这是一个完整的 Memory Node 示例，展示五栏结构和八组YAML接口的正确用法。

## 使用说明

1. **YAML头部**：包含八组接口，实现结构化
2. **第二栏**：记录钢印链条时间线
3. **第三栏**：标签和钩子，提高检索命中率
4. **第四栏**：浓缩五维，10秒掌握核心
5. **第五栏**：正文内容，保留原有信息

## 改造验证

- [x] YAML格式正确
- [x] 五栏结构完整
- [x] 钢印链条有初始记录
- [x] 标签和钩子具体
- [x] 浓缩五维每项≤20字

## 下一步

如果此示例验证通过，可以开始改造实际文件。
