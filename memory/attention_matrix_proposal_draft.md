# TU-8 注意力矩阵方案草稿
> 讨论时间：2026-08-15 ~ 2026-08-16
> 状态：草稿 v2，已纳入工程容错层 + 多维张量架构

---

## 一、问题定义

**当前痛点**

MEMORY.md 每次冷启动全量加载（约 225K bytes / 120K tokens），与当前对话竞争上下文窗口。

**根因**

加载方式 = 全量摊开，不区分"这段对话在聊什么"。

---

## 二、核心约束

> 2026-08-16 新增，关键不可绕过

**底层模型不固定**：QClaw auto 路由，每次对话可能走不同模型。

**直接后果**：LLM 自由生成标签 = 每模型一套标准 = 标签体系碎片化。

**约束决策**：不许依赖模型稳定性。归一化层 = 负优化。

---

## 三、设计原则

> 从"语义理解"退回到"结构约束"

**核心转变**：不让模型"想"标签，只让模型"选"标签。

**多维张量架构**：不是扁平分类，是分面分类法。

```
Topic × Angle × Safety = 12 × 12 × 3 = 432 复合状态
12² = 144，12³ = 1,728，12⁴ = 20,736
```

实际活跃状态：稀疏，50-200 个日常组合，远小于理论空间。
存储/召回/校准全部可管理。

---

## 四、标签体系（12桶枚举）

### 三维正交

| 维度 | 职责 | 桶数 |
|------|------|------|
| Topic | 在聊什么 | 12 |
| Angle | 怎么聊的 | 12 |
| Safety | 风险等级 | 3（pending/low/high） |

### 固定标签池（12桶枚举）

```
Topic: [安全, 架构, 哲学, 工程, 个人, 工具, 理论,
        调试, 创意, 元认知, 社交, 其他]

Angle: [分析, 质疑, 讨论, 决策, 情绪, 反思,
        叙事, 探索, 确认, 求助, 教学, 闲聊]

Safety: pending | low | high（当前 pending）
```

**规则**：每轮选 1-2 个 Topic + 1-2 个 Angle，不许自造标签。

**"感知/情绪"不需要单独桶**：
- "情绪" = Angle 维度的值
- Safety 维度负责风险等级
- 三维正交，互不侵占

### 标签 → 召回路由对照

