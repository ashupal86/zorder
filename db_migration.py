import sqlite3
import os
from datetime import datetime

def migrate_database():
    """
    Add updated_at column to orders table for existing databases
    """
    # Get database path - modify this to match your actual database path
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'digital_waiter.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if updated_at column exists
    cursor.execute('PRAGMA table_info("order")')
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'updated_at' not in columns:
        print("Adding updated_at column to orders table...")
        
        # Add the column
        cursor.execute("ALTER TABLE `order` ADD COLUMN updated_at TIMESTAMP")
        
        # Update existing records to set updated_at to same as created_at
        cursor.execute("UPDATE `order` SET updated_at = created_at")
        
        conn.commit()
        print("Migration complete. updated_at column added and populated.")
    else:
        print("updated_at column already exists in orders table.")
    
    conn.close()

if __name__ == "__main__":
    migrate_database() 