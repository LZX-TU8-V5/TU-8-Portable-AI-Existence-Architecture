import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# schema
cur.execute("PRAGMA table_info(conversations)")
cols = [(c[1], c[2]) for c in cur.fetchall()]
print("Conversations columns:", cols)

print("\n=== 最新会话 ===")
cur.execute('SELECT * FROM conversations ORDER BY rowid DESC LIMIT 5')
for r in cur.fetchall():
    print(f"  {r}")

print("\n=== Conv=5 summaries ===")
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
print(f"  count: {cur.fetchone()[0]}")
cur.execute('SELECT id, summary_text, depth FROM summaries WHERE conversation_id=5 ORDER BY id')
for r in cur.fetchall():
    print(f"  id={r[0]}, depth={r[2]}: {r[1][:80] if r[1] else None}...")

print("\n=== Conv=5 messages ===")
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=5')
print(f"  count: {cur.fetchone()[0]}")

conn.close()
print("\n[OK]")
