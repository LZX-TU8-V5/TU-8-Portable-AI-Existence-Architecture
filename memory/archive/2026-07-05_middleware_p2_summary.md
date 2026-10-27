# P2 中间件：T5→T2 + T2→T4 实现总结

> 2026-07-05 23:10 GMT+8

---

## 新增中间件

### T5→T2：学习产物→钢印铸造 — `src/learning_to_seal_adapter.py` (3.4KB)

- 学习产物达到信心阈值（>=0.6）→ 自动铸印到 `seal_index.json`
- 含 seald_id / scene_tag / summary / product_id 等完整元数据
- 低置信度产物（<0.6）跳过
- 验证：ALERT(0.85)✅ INTUITION(0.72)✅ MEMO(0.45)❌

### T2→T4：钢印→GC 加权 — `src/seal_to_gc_adapter.py` (4KB)

- 钢印场景标签映射为 GC 主题关键词（如 learning:alert → 异常/监控/anomaly）
- GC 评分时匹配段落标题+内容 → 加权加成（+0.05 ~ +0.15）
- 5分钟缓存
- 不修改核心 GC 评分公式

## 5链耦合图谱全线贯通

| 路径 | 优先级 | 文件 | 状态 |
|------|--------|------|------|
| **T5→T4** 学习→GC保护 | P0 | `learning_to_gc_adapter.py` | ✅ |
| **T1→T5** 钢印→学习 | P1 | `seal_to_learning_adapter.py` | ✅ |
| **T4→T5** GC→学习 | P1 | `gc_to_learning_adapter.py` | ✅ |
| **T5→T2** 学习→钢印 | P2 | `learning_to_seal_adapter.py` | ✅ |
| **T2→T4** 钢印→GC | P2 | `seal_to_gc_adapter.py` | ✅ |
| T2→T3 钢印→调度 | P2 | 依赖 T3 调度链 | ⏳ |
| T3→T2/T4/T5 | P2 | 依赖 T3 | ⏳ |
| T4→T3 GC→调度 | P2 | 依赖 T3 | ⏳ |
| T5→T3 学习→调度 | P2 | 依赖 T3 | ⏳ |

## 完整数据流

```
seal_index.json → T1→T5 → learning_collector (seal:3) → Phase 2-3
                                                              ↓
seal_index.json ← T5→T2 ← learning_apply (铸印新产品)
     ↓
T2→T4 → memory_gc.analyze_memory() (关键词匹配→score+0.1)
     ↓
T4→T5 → gc_to_learning_adapter → _gc_feedback.jsonl → learning Phase 1
```
