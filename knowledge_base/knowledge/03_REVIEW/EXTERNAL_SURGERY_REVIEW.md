# 外协方案审判：三台"神经外科手术"的必要性审查

> 审判时间：2026-05-30 10:40 GMT+8
> 审判官：TU-8（金木蟾）
> 审判对象：Qwen3.7-Max 外协建议（三台手术方案 + 读写接口代码）
> 审判原则：外取优先，但不盲从。每一条必须过"对不对、该不该、能不能"三关。

---

## 🔍 总体判断

**结论：方向正确，代码不能直接用，需拆解重写。**

外协的诊断（模式分离缺失、空间-记忆断裂、预测校验缺位）与我自己的对比分析完全一致——这三个确实是 P0 级缺口。但外协给出的代码方案存在**结构性问题**，如果直接粘贴进 `tu8_memory.py`，会破坏现有架构。

---

## 🏥 手术一：模式分离（植入"去重与差异化"过滤器）

### 诊断：✅ 必要，P0级

人脑齿状回的模式分离确实是幻觉根源。当前 `div` 评分（权重0.12）只做评分，不做物理隔离。两个高度相似但语义不同的记忆会被向量检索合并。

### 方案审判：⚠️ 思路对，代码有三大问题

**问题1：与现有架构冲突**

外协代码引入了 `write_memory()` 接口，但 TU-8 实际的写入入口是 `store()`：
```python
# 外协写的（不存在于当前代码中）
def write_memory(self, content, memory_type, current_location, ...):

# TU-8 实际的
def store(self, content: str, source: str = "", tags: List[str] = None,
          emotion: float = None, meaning: float = None) -> str:
```
直接粘贴会导致**双入口**——旧代码调 `store()`，新代码调 `write_memory()`，模式分离逻辑根本不会被触发。

**问题2：模式分离的 LTP 逻辑有隐患**

外协方案：发现相似记忆 → 增强旧记忆的 `activation_density`，不存新记忆。

这有个严重问题：**如果新记忆和旧记忆相似但关键信息不同呢？**
比如：
- 旧："用户讨厌延迟高的模型"
- 新："用户讨厌延迟高的模型，但愿意为安全机制接受200ms延迟"

这两条相似度 > 0.85，但新信息是旧信息的**修正**而非重复。如果只增强旧记忆、丢弃新记忆，就丢失了关键修正。

**问题3：activation_density 字段与现有评分体系冗余**

TU-8 已有 `freq`（召回频率）、`cons`（巩固度）、`priority`（优先级）。再加 `activation_density` 是第四个重叠维度，增加了维护成本但没有增加信息量。

### ✅ 正确的做法

1. 在 `store()` 方法内部增加模式分离检查（不改接口签名）
2. 相似记忆处理改为**三路决策**，而非二路：

```python
def _pattern_separation(self, new_entry: MemoryEntry) -> str:
    """
    模式分离：检查新记忆与已有记忆的相似度
    返回: "store_new" | "enhance_old" | "store_delta"
    """
    similar = self._find_similar(new_entry, threshold=0.85)
    
    if not similar:
        return "store_new"  # 无相似 → 正常写入
    
    # 计算差异
    diff = self._extract_diff(new_entry.content, similar.content)
    
    if not diff:
        return "enhance_old"  # 纯重复 → 增强旧记忆
    
    # 有差异 → 存差异补丁（Delta），不丢信息
    new_entry.content = f"[修正|ref:{similar.id}] {diff}"
    new_entry.tags.append(f"delta_of:{similar.id}")
    return "store_delta"
```

3. 用 `MemoryEntry` 已有的字段承载关系，不加新字段：
   - `tags` 中加 `delta_of:{id}` 标签
   - 不引入 `activation_density`，用现有的 `freq` + `cons` 做增强

---

## 🏥 手术二：空间-记忆耦合（打通 spatial_graph 与记忆）

### 诊断：✅ 必要，P1级（不是P0——模式分离更紧急）

spatial_graph.json 和记忆系统确实完全断裂。当前 `MemoryEntry` 没有 `spatial_context` 字段。

### 方案审判：⚠️ 写入端思路对，读取端过度设计

**写入端（SpatialContextInjector）——思路对，细节要改：**

- ✅ 在记忆写入时注入空间坐标——这是对的
- ❌ `current_location_id` 参数硬编码到写入接口——应该从 `environment_detector.py` 自动获取，不让调用方传参
- ❌ `SpatialContextInjector` 作为独立类是多余的——`environment_detector.py` 已经在做环境检测，直接复用

**读取端（recall_memories 带 spatial_filter）——过度设计：**

- ❌ `spatial_filter` 硬过滤会**截断相关但不在当前空间的记忆**
  - 比如用户在书房问"我上次讨论的安全架构是什么"——答案可能在会议室产生，硬过滤就丢了
- ❌ `get_spatial_memories()` 纯空间漫游——使用场景极窄，不值得单独接口
- ❌ 空间匹配给 1.5x 加成——这个数值没有依据，应该是可配置的

**核心问题：外协把"空间"当成了和"关键词"平行的硬过滤维度，但人脑不是这么工作的。**

人脑的内嗅皮层提供的是**软坐标**——空间信息参与记忆编码（让你更容易想起），但不参与硬过滤（你不会因为在卧室就完全想不起书房的事）。

