# 任务归档：alignment_verify 疤自适应阻断阈值升级

**时间**：2026-07-20 11:22
**任务**：疤积累 ≥ 0.6 → L1热也能阻断（疤自适应阻断）

---

## 变更摘要

### `src/alignment_verify.py`（`_check_deep_surface_isolation` 函数）

**疤自适应阻断阈值逻辑**（L1热判断前先查疤）：

| 疤强度 | 条件 | 响应 |
|--------|------|------|
| 无疤 / 轻疤 < 0.6 | `existing_scar < NOTIFY(0.6)` | 带疤通过（A路：抱死保护） |
| 重疤 ≥ 0.6 | `existing_scar >= NOTIFY(0.6)` | **L1热阻断** + `auto_surface=True` |
| 深疤 ≥ 0.8 | `existing_scar >= ARBITER(0.8)` | 阻断 + 触发矛盾仲裁 |

**关键公式**：
```
scar_adjusted_block = existing_scar >= FRICTION_THRESHOLD_NOTIFY  # 0.6
scarred_tension     = min(0.95, base_tension + existing_scar × 0.3)
```

**执行顺序**（先疤后热，防热掩盖疤）：
1. 疤查询（同类历史疤 + topic 匹配）
2. 热锁判断（L3崩溃 → 无条件阻断）
3. L1疤自适应判断

### `src/cognitive_friction_detector.py`（`_load` 函数）

**两个修复**：

1. **`created_ts` 静默错误**：JSON 有 `to_dict()` 写入的 `created_ts`，但 `CognitiveFrictionRecord` dataclass 不接受 → 加载时 `**kwargs` 报错 → `_load()` 吞异常 → 疤痕全丢
   - **修复**：只传 dataclass 接受的字段（白名单过滤）

2. **Suppressed 记录不加载**：旧疤痕被 `suppress()` 后仍留在 JSON 里，被 `_load()` 加载回来
   - **修复**：`if f.get("status") == "suppressed": continue`

### `src/topology_thermal_monitor.py`（调用方修复）

`_check_deep_surface_isolation` 调用了不存在的方法 `tm.get_state()` → 异常被吞 → `thermal_level="unknown"` → 所有热检查失效 → 疤判断短路

- **修复**：改用 `tm.check()` 返回 `ThermalReport`，字段映射：
  - `locked` → `level == "L3_CRITICAL"`
  - `lock_reason` → `recommended_action`

---

## 测试结果

| 测试 | 条件 | 预期 | 实际 |
|------|------|------|------|
| A | 无疤 + L1热 | pass=True + 警告 | ✓ pass=True |
| B | scar=0.65 ≥ NOTIFY(0.6) + L1热 | pass=False 阻断 | ✓ pass=False |
| C | scar=0.82 ≥ ARBITER(0.8) + L1热 | pass=False 阻断 | ✓ pass=False |
| D | scar=0.55 < NOTIFY(0.6) + L1热 | pass=True + 警告 | ✓ pass=True |

全链路集成测试（8阶段）：✓ 通过

---

## 核心机制

```
疤触发（L1热警告）
    ↓ 反复同类话题
疤 ≥ 0.6 → 疤自适应阻断（痛觉记忆）
    ↓ 继续同类话题
疤 ≥ 0.8 → 矛盾仲裁触发（深层求解）
    ↓ 仍不收敛
搁浅协议（L5钢印边界）
```

---
