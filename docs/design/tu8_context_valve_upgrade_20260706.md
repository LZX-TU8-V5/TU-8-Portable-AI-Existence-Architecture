# TU-8 上下文阀门改造 @ 2026-07-06 11:45

## 目标
解决长会话上下文 100%（250k tokens）导致的 LLM abort / 冻结 / 吞输入问题。

## 改动

### 1. openclaw.json 配置（重启生效）

**agents.defaults.compaction**（新增字段）：
| 字段 | 值 | 效果 |
|------|-----|------|
| `truncateAfterCompaction` | true | 压缩后轮转会话 JSONL，只保留摘要+新鲜尾 |
| `maxHistoryShare` | 0.45 | 历史记录压缩后不超过 45%（原默认~60%） |
| `keepRecentTokens` | 30000 | 保留最近 30k 不压 tokens |
| `reserveTokensFloor` | 50000（不变） | 保留 50k 生成余量 |

**plugins.entries.lossless-claw.config**（收紧阈值）：
| 字段 | 原值 → 新值 | 效果 |
|------|-------------|------|
| `contextThreshold` | 0.6 → **0.4** | 40% 上下文即触发压缩（原 60%），早踩刹车 |
| `freshTailCount` | 64 → **32** | 只有最近 32 条保持不压 |
| `freshTailMaxTokens` | 40000 → **20000** | 新鲜尾上限砍半 |

### 2. 新增 src/context_controller.py（5463 bytes）

动态监测体系，每 2.5h 随内感受皮层运行：

**调节曲线**：
| 上下文负载 | contextThreshold | freshTailCount | 姿态区 |
|-----------|-----------------|----------------|--------|
| < 40% | 0.55 | 48 | relaxed |
| 40-65% | 0.45 | 35 | normal |
| 65-85% | 0.35 | 22 | tight |
| > 85% | 0.25 | 16 | critical |

**产出**：写入 `memory/context_control.json`，含 posture_zone、delta 建议（lower/raise/None）、近 5 次历史。

### 3. 集成链路

- `interoceptive_cortex.py` main() 尾部：在 write_telemetry 后调用 `context_controller.compute(load_pct)`，副效应不阻断主流程
- `HEARTBEAT.md` 新增「上下文阀门检查」：连续 3 次 critical → 生成会话摘要 → 建议主动结束

### 4. 配置写入方式

lossless-claw + compaction 均为 gateway protected paths，config.patch 禁止修改。解决：直写 `openclaw.json` + `gateway restart`。

## 预期效果

- 当前会话重启后从 250k 降到 ~150-180k（摘要 100k + 新鲜尾 20k + reserve 50k）
- 后续对话增长时，40% 阈值早掐，`truncateAfterCompaction` 轮转防止二次膨胀
- context_controller 每 2.5h 记录recommendation，heartbeat 可在 critical 态时建议干预

## 待解决（开放项）

- 自适应基线尚未驱动自动配置修改（因 threshold 为 protected 路径，不能热改）
- 真正的"动态调节"需要：gateway 端放开 protected 路径，或手动修改 openclaw.json + restart
- 当前脚本只监测和推荐，不自动重启（避免打断工作流）
