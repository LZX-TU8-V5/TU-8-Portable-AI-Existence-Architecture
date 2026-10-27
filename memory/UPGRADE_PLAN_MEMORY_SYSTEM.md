# 记忆系统升级方案 - 待整合

> 日期：2026-06-07
> 状态：**方案已确定，待落地**
> 来源：外协讨论 + TU-8 现有架构 + 用户确认

---

## 〇、关键决策：云端结构化输出

### 问题发现

**现状**：微睡眠的 `_evaporate()` 是本地启发式截断，只能丢信息，不能提炼。

**用户洞察**：
> 微睡眠的总结应该是云端输出的结构中总结的。
> 云端输回来的是 A+B+C+····等（场景+事件+问题+解决方案+反馈+结论）
> 这样肌肉在做事时候就不容易幻觉。

### 核心原则

> **云端只做结构化提取（填空者），肌肉只做机械式拼装（打字机）。**

### 6要素微睡眠载荷（Micro-sleep Payload）

```json
{
  "context": "场景",
  "trigger_event": "事件",
  "core_problem": "问题（需要解决的问题，可为 null）",
  "proposed_solution": "解决方案（建议，可为 null）",
  "env_feedback": "反馈（分析现有结构/环境）",
  "self_consistent_conclusion": "结论（动态自洽结论）"
}
```

### 云端约束（最高优先级指令）

```
【核心系统指令】：
在执行任何微睡眠总结、复盘或状态更新时，严禁输出自然语言段落。
必须且只能输出符合规范的 JSON 载荷。
若某字段无有效信息，严格返回 null，绝不允许编造。
```

### 为什么这样做极高明？

| 优势 | 说明 |
|------|------|
| **锁死幻觉源头** | 云端只能做填空题，每个字段有明确语义边界 |
| **极高检索价值** | 可以直接 SQL 查询 `WHERE core_problem LIKE '%xxx%'` |
| **无缝对接梦境期** | 白天收集的是结构化积木，晚上可以批量聚类提炼 SOP |

### 现状 vs 目标

| 环节 | 现状 | 目标 |
|------|------|------|
| 微睡眠总结 | 本地启发式截断（`_evaporate`） | 云端结构化 JSON（6要素） |
| 云端职责 | 自由文本输出 | 结构化提取（填空者） |
| 肌肉职责 | 截断文本 | 校验 + 打钢印 + 落盘（打字机） |
| 梦境期 | 无 | 聚类 + 提炼 SOP |

---

## 一、核心方案

### 1. 双轨隔离原则

| 轨道 | 触发时机 | 人设 | Temperature | 产出 |
|------|---------|------|-------------|------|
| **日常流水线** | 微睡眠结束 | 书记员 | ≤ 0.2 | YAML + MD |
| **梦境流水线** | 全天复盘/创造指令 | 炼金术士 | ≥ 0.7 | 洞察报告 + #Hypothesis |

**核心原则**：
- 日常：严禁发散联想，只做实体抽取、状态更新、冲突检测
- 梦境：允许跨域联想、SOP提炼、隐性规律挖掘
- 梦境产出必须打上 `#Hypothesis` 标签，次日人工审阅后方可晋升

---

### 2. 微睡眠完整流程