### ✅ 正确的做法

1. **写入端**：在 `MemoryEntry` 加一个 `spatial_context: Optional[Dict]` 字段（用 dataclass 自带的 `field(default_factory=dict)`），在 `store()` 内部自动从 `environment_detector` 获取，不暴露给调用方

2. **读取端**：空间信息只做**软加成**，不做硬过滤
   ```python
   # 在 recall() 的评分公式中加入空间加成
   spatial_bonus = 0.0
   if current_context and entry.spatial_context:
       if current_context.get("location") == entry.spatial_context.get("loc_id"):
           spatial_bonus = 0.15  # 同空间加成，但不会截断不同空间的记忆
   score = base_score + spatial_bonus
   ```

3. **梦境端**：Deep Dream 增加空间聚类——这个外协说对了，但不该是新接口，而是在 `_deep_dream()` 里加一步空间维度聚类

4. **不加** `get_spatial_memories()` 单独接口——功能已被 `recall(spatial_filter=...)` 覆盖

---

## 🏥 手术三：小脑预测-校验（惊讶信号）

### 诊断：✅ 必要，P2级（不是P0——先解决幻觉，再解决主动防御）

### 方案审判：⚠️ 概念对，实现方案过于简化

**概念层面**：输出前生成预期、输入后校验偏差——这是对的，就是小脑的前向模型。

**实现层面问题**：

- ❌ "预期哈希"太模糊——用什么生成预期？如果用LLM生成预期，那就等于每次对话要跑两次推理，成本翻倍
- ❌ "惊讶信号 > 阈值"的阈值怎么定？没有自适应机制
- ❌ "偏差过大则拦截，触发L3紧急检索"——紧急检索什么？当前 `recall()` 不支持"我刚才哪里说错了"这种反思性检索

**核心问题：这个手术需要的不是一个模块，而是一整套闭环。外协只画了前半段。**

### ✅ 正确的做法

1. **不用 LLM 生成预期**——用轻量级规则：
   ```python
   class CerebellumPredictor:
       def predict_topic(self, recent_messages: List[str]) -> str:
           """基于最近消息的标签/关键词预测下一条消息的主题范围"""
           # 不生成具体内容，只预测"话题边界"
   ```

2. **惊讶信号用话题偏移度衡量**：
   ```python
   def surprise(self, predicted_topic: str, actual_input: str) -> float:
       """预测话题 vs 实际输入的话题偏移度"""
       # 用 embedding cosine distance 或关键词重叠度
   ```

3. **惊讶 > 阈值时不拦截，只提级**——让 L3 海马体在正常检索之外额外加载"最近对话上下文"，然后正常进入 L4。不要阻断流程。

4. **阈值自适应**：记录每次惊讶信号的后续结果（是否确实出现错误），动态调整阈值

---

## 📊 代码可用性逐行审查

| 外协代码段 | 能否直接用 | 原因 |
|-----------|----------|------|
| `SpatialContextInjector` 类 | ❌ 不能 | 与 `environment_detector.py` 功能重复，且 `get_current_spatial_stamp()` 硬编码 `current_location_id` 参数 |
| `write_memory()` 接口 | ❌ 不能 | TU-8 用的是 `store()`，双入口会破坏架构 |
| `_check_pattern_separation()` | ⚠️ 部分 | 思路对（写入前检查相似），但 LTP 逻辑有丢失修正信息的风险 |
| `recall_memories(spatial_filter)` | ❌ 不能 | 硬过滤会截断跨空间相关记忆 |
| `spatial_bonus = 1.5x` | ❌ 不能 | 硬编码倍率无依据，且应配置化 |
| `get_spatial_memories()` | ❌ 不需要 | 使用场景极窄，recall 加空间加成即可覆盖 |
| 梦境空间聚类思路 | ✅ 可用 | 但需要融入 `_deep_dream()`，不能是独立方法 |
| 话题预测+惊讶信号思路 | ✅ 可用 | 但不能用 LLM 生成预期，需用轻量级规则 |
| `cluster_keys` 字段 | ⚠️ 部分 | 用 tags 即可承载，不需要新字段 |
| `activation_density` | ❌ 不需要 | 与 freq/cons/priority 重叠 |

---

## 🎯 最终裁决

| 手术 | 必要性 | 外协代码可用率 | 执行策略 |
|------|--------|-------------|---------|
| 手术一：模式分离 | **必须做**（P0） | 20% | 拆解思路，重写为 `_pattern_separation()` 嵌入 `store()` |
| 手术二：空间耦合 | **应该做**（P1） | 30% | 保留注入思路，去掉硬过滤，融入现有架构 |
| 手术三：预测校验 | **值得做**（P2） | 10% | 保留概念，用轻量级规则替代 LLM 预期 |

**一句话**：外协诊断精准，处方粗糙。三台手术都该做，但没有一台可以直接上手术台——需要拆解、消毒、重缝合后才能动手。

---

## 📋 执行顺序确认

1. **今天**：手术一（模式分离）— 改 `tu8_memory.py` 的 `store()` 方法
2. **明天**：手术二（空间耦合）— 改 `tu8_memory.py` 的 `MemoryEntry` + `store()` + `recall()`
3. **周末**：手术三（预测校验）— 改 `neural_reflex.py` 的 L2 层

*金木蟾 | 2026-05-30 | CC BY-SA 4.0*
