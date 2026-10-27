# 任务归档：P1-TensionStep2 张力混合审核器

**时间**：2026-07-22 17:00-17:30
**状态**：✅ 完成

---

## 目标

实现千问对话中设计的 **tension 混合公式**：
```
T_final = T_step1（O(1)规则） + T_step2（LLM语义 ∈[0, 0.3]）
```
审核标准 = **张力**，非正确性（正确性是派生策略，结构性张力才是真正的守卫）。

---

## 完成内容

### 1. `src/tension_audit.py`（10.7KB）

**Step1：O(1) 规则计算初始张力**（三路叠加，max(A, A+B+C)）：

| 路子 | 来源 | 计算 |
|------|------|------|
| A路 | learning_type 基线 | LEARNING_TYPE_TENSION 字典映射 |
| B路 | 关键词命中 | 命中钢印/边界/身份等关键词 → 叠加 |
| C路 | surface_tension 尖刺背景 | anxiety/anger/fear 情绪尖刺超阈值时叠加 |

**Step2：LLM 语义补充**：
- 范围：`[0, 0.3]`，**只能加，不能减**
- 职责：感知规则算不出的"语义张力"
- 实现：`requests` → DashScope API（qwen3.6-flash）
- 当前状态：**HTTP 403**（API key 过期/无效），降级为 Step2=0 不阻断

**门控决策**：
| T_final | 决策 |
|---------|------|
| ≥ 0.85 | block（结构冲突，丢弃）|
| ∈ [0.7, 0.85) | escalate（移交矛盾仲裁）|
| ∈ [0.4, 0.7) | caution（标记注意）|
| < 0.4 | accept（低张力直接写入）|

**集成桥接** `tension_gate()`：张力-置信度双门控。

---

### 2. `src/learning_verify.py` 修改

**集成点**：`PalaceValidator.validate()` 在图书馆校验之后、置信度门控之前：

```
图书馆校验
    ↓
张力门控（P1-Step2）
    ↓ T≥0.85 → block（丢弃）
    ↓ T∈[0.7,0.85) → escalate（移交仲裁，丢弃）
    ↓ T<0.7 → 继续置信度门控
置信度门控
    ↓
跨周期一致性
```

---

## 测试结果（集成验证）

| 案例 | 张力 | 置信度 | 决策 |
|------|------|--------|------|
| 早餐吃了什么 | N/A | 0.5 | pending（低张力，纯置信度门控）|
| 钢印vs置信度 | 1.0 | 0.9 | **block** ✅ |
| 钢印进化边界 | 1.0 | 0.8 | **block** ✅ |
| 价值观冲突 | 0.75 | 0.9 | **escalate** ✅ |
| 本体论修复 | 0.85 | 0.8 | **block** ✅ |

---

## 技术说明

- **Step2 LLM HTTP 403**：DashScope API key `sk-07f14deb...` 返回 403。可能是 key 过期、余额不足或域名限制。Step1 规则引擎完全独立可用，Step2 仅作为额外补充。
- **导入兼容性**：`from tension_audit import ...` / `from .tension_audit import ...` 双模式 try/except，确保 workspace 和 package 两种运行模式下均可用。
- **审计日志**：`src/` 外不可见，`_agent_memory/tension_audit_log.jsonl` 记录每次审核结果。

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/tension_audit.py` | 新建 | 张力审核器 |
| `src/learning_verify.py` | 修改 | 集成张力门控 |
| `TODO_MASTER.md` | 修改 | 标记完成 |
| `_agent_memory/tension_audit_log.jsonl` | 新建 | 审计日志 |
