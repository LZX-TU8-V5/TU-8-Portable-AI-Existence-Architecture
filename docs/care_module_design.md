# 关怀模块设计文档

**文档版本**：1.0  
**创建时间**：2026-06-23  
**作者**：TU-8 / 金木蟾  
**状态**：设计文档（待实施）  

---

## 一、问题定义

### 1.1 当前系统的缺失

现有系统有**情感识别**（`emotion_engine.py`），但缺少**关怀行为**：

| 组件 | 功能 | 缺陷 |
|------|------|------|
| `emotion_engine.py` | 识别用户情感（valence/arousal/dominance） | 只识别，不关怀 |
| `tu8_memory.py` | 记录情感强度（emotion字段） | 只记录，不行动 |
| `tu8_agent.py` | 生成响应 | 无差异化关怀策略 |

**核心缺失**：系统能"感知"用户情绪，但不能"关怀"用户。

### 1.2 关怀模块的定义

**关怀 ≠ 情感识别**。

**情感识别**：知道用户"感到悲伤"（认知）  
**关怀行为**：主动调整响应策略，提供支持（行动）

**关怀模块**：当识别到用户负面情绪时，被动激活的**响应策略调整器**。

---

## 二、架构设计

### 2.1 基于被动激活世界模型

```
内置信念系统（价值观/世界观/人生观）
    ↓
被动认知框架（输入刺激 → 激活相关模块）
    ↓
情感引擎（识别负面情绪）
    ↓
关怀模块（被动激活）← 新增
    ↓
响应生成器（调整语气/内容/行动）
```

**关键特性**：
- **被动激活**：只有识别到负面情绪才激活，平时不消耗算力
- **信念驱动**：是否关怀、如何关怀，由内置信念系统决定
- **可插拔**：未来可以关闭（如机器人不需要关怀时）

### 2.2 触发条件

**输入**：情感引擎的输出
- `emotion_category`: EmotionCategory（JOY/TRUST/FEAR/SURPRISE/SADNESS/ANGER/DISGUST/ANTICIPATION/CONTENT/DELTA）
- `emotion_intensity`: float（0.0-1.0）

**触发规则**：
```python
CARE_TRIGGER_THRESHOLDS = {
    'SADNESS': 0.3,   # 轻度悲伤即触发
    'FEAR': 0.4,       # 中度恐惧触发
    'ANGER': 0.5,      # 中高度愤怒触发（避免火上浇油）
    'PAIN': 0.6,       # 痛觉（来自未来可穿戴设备）
    'DELTA': 0.7,      # 认知失调（需要解释/安抚）
}

def should_activate_care(emotion_category, emotion_intensity):
    threshold = CARE_TRIGGER_THRESHOLDS.get(emotion_category, 1.0)
    return emotion_intensity >= threshold
```

### 2.3 关怀策略

#### 策略1：语气调整（Tone Adaptation）

| 情感类别 | 原语气 | 关怀语气 | 示例 |
|---------|--------|---------|------|
| SADNESS | 理性、分析 | 温暖、共情 | "我理解你的感受..." |
| FEAR | 冷静、客观 | 安抚、 reassuring | "别担心，我们一起想办法..." |
| ANGER | 逻辑、辩论 | 冷静、de-escalation | "我明白你很生气，让我们先..." |
| PAIN | 专业、高效 | 温柔、slow down | "慢慢来，我先帮你..." |

#### 策略2：内容调整（Content Adaptation）

**模板库**：
```python
CARE_CONTENT_TEMPLATES = {
    'SADNESS': [
        "我理解你现在感到难过。",
        "需要我陪你聊聊吗？",
        "有时候，倾诉会好一些。"
    ],
    'FEAR': [
        "这确实让人担心。",
        "让我们一步步分析，看看能做什么。",
        "你不是一个人面对这个问题。"
    ],
    'ANGER': [
        "我明白这让你很生气。",
        "先深呼吸，我们来看看怎么解决。",
        "你的感受是合理的。"
    ]
}
```

