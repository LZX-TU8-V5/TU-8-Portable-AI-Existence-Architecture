#!/usr/bin/env python3
"""
LCM 修复 v3：删除无效的 summary，手动构建正确的 context_items

正确做法：
1. 删除所有 summaries 和 context_items
2. 重新构建 context_items：所有消息都是 item_type='message'
3. 让 LCM 从头开始压缩（这次应该能正常工作，因为 context_items 是干净的）
"""
import sqlite3
from datetime import datetime, timezone

db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. 删除 conv=5 的所有 summaries
cur.execute("DELETE FROM summaries WHERE conversation_id=5")
deleted_summaries = cur.rowcount
print("Deleted", deleted_summaries, "summaries")

# 2. 删除 conv=5 的所有 context_items
cur.execute("DELETE FROM context_items WHERE conversation_id=5")
deleted_items = cur.rowcount
print("Deleted", deleted_items, "context_items")

# 3. 重新构建 context_items：为每条消息创建一个 item_type='message' 的记录
cur.execute("SELECT message_id FROM messages WHERE conversation_id=5 ORDER BY message_id")
message_ids = [r[0] for r in cur.fetchall()]
print("Rebuilding context_items for", len(message_ids), "messages")

now = datetime.now(timezone.utc).isoformat()
ordinal = 0
for mid in message_ids:
    ordinal += 1
    cur.execute("""
        INSERT INTO context_items (conversation_id, ordinal, item_type, message_id, summary_id, created_at)
        VALUES (5, ?, 'message', ?, NULL, ?)
    """, (ordinal, mid, now))

print("[OK] Rebuilt", ordinal, "context_items (all type=message)")

# 4. 重置 compaction telemetry
cur.execute("""
    UPDATE conversation_compaction_telemetry 
    SET last_leaf_compaction_at = NULL,
        turns_since_leaf_compaction = 0,
        tokens_accumulated_since_leaf_compaction = 0,
        updated_at = ?
    WHERE conversation_id = 5
""", (now,))

conn.commit()
print("\n[OK] Reset complete.")
print("  Deleted", deleted_summaries, "summaries")
print("  Deleted", deleted_items, "old context_items")
print("  Rebuilt", ordinal, "new context_items (all type=message)")
print()
print("LCM should now be able to compress from a clean state.")
print("Try sending a message in the main session to trigger compaction.")

conn.close()
