#!/usr/bin/env python3
"""
LCM 手动压缩：手动创建第一个有效的 summary，并正确关联所有源消息
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

if summary_cnt > 0:
    print("已有 summary，无需注入。退出。")
    conn.close()
    exit(0)

# 2. 取前 30 条消息作为第一个 summary 的源（减少量，提高成功率）
cur.execute("""
    SELECT message_id, role, content, token_count
    FROM messages 
    WHERE conversation_id=5 
    ORDER BY message_id 
    LIMIT 30
""")
source_msgs = cur.fetchall()
print(f"将压缩 {len(source_msgs)} 条消息为第一个 summary")

# 3. 构造 summary 内容（简化版，避免 JSON 解析错误）
summary_lines = []
for m in source_msgs:
    role = m['role']
    content = m['content'] or ''
    # 简单截断
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
print('[OK] Inserted summary:', summary_id)

# 7. 写入 context_items（关键步骤：为每个源消息创建一条记录）
ordinal = 0
for m in source_msgs:
    ordinal += 1
    cur.execute("""
        INSERT INTO context_items (conversation_id, ordinal, item_type, message_id, summary_id, created_at)
        VALUES (5, ?, 'message', ?, ?, ?)
    """, (ordinal, m['message_id'], summary_id, now))

print('[OK] Inserted', ordinal, 'context_items')

# 8. 更新 compaction telemetry
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
print('[OK] Manual compaction complete!')
print(f"   Summary: {summary_id}")
print(f"   压缩了 {len(source_msgs)} 条消息")
print(f"   写入了 {ordinal} 条 context_items")
print(f"   更新了 compaction telemetry")
print()
print("现在 LCM 有了一个有效的 summary，应该能正常触发后续压缩。")
print("请重启 OpenClaw 或等待下一次自动压缩。")

conn.close()