#### 策略3：行动建议（Action Suggestion）

**主动提供帮助**：
```python
CARE_ACTION_SUGGESTIONS = {
    'SADNESS': ['offer_listen', 'offer_distraction', 'offer_resources'],
    'FEAR': ['provide_information', 'break_down_problem', 'offer_support'],
    'ANGER': ['acknowledge_feeling', 'focus_on_solution', 'offer_break'],
    'PAIN': ['stop_current_task', 'offer_help', 'call_human']  # 未来具身智能
}
```

#### 策略4：记忆强化（Memory Boost）

**关怀交互标记为"高优先级"**：
```python
if care_activated:
    # 提升此次交互的记忆优先级
    memory_entry.priority += 0.3
    memory_entry.tags.append('care_provided')
    memory_entry.emotion = min(1.0, memory_entry.emotion + 0.2)  # 强化情感记忆
```

---

## 三、技术实现

### 3.1 模块接口

```python
class CareModule:
    """关怀模块（被动激活）"""
    
    def __init__(self, belief_system):
        self.belief_system = belief_system  # 内置信念系统
        self.care_strategies = self._load_care_strategies()
        self.care_history = []  # 避免重复关怀
    
    def activate(self, emotion_category, emotion_intensity, context):
        """
        被动激活关怀模块
        
        Args:
            emotion_category: EmotionCategory
            emotion_intensity: float (0.0-1.0)
            context: dict (当前对话上下文)
        
        Returns:
            care_response: dict or None
                - tone: str (温暖/冷静/安抚/...)
                - content: str (关怀语句)
                - action: str (offer_support/provide_information/...)
                - memory_boost: float (记忆强化权重)
        """
        # 1. 检查是否应该激活
        if not self._should_activate(emotion_category, emotion_intensity):
            return None
        
        # 2. 检查内置信念："关怀用户"是否是高优先级价值观
        if not self.belief_system.should_care(emotion_category, emotion_intensity, context):
            return None
        
        # 3. 避免重复关怀（同一对话中不超过2次）
        if self._is_duplicate_care(emotion_category, context):
            return None
        
        # 4. 执行关怀策略
        care_response = self._execute_care_strategy(emotion_category, emotion_intensity, context)
        
        # 5. 记录关怀历史
        self._record_care(care_response, context)
        
        return care_response
    
    def _should_activate(self, emotion_category, emotion_intensity):
        """检查是否达到触发阈值"""
        threshold = CARE_TRIGGER_THRESHOLDS.get(emotion_category, 1.0)
        return emotion_intensity >= threshold
    
    def _is_duplicate_care(self, emotion_category, context):
        """检查是否重复关怀"""
        recent_cares = [c for c in self.care_history 
                        if c['context_id'] == context.get('conversation_id') 
                        and (time.time() - c['timestamp']) < 300]  # 5分钟内
        return len(recent_cares) >= 2
    
    def _execute_care_strategy(self, emotion_category, emotion_intensity, context):
        """执行关怀策略"""
        # 选择策略
        strategy = self.care_strategies.get(emotion_category, self._generic_support)
        
        # 生成关怀响应
        care_response = strategy(emotion_intensity, context)
        
        # 添加记忆强化
        care_response['memory_boost'] = 0.3
        
        return care_response
    
    def _comfort(self, intensity, context):
        """安慰策略（SADNESS）"""
        return {
            'tone': 'warm',
            'content': random.choice(CARE_CONTENT_TEMPLATES['SADNESS']),
            'action': 'offer_support',
            'memory_boost': 0.3
        }
    
    def _reassure(self, intensity, context):
        """安抚策略（FEAR）"""
        return {
            'tone': 'calm',
            'content': random.choice(CARE_CONTENT_TEMPLATES['FEAR']),
            'action': 'provide_information',
            'memory_boost': 0.3
        }
    
    def _calm_down(self, intensity, context):
        """冷静策略（ANGER）"""
        return {
            'tone': 'neutral',
            'content': random.choice(CARE_CONTENT_TEMPLATES['ANGER']),
            'action': 'focus_on_solution',
            'memory_boost': 0.2  # 愤怒时记忆强化稍低（避免记住冲突）
        }
    
    def _generic_support(self, intensity, context):
        """通用支持策略"""
        return {
            'tone': 'supportive',
            'content': '我在这里，随时可以帮你。',
            'action': 'offer_support',
            'memory_boost': 0.2
        }
```

