# consciousness_cycle.py 现状分析报告

**日期**：2026-06-27 02:05 GMT+8
**文件**：src/consciousness_cycle.py
**行数**：2762 行

---

## 一、文件结构

### 类定义（8个）

| 行号 | 类名 | 功能 |
|------|------|------|
| 131 | NoteType | 外化笔记类型枚举 |
| 145 | StateVector | 自我状态向量 |
| 191 | MicroSleepPayload | 微睡眠负载数据结构 |
| 227 | Seal | 钢印类 |
| 321 | Note | 外化笔记 |
| 354 | NoteCandidate | 笔记候选 |
| 367 | CycleConfig | 配置类 |
| 453 | ConsciousnessCycle | **主类（意识循环引擎）** |

### 导入依赖（17个模块）

#### 标准库（12个）
```python
json, hashlib, logging, os, time, uuid
asyncio, threading, queue
enum, dataclasses, typing, pathlib, datetime
```

#### 外部模块（5个认知组件）
```python
cognitive_evaluator      # 认知负荷评估
cognitive_time_engine    # 认知时间引擎
cognitive_manifold_aligner  # 流形对齐
cognitive_integration    # 认知中间件
decision_pruner          # 决策剪枝
credit_assigner          # 信用分配
llm_gateway              # 大模型网关
micro_sleep              # 微睡眠引擎
```

---

## 二、ConsciousnessCycle 主类分析

### 方法统计

**总方法数**：~60 个

**分类**：

| 类别 | 方法数 | 代表方法 |
|------|--------|---------|
| **生命周期** | 3 | `__init__`, `tick`, `status` |
| **相位转换** | 6 | `_should_enter_sleep`, `_should_wake_up`, `_enter_light_sleep`, `_enter_deep_sleep` |
| **微睡眠六步** | 6 | `_step_freeze`, `_step_compress`, `_step_align`, `_step_seal`, `_step_release`, `_step_restore` |
| **深睡眠三操作** | 3 | `_deep_seal_consolidation`, `_deep_cross_chain_align`, `_deep_memory_reorganize` |
| **冬眠/恢复** | 2 | `enter_hibernation`, `recover_from_hibernation` |
| **记忆队列** | 5 | `_enqueue_seal`, `_write_seal_to_memory`, `_start_memory_consumer`, `_stop_memory_consumer` |
| **外化笔记** | 3 | `_should_externalize_note`, `_enqueue_note_candidate`, `externalize_note` |
| **验证/检查** | 8 | `_verify_seal_chain`, `_check_tail_continuity`, `_check_skepticism`, `_check_semantic_continuity` |
| **持久化** | 6 | `_load_seal_chain`, `_persist_seal_chain`, `_persist_notes`, `_sync_to_workspace_c` |
| **辅助工具** | ~18 | `_extract_fragments`, `_lossy_compress`, `_evaporate`, `_infer_scene_tag` 等 |

---

## 三、核心流程

### 3.1 主循环（tick）

```python
def tick(self, context_snapshot, force_sleep):
    """主循环 - 每次对话调用一次"""

    # 1. 检查是否进入睡眠
    if _should_enter_sleep():
        # 2. 进入浅睡（微睡眠）
        result = _enter_light_sleep()

        # 3. 检查是否进入深睡
        if _should_enter_deep_sleep():
            result = _enter_deep_sleep()

    # 4. 检查是否外化笔记
    if _should_externalize_note():
        externalize_note()

    # 5. 返回状态
    return status()
```

### 3.2 微睡眠六步流水线

```python
def _enter_light_sleep(self, context_snapshot):
    """浅睡 - 微睡眠六步"""

    # 1. FREEZE - 冻结上下文
    _step_freeze(context_snapshot)

    # 2. COMPRESS - 有损压缩
    compression = _step_compress()

    # 3. ALIGN - 钢印对齐
    coherence = _step_align(compression)

    # 4. SEAL - 生成钢印
    seal = _step_seal(compression, coherence)

    # 5. RELEASE - 释放到队列
    _step_release(context_snapshot)

    # 6. RESTORE - 恢复状态
    _step_restore()

    return result
```

### 3.3 深睡眠三操作

