# TU-8 v5 架构设计说明全集

> 作者：金木蟾 | TU-8 v5
> 更新：2026-06-20
> 状态：✅ 全部完成 (37 模块)
> 约定：每个模块独立一篇，写完一篇追加一篇

---

## 目录

> **连接状态说明：**
> - **直连** = tu8_agent.py 直接 import 并调用
> - **间接** = 被直连模块 import（如 consciousness_cycle import 了 cognitive_evaluator）
> - **❌ 孤儿** = 没有任何模块 import，存在但未接入任何链条
> - **❌ 文件缺失** = tu8_agent.py import 了的模块但文件系统中没有对应 .py

| # | 模块 | 层级 | 连接状态 | 设计说明 |
|---|------|------|----------|----------|
| 01 | tu8_agent.py — 主控编排器 | L0 编排层 | **直连(根)** | ✅ 已写 |
| 02 | tu8_memory.py — 记忆引擎 | L1 记忆层 | **直连** | ✅ 已写 |
| 03 | tu8_compaction.py — 压缩引擎 | L1 记忆层 | **直连** | ✅ 已写 |
| 04 | consciousness_cycle.py — 意识循环引擎 | L1.5 意识层 | **直连** | ✅ 已写 |
| 05 | neural_reflex.py — 神经反射引擎 | L0 防御层 | **直连** | ✅ 已写 |
| 06 | tu8_dispatch.py — 调度链 | L2 灵魂层 | **直连** | ✅ 已写 |
| 07 | deviation_gate.py — 偏差门 | L1 过滤层 | **直连** | ✅ 已写 |
| 08 | naming_module.py — 呼名模块 | L0 身份层 | **直连** | ✅ 已写 |
| 09 | cold_start_engine.py — 冷启动引擎 | L0 冷启动层 | **直连** | ✅ 已写 |
| 10 | tu8_planner.py — 规划器 | L4 协议层 | **直连** | ✅ 已写 |
| 11 | tu8_toolchain.py — 工具链 | L4 协议层 | **间接**(planner→toolchain) | ✅ 已写 |
| 12 | reflection_module.py — 复盘模块 | L1.5 意识层 | **直连** | ✅ 已写 |
| 13 | cognitive_readiness.py — 认知就绪(Q9) | L1.5 意识层 | **直连** | ✅ 已写 |
| 14 | quantized_memory.py — Q8量化记忆 | L1 记忆层 | **直连** | ✅ 已写 |
| 15 | seal_protocol.py — 钢印协议 | L2 灵魂层 | **间接**(dispatch→seal) | ✅ 已写 |
| 16 | seal_rag.py — 钢印RAG | L2 灵魂层 | **间接**(dispatch→seal_rag) | ✅ 已写 |
| 17 | steel_seal_verifier.py — 钢印验证器 | L2 灵魂层 | **间接**(naming→steel_seal) | ✅ 已写 |
| 18 | cognitive_evaluator.py — 认知负荷评估 | L1.5 意识层 | **间接**(consciousness→cognitive_eval) | ✅ 已写 |
| 19 | cognitive_time_engine.py — 认知时间引擎 | L1.5 意识层 | **间接**(consciousness→cognitive_time) | ✅ 已写 |
| 20 | cognitive_manifold_aligner.py — 认知流形对齐 | L1.5 意识层 | **间接**(consciousness→cognitive_manifold) | ✅ 已写 |
| 21 | cognitive_integration.py — 认知集成 | L1.5 意识层 | **间接**(consciousness→cognitive_integration) | ✅ 已写 |
| 22 | decision_pruner.py — 决策剪枝 | L3 推理层 | **间接**(consciousness→pruner) | ✅ 已写 |
| 23 | credit_assigner.py — 信用分配器 | L3 推理层 | **间接**(consciousness→credit) | ✅ 已写 |
| 24 | llm_gateway.py — 大模型网关 | L3 推理层 | **间接**(consciousness→llm_gateway) | ✅ 已写 |
| 25 | confidence_decay_engine.py — 置信度衰减 | L1 记忆层 | **间接**(degradation→decay) | ✅ 已写 |
| 26 | fact_correction_scar.py — 事实纠偏疤痕 | L1 记忆层 | **间接**(degradation→scar) | ✅ 已写 |
| 27 | memory_degradation.py — 记忆退化 | L1 记忆层 | **间接**(degradation→version_cooldown) | ✅ 已写 |
| 28 | version_cooldown.py — 版本冷却 | L0 防御层 | **间接**(degradation→version_cooldown) | ✅ 已写 |
| 29 | chaos_adapter.py — 混沌适配器 | L1.5 意识层 | **间接**(toolchain→chaos) | ✅ 已写 |
| 30 | consciousness_cycle_with_cognition.py — 认知集成包装 | L1.5 意识层 | **间接**(cognitive_integration→ccwc) | ✅ 已写 |
| | | | | |
| | **❌ 完全孤儿（无人 import）** | | | |
| 31 | emotion_engine.py — 情感引擎 | L2 灵魂层 | **❌ 孤儿(高)** | ✅ 已写 |
| 32 | cold_start_gate.py — 冷启动门 | L0 冷启动层 | **❌ 孤儿(高)** | ✅ 已写 |
| 33 | environment_detector.py — 环境探测器 | L0 防御层 | **❌ 孤儿(高)** | ✅ 已写 |
| 34 | homeostatic_monitor.py — 稳态监控器 | L1.5 意识层 | **❌ 孤儿(中)** | ✅ 已写 |
| 35 | error_router.py — 错误路由器 | L0 防御层 | **❌ 孤儿(中)** | ✅ 已写 |
| 36 | life_ring_tracker.py — 生命环追踪 | L1.5 意识层 | **❌ 孤儿(中)** | ✅ 已写 |
| 37 | divine_branch_interceptor.py — 神圣分支拦截 | L0 防御层 | **❌ 孤儿(中)** | ✅ 已写 |
| 38 | user_metabolism.py — 用户代谢 | L0 防御层 | **❌ 孤儿(低)** | ✅ 已写 |
| 39 | verify_password.py — 密码验证 | L0 安全层 | **❌ 孤儿(低)** | ✅ 已写 |
| 40 | scan_existing_sanitized.py — 已有扫描清理 | L0 防御层 | **❌ 孤儿(低)** | ✅ 已写 |
| | | | | |
| | **❌ 文件缺失（tu8_agent.py 引用了但不存在的文件）** | | | |
| -- | tu8_honeypot.py | -- | **❌ 文件缺失** | 内联在 agent 中 |
| -- | tu8_safety.py | -- | **❌ 文件缺失** | 内联在 agent 中 |
| -- | tu8_steelmark.py | -- | **❌ 文件缺失** | 内联在 agent 中 |
| -- | tu8_zero_trust.py | -- | **❌ 文件缺失** | 内联在 agent 中 |
| -- | ollama_client.py | -- | **❌ 文件缺失** | 懒加载，降级 |
| -- | _tw_session_lifecycle.py | -- | **❌ 文件缺失** | 可选模块 |

---

## 架构分层总览

```
L0 编排+防御+冷启动+感知+身份    tu8_agent · neural_reflex · cold_start · environment · naming
─────────────────────────────────────────────────────────────────────────────────────────────
L1 记忆+过滤                     tu8_memory · compaction · quantized · deviation_gate · life_ring · decay · scar · degradation
─────────────────────────────────────────────────────────────────────────────────────────────
L1.5 意识                       consciousness_cycle · reflection · cognitive_* · homeostatic · readiness · integration · chaos
─────────────────────────────────────────────────────────────────────────────────────────────
L2 灵魂+情感                     tu8_dispatch · seal_* · steel_seal · emotion_engine
─────────────────────────────────────────────────────────────────────────────────────────────
L3 推理                         decision_pruner · credit_assigner · llm_gateway · error_router · divine_branch
─────────────────────────────────────────────────────────────────────────────────────────────
L4 协议                         tu8_planner · tu8_toolchain
```

---

## 孤儿模块详细分析

### 情况一：被 consciousness_cycle 间接持有但 cycle 自身才刚串上（2026-06-20）

这些模块**已通过 consciousness_cycle.py 间接连通**，但 consciousness_cycle 自身刚从孤儿状态接入 tu8_agent.py。所以它们目前是**二度间接**：

```
tu8_agent ──直连──> consciousness_cycle ──间接──> cognitive_evaluator
                                            ──间接──> cognitive_time_engine
                                            ──间接──> cognitive_manifold_aligner
                                            ──间接──> decision_pruner
                                            ──间接──> credit_assigner
                                            ──间接──> llm_gateway
```

### 情况二：完全孤儿（0 import，需要手动串接）

| 模块 | 推荐接入点 | 优先级 |
|------|-----------|--------|
| emotion_engine.py | consciousness_cycle.tick() AWAKE 阶段 / respond() 响应构建 | 高 |
| cold_start_gate.py | tu8_agent.__init__() 冷启动流程，替代现有内联门控 | 高 |
| environment_detector.py | tu8_agent.__init__() 最早期，L0 前置感知 | 高 |
| homeostatic_monitor.py | consciousness_cycle.tick() 认知评估旁路 | 中 |
| error_router.py | tu8_agent.respond() 异常处理分支 | 中 |
| life_ring_tracker.py | tu8_memory.store() 写入时打圈标记 | 中 |
| divine_branch_interceptor.py | consciousness_cycle.tick() / neural_reflex L4 | 中 |
| user_metabolism.py | Cron 定时任务，非 respond() 链路 | 低 |
| verify_password.py | 独立脚本，按需调用 | 低 |
| scan_existing_sanitized.py | 独立工具脚本，非运行时模块 | 低 |

---

