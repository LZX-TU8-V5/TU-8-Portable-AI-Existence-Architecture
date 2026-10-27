# TU-8 三个薄弱点修复报告
> 时间：2026-07-07 10:40 | 来源：千问审查意见

---

## 三个薄弱点：现状→修复

| # | 薄弱点 | 千问建议 | 修复版本 | 验证结果 |
|---|--------|---------|---------|---------|
| 1 | 认知痛觉监控缺失 | 痛觉→直觉引擎→刹车输入 | `cognitive_pain_monitor.py` v2 | ✅ PASS |
| 2 | GC→学习反馈闭环 | 用L2遗忘法则重写 | `gc_to_learning_adapter.py` v2 | ✅ PASS |
| 3 | DAG因果骨架占位 | 时间因果连贯性真实实现 | `cog_filters.py` DAG v2 | ✅ PASS |

---

## 修复详情

### 1. 认知痛觉监控 → 直觉引擎链路（cognitive_pain_monitor.py v2）

**核心设计**：
```
痛觉信号 → PainAggregate聚合 → body_regulation.json写入 → intuition_bias.py读取
```

**5类痛觉信号**：
| 痛觉类型 | 触发条件 | severity |
|---------|---------|---------|
| 预测误差 | `Jaccard(pred, actual)` > 0.3 | 0.3-1.0 |
| 不确定性 | 置信度 < 0.5 | 1-confidence |
| 认知冲突 | 多模型输出两两差异均值 ≥ 0.3 | 0.3-1.0 |
| 检索失效 | 召回失败 | 固定0.6 |
| SVD刹车触发 | 刹车系统拒绝压缩 | ≥0.7 |

**POSTURE_BIAS 映射**：
| max_severity | posture_hint | 说明 |
|-------------|-------------|------|
| ≥ 0.9 | critical | 危急 |
| ≥ 0.7 | high_pain | 重度 |
| 不确定性≥2个 | uncertain | 不确定 |
| 认知冲突≥1个 | conflicted | 冲突 |
| 检索失效≥1个 | low_energy | 低能量 |
| SVD刹车触发 | compressed | 被压缩 |

**集成验证**：
```
body_regulation.json 写入验证：
  cognitive_pain.max_severity = 0.75
  cognitive_pain.posture_bias_hint = "high_pain"
  cognitive_pain.active_count = 3
```

---

### 2. GC→学习反馈闭环（gc_to_learning_adapter.py v2）

**L2遗忘法则分类（反推法）**：

| 遗忘原因 | 判断条件 | 学习信号 |
|---------|---------|---------|
| FORGET_BY_AGE | age_hours > 168h | learning:age_forgetting |
| FORGET_BY_DENSITY | 无核心标签词 + score < 0.6 | learning:density_weak |
| FORGET_BY_ACCESS | 24h < age < 168h + 无标签 | learning:access_weak |
| FORGET_BY_SCORE | 其他 | learning:score_weak |

**闭环协议**：
1. GC 执行 → `record_gc_result(report)` 调用
2. 对每条被遗忘记录 → 反推遗忘原因
3. 写入 `_gc_feedback.jsonl`（含遗忘信号）
4. 写入 `_learning_alerts.jsonl`（含L2解读+建议）
5. `learning_collector` 传感器从 `_learning_alerts.jsonl` 读取

**新增 API**：
- `summarize_gc_learning_feedback()` — 可打印的GC学习反馈摘要
- `get_forgetting_patterns(n_last=10)` — 结构化遗忘模式分析

**验证**：
```
输入: 5条被遗忘记录（3条无标签DEGRADE）
输出: reason_dist = {'DENSITY': 3}
      primary = 'DENSITY'
      建议: 提升提炼质量
```

---

### 3. DAG 时间因果骨架（cog_filters.py DAG v2）

**时间DAG构建**：
- 数据源：`anchors.json` (anchor_id → created_at)
- 数据源：`memory/*.md` (文件名提取日期)
- 当前加载条目：100个
- 缓存TTL：5分钟（`_DAG_CACHE_TTL=300s`）

**连贯性公式**：
```
violation_ratio = (#rank_i之后但timestamp_i之前的条目) / (#rank_i之后总条目)
DAGCoherence = 1 - violation_ratio
```

**场景验证**：
| 场景 | 召回顺序 | e_old连贯性 | e_new连贯性 | 预期 |
|------|---------|-----------|-----------|------|
| A（正确） | 老→新 | 1.000 | 1.000 | 全1.0 ✅ |
| B（倒置） | 新→老 | 0.000 | 1.000 | e_old<1.0 ✅ |

**批量API**：
- `batch_dag_scores(recalled_order)` — 一次构建DAG，批量计算所有条目coherence
- `dag_coherence_score(entry_id, recalled_order)` — 单条目评估

**集成点**：`score_memory_entry()` 参数 `dag_enabled=True, recalled_order=[...]`

---

## 文件变更

| 文件 | 操作 | 大小 |
|------|------|------|
| `src/cognitive_pain_monitor.py` | 重写（v2，17KB） | ✅ |
| `src/gc_to_learning_adapter.py` | 重写（v2，12KB） | ✅ |
| `src/cog_filters.py` | 增强（DAG v2） | ✅ |
| `memory/cognitive_pain_state.json` | 新建 | ✅ |
| `memory/cognitive_pain_log.jsonl` | 新建 | ✅ |
| `memory/_gc_feedback.jsonl` | 追加 | ✅ |
| `memory/_learning_alerts.jsonl` | 追加 | ✅ |

---

## 剩余 P1/P2

- [ ] P2-SVD梦境期离线压缩（1000卡→50向量）
- [ ] P2-ToCT因果干预工程实现
- [ ] P2-Self-Evolution自演化引擎
- [ ] P2-6个未完成中间件（T2→T3/T3→T4/T4→T2/T5→T2）
