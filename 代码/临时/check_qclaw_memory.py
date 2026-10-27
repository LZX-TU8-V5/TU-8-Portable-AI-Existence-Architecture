import sqlite3
import sys

db_path = r"C:\Users\qq366410837\.qclaw\memory\main.sqlite"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("=== Tables ===")
for t in tables:
    print(f"\n--- {t[0]} ---")
    cur.execute(f'SELECT sql FROM sqlite_master WHERE name="{t[0]}"')
    schema = cur.fetchone()
    if schema:
        print(schema[0][:800])
    # Show row count
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{t[0]}"')
        count = cur.fetchone()[0]
        print(f"  Rows: {count}")
    except:
        pass

conn.close()
