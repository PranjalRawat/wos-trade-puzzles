import sqlite3
import os

db_path = "puzzle_bot.db"

if os.path.exists(db_path):
    print(f"Migrating database: {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create scan_details table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            scene TEXT NOT NULL,
            slot_index INTEGER NOT NULL,
            added_duplicates INTEGER DEFAULT 0,
            FOREIGN KEY (scan_id) REFERENCES scan_history(id) ON DELETE CASCADE
        )
        """)
        
        # Create index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_details_scan ON scan_details(scan_id)")
        
        conn.commit()
        print("Migration successful: Added scan_details table.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()
else:
    print(f"Database {db_path} not found. Schema will be initialized on first run.")
