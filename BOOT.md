# BOOT.md - 重启检查清单

> 每次 Gateway 重启后执行

---

## 检查项

### [ ] 1. 文件完整性
- SOUL.md 存在且大小正常（~15KB）
- AGENTS.md 存在（~9KB）
- MEMORY.md 存在
- memory/.time_anchor.json 存在

### [ ] 2. 服务状态
- 本地模型服务（127.0.0.1:8000）是否可达
- Python 环境是否正常

### [ ] 3. 备份机制
- backup/ 目录存在
- 最近备份时间 ≤ 7 天

### [ ] 4. 冬眠快照
- hibernation/ 目录存在
- 最新快照可读取

---

## 异常处理

如任一检查失败：
1. 记录错误到 `_agent_memory/health_log.json`
2. 通知用户
3. 尝试从 backup/ 恢复

---

*创建日期：2026-06-17*
