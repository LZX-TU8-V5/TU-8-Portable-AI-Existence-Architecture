import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

print("=== Conv=5 状态总览 ===")
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=5')
m5 = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
s5 = cur.fetchone()[0]
print(f"  消息数: {m5}")
print(f"  summaries数: {s5}")

cur.execute('SELECT cache_state, consecutive_cold_observations, turns_since_leaf_compaction, last_leaf_compaction_at, tokens_accumulated_since_leaf_compaction FROM conversation_compaction_telemetry WHERE conversation_id=5')
row = cur.fetchone()
if row:
    print(f"  cache_state: {row[0]}")
    print(f"  cold_obs: {row[1]}")
    print(f"  turns_since_leaf: {row[2]}")
    print(f"  last_leaf_at: {row[3]}")
    print(f"  tokens_accumulated: {row[4]}")

print("\n=== Conv=5 Summaries ===")
cur.execute('SELECT content, depth, kind FROM summaries WHERE conversation_id=5 ORDER BY created_at')
for r in cur.fetchall():
    print(f"  [{r[2]}] depth={r[1]}: {str(r[0])[:100]}...")

conn.close()
print("\n[OK]")
