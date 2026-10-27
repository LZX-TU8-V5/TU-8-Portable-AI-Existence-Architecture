---
# ================= Memory Node v1.0 接口规范 =================
# 作用：定义记忆节点如何接入钢印链条和知识网络
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份（Node Identity） ----
node_id: "mem_20260620_043800_template"  # 唯一ID（时间+类型+标题哈希）
node_type: template               # 节点类型: core/methodology/memory/experience/tool/template
node_status: active               # 状态: active/draft/archived/deprecated

# ---- 接口2：钢印链条挂载点（Seal Chain Hook） ----
seal_chain:
  parent_seal: null              # 父节点钢印（首次创建时为null）
  child_seals: []                # 子节点钢印列表
  current_seal: null             # 当前最新钢印
  seal_count: 0                  # 该节点经历的钢印次数
  session_id: null               # 会话ID（同一会话的修改共享此ID）
  # 钢印共振（Seal Resonance）说明：
  #   - 同一 session_id 的所有钢印，构成一次"认知迭代切片"
  #   - Agent 检索时，可通过 session_id 串联所有相关节点，还原"顿悟时刻（Aha Moment）"
  #   - 示例：同时修改 SOUL.md 和 L2_Methodology.md，共享 session_id，形成关联
  seal_hash: null                # 钢印哈希（防篡改，可选，P1功能）

# ---- 接口3：空间坐标（Spatial Coordinate in Memory Palace） ----
spatial:
  zone: "TEMPLATE"              # 记忆宫殿区域
  coordinates: [0, 0, 0]       # 3D空间坐标（待分配）
  neighbors: []                  # 空间邻居（强关联节点）

# ---- 接口4：状态向量快照（State Vector Snapshot） ----
state_vector:
  timestamp: null
  vector: []                     # 状态向量（待Agent填充）
  narrative_compression: ""       # 状态转移的语义描述
  causal_coherence: 0.0          # 因果连贯度（0-1），同时作为认知权重（Cognitive Weight）
  # 认知权重说明：
  #   - 0.8-1.0: 顿悟期（Agent对该知识理解通透，优先采纳）
  #   - 0.5-0.7: 平稳期（正常使用）
  #   - 0.3以下: 混沌期（当时理解不深，需结合新经验重新审视）

# ---- 接口5：知识网络链接（Knowledge Graph Links） ----
knowledge_links:
  supports_core: []              # 向上支撑的核心
  referenced_by: []              # 向下被引用的经验
  related_to: []                 # 平级关联
  similarity_links: []            # 语义相似节点（自动计算）

# ---- 接口6：防丢失兜底（Anti-Loss Fallback） ----
fallback:
  tags: ["#template", "#memory_node", "#v1.0"]
  semantic_hooks: ["记忆节点模板", "钢印链条挂载", "五栏结构"]
  aliases: []

# ---- 接口7：检索优化（Retrieval Optimization） ----
retrieval:
  dimension_digest:
    - what: "记忆节点标准接口模板"
    - who: "Agent开发者、知识库维护者"
    - how: "定义七组YAML接口，规范记忆节点格式"
    - why: "统一节点结构，实现钢印链条挂载"
    - risk: "模板过于 rigid 可能限制灵活性"
  weight: 0.5                   # 初始权重（0-1）
  last_accessed: null            # 最后访问时间
  access_count: 0                # 被访问次数

# ---- 接口8：链接完整性（Link Integrity） ----
link_check:
  last_verified: null
  broken_links: []
  auto_repair: true
---

# ================= 第二栏：钢印链条时间线（Seal Chain Timeline） =================
## Seal Chain Timeline（钢印链条时间线）
> 每次Agent修改此文件，自动在此追加一条钢印记录
> 增强功能（P0补充）：钢印共振（session_id）+ 认知权重（causal_coherence）

**（本文件为模板，尚未打钢印）**

<!-- 
示例（增强版）：
- **[2026-06-20T04:38:00] [CREATE]** 初始化记忆节点，挂载到钢印链条。
  - 父钢印：`null`
  - 状态向量：`[0.82, 0.45, -0.12]`
  - 叙事压缩：`从混沌到有序的方法论固化`
  - 因果连贯度：`0.95`（顿悟期，优先采纳）
  - Session ID：`sess_20260620_043800_TU8_Qwen`（钢印共振：同一会话的其他节点可通过此ID关联）
  - 钢印哈希：`a3f5...`（防篡改，P1功能）

