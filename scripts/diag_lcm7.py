import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

print("=== Conv=5 状态 ===")
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
s5 = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=5')
m5 = cur.fetchone()[0]
cur.execute('SELECT turns_since_leaf_compaction, cold_obs FROM conversation_compaction_telemetry WHERE conversation_id=5')
row = cur.fetchone()
turns = row[0] if row else 'N/A'
cold_obs = row[1] if row else 'N/A'
print(f"  msgs={m5}, summaries={s5}, turns_since_leaf={turns}, cold_obs={cold_obs}")

print("\n=== 最新会话 ===")
cur.execute('SELECT id, session_id FROM conversations ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(f"  id={r[0]}: {r[1]}")

print("\n=== Conv=4 状态 ===")
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=4')
s4 = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=4')
m4 = cur.fetchone()[0]
cur.execute('SELECT turns_since_leaf_compaction FROM conversation_compaction_telemetry WHERE conversation_id=4')
row4 = cur.fetchone()
turns4 = row4[0] if row4 else 'N/A'
print(f"  msgs={m4}, summaries={s4}, turns_since_leaf={turns4}")

conn.close()
print("\n[OK]")
