# LCM Compaction Bug 修复记录

## Bug ID
LOSSLESS-CLAW-COMPACTION-BUG-2026-06-30

## 状态
✅ 已修复（临时方案）

## 根因
lossless-claw 插件在压缩会话时，试图在 `context_items` 表里同时设置 `message_id` 和 `summary_id`，违反了表的 CHECK 约束：
- `item_type='message'` → `message_id IS NOT NULL AND summary_id IS NULL`
- `item_type='summary'` → `summary_id IS NOT NULL AND message_id IS NULL`

导致压缩失败，报 "Auto-compaction could not recover" 警告。

## 修复方案（临时）
运行 `scripts/lcm_fix_v3.py`：
1. 删除 conv=5 的所有 summaries 和 context_items
2. 重新构建 context_items：为每条消息创建 `item_type='message'` 的记录
3. 重置 compaction telemetry

**注意**：这是临时方案。根本修复需要修改 lossless-claw 插件的压缩逻辑。

## 验证（2026-06-30 18:30）
- ✅ conv=5 有 6 个 summaries
- ✅ context_items 结构正确（ordinal 0~5: summaries, ordinal 6~: messages）
- ✅ 无 compaction 警告

## 根本修复建议
需要修改 lossless-claw 插件的源码（`compaction.ts`），确保：
1. 创建 summary 后，正确更新 context_items（删除源消息的 item_type='message' 记录，插入 item_type='summary' 记录）
2. 不违反 CHECK 约束

## 相关文件
- 修复脚本: `scripts/lcm_fix_v3.py`
- 详细诊断: `memory/2026-06-30.md`
- 根因记录: `memory/LCM_COMPACTION_FIX.md`
- LCM DB: `memory/lossless/lcm.db`

## 报告给 OpenClaw
建议向 OpenClaw 报告此 bug，附上：
1. 错误日志（CHECK constraint failed）
2. 修复脚本（临时方案）
3. 根本修复建议

---
更新时间：2026-06-30 18:35
