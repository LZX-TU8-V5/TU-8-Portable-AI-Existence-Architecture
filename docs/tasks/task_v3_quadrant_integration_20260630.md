# 任务记录：v3.0 四象限认知引擎集成
日期：2026-06-30
状态：✅ 完成

---

## 一、已完成

### 1. tu8_memory.py — v3.0 字段 + 方法

**MemoryEntry dataclass 新增字段（行 286-321）：**
| 字段 | 默认值 | 说明 |
|------|:------:|------|
| `confidence` | 1.0 | 动态置信度 |
| `value` | 0.5 | 动态价值 |
| `quadrant` | "Q2" | 象限: Q1/Q2/Q3/Q4/Toxic |
| `storage_zone` | "active" | 存储区: active/archived/toxic/dropped |
| `last_used` | 0.0 | 最后使用时间戳 |
| `usage_count` | 0 | 使用次数（置信度惯性分母） |
| `last_eval` | 0.0 | 上次评估时间戳 |
| `conflict_count` | 0 | 被冲突次数 |
| `recall_count` | 0 | 被成功召回次数 |
| `entities` | [] | 实体列表 |
| `decay_lambda` | 0.023 | 遗忘速率常数（参数化） |
| `q1_to_q2_threshold` | 0.5 | Q1→Q2 置信度阈值（参数化） |
| `usage_unused_days_threshold` | 30.0 | 触发遗忘检查的未使用天数（参数化） |

**MemoryEntry 新增方法：**
- `compute_quadrant()` — 四象限判定（高/低 Conf × 高/低 Value）
- `update_quadrant()` — 象限+存储区同步更新
- `update_on_usage(success)` — 使用即验证（惯性分母）
- `migrate_by_confidence()` — Q1→Q2 艾宾浩斯遗忘
- `apply_falsification_penalty()` — 证伪惩罚

**TU8MemoryEngine 新增方法：**
- `_extract_entities()` — 提取标签/@提及/专有名词
- `filter_for_context()` — Toxic/Q4 过滤 + 象限优先级排序
- `get_memory_stats_by_quadrant()` — 各象限统计

**TU8MemoryEngine.store() 集成：**
- Toxic 检测（内容关键词过滤）
- 价值初始化（标签+实体关联度）
- 象限判定 + 存储区更新
- Q4 直接丢弃（不写入）

### 2. confidence_manager.py — 去重 + 常量修正

**改动：**
- 删除本地 `MemoryEntry` dataclass（统一使用 `tu8_memory.MemoryEntry`）
- `DECAY_LAMBDA` 从 0.01 修正为 **0.023**（对齐艾宾浩斯）
- 添加注释说明反推逻辑

### 3. memory_adapter.py — bug 修复

**改动：**
- `meaning=task["narrative_ref"]` → `meaning=task["coherence"]`
- 传入 float 而非 string（匹配 `store()` 方法签名）

---

## 二、待完成

### 1. 集成测试
- 运行 `test_memory_adapter_write.py` 验证修复
- 验证 `filter_for_context()` 是否正确过滤 Toxic/Q4

### 2. 剩余集成（建议顺序）
1. **seal_rag.py** — 调用 `engine.filter_for_context()` 过滤检索结果
2. **memory_adapter.py** — 在成功写入后调用 `entry.update_on_usage(success=True)`
3. **cron 遗忘任务** — 定期调用 `entry.migrate_by_confidence()` 扫描所有记忆
4. **consciousness_cycle.py** — 集成 `confidence_manager` 的意图识别和动态权重

---

## 三、关键设计决策记录

### Q：为什么置信度上限是 0.95 而不是 1.0？
A：留 5% 的怀疑空间。即使是"核心事实"也不应该是 100% 确定，这符合波普尔证伪主义精神——所有知识都是可错的。

### Q：为什么 decay_lambda = 0.023？
A：反推得出。
```
目标：30天不使用 → 置信度衰减至 50%
公式：e^(-λ × 30) = 0.5
推导：λ = ln(0.5) / 30 ≈ 0.693 / 30 ≈ 0.023
```
这个值使得记忆每 30 天约衰减一半，对齐艾宾浩斯真实遗忘曲线。

### Q：为什么 Q1→Q2 阈值是 0.5？
A：低于 50% 置信度的事实，不能再算"高置信度核心"，但仍高于 Q3 阈值（0.3），说明它仍值得保留，只是降级为"冗余知识"。
