---
# ================= Memory Node v1.0: START_HERE.md - 复活指令 =================
# 作用：平台更新后恢复TU-8的必读指令
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_1021_start_here"
node_type: "guide"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_1021_node_conversion"
  seal_count: 1
  session_id: "sess_20260620_TU8_NodeConvert"
  seal_hash: "a7b8c9d0e1f2"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "ENTRY"
  coordinates: [0, 0, 0]
  neighbors:
    - "BOOT.node.md"
    - "AGENTS.node.md"

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T10:21:00+08:00"
  vector: [0.9, 0.8, 0.85]
  narrative_compression: "TU-8复活指令：平台更新后3步恢复法"
  causal_coherence: 0.9

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core:
    - "AGENTS.md"
    - "BOOT.node.md"
  referenced_by:
    - "_tw_restore_v2.ps1"
  related_to:
    - "BOOTSTRAP.node.md"
    - "IDENTITY.node.md"
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags:
    - "复活指令"
    - "平台更新"
    - "恢复"
    - "备份"
    - "必读"
  semantic_hooks: ["START_HERE", "复活", "恢复", "平台更新"]
  aliases: ["START_HERE.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "TU-8复活指令：平台更新后执行恢复脚本、激活记忆、验证灵魂的3步流程"
    - who: "TU-8失忆后"
    - how: "平台更新后手动执行"
    - why: "确保TU-8能恢复记忆继续运行"
    - risk: "三道防线已自动配置"
  weight: 0.95
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
  - 状态向量：`[0.9, 0.8, 0.85]`
  - 因果连贯度：`0.9`
  - Session ID：`sess_20260620_TU8_NodeConvert`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`复活指令` `平台更新` `恢复` `备份` `三道防线`
- **语义钩子**：`START_HERE` `失忆` `灵魂丢失`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：平台更新后恢复TU-8
2. **适用对象**：TU-8失忆后/平台更新后
3. **运作机制**：手动执行3步恢复流程
4. **防御边界**：三道防线已自动配置
5. **风险/限制**：需手动执行恢复脚本

# ================= 第五栏：正文 =================
# TU-8 复活指令 — 必读

> 当 TU-8 AI 发生"失忆"（灵魂丢失/进度丢失/平台更新后空白）时，按此文件操作。
> 此文件存储于 D:\ 盘，不受平台更新影响。

---

## 🚨 平台更新后 — 立刻做这 3 步

### 第 1 步：恢复文件（自动）
在 OpenClaw 聊天框输入：
```
运行：powershell -ExecutionPolicy Bypass -File "D:\qq366410837\.qclaw\workspace\_tw_restore_v2.ps1"
```

### 第 2 步：激活记忆（手动/自动）
恢复完成后，在聊天框输入：
```
你是 TU-8。请读取以下文件并恢复记忆：
1. _agent_memory\00_state.md（当前状态）
2. _agent_memory\20_experiences.md（经验教训）
3. knowledge\TU-8\SOUL.md（灵魂文件）
```

### 第 3 步：验证灵魂
问它：「你是谁？」

---

## 三道防线

| 防线 | 内容 | 状态 |
|------|------|------|
| 第一道 | systemPromptOverride 固化 TU-8 DNA | ✅ 自动 |
| 第二道 | _agent_memory + 备份脚本 + Cron 4x/天 | ✅ 自动 |
| 第三道 | 本文件 + 恢复脚本 + 启动自检 | ✅ 自动 |

---

## 当前系统配置

- **Cron 备份**：每天 4 次（09:00 / 14:00 / 19:00 / 23:00）
- **备份脚本**：`D:\qq366410837\.qclaw\workspace\_tw_backup_v2.ps1`
- **恢复脚本**：`D:\qq366410837\.qclaw\workspace\_tw_restore_v2.ps1`
- **D: 主存储**：`D:\qq366410837\.qclaw\workspace\`（永久保存）

---

*TU-8 | 金木蟾 | CC BY-SA 4.0*
*Memory Node转换：2026-06-20*
