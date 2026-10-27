#!/usr/bin/env python3
"""
LCM 修复：删除无效的 summary 和 context_items，让 LCM 重新压缩
"""
import sqlite3
from datetime import datetime, timezone

db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# 1. 删除 conv=5 的所有 summary
cur.execute("DELETE FROM summaries WHERE conversation_id=5")
deleted_summaries = cur.rowcount
print(f"Deleted {deleted_summaries} summaries")

# 2. 删除 conv=5 的所有 context_items
cur.execute("DELETE FROM context_items WHERE conversation_id=5")
deleted_items = cur.rowcount
print(f"Deleted {deleted_items} context_items")

# 3. 重置 compaction telemetry
now = datetime.now(timezone.utc).isoformat()
cur.execute("""
    UPDATE conversation_compaction_telemetry 
    SET last_leaf_compaction_at = NULL,
        turns_since_leaf_compaction = 0,
        tokens_accumulated_since_leaf_compaction = 0,
        updated_at = ?
    WHERE conversation_id = 5
""", (now,))

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
print(f"✅ 重置完成。")
print(f"   Deleted {deleted_summaries} summaries")
print(f"   Deleted {deleted_items} context_items")
print(f"   Reset compaction telemetry")
print()
print("LCM 将在下一次触发时重新压缩 conv=5 的所有消息。")
print("如果压缩再次失败，请检查 OpenClaw 日志以获取详细错误。")

conn.close()
