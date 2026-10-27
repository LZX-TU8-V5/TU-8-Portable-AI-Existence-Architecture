# 产物记录：confidence_manager.py 清理 & 乘法黑盒落地

**时间**: 2026-06-30 16:38 GMT+8
**操作**: 清理 confidence_manager.py + 新增核心乘法函数

---

## 一、清理内容

### 1. 去重 MemoryEntry
- **问题**: `confidence_manager.py` 内定义了本地的 `MemoryEntry` dataclass，与 `tu8_memory.py` 重复
- **修复**: 删除本地定义，改用 `from tu8_memory import MemoryEntry`
- **状态**: ✅ 完成

### 2. 统一字段名
- **问题**: `entry.source` → `entry.source_file`（MemoryEntry 真实字段名）
- **修复**: `_is_toxic()` 中 `entry.source` → `getattr(entry, 'source_file', '')`
- **状态**: ✅ 完成

### 3. 统一 ID 字段
- **问题**: 日志中用 `entry.id`（向后兼容字段），但 `MemoryEntry.__post_init__` 只单向迁移 `id→seal_id`
- **修复**: 9处 `entry.id` → `entry.seal_id`（日志输出更准确）
- **状态**: ✅ 完成

### 4. 常量对齐
- `DECAY_LAMBDA = 0.023`（已对齐 tu8_memory.py）
- **状态**: ✅ 已确认

---

## 二、新增：calculate_final_score() 乘法黑盒

```python
def calculate_final_score(self, confidence: float, value: float) -> float:
    """
    最终记忆得分 = 置信度 × 价值

    设计哲学:
      - Toxic (value < 0): 返回负分，不 clamp → 永远排最后
      - Normal (0 ≤ value ≤ 1): clamp [0, 1]

    N维扩展预留:
      total_value = sum(v * w for v, w in zip(entry.value_vector, context_weights))
      final_score = confidence * total_value  # ← 复用此黑盒
    """
    if value < 0:
        return confidence * value  # 负分，不 clamp
    return max(0.0, min(1.0, confidence * value))
```

**测试用例**: 9/9 ✅（边界、Toxic、零值全覆盖）

---

## 三、验证结果

| 测试 | 结果 |
|------|------|
| `confidence_manager.py` 完整自测 | ✅ 7/7 通过 |
| `test_memory_adapter_meaning_fix.py` | ✅ meaning参数修复验证通过 |
| `test_confidence_blackbox.py` | ✅ 9/9 乘法边界测试通过 |

---

## 四、后续待办

- [ ] `Value_Vector` N维数据结构设计（点积接口预留）
- [ ] `calculate_final_score()` 在 `filter_for_context_assembly` 中的实际调用集成
- [ ] 删除遗留临时脚本（`test_*.py`）
