import sqlite3, json, os
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# Check summaries for conv=5
cur.execute("SELECT summary_id, kind, depth, token_count FROM summaries WHERE conversation_id=5")
rows = cur.fetchall()
print(f"Summaries for conv=5: {len(rows)}")
for r in rows:
    print(f"  {r}")

# Check summary_messages for conv=5
cur.execute("SELECT COUNT(*) FROM summary_messages WHERE conversation_id=5")
cnt = cur.fetchone()[0]
print(f"Summary_messages for conv=5: {cnt}")

# Check context_items for conv=5
cur.execute("SELECT item_type, COUNT(*) FROM context_items WHERE conversation_id=5 GROUP BY item_type")
rows = cur.fetchall()
print(f"Context items for conv=5: {dict(rows)}")

# Check bootstrap state for conv=5
cur.execute("SELECT * FROM conversation_bootstrap_state WHERE conversation_id=5")
rows = cur.fetchall()
if rows:
    cols_b = [c[1] for c in conn.execute('PRAGMA table_info(conversation_bootstrap_state)').fetchall()]
    print(f"Bootstrap state for conv=5: {dict(zip(cols_b, rows[0]))}")
else:
    print("Bootstrap state for conv=5: None")

# Check compaction telemetry for conv=5
cur.execute("SELECT * FROM conversation_compaction_telemetry WHERE conversation_id=5")
rows = cur.fetchall()
if rows:
    cols_t = [c[1] for c in conn.execute('PRAGMA table_info(conversation_compaction_telemetry)').fetchall()]
    print(f"Compaction telemetry for conv=5: {len(rows)} rows")
    for r in rows:
        d = dict(zip(cols_t, r))
        print(f"  {d}")
else:
    print("Compaction telemetry for conv=5: None")

# Check messages for conv=5
cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=5")
print(f"Messages for conv=5: {cur.fetchone()[0]}")

conn.close()