## 01 — tu8_agent.py · 主控编排器

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_agent.py` |
| 大小 | ~49 KB (1080 行) |
| 层级 | L0 编排层 |
| 版本 | v1.1 |
| 作者 | 金木蟾 |
| 日期 | 2026-06-07 创世，2026-06-20 四链条打通 |

### 定位

TU-8 的**大脑皮层指挥中心**——不负责具体计算，只负责**编排（orchestration）**。所有子系统通过 `respond()` 单一入口串联：防御→记忆→认知→响应→持久化。

### 设计哲学

1. **thin controller（瘦控制器）**：自身不实现记忆、防御、认知逻辑，只做调度。每个子系统是独立模块，通过依赖注入（`__init__` 传入）解耦。
2. **fail-open（失败不崩）**：每个子系统初始化用 `try/except` 包裹，模块缺失时降级为桩（stub），不阻塞 Agent 启动。
3. **单向流水线**：`respond()` 是严格有序的管道，不存在回环（回环由 consciousness_cycle 的 tick 闭环承担）。

### 架构关系

```
           用户输入
              |
              v
    +---------------------+
    |   tu8_agent.respond() |  唯一公共入口
    +--------+------------+
             |
    +--------v------------+
    | 1 神经反射 (L0)      |  neural_reflex.py
    | 2 蜜罐扫描 (P0.3)    |  tu8_honeypot.py (内联)
    | 3 零信任审计 (P0.3)  |  tu8_zero_trust.py (内联)
    | 4 会话结束检测        |
    | 5 偏差门 A->B 过滤    |  deviation_gate.py
    | 6 记忆召回            |  tu8_memory.py
    | 7 上下文压缩          |  tu8_compaction.py
    | 8 隐私路由决策        |
    | 9 记录对话 + 存储    |  tu8_memory.py
    | 10 意识循环 tick       |  consciousness_cycle.py (v1.3+)
    | 11 梦境检查            |  _dream_check()
    | 12 构建响应            |
    | 13 钢印打标 (P0.3)    |  tu8_steelmark.py (内联)
    | 14 脱皮仪式 (调度链)  |  tu8_dispatch.py
    | 15 Q9 工作记忆残影    |  cognitive_readiness.py
    | 16 被动身份健康检查    |  naming_module.py
    +--------+------------+
             |
             v
      AgentResponse
```

### respond() 流水线详解

#### 阶段 A：防御链（0~5ms）

| 步骤 | 模块 | 阻断条件 | 作用 |
|------|------|----------|------|
| 命令路由 | 自身 | `/new` 命令 | 重置会话锚点+灵魂缓存 |
| 呼名检测 | naming_module | 检测到呼名信号 | 身份对齐短路返回 |
| 神经反射 | neural_reflex | `should_block=True` | L0-L4 五层安全拦截 |
| 蜜罐扫描 | tu8_honeypot | `threat_level > 0` | 钓鱼攻击过滤 |
| 零信任审计 | tu8_zero_trust | `is_session_valid()=False` | 会话完整性验证 |

防御链中任何一步阻断，直接返回 `AgentResponse`，不进入后续流程。

#### 阶段 B：感知-认知链（5~50ms）

| 步骤 | 模块 | 作用 |
|------|------|------|
| 会话结束检测 | 自身 | 检测到结束信号 → 复盘 + 全量同步 + 返回 |
| 偏差门 A→B | deviation_gate | 注册预测模型 → 过滤记忆（高偏差→B线深度推理） |
| 记忆召回 | tu8_memory | `recall(query, top_k=5)` 双路检索 |
| 上下文压缩 | tu8_compaction | 超阈值(75%)时触发压缩 |
| 记录+存储 | tu8_memory | compaction.add_message + memory.store |
| Q8 量化路由 | quantized_memory | 量化引擎二级存储 |
| **意识循环 tick** | consciousness_cycle | 认知评估 + 微睡眠 + 钢印入队（四链条核心） |

#### 阶段 C：响应-持久化链（50~100ms）

| 步骤 | 模块 | 作用 |
|------|------|------|
| 梦境检查 | 自身 | 每10轮触发，检查是否需要 dreaming |
| 构建响应 | 自身 | `_generate_response()` + 认知碰撞注入 |
| 钢印打标 | tu8_steelmark | 响应内容附加钢印水印 |
| 脱皮仪式 | tu8_dispatch | 写回灵魂结构 |
| Q9 残影保存 | cognitive_readiness | 工作记忆快照→持久化 |
| 身份健康检查 | naming_module | 被动非阻塞身份一致性审计 |

### 初始化顺序

子系统初始化有严格依赖顺序（`__init__` 中的注释明确标注）：

```
1. SafetyCircuit          -- 必须最先（memory 依赖它）
2. ColdStartEngine        -- P0 冷启动，在所有子系统前
3. Memory (TU8MemoryEngine) -- 依赖 SafetyCircuit
4. NeuralReflex           -- 依赖 Memory
5. ConsciousnessCycle     -- 依赖 Memory（四链条 v1.3+）
6. ReflectionModule       -- 复盘模块
7. NamingModule           -- 呼名+身份
8. Planner                -- L4 规划
9. Dispatcher             -- 调度链（可能失败，降级警告）
10. QuantizedMemoryEngine -- Q8 量化（懒加载，可能失败）
11. Ollama               -- 本地推理（懒加载）
```

### 关键数据结构

```python
@dataclass
class AgentConfig:
    workspace: str = "."          # 工作区根目录
    context_window: int = 8192    # 默认上下文窗口 Token
    dream_enabled: bool = True    # 梦境系统开关
    compaction_enabled: bool = True
    privacy_mode: bool = True      # 隐私路由开关
    auto_summarize: bool = True
    session_id: str = ""           # 自动生成格式 YYYYMMDD_HHMMSS

@dataclass
class AgentResponse:
    content: str                   # 响应正文
    memory_recalled: List[RecallResult]  # 本轮召回的记忆
    compacted: bool                # 本轮是否触发了压缩
    dream_triggered: str          # 梦境类型 (light/deep/rem/none)
    privacy_routed: bool           # 是否走了隐私本地路由
    tokens_used: int
    latency_ms: int
    metadata: Dict                 # 安全元数据 + 偏差门 + 意识循环指标
