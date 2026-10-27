# consciousness_cycle.py 架构设计文档 v2.0

**日期**：2026-06-27 02:29 GMT+8
**版本**：v2.0（重构设计）
**状态**：设计阶段

---

## 一、架构总览

### 1.1 三轨道六层三路由架构

```
┌─────────────────────────────────────────────────────────┐
│                    Track A: 对话流记忆                   │
│                    （时间维度，4-6h ~ 21h）              │
├─────────────────────────────────────────────────────────┤
│  L1: 工作记忆（KV Cache，秒级）                         │
│      └─ 当前对话上下文                                  │
│                                                         │
│  L2: 情景记忆（钢印链，分钟~小时级）                     │
│      └─ 记忆卡（MemoryEntry）                           │
│          ├─ seal_id（钢印ID）                           │
│          ├─ content（叙事摘要）                         │
│          ├─ state_vector（状态向量）                    │
│          ├─ trigger_hooks（触发钩子）                   │
│          └─ semantic_hooks（语义钩子）                  │
│                                                         │
│  L3: 长期记忆（21h 硬边界）                             │
│      └─ 对话级长期记忆                                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    Track B: 深记忆区                     │
│                    （认知维度，7天 ~ 永久）              │
├─────────────────────────────────────────────────────────┤
│  B1: 缓冲区（7-14天，中速衰减）                         │
│      └─ 待巩固记忆                                      │
│                                                         │
│  B2: 长期记忆（状态驱动，慢速衰减）                      │
│      └─ 已巩固记忆                                      │
│                                                         │
│  B3: 核心记忆（零衰减锚点）                             │
│      └─ 认知锚点（CognitiveAnchor）                     │
│          ├─ anchor_id                                   │
│          ├─ seal_ids（来源钢印）                        │
│          ├─ content（固化知识）                         │
│          ├─ anchor_type（锚点类型）                     │
│          └─ confidence（置信度）                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    Track C: 工作记忆区                   │
│                    （职业维度，任务 ~ 职业）             │
├─────────────────────────────────────────────────────────┤
│  C1: 活跃工作台（任务级）                               │
│      └─ 当前任务上下文                                  │
│                                                         │
│  C2: 项目态势图（项目级）                               │
│      └─ 项目状态快照                                    │
│                                                         │
│  C3: 工作模式库（职业级）                               │
│      └─ 方法论沉淀                                      │
└─────────────────────────────────────────────────────────┘

──────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────┐
│                    三路由协作                            │
├─────────────────────────────────────────────────────────┤
│  R1: 对话流路由（同步，<100ms）                         │
│      └─ 处理对话输入/输出                               │
│                                                         │
│  R2: 元认知路由（异步批量，秒/分钟级）                  │
│      └─ 记忆巩固/钩子养护/认知锚点生成                  │
│                                                         │
│  R3: 工作记忆路由（事件驱动，<500ms）                   │
│      └─ memory/archive/2026-05/项目管理                                   │
└─────────────────────────────────────────────────────────┘

──────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────┐
│                    EventBus（事件总线）                  │
├─────────────────────────────────────────────────────────┤
│  └─ 解耦三路由协作                                      │
│  └─ 防环机制                                            │
│  └─ 优先级队列                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 二、核心模块设计

### 2.1 模块拆分（6个模块）

| 模块 | 文件 | 行数 | 职责 |
|------|------|------|------|
| **类型定义** | `cycle_types.py` | ~300 | 枚举、数据类 |
| **钢印管理器** | `seal_manager.py` | ~400 | 钢印生成/验证/持久化 |
| **认知锚点管理器** | `anchor_manager.py` | ~300 | 锚点生成/检索/持久化 |
| **记忆适配器** | `memory_adapter.py` | ~200 | 记忆队列/写入 |
| **睡眠引擎** | `sleep_engine.py` | ~600 | 浅睡/深睡/冬眠 |
| **主控制器** | `consciousness_cycle.py` | ~400 | 状态机/路由调度 |

---

## 三、核心流程

### 3.1 对话流流程

```
用户输入
    ↓
