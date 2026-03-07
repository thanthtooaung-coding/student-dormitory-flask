"""
Database Migration Script
This script updates existing database tables to match the current schema.
It adds missing columns without affecting existing data.
"""

import sqlite3
import os

def get_table_schema():
    """Returns the expected schema for all tables"""
    return {
        'students': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'TEXT UNIQUE NOT NULL'),
                ('name', 'TEXT NOT NULL'),
                ('email', 'TEXT UNIQUE NOT NULL'),
                ('password', 'TEXT NOT NULL'),
                ('faculty', 'TEXT'),
                ('major', 'TEXT')
            ]
        },
        'dorm_managers': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('manager_id', 'TEXT UNIQUE NOT NULL'),
                ('name', 'TEXT NOT NULL'),
                ('phone_number', 'TEXT'),
                ('line_id', 'TEXT')
            ]
        },
        'hostels': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('name', 'TEXT NOT NULL'),
                ('location', 'TEXT NOT NULL'),
                ('distance_from_campus', 'REAL'),
                ('rating', 'REAL')
            ]
        },
        'rooms': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('hostel_id', 'INTEGER NOT NULL'),
                ('room_type', 'TEXT NOT NULL'),
                ('price', 'REAL NOT NULL'),
                ('facilities', 'TEXT'),
                ('available', 'INTEGER DEFAULT 1')
            ]
        },
        'bookings': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('room_id', 'INTEGER NOT NULL'),
                ('checkin_date', 'TEXT NOT NULL'),
                ('booking_status', 'TEXT DEFAULT \'pending\'')
            ]
        },
        'payments': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('booking_id', 'INTEGER'),
                ('amount', 'REAL NOT NULL'),
                ('payment_method', 'TEXT NOT NULL'),
                ('payment_status', 'TEXT DEFAULT \'pending\'')
            ]
        },
        'bills': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('type', 'TEXT NOT NULL'),
                ('amount', 'REAL NOT NULL'),
                ('due_date', 'TEXT NOT NULL'),
                ('status', 'TEXT DEFAULT \'pending\'')
            ]
        },
        'parcels': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('sender', 'TEXT NOT NULL'),
                ('arrival_date', 'TEXT NOT NULL'),
                ('status', 'TEXT DEFAULT \'pending\'')
            ]
        },
        'facility_bookings': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('facility_name', 'TEXT NOT NULL'),
                ('booking_date', 'TEXT NOT NULL')
            ]
        },
        'repair_requests': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('issue_type', 'TEXT NOT NULL'),
                ('description', 'TEXT NOT NULL'),
                ('status', 'TEXT DEFAULT \'pending\''),
                ('report_date', 'TEXT')
            ]
        },
        'visitors': {
            'columns': [
                ('id', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
                ('student_id', 'INTEGER NOT NULL'),
                ('visitor_name', 'TEXT NOT NULL'),
                ('visit_date', 'TEXT NOT NULL'),
                ('visit_time', 'TEXT NOT NULL')
            ]
        }
    }

def get_existing_columns(cursor, table_name):
    """Get list of existing columns in a table"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]  # Column name is at index 1
    except sqlite3.OperationalError:
        return []  # Table doesn't exist

def add_missing_columns(cursor, table_name, expected_columns):
    """Add missing columns to a table"""
    existing_columns = get_existing_columns(cursor, table_name)
    added_count = 0
    
    for col_name, col_def in expected_columns:
        # Skip PRIMARY KEY columns (they should already exist)
        if 'PRIMARY KEY' in col_def.upper():
            continue
            
        if col_name not in existing_columns:
            try:
                # Extract just the data type for ALTER TABLE
                # Remove constraints that can't be added with ALTER TABLE
                col_type = col_def.split()[0]  # Get the base type (TEXT, INTEGER, REAL)
                
                # Handle DEFAULT values
                if 'DEFAULT' in col_def.upper():
                    default_value = col_def.split('DEFAULT')[1].strip().strip("'")
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} DEFAULT '{default_value}'"
                else:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                
                cursor.execute(alter_sql)
                print(f"  [+] Added column '{col_name}' to table '{table_name}'")
                added_count += 1
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"  [-] Column '{col_name}' already exists in '{table_name}'")
                else:
                    print(f"  [X] Error adding column '{col_name}' to '{table_name}': {e}")
    
    return added_count

def migrate_database():
    """Main migration function"""
    db_path = "database/data.db"
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        print("Please run init_db.py first to create the database.")
        return
    
    print("Starting database migration...")
    print("=" * 50)
    
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    schema = get_table_schema()
    total_added = 0
    
    for table_name, table_info in schema.items():
        print(f"\nChecking table: {table_name}")
        
        # Check if table exists
        existing_columns = get_existing_columns(cursor, table_name)
        
        if not existing_columns:
            print(f"  [!] Table '{table_name}' does not exist. Run init_db.py to create it.")
            continue
        
        # Add missing columns
        added = add_missing_columns(cursor, table_name, table_info['columns'])
        total_added += added
        
        if added == 0:
            print(f"  [OK] Table '{table_name}' is up to date")
    
    connection.commit()
    connection.close()
    
    print("\n" + "=" * 50)
    print(f"Migration completed! Added {total_added} column(s) across all tables.")
    print("=" * 50)

if __name__ == "__main__":
    migrate_database()