```python
def _enter_deep_sleep(self):
    """深睡 - 记忆整合"""

    # 1. 钢印链整合
    _deep_seal_consolidation()

    # 2. 跨钢印链对齐
    _deep_cross_chain_align()

    # 3. 记忆重排
    _deep_memory_reorganize()

    return result
```

---

## 四、耦合点分析

### 4.1 强耦合模块

| 模块 | 耦合方式 | 行数 |
|------|---------|------|
| `micro_sleep` | 直接导入，已解耦 | ✅ |
| `cognitive_*` | 5个认知组件，紧密耦合 | ⚠️ |
| `decision_pruner` | 决策剪枝，中等耦合 | ⚠️ |
| `credit_assigner` | 信用分配，中等耦合 | ⚠️ |
| `llm_gateway` | LLM 网关，松耦合 | ✅ |

### 4.2 数据流耦合

```
用户输入
    ↓
tick() 接收 context_snapshot
    ↓
_enter_light_sleep() 处理
    ↓
生成 Seal（钢印）
    ↓
_enqueue_seal() 写入队列
    ↓
_write_seal_to_memory() 异步持久化
    ↓
memory/tu8_memory.py（外部存储）
```

### 4.3 状态依赖

**钢印链**：
- 存储在 `self.seal_chain: List[Seal]`
- 持久化到 `memory/time_chain/seal_index.json`
- 依赖外部 `tu8_memory.py` 写入

**记忆队列**：
- `self.memory_queue: queue.Queue`
- 后台线程消费
- 写入到 `tu8_memory.py`

---

## 五、问题清单

### 5.1 架构问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **职责过重** | 🔴 P0 | ConsciousnessCycle 类承担太多职责（睡眠/记忆/笔记/验证） |
| **认知组件耦合** | 🟡 P1 | 5个认知组件紧密耦合，难以替换 |
| **记忆系统未集成** | 🔴 P0 | 新的记忆系统（钩子/工作记忆）未接入 |

### 5.2 技术问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **文件过大** | 🟡 P1 | 2762行，难以维护 |
| **方法过多** | 🟡 P1 | ~60个方法，难以理解 |
| **测试覆盖不足** | 🟡 P1 | 缺少完整的单元测试 |

### 5.3 功能问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **钩子系统缺失** | 🔴 P0 | 无钩子检索/养护机制 |
| **工作记忆缺失** | 🔴 P0 | 无 C1/C2/C3 工作记忆区 |
| **三路由缺失** | 🔴 P0 | 无 R1/R2/R3 路由协作 |

---

## 六、重构建议

### 6.1 解耦边界

**建议拆分为 5 个子模块**：

```
consciousness_cycle.py (主控制器，~500行)
    ├─ sleep_engine.py (睡眠引擎，~600行)
    ├─ seal_manager.py (钢印管理，~400行)
    ├─ note_manager.py (笔记管理，~300行)
    └─ memory_adapter.py (记忆适配器，~200行)
```

### 6.2 接入新模块

**接入顺序**：

1. **Phase 1**：引入 EventBus（解耦内部通信）
2. **Phase 2**：接入 HookMaintenance（钩子养护）
3. **Phase 3**：接入 WorkingMemory（工作记忆）
4. **Phase 4**：接入 RouterDialogue（对话流路由）

### 6.3 测试策略

**分层测试**：

1. **单元测试**：每个子模块独立测试
2. **集成测试**：主控制器 + 子模块
3. **端到端测试**：完整对话流程

---

## 七、风险评估

### 高风险区域

| 区域 | 风险 | 缓解措施 |
|------|------|---------|
| `tick()` 主循环 | 修改影响全局 | 完整测试套件 |
| 记忆队列 | 异步写入失败 | 事务日志 |
| 钢印链 | 损坏不可恢复 | 备份机制 |

### 低风险区域

| 区域 | 风险 | 说明 |
|------|------|------|
| 辅助函数 | 低 | 纯函数，易测试 |
| 配置类 | 低 | 独立，无副作用 |

---

## 八、下一步

**阶段 2**：制定重构计划

**任务**：
1. 确定解耦边界
2. 设计模块接口
3. 制定重构步骤
4. 评估工作量

---

**钢印验证**：⅋
