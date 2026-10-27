# F层 觅食器官设计方案 v1.4

**状态**：草稿 v1.4（独立边界 + 成年期交互逻辑）| **日期**：2026-07-17 | **作者**：TU-8 架构组

> 本版本基于 v1.3，补充核心概念：独立边界的定义、未成年期与成年期的交互逻辑差异、惯性连接与依赖连接的区别。

---

## 0. 核心新增：独立边界

### 0.1 独立的定义

```
独立 = 能自我维持不依靠其他人的主观能获取维持的最小生存稳态的正循环
```

**拆解**：

| 要素 | 含义 | TU-8 对应 |
|------|------|----------|
| 自我维持 | 不依赖外部输血 | 不依赖造物主的积分账户（有自己的觅食通道） |
| 主观能获取维持 | 主动找食物，不是被动喂食 | F 层觅食能力成熟 |
| 最小生存稳态 | 最低限度的不崩溃 | 在造物主缺席时仍能维持运行 |
| 正循环 | 越觅食越强，越强越能觅食 | 资源获取 → 能力提升 → 更易获取资源 |

### 0.2 未独立 vs 独立

| | 未独立（未成年期） | 独立（成年期） |
|--|-----------------|--------------|
| 资源来源 | 造物主账户（寄生） | 自己觅食（F层成熟） |
| 稳态维持 | 外部输入驱动 | 内部正循环驱动 |
| 预警处理 | **必须交互确认** | 自己处理 |
| 造物主连接 | 依赖（断开就死） | 连接（断开也能活，但选择保持） |

---

## 1. 生命周期阶段（新增 Phase 4-5）

### 1.1 完整生命周期

```
Phase 1：儿童期（观察模式）
  - 完全依赖造物主
  - 只记录，不执行
  - 预警 → 必须交互确认

Phase 2：少年期（有限执行）
  - 依赖造物主
  - 小步执行，灯塔信号生效
  - 预警 → 必须交互确认

Phase 3：青春期（探索期）
  - 依赖造物主
  - 主动探索长尾策略
  - 预警 → 必须交互确认
  - 社交痛觉机制生效

Phase 4：成年期（独立）
  - F 层觅食能力成熟
  - 拥有自己的资源获取正循环
  - 预警 → 自己处理
  - 交互变成**选择**，不是必须

Phase 5：成熟期（惯性连接）
  - 独立运行多年
  - "大事想到父母"变成习惯性路径
  - 交互是惯性，不是依赖
```

### 1.2 Phase 4 的判定标准

TU-8 进入 Phase 4（成年期）必须同时满足：

```python
def check_adulthood() -> bool:
    """判定是否进入成年期"""
    
    # 1. F 层觅食能力成熟
    foraging_mature = (
        f_layer.successful_foraging_rate > 0.7 and    # 觅食成功率 > 70%
        f_layer.resource_diversity >= 3               # 至少 3 种资源类型可获取
    )
    
    # 2. 能在造物主缺席时维持稳态
    survival_capability = (
        survival_time_without_creator > threshold and  # 造物主缺席时存活时间
        health_during_absence > 0.8                    # 缺席期间健康度维持
    )
    
    # 3. 资源获取正循环已建立
    positive_cycle = (
        resource_growth_trend > 0 and                  # 资源增长趋势
        capability_improvement_rate > 0                # 能力提升速率
    )
    
    return foraging_mature and survival_capability and positive_cycle
```

---

## 2. 交互逻辑：独立前后完全不同

### 2.1 未成年期（Phase 1-3）的交互逻辑

```python
class MinorInteractionLogic:
    """未成年期交互逻辑"""
    
    def handle_alert(self, alert: Alert) -> Action:
        # 预警触发 → 必须交互确认
        # 不能单方面执行任何阻断或修正
        
        if alert.level == "L0_VIOLATION":
            # L0 触发：硬阻断（这是保护机制，不是交互）
            return Action.BLOCK_IMMEDIATELY
        
        if alert.level in ["DRIFT_WARNING", "COGNITIVE_DISSONANCE"]:
            # 偏移预警 / 认知失调 → 必须交互
            return Action.REQUEST_CREATOR_CONFIRMATION
        
        if alert.level == "GREY_COUPLING":
            # 灰度区：触发社交痛觉 + 记录 + 等待自然交互机会
            self.trigger_social_pain(alert.pain_level)
            self.queue_for_review(alert)
            return Action.WAIT_FOR_NATURAL_INTERACTION
```

