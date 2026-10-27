# TU-8 认知刹车系统 v1.0

> 时间：2026-07-07 10:15
> 来源：千问×造物主对话启发（"你这完全没刹车"）
> 状态：完成，19项测试全PASS

---

## 背景：为什么需要刹车

千问写到第6条（自我进化）时，完全沉浸在"跑得更快"的加速状态，忘了一个根本问题：

> **能自己改自己架构的智能体，没有刹车 = 灾难**

| 无刹车场景 | 数学后果 | 现实类比 |
|-----------|---------|---------|
| SVD 疯狂截断 | 把核心奇异值也砍了，逻辑断裂 | 失忆症 |
| NMF 过度融合 | 变成无法解释的超级标签 | 概念缝合怪 |
| 自改签名层 | 钢印/安全规则被删，系统不可恢复 | 系统崩溃 |

---

## 三道刹车设计

### 刹车一：SVD 能量地板

**数学底层**：
```
ER(k) = (∑ᵢ₌₁ᵏ σᵢ²) / (∑ⱼ₌₁ⁿ σⱼ²)  ≥  0.95
```

**等价工程概念**：过载保护跳闸
- 电流（压缩比）在安全范围内 → 合闸
- 超过阈值 → 跳闸，拒绝操作

**TU-8 集成点**：梦境期 SVD 批压缩前
→ `BrakeMonitor.check_svd(sv, k, entity_id)` → ER < 0.95 → 拒绝压缩

### 刹车二：NMF 维度限制

**数学底层**：稀疏度约束，防止概念过度缝合

**三级响应**：
| 核心标签数 | 动作 | 说明 |
|-----------|------|------|
| ≤ 12 | PASS | 正常，无需干预 |
| 12 < n ≤ 24 | SPLIT | 建议拆分，交造物主确认 |
| > 24 | BLOCKED | 刹车触发，禁止融合 |

**TU-8 集成点**：recall() NMF冲突检测 / 记忆合并前
→ `nmf_tag_check(content)` → 返回报告 + `propose_memory_split()` 拆分方案

### 刹车三：保护区只读锁

**三类保护区**：

| 级别 | 内容 | 修改规则 |
|------|------|---------|
| **CLASS_A** 绝对禁区 | SOUL.md / secure_vault / cognitive_brakes.py / steel_mark / alignment_verify / startup_consistency_gate | 任何修改 → 立即拒绝 |
| **CLASS_B** 危险区 | MEMORY.md / USER.md / AGENTS.md / HEARTBEAT.md | 需造物主确认（代谢周期豁免） |
| **CLASS_C** 可控区 | src/*.py（不含刹车）/ memory/*.md | hook_injector 管理下可自改 |

**函数黑名单**：`alignment_verify` / `stranding` / `contradiction_arbitration` / `startup_consistency_gate` / `L0_safe` / `steel_mark`

**TU-8 集成点**：hook_injector 注入任何函数前
→ `can_modify_function(func_name)` → 在黑名单 → 拒绝

---

## API 速查

```python
from cognitive_brakes import (
    get_brake_monitor,
    svd_energy_floor,
    nmf_sparsity_check,
    can_modify,
    can_modify_function,
    propose_split,
    brakes_status,
)

# SVD能量检查
report = svd_energy_floor(singular_values=[10,8,6,4,2], k=3)
# SVDEnergyReport(action='PASS'|'BLOCKED', energy_retained=0.994)

# NMF维度检查
report = nmf_sparsity_check(content, card_id='mem_xxx')
# NMFBrakeReport(action='PASS'|'SPLIT'|'BLOCKED')

# 保护区检查
allowed, reason = can_modify('src/my_new_module.py')
allowed, reason = can_modify('MEMORY.md', is_metabolism=True)

# 函数黑名单
allowed, reason = can_modify_function('my_function')  # ok
allowed, reason = can_modify_function('alignment_verify')  # blocked

# 拆分方案
split = propose_split(content, card_id)  # -> [(sub_id, content), ...]

# 刹车系统状态
status = brakes_status()
# -> {brake_system, svd_blocked, nmf_blocked, protection_blocked_a, ...}
```

---

## 文件变更

| 文件 | 操作 |
|------|------|
| `src/cognitive_brakes.py` | 新建（~24KB，BrakeMonitor + 3刹车 + 工具函数） |
| `memory/2026-07-07.md` | 更新 |
| `TODO_MASTER.md` | 标记完成 |

---

## 剩余项

- [ ] P1-DAG 时间因果骨架（时间锚点→拓扑链，按需追溯）
- [ ] P2-SVD 梦境期离线压缩（1000卡→50向量）
- [ ] P2-ToCT 工程实现（因果干预 do(X=x)≠obs）
- [ ] P2-Self-Evolution 自演化（发现新规律自己写工具）