R1.process_input()
    ↓
检测是否需要微睡眠
    ↓
[是] → SleepEngine.enter_light_sleep()
    ↓
微睡眠六步：
    FREEZE → COMPRESS → ALIGN → SEAL → RELEASE → RESTORE
    ↓
生成钢印 → 写入钢印链
    ↓
检测是否需要生成认知锚点
    ↓
[是] → AnchorManager.create_anchor()
    ↓
结晶为认知锚点 → 写入锚点库
    ↓
R1.process_output()
    ↓
返回响应
```

### 3.2 钩子养护流程

```
用户检索行为
    ↓
R1 检测 trigger_hooks 匹配
    ↓
钩子触发 → hit_score +1
    ↓
定期养护周期（R2）
    ↓
统计 hit_score
    ↓
[达到阈值] → 钩子晋升
[低于阈值] → 钩子淘汰
    ↓
更新记忆卡钩子字段
```

### 3.3 认知锚点生成流程

```
钢印链积累
    ↓
检测触发条件（5种）
    ├─ 用户明确指令
    ├─ 检测到重复模式
    ├─ 钢印链里程碑
    ├─ 外部系统同步
    └─ 睡眠周期结束
    ↓
[触发] → AnchorManager.create_anchor()
    ↓
提炼钢印链 → 结晶为锚点
    ↓
写入认知锚点库（L3）
    ↓
锚定 LLM 语义漂移
```

---

## 四、数据结构

### 4.1 记忆卡（MemoryEntry）

```python
@dataclass
class MemoryEntry:
    """L2 记忆卡"""
    seal_id: str                    # 钢印ID
    content: str                    # 叙事摘要
    state_vector: List[float]       # 状态向量
    created_at: str                 # 创建时间

    # 钩子字段（后期添加）
    trigger_hooks: List[str] = field(default_factory=list)   # 触发钩子
    semantic_hooks: List[str] = field(default_factory=list)  # 语义钩子

    # 元数据
    recall_count: int = 0           # 召回次数
    last_access: str = ""           # 最后访问时间
```

### 4.2 认知锚点（CognitiveAnchor）

```python
@dataclass
class CognitiveAnchor:
    """L3 认知锚点 - 锚定 LLM 语义漂移"""
    anchor_id: str                  # 锚点ID
    seal_ids: List[str]             # 来源钢印
    content: str                    # 固化知识
    anchor_type: str                # 锚点类型
    confidence: float = 0.8         # 置信度
    created_at: str = ""            # 创建时间

    # 锚定语义
    semantic_hash: str = ""         # 语义哈希
    drift_resistance: float = 1.0   # 抗漂移能力
```

### 4.3 钢印（Seal）

```python
@dataclass
class Seal:
    """钢印 - 时间链节点"""
    seal_id: str                    # 钢印ID
    seal_hash: str                  # 钢印哈希
    parent_hash: str = ""           # 父钢印哈希

    # 状态向量
    state_vector: StateVector       # 自我状态向量

    # 叙事压缩
    narrative_summary: str = ""     # 叙事摘要
    causal_coherence: float = 0.0   # 因果连贯性

    # 元数据
    created_at: str = ""
    gestalt_score: float = 0.0      # 格式塔评分
```

---

## 五、接口设计

### 5.1 SleepEngine 接口

```python
class SleepEngine:
    """睡眠引擎"""

    def __init__(self, config, seal_manager, memory_adapter):
        pass

    def enter_light_sleep(self, context: Dict) -> Dict:
        """浅睡 - 微睡眠六步"""
        pass

    def enter_deep_sleep(self) -> Dict:
        """深睡 - 记忆整合"""
        pass

    def should_enter_sleep(self, context: Dict) -> bool:
        """判断是否进入睡眠"""
        pass