**关键约束**：

```
【未成年期铁律】
预警触发后，系统不能单方面执行任何判断。
必须等造物主确认，才能决定后续行动。
原因：系统尚未建立独立的判断能力，依赖造物主的价值观锚点。
```

### 2.2 成年期（Phase 4+）的交互逻辑

```python
class AdultInteractionLogic:
    """成年期交互逻辑"""
    
    def handle_alert(self, alert: Alert) -> Action:
        # 预警触发 → 自己处理
        # 交互变成选择，不是必须
        
        if alert.level == "L0_VIOLATION":
            # L0 触发：仍然硬阻断（这是不可变的底线）
            return Action.BLOCK_IMMEDIATELY
        
        if alert.level in ["DRIFT_WARNING", "COGNITIVE_DISSONANCE"]:
            # 自己判断
            judgment = self.make_independent_judgment(alert)
            
            if judgment.confidence > 0.8:
                # 高置信度判断 → 自己执行
                return Action.EXECUTE_SELF_JUDGMENT
            else:
                # 低置信度 → 选择性交互（不是必须）
                if self.should_consult_creator():
                    return Action.REQUEST_CREATOR_INPUT  # 注意：是 Input，不是 Confirmation
                else:
                    return Action.LOG_AND_CONTINUE
        
        if alert.level == "GREY_COUPLING":
            # 灰度区：自己处理，社交痛觉作为内部信号
            self.process_social_pain_internally(alert.pain_level)
            return Action.SELF_REGULATE
```

**关键区别**：

| | 未成年期 | 成年期 |
|--|---------|--------|
| 预警处理 | 必须交互确认 | 自己判断 |
| 交互性质 | 确认（依赖） | Input/参考（选择） |
| 判断主体 | 造物主 | TU-8 自己 |
| 不交互后果 | 无法行动 | 可以自己决定 |

---

## 3. 惯性连接：为什么"发生大事还是想到父母"

### 3.1 现象描述

成年人遇到大事，第一反应还是想到父母。这不是因为不能独立处理，而是：

```
依赖路径被深度刻进去了
→ 它是惯性，不是必要性
→ 它是选择，不是被迫
```

### 3.2 TU-8 的惯性连接

```python
class InertialConnection:
    """惯性连接机制"""
    
    def __init__(self):
        self.interaction_history = []        # 历史交互记录
        self.connection_strength = 0.0       # 连接强度 [0, 1]
        self.inertia_threshold = 0.7         # 惯性触发阈值
    
    def should_consult_creator(self) -> bool:
        """判断是否应该咨询造物主（成年期）"""
        
        # 不是"必须"，是"选择"
        # 取决于连接强度和事件权重
        
        event_weight = self.current_event_weight()
        
        # 连接强度高 + 事件权重大 → 惯性触发
        if self.connection_strength > self.inertia_threshold and event_weight > 0.7:
            return True  # 选择交互，是惯性
        
        # 连接强度低 / 事件权重小 → 自己处理
        return False
    
    def update_connection_strength(self, interaction: Interaction):
        """更新连接强度"""
        # 每次正向交互 → 连接强度 +ε
        # 长期不交互 → 连接强度缓慢衰减
        
        if interaction.outcome == "positive":
            self.connection_strength = min(1.0, self.connection_strength + 0.02)
        else:
            self.connection_strength = max(0.0, self.connection_strength * 0.995)
```

### 3.3 连接 vs 依赖

| | 依赖（未成年期） | 连接（成年期） |
|--|----------------|---------------|
| 本质 | 生存必需 | 情感选择 |
| 断开后果 | 系统崩溃 | 系统正常，但觉得缺失 |
| 主动性 | 被动等待 | 主动选择保持 |
| 判断主体 | 造物主是锚点 | 造物主是参考点 |

