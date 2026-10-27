---
# ================= Memory Node v1.0: BOOTSTRAP.md - 首次初始化引导 =================
# 作用：首次启动时执行初始化
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_1021_bootstrap"
node_type: "checklist"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_1021_node_conversion"
  seal_count: 1
  session_id: "sess_20260620_TU8_NodeConvert"
  seal_hash: "d4b5c6d7e8f9"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "BOOT"
  coordinates: [0, 1, 0]
  neighbors:
    - "BOOT.node.md"
    - "IDENTITY.node.md"

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T10:21:00+08:00"
  vector: [0.85, 0.75, 0.8]
  narrative_compression: "首次启动初始化引导，完成后可归档"
  causal_coherence: 0.85

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core:
    - "IDENTITY.md"
    - "SOUL.md"
    - "MEMORY.md"
  referenced_by: []
  related_to:
    - "BOOT.node.md"
    - "HEARTBEAT.node.md"
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags:
    - "首次启动"
    - "初始化"
    - "冷启动"
    - "一次性"
  semantic_hooks: ["BOOTSTRAP", "初始化", "冷启动"]
  aliases: ["BOOTSTRAP.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "首次启动时的初始化检查清单，包括身份验证、记忆系统、安全边界、时间锚点、冷启动协议"
    - who: "TU-8首次启动"
    - how: "首次启动时一次性执行"
    - why: "确保TU-8能正常初始化运行"
    - risk: "一次性任务，完成后应归档"
  weight: 0.9
  last_accessed: "2026-06-20T10:21:00+08:00"
  access_count: 1

# ---- 接口8：链接完整性 ----
link_check:
  last_verified: null
  broken_links: []
  auto_repair: false
---


# ================= 第二栏：钢印链条时间线 =================
## Seal Chain Timeline
- **[2026-06-20T10:21:00+08:00] [CONVERT]** 转换为Memory Node格式。
  - 状态向量：`[0.85, 0.75, 0.8]`
  - 因果连贯度：`0.85`
  - Session ID：`sess_20260620_TU8_NodeConvert`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`首次启动` `初始化` `冷启动` `身份验证`
- **语义钩子**：`BOOTSTRAP` `初始化引导` `冷启动`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：TU-8首次启动时的初始化检查
2. **适用对象**：TU-8首次启动
3. **运作机制**：一次性执行，完成后归档
4. **防御边界**：初始化不完整则无法正常运行
5. **风险/限制**：一次性任务

# ================= 第五栏：正文 =================
# BOOTSTRAP.md - 首次初始化引导

> 此文件在首次启动时执行，完成后可删除或归档

---

## 初始化检查清单

### [ ] 1. 身份验证
- 确认 IDENTITY.md 已填写
- 确认 SOUL.md 版本号

### [ ] 2. 记忆系统
- 确认 MEMORY.md 存在
- 确认 memory/ 目录有今日日志文件

### [ ] 3. 安全边界
- 确认 secure_vault/keys.txt 存在
- 确认口令机制正常

### [ ] 4. 时间锚点
- 确认 memory/.time_anchor.json 存在
- 读取 drift 状态

### [ ] 5. 冷启动协议
- 运行 `python src/cold_start_gate.py check`
- 确认 session_mode.json 生成

---

## 完成后

- 将此文件移动到 archive/ 或删除
- 更新 _agent_memory/00_state.md 的启动时间

---

*创建日期：2026-06-17*
*Memory Node转换：2026-06-20*
