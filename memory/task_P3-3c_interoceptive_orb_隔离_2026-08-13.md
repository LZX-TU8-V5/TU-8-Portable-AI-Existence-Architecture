# P3-3c：内感受到 orb 数据隔离

**日期**：2026-08-13 下午
**状态**：✅ IC 写入已完成

---

## 问题描述

IC（内感受皮层）和 LT（λ调参器）写同一文件 `lambda_state.json`，字段名不规范，导致：
- IC 写 `pain_int` / `pain_ext`（raw 值）
- LT 读 body 的 `_parse_pain_signals()`，然后写 `smoothed_pain_ext/int`
- ORB 读 `smoothed_pain_ext/int`（正确，这是 ORB 用的）
- **但 LT 写时字段名有 bug**：`smoothed_ext` / `smoothed_int`（非 `smoothed_pain_ext/int`）

## 目标

三层职责分离：
| 模块 | 职责 | 字段 |
|------|------|------|
| **IC** | 写 raw（体感感知层） | `pain_int_raw` / `pain_ext_raw` |
| **LT** | 读 raw → EMA 平滑 → 重写 | 读 `pain_int_raw/ext_raw`，写 `smoothed_pain_ext/int` |
| **ORB** | 读 smoothed（状态展示层） | `smoothed_pain_ext/int` ✅ |

## 改动

**文件**：`src/interoceptive_cortex.py` 行 280-281

**Before**：
```python
"pain_int":       pain_int,
"pain_ext":       pain_ext,
```

**After**：
```python
"pain_int_raw":   pain_int,   # [P3-3c] IC写raw版本，LT读后做EMA平滑再写smoothed版本
"pain_ext_raw":   pain_ext,   # [P3-3c] ORB只读smoothed版本，两层隔离
```

## 待办

- [x] **LT 写文件竞态**：✅ 已修。`_save_lambda_state` → `flock.safe_read_json` → `prev.update` → `flock.atomic_write_json`
- [x] **LT 字段名 bug**：✅ 已修。写入改为 `smoothed_pain_ext/int`（原为 `smoothed_ext/int`）
- [x] **IC 写入字段名**：✅ 已修。写 `pain_int_raw/ext_raw`（原为 `pain_int/ext`）