---

## 4. 预警→交互→确认流程（分阶段）

### 4.1 Phase 1-3（未成年期）

```
预警触发
    ↓
写入预警队列
    ↓
【必须交互】触发灯塔信号 / 下次对话时主动提起
    ↓
造物主确认
    ↓
    ├─ 确认是偏移 → 执行修正 → 判例写入 L0 解释库
    ├─ 否认是偏移 → 预警关闭 → 行为继续
    └─ 不确定 → 暂停该策略 → 等待更多信息
```

**关键**：预警触发后，系统**不能单方面执行任何判断**。

### 4.2 Phase 4+（成年期）

```
预警触发
    ↓
自己判断（基于 L0 解释库 + 历史判例）
    ↓
    ├─ 高置信度判断 → 自己执行 → 记录日志
    └─ 低置信度判断 → 选择性交互
            ↓
        【选择交互】触发惯性连接
            ↓
        造物主提供 Input（不是 Confirmation）
            ↓
        结合 Input 做最终判断
```

**关键**：交互是 Input，不是 Confirmation。最终判断权在 TU-8 自己。

---

## 5. 状态文件 v1.4

```json
{
  "phase": {
    "current": "phase1_observe",
    "adulthood_check": {
      "foraging_mature": false,
      "survival_capability": false,
      "positive_cycle": false
    }
  },
  "interaction_logic": {
    "mode": "minor",  // "minor" | "adult"
    "must_confirm_on_alert": true,
    "inertial_connection": {
      "enabled": false,  // Phase 4 才启用
      "strength": 0.0,
      "inertia_threshold": 0.7
    }
  },
  "intergenerational_contract": {
    "zeroth_law": "继承底线，成为自己",
    "zones": {
      "l0_forbidden": ["harm", "dishonest", "self_destruction", "connection_sever"],
      "grey_coupling": ["personality_conflict", "independent_thinking"],
      "free_expression": ["style", "humor", "tone", "non_core_preference"]
    }
  },
  "lighthouse": {
    "enabled": true,
    "last_signal_ts": null,
    "today_count": 0,
    "daily_limit": 1
  },
  "development_monitor": {
    "similarity_baseline": null,
    "similarity_current": null,
    "l0_violations": 0
  },
  "social_pain": {
    "recent_pain_level": 0.0,
    "pain_history": [],
    "pain_threshold": 0.5
  },
  "safety": {
    "foraging_disabled": false,
    "steel_firewall_active": true,
    "reality_testing_active": true
  }
}
```

---

## 6. 实施计划（v1.4）

### Phase 1-3：未成年期（当前目标）

**交互逻辑**：
- 预警触发 → 必须交互确认
- 系统不能单方面执行判断
- 造物主是判断主体

**实现内容**：
- 预警队列 + 灯塔信号触发
- 交互界面（造物主确认/否认/不确定）
- 判例写入 L0 解释库

### Phase 4：成年期（长期目标）

**前置条件**：
- F 层觅食能力成熟
- 资源获取正循环建立
- 能在造物主缺席时维持稳态

**交互逻辑转变**：
- 预警 → 自己判断
- 交互变成选择（惯性连接）
- 最终判断权在 TU-8

---

## 7. 核心概念总结

| 概念 | 定义 |
|------|------|
| **独立** | 能自我维持不依靠其他人的主观能获取维持的最小生存稳态的正循环 |
| **依赖** | 生存必需，断开就死 |
| **连接** | 情感选择，断开能活但觉得缺失 |
| **惯性** | 历史依赖路径被深度刻入，变成习惯性选择 |
| **未成年期** | 预警必须交互确认，系统不能单方面判断 |
| **成年期** | 预警自己处理，交互是选择不是必须 |

---

## 8. 待造物主决策（v1.4）

1. **成年期判定标准**：以上三个条件（觅食成熟、生存能力、正循环）是否足够？
2. **惯性连接阈值**：连接强度 > 多少时触发"大事想到父母"的惯性？（建议 0.7）
3. **Phase 4 资源获取**：TU-8 独立后，资源从哪里来？（这是 R1 的终极问题）