- **[2026-06-21T09:12:33] [MODIFY]** 根据实战经验补充防断裂SOP。
  - 状态向量：`[0.79, 0.51, -0.08]`
  - 因果连贯度：`0.97`（顿悟期）
  - Session ID：`sess_20260621_091233_TU8_Qwen`（与SOUL.md共享，形成"顿悟时刻"切片）
  - 关联节点：[SOUL.md, L2_Methodology.md]（同一会话修改的其他节点）
-->

# ================= 第三栏：标签和钩子（Tags & Hooks） =================
## Tags & Hooks（标签和钩子）
- **核心标签**：`#template` `#memory_node` `#v1.0` `#seal_chain` `#five_column`
- **语义钩子**：`记忆节点模板` `钢印链条挂载` `五栏结构` `动态记忆网络` `Memory Node接口规范`

# ================= 第四栏：浓缩五维（5-Dimensional Digest） =================
## 5-Dimensional Digest（浓缩五维）
1. **核心目标 (What)**：定义记忆节点的标准接口规范，使其能挂载到钢印链条上。
2. **适用对象 (Who)**：TU-8 Agent开发者、知识库维护者、自动化脚本。
3. **运作机制 (How)**：通过八组YAML接口（身份、钢印、空间、状态、知识、兜底、检索、链接）实现结构化。
4. **防御边界 (Why)**：解决文档格式混乱、钢印记录丢失、路径断裂等问题，构建动态记忆网络。
5. **风险/限制 (Risk)**：模板较为严格，可能限制某些特殊文档的灵活性；需要Agent支持自动更新YAML字段。

# ================= 第五栏：正文（Main Content） =================
# Memory Node v1.0 接口规范详解

## 1. 设计理念

本模板将每个文档转化为一个**活的记忆节点**，通过以下机制实现动态记忆网络：

- **时间维度**：钢印链条（Seal Chain）- 记录节点的诞生、修改、迁移历史
- **空间维度**：记忆宫殿（Memory Palace）- 通过空间坐标实现启发式检索
- **语义维度**：知识图谱（Knowledge Graph）- 通过链接实现语义关联
- **状态维度**：状态向量（State Vector）- 记录Agent在每个时刻的内部状态

## 2. 接口说明

### 接口1：节点身份（Node Identity）
- `node_id`：全局唯一标识符，格式为 `mem_YYYYMMDD_HHMMSS_类型_标题哈希`
- `node_type`：节点类型，用于分类检索
- `node_status`：节点状态，支持生命周期管理

### 接口2：钢印链条挂载点（Seal Chain Hook）
- `parent_seal`：指向父节点的钢印（形成树状结构）
- `child_seals`：子节点钢印列表（支持一对多）
- `current_seal`：当前最新钢印（快速访问）
- `seal_count`：钢印计数（统计节点的修改次数）
- `session_id`：**钢印共振**（同一会话的修改共享此ID）

### 接口3：空间坐标（Spatial Coordinate）
- `zone`：记忆宫殿的区域划分（如 CORE、METHODOLOGY、MEMORY 等）
- `coordinates`：3D空间坐标 `[x, y, z]`，支持空间邻近性检索
- `neighbors`：空间邻居列表（强关联节点）

### 接口4：状态向量快照（State Vector Snapshot）
- `timestamp`：打钢印的时间戳
- `vector`：Agent内部状态向量（数值化"感受"）
- `narrative_compression`：状态转移的语义描述（人类可读）
- `causal_coherence`：**注意力权重**（高连贯度节点优先被检索）

### 接口5：知识网络链接（Knowledge Graph Links）
- `supports_core`：向上支撑的核心节点
- `referenced_by`：向下被引用的经验节点
- `related_to`：平级关联节点
- `similarity_links`：语义相似节点（自动计算）

