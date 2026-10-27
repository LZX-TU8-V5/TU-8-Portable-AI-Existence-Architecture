#!/usr/bin/env python3
"""
LCM 死锁修复：给 conv=5 注入第一个 summary，打破"0 summary → 无法压缩 → 永远0 summary"循环

DB schema (已验证):
- messages(message_id, conversation_id, seq, role, content, token_count, ...)
- summaries(summary_id, conversation_id, kind, depth, content, token_count, earliest_at, latest_at, ...)
- context_items(conversation_id, ordinal, item_type, message_id, summary_id, ...)
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
cur.execute("SELECT MIN(message_id), MAX(message_id) FROM messages WHERE conversation_id=5")
row = cur.fetchone()
min_id, max_id = row[0], row[1]
print(f"conv=5: {msg_cnt} messages, {summary_cnt} summaries, message_id range: {min_id}-{max_id}")

if summary_cnt > 0:
    print("✅ 已有 summary，无需注入。退出。")
    conn.close()
    exit(0)

# 2. 取前 60 条消息作为第一个 summary 的源
cur.execute("""
    SELECT message_id, role, content, token_count
    FROM messages 
    WHERE conversation_id=5 
    ORDER BY message_id 
    LIMIT 60
""")
source_msgs = cur.fetchall()
print(f"将压缩 {len(source_msgs)} 条消息为第一个 summary")

# 3. 构造 summary 内容
summary_lines = []
for m in source_msgs:
    role = m['role']
    content = m['content'] or ''
    # 尝试提取纯文本
    try:
        c = json.loads(content) if content.startswith('[') or content.startswith('{') else content
        if isinstance(c, list):
            texts = [p.get('text','') for p in c if isinstance(p, dict) and p.get('type')=='text']
            content = '\n'.join(texts)
        elif isinstance(c, dict):
            content = c.get('text','')
    except:
        pass
    summary_lines.append(f"[{role}] {str(content)[:300]}")

summary_content = (
    f"[自动生成的初始摘要 — conv=5 第一批 {len(source_msgs)} 条消息]\n"
    f"时间范围: message_id {source_msgs[0]['message_id']} ~ {source_msgs[-1]['message_id']}\n\n"
    + "\n\n".join(summary_lines)
)
summary_id = "sum_" + hashlib.sha256(f"{summary_content}{datetime.now().timestamp()}".encode()).hexdigest()[:16]

# 4. 计算 token_count
total_tokens = sum(m['token_count'] or 100 for m in source_msgs)
summary_token_count = max(500, len(summary_content) // 4)

# 5. 写入 summary
now = datetime.now(timezone.utc).isoformat()
earliest = now  # 简化：用当前时间
latest = now

cur.execute("""
    INSERT INTO summaries (
        summary_id, conversation_id, kind, depth, 
        content, token_count, 
        earliest_at, latest_at,
        descendant_count, descendant_token_count,
        source_message_token_count,
        file_ids, model,
        created_at
    ) VALUES (?, 5, 'leaf', 0, ?, ?, ?, ?, 0, 0, ?, '[]', 'lossless-claw', ?)
""", (
    summary_id,
    summary_content,
    summary_token_count,
    earliest, latest,
    total_tokens,
    now
))
print(f"✅ 已插入 summary: {summary_id}")

# 6. 写入 context_items（把源消息标记为已压缩）
ordinal = 0
for m in source_msgs:
    ordinal += 1
    cur.execute("""
        INSERT INTO context_items (conversation_id, ordinal, item_type, message_id, summary_id, created_at)
        VALUES (5, ?, 'message', ?, ?, ?)
    """, (ordinal, m['message_id'], summary_id, now))

# 7. 更新 compaction telemetry
cur.execute("""
    UPDATE conversation_compaction_telemetry 
    SET last_leaf_compaction_at = ?,
        turns_since_leaf_compaction = 0,
        tokens_accumulated_since_leaf_compaction = 0
    WHERE conversation_id = 5
""", (now,))

if cur.rowcount == 0:
    # 如果没有记录，插入一条
    cur.execute("""
        INSERT INTO conversation_compaction_telemetry (
            conversation_id, cache_state, consecutive_cold_observations,
            turns_since_leaf_compaction, tokens_accumulated_since_leaf_compaction,
            last_activity_band, last_api_call_at, last_cache_touch_at,
            provider, model, updated_at
        ) VALUES (5, 'cold', 0, 0, 0, 'low', ?, ?, 'qclaw', 'modelroute', ?)
    """, (now, now, now))

conn.commit()
print(f"✅ 注入完成。")
print(f"   Summary: {summary_id}")
print(f"   标记了 {len(source_msgs)} 条消息为已压缩（context_items）")
print(f"   更新了 compaction_telemetry")
print()
print("现在 LCM 有了第一个 summary，应该能正常触发后续压缩。")
print("请重启 OpenClaw 或等待下一次自动压缩。")

conn.close()
