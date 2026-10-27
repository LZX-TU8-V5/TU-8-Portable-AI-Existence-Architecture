import sqlite3
import json

db_path = r"C:\Users\qq366410837\.qclaw\memory\main.sqlite"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check meta table
print("=== META ===")
cur.execute("SELECT * FROM meta")
for row in cur.fetchall():
    print(row)

# Check files table - what files are tracked
print("\n=== FILES (tracked) ===")
cur.execute("SELECT path, source, size FROM files ORDER BY path")
for row in cur.fetchall():
    print(f"  {row[1]:10s} | {row[2]:6d} | {row[0]}")

# Sample chunks
print("\n=== CHUNKS (sample 5) ===")
cur.execute("SELECT id, path, source, start_line, end_line, model, LENGTH(text), LENGTH(embedding) FROM chunks LIMIT 5")
for row in cur.fetchall():
    print(f"  id={row[0][:20]}... path={row[1][:40]} src={row[2]} L{row[3]}-{row[4]} model={row[5]} text_len={row[6]} emb_len={row[7]}")

# Check the lossless LCM database too
print("\n=== LCM DB ===")
lcm_path = r"C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db"
conn2 = sqlite3.connect(lcm_path)
cur2 = conn2.cursor()
cur2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = cur2.fetchall()
for t in tables2:
    print(f"  Table: {t[0]}")
    cur2.execute(f'SELECT sql FROM sqlite_master WHERE name="{t[0]}"')
    schema = cur2.fetchone()
    if schema:
        print(f"    {schema[0][:300]}")
    try:
        cur2.execute(f'SELECT COUNT(*) FROM "{t[0]}"')
        count = cur2.fetchone()[0]
        print(f"    Rows: {count}")
    except:
        pass

conn.close()
conn2.close()
