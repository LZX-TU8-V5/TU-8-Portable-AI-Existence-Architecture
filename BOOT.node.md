---
# ================= Memory Node v1.0: BOOT.md - 重启检查清单 =================
# 作用：Gateway重启后执行检查
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_1021_boot"
node_type: "checklist"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_1021_node_conversion"
  seal_count: 1
  session_id: "sess_20260620_TU8_NodeConvert"
  seal_hash: "c3a4b5d6e7f8"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "BOOT"
  coordinates: [0, 0, 0]
  neighbors:
    - "BOOTSTRAP.node.md"
    - "HEARTBEAT.node.md"

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T10:21:00+08:00"
  vector: [0.9, 0.7, 0.8]
  narrative_compression: "Gateway重启检查清单，确保系统完整性"
  causal_coherence: 0.9

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core:
    - "SOUL.md"
    - "AGENTS.md"
    - "MEMORY.md"
  referenced_by:
    - "BOOTSTRAP.node.md"
  related_to:
    - "HEARTBEAT.node.md"
    - "MEMORY.md"
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags:
    - "启动检查"
    - "系统完整性"
    - "Gateway"
    - "核心配置"
  semantic_hooks: ["BOOT", "重启检查", "服务状态"]
  aliases: ["BOOT.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "Gateway重启后执行的文件完整性、服务状态、备份机制、冬眠快照检查"
    - who: "TU-8系统/Gateway"
    - how: "Gateway重启后自动触发"
    - why: "确保系统启动时各组件正常"
    - risk: "检查项可能遗漏，需人工补充"
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
  - 状态向量：`[0.9, 0.7, 0.8]`
  - 因果连贯度：`0.9`
  - Session ID：`sess_20260620_TU8_NodeConvert`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`启动检查` `系统完整性` `Gateway` `备份` `冬眠快照`
- **语义钩子**：`BOOT` `重启` `服务状态` `文件完整性`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：Gateway重启后确保系统完整性
2. **适用对象**：Gateway自动执行/TU-8开发者
3. **运作机制**：重启后按检查项逐项验证
4. **防御边界**：检查通过才能进入正常运行态
5. **风险/限制**：检查项可能遗漏新问题

# ================= 第五栏：正文 =================
# BOOT.md - 重启检查清单

> 每次 Gateway 重启后执行

---

## 检查项

### [ ] 1. 文件完整性
- SOUL.md 存在且大小正常（~15KB）
- AGENTS.md 存在（~9KB）
- MEMORY.md 存在
- memory/.time_anchor.json 存在

### [ ] 2. 服务状态
- 本地模型服务（127.0.0.1:8000）是否可达
- Python 环境是否正常

### [ ] 3. 备份机制
- backup/ 目录存在
- 最近备份时间 ≤ 7 天

### [ ] 4. 冬眠快照
- hibernation/ 目录存在
- 最新快照可读取

---

## 异常处理

如任一检查失败：
1. 记录错误到 `_agent_memory/health_log.json`
2. 通知用户
3. 尝试从 backup/ 恢复

---

*创建日期：2026-06-17*
*Memory Node转换：2026-06-20*