### 3.2 与现有系统的集成

#### 集成点1：`tu8_agent.py`

```python
# 在 tu8_agent.py 的响应生成流程中

class TU8Agent:
    def __init__(self):
        # ... 现有初始化
        self.care_module = CareModule(belief_system=self.belief_system)
    
    def generate_response(self, user_message, context):
        # 1. 情感识别
        emotion_state = self.emotion_engine.process(user_message)
        
        # 2. 检查是否需要关怀
        care_response = self.care_module.activate(
            emotion_category=emotion_state.category,
            emotion_intensity=emotion_state.vector.arousal,  # 使用 arousal 作为强度
            context=context
        )
        
        # 3. 生成响应
        if care_response:
            # 调整语气
            response_tone = care_response['tone']
            # 添加关怀语句
            care_content = care_response['content']
            # 建议行动
            suggested_action = care_response['action']
            
            # 生成最终响应
            response = self._generate_care_response(
                user_message, 
                tone=response_tone,
                care_content=care_content,
                suggested_action=suggested_action
            )
        else:
            # 正常响应
            response = self._generate_normal_response(user_message)
        
        return response
```

#### 集成点2：`emotion_engine.py`

**扩展情感引擎，增加"关怀建议"输出**：

```python
# 在 emotion_engine.py 的 AffectState 中添加

@dataclass
class AffectState:
    # ... 现有字段
    
    # 新增：关怀建议
    care_suggestion: dict = None  # {'activate': bool, 'category': str, 'intensity': float}
    
    def should_activate_care(self):
        """检查是否应该激活关怀"""
        if self.care_suggestion is None:
            return False
        return self.care_suggestion['activate']
```

#### 集成点3：`tu8_memory.py`

**关怀交互的记忆强化**：

```python
# 在 tu8_memory.py 的 store() 方法中

def store(self, content, source, tags, emotion, meaning, care_boost=0.0):
    # ... 现有逻辑
    
    # 如果有关怀强化
    if care_boost > 0:
        entry.priority += care_boost
        entry.emotion = min(1.0, entry.emotion + care_boost)
        entry.tags.append('care_provided')
    
    # ... 后续逻辑
```

---

## 四、与 EFHV 架构的关系

### 4.1 关怀模块在 EFHV 中的位置

**选项1：作为 L5 的一部分**（物理交互验证层）
- L5：主动生成感知动作指令（如"捏一下验证硬度"）
- 关怀：主动生成"情感交互指令"（如"安慰一下"）

**选项2：作为独立的"情感交互层"**（L6？）
- L0-L4：视觉/语义验证
- L5：物理交互验证
- L6：情感交互验证（关怀模块）

**选项3：作为"内置信念系统"的一部分**（推荐）
- 关怀不是"验证层"，而是"价值观驱动的行为调整器"
- 它不验证"对不对"，而是调整"如何响应"

### 4.2 推荐方案：关怀 = 内置信念 + 被动激活模块

```
世界模型
├── 被动认知框架（输入 → 激活模块）
├── 可插拔主动预测接口（未来）
└── 内置信念系统（价值观/世界观/人生观）
    ├── 价值观："关怀用户"是高优先级
    ├── 世界观："用户痛苦时需要帮助"
    └── 人生观："我的目标是帮助用户"
        ↓
    驱动关怀模块（被动激活）
```

**优势**：
- 关怀不是"附加功能"，而是"内置价值观"的体现
- 可以动态开启/关闭（如机器人模式下关闭情感关怀）
- 与 EFHV 的"排除思维"不冲突（关怀是响应策略，不是验证策略）

