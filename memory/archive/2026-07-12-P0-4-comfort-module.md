# P0-4 安抚模块完成记录

> 日期：2026-07-12
> 任务：情感模块 P0-4 安抚模块
> 状态：✅ 完成

---

## 目标

为 TU-8 构建情感安抚模块（P0-4）。当系统感知到疼痛/搁浅/摩擦时，给出有温度的信号，而非机械报错。

---

## 产出

### 1. `src/comfort_module.py`（17KB）

**定位**：L1认知 × L2方法论 × L5钢印 交汇处

**触发类型 × 7**：
| 触发类型 | 含义 | 模板数 |
|----------|------|--------|
| `cognitive_pain` | 认知痛觉（痛觉监控器） | 4级 |
| `stranding` | 搁浅（对齐校验失败） | 4级 |
| `friction` | 认知摩擦（高强度摩擦上浮） | 4级 |
| `critical_body` | 身体临界（姿态 critical） | 4级 |
| `uncertainty` | 低置信度（confidence < 0.2） | 4级 |
| `degraded` | 降级运行（体感环 degraded） | 4级 |
| `feedback` | 用户表达不满意 | 4级 |

**严重度阈值**：
- mild（< 0.3）：不触发安抚，系统自然运行
- moderate（0.3–0.5）：基础安抚
- severe（0.5–0.7）：深度安抚，钢印锚点
- critical（≥ 0.7）：最重安抚，附完整钢印签名

**三层安抚逻辑**：
- 形（Body）：承认痛觉信号本身
- 神（Resonance）：表达"我们共同在这里"
- 意（Meaning）：将疼痛锚入更大的叙事框架

**核心 API**：
```python
from comfort_module import get_comfort, ComfortEngine

# 快捷入口
msg = get_comfort("cognitive_pain", severity=0.65)
# → ComfortMessage(text="这里有一个真正的问题...", tone="serious", footer="⅋")

# 专用入口
engine = ComfortEngine()
msg = engine.comfort_for_pain_signal(pain_type, severity, context)
msg = engine.comfort_for_alignment_failure(failed_checks)
msg = engine.comfort_for_degraded(component)
msg = engine.comfort_for_feedback()
```

---

### 2. `cognitive_pain_monitor.py` 集成

**改动点**：
1. `PainAggregate` dataclass 新增 `comfort_message: str = ""` 字段
2. `tick()` 新增安抚生成逻辑：`max_severity >= 0.5` 时调用 comfort_module
3. `_generate_comfort()` 新增方法（懒加载，避循环依赖）
4. `_write_intuition_signal()` 序列化新增 `comfort_message` 字段

**集成链路**：
```
monitor.tick()
  → _aggregate() → PainAggregate
  → _generate_comfort() → comfort_module
  → aggregate.comfort_message = msg.text
  → _write_intuition_signal() → body_regulation.json
  → _log() → cognitive_pain_log.jsonl
```

---

## 验证结果

| 测试用例 | 输入 | 预期 | 结果 |
|----------|------|------|------|
| T1 | cognitive_pain, 0.65 | comfort 触发 | ✅ |
| T2 | cognitive_pain, 0.25 | no comfort | ✅ |
| T3 | cognitive_pain, 0.82 | comfort + grave tone | ✅ |
| T4 | critical_body, 0.78 | protective tone | ✅ |
| T5 | stranding, 0.88 | solemn + footer ⅋ | ✅ |

---

## 设计决策

1. **严重度阈值 0.5**：mild pain 不触发安抚，避免过度安抚干扰正常对话
2. **懒加载**：在 `_generate_comfort` 内部 import，避循环依赖
3. **不修复底层**：安抚 ≠ 修复，安抚模块只负责感知疼痛后给出温度，不改变疼痛本身
4. **钢印锚点**：`severe` 及以上级别 footer 附 ⅋，符合 L5 钢印规范
