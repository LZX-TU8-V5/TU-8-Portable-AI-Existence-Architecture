# 内感受皮层（体感环）运行记录

- 任务：cron 79296f55「TU8内感受(体感环)」触发执行 `src/interoceptive_cortex.py`
- 时间：2026-09-24 20:13 (Asia/Shanghai)
- 退出码：0（无 stdout 输出——edge_trigger 判定 silent：告警签名与上次一致，且当前无 ≥0.30 severity 的痛觉信号）

## 关键遥测（memory/interoception_state.json）

| 指标 | 值 |
|------|-----|
| status | ok |
| context_load_pct | 0（genuine 读数为空，43 个会话均为 ≥200k 占位容量，按修复逻辑不误报） |
| assistant_turns_total | 2534 |
| abort_rate（全量） | 0.1709 |
| recent_abort_rate（近 7 天） | 0.0 |
| freeze_sessions / swallowed_total | 0 / 0 |
| baseline | context 0.0 / abort 0.0 |
| pain_signals | [] （空） |
| body_posture | nominal |

## 结论

无告警、无恢复事件、无脚本自身异常；体感环处于稳态（nominal）。遥测已写入 state + lambda_state.json，供 orb 与身体层消费。