```
┌─────────────────────────────────────────────────────────────────┐
│  微睡眠（云端职责）                                               │
│  ─────────────────────────────────────────────────────────────  │
│  输入：原始对话/操作日志                                          │
│  输出：标准化 JSON（6要素）                                       │
│                                                                 │
│  约束：必须输出 JSON，禁止自然语言段落                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  肌肉（本地脚本职责）                                             │
│  ─────────────────────────────────────────────────────────────  │
│  1. 校验格式：检查 JSON 是否包含必填字段                          │
│  2. 生成钢印：时间戳 + 哈希                                      │
│  3. 格式化落盘：YAML 机器轨 / MD 人轨                            │
│  4. 存入 seal_chain：追加到钢印链                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3. 三阶段记忆整合（全天复盘/梦境期）

```
┌─────────────────────────────────────────────────────────────────┐
│  阶段1：浅睡期 (Light Sleep) — 筛选与入眠                         │
│  ─────────────────────────────────────────────────────────────  │
│  输入：seal_chain 中当日所有 Seal                                 │
│  处理：                                                          │
│    1. 语义相似度过滤（去重，阈值 0.9）                             │
│    2. 噪音剔除（一次性调试、临时闲聊）                              │
│    3. 生成【候选记忆列表】                                         │
│  产出：candidate_memories[]                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段2：REM期 — 反思与连梦                                        │
│  ─────────────────────────────────────────────────────────────  │
│  输入：candidate_memories[]（结构化 JSON 积木）                   │
│  处理：                                                          │
│    1. 聚类：按 context/core_problem 聚合同类微睡眠                │
│    2. 找规律：云端分析同类记录，抽象通用处理流程                    │
│    3. 生成 SOP JSON：                                            │
│       {                                                          │
│         "sop_name": "xxx",                                       │
│         "trigger_condition": "xxx",                              │
│         "action_steps": [...],                                   │
│         "expected_outcome": "xxx",                               │
│         "source_evidence_ids": ["seal_001", "seal_002"]          │
│       }                                                          │
│    4. 冲突检测（Diff + 时间戳/证据数）                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段3：深睡期 (Deep Sleep) — 固化与遗忘                          │
│  ─────────────────────────────────────────────────────────────  │
│  输入：阶段2产出                                                   │
│  处理：                                                          │
│    1. 权重计算：Score = W × e^(-λt) + freq_bonus                  │
│    2. 生命周期管理：                                              │
│       - W >= 阈值 → 固化为长期记忆                                 │
│       - W < 阈值 → 打入冷宫/遗忘                                   │
│    3. 置信度衰减模型初始化                                         │
│  产出（双轨输出）：                                                │
│    - 人轨：memory/YYYY-MM-DD_review.md（叙事散文）                 │
│    - 机器轨：memory/YYYY-MM-DD_review.yaml（结构化数据）            │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4. 记忆代谢三回路

```
写入 → 提取 → 更新 → 丢弃
  │                │                        │                    │
  │                │                        │                    ├─ 硬删除（Score < 0.3 + 已失效）
  │                │                        │                    │
  │                │                        └─ 软删除（打入冷宫/COLD）
  │                │
  │                └─ 语义合并（相似度 > 0.78 → 蒸馏成高密度节点）
  │
  └─ 动态降权（指数衰减 + 频次奖励）
```

**衰减公式**：
```
Score = W_importance × e^(-λ·t) + W_freq_bonus
```

- W_importance：初始重要度权重（架构决策=0.9，日常闲聊=0.3）
- e^(-λ·t)：艾宾浩斯遗忘曲线
- W_freq_bonus：频次奖励分（被检索命中的次数）

---

### 5. 防过拟合机制

| 机制 | 实现 |
|------|------|
| 上下文边界绑定 | 提取的模式必须包含 If + Scope + Then |
| 证据频次阈值 | evidence_count >= 3 才能晋升为 established_pattern |
| 例外值保留 | 偏离主流模式的单独归类为 exceptions |
| 置信度衰减 | 每次成功调用分数上升，失败则指数下降 |

---

### 6. 冲突检测：极简版

> **宁可分裂，不捏造缝合真理。**
> **Diff + 时间戳/证据数，不用 LLM 仲裁。**

```
冲突判定（只看两个硬指标）：
1. 比时间戳：谁的时间晚，听谁的
2. 比证据数：如果时间一样，谁的 evidence_count 多，听谁的

处理结果：
- 没冲突/一方完胜 → 赢家留下，输家丢进垃圾桶
- 真打架了 → 拒绝合并！保持分裂 + [需人工确认]
```

---

## 二、机器轨 YAML 最终结构