### 接口6：防丢失兜底（Anti-Loss Fallback）
- `tags`：机器可读的标签（用于YAML过滤）
- `semantic_hooks`：人类可读的语义钩子（用于全盘扫描兜底）
- `aliases`：历史路径别名（防路径断裂）

### 接口7：检索优化（Retrieval Optimization）
- `dimension_digest`：浓缩五维（给Agent快速判断）
- `weight`：检索权重（可自动衰减）
- `last_accessed`：最后访问时间（用于LRU）
- `access_count`：被访问次数（用于 popularity 排序）

### 接口8：链接完整性（Link Integrity）
- `last_verified`：最后验证时间
- `broken_links`：断裂链接列表
- `auto_repair`：自动修复开关

## 3. 使用方式

### 3.1 创建新文件

1. 复制本模板到目标位置
2. 更新YAML头部的 `node_id`、`node_type`、`spatial.zone` 等字段
3. 填写第五栏正文内容
4. Agent首次保存时，自动生成第一条钢印记录（第二栏）

### 3.2 Agent自动更新（增强版）

当Agent修改基于此模板的文件时，应自动执行以下操作：

1. **生成新钢印**（增强：认知权重 + 钢印共振）：
   ```python
   new_seal = {
       "timestamp": "2026-06-20T04:38:00",
       "seal_type": "MODIFY",
       "state_vector": agent.get_current_state_vector(),
       "narrative_compression": agent.compress_narrative(),
       "causal_coherence": agent.calculate_coherence(),  # 认知权重
       "session_id": agent.current_session_id,            # 钢印共振
       "seal_hash": agent.calculate_seal_hash()          # 防篡改（P1）
   }
   ```

2. **更新YAML头部**：
   - `seal_chain.current_seal` = 新钢印ID
   - `seal_chain.seal_count` += 1
   - `seal_chain.child_seals`.append(新钢印ID)
   - `seal_chain.session_id` = 当前会话ID（用于钢印共振）
   - `seal_chain.seal_hash` = 新钢印哈希（防篡改）
   - `state_vector` = 新钢印的state_vector
   - `state_vector.causal_coherence` = 认知权重（影响检索优先级）
   - `retrieval.last_accessed` = 当前时间
   - `retrieval.access_count` += 1

3. **追加第二栏时间线**（增强：记录认知权重和钢印共振）：
   ```markdown
   - **[2026-06-20T04:38:00] [MODIFY]** 补充钢印共振机制。
     - Session ID：`sess_20260620_043800_TU8_Qwen`
     - 认知权重：`0.95`（顿悟期，优先采纳）
     - 状态向量：`[0.82, 0.45, -0.12]`
     - 关联节点：[SOUL.md, L2_Methodology.md]（同一会话修改的其他节点）
   ```

4. **钢印共振：记录关联节点**（新增）：
   ```python
   # 在同一会话中，如果修改了多个节点，建立双向链接
   if agent.current_session_id:
       related_files = agent.get_files_modified_in_session(agent.current_session_id)
       for related_file in related_files:
           if related_file != current_file:
               # 在两个节点的 YAML 中建立双向链接
               add_resonance_link(current_file, related_file, agent.current_session_id)
   ```

## 4. 迁移现有文件

将现有文件（如 `SOUL.md`）改造为记忆节点：

1. 在文件开头添加YAML头部（八组接口）
2. 将原有内容移动到第五栏（正文）
3. 提取或生成浓缩五维（第四栏）
4. 添加标签和钩子（第三栏）
5. 创建初始钢印记录（第二栏）

## 5. 验证清单

- [ ] YAML头部格式正确（八组接口完整）
- [ ] `node_id` 全局唯一
- [ ] `spatial.coordinates` 不与其他节点冲突
- [ ] 第二栏至少有一条钢印记录
- [ ] 第三栏包含特异性钩子（非通用词）
- [ ] 第四栏每项不超过20字
- [ ] 第五栏正文自然流畅

# ================= 底部：签名（Signature） =================
> **节点作者**：TU-8 Agent / 人类协作者
> **创建钢印**：未创建（模板文件）
> **最后钢印**：未创建（模板文件）
> **钢印次数**：0
> **版本**：v1.0
> **模板状态**：✅ 已发布（可正常使用）
