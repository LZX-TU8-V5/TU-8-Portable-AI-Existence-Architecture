# 耦合中间件完成清单

> 2026-07-05 23:00 GMT+8
> P0+P1 全通道验证通过

---

## 实现状态

| 路径 | 优先级 | 文件 | 状态 |
|------|--------|------|------|
| **T5→T4** 学习产物→GC保护 | P0 | `src/learning_to_gc_adapter.py` | ✅ |
| **T1→T5** 钢印→学习传感器 | P1 | `src/seal_to_learning_adapter.py` | ✅ |
| **T4→T5** GC反馈→学习传感器 | P1 | `src/gc_to_learning_adapter.py` | ✅ |

## 修改文件

| 文件 | 改动 |
|------|------|
| `src/memory_gc.py` | `_load_protected_sections()` + `analyze_memory()` 保护检查 + `run_gc()` 后调用 `record_gc_result()` |
| `src/learning_apply.py` | 导入 `gc_on_apply`，apply 后自动注册保护 |
| `src/learning_collector.py` | 导入 `SealSensorAdapter`，新增 seal/gc_feedback 传感器 + SENSOR_PATHS |

## 仍缺失的中间件（P2）

| 路径 | 功能 |
|------|------|
| T2→T3 | 钢印链→调度链 |
| T2→T4 | 钢印链→代谢链（钢印置信度影响 GC 分数） |
| T3→T2 | 调度链→钢印链（执行历史→决策反思） |
| T3→T4 | 调度链→代谢链（执行频率→访问计数刷新） |
| T3→T5 | 调度链→学习链（执行模式→模式发现） |
| T4→T3 | 代谢链→调度链（GC 清仓后触发调度重排） |
| T5→T2 | 学习链→钢印链（新学习产物→新钢印铸造） |
| T5→T3 | 学习链→调度链（产物优先级→调度重排） |
