"""
迁移 knowledge_graph.db，添加缺少的列
"""
import sqlite3

db_path = r"C:\Users\qq366410837\.qclaw\workspace\knowledge_graph.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查并添加缺少的列
missing_columns = {
    "rationale": "TEXT NOT NULL DEFAULT ''",
    "embedding": "BLOB",  # 注意：这个列已经存在，不需要添加
}

# 获取当前列
cursor.execute("PRAGMA table_info(events)")
existing_columns = {row[1] for row in cursor.fetchall()}

print(f"Existing columns: {existing_columns}")

# 添加缺少的列
for col_name, col_def in missing_columns.items():
    if col_name not in existing_columns:
        try:
            sql = f"ALTER TABLE events ADD COLUMN {col_name} {col_def}"
            print(f"Executing: {sql}")
            cursor.execute(sql)
            conn.commit()
            print(f"✅ Added column: {col_name}")
        except Exception as e:
            print(f"❌ Failed to add column {col_name}: {e}")

# 验证
cursor.execute("PRAGMA table_info(events)")
updated_columns = {row[1] for row in cursor.fetchall()}
print(f"\nUpdated columns: {updated_columns}")

# 创建索引（如果不存在）
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_rationale ON events(rationale) WHERE rationale != ''")
    conn.commit()
    print("✅ Created index: idx_events_rationale")
except Exception as e:
    print(f"❌ Failed to create index: {e}")

conn.close()
print("\n✅ Migration completed!")
