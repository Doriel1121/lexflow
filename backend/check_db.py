import sqlite3
import os

db_path = "c:/my projects/ai-lawyer/backend/lexflow.db"

if not os.path.exists(db_path):
    print(f"Database file not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Users table columns: {columns}")
        if "role" in columns:
            print("Role column EXISTS")
        else:
            print("Role column MISSING")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
