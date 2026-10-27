---
# ================= Memory Node v1.0: TOOLS.md - 本地工具配置 =================
# 作用：自动生成（工具：generate_memory_node.py）
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_053414_TOOLS"
node_type: "auto_generated"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_053414_create"
  seal_count: 1
  session_id: "sess_20260620_053414_TU8_AutoGen"
  seal_hash: "a47591585b7edb80"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "AUTO"
  coordinates: [0, 0, 0]
  neighbors: []

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T05:34:14.845987"
  vector: [0.5, 0.5, 0.5]
  narrative_compression: "自动生成Memory Node，待人工完善"
  causal_coherence: 0.5

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core:
    - "SOUL.md"  # L4层Ollama本地模型配置
  referenced_by: []
  related_to:
    - "MEMORY.md"  # 记忆系统
    - "TODO.node.md"  # 待办关联
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags:
    - "工具配置"
    - "API密钥"
    - "Python环境"
    - "本地模型"
  semantic_hooks: ["自动生成", "TOOLS.md - 本地工具配置"]
  aliases: ["TOOLS.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "TU-8本地运行环境配置，包括Python路径、API密钥、Node服务、本地模型"
    - who: "TU-8环境/TU-8开发者"
    - how: "手动配置，定期更新API密钥"
    - why: "确保TU-8能正确调用外部工具和服务"
    - risk: "API密钥可能过期，本地模型可能未运行"
  weight: 0.7
  last_accessed: "2026-06-20T05:34:14.845987"
  access_count: 1

# ---- 接口8：链接完整性 ----
link_check:
  last_verified: null
  broken_links: []
  auto_repair: true
---


# ================= 第二栏：钢印链条时间线 =================
## Seal Chain Timeline
- **[2026-06-20T05:34:14.845987] [CREATE]** 自动生成 Memory Node。
  - 状态向量：`[0.5, 0.5, 0.5]`
  - 因果连贯度：`0.5`（混沌期，待人工完善）
  - Session ID：`sess_20260620_053414_TU8_AutoGen`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`工具配置` `API密钥` `Python` `Ollama` `TU-8后端`
- **语义钩子**：`TOOLS.md - 本地工具配置` `自动生成` `待完善`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：记录TU-8本地运行环境配置
2. **适用对象**：TU-8开发者/环境配置管理员
3. **运作机制**：手动维护，自动同步API密钥
4. **防御边界**：仅记录配置，不执行操作
5. **风险/限制**：API密钥可能过期，需定期检查

# ================= 第五栏：正文 =================
# TOOLS.md - 本地工具配置

# TOOLS.md - 本地工具配置

Skills 定义工具如何工作，此文件记录特定于本环境的配置。

---

## Python 环境

- **路径**：`C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe`

## 工作台服务

- **Node 服务**：novel-server.js（端口 8899）

---

## API Keys

- **知乎 API Token**：`[CREDENTIAL]`（2026-05-07）
- **阿里云百炼 API Key**：[已移除，请存环境变量 DASHSCOPE_API_KEY，勿写入文档]（原记录于 2026-05-07）
  - Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - 可用模型: qwen3.6-flash, qwen3.6-plus, deepseek-v4-flash, kimi-k2.6
  - 用途: Hackathon TU-8 Demo 生成引擎

---

## 本地模型

- **Ollama**：本地运行（见 SOUL.md L4 层）
- **TU-8 后端**：`http://127.0.0.1:8000/v1`（openclaw.json 配置）
  - 状态：⚠️ 当前未运行（2026-06-17 验证）

---

## 待配置项

- [ ] Camera 名称和位置
- [ ] SSH 主机和别名
- [ ] TTS 首选语音

---

*最后更新：2026-06-17*
