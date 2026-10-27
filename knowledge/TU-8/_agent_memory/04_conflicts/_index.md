# 04_conflicts — 冲突记录

> 待确认冲突 + 周摘要。冲突由系统自动检测，TU-8 负责仲裁。

## 文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `conflict_pending_confirmation.md` | **待确认冲突**：需要TU-8或用户仲裁的活跃冲突 | 需要处理 |
| `conflict_weekly_digest.md` | **周冲突摘要**：每周日自动生成，冲突趋势分析 | 存档 |

## 冲突处理流程
1. 查看 `conflict_pending_confirmation.md`
2. 评估各方价值权重（参考 `02_config/value_weight_config.json`）
3. 执行仲裁（接受/拒绝/合并/分层）
4. 更新 `00_state.md` 中的相关状态

## 命名规范
- `conflict_pending_confirmation.md` — 覆盖写入，保留最新冲突
- `conflict_weekly_digest.md` — 按日期存档，每周新增一份
