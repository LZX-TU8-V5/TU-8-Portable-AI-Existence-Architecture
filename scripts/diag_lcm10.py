import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# schema
cur.execute("PRAGMA table_info(summaries)")
cols = [(c[1], c[2]) for c in cur.fetchall()]
print("Summaries columns:", cols)

print("\n=== Conv=5 summaries ===")
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
print(f"  count: {cur.fetchone()[0]}")
cur.execute('SELECT summary_text, depth FROM summaries WHERE conversation_id=5 ORDER BY rowid')
for r in cur.fetchall():
    print(f"  depth={r[1]}: {str(r[0])[:80]}...")

print("\n=== Conv=5 telemetry (最新) ===")
cur.execute('SELECT cache_state, consecutive_cold_observations, turns_since_leaf_compaction, last_leaf_compaction_at FROM conversation_compaction_telemetry WHERE conversation_id=5')
row = cur.fetchone()
if row:
    print(f"  cache_state: {row[0]}")
    print(f"  cold_obs: {row[1]}")
    print(f"  turns_since_leaf: {row[2]}")
    print(f"  last_leaf_at: {row[3]}")

print("\n=== Conv=5 messages ===")
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=5')
print(f"  count: {cur.fetchone()[0]}")

conn.close()
print("\n[OK]")
