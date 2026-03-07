"""
Script to add or update a dorm manager with email and password
Run this script to add a manager account to the database
"""

import sqlite3
from db import get_db_connection

def add_manager(manager_id, name, email, password, phone_number=None, line_id=None):
    """Add or update a dorm manager"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO dorm_managers 
            (manager_id, name, email, password, phone_number, line_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (manager_id, name, email, password, phone_number, line_id))
        
        conn.commit()
        print(f"Manager '{name}' added/updated successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error adding manager: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Add default manager
    add_manager(
        manager_id='MGR001',
        name='Dorm Manager',
        email='manager@kmitl.ac.th',
        password='manager123',
        phone_number='02-XXX-XXXX',
        line_id='@dormmanager'
    )
