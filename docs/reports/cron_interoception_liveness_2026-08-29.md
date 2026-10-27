# Cron: TU8监测存活 — interoception_liveness.py

- 时间: 2026-08-29 09:47 (Asia/Shanghai)
- 命令: `interoception_liveness.py --stale-min 360 --degraded-ok`
- 退出码: 0

## 现象
脚本在普通模式（无 --json）下**无任何 stdout 输出**。

## 根因（边沿触发静默）
- `check()` 返回 problems = [("missing", "interopertion_state.json 不存在...")]
- 边沿触发逻辑：当前签名 sig 与上次记录 `interopertion_liveness_last.json` 中 sig 完全一致
  - 上次记录时间: 2026-08-09 10:31:09
  - 签名未变化 → `return` 静默，不打印告警
- 因此脚本"正常退出且无输出"，不等于"监测健康"

## 真实状态（--json 实测）
```json
{
  "timestamp": "2026-08-29 09:47:56",
  "problems": [
    {
      "type": "missing",
      "message": "interopertion_state.json 不存在（监控从未运行或已死）"
    }
  ]
}
```

## 结论
- `memory/interopertion_state.json` 自 2026-08-09 起持续缺失（内感受体感环未运行/已死）
- 因边沿触发，告警自 2026-08-09 起被压制，cron 每轮静默
- 建议：确认内感受脚本（interoception 模块）是否仍在调度；或清除 `interopertion_liveness_last.json` 让其重新告警
