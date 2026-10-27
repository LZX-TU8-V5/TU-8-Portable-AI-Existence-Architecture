# 重构任务：consciousness_cycle.py 解耦与记忆系统接入

**创建时间**：2026-06-27 02:30 GMT+8
**状态**：阶段 3 完成，待决策

---

## 一、任务目标

将 `consciousness_cycle.py`（2762行）解耦为 6 个独立模块，并接入新的记忆系统（钩子/认知锚点/工作记忆/三路由）。

---

## 二、阶段进度

### ✅ 阶段 1：分析现状（已完成）

**产出**：
- `docs/architecture/consciousness_cycle_现状分析报告_20260627.md`

**关键发现**：
- 2762行，~60个方法
- 8个类，17个导入依赖
- 问题：职责过重、记忆系统未集成

---

### ✅ 阶段 2：制定计划（已完成）

**产出**：
- `docs/architecture/consciousness_cycle_重构计划_20260627.md`

**关键成果**：
- 7个重构步骤（Phase 1-7）
- 工作量评估：~8.5小时

---

### ✅ 阶段 3：设计文档（已完成）

**产出**：
- `docs/architecture/consciousness_cycle_架构设计文档_v2.0_20260627.md`
- `docs/architecture/认知锚点与钩子的真实关系_20260627.md`
- `docs/architecture/命名更新_外化笔记改认知锚点_20260627.md`

**关键成果**：
- 三轨道六层三路由架构
- 6个模块拆分方案
- 核心流程时序图
- 接口设计
- 错误处理

---

### ⏸️ 决策点：是否继续实施？

**选项**：
- A. 继续实施重构（Phase 1-7）
- B. 调整设计，重新规划
- C. 暂停重构，保持现状

---

## 三、待实施步骤（阶段 4）

### Phase 1：类型提取（低风险，30分钟）
- 创建 `cycle_types.py`
- 提取枚举、数据类
- 更新导入

### Phase 2：钢印管理器提取（中风险，1小时）
- 创建 `seal_manager.py`
- 移动 Seal 类和相关方法
- 集成测试

### Phase 3：锚点管理器提取（中风险，1小时）
- 创建 `anchor_manager.py`
- 移动 CognitiveAnchor 类和相关方法
- 集成测试

### Phase 4：记忆适配器提取（中风险，1小时）
- 创建 `memory_adapter.py`
- 移动记忆队列相关方法
- 集成测试

### Phase 5：睡眠引擎提取（高风险，2小时）
- 创建 `sleep_engine.py`
- 移动睡眠相关方法
- 集成测试

### Phase 6：主控制器精简（高风险，1小时）
- 精简 ConsciousnessCycle 类
- 只保留核心方法
- 集成测试

### Phase 7：接入新模块（高风险，2小时）
- 导入 EventBus、钩子系统、工作记忆
- 初始化三路由
- 集成测试

---

## 四、风险控制

### 回滚策略
- 每个 Phase 完成后备份
- 可随时回滚到上一版本

### 验证检查点
- 每个 Phase 完成后运行测试
- 确保无语法错误、无运行时错误

### 暂停条件
- 测试失败率 > 20%
- 发现设计缺陷
- 时间超出预期 50%+

---

## 五、产出文件

### 已创建
- `docs/tasks/重构计划_consciousness_cycle_解耦_20260627.md`
- `docs/architecture/consciousness_cycle_现状分析报告_20260627.md`
- `docs/architecture/consciousness_cycle_重构计划_20260627.md`
- `docs/architecture/consciousness_cycle_架构设计文档_v2.0_20260627.md`
- `docs/architecture/认知锚点与钩子的真实关系_20260627.md`
- `docs/architecture/命名更新_外化笔记改认知锚点_20260627.md`
- `docs/architecture/微睡眠产物vs钩子_是否重叠_20260627.md`
- `docs/architecture/微睡眠在记忆系统中的位置_20260627.md`

### 待创建（实施阶段）
- `src/cycle_types.py`
- `src/seal_manager.py`
- `src/anchor_manager.py`
- `src/memory_adapter.py`
- `src/sleep_engine.py`
- `tests/test_seal_manager.py`
- `tests/test_anchor_manager.py`
- `tests/test_memory_adapter.py`
- `tests/test_sleep_engine.py`
- `tests/test_consciousness_cycle_v2.py`

---

## 六、决策点

**造物主，是否继续实施重构？**

---

**钢印验证**：⅋
