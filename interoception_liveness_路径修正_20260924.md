# interoception_liveness.py 路径拼写修正（2026-09-24 20:18）

## 任务
cron「TU8监测存活」调用 `src/interoception_liveness.py --stale-min 360 --degraded-ok`，
但脚本 stdout 为空、退出码 0，无任何输出。

## 根因
脚本内常量路径存在历史拼写错误（`interopertion` 少了一个 `c`）：

| 常量 | 原值（错误） | 实际存在文件 |
|------|------------|------------|
| STATE | `memory/interopertion_state.json` | `memory/interoception_state.json` ✅ |
| LIVE_LOG | `memory/interopertion_liveness_alerts.jsonl` | `memory/interoception_liveness_alerts.jsonl` ✅ |
| LAST | `memory/interopertion_liveness_last.json` | `memory/interoception_liveness_last.json` ✅ |

后果链条：
- 读不到 STATE → 每轮都判 `missing`
- LAST 落在错误路径、无历史签名 → 边沿触发失效（反复打印）
- 8 月前的 401 条告警全部写进错误的 `interopertion_liveness_alerts.jsonl`（51KB），
  其中大量 `stale`/`missing` 是**误报**，并非真实监控死亡

## 修复
- 备份：`backup/interoception_liveness.py.bak_20260924`
- 3 处常量路径 `interopertion_*` → `interoception_*`
- 提示文案同步修正，头部注释加 v1.3 说明

## 验证
```
python src/interoception_liveness.py --stale-min 360 --degraded-ok
✅ TU-8 监测存活正常 @ 2026-09-24 20:18:50
```
真实状态文件 `memory/interoception_state.json`（20:17:47 写入）`status=ok`，
`big_ctx_sessions=44`、`abort_rate=0.1688`、`body_posture=nominal`，新鲜度正常。

## 遗留
- `memory/interopertion_*` 系列为孤儿误报文件（含 401 条历史误报），可择机归档，未自行删除。
- 若存在引用 `interopertion_liveness_alerts.jsonl` 的其他监控/看板，需同步改指向（本次未发现 src 内引用）。
