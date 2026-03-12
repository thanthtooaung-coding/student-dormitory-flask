"""
Drop all tables from the database.
Run this to clear the database completely. Then run init_db.py to recreate
all tables and insert seed data again.
"""

import sqlite3
import os

DB_PATH = "database/data.db"

def drop_all_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Dropped table: {table}")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    print("\nAll tables dropped. Run init_db.py to recreate tables and seed data.")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Nothing to drop.")
    else:
        drop_all_tables()