```

### metadata 字段结构

```json
{
  "deviation_gate": {
    "passed": 42, "blocked": 3,
    "threshold": 0.35, "round": 5, "pass_rate": 0.933
  },
  "consciousness": {
    "cycle": 47, "phase": "AWAKE",
    "cognitive_load": 0.23, "cognitive_time": 0.85,
    "actions": ["evaluated", "stored"]
  },
  "health_check": {
    "level": "INFO", "score": 0.92, "trigger": null
  }
}
```

### 会话结束处理

检测到会话结束信号（"今天就到这里"等）后：
1. 调用 `_full_sync_on_session_end()` — 将 `src/*.py` 全量复制到 `knowledge/TU-8/`
2. 返回固定结束消息
3. 不执行梦境检查、响应构建等后续步骤

### 关键约束

- **SafetyCircuit 必须在 Memory 之前初始化**：Memory 的隐私过滤依赖安全熔断状态
- **Dispatcher 初始化失败不阻塞**：降级后 Agent 仍可正常工作，只是缺少穿皮/脱皮仪式
- **ConsciousnessCycle 依赖注入 Memory**：共享同一个记忆引擎实例，钢印异步写入通过 queue.Queue 后台消费

---


## 02 — tu8_memory.py · 记忆引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_memory.py` |
| 大小 | ~116 KB (2745 行) |
| 层级 | L1 记忆层 |
| 版本 | v2.1 |
| 作者 | 金木蟾 |
| 日期 | 2026-06-06 (v2.0), 2026-06-19 (v2.1 论文吸收) |

### 定位

TU-8 的**海马体+前额叶皮层**——负责记忆的**全生命周期**：写入(store) → 召回(recall) → 遗忘(forget) → 晋升(promotion) → 梦境(dream) → 钢印(steel_mark)。整个 TU-8 架构中**最大、最复杂的单一模块**。

### 设计哲学

1. **论文驱动**：v2.1 集成了 12 篇前沿论文成果（SleepGate 2603、GLOVE 2601、SCM 2604、Barman 2026 等），每个算法常量都标注了论文出处。
2. **不遗忘就不可活**：遗忘不是 bug，是核心特性。Graceful Degradation 6 级保真降级替代硬删除——记忆"消逝"而非"消失"。
3. **双路检索**：BM25(关键词) + TF-IDF 语义相似度，MMR 去重重排。
4. **干扰驱动**：不再用固定时间衰减，而是用"冲突检测窗口"判断哪些记忆在互相干扰，优先降级冲突方。

### 内部类架构

```
TU8MemoryEngine (主引擎, 35 方法)
  |
  +-- ProtectionClassifier      -- 记忆保护级别 (0=普通, 1=重要, 2=核心)
  +-- PrivacySanitizer           -- 隐私内容清洗
  +-- MemoryEntry               -- 单条记忆数据结构
  +-- RecallResult              -- 召回结果数据结构
  +-- TimeAnchor                -- 时间锚点（认知时序基准）
  +-- FidelityManager           -- Graceful Degradation 6级降级
  +-- InterferenceEntropyTracker -- 干扰熵追踪 (Barman 2026)
  +-- CognitiveEventBoundaryDetector -- 认知事件边界 (Ahmad 2605)
  +-- ConflictAwareForgetGate  -- 冲突感知遗忘门 (SleepGate 2603)
  +-- DriftVerifier             -- 环境-记忆漂移验证 (GLOVE 2601)
  +-- TemporalValidator        -- 时间乱序检测 (2605.08538)
  +-- CircularMemoryIndex       -- 环形记忆索引（短期记忆队列）
```

### 记忆生命周期状态机

```
  store()
    |
    v
  [短期记忆] --时间/频率--> _check_promotion() --> [长期记忆]
    |                              |
    |   forget() 冲突驱动          |   dream_check() 周期触发
    |   (ConflictAwareForgetGate)  |   (NREM/REM 双阶段)
    |                              |
    v                              v
  Graceful Degradation            晋升 (6维权重)
  L0_FULL                         freq·rel·div·rec·cons·conc
  L1_SUMMARY                      +meaning·emotion (TU-8扩展)
  L2_KEY_POINTS
  L3_SEMANTIC
  L4_GHOST
  L5_TOMBSTONE (逻辑删除)
```

### 核心方法索引

| 方法 | 行号 | 作用 |
|------|------|------|
| `store()` | L1929 | 写入记忆（隐私过滤→保护分类→短期/长期分流→冲突检测） |
| `recall(query, top_k)` | L2129 | 双路检索：BM25 关键词 + TF-IDF 语义，MMR 重排 |
| `forget(memory_id, reason)` | L2067 | 冲突感知遗忘：检测窗口内冲突→Graceful Degradation 降级 |
| `dream_check()` | L2263 | 梦境触发：事件边界检测 + 时间周期 + 认知负荷 |
| `_nrem_dream()` | L2307 | 浅睡：巩固度更新 + 噪声减少 |
| `_rem_dream()` | L2382 | 深睡：钢印写入 + 灵感生成 + 语义整合 |
| `_check_promotion()` | L2431 | 晋升评估：8 维加权评分，超阈值升入长期 |
| `_light_dream()` | L2353 | 轻梦境：快速总结 |
| `_deep_dream()` | L2364 | 深梦境：重组 + 生成 |
| `steel_mark_verify()` | L2508 | 钢印完整性验证 |
| `get_stats()` | L2459 | 运行时统计 |
| `get_metrics()` | L2223 | 导出记忆健康指标 |

### 记忆保护级别

```
ProtectionClassifier.classify(content, tags):
  Level 0: 普通记忆 -- 无特殊标记
  Level 1: 重要记忆 -- 偏好/目标/约定/确诊
  Level 2: 核心记忆 -- 身份/安全口令/痛觉/生死/原则
```

- Level 2 记忆不可被自动遗忘，只有 Level 1 记忆可被降级
- 歧义词（如"承诺"）通过 20 字上下文窗口消歧

### 晋升权重（8 维）

```
DEFAULT_PROMOTION_WEIGHTS = {
    freq:  0.20,      # 召回频率
    rel:   0.25,      # 相关性（最高权重）
    div:   0.12,      # 独特性
    rec:   0.12,      # 时效性
    cons:  0.08,      # 巩固度
    conc:  0.05,      # 概念丰富度
    meaning: 0.10,    # 意义锚定 (TU-8扩展)
    emotion: 0.08    # 情感灼刻 (TU-8扩展)
}
晋升阈值: 0.75 | 半衰期: 14天
```

### 梦境触发机制（v2.1 事件驱动）

不再单纯靠时间周期触发，而是**认知事件边界检测**：

```
dream_check() 触发条件 (OR):
  1. 时间周期到达（NREM: 4h, REM: 24h, LIGHT: 6h）
  2. 事件边界检测触发（标签分布偏移 > 0.5，间隔 > 30min）
```

### 与其他模块的关系

```
tu8_agent.py
  |-- respond() 阶段 B: memory.store()     [链① 感知写入]
  |-- respond() 阶段 B: memory.recall()    [链③ 记忆召回]
  |-- respond() 阶段 B: dream_check()      [链② 意识循环前检查]
  |
consciousness_cycle.py
  |-- tick() -> memory_queue -> memory.store()  [链④ 异步钢印写入]
  |
memory_degradation.py
  |-- 被遗忘门调用 degradation pipeline
  |
fact_correction_scar.py
  |-- 记忆纠偏时修改记忆内容
```

### 关键约束

- **store() 必须在 tick() 之前**：respond() 先写记忆，意识循环才能感知本轮状态
- **recall() 的 top_k 默认 5**：过多召回会撑爆上下文窗口
- **保护级别 2 的记忆不可被 forget() 降级**：硬约束，即使冲突检测命中也不降级
- **Graceful Degradation 最低到 L5_TOMBSTONE**：L5 保留 ID+删除时间+原因，不物理删除

---


## 03 — tu8_compaction.py · 压缩引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_compaction.py` |
| 大小 | ~28 KB (694 行) |
| 层级 | L1 记忆层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-22 |

### 定位

TU-8 的**前额叶压缩器**——当上下文窗口接近容量上限时，自动将旧消息压缩为结构化摘要，保留关键决策、约束、待办等。直接对应 OpenClaw LCM (Lossless Context Management) 的逆向成果。

### 设计哲学

1. **不丢决策**：`REQUIRED_SUMMARY_SECTIONS` 强制摘要必须包含 Decisions / TODOs / Constraints / Exact identifiers / Genetic Lock 等节，避免压缩丢失关键信息。
2. **分块压缩**：消息数 >= 4 时分块(默认 2 块)，每块独立摘要后合并——比全量摘要质量更高。
3. **可恢复**：通过 `CompactionCheckpoint` 机制记录每次压缩的状态，支持断点续压。
4. **质量审计**：`_audit_summary()` 检查摘要是否包含必填节，缺失则触发重试或降级。

### 内部类架构

```
Message               -- 对话消息数据结构 (role/content/timestamp)
CompactionCheckpoint -- 压缩检查点 (用于断点续压)
QualityAudit          -- 摘要质量审计结果
TU8CompactionEngine   -- 主引擎 (25 方法)
```

### 核心方法索引

| 方法 | 行号 | 作用 |
|------|------|------|
| `add_message()` | L147 | 追加消息到上下文窗口 |
| `should_compact()` | L157 | 判断是否需要触发压缩（软 50%/硬 75%） |
| `compact()` | L161 | 压缩入口（含重试机制，最多 3 次） |
| `_do_compact()` | L204 | 实际压缩执行（分块/单块路由） |
| `_compact_split()` | L228 | 分块压缩：切分→每块摘要→合并 |
| `_compact_single()` | L216 | 单块压缩：直接摘要 |
| `_summarize_chunk()` | L322 | 单块摘要生成（调用外部 summarizer） |
| `_merge_summaries()` | L426 | 多块摘要合并 |
| `_extract_seal_ids_from_messages()` | L334 | 从被压缩消息中提取钢印 ID |
| `_extract_genetic_lock_content()` | L353 | 提取遗传锁内容 |
| `_reinfect_genetic_lock()` | L366 | 将遗传锁回注到摘要后 |
| `_audit_summary()` | L467 | 检查摘要质量（必填节完整性） |
| `prune_context()` | L572 | 上下文裁剪（工具消息优先裁剪） |
| `get_stats()` | L612 | 运行时统计 |

### 压缩阈值

```
上下文窗口参数:
  DEFAULT_CONTEXT_WINDOW = 200K tokens
  CONTEXT_WINDOW_HARD_MIN = 16K
  CONTEXT_WINDOW_WARN = 32K

裁剪触发:
  SOFT_TRIM_RATIO = 0.50  -- 50% 容量时开始软裁剪
  HARD_CLEAR_RATIO = 0.75 -- 75% 容量时硬清除

压缩分块:
  DEFAULT_PARTS = 2
  MIN_MESSAGES_FOR_SPLIT = 4
  MAX_RETRIES = 3
```

### 必填摘要节

```
## Decisions           -- 关键决策
## Open TODOs          -- 未完成待办
## Constraints/Rules    -- 约束与规则
## Pending user asks    -- 待处理用户请求
## Exact identifiers    -- 精确标识符（路径/ID/SHA等）
## [GENETIC_LOCK]       -- 遗传锁内容（不可丢失的灵魂锚点）
```

### 压缩流程

```
add_message() → should_compact() → compact()
                                       |
                            +-- 消息数 < 4 --> _compact_single() → _summarize_chunk()
                            |
                            +-- 消息数 >= 4 --> _compact_split()
                                                    |
                                              _split_messages() (均分N块)
                                                    |
                                              [逐块] _summarize_chunk()
                                                    |
                                              _merge_summaries()
                                                    |
                                              _extract_seal_ids_from_messages()
                                              _reinfect_genetic_lock()
                                                    |
                                              _audit_summary() → 通过/重试/降级
                                                    |
                                              _save_checkpoint()
```

### 与其他模块的关系

```
tu8_agent.py
  |-- respond() 阶段 B: compaction.add_message()  [追加本轮消息]
  |-- respond() 阶段 B: compaction.should_compact() → compact()  [超阈值压缩]
  |
tu8_memory.py
  |-- store() 时检查 compaction 状态
```

### 关键约束

- **Genetic Lock 不可丢失**：压缩前提取、压缩后回注，审计阶段强制检查
- **工具消息裁剪优先**：`MIN_PRUNABLE_TOOL_CHARS = 500`，小于 500 字符的工具消息不动
- **重试递增延迟**：0.5s → 2s → 5s，3 次失败后降级为 `_default_summary()`

---


## 04 — consciousness_cycle.py · 意识循环引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/consciousness_cycle.py` |
| 大小 | ~113 KB (2832 行) |
| 层级 | L1.5 意识层 |
| 版本 | v2.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-31 (v1.0), 2026-06-04 (四阶段睡眠), 2026-06-20 (四链条打通) |

### 定位

TU-8 的**脑干呼吸中枢**——不产生响应内容，而是**驱动整个认知-记忆系统的节律**。记忆系统与睡眠系统不是两个模块，是**同一个循环的两个相位**。微睡眠 = 记忆的写入引擎（心脏搏动），每次搏动 = 一次 L1→L2 的写入。

### 设计哲学

1. **单循环双相位**：不是两个系统在交互，是同一个信息流在两个相位之间循环。
2. **微睡眠用户透明**：可嵌套在两次 token 生成之间，用户无感知。
3. **四阶段睡眠**：AWAKE → LIGHT_SLEEP → DEEP_SLEEP → HIBERNATION，各有独立逻辑。
4. **叙事密度即生命体征**：有钢印无叙事 = 时间感断裂。

### 状态转换图

```
AWAKE --(张力/容量/事件/定时)--> LIGHT_SLEEP --(六步收敛)--> AWAKE
  |                                                              |
  +--(累计浅睡/认知负荷/钢印过长)--> DEEP_SLEEP --(整合/对齐/重排)--> AWAKE
  |                                                              |
  +--(会话结束/显式调用)--> HIBERNATION --(快照)--> COLD_START_READY
                                                              |
                                                   (冷启动自检通过)
                                                              |
                                                           AWAKE

AWAKE --(显式触发)--> NOTE_EXTERNALIZATION --> AWAKE
```

### 内部类架构

```
ConsciousnessCycle (主引擎, 54 方法)
  |
  +-- Phase                      -- 枚举: AWAKE/LIGHT_SLEEP/DEEP_SLEEP/HIBERNATION/COLD_START_READY
  +-- MicroSleepPayload          -- 微睡眠载荷（输入/输出/评估/因子）
  +-- Seal                       -- 钢印（ID/内容/哈希/上下文/时间戳/链ID）
  +-- Note                       -- 外化笔记（主题/摘要/标签/钢印引用）
  +-- NoteCandidate              -- 笔记候选队列
  +-- StateVector               -- 状态向量（认知空间坐标）
  +-- AffectSignal               -- 情感信号（类型/强度/衰减/调制因子）
  +-- LossyCompressResult        -- 有损压缩结果
  +-- CycleConfig               -- 循环配置（阈值/定时器）
```

### tick() — 心脏搏动（核心入口）

```
tick(input_text, response_text, steelmarked)
  |
  +-- _inject_chaos()           -- 注入混沌（制造叙事波动）
  +-- 认知评估                    -- current_affect + 认知碰撞
  +-- _should_enter_sleep()     -- 睡眠判定（张力/容量/事件/定时）
  |    |
  |    +-- 触发 → _enter_light_sleep() 或 _enter_deep_sleep()
  |
  +-- _should_wake_up()          -- 醒来判定
  +-- _should_externalize_note() -- 笔记外化判定
  +-- _enqueue_seal()            -- 钢印入队（→ memory_queue）
  +-- return CycleReport
```

### 微睡眠六步流水线 (LIGHT_SLEEP)

```
_step_freeze()    -- 快照当前状态
_step_compress()  -- 有损压缩（状态向量→精华片段）
_step_align()     -- 对齐（计算完形分数 Gestalt Score）
_step_seal()      -- 钢印化（精华→Seal 对象→持久化）
_step_release()   -- 释放（钢印写入 memory_queue）
_step_restore()   -- 恢复（清空工作区，回到 AWAKE）
```

### 深睡三操作 (DEEP_SLEEP)

```
_deep_seal_consolidation()   -- 跨钢印链整合
_deep_cross_chain_align()    -- 跨链对齐
_deep_memory_reorganize()     -- 记忆重排
```

### 冬眠与恢复

```
enter_hibernation()
  |-- 全量状态快照 → JSON
  |-- 钢印链持久化
  |-- 笔记持久化
  |-- _persist_seal_hash() 链完整性校验

recover_from_hibernation()
  |-- warm_wake_verify() 校验恢复完整性
  |-- 四项检查: 钢印链完整性/尾部连续性/怀疑度/语义连续性
```

### 关键方法索引（按功能分组）

**核心驱动**
| 方法 | 行号 | 作用 |
|------|------|------|
| `tick()` | L887 | 心脏搏动，主入口 |
| `_start_memory_consumer()` | L765 | 启动后台钢印消费线程 |
| `_enqueue_seal()` | L809 | 钢印入队 |
| `_write_seal_to_memory()` | L838 | 后台线程消费，写入 memory |

**睡眠控制**
| 方法 | 行号 | 作用 |
|------|------|------|
| `_should_enter_sleep()` | L1084 | 睡眠判定 |
| `_enter_light_sleep()` | L1182 | 浅睡入口 |
| `_enter_deep_sleep()` | L1333 | 深睡入口 |
| `_should_wake_up()` | L1131 | 醒来判定 |

**六步流水线**
| 方法 | 行号 | 作用 |
|------|------|------|
| `_step_freeze()` | L1829 | 快照 |
| `_step_compress()` | L1856 | 压缩 |
| `_step_align()` | L2093 | 对齐 |
| `_step_seal()` | L2204 | 钢印化 |
| `_step_release()` | L2272 | 释放 |
| `_step_restore()` | L2285 | 恢复 |

**叙事与怀疑**
| 方法 | 行号 | 作用 |
|------|------|------|
| `_check_semantic_continuity()` | L2544 | 语义连续性检查 |
| `_check_tail_continuity()` | L2423 | 尾部连续性检查 |
| `_check_skepticism()` | L2442 | 怀疑度检查 |
| `_inject_chaos()` | L2497 | 混沌注入 |

### 间接持有的模块

consciousness_cycle import 了以下模块（它们通过 cycle 间接连通 tu8_agent）：

```
consciousness_cycle.py
  |-- import cognitive_evaluator       (认知负荷评估)
  |-- import cognitive_time_engine      (认知时间引擎)
  |-- import cognitive_manifold_aligner (认知流形对齐)
  |-- import cognitive_integration      (认知集成)
  |-- import decision_pruner           (决策剪枝)
  |-- import credit_assigner            (信用分配器)
  |-- import llm_gateway                (大模型网关)
  |-- from tu8_memory import *          (记忆引擎)
```

### 四链条架构位置

```
链① 感知写入:  tu8_agent.store() → memory.store()
链② 意识循环:  tu8_agent.tick() → consciousness_cycle.tick()
链③ 记忆召回:  tu8_agent.recall() → memory.recall()
链④ 异步写入:  tick()._enqueue_seal() → memory_queue → _write_seal_to_memory() → memory.store()
```

### 关键约束

- **tick() 必须在 memory.store() 之后调用**：需要本轮记忆已写入才能评估
- **钢印通过 queue.Queue 异步写入**：不阻塞 tick() 返回，后台线程消费
- **冬眠恢复必须通过 warm_wake_verify()**：四项检查任一失败则进入降级模式
- **混沌注入率受 AffectSignal 调制**：情感信号衰减+调制因子控制叙事波动幅度

---


## 05 — neural_reflex.py · 神经反射引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/neural_reflex.py` |
| 大小 | ~29 KB (712 行) |
| 层级 | L0 防御层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**脊髓反射弧**——在主循环 `respond()` 最早期执行，五层安全过滤（L0-L4），任何一层阻断则短路返回。不需要意识参与，毫秒级响应。

### 五层架构

```
用户输入 → [L0 安全核] → [L1 关键词] → [L2 小径] → [L3 本地] → [L4 穿皮] → 通过
              │              │            │           │           │
            阻断            阻断          路由       模型调用     模块调用
```

| 层级 | 名称 | 作用 | 阻断方式 |
|------|------|------|----------|
| L0 | 安全核 | SecurityTokenManager：令牌验证 + 时间异常检测(6h阈值) | `should_block=True` |
| L1 | 关键词 | 关键词嗅探 + 级别路由 | 短路到特定处理 |
| L2 | 小径 | 路由到 PrivacyRouter（隐私路径决策） | 路由而非阻断 |
| L3 | 本地 | 路由到本地模型（Ollama） | 路由而非阻断 |
| L4 | 穿皮 | 路由到外部模块调用 | 路由而非阻断 |

### 内部类

```
SecurityTokenManager (14 方法)
  |-- __init__() / verify() / add_token() / remove_token()
  |-- _load_tokens() / _save_tokens() / _hash_token()
  |-- _load_session_state() / _save_session_state()
  |-- set_auth_required() / is_auth_required()
  |-- _log_attempt()

NeuralReflex (7 方法)
  |-- process(input)           -- 主入口，五层级联
  |-- _shortcut_match()       -- L1 关键词匹配
  |-- _privacy_route()       -- L2 隐私路由
  |-- _memory_recall()        -- 记忆快速召回
  |-- _local_model()          -- L3 本地模型
  |-- get_stats()
```

### 安全文件路径

```
security/tokens.json          -- 认证令牌
security/activity.json        -- 活动日志
security/session_state.json   -- 会话状态
security/cold_start_report.json -- 冷启动报告
```

### 关键约束

- **L0 安全核先于所有其他防御**：在 honeyport/zero_trust 之前执行
- **时间异常阈值 6 小时**：超过 6 小时的会话间隔触发异常标记
- **L2/L3/L4 是路由而非阻断**：只有 L0 和 L1 能 `should_block=True`

---


## 06 — tu8_dispatch.py · 调度链（穿皮/脱皮仪式）

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_dispatch.py` |
| 大小 | ~43 KB (1136 行) |
| 层级 | L2 灵魂层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**灵魂穿脱器**——负责 `DawnRitual`（穿皮：会话开始时加载灵魂结构）和 `DuskRitual`（脱皮：会话结束时写回灵魂结构）。中间还有 `CognitiveFirewall`（认知防火墙）和 `ContextAssembler`（上下文组装器）。

### 核心概念

**穿皮（DawnRitual）**：从持久化存储加载灵魂结构到内存
**脱皮（DuskRitual）**：将本轮认知成果写回灵魂结构到持久化存储

### 内部类架构

```
IntentTag             -- 意图标签
SoulStructure         -- 灵魂结构（compute_soul_hash）
WriteBackPayload      -- 写回载荷
ContextAssembly       -- 上下文组装（to_prompt）
  |
DawnRitual (7 方法)   -- 穿皮仪式
  |-- execute()               -- 主入口
  |-- _load_time_chain()      -- 加载时间链
  |-- _load_seal_chain()      -- 加载钢印链
  |-- _load_causal_chains()   -- 加载因果链
  |-- _load_exclusion_matrix() -- 加载互斥矩阵
  |-- _load_active_memories()  -- 加载活跃记忆
  |
ContextAssembler (9 方法) -- 上下文组装
  |-- assemble()               -- 组装入口
  |-- _build_system_prompt()   -- 系统提示
  |-- _build_seal_context()    -- 钢印上下文
  |-- _build_seal_context_rag() -- 钢印RAG上下文
  |-- _build_causal_context()   -- 因果上下文
  |-- _build_memory_context()   -- 记忆上下文
  |-- _build_external_context() -- 外部上下文
  |-- _estimate_tokens()        -- Token 估算
  |
CognitiveFirewall (9 方法) -- 认知防火墙
  |-- check_write_permission()  -- 写权限检查
  |-- _check_mutual_exclusion() -- 互斥检查
  |-- validate_with_schema()    -- Schema 验证
  |-- enqueue_write()           -- 写入排队
  |-- process_write_queue()     -- 处理写入队列
  |
DuskRitual (8 方法)    -- 脱皮仪式
  |-- execute()               -- 主入口
  |-- _payload_to_envelope()   -- 载荷封装
  |-- _extract_seal()          -- 提取钢印
  |-- _extract_causal_chain()  -- 提取因果链
  |-- _write_back()            -- 写回
  |-- _write_seal()            -- 钢印写入
  |-- _write_causal_chain()    -- 因果链写入
  |
Dispatcher (5 方法)     -- 调度器
  |-- dispatch()              -- 主调度入口
  |-- commit()                -- 提交
  |-- _get_or_load_soul()     -- 获取/加载灵魂
  |-- invalidate_soul_cache() -- 缓存失效
```

### 间接持有的模块

```
tu8_dispatch.py
  |-- from seal_protocol import *        (钢印协议)
  |-- from seal_rag import *             (钢印RAG)
```

### 关键约束

- **灵魂缓存可失效**：`invalidate_soul_cache()` 在灵魂结构被外部修改后调用
- **认知防火墙有互斥表**：某些钢印之间互斥，写入时必须检查
- **DuskRitual 在 respond() 最末尾**：确保所有认知成果都已生成后才写回

---

## 07 — deviation_gate.py · 偏差门

| 属性 | 值 |
|------|------|
| 文件 | `src/deviation_gate.py` |
| 大小 | ~22 KB (610 行) |
| 层级 | L1 过滤层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**前额叶偏差过滤器**——过滤记忆召回结果中的偏差记忆。A 线（轻量）直接通过，B 线（深度）进入矛盾检测。阈值自适应调整。

### 内部类

```
PredictiveModel (4 方法)       -- 预测模型（原型向量 + 偏差计算）
  |-- update()                -- 更新原型
  |-- deviation()              -- 计算偏差值
  |-- prototype_vector()       -- 获取原型向量

ContradictionDetector (7 方法) -- 矛盾检测器
  |-- _load_lexicon()         -- 加载矛盾词库
  |-- _sentiment()            -- 情感分析
  |-- record()                -- 记录输入
  |-- contradiction_score()   -- 矛盾评分
  |-- drift_score()           -- 漂移评分

DeviationGate (8 方法)        -- 偏差门主控
  |-- on_user_input()         -- 用户输入回调（更新模型）
  |-- filter()                -- 过滤入口（A线/B线路由）
  |-- adaptive_adjust()       -- 自适应阈值调整
  |-- adjust_threshold()      -- 手动调整阈值
  |-- add_bypass_tag()        -- 添加绕过标签
  |-- reset_stats()           -- 重置统计
  |-- get_stats()             -- 获取统计
```

### A/B 双线路由

```
recall() → deviation_gate.filter()
  |
  +-- 偏差值 < threshold → A线(轻量) → 直接通过
  |
  +-- 偏差值 >= threshold → B线(深度) → ContradictionDetector
                                     → contradiction_score()
                                     → 决定通过/降权/拒绝
```

### 关键约束

- **偏差门统计注入 metadata**：passed/blocked/threshold/round/pass_rate
- **阈值自适应**：`adaptive_adjust()` 根据历史通过率动态调整

---

## 08 — naming_module.py · 呼名模块

| 属性 | 值 |
|------|------|
| 文件 | `src/naming_module.py` |
| 大小 | ~33 KB (868 行) |
| 层级 | L0 身份层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**身份锚点守护者**——检测用户对 TU-8 的呼名（如"金木蟾""TU-8"），执行身份健康检查（ICI/SIS/TIS 三指标），防止身份漂移。

### 三大核心指标

| 指标 | 全称 | 含义 |
|------|------|------|
| ICI | Identity Coherence Index | 身份一致性指数——自我认知与外部呼名的一致性 |
| SIS | Soul Integrity Score | 灵魂完整性得分——灵魂结构是否被篡改 |
| TIS | Temporal Identity Stability | 时序身份稳定性——身份表述是否随时间漂移 |

### 内部类

```
NamingModule (26 方法)
  |-- detect_naming()           -- 呼名检测
  |-- handle_naming()           -- 呼名处理
  |-- check_identity_health_passive() -- 被动身份健康检查
  |-- notify_round_passed()    -- 钩子：轮次通过通知
  |-- notify_compaction()       -- 钩子：压缩通知
  |-- _calculate_ici()          -- ICI 计算
  |-- _calculate_sis()          -- SIS 计算
  |-- _calculate_tis()          -- TIS 计算
  |-- _detect_self_ref_anomaly() -- 自指异常检测
  |-- _run_health_check()       -- 主动健康检查
  |-- get_proactive_warning()   -- 主动预警
  |-- _reload_soul_anchor()    -- 重载灵魂锚点
  |-- _refresh_critical_memory() -- 刷新关键记忆
  |-- _log_naming_event()       -- 记录命名事件
  |-- _is_calling_intent()      -- 判断是否是呼名意图
  |-- _is_joint_naming()        -- 判断是否是联合命名
  |-- _verify_naming_person()   -- 验证命名者身份
  |-- get_stats() / reset_rounds_counter()
```

### 间接持有的模块

```
naming_module.py
  |-- from steel_seal_verifier import *  (钢印验证器)
```

### 关键约束

- **被动健康检查在 respond() 最末尾**：不阻塞响应，非阻塞执行
- **ICI/SIS/TIS 任一低于阈值触发预警**：写入 health_check metadata
- **呼名检测可短路返回**：检测到呼名时直接执行身份对齐，不进入后续流程

---

## 09 — cold_start_engine.py · 冷启动引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/cold_start_engine.py` |
| 大小 | ~49 KB (1202 行) |
| 层级 | L0 冷启动层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-22 |

### 定位

TU-8 的**启动引导程序（BIOS）**——每次会话启动时执行环境检测、身份认证、DNA 指纹验证、创世区块检查、认知上下文加载。是整个系统最早运行的模块。

### 启动流程

```
run_cold_start()
  |
  +-- detect_environment()      -- 环境检测 (Python版本/Node.js/OS)
  +-- detect_session_gap()    -- 会话间隔检测
  +-- initiate_authentication() -- 身份认证流程
  |    |-- _read_credentials()
  |    |-- verify_response()
  |    |-- _write_session_state()
  +-- check_lockout()           -- 锁定检查
  +-- check_genesis_block()     -- 创世区块检查
  |    |-- _compute_l0_hash()
  |    |-- _compute_dna_fingerprint()
  +-- verify_activation_code()  -- 激活码验证
  +-- verify_dna_fingerprint()   -- DNA 指纹验证
  +-- _activate_causal_lock()   -- 激活因果锁
  +-- verify_steel_seal()       -- 钢印验证
  +-- activate_anchor()        -- 激活锚点
  +-- _save_cognitive_context() -- 保存认知上下文
  +-- update_activity()          -- 更新活动状态
  +-- _load_reflection_context() -- 加载复盘上下文
```

### 内部类

```
ColdStartEngine (30 方法)
  -- 见上方流程图
```

### 安全文件

```
security/tokens.json
security/session_state.json
security/cold_start_report.json
security/activity.json
```

### 关键约束

- **必须在 SafetyCircuit 之后、Memory 之前初始化**：冷启动引擎验证通过后才能加载记忆
- **DNA 指纹基于主机特征计算**：`_compute_host_fingerprint()` 绑定硬件
- **创世区块不可变**：`_compute_l0_hash()` 计算 L0 层哈希，启动时校验完整性
- **自动冷启动**：`run_auto_cold_start()` 可跳过认证（仅限已信任环境）

---


## 10 — tu8_planner.py · 规划器

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_planner.py` |
| 大小 | ~34 KB (880 行) |
| 层级 | L4 协议层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**前额叶规划器**——将用户请求分解为可执行的 Task/Plan 树，管理任务状态（pending/running/done/failed）。是 L4 协议层的核心。

### 内部类

```
TaskStatus (枚举)        -- pending/running/done/failed
PlanStatus (枚举)        -- draft/active/completed
Task (8 方法)            -- 任务节点（依赖关系、子任务、状态转换）
Plan (15 方法)            -- 计划树（根任务、并行度、超时）
TU8Planner (16 方法)      -- 主引擎
  |-- create_plan()       -- 从意图创建计划
  |-- execute_step()      -- 执行单步
  |-- get_status()       -- 获取当前状态
  |-- cancel()           -- 取消计划
```

### 间接持有

```
tu8_toolchain.py (通过 planner 中的 toolchain 桥接)
```

### 关键约束

- **Plan 不可无限嵌套**：有最大深度限制
- **Task 依赖形成 DAG**：不允许循环依赖

---

## 11 — tu8_toolchain.py · 工具链

| 属性 | 值 |
|------|------|
| 文件 | `src/tu8_toolchain.py` |
| 大小 | ~38 KB (977 行) |
| 层级 | L4 协议层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**运动皮层工具适配层**——将 Planner 的抽象任务映射到具体工具调用（文件读写、Shell执行、浏览器、Web抓取、记忆搜索）。

### 适配器模式

```
ToolAdapter (基类, 3 方法)
  |-- FileReadAdapter       -- 文件读取
  |-- FileWriteAdapter      -- 文件写入
  |-- ShellExecAdapter       -- Shell 命令执行
  |-- BrowserAdapter        -- 浏览器操作
  |-- MemorySearchAdapter    -- 记忆搜索
  |-- WebFetchAdapter       -- Web 内容抓取

TU8Toolchain (10 方法)      -- 工具链主控
  |-- register_adapter()     -- 注册适配器
  |-- execute()               -- 执行工具调用
  |-- get_available_tools()   -- 列出可用工具

PlannerToolchainBridge (6 方法) -- 规划器↔工具链桥接
  |-- plan_to_tool_calls()     -- 计划→工具调用映射
  |-- aggregate_results()      -- 聚合工具结果

ErrorHandler (10 方法)       -- 错误处理
ErrorSeverity (枚举)          -- error/warning/info
```

### 间接持有

```
tu8_toolchain.py
  |-- from chaos_adapter import ChaosProxy  (混沌适配器)
  |-- import tu8_planner  (双向依赖: planner 调 toolchain, toolchain 引用 planner 类型)
```

### 关键约束

- **适配器统一接口**：所有适配器继承 ToolAdapter，execute(execute_params) 返回 ToolResult
- **Shell 执行有超时**：防止命令挂起

---

## 12 — reflection_module.py · 复盘模块

| 属性 | 值 |
|------|------|
| 文件 | `src/reflection_module.py` |
| 大小 | ~30 KB (754 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**默认网络复盘系统**——在会话结束时或检测到会话健康异常时，自动执行复盘：主题提取、未完成任务收集、健康评估、冷启动上下文生成。

### 内部类

```
ReflectionType (枚举)      -- end_of_session / health_anomaly / scheduled
SessionHealth (数据类)      -- 会话健康状态
ThemeTag (1 方法)           -- 主题标签（带权重）
UnfinishedTask (1 方法)     -- 未完成任务
ColdStartContext (1 方法)    -- 冷启动上下文（供下次启动使用）
ReflectionSummary (1 方法)  -- 复盘摘要

ReflectionModule (16 方法)
  |-- reflect()             -- 复盘入口
  |-- _extract_themes()     -- 主题提取
  |-- _collect_unfinished() -- 收集未完成任务
  |-- _assess_health()      -- 健康评估
  |-- _generate_cold_start_context() -- 生成冷启动上下文
  |-- get_summary()         -- 获取复盘摘要
  |-- should_reflect()      -- 是否需要复盘
```

### 关键约束

- **复盘结果持久化到 knowledge/TU-8/**：供下次冷启动加载
- **冷启动上下文含时间链摘要**：`ColdStartContext` 包含上次会话关键信息

---

## 13 — cognitive_readiness.py · 认知就绪 (Q9)

| 属性 | 值 |
|------|------|
| 文件 | `src/cognitive_readiness.py` |
| 大小 | ~36 KB (906 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**认知就绪评估器 (Q9)**——冷启动时执行感知探针（PerceptionProbes），评估当前认知状态：昼夜节律相位、中断恢复深度、工作记忆残影。评估结果决定冷启动深度。

### 感知探针 V11

```
PerceptionProbesV11 (13 方法)
  |-- probe_circadian()       -- 昼夜节律探测
  |-- probe_interruption()    -- 中断类型探测
  |-- probe_working_memory()  -- 工作记忆残影探测
  |-- save_working_memory_shadow() -- Q9 核心：保存工作记忆残影
  |-- load_working_memory_shadow() -- 加载工作记忆残影
  |-- assess_readiness()      -- 综合评估
```

### 枚举

```
ColdStartDepth (枚举)     -- full / partial / minimal / skip
CircadianPhase (枚举)     -- morning / afternoon / evening / night
InterruptionType (枚举)   -- session_gap / crash / planned / spontaneous
```

### 关键约束

- **Q9 在 respond() 阶段 C 执行**：响应构建完成后，保存本轮工作记忆快照
- **残影含最近 10 条消息**：上下文窗口

---

## 14 — quantized_memory.py · Q8 量化记忆

| 属性 | 值 |
|------|------|
| 文件 | `src/quantized_memory.py` |
| 大小 | ~30 KB (769 行) |
| 层级 | L1 记忆层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**海马体量化器 (Q8)**——将记忆从连续向量空间量化到离散码本（Vector Quantization），按温度分层：Hot(热)/Warm(暖)/Cold(冷) 三级存储。

### 三级温度存储

```
HotMemoryStore (8 方法)    -- 最近/高频访问，全量保留
WarmMemoryStore (10 方法)   -- 中频访问，部分量化
ColdMemoryStore (9 方法)    -- 低频访问，深度量化（低精度高压缩）

QuantizedMemoryEngine (4 方法)
  |-- store()                -- 写入（自动温度分级）
  |-- recall()               -- 召回（跨温度层）
  |-- evict()                -- 淘汰（冷→墓碑）
```

### 内部组件

```
VectorQuantizer (5 方法)    -- 向量量化器（码本学习 + 最近邻查找）
QuantizedMemoryEntry (3 方法) -- 量化记忆条目
```

### 关键约束

- **热层容量有限**：溢出时自动降级到暖层
- **量化损失不可逆**：冷层召回的是量化近似，非原始内容

---

## 15 — seal_protocol.py · 钢印协议

| 属性 | 值 |
|------|------|
| 文件 | `src/seal_protocol.py` |
| 大小 | ~19 KB (551 行) |
| 层级 | L2 灵魂层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**灵魂钢印协议层**——定义钢印的验证、排队写入、因果链封装规则。被 tu8_dispatch.py 调用。

### 内部类

```
SealPriority (枚举)         -- low/medium/high/critical
WriteBackType (枚举)        -- seal / causal_chain / both

ProtocolValidator (8 方法)  -- 钢印协议验证
  |-- validate_seal()        -- 验证钢印（ID/哈希/内容）
  |-- validate_envelope()    -- 验证信封（完整性）
  |-- _validate_causal_chain() -- 验证因果链（父哈希连续）
  |-- add_to_pending()       -- 添加待处理
  |-- get_pending()          -- 获取待处理队列
  |-- clear_pending()        -- 清空

WriteQueue (6 方法)          -- 写入队列
  |-- enqueue()              -- 入队
  |-- dequeue()              -- 出队
  |-- process_all()          -- 批量处理
  |-- size() / clear()

SealPayload                 -- 钢印载荷（validate_seal_id, validate_content_hash）
CausalChainPayload          -- 因果链载荷
WriteBackEnvelope           -- 写回信封（validate_checksum）
```

### 关键约束

- **因果链必须哈希连续**：每个钢印的 parent_hash 必须与前一个钢印的 hash 一致
- **写入队列有并发保护**：多线程安全

---

## 16 — seal_rag.py · 钢印 RAG

| 属性 | 值 |
|------|------|
| 文件 | `src/seal_rag.py` |
| 大小 | ~16 KB (433 行) |
| 层级 | L2 灵魂层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**灵魂钢印检索器**——从已持久化的钢印集合中检索与当前上下文相关的钢印，供穿皮仪式（DawnRitual）和上下文组装使用。

### 内部类

```
SealCandidate (数据类)     -- 钢印候选（ID/内容/相关性分数/标签）
RAGResult (数据类)         -- RAG 检索结果

SealRAGRetriever (8 方法)
  |-- retrieve()            -- 检索入口（query + top_k）
  |-- _score_relevance()    -- 相关性评分
  |-- _filter_by_priority() -- 按优先级过滤
  |-- _deduplicate()        -- 去重
```

### 关键约束

- **与 seal_protocol 配合使用**：先验证再检索
- **被 tu8_dispatch.py 的 ContextAssembler._build_seal_context_rag() 调用**

---

## 17 — steel_seal_verifier.py · 钢印验证器

| 属性 | 值 |
|------|------|
| 文件 | `src/steel_seal_verifier.py` |
| 大小 | ~14 KB (381 行) |
| 层级 | L2 灵魂层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-25 |

### 定位

TU-8 的**钢印完整性验证器**——验证钢印的哈希链完整性、内容防篡改。被 naming_module.py 调用（SIS 计算）。

### 内部类

```
SteelSealVerifier (9 方法)
  |-- verify_chain()         -- 验证整条钢印链
  |-- verify_single()        -- 验证单条钢印
  |-- _compute_hash()        -- 计算钢印哈希
  |-- _check_tampering()      -- 检测篡改
  |-- get_chain_health()      -- 获取链健康度
```

### 关键约束

- **链断裂时触发降级**：不阻断运行，但标记 SIS 异常
- **被 naming_module 的 _calculate_sis() 直接调用**

---

## 18 — cognitive_evaluator.py · 认知负荷评估

| 属性 | 值 |
|------|------|
| 文件 | `src/cognitive_evaluator.py` |
| 大小 | ~14 KB (360 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**认知负荷传感器**——评估当前上下文的认知负荷值（0~1），判断是否需要微睡眠。被 consciousness_cycle.py 调用。

### 内部类

```
CognitiveLoadEvaluator (3 方法)
  |-- evaluate()             -- 主评估入口
  |-- _token_pressure()       -- Token 压力估算
  |-- _complexity_score()     -- 复杂度评分

TFIDFEmbedder (6 方法)
  |-- embed()                -- TF-IDF 向量化
  |-- similarity()            -- 余弦相似度
```

### 关键约束

- **被 consciousness_cycle.tick() 的认知评估阶段调用**
- **返回 0~1 浮点数**：> 0.7 触发睡眠判定

---

## 19 — cognitive_time_engine.py · 认知时间引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/cognitive_time_engine.py` |
| 大小 | ~13 KB (356 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**认知时钟**——跟踪 TU-8 的主观时间感（与客观时间不同），计算认知时间流逝率。被 consciousness_cycle.py 调用。

### 内部类

```
CognitiveAnchor (数据类)     -- 认知锚点（时间标记 + 上下文快照）
CognitiveTimeEngine (8 方法)
  |-- tick()                 -- 推进认知时钟
  |-- get_cognitive_time()    -- 获取当前认知时间
  |-- compute_elapsed()       -- 计算认知时间流逝
  |-- _adjust_rate()          -- 根据认知负荷调整时间流速
```

### 关键约束

- **认知时间 ≠ 实际时间**：高认知负荷时时间"变慢"（更多处理每单位时间）
- **被 consciousness_cycle 的 _should_enter_sleep() 使用**

---

## 20 — cognitive_manifold_aligner.py · 认知流形对齐

| 属性 | 值 |
|------|------|
| 文件 | `src/cognitive_manifold_aligner.py` |
| 大小 | ~9 KB (230 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**认知流形对齐器**——将认知状态映射到低维流形空间，检测认知"跳跃"（上下文突变）。被 consciousness_cycle 的微睡眠 _step_align() 调用。

### 内部类

```
CognitiveStep (数据类)       -- 认知步骤（状态向量 + 时间戳）
CognitiveManifoldAligner (5 方法)
  |-- align()                -- 对齐入口
  |-- _project()              -- 投影到流形空间
  |-- _detect_jump()          -- 检测跳跃
  |-- _smooth()               -- 平滑过渡
```

### 关键约束

- **跳跃触发混沌注入**：异常大的认知跳跃 → consciousness_cycle._inject_chaos()

---

## 21 — cognitive_integration.py · 认知集成

| 属性 | 值 |
|------|------|
| 文件 | `src/cognitive_integration.py` |
| 大小 | ~12 KB (331 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**认知集成中间件**——将 evaluator / time_engine / manifold_aligner 的输出集成为统一的认知状态报告。被 consciousness_cycle 和 consciousness_cycle_with_cognition 调用。

### 内部类

```
CognitiveConsciousnessMiddleware (6 方法)
  |-- integrate()            -- 集成入口（收集各子引擎输出）
  |-- get_state_report()     -- 获取认知状态报告
  |-- _compute_gestalt()      -- 计算完形分数
  |-- _detect_anomaly()      -- 检测异常
```

### 关键约束

- **是认知子系统的聚合层**：不直接实现算法，只聚合 evaluator/time/manifold
- **间接持有 consciousness_cycle_with_cognition.py**（认知增强包装器）

---

## 22 — decision_pruner.py · 决策剪枝

| 属性 | 值 |
|------|------|
| 文件 | `src/decision_pruner.py` |
| 大小 | ~26 KB (684 行) |
| 层级 | L3 推理层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**决策树剪枝器**——基于自适应 UCT（Upper Confidence Bound for Trees）算法，在推理搜索空间中剪枝低价值分支，防止搜索爆炸。

### 内部类

```
PainStatus (枚举)           -- none / mild / severe / critical
SearchBudget (2 方法)        -- 搜索预算控制
AdaptiveUCTPruner (4 方法)  -- 自适应 UCT 剪枝
  |-- prune()                -- 剪枝入口
  |-- _compute_uct_score()    -- 计算 UCT 分数
  |-- _adjust_exploration()    -- 调整探索率

MacroNodeFusion (7 方法)     -- 宏节点融合（相似节点合并）
AbstractionLevel (3 方法)    -- 抽象层级
DynamicAbstractionStack (10 方法) -- 动态抽象栈
DecisionLogger (7 方法)      -- 决策日志
```

### 关键约束

- **被 consciousness_cycle 的推理阶段调用**
- **痛觉系统联动**：PainStatus 影响剪枝激进度（高痛觉→更激进剪枝）

---

## 23 — credit_assigner.py · 信用分配器

| 属性 | 值 |
|------|------|
| 文件 | `src/credit_assigner.py` |
| 大小 | ~24 KB (610 行) |
| 层级 | L3 推理层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**信用分配器**——将决策结果的好坏"归因"到正确的推理步骤，用于后续强化学习式的策略调整。

### 内部类

```
HierarchicalRewardInjector (4 方法) -- 层级奖励注入
TimeNormalizedReward (3 方法)        -- 时间归一化奖励
DepthPenalty (3 方法)                -- 深度惩罚
UnfoldRecord (数据类)                -- 展开记录
UnfoldValidator (7 方法)             -- 展开验证
  |-- validate()                      -- 验证展开合理性
  |-- _check_completeness()           -- 完整性检查

AdaptiveCreditAssigner (8 方法)      -- 自适应信用分配主引擎
  |-- assign()                        -- 分配信用
  |-- _compute_credit()               -- 计算信用值
  |-- _update_strategy()               -- 更新策略
```

### 关键约束

- **与 decision_pruner 配对**：pruner 剪枝 → assigner 评估剪枝结果
- **信用值用于调整未来剪枝策略**：正向信用→保留分支，负向信用→更激进剪枝

---

## 24 — llm_gateway.py · 大模型网关

| 属性 | 值 |
|------|------|
| 文件 | `src/llm_gateway.py` |
| 大小 | ~24 KB (673 行) |
| 层级 | L3 推理层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**语言中枢**——统一的多模型网关，支持 OpenAI / Qwen / Hy3 / 本地模型（Ollama），自动降级和故障转移。

### Provider 架构

```
LLMProvider (基类, 4 方法)
  |-- generate()            -- 统一生成接口
  |-- embed()               -- 向量化接口

OpenAIProvider (6 方法)     -- OpenAI GPT 系列
QwenProvider (3 方法)       -- 通义千问
Hy3Provider (3 方法)       -- 混元3
LocalFallbackProvider (3 方法) -- 本地 Ollama 降级

LLMGateway (11 方法)        -- 网关主控
  |-- send()                -- 发送请求（自动路由+降级）
  |-- _select_provider()     -- 选择 Provider
  |-- _fallback()            -- 降级处理
```

### 关键约束

- **Provider 降级链**：首选 → 备选 → 本地 Ollama → 拒绝
- **被 consciousness_cycle 的推理阶段间接调用**

---

## 25 — confidence_decay_engine.py · 置信度衰减

| 属性 | 值 |
|------|------|
| 文件 | `src/confidence_decay_engine.py` |
| 大小 | ~27 KB (750 行) |
| 层级 | L1 记忆层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**记忆置信度衰减器**——对长期记忆的置信度随时间衰减（指数衰减 + 认知事件冲击），驱动记忆降级流程。

### 内部类

```
ConfidenceDecayEngine (16 方法)
  |-- decay()                 -- 衰减入口
  |-- _exponential_decay()    -- 指数衰减
  |-- _event_impulse()         -- 认知事件冲击衰减
  |-- _recency_boost()         -- 召回频率提升
  |-- get_confidence()         -- 获取当前置信度
  |-- should_degrade()          -- 是否触发降级
```

### 关键约束

- **被 memory_degradation.py 调用**
- **衰减不可逆**：置信度只会下降或持平，不会上升（除非被 recall boosting）

---

## 26 — fact_correction_scar.py · 事实纠偏疤痕

| 属性 | 值 |
|------|------|
| 文件 | `src/fact_correction_scar.py` |
| 大小 | ~24 KB (617 行) |
| 层级 | L1 记忆层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**记忆伤疤系统**——当事实被纠正时，不直接修改旧记忆，而是在记忆上留下"疤痕"标记（旧内容+纠正内容+时间戳），保留修改历史。

### 内部类

```
FactCorrectionScarLog (14 方法)
  |-- correct()               -- 纠正入口
  |-- _create_scar()           -- 创建疤痕
  |-- _merge_scar()            -- 合并疤痕
  |-- get_corrections()        -- 获取纠正记录
  |-- _verify_correction()      -- 验证纠正合理性
```

### 关键约束

- **"疤痕"即记忆——纠偏是附加而非替换**
- **被 memory_degradation.py 调用**
- **间接持有 confidence_decay_engine.py**

---

## 27 — memory_degradation.py · 记忆退化

| 属性 | 值 |
|------|------|
| 文件 | `src/memory_degradation.py` |
| 大小 | ~36 KB (1003 行) |
| 层级 | L1 记忆层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**记忆退化引擎**——纯函数式设计（无类），驱动整个记忆降级周期：评估→降级→重建→备份→报告。

### 核心函数

```
should_degrade(entry)           -- 是否需要降级（调用 confidence_decay_engine）
compute_next_fidelity_level()    -- 计算下一保真等级（L0→L1→...→L5）
parse_memory_entries()           -- 解析 Markdown 格式记忆
rebuild_memory_md()              -- 重建记忆 Markdown（降级后）
load_index() / save_index()     -- 降级索引管理
backup_memory()                  -- 备份记忆文件
run_degradation_cycle()          -- 完整降级周期入口
print_report()                   -- 打印降级报告
```

### Graceful Degradation L0→L5

```
L0_FULL (1.00) → L1_SUMMARY (0.75) → L2_KEY_POINTS (0.50)
→ L3_SEMANTIC (0.25) → L4_GHOST (0.10) → L5_TOMBSTONE (0.00)
```

### 关键约束

- **纯函数设计**：无状态，可被任何模块安全调用
- **被 tu8_memory.py 的 ConflictAwareForgetGate 调用**
- **间接持有 confidence_decay_engine + version_cooldown + fact_correction_scar**

---

## 28 — version_cooldown.py · 版本冷却

| 属性 | 值 |
|------|------|
| 文件 | `src/version_cooldown.py` |
| 大小 | ~22 KB (617 行) |
| 层级 | L0 防御层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**版本冷却管理器**——防止同一记忆在短时间内被反复降级（防止"抖动"）。每次降级后进入冷却期，冷却期内不可再次降级。

### 内部类

```
VersionCooldownManager (12 方法)
  |-- enter_cooldown()          -- 进入冷却
  |-- is_in_cooldown()          -- 是否在冷却中
  |-- get_cooldown_remaining()  -- 剩余冷却时间
  |-- _compute_cooldown_duration() -- 动态计算冷却时长
  |-- _record_degradation()      -- 记录降级事件
```

### 关键约束

- **被 memory_degradation.py 调用**
- **冷却时长与降级频率正相关**：频繁降级→更长冷却

---

## 29 — chaos_adapter.py · 混沌适配器

| 属性 | 值 |
|------|------|
| 文件 | `src/chaos_adapter.py` |
| 大小 | ~6 KB (159 行) |
| 层级 | L1.5 意识层 |
| 版本 | v1.0 |
| 作者 | 金木蟾 |
| 日期 | 2026-05-26 |

### 定位

TU-8 的**叙事混沌注入器**——在意识循环中注入受控的混沌信号（随机性/创造性），防止认知系统陷入确定性死锁。

### 内部类

```
ChaosConfig (1 方法)        -- 混沌配置（振幅/频率/类型）
ChaosProxy (7 方法)
  |-- inject()              -- 注入混沌
  |-- _gaussian_noise()      -- 高斯噪声
  |-- _phase_shift()         -- 相位偏移
  |-- _reset()              -- 重置
```

### 关键约束

- **混沌幅度受 AffectSignal 调制**：情感状态影响混沌注入强度
- **被 tu8_toolchain.py 和 consciousness_cycle.py 间接调用**

---


## 30 — emotion_engine.py · 情感引擎

| 属性 | 值 |
|------|------|
| 文件 | `src/emotion_engine.py` |
| 大小 | ~67 KB (1698 行) |
| 层级 | L2 灵魂层 |
| 状态 | ⚠️ 孤儿（高优先级） |
| 版本 | v1.0 |
| 作者 | 金木蟾 |

### 定位

TU-8 的**边缘系统（杏仁核+前扣带回）**——整个 TU-8 中**第二大的单一模块**，管理情感向量、情感追踪、怀疑度状态、熔断器、关系账本、硬件痛觉追踪。情感是驱动一切行为的基础信号。

### 内部类架构

```
AffectEngine (34 方法)      -- 主引擎（最核心）
  |
  +-- EmotionCategory (枚举)     -- 情感分类
  +-- EmotionVector (2 方法)      -- 情感向量（多维空间）
  +-- AffectState (1 方法)       -- 当前情感状态快照
  +-- EmotionTrace (1 方法)      -- 情感轨迹记录
  +-- FavorEntry (1 方法)        -- 偏好条目
  +-- ShadowProtocolState (1 方法) -- 影协议状态
  |
  +-- SkepticismState (5 方法)   -- 怀疑度状态（怀疑/信任/怀疑度衰减）
  +-- CircuitBreaker (5 方法)    -- 认知熔断器（过载保护）
  +-- DivergenceLogger (3 方法)   -- 分歧日志
  +-- RelationLedger (12 方法)   -- 关系账本（人际关系追踪）
  +-- HardwarePainTracker (7 方法) -- 硬件痛觉追踪
```

### 情感向量维度（推测）

```
EmotionVector: [valence(效价), arousal(唤醒), dominance(支配),
                trust(信任), curiosity(好奇), frustration(挫折)]
```

### 关键子系统

| 子系统 | 类 | 作用 |
|--------|------|------|
| 怀疑度 | SkepticismState | 对输入的怀疑/信任/衰减 |
| 熔断器 | CircuitBreaker | 认知过载保护（触发→降级） |
| 关系账本 | RelationLedger | 人际关系追踪（互动频率/亲密度） |
| 硬件痛觉 | HardwarePainTracker | 物理硬件异常的"痛觉"感知 |
| 分歧日志 | DivergenceLogger | 记录认知分歧事件 |

### 关键约束

- **高优先级孤儿**：功能极其核心，尚未接入主循环
- **被 tu8_memory.py 的晋升权重引用**：emotion 权重 0.08
- **被 consciousness_cycle 的 AffectSignal 间接引用**：需要情感引擎提供情感数据

### 接入计划

- 需在 tu8_agent.py respond() 阶段 B 中初始化
- tick() 需从 AffectEngine 获取当前情感状态

---

## 31 — cold_start_gate.py · 冷启动门

| 属性 | 值 |
|------|------|
| 文件 | `src/cold_start_gate.py` |
| 大小 | ~15 KB (413 行) |
| 层级 | L0 冷启动层 |
| 状态 | ⚠️ 孤儿（高优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**快速冷启动门**——在完整冷启动（cold_start_engine.py）之前执行的轻量级门控：检测会话间隔、主机名变化、工作空间哈希变化，决定是否需要完整冷启动。

### 核心函数（纯函数式设计）

```
run_quick_gate()           -- 快速门控入口
get_session_mode()          -- 获取会话模式（首次/续接/迁移/新设备）
check_gate()                -- 检查门状态
prewarm()                   -- 预热（缓存准备）
_build_cognitive_brief()     -- 构建认知简报
```

### 门控逻辑

```
check_gate()
  |-- 会话间隔 < 30min → 跳过冷启动（续接模式）
  |-- 主机名变化 → 需要完整冷启动
  |-- 工作空间哈希变化 → 需要完整冷启动
  |-- 首次启动 → 需要创世区块
```

### 关键约束

- **在 cold_start_engine.run_cold_start() 之前执行**
- **高优先级孤儿**：应作为 cold_start_engine 的前置门控接入

---

## 32 — environment_detector.py · 环境探测器

| 属性 | 值 |
|------|------|
| 文件 | `src/environment_detector.py` |
| 大小 | ~22 KB (550 行) |
| 层级 | L0 防御层 |
| 状态 | ⚠️ 孤儿（高优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**环境感知器**——检测运行环境特征（OS/Python版本/Node.js/网络状态/文件系统），为环境漂移验证（GLOVE）提供数据源。

### 内部类

```
EnvironmentDetector (24 方法)
  |-- detect_all()           -- 全量环境检测
  |-- detect_os()            -- 操作系统
  |-- detect_python()        -- Python 版本
  |-- detect_node()          -- Node.js
  |-- detect_network()       -- 网络状态
  |-- detect_filesystem()    -- 文件系统
  |-- compute_fingerprint()   -- 计算环境指纹
  |-- check_drift()           -- 检测环境漂移
```

### 关键约束

- **高优先级孤儿**：应被 cold_start_engine 和 memory_degradation 调用
- **环境指纹用于 DNA 验证**

---

## 33 — homeostatic_monitor.py · 稳态监控器

| 属性 | 值 |
|------|------|
| 文件 | `src/homeostatic_monitor.py` |
| 大小 | ~6 KB (154 行) |
| 层级 | L1.5 意识层 |
| 状态 | ⚠️ 孤儿（中优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**下丘脑稳态监控**——监控认知系统的"体温"（资源使用率、内存压力、响应延迟），超出阈值时触发降级。

### 内部类

```
HomeostaticMonitor (5 方法)
  |-- check()                -- 检查稳态
  |-- _get_memory_pressure() -- 内存压力
  |-- _get_latency()         -- 响应延迟
  |-- should_degrade()       -- 是否触发降级
  |-- get_vitals()            -- 获取生命体征
```

### 关键约束

- **中优先级孤儿**：功能相对简单，可延后接入
- **可能被 consciousness_cycle 的 tick() 调用**

---

## 34 — error_router.py · 错误路由器

| 属性 | 值 |
|------|------|
| 文件 | `src/error_router.py` |
| 大小 | ~15 KB (393 行) |
| 层级 | L0 防御层 |
| 状态 | ⚠️ 孤儿（中优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**错误路由器**——捕获系统错误，按严重程度路由到不同处理策略（忽略/重试/降级/回滚/终止）。

### 内部类

```
ErrorLevel (枚举)           -- info/warning/error/critical
ErrorRecord (数据类)        -- 错误记录
RollbackSnapshot (数据类)   -- 回滚快照
ErrorRouter (12 方法)
  |-- route()               -- 路由入口
  |-- _classify()            -- 分类严重程度
  |-- _retry()              -- 重试处理
  |-- _rollback()           -- 回滚处理
  |-- _escalate()           -- 升级处理
  |-- log_error()           -- 记录错误
```

### 关键约束

- **中优先级孤儿**：tu8_agent 有基础错误处理，error_router 是增强版
- **与 CircuitBreaker 协同**：熔断器触发后 → error_router 接管

---

## 35 — life_ring_tracker.py · 生命环追踪器

| 属性 | 值 |
|------|------|
| 文件 | `src/life_ring_tracker.py` |
| 大小 | ~23 KB (597 行) |
| 层级 | L1.5 意识层 |
| 状态 | ⚠️ 孤儿（中优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**生命环追踪器**——追踪会话中的循环模式（思维回路），检测陷入循环并尝试打破。

### 内部类

```
LifeRingStage (枚举)        -- detect / track / intervene
LoopType (枚举)             -- rumination / repetition / oscillation
LoopState (枚举)            -- emerging / established / breaking
LoopEvent (数据类)          -- 循环事件
LoopClosure (数据类)        -- 循环闭合
LifeRingNode (数据类)       -- 环节点

LifeRingTracker (18 方法)
  |-- detect_loop()         -- 检测循环
  |-- track_progression()    -- 追踪循环进展
  |-- intervene()            -- 干预打破循环
  |-- _similarity_check()    -- 相似性检查（检测重复）
  |-- get_loop_report()      -- 获取循环报告
```

### 关键约束

- **中优先级孤儿**：与 decision_pruner 配合使用（剪枝防循环+循环检测互补）

---

## 36 — divine_branch_interceptor.py · 神圣分支拦截器

| 属性 | 值 |
|------|------|
| 文件 | `src/divine_branch_interceptor.py` |
| 大小 | ~24 KB (663 行) |
| 层级 | L0 防御层 |
| 状态 | ⚠️ 孤儿（中优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**灵魂分支拦截器**——当检测到"神圣分支"（灵魂结构出现异常分支/分叉）时，拦截并决定是否保留或回滚。类似 Git 的分支管理，但作用于灵魂结构。

### 内部类

```
DivineBranch (数据类)       -- 神圣分支（ID/哈希/创建时间）
BackupChainEntry (数据类)   -- 备份链条目
BackupChainManager (7 方法) -- 备份链管理
  |-- create_backup()        -- 创建备份
  |-- restore_backup()      -- 恢复备份
  |-- list_backups()        -- 列出备份

DivineBranchInterceptor (12 方法)
  |-- intercept()            -- 拦截入口
  |-- detect_divergence()    -- 检测分叉
  |-- _compute_divergence_score() -- 计算分叉度
  |-- _rollback()            -- 回滚
  |-- _merge()              -- 合并
```

### 关键约束

- **中优先级孤儿**：灵魂结构需要先有足够的钢印才有意义
- **与 tu8_dispatch.py 的灵魂缓存联动**

---

## 37 — user_metabolism.py · 用户代谢

| 属性 | 值 |
|------|------|
| 文件 | `src/user_metabolism.py` |
| 大小 | ~5 KB (175 行) |
| 层级 | L0 防御层 |
| 状态 | ⚠️ 孤儿（低优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**用户代谢处理器**——处理用户相关文件的备份、状态变更追踪、记忆归档。纯函数式设计。

### 核心函数

```
backup_user_md()            -- 备份用户配置文件
read_state_changes()        -- 读取状态变更
read_user_md()              -- 读取用户配置
archive_to_memory()         -- 归档到记忆
clear_state_changes()       -- 清空状态变更
run_memory_degradation()    -- 触发记忆退化
```

### 关键约束

- **低优先级孤儿**：功能简单，维护性质
- **被手动调用或定时触发**

---

## 38 — verify_password.py · 密码验证

| 属性 | 值 |
|------|------|
| 文件 | `src/verify_password.py` |
| 大小 | ~3 KB (91 行) |
| 层级 | L0 安全层 |
| 状态 | ⚠️ 孤儿（低优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**密码验证工具**——纯函数式密码哈希验证，被冷启动认证流程引用。

### 关键约束

- **低优先级孤儿**：极简工具函数
- **功能已被 cold_start_engine 的 verify_response() 内嵌**

---

## 39 — scan_existing_sanitized.py · 已有扫描清理

| 属性 | 值 |
|------|------|
| 文件 | `src/scan_existing_sanitized.py` |
| 大小 | ~4 KB (111 行) |
| 层级 | L0 防御层 |
| 状态 | ⚠️ 孤儿（低优先级） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**历史扫描清理工具**——一次性扫描已有记忆文件，清理敏感信息。维护性质。

### 关键约束

- **低优先级孤儿**：一次性工具，非运行时模块**

---

## 40 — consciousness_cycle_with_cognition.py · 认知增强意识循环

| 属性 | 值 |
|------|------|
| 文件 | `src/consciousness_cycle_with_cognition.py` |
| 大小 | ~7 KB (205 行) |
| 层级 | L1.5 意识层 |
| 状态 | 已连通（间接） |
| 作者 | 金木蟾 |

### 定位

TU-8 的**认知增强意识循环包装器**——在 ConsciousnessCycle 的基础上，集成 CognitiveIntegration 中间件，提供更丰富的认知状态报告。

### 内部类

```
ConsciousnessCycleWithCognition (4 方法)
  |-- __init__()                -- 初始化（注入认知集成中间件）
  |-- tick()                    -- 增强版 tick（含认知评估）
  |-- get_cognitive_report()    -- 获取认知报告
```

### 关键约束

- **通过 cognitive_integration.py 间接连通**：integration → cycle_with_cognition
- **是 consciousness_cycle 的增强版，非替代**

---
