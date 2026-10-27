# 内感受皮层运行记录

- 时间：2026-08-19 08:33 (Asia/Shanghai)
- 命令：`python src/interoceptive_cortex.py`
- 退出码：0
- 标准输出：空（silent 模式，无告警边沿）

## 说明
脚本默认模式仅在「告警边沿触发(edge_trigger=alert)」或「恢复(recover)」时打印，
否则静默（仅写遥测文件：memory/interoception_state.json + _agent_memory/lambda_state.json）。
本次运行未触发告警边沿，故 stdout 为空，属正常行为。

## 本轮回写产物（未打印，但已落盘）
- memory/interoception_state.json（含 context_load_pct / abort_rate / baseline / pain_signals）
- _agent_memory/lambda_state.json（orb 三轴：anxiety/anger/fear/curiosity/basin_health）
- memory/interoception_history.json（滚动基线更新，cap=200）

## 如需完整诊断输出
运行：`python src/interoceptive_cortex.py --json`