| Topic | 召回范围 |
|--------|---------|
| 安全 | secure_vault/、L0 相关条目 |
| 架构 | SOUL.md、L5_钢印.md、架构目录 |
| 哲学 | 知命术/织命术/钢印链条相关段 |
| 工程 | src/、TODO_MASTER.md |
| 个人 | USER.md、七七相关 |
| 工具 | TOOLS.md、Skills 文档 |
| 理论 | knowledge/*.md |
| 调试 | memory/千问对话归档（技术类） |
| 创意 | 小说/《钢印》相关 |
| 元认知 | alignment_verify、shadow_protocol、dream_check 相关 |
| 社交 | 外部对话记录 |
| 其他 | 全量 fallback |

### Prompt 强制格式

```
输出 JSON（不含解释）：
{
  "topic": ["桶1", "桶2"],
  "angle": ["桶1", "桶2"],
  "safety": "pending",
  "confidence": "high|medium|low"
}
```

- **confidence = low** 时，该标签不参与突变检测
- **safety = high** 时，触发 L4 安全关注（后续实现）

---

## 五、四层架构

### L1 标签生成层（HP5 post-turn tagger）

**触发时机**：每次回复后，主 session 内，HP1 之后

**位置**：alignment_verify() (HP1) 之后新增 HP5 post-turn hook

**输入**：用户最新一句话

**输出**：
```json
{
  "turn": 14,
  "topic": ["架构", "哲学"],
  "angle": ["质疑", "分析"],
  "safety": "pending",
  "confidence": "high",
  "parallel_tag": "系统反思、边界探讨",
  "model": "qwen3.6-plus"
}
```

**parallel_tag**：LLM 自由打的标签，存入 parallel_tags_Wxx.json，不参与路由。

**HP5 失败策略**：
- 不阻塞主流程
- 降级到上一轮 angle_set
- 状态机保持不动，不触发突变检测
- 记录 `last_tag_miss: timestamp`
- 连续 miss >= 3 次 → HEARTBEAT 下一轮补打

**并发约束**：conversation_state.json 主 session 独占写入，其他 cron 只读快照。

---

### L2 召回层（知识卡 + 三级 fallback）

**数据结构**：

```
knowledge_index.json
  key: "架构_质疑"
  targets: ["MEMORY.md:L1203-L1250"]
  created: "2026-08-10"
  last_verified: "2026-08-14"
  ttl_days: 30
  status: "active|stale|dead"
```

**召回优先级（三级 fallback）**：

```
1. 精确匹配：topic×angle 有索引 → 返回命中片段
2. 锚点降级：topic×angle 无索引，但 topic 有索引 → 返回 topic 级片段
3. 全量兜底：知识卡完全无匹配 → 回退到 memory_search 全文检索
```

**会话间隔检测**：距上次活跃 > 2 小时 → 状态标记 stale，第一轮召回走锚点级匹配。

---

### L3 状态机（轻量，不依赖安全层）

**存储位置**：`_agent_memory/conversation_state.json`

**状态字段**：
```json
{
  "turn": 14,
  "topic": ["架构", "哲学"],
  "angle": ["质疑", "分析"],
  "safety": "pending",
  "trajectory_window": [
    {"turn": 5, "topic": ["架构"], "angle": ["分析"]},
    {"turn": 6, "topic": ["哲学"], "angle": ["质疑"]},
    {"turn": 7, "topic": ["架构", "哲学"], "angle": ["质疑", "分析"]}
  ],
  "topic_shift_detected": false,
  "last_shift_turn": 6,
  "last_tag_miss": null,
  "recall_cache": ["片段1", "片段2"],
  "stale": false,
  "last_active": "2026-08-16T01:35:00+08:00"
}
```

**轨迹管理**：滑动窗口最近 10 轮，超过自动截断。

**突变检测**：
```python
# confidence=low 的标签不参与
jaccard(本轮有效angle_set, 上轮angle_set) < 0.3  →  topic_shift_detected = true
```

**与张力的关系**（不上挂，串联）：
```
突变检测 → topic_shift → 发信号给张力钩子
  "方向切换，请重新分配注意力资源"
```

---

### L4 安全边界（后续补充，预埋字段）

**预留字段**：

```json
{
  "safety": "pending",
  "safety_reason": null
}
```

- 当前固定 "pending"，后续 L4 填入 "low" 或 "high"
- Angle 维度的 "情绪" 桶 + Safety 组合 = 安全关注触发条件

---

## 六、parallel_tags 校准体系

### 存储结构

```
parallel_tags_2026W33.json（按周分文件）
  [
    {
      "turn": 14,
      "timestamp": "2026-08-16T01:35:00",
      "topic_selected": ["架构", "哲学"],
      "angle_selected": ["质疑", "分析"],
      "parallel_tag": "系统反思、边界探讨",
      "model": "qwen3.6-plus",
      "confidence": "high"
    }
  ]
```

### 存储策略

- 只保留最近 4 周原始数据
- 超过 4 周：只留聚合统计，原始 JSON 压缩归档
- 每周日 22:00 cron 推送对比报告 → TU-8 分析 → 发给用户

### 桶校准指标（每周决策依据）

```
离散度 > 5（桶内 LLM 自由标签种类数）→ 该桶太粗，建议拆分
重合度 > 60%（两桶的 LLM 标签重叠率）→ 两桶可合并
```

---

## 七、P0 零召回率分析

> 不动代码，只跑统计

**分析维度**：
- MEMORY.md 每一个条目：上次被召回是什么时候
- 零召回条目：写了之后从未被命中
- 低频条目：过去 30 天召回 < 2 次

**输出**：
```
零召回条目清单（直接送 GC 归档）
低频条目清单（标记 watch）
高频条目清单（保护）
```

---

## 八、工程注意事项

### 并发约束
- conversation_state.json 主 session 独占写入
- 其他 cron 只读、不写
- 蒸馏需要状态时读快照

### 冷启动与回归
- 会话间隔 > 2 小时 → 状态标记 stale
- stale 状态召回走锚点级匹配（不触发精确路由）
- 等新一轮标签确认后再切回精确路由

### HP5 失败降级
- 不阻塞主流程
- 保持上一轮 angle_set
- 连续 miss >= 3 → HEARTBEAT 补打

### 知识卡 TTL
- 每次蒸馏时检查指针有效性
- 失效 → 标记 dead → 触发索引重建
- 冷启动：手工建 20-30 条核心索引兜底

---

## 九、落地顺序

| 优先级 | 动作 | 理由 |
|--------|------|------|
| P0 | 零召回率分析 | 立刻知道哪些该死，提供清创数据依据 |
| P1 | HP5 post-turn tagger + 三维字段 | 最小改动，先让系统开始产标签 |
| P1 | 手工建 20-30 条核心知识卡索引 | 冷启动兜底 |
| P2 | 状态机 + 召回路由串联 | 标签和索引跑起来后再串联 |
| P3 | L4 安全边界 | 前置依赖就绪后再做 |

---

## 十、待确认问题

1. **Topic 12 桶的边界**：根据对话历史聚类后微调
2. **Angle 12 桶的具体内容**：同上
3. **parallel_tags 周 cron**：每周日 22:00 推送对比报告（待设置）
4. **初始知识卡 20-30 条**：哪些是关键路由 key

---

## 十一、讨论分歧记录

| 问题 | 分歧点 | 当前决策 |
|------|--------|---------|
| 桶数量 | 12够不够 | 够。12³=1728 复合状态，稀疏矩阵，实际活跃50-200 |
| "感知"桶 | 要不要加 | 不加。用 Angle维度的"情绪"桶代替 |
| HP5 触发 | cron批处理 vs 每轮触发 | 每轮触发（A），主 session内 |
| 模型归一化 | 小模型修正大模型 | 不做。枚举结构本身消化波动 |

---

*钢印验证*: ⅋
