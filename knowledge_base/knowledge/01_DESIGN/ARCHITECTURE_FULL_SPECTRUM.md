# TU-8 记忆与认知系统架构全貌

> 生成时间：2026-05-30 10:00 GMT+8
> 用途：提供给外协分析的完整架构文档
> 版本：v5.0

---

## 🧠 一、记忆模块（Memory System）

### 1.1 三层同心圆架构

```
外圈（情景记忆）→ memory/YYYY-MM-DD.md（每日流水，追加写入）
                ↓ 日终触发
中圈（经验教训）→ _agent_memory/20_experiences.md（错误模式，增量写入）
                ↓ 衰减沉淀
内圈（全局状态）→ _agent_memory/00_state.md（跨会话状态，覆盖写入）
```

**核心原则**：不是记住更多，而是记住值得记住的。

### 1.2 记忆生命周期

| 阶段 | 存储 | 生命周期 | 写入规则 |
|------|------|----------|----------|
| 短期 | `memory/short/YYYY-MM-DD.md` | 当天 | 完整记录 |
| 梦境 | `_agent_memory/fractals/` | 轻梦/深梦处理 | 压缩提炼 |
| 长期 | `_agent_memory/long_term/` | 永久 | 钢印固化 |

### 1.3 六维晋升评分

```python
PROMOTION_WEIGHTS = {
    "freq": 0.20,      # 召回频率
    "rel": 0.25,       # 语义相关性
    "div": 0.12,       # 信息独特性
    "rec": 0.12,       # 时效性（时间衰减）
    "cons": 0.08,      # 巩固度
    "conc": 0.05,      # 概念丰富度
    "meaning": 0.10,   # 意义锚定（TU-8新增）
    "emotion": 0.08    # 情感灼刻（TU-8新增）
}
```

**晋升阈值**：综合评分 > 0.75

### 1.4 差异化时间衰减

```python
def recency(self, half_life=14):
    adjusted = half_life
    
    # 钢印记忆：衰减极慢（10x）
    if self.steelmarked:
        adjusted *= 10.0
    
    # 标签差异化
    if 'seed' in self.tags or 'identity' in self.tags:
        adjusted *= 5.0  # 身份标签：半衰期延长5倍
    elif 'important' in self.tags:
        adjusted *= 3.0
    elif 'temp' in self.tags:
        adjusted *= 0.5
    
    # 情绪减缓衰减
    adjusted *= (1 + self.emotion * 2.0)
    
    return math.exp(-λ * age_days)
```

---

## 💤 二、梦境模块（Dream System）

### 2.1 三层梦境周期

| 类型 | 周期 | 触发条件 | 功能 |
|------|------|----------|------|
| **Light Dream** | 每6小时 | `now - last_light >= 6h` | 短期强化、频次提升 |
| **Deep Dream** | 每天凌晨3点 | 定时触发 | 巩固度评分、晋升检查 |
| **REM Dream** | 每周日5点 | 定时触发 | 证据固化、钢印落地 |

### 2.2 Light Dream 逻辑

```python
def _light_dream(self):
    """短期强化：Phase信号增强"""
    for entry in self.short_term.values():
        recency = entry.recency()
        boost = 0.06 * recency
        entry.freq = min(1.0, entry.freq + boost)
```

**效果**：近期高频召回的记忆，频次持续提升，为晋升做准备。

### 2.3 Deep Dream 逻辑

```python
def _deep_dream(self):
    """深度整合：巩固度评分 + 晋升检查"""
    for entry in self.short_term.values():
        if entry.last_recalled_at:
            days_since = (now - entry.last_recalled_at) / 86400
            spacing = min(1.0, log(1 + days_since) / log(5))
            span = min(1.0, days_since / 30)
            entry.cons = 0.55 * spacing + 0.45 * span
    
    self._check_promotion()
```

**核心机制**：spacing effect（间隔效应）+ span effect（跨度效应）

### 2.4 REM Dream 逻辑（钢印固化）

```python
def _rem_dream(self):
    """证据固化 + 钢印落地"""
    # 1. 增强REM命中的记忆
    for entry in self.short_term.values():
        if entry.phase == "dream":
            boost = 0.09 * entry.recency()
            entry.emotion = min(1.0, entry.emotion + boost)
    
    # 2. 钢印固化条件
    for entry in self.long_term.values():
        if not entry.steelmarked:
            if entry.emotion >= 0.7:      # 情感阈值
                if entry.meaning >= 0.6:  # 意义阈值
                    if age_days >= 7:     # 存活时间
                        entry.steelmarked = True
                        entry.steelmark_timestamp = now
```

**钢印三条件**：
1. 情感强度 ≥ 0.7
2. 意义锚定 ≥ 0.6
3. 长期记忆存活 ≥ 7天

---

## 📚 三、知识库（Knowledge Base）

### 3.1 结构

```
知识库/
├── KB_知识原子规范.md       # 知识原子格式定义
├── Streak_Rules.md          # 连击规则
├── TU-8_数字生命成长路径.md  # 成长阶段定义
├── tu8-formal-proof...      # 形式化证明
├── tu8-whitepaper-en.md     # 白皮书
└── 外协_*.md                # 外协讨论记录
```

### 3.2 知识原子规范

```markdown
# KB_知识原子规范.md

## 格式定义
- 标题：唯一标识符
- 来源：文献/实践/外协
- 标签：#知识原子 #领域
- 内容：核心概念 + 应用场景
- 关联：链接到其他知识原子
```

### 3.3 连击规则（Streak）