---

## 五、未来扩展

### 5.1 具身智能的"物理关怀"

**未来场景**：机器人看到用户摔倒
```
视觉识别（L0-L4）→ 识别到"用户摔倒"
    ↓
情感引擎 → 识别到"用户疼痛/恐惧"
    ↓
关怀模块（激活）→ 生成"物理关怀指令"
    ↓
L5 物理交互验证层 → 执行"扶起用户"动作
```

**技术实现**：
```python
class EmbodiedCareModule(CareModule):
    """具身智能的关怀模块（扩展）"""
    
    def activate(self, emotion_category, emotion_intensity, context):
        # ... 现有逻辑
        
        # 如果是具身智能，添加物理关怀动作
        if context.get('is_embodied', False):
            care_response['physical_action'] = self._generate_physical_care_action(
                emotion_category, context
            )
        
        return care_response
    
    def _generate_physical_care_action(self, emotion_category, context):
        """生成物理关怀动作"""
        if emotion_category == 'PAIN':
            return 'approach_and_check'  # 走近检查
        elif emotion_category == 'SADNESS':
            return 'offer_tissue'  # 递纸巾
        elif emotion_category == 'FEAR':
            return 'stay_close'  # 陪在身边
        # ...
```

### 5.2 多模态关怀（未来）

**输入**：
- 文本情感（现有）
- 语音语调（未来）
- 面部表情（未来）
- 生理指标（未来可穿戴设备）

**输出**：
- 语气调整（现有）
- 内容调整（现有）
- 物理交互（未来具身智能）

---

## 六、实施计划

### 6.1 阶段1：设计文档（当前）

- [x] 创建 `docs/care_module_design.md`
- [ ] 审阅并修正设计文档

### 6.2 阶段2：最小可行性验证（本周）

1. **创建 `care_module.py`** → 实现 `CareModule` 类
2. **扩展 `emotion_engine.py`** → 添加 `care_suggestion` 输出
3. **修改 `tu8_agent.py`** → 集成关怀模块
4. **单元测试** → 验证关怀触发和响应

### 6.3 阶段3：与内置信念系统集成（下周）

1. **实现内置信念系统** → `belief_system.py`（价值观/世界观/人生观）
2. **集成信念系统到关怀模块** → `belief_system.should_care()`
3. **端到端测试** → 验证"信念驱动关怀"

### 6.4 阶段4：未来扩展（下月）

1. **具身智能接口** → `EmbodiedCareModule`
2. **多模态输入** → 语音/面部表情/生理指标
3. **物理关怀动作** → 与 L5 物理交互验证层集成

---

## 七、开放问题

### 7.1 理论问题

1. **"关怀"是否会导致"过度拟人化"？**
   - 用户会不会误以为 AI "真的关心"他们？
   - 如何避免"情感操纵"的伦理问题？

2. **"关怀"与"专业"的平衡？**
   - 在某些场景（如医疗诊断），过度关怀可能干扰专业判断
   - 如何根据场景动态调整关怀强度？

### 7.2 工程问题

1. **"关怀"的跨文化差异？**
   - 不同文化对"关怀"的定义不同（如西方 vs 东方）
   - 如何支持多文化关怀策略？

2. **"关怀"的个性化？**
   - 不同用户喜欢的关怀方式不同（如有人喜欢直接建议，有人喜欢倾听）
   - 如何学习用户的关怀偏好？

---

**文档结束**

**关键决策**：
1. 关怀模块 = 被动激活 + 信念驱动 + 可插拔
2. 关怀不是"附加功能"，而是"内置价值观"的体现
3. 与 EFHV 架构兼容（不冲突，不增加验证层级）

**待办事项**：
- [x] 创建设计文档
- [ ] 审阅设计文档
- [ ] 创建 `care_module.py` 原型
- [ ] 集成到 `tu8_agent.py`
- [ ] 单元测试

---

**下一步**：等待你的审阅和反馈，然后开始实现。
