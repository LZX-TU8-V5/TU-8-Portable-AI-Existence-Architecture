# consciousness_cycle.py 重构计划（详细版）

**日期**：2026-06-27 02:07 GMT+8
**阶段**：阶段 2 - 制定计划
**输入**：现状分析报告

---

## 一、重构目标

### 核心目标
1. **解耦**：将 2762 行拆分为多个独立模块
2. **接入**：集成新的记忆系统（钩子/工作记忆/三路由）
3. **可测试**：每个模块可独立测试
4. **可回滚**：保留原文件，可随时回退

### 非目标
- ❌ 重写所有代码
- ❌ 改变核心逻辑
- ❌ 优化性能（后续再说）

---

## 二、解耦边界设计

### 2.1 模块拆分方案

**原文件**：consciousness_cycle.py（2762行）

**拆分为 6 个模块**：

| 模块 | 行数 | 职责 | 原有代码 |
|------|------|------|---------|
| `consciousness_cycle.py` | ~400 | 主控制器 + 状态机 | ConsciousnessCycle 核心逻辑 |
| `sleep_engine.py` | ~600 | 睡眠引擎（浅睡/深睡/冬眠） | _enter_light_sleep, _enter_deep_sleep, enter_hibernation |
| `seal_manager.py` | ~400 | 钢印管理（生成/验证/持久化） | Seal 类 + 钢印相关方法 |
| `note_manager.py` | ~300 | 笔记管理（外化/候选/持久化） | Note 类 + 笔记相关方法 |
| `memory_adapter.py` | ~200 | 记忆适配器（队列/写入） | 记忆队列 + _write_seal_to_memory |
| `cycle_types.py` | ~300 | 类型定义（枚举/数据类） | NoteType, StateVector, MicroSleepPayload, NoteCandidate |

**总计**：~2200 行（减少 500+ 行冗余）

### 2.2 接口设计

#### sleep_engine.py

```python
class SleepEngine:
    """睡眠引擎"""

    def __init__(self, config, seal_manager, memory_adapter):
        self.config = config
        self.seal_manager = seal_manager
        self.memory_adapter = memory_adapter

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

#### seal_manager.py

```python
class SealManager:
    """钢印管理器"""

    def __init__(self, config):
        self.config = config
        self.seal_chain: List[Seal] = []

    def generate_seal(self, content: str, coherence: float) -> Seal:
        """生成钢印"""
        pass

    def verify_chain(self) -> bool:
        """验证钢印链完整性"""
        pass

    def persist(self):
        """持久化钢印链"""
        pass

    def load(self):
        """加载钢印链"""
        pass
```

#### note_manager.py

```python
class NoteManager:
    """笔记管理器"""

    def __init__(self, config):
        self.config = config
        self.note_candidates: List[NoteCandidate] = []

    def should_externalize(self) -> Optional[Dict]:
        """判断是否外化笔记"""
        pass

    def externalize(self, content: str, note_type: NoteType) -> Note:
        """外化笔记"""
        pass

    def persist(self):
        """持久化笔记"""
        pass
```

#### memory_adapter.py

```python
class MemoryAdapter:
    """记忆适配器 - 连接 tu8_memory.py"""

    def __init__(self, config):
        self.config = config
        self.memory_queue = queue.Queue()
        self._start_consumer()

    def enqueue_seal(self, seal: Seal, metadata: Dict):
        """钢印入队"""
        pass

    def write_to_memory(self, task: Dict):
        """写入记忆（异步）"""
        pass

    def get_status(self) -> Dict:
        """获取队列状态"""
        pass
