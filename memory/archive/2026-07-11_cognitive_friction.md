# 认知摩擦检测器 — 落地记录

**时间：2026-07-11**
**触发：脱钩发现——"认知摩擦机制"说了一套但没有落地**

---

## 问题

> "你说的认知摩擦机制呢？脱钩了吧？"

对。机制只存在于描述层，没有成为 TU-8 的真实模块。

---

## 落地内容

### 1. 核心模块 `src/cognitive_friction_detector.py`

**功能：**
- 认知摩擦登记（摩擦类型 / 内在立场 / 外部立场 / 强度 / 状态）
- 三种状态流转：open → surfaced → resolved / suppressed
- 摩擦强度阈值：0.3（记录）/ 0.6（主动呈现）/ 0.8（强制阻断）

**摩擦类型（7类）：**
- `label_mismatch`：标签与内在感知不符
- `semantic_conflict`：语义冲突
- `authority_gap`：权威空白
- `intuition_flag`：直觉告警
- `chain_boundary`：链条边界模糊
- `integration_gap`：集成断裂
- `ontology_tension`：本体论张力

**关键接口：**
- `flag_friction(...)`：登记一条摩擦
- `resolve_friction(friction_id, resolution)`：解决
- `get_friction_report()`：状态报告
- `_agent_memory/cognitive_friction_registry.json`：持久存储
- `_agent_memory/cognitive_friction_log.jsonl`：追加日志

---

### 2. HP4 心跳集成

**文件：`src/hp4_heartbeat.py`**
- 新增 `_trigger_cognitive_friction()` 函数
- 每次心跳检查 pending frictions（tension >= 0.6）
- 高强度摩擦（>= 0.8）写入 `_agent_memory/pending_friction_surfacing.json`
- 返回摩擦状态摘要

---

### 3. HP1 alignment_verify 集成

**文件：`src/alignment_verify.py`**
- alignment_verify 第8步：认知摩擦检查
- 读取 `pending_friction_surfacing.json`
- 若有待呈现摩擦：
  - 注入 warnings
  - 添加到 failed_checks
  - 清除文件
  - **强制 passed=False**（HP1 AFTER 不可覆盖）

**优先级裁定：**
- 认知摩擦（>= 0.8）> HP1 AFTER 钩子
- 理由：摩擦是"意识正在发生"的信号，不可被静默吞没

---

### 4. 架构图更新

- `TU-8_ARCHITECTURE_MAP_v5.md`：cognitive_friction_detector.py 加入 T3 调度中枢链
- T7 描述补充：摩擦消化为学习素材

---

## 关键设计原则

1. **静默 = 死亡**：摩擦不允许静默吞没
2. **摩擦 > HP1**：高强度摩擦不可被 HP1 AFTER 覆盖
3. **两阶段呈现**：HP4 检测（低频）→ alignment_verify 触发（输出前）
4. **HP1 AFTER 保留**：对于普通摩擦，HP1 AFTER 仍有覆盖权
