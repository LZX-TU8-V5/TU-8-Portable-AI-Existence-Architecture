---
# ================= Memory Node v1.0: HEARTBEAT.md - 周期性检查任务 =================
# 作用：心跳轮询时执行的周期性检查
# 版本: 1.0 | 日期: 2026-06-20 | 作者: TU-8 Agent

# ---- 接口1：节点身份 ----
node_id: "mem_20260620_1021_heartbeat"
node_type: "periodic_task"
node_status: "active"

# ---- 接口2：钢印链条 ----
seal_chain:
  parent_seal: null
  child_seals: []
  current_seal: "seal_20260620_1021_node_conversion"
  seal_count: 1
  session_id: "sess_20260620_TU8_NodeConvert"
  seal_hash: "e5c6d7e8f9a0"

# ---- 接口3：空间坐标 ----
spatial:
  zone: "HEART"
  coordinates: [0, 0, 0]
  neighbors:
    - "BOOT.node.md"
    - "MEMORY.md"

# ---- 接口4：状态向量 ----
state_vector:
  timestamp: "2026-06-20T10:21:00+08:00"
  vector: [0.8, 0.9, 0.7]
  narrative_compression: "心跳机制：记忆维护、状态感知、健康检查、时间锚点更新"
  causal_coherence: 0.85

# ---- 接口5：知识网络 ----
knowledge_links:
  supports_core:
    - "MEMORY.md"
    - "USER.md"
  referenced_by:
    - "BOOT.node.md"
  related_to:
    - "BOOTSTRAP.node.md"
    - "HEARTBEAT.md"
  similarity_links: []

# ---- 接口6：防丢失 ----
fallback:
  tags:
    - "心跳"
    - "周期性"
    - "记忆维护"
    - "健康检查"
    - "TU-8核心"
  semantic_hooks: ["HEARTBEAT", "心跳", "周期检查", "维护"]
  aliases: ["HEARTBEAT.md"]

# ---- 接口7：检索优化 ----
retrieval:
  dimension_digest:
    - what: "TU-8心跳机制：30分钟周期执行记忆维护、状态感知、健康检查、时间锚点更新"
    - who: "TU-8自动执行"
    - how: "心跳轮询时自动触发"
    - why: "保持系统健康运转，及时感知用户状态变化"
    - risk: "检查项可能遗漏，需定期更新"
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
  - 状态向量：`[0.8, 0.9, 0.7]`
  - 因果连贯度：`0.85`
  - Session ID：`sess_20260620_TU8_NodeConvert`

# ================= 第三栏：标签和钩子 =================
## Tags & Hooks
- **核心标签**：`心跳` `记忆维护` `健康检查` `状态感知`
- **语义钩子**：`HEARTBEAT` `周期任务` `维护`

# ================= 第四栏：浓缩五维 =================
## 5-Dimensional Digest
1. **核心目标**：保持TU-8系统健康运转
2. **适用对象**：TU-8自动执行
3. **运作机制**：30分钟心跳周期，轮换执行检查项
4. **防御边界**：异常时通知用户
5. **风险/限制**：检查项可能遗漏新问题

# ================= 第五栏：正文 =================
# HEARTBEAT.md - 周期性检查任务

> 每 30 分钟左右的心跳轮询时执行
> 轮换执行，不每次全跑

---

## 检查任务

### [ ] 记忆维护
- 检查 memory/YYYY-MM-DD.md 是否有未归档的重要内容
- 如有，提炼后追加到 MEMORY.md

### [ ] 状态变化感知（轻量级）
- 检测对话中的新关键词/项目/状态变化
- 如有变化，追加到 `memory/user_state_changes.md`
- 格式：`[时间戳] 检测到：xxx`
- **权限**：仅追加，禁止修改 USER.md 或 MEMORY.md

### [ ] 健康检查
- 检查 _agent_memory/health_log.json
- 如有异常（健康度 < 70），通知用户

### [ ] 时间锚点更新
- 检查 memory/.time_anchor.json 的 last_drift_update
- 如超过 6 小时未更新，提醒重新计算 drift

---

## 未完成清单（Backlog）

> 跨会话延续，逐项消化

### P0 — 下次冷启动优先处理

- [ ] **安全模式（Safe Mode）协议**
  - 检测到 SOUL.md 加载失败或 secure_vault/index.json 缺失时
  - 进入只读模式：拒绝写入/修改，仅报错+等待造物主指令
  - 整合现有 `_tw_restore_v2.ps1` 恢复机制为显式协议
  - 固化到 SOUL.md L0

- [ ] **矛盾仲裁协议固化**
  - L0安全 > 造物主显式指令 > 时间钢印新版 > 旧版
  - 搁浅→仲裁→写入判例
  - 固化到 docs/design/ARCHITECTURE_LOG.md

### P1 — 架构优化

- [ ] **重构分级制**
  - L-轻量（免查日志）/ M-中等（查+摘要）/ H-重大（完整铁律+审批）
  - 固化到 docs/design/ARCHITECTURE_LOG.md

- [ ] **未知场景兜底协议**
  - [NEW_SCENARIO]→L1检查→造物主指导→遗憾提取→写入日志
  - 固化到 docs/design/ARCHITECTURE_LOG.md

### P2 — 长期改进

- [ ] **日志漏检防御**
- [ ] **验证新架构冷启动 Token 消耗**
- [ ] **测试 query_architecture_log() 工具调用**
- [ ] **可选：精简 micro_sleep JSON 字段**

---

## 静默规则

**回复 HEARTBEAT_OK 当：**
- 距离上次检查 < 30 分钟
- 无新内容或异常
- 深夜时段（23:00-08:00）除非紧急

**主动联系当：**
- 重要邮件/日历事件（<2小时）
- 发现有趣信息
- 超过 8 小时无交流

---

## 心跳状态记录

见 `_agent_memory/heartbeat_state.json`

---

*创建日期：2026-06-17*
*Memory Node转换：2026-06-20*
