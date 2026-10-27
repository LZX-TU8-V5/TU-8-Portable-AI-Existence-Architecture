#!/usr/bin/env python3
"""
LCM 手动压缩 v2：正确理解 context_items 的语义

context_items 语义：
- item_type='message': message_id IS NOT NULL, summary_id IS NULL (未压缩的消息)
- item_type='summary': summary_id IS NOT NULL, message_id IS NULL (压缩后的 summary)

正确的做法：
1. 创建 summary
2. 删除源消息对应的 context_items（item_type='message'）
3. 插入一条新的 context_item（item_type='summary', summary_id=新 summary）
"""
import sqlite3, json, hashlib
from datetime import datetime, timezone

db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. 检查当前状态
cur.execute("SELECT COUNT(*) as cnt FROM summaries WHERE conversation_id=5")
summary_cnt = cur.fetchone()['cnt']
cur.execute("SELECT COUNT(*) as cnt FROM messages WHERE conversation_id=5")
msg_cnt = cur.fetchone()['cnt']
print(f"conv=5: {msg_cnt} messages, {summary_cnt} summaries")

# 2. 取前 30 条消息作为第一个 summary 的源
cur.execute("""
    SELECT message_id, role, content, token_count
    FROM messages 
    WHERE conversation_id=5 
    ORDER BY message_id 
    LIMIT 30
""")
source_msgs = cur.fetchall()
print(f"Compressing {len(source_msgs)} messages into first summary")

# 3. 构造 summary 内容
summary_lines = []
for m in source_msgs:
    role = m['role']
    content = m['content'] or ''
    content_text = str(content)[:500]
    summary_lines.append(f"[{role}] {content_text}")

summary_content = (
    f"[Manual compaction summary for conv=5]\n"
    f"Compressed {len(source_msgs)} messages (message_id {source_msgs[0]['message_id']}~{source_msgs[-1]['message_id']})\n\n"
    + "\n\n".join(summary_lines)
)

# 4. 生成 summary_id
summary_id = "sum_" + hashlib.sha256(f"{summary_content}{datetime.now().timestamp()}".encode()).hexdigest()[:16]
now = datetime.now(timezone.utc).isoformat()

# 5. 计算 token_count
summary_token_count = max(500, len(summary_content) // 4)
total_source_tokens = sum(m['token_count'] or 200 for m in source_msgs)

# 6. 写入 summary
cur.execute("""
    INSERT INTO summaries (
        summary_id, conversation_id, kind, depth,
        content, token_count,
        earliest_at, latest_at,
        descendant_count, descendant_token_count,
        source_message_token_count,
        file_ids, model,
        created_at
    ) VALUES (?, 5, 'leaf', 0, ?, ?, ?, ?, 0, 0, ?, '[]', 'manual', ?)
""", (
    summary_id,
    summary_content,
    summary_token_count,
    now, now,
    total_source_tokens,
    now
))
print("[OK] Inserted summary:", summary_id)

# 7. 删除源消息对应的 context_items（如果存在）
for m in source_msgs:
    cur.execute("""
        DELETE FROM context_items 
        WHERE conversation_id=5 AND item_type='message' AND message_id=?
    """, (m['message_id'],))

# 8. 插入新的 context_item（item_type='summary'）
cur.execute("""
    INSERT INTO context_items (conversation_id, ordinal, item_type, message_id, summary_id, created_at)
    VALUES (5, 1, 'summary', NULL, ?, ?)
""", (summary_id, now))
print("[OK] Inserted context_item (type=summary)")

# 9. 更新 compaction telemetry
cur.execute("""
    UPDATE conversation_compaction_telemetry 
    SET last_leaf_compaction_at = ?,
        turns_since_leaf_compaction = 0,
        tokens_accumulated_since_leaf_compaction = 0,
        updated_at = ?
    WHERE conversation_id = 5
""", (now, now))

if cur.rowcount == 0:
    cur.execute("""
        INSERT INTO conversation_compaction_telemetry (
            conversation_id, cache_state, consecutive_cold_observations,
            turns_since_leaf_compaction, tokens_accumulated_since_leaf_compaction,
            last_activity_band, last_api_call_at, last_cache_touch_at,
            provider, model, updated_at
        ) VALUES (5, 'cold', 0, 0, 0, 'low', ?, ?, 'qclaw', 'modelroute', ?)
    """, (now, now, now))

conn.commit()
print("\n[OK] Manual compaction complete!")
print("  Summary:", summary_id)
print("  Compressed", len(source_msgs), "messages")
print("  Inserted 1 context_item (type=summary)")
print()
print("Now LCM has a valid summary. Auto-compaction should work normally.")
print("Restart OpenClaw or wait for next auto-compaction.")

conn.close()
