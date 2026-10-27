import sqlite3
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# schema
cur.execute("PRAGMA table_info(conversation_compaction_telemetry)")
cols = [(c[1], c[2]) for c in cur.fetchall()]
print("Compaction telemetry columns:", cols)

print("\n=== Conv=5 状态 ===")
cur.execute('SELECT COUNT(*) FROM summaries WHERE conversation_id=5')
s5 = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=5')
m5 = cur.fetchone()[0]
cur.execute('SELECT * FROM conversation_compaction_telemetry WHERE conversation_id=5')
row = cur.fetchone()
if row:
    print(f"  cols: {cols}")
    print(f"  row:  {row}")
else:
    print("  无 telemetry 记录")

print("\n=== 最新会话 ===")
cur.execute('SELECT id, session_id FROM conversations ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(f"  id={r[0]}: {r[1]}")

conn.close()
print("\n[OK]")
