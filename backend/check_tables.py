import sqlite3
conn = sqlite3.connect('lexflow.db')

# Check organisations table schema
print('=== organisations table schema ===')
cols = conn.execute("PRAGMA table_info(organisations)").fetchall()
for col in cols:
    print(f"  {col[1]:20s} {col[2]:15s} not_null={col[3]} default={col[4]}")

# Check alembic version
version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
print(f"\n=== Alembic version: {version[0]} ===")
conn.close()