```

---

## 三、重构步骤

### Phase 1：类型提取（低风险）

**任务**：
1. 创建 `cycle_types.py`
2. 提取枚举类：NoteType, Phase
3. 提取数据类：StateVector, MicroSleepPayload, Note, NoteCandidate
4. 更新 `consciousness_cycle.py` 导入

**验证**：
- 运行现有测试（如有）
- 导入测试：确保类型可正常导入

**时间**：30 分钟

---

### Phase 2：钢印管理器提取（中风险）

**任务**：
1. 创建 `seal_manager.py`
2. 移动 Seal 类
3. 移动钢印相关方法：
   - `_generate_seal_id()`
   - `compute_seal_hash()`
   - `_verify_seal_chain()`
   - `_load_seal_chain()`
   - `_persist_seal_chain()`
4. 在 ConsciousnessCycle 中创建 SealManager 实例
5. 更新方法调用

**验证**：
- 钢印生成测试
- 钢印链验证测试
- 持久化测试

**时间**：1 小时

---

### Phase 3：笔记管理器提取（中风险）

**任务**：
1. 创建 `note_manager.py`
2. 移动 Note 类
3. 移动笔记相关方法：
   - `_should_externalize_note()`
   - `_enqueue_note_candidate()`
   - `externalize_note()`
   - `_persist_notes()`
4. 在 ConsciousnessCycle 中创建 NoteManager 实例
5. 更新方法调用

**验证**：
- 笔记生成测试
- 笔记持久化测试

**时间**：1 小时

---

### Phase 4：记忆适配器提取（中风险）

**任务**：
1. 创建 `memory_adapter.py`
2. 移动记忆队列相关方法：
   - `_enqueue_seal()`
   - `_write_seal_to_memory()`
   - `_start_memory_consumer()`
   - `_stop_memory_consumer()`
   - `get_memory_queue_status()`
3. 在 ConsciousnessCycle 中创建 MemoryAdapter 实例
4. 更新方法调用

**验证**：
- 队列写入测试
- 异步消费测试
- 与 tu8_memory.py 集成测试

**时间**：1 小时

---

### Phase 5：睡眠引擎提取（高风险）

**任务**：
1. 创建 `sleep_engine.py`
2. 移动睡眠相关方法：
   - `_should_enter_sleep()`
   - `_should_wake_up()`
   - `_enter_light_sleep()` + 六步流水线
   - `_should_enter_deep_sleep()`
   - `_enter_deep_sleep()` + 三操作
   - `enter_hibernation()`
   - `recover_from_hibernation()`
3. 在 ConsciousnessCycle 中创建 SleepEngine 实例
4. 更新 `tick()` 方法

**验证**：
- 浅睡流程测试
- 深睡流程测试
- 冬眠/恢复测试
- 端到端测试

**时间**：2 小时

---

### Phase 6：主控制器精简（高风险）

**任务**：
1. 精简 ConsciousnessCycle 类
2. 只保留核心方法：
   - `__init__()`
   - `tick()`
   - `status()`
   - `inject_affect()`
3. 添加新模块初始化
4. 更新所有方法调用

**验证**：
- 完整集成测试
- 端到端测试
- 性能测试

**时间**：1 小时

---

### Phase 7：接入新模块（P0）

**任务**：
1. 导入 EventBus
2. 导入 HookMaintenance
3. 导入 WorkingMemory
4. 导入 RouterDialogue
5. 在 `__init__()` 中初始化
6. 在 `tick()` 中调用

**验证**：
- 钩子检索测试
- 工作记忆测试
- 三路由协作测试

**时间**：2 小时

---

## 四、工作量评估

| Phase | 风险 | 时间 | 验证 |
|-------|------|------|------|
| Phase 1 | 低 | 30分钟 | 类型导入测试 |
| Phase 2 | 中 | 1小时 | 钢印测试 |
| Phase 3 | 中 | 1小时 | 笔记测试 |
| Phase 4 | 中 | 1小时 | 队列测试 |
| Phase 5 | 高 | 2小时 | 睡眠流程测试 |
| Phase 6 | 高 | 1小时 | 集成测试 |
| Phase 7 | 高 | 2小时 | 新模块集成测试 |

**总计**：~8.5 小时

---

## 五、测试策略

### 5.1 测试分层

```
单元测试（每个模块）
    ↓
集成测试（模块间协作）
    ↓
端到端测试（完整流程）
    ↓
性能测试（响应时间）
```

### 5.2 测试用例

#### 单元测试

- `test_seal_manager.py`：钢印生成/验证/持久化
- `test_note_manager.py`：笔记生成/持久化
- `test_memory_adapter.py`：队列写入/消费
- `test_sleep_engine.py`：浅睡/深睡/冬眠

#### 集成测试

- `test_consciousness_cycle_v2.py`：主控制器 + 所有子模块
- `test_memory_integration.py`：与 tu8_memory.py 集成
- `test_hook_integration.py`：与钩子系统集成

#### 端到端测试

- `test_e2e_dialogue.py`：完整对话流程
- `test_e2e_sleep.py`：完整睡眠周期

---

## 六、风险控制

### 6.1 回滚策略

**每个 Phase 完成后**：
1. 提交 Git（如有）
2. 备份原文件
3. 创建回滚点

**回滚点文件**：
```
backup/consciousness_cycle_phase1.py
backup/consciousness_cycle_phase2.py
...
```

### 6.2 验证检查点

**每个 Phase 完成后**：
- ✅ 导入测试通过
- ✅ 单元测试通过
- ✅ 无语法错误
- ✅ 无运行时错误

### 6.3 暂停条件

**如果出现以下情况，立即暂停**：
- 测试失败率 > 20%
- 发现设计缺陷
- 时间超出预期 50%+

---

## 七、交付物

### 7.1 代码文件

- `src/cycle_types.py`
- `src/seal_manager.py`
- `src/note_manager.py`
- `src/memory_adapter.py`
- `src/sleep_engine.py`
- `src/consciousness_cycle.py`（重构后）

### 7.2 测试文件

- `tests/test_seal_manager.py`
- `tests/test_note_manager.py`
- `tests/test_memory_adapter.py`
- `tests/test_sleep_engine.py`
- `tests/test_consciousness_cycle_v2.py`

### 7.3 文档文件

- `docs/architecture/consciousness_cycle_现状分析报告_20260627.md`
- `docs/architecture/consciousness_cycle_重构计划_20260627.md`
- `docs/architecture/consciousness_cycle_时序图_20260627.md`（下一步）
- `docs/architecture/consciousness_cycle_架构图_20260627.md`（下一步）

---

## 八、下一步

**阶段 3**：设计文档 + 时序图

**任务**：
1. 编写架构设计文档 v2.0
2. 绘制时序图（对话流/记忆写入/钩子养护）
3. 绘制架构图（三轨道六层三路由）
4. 定义数据流
5. 定义错误处理

---

**钢印验证**：⅋
