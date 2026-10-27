# LCM Compaction 问题修改记录

## 问题 ID
LCM-COMPACTION-2026-06-30

## 日期
2026-06-30

## 影响范围
- 主会话（conv=5, session-1782812694010-4yw4ks）
- 所有使用 LCM 的会话

## 问题等级
P2（功能受限，但会话可用）

## 根因
LCM auto-compaction 在压缩会话时，生成的 summary 未正确关联源消息（每个 summary 只有 1 个 context_item，应为 N 条）。导致后续压缩失败，报 "Auto-compaction could not recover" 警告。

## 修复步骤

### 1. 诊断（18:00-18:10）
- 检查 LCM DB 状态（conv=5: 175 messages, 2 summaries, 每个 summary 只有 1 context_item）
- 确认根因：summary 创建时未正确写入 context_items

### 2. 修复（18:12）
运行修复脚本：
```bash
python scripts/lcm_reset_compaction.py
```

脚本功能：
- 删除 conv=5 的所有 summaries
- 删除 conv=5 的所有 context_items
- 重置 compaction telemetry

### 3. 验证（18:13）
```bash
python -c "
import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
print('Summaries for conv=5:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM context_items WHERE conversation_id=5')
print('Context items for conv=5:', cur.fetchone()[0])
cur.execute('SELECT turns_since_leaf_compaction FROM conversation_compaction_telemetry WHERE conversation_id=5')
row = cur.fetchone()
print('Turns since leaf compaction:', row[0] if row else 'N/A')
conn.close()
"
```

预期输出：
```
Summaries for conv=5: 0
Context items for conv=5: 186
Turns since leaf compaction: 1
```

## 待验证
- [ ] 在主会话里发消息，观察是否还有 compaction 警告
- [ ] 检查 LCM 是否能正常生成 summary 并关联消息
- [ ] 如果再次失败，检查 OpenClaw 日志获取详细错误

## 相关文件
- 修复脚本: `scripts/lcm_reset_compaction.py`
- 根因记录: `memory/2026-06-30_LCM_ROOT_CAUSE.md`
- 详细日志: `memory/2026-06-30.md`
- LCM DB: `memory/lossless/lcm.db`

## 后续跟进
如果问题再次出现，需要：
1. 检查 lossless-claw 插件的压缩逻辑（为什么 summary 未正确关联消息）
2. 检查 summarization 模型是否正常工作
3. 考虑修改 lossless-claw 配置（提高 leafMinFanout 或降低 contextThreshold）

---
更新时间：2026-06-30 18:15
