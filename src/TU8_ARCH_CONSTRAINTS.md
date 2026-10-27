# TU-8 架构约束清单 v1.0

> 用途：Auto 模型生成 TU-8 代码时强制遵守的架构约束
> 版本：v1.0 | 日期：2026-07-12
> 维护：造物主 + TU-8

---

## 约束生效范围

**所有 TU-8 核心模块**（新建或重写时必须满足）：
- 欲系统：`surface_tension.py`
- 学习系统：`learning_collector.py`, `learning_engine.py`, `gc_to_learning_adapter.py`
- 置信度：`dual_track_confidence_updater.py`, `confidence_pipeline.py`
- 痛觉系统：`cognitive_pain_monitor.py`
- 耦合器：`tension_learning_coupler.py`, `prediction_tension_coupler.py`
- 元认知：`dream_consolidation.py`, `hook_injector.py`

---

## 约束条款

### C1【强制】未解尖刺暂存队列

**适用**：任何涉及 surface_tension / 欲系统 / 学习信号 的模块

**要求**：
- 必须维护一个 `_agent_memory/unresolved_spikes.jsonl` 文件
- 每条尖刺记录必须包含：`spike_id`, `ts_unix`, `emotion`, `magnitude`, `is_valley`
- 必须提供 `resolve_spike(spike_id)` 方法，将已解决的尖刺从队列移除
- **禁止**：尖刺只记录不追踪

**违例**：
```python
# ❌ 错误：只记录，无追踪
surface_tension.record(type="steel_conflict")

# ✅ 正确：追踪 + 可解决
sig = predict_error_to_tension(...)
# → 自动写入 unresolved_spikes.jsonl
resolve_spike(sig.spike_id)  # 解决后移除
```

---

### C2【强制】传感器路径耦合

**适用**：新建 `SENSOR_PATHS` 或修改学习收集器

**要求**：
- learning_collector 的 SENSOR_PATHS 必须包含：
  - `gc_feedback` → `_gc_feedback.jsonl`
  - `tension_signals` → `learning_alerts.jsonl`
  - `cognitive_pain` → `cognitive_pain_monitor.json`
- 禁止新建孤立的传感器路径（不被任何消费者读取）
- 新增传感器必须通知 TU-8 验收

**违例**：
```python
# ❌ 错误：孤立传感器，无消费者
"my_sensor": WORKSPACE / "memory" / "my_data.jsonl"

# ✅ 正确：传感器 → 有明确消费者
"tension_signals": WORKSPACE / "memory" / "learning_alerts.jsonl"
```

---

### C3【强制】三维耦合链路

**适用**：欲系统 × 学习系统 × 置信度 的任意交叉模块

**要求**：必须覆盖三段链路：

| 链路段 | 起点 | 终点 | 必须包含 |
|--------|------|------|---------|
| 外部→欲 | cognitive_pain / friction | surface_tension | `predict_error_to_tension()` |
| 欲→置信度 | surface_tension | Track B | `get_unresolved_tension_score()` |
| 置信度→欲 | confidence update resolved | surface_tension | `resolve_spike()` |

**违例**：
```python
# ❌ 错误：只做单向，不闭环
def record_tension(type):
    surface_tension.record(type)
    # 没有追踪，没有反馈

# ✅ 正确：完整三维链路
sig = predict_error_to_tension(...)
_write_unresolved_spike(sig)
# ... later ...
resolve_spike(sig.spike_id, resolution="learned")
```

---

### C4【强制】预测误差 × 置信度 → 七情映射表

**适用**：`prediction_tension_coupler.py` 或等价模块

**要求**：必须包含以下映射（禁止删减）：

| 置信度 | 误差幅度 | 情绪 | 尖刺类型 |
|--------|---------|------|---------|
| 低 | 高 | 焦虑 | spike |
| 高 | 高 | 愤怒 | spike |
| 中 | 高 | 恐惧 | spike |
| 中 | 低 | 好奇 | valley |
| 高 | 低 | 微好奇 | valley |
| 低 | 中 | 焦虑 | spike |

**映射函数签名**：
```python
def predict_error_to_tension(
    prediction: str,
    actual: str,
    confidence: float,      # [0, 1]
    error_magnitude: float # [0, 1]
) -> PredictionTensionSignal
```

---

### C5【强制】Track B 张力惩罚机制

**适用**：`dual_track_confidence_updater.py`

**要求**：
- Track B 更新必须调用 `get_unresolved_tension_penalty()`
- 公式：`adjusted_tension = tension_resolved × penalty`
- 惩罚系数范围：`[0.3, 1.0]`
- 提供 `update_track_B_with_tension_penalty()` 方法

**违例**：
```python
# ❌ 错误：硬编码，无欲系统调制
delta = 0.15 + 0.25 * tension

# ✅ 正确：欲系统惩罚
penalty = self.get_unresolved_tension_penalty()
delta = 0.15 + 0.25 * (tension * penalty)
```

---

### C6【强制】身体状态 → 欲系统基线

**适用**：`body_state_to_tension()` 或等效模块

**要求**：必须读取并耦合以下身体信号：

| 身体信号 | 来源文件 | 耦合目标 |
|---------|---------|---------|
| cognitive_pain severity | body_regulation.json | anxiety / fear |
| interoceptive status | body_regulation.json | anxiety / fear |
| system_entropy | body_regulation.json | baseline_tension |

---

### C7【强制】耦合文件路径规范

**要求**：
- surface_tension 状态：`_agent_memory/surface_tension_state.json`
- 未解尖刺队列：`_agent_memory/unresolved_spikes.jsonl`
- 学习警报（统一）：`memory/learning_alerts.jsonl`
- cognitive_pain 状态：`memory/cognitive_pain_monitor.json`
- 禁止混用路径（如 `learning_alerts.jsonl` 和 `_learning_alerts.jsonl` 并存）

---

## 验收协议

### Auto 模型生成后，TU-8 执行以下检查：

**自动验收（必须通过）**：
- [ ] C1：`unresolved_spikes.jsonl` 存在且格式正确
- [ ] C2：`learning_collector.py` 的 SENSOR_PATHS 包含 tension_signals
- [ ] C3：耦合链路三段均有实现
- [ ] C4：预测误差映射表完整（6行）
- [ ] C5：Track B 有张力惩罚机制
- [ ] C6：body_state_to_tension() 存在
- [ ] C7：路径无混用

**人工验收（TU-8 执行）**：
- [ ] 集成测试：5/5 用例通过
- [ ] 无循环依赖
- [ ] artifact 写入 memory/

---

## 约束变更流程

1. 造物主提出新增/修改约束
2. TU-8 评估技术可行性
3. 更新本文档，标注变更日期
4. Auto 模型下次生成时自动遵守新约束

---

**版本历史**：
- v1.0（2026-07-12）：初始版本，包含 C1-C7 七条约束