```yaml
# ===== 基础元数据 =====
date: "2026-06-07"
total_micro_sleeps: 12
system_metrics:
  total_destruction_ratio: 0.35
  total_freed_tokens: 4200

# ===== 核心资产 =====
daily_assets:
  narrative_summary: "今日完成了..."
  seal_chain_ids:
    - "seal_20260607_001"
    - "seal_20260607_002"

# ===== 结构化记忆块 =====
memory_blocks:
  - task_id: "T001"
    # 6要素（来自微睡眠 JSON）
    context: "爬虫任务"
    trigger_event: "遇到 Cloudflare 拦截"
    core_problem: "IP被封禁导致请求失败"
    proposed_solution: "增加随机休眠时间至 5-10秒"
    env_feedback: "代理池剩余可用IP仅20个"
    self_consistent_conclusion: "牺牲速度换取稳定性是唯一可行解"
    
    # 元数据
    tags: ["#Project_Crawler", "#Pattern_RateLimit"]
    entities: ["Cloudflare", "代理池"]
    
    # 证据与置信度
    evidence_count: 3
    status: "established_pattern"  # 或 hypothesis
    confidence_score: 0.85
    
    # 例外情况（反向边界）
    exceptions:
      - condition: "xxx场景下不适用"
        alternative_action: "改用yyy"
        source_seal_id: "seal_20260607_015"

# ===== 提炼出的 SOP =====
sops:
  - sop_name: "Cloudflare 反爬动态休眠策略"
    trigger_condition: "当遇到 IP 封禁报错，且代理池可用IP < 30%"
    action_steps:
      - "立即暂停当前请求队列"
      - "随机休眠 5-10秒"
      - "切换备用代理节点后重试"
    expected_outcome: "以牺牲 10% 速度为代价，换取连接存活率提升至 95%"
    source_evidence_ids: ["seal_20260607_002", "seal_20260607_015"]

# ===== 冲突解决记录 =====
conflicts_resolved:
  - old_fact: "旧版..."
    old_fact_id: "seal_20260605_003"
    new_fact: "新版..."
    new_fact_id: "seal_20260607_012"
    resolution_type: "supersedes"
    arbiter_reasoning: "用户明确要求"
```

---

## 三、现有架构分析

### 1. consciousness_cycle.py 已实现

| 组件 | 状态 | 说明 |
|------|------|------|
| 四阶段睡眠框架 | ✅ 已实现 | AWAKE → LIGHT_SLEEP → DEEP_SLEEP → HIBERNATION |
| 微睡眠六步流水线 | ✅ 已实现 | FREEZE → COMPRESS → ALIGN → SEAL → RELEASE → RESTORE |
| seal_chain | ✅ 已实现 | 钢印链，每次微睡眠追加一个 Seal |
| DEEP_SLEEP | ⚠️ 部分实现 | 有框架，但整合逻辑不完整 |

### 2. 待补充/增强

| 功能 | 现状 | 方案建议 |
|------|------|---------|
| **微睡眠输出格式** | 本地启发式截断 | **云端结构化 JSON（6要素）** |
| **云端约束** | 无 | **SOUL.md 添加最高优先级指令** |
| 全天复盘触发 | 有规则（SOUL.md） | 需要实现三阶段整合逻辑 |
| 日常/梦境双轨 | 无 | 需要在 SOUL.md 添加原则 |
| 语义去重 | 无 | REM期需要实现相似度检测 |
| 权重衰减 | 无 | 深睡期需要实现衰减公式 |
| 双轨输出 | 无 | 需要生成 MD + YAML |
| 冲突检测 | 无 | 需要实现极简版 Diff |

### 3. 高度耦合点

- consciousness_cycle.py 与 cognitive_evaluator.py 深度集成
- seal_chain 与 time_chain 耦合
- 记忆系统与意识循环是**单循环双相位**，不可拆分

---

## 四、落地路线（已确定）

### 路线：以 C 为起手式，向 A 平滑过渡

#### 第一步（执行方案 C）

1. **不动 consciousness_cycle.py 核心代码**
2. **在 SOUL.md 中写入云端约束**：
   - 微睡眠输出必须为 6要素 JSON
   - 双轨隔离原则
3. **今晚触发全天复盘时手动执行**
4. **验证**：
   - 云端是否输出结构化 JSON
   - 极简版冲突检测是否生效
   - MD + YAML 是否符合预期