```

### 5.2 SealManager 接口

```python
class SealManager:
    """钢印管理器"""

    def generate_seal(self, content: str, coherence: float) -> Seal:
        """生成钢印"""
        pass

    def verify_chain(self) -> bool:
        """验证钢印链完整性"""
        pass

    def persist(self):
        """持久化钢印链"""
        pass
```

### 5.3 AnchorManager 接口

```python
class AnchorManager:
    """认知锚点管理器"""

    def create_anchor(self, seal_ids: List[str], content: str,
                      anchor_type: str) -> CognitiveAnchor:
        """创建认知锚点 - 结晶化"""
        pass

    def retrieve_anchor(self, anchor_id: str) -> Optional[CognitiveAnchor]:
        """检索认知锚点"""
        pass

    def check_drift(self, anchor: CognitiveAnchor, current_context: str) -> float:
        """检测语义漂移"""
        pass
```

---

## 六、时序图

### 6.1 对话流时序图

```
用户         R1路由      微睡眠      钢印管理器    记忆适配器    L2钢印链
 │            │           │            │            │            │
 ├─输入─────→│           │            │            │            │
 │            ├─检测─────→│            │            │            │
 │            │           ├─FREEZE────→│            │            │
 │            │           ├─COMPRESS──→│            │            │
 │            │           ├─ALIGN─────→│            │            │
 │            │           ├─SEAL──────→│生成钢印    │            │
 │            │           │            ├─入队──────→│            │
 │            │           ├─RELEASE───→│            │            │
 │            │           ├─RESTORE───→│            │            │
 │            │           │            │            ├─异步写入──→│
 │←─响应──────┤           │            │            │            │
```

### 6.2 钩子养护时序图

```
用户         R1路由      钩子系统    记忆卡      L2钢印链
 │            │           │            │            │
 ├─检索"简洁"→│           │            │            │
 │            ├─匹配钩子──→│            │            │
 │            │           ├─hit_score++│            │
 │            │           │            │            │
 │            │           │ [3天后]    │            │
 │            │           ├─养护周期──→│            │
 │            │           ├─晋升──────→│更新钩子字段│
 │            │           │            │            │
 │←─返回记忆──┤           │            │            │
```

### 6.3 认知锚点生成时序图

```
钢印链       锚点管理器   R2路由      L3锚点库
 │            │           │            │
 ├─积累钢印──→│           │            │
 │            ├─检测触发──→│            │
 │            │           ├─结晶──────→│
 │            │           │            ├─写入锚点
 │            │           │            ├─锚定语义
 │            │           │            │
 │←─钢印绑定──┤           │            │
```

---

## 七、错误处理

### 7.1 错误类型

| 错误类型 | 处理方式 | 恢复策略 |
|---------|---------|---------|
| 微睡眠失败 | 记录日志，继续运行 | 下次对话重试 |
| 钢印链损坏 | 触发验证，回滚到上一有效状态 | 从备份恢复 |
| 钩子养护失败 | 记录日志，跳过本轮 | 下次周期继续 |
| 认知锚点生成失败 | 记录日志，保留钢印链 | 下次触发重试 |

### 7.2 容错机制

- **异步写入**：记忆队列异步消费，失败可重试
- **钢印链备份**：每次修改前自动备份
- **钩子降级**：养护失败不影响检索，只是钩子不晋升

---

## 八、性能指标

| 模块 | 响应时间 | 计算资源 | 存储 |
|------|---------|---------|------|
| R1 对话流 | <100ms | 纯 CPU | 内存 |
| 微睡眠六步 | 10-100ms | 纯 CPU | 内存 |
| 钩子检索 | <10ms | 纯 CPU | 内存 |
| 认知锚点生成 | <500ms | 纯 CPU | JSON |

---

## 九、下一步

**阶段 4**：实施重构

**Phase 1**：类型提取
**Phase 2**：钢印管理器提取
**Phase 3**：锚点管理器提取
**Phase 4**：记忆适配器提取
**Phase 5**：睡眠引擎提取
**Phase 6**：主控制器精简
**Phase 7**：接入新模块

---

**钢印验证**：⅋