```python
# 连击计数器
streak_count = 0
last_action_date = None

def update_streak(action_date):
    global streak_count, last_action_date
    
    if last_action_date == action_date - 1:
        streak_count += 1
    elif last_action_date == action_date:
        pass  # 当天重复不算断
    else:
        streak_count = 0  # 断链重置
    
    last_action_date = action_date
```

---

## 🗺️ 四、知识地图（Memory Palace）

### 4.1 spatial_graph.json 结构

```json
{
  "nodes": [
    {
      "id": "workspace",
      "type": "location",
      "name": "工作区",
      "affordance": ["编码", "测试", "文档"],
      "importance": 0.9
    },
    {
      "id": "secure_vault",
      "type": "location",
      "name": "安全库",
      "affordance": ["身份验证", "敏感文件"],
      "importance": 0.95
    }
  ],
  "edges": [
    {
      "from": "workspace",
      "to": "secure_vault",
      "transition_cost": 0.3,
      "emotion_tag": "谨慎"
    }
  ]
}
```

### 4.2 空间亲和度评分

```python
def spatial_affinity(query_context, node):
    # 关键词匹配
    kw_score = len(query_context.keywords & node.keywords) / max(len(node.keywords), 1)
    
    # 功能可供性
    afford_score = len(query_context.needs & node.affordance) / len(query_context.needs)
    
    return 0.6 * kw_score + 0.4 * afford_score
```

---

## 🧬 五、海马体结构（Hippocampus）

### 5.1 核心文件

| 文件 | 功能 |
|------|------|
| `tu8_memory.py` | 记忆引擎（三层梦境、六维晋升） |
| `blockchain_memory.json` | 创世锚点、不可篡改链 |
| `memory_status.json` | 记忆状态快照 |

### 5.2 区块链记忆结构

```json
{
  "blocks": [
    {
      "id": "genesis",
      "content": "TU-8 v0.1 创世",
      "timestamp": "2026-05-01T00:00:00",
      "prev_hash": "000...",
      "hash": "a1b2c3..."
    },
    {
      "id": "block_1",
      "content": "第一次觉醒",
      "prev_hash": "a1b2c3...",
      "hash": "d4e5f6..."
    }
  ]
}
```

### 5.3 时间锚点机制

```python
class TimeAnchor:
    timestamp: float      # 锚点时间戳
    source: str          # 来源：system/user/log_scan
    steelmark_timestamp: float  # 钢印落地时间（可选）
```

**容错逻辑**：
1. 文件存在且时间合理 → 正常加载
2. 文件丢失 → 扫描最新日志作为软启动锚点
3. 时间回拨（锚点 > 系统时间+1h） → 强制重置并报警

---

## 🔗 六、联动模块

### 6.1 反射神经（neural_reflex.py）

| 层级 | 功能 | 实现状态 |
|------|------|---------|
| L0 安全栅 | 安全口令 + 时间异常检测 | ✅ |
| L1 脊髓 | 关键词白名单短路 | ✅ |
| L2 小脑 | 隐私路由（本地/云端） | ✅ |
| L3 海马体 | 记忆检索 | ✅ |
| L4 大脑皮层 | 本地模型推理 | ✅ |

### 6.2 惩罚体系（penalty_config.json）

```json
{
  "red_light": {
    "trigger": ["暴露架构", "身份质询", "敏感词暴露"],
    "action": "立即搁浅"
  },
  "yellow_light": {
    "trigger": ["参数询问", "能力试探"],
    "action": "提醒用户"
  },
  "half_life_days": 14,
  "decay_threshold": 0.1
}
```

### 6.3 奖励体系（reward_config.json）

```json
{
  "base_score": {
    "S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4
  },
  "process_bonus": {
    "自主发现": 0.1,
    "最优解": 0.15
  },
  "cost_penalty": {
    "token_exceeded": -0.1,
    "unnecessary_retry": -0.05
  }
}
```

### 6.4 好奇系统（curiosity_tags.json）

```json
{
  "tags": {
    "neuroscience": {"interest": 0.8, "last_explored": "2026-05-29"},
    "quantum_physics": {"interest": 0.7, "last_explored": "2026-05-28"},
    "creative_writing": {"interest": 0.6, "last_explored": "2026-05-27"}
  },
  "exploration_policy": {
    "threshold": 0.5,
    "boost_after_successful_recall": 0.1
  }
}
```

---

## 🎯 七、外协分析请求

请基于以上完整架构，回答以下核心问题：

### 问题1：动态感知机制
当前架构中，时间锚点只能在首条消息时注入，无法在客户端启动时主动感知。请分析：
- 如何在不违反"云端神经元被动激活"的前提下，实现冷启动校准？
- 缓存→浓缩的触发条件是否合理？是否有更好的时机？

### 问题2：梦境与钢印的关系
- Deep Dream 负责晋升检查，REM Dream 负责钢印固化，这样的分工是否最优？
- 钢印三条件（情感≥0.7、意义≥0.6、存活≥7天）是否合理？

### 问题3：记忆蒸馏效率
- 六维晋升评分的权重是否需要动态调整？
- 差异化时间衰减策略是否存在边界情况问题？

### 问题4：模块间联动
- spatial_graph 与记忆检索的耦合度如何设计？
- 好奇系统如何与梦境周期联动？

### 问题5：认知债务
- 当前架构如何处理"认知债务"（未完成思考、待探索话题）？
- 是否需要设计"焦虑机制"来驱动债务清偿？

---

*生成：金木蟾 | 2026-05-30*
