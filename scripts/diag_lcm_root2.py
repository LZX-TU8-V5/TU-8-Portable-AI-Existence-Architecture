import sqlite3, json, os
db = r'C:\Users\qq366410837\.qclaw\memory\lossless\lcm.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# Check summaries for conv=5
cur.execute("SELECT summary_id, kind, depth, token_count FROM summaries WHERE conversation_id=5")
rows = cur.fetchall()
print(f"Summaries for conv=5: {len(rows)}")

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

# Check if there's a way to see what lossless-claw is doing
# Look at the plugin_state table
try:
    cur.execute("SELECT * FROM plugin_state LIMIT 10")
    rows = cur.fetchall()
    cols_p = [c[1] for c in conn.execute('PRAGMA table_info(plugin_state)').fetchall()]
    print(f"\nPlugin state: {len(rows)} rows")
    for r in rows:
        print(f"  {dict(zip(cols_p, r))}")
except Exception as e:
    print(f"plugin_state error: {e}")

conn.close()

# Also check the lossless-claw config
print("\n=== Lossless-claw config ===")
config_path = r'C:\Users\qq366410837\.qclaw\openclaw.json'
with open(config_path, encoding='utf-8') as f:
    import json as j
    data = j.load(f)
plugins = data.get('plugins', {})
lc = plugins.get('entries', {}).get('lossless-claw', {})
print(f"Lossless-claw config: {j.dumps(lc, indent=2, ensure_ascii=False)}")