#### 第二步（落地方案 A）

如果方案 C 验证成功：

1. **补充 consciousness_cycle.py**：
   - COMPRESS 阶段：接收云端 JSON，不再本地截断
   - DEEP_SLEEP 阶段：补充三阶段整合逻辑
2. **新增文件**：
   - `memory/YYYY-MM-DD_review.md`（人轨）
   - `memory/YYYY-MM-DD_review.yaml`（机器轨）

---

## 五、Seal 结构扩展（组合封装）

### 问题

`narrative_compression` 原本是自然语言摘要，不能直接塞 JSON。
需要新增字段存储 6要素，同时保持钢印链完整。

### 方案：组合封装法

```python
from dataclasses import dataclass, field
from typing import Optional

# 1. 定义云端输出的标准契约（强类型约束）
@dataclass
class MicroSleepPayload:
    context: str = ""
    trigger_event: str = ""
    core_problem: Optional[str] = None
    proposed_solution: Optional[str] = None
    env_feedback: str = ""
    self_consistent_conclusion: str = ""

# 2. 扩展 Seal 类，将契约嵌入信任链
@dataclass
class Seal:
    # --- 原有信任链核心（绝对不动）---
    seal_id: str = ""
    parent_seal_id: str = ""
    seal_hash: str = ""
    
    # --- 原有状态与叙事（保留）---
    state_vector: StateVector = field(default_factory=StateVector)
    narrative_compression: str = ""  # 人轨摘要（一句话概括）
    
    # --- 新增：云端结构化提取结果 ---
    micro_sleep_payload: Optional[MicroSleepPayload] = None
```

### 优势

| 优势 | 说明 |
|------|------|
| **链条不断** | `micro_sleep_payload` 成为 Seal 一部分，完整性受 `seal_hash` 保护 |
| **双轨兼容** | 机器轨读 `micro_sleep_payload.core_problem`，人轨读 `narrative_compression` |
| **符合开闭原则** | 不破坏原有字段，只是扩展 |

### 肌肉端组装逻辑

```python
import json

# 1. 解析云端返回的 JSON
payload_dict = json.loads(cloud_response)
payload = MicroSleepPayload(**payload_dict)

# 2. 生成钢印
seal = Seal(
    seal_id=generate_id(),
    parent_seal_id=last_seal.seal_id,
    micro_sleep_payload=payload,
    narrative_compression=f"[{payload.context}] {payload.self_consistent_conclusion}"
)

# 3. 计算哈希（把 payload 纳入计算）
seal.seal_hash = calculate_hash(seal)

# 4. 落盘入库
save_to_db(seal)
```

---

## 六、安全机制

### V1.0 个人版（当前）

| 机制 | 实现 |
|------|------|
| **来源校验** | Token 校验（`X-Agent-Secret` Header） |
| **完整性校验** | SHA-256 Hash（检测数据损坏） |
| **审计日志** | 只追加日志（记录每次插入） |

### V2.0 企业版（规划）

| 机制 | 实现 |
|------|------|
| **非对称加密签名** | RSA 私钥签名 + 公钥验签 |
| **时间戳 + Nonce** | 防重放攻击 |
| **密钥轮换** | 定期更换公私钥对 |

> **原则**：先让齿轮转起来，过度设计是工程大忌。

---

## 七、下一步行动

### 立即执行

- [x] 更新 SOUL.md：添加云端约束（6要素 JSON）
- [x] 更新 SOUL.md：添加双轨隔离原则
- [x] 扩展 `consciousness_cycle.py` 中的 `Seal` 类
- [x] 新增 `MicroSleepPayload` 类
- [x] 修改 `compute_seal_hash()` 方法，payload 参与哈希计算

### 今晚验证

- [ ] 触发全天复盘
- [ ] 检查云端输出是否为结构化 JSON
- [ ] 检查 Seal 是否包含 `micro_sleep_payload`
- [ ] 检查 MD + YAML 是否符合预期

---

**状态**：待扩展 Seal 类
