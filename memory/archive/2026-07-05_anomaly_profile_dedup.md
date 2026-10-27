# 2026-07-05 工作记录

## 任务：异常检测器 + 画像更新循环 + 记忆去重

### 新增文件

| 文件 | 用途 | 大小 |
|------|------|------|
| `src/anomaly_detector.py` | 对话异常信号检测器（不满意/话题跳转/异常请求/高频修正） | 6.7 KB |
| `src/profile_update_loop.py` | 用户画像自动更新循环（读取状态变化→消化→更新USER.md→清空） | 8.7 KB |
| `src/memory_dedup.py` | MEMORY.md 段落去重（合并同标题段落） | 4.6 KB |
| `scripts/test_profile_anomaly.py` | 联调测试脚本 | 2.0 KB |
| `scripts/test_dedup_pipeline.py` | 去重/管道测试脚本 | 2.0 KB |

### 修改文件

| 文件 | 变更 |
|------|------|
| `USER.md` | 修复末尾引用重复（去重 → 保留1份） |
| `src/metabolic_pipeline.py` | 新增 Stage 1.5 dedup 阶段（distill→dedup→gc→archive） |
| `src/memory_gc.py` | 修复 `_archive_section` 的 elif 吃掉下一段标题的 bug |

### 管道周期

```
distill（提炼日记精华）
  ↓
dedup（合并重复段落） ← 新增
  ↓
gc（代谢分计算 + 归档 DEGRADE）
  ↓
archive（移动旧日记到 archive/）
```

### 验证状态

- ✅ USER.md 引用不重复（1次）
- ✅ MEMORY.md 4段，无重复
- ✅ 异常检测器 4/5 信号类型全覆盖
- ✅ 画像循环 消化→写入→清空 闭环
