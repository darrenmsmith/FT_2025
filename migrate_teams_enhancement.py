#!/usr/bin/env python3
"""
Safe Database Migration Script for Team Management Enhancement
Adds sport, gender, season, coach_name, notes, and active fields to teams table
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime

# Configuration
DB_PATH = '/opt/data/field_trainer.db'

def backup_database():
    """Create timestamped backup of database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{DB_PATH}.backup_{timestamp}"

    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ Database backed up to: {backup_path}")

        # Verify backup
        test_conn = sqlite3.connect(backup_path)
        test_conn.execute("SELECT COUNT(*) FROM teams")
        test_conn.close()
        print(f"✓ Backup verified successfully")

        return backup_path
    except Exception as e:
        print(f"✗ Backup failed: {e}")
        sys.exit(1)

def check_column_exists(conn, table, column):
    """Check if column exists in table"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate_teams_table(conn):
    """Add new columns to teams table with transaction safety"""
    cursor = conn.cursor()

    columns_to_add = [
        ("sport", "VARCHAR(50)"),
        ("gender", "VARCHAR(20)"),
        ("season", "VARCHAR(50)"),
        ("active", "BOOLEAN DEFAULT 1"),
        ("coach_name", "VARCHAR(100)"),
        ("notes", "TEXT")
    ]

    # Start transaction
    cursor.execute("BEGIN TRANSACTION")

    try:
        added_count = 0
        for column_name, column_type in columns_to_add:
            if check_column_exists(conn, 'teams', column_name):
                print(f"  - Column '{column_name}' already exists")
                continue

            cursor.execute(f"ALTER TABLE teams ADD COLUMN {column_name} {column_type}")
            print(f"  ✓ Added column: {column_name}")
            added_count += 1

        # Commit transaction
        cursor.execute("COMMIT")
        print(f"✓ Teams table migration completed successfully ({added_count} columns added)")
        return True

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"✗ Migration failed and rolled back: {e}")
        raise

def verify_migration(conn):
    """Comprehensive migration verification"""
    print("\n=== Verifying Migration ===")
    cursor = conn.cursor()

    # Check teams columns
    cursor.execute("PRAGMA table_info(teams)")
    columns = [row[1] for row in cursor.fetchall()]

    required_columns = ['team_id', 'name', 'age_group', 'sport', 'gender',
                       'season', 'active', 'coach_name', 'notes',
                       'created_at', 'updated_at']

    all_good = True
    for col in required_columns:
        if col in columns:
            print(f"  ✓ Column '{col}' exists")
        else:
            print(f"  ✗ Column '{col}' MISSING")
            all_good = False

    # Check data integrity
    cursor.execute("SELECT COUNT(*) FROM teams")
    count = cursor.fetchone()[0]
    print(f"  ✓ Teams table contains {count} record(s)")

    # Check that existing teams still have their data
    cursor.execute("SELECT team_id, name, age_group FROM teams LIMIT 3")
    existing_teams = cursor.fetchall()
    if existing_teams:
        print(f"  ✓ Existing team data intact:")
        for team in existing_teams:
            print(f"    - {team[1]} (ID: {team[0][:8]}...)")

    return all_good

def main():
    """Main migration function with comprehensive safety checks"""
    print("="*60)
    print("Field Trainer Team Management Enhancement Migration")
    print("="*60)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH) / 1024:.2f} KB\n")

    # Step 1: Backup
    print("=== Step 1: Creating Backup ===")
    backup_path = backup_database()

    # Step 2: Run migration
    print("\n=== Step 2: Running Migration ===")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        migrate_teams_table(conn)
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"\n✗ MIGRATION FAILED: {e}")
        print(f"Database unchanged. Backup available at: {backup_path}")
        sys.exit(1)

    # Step 3: Verify
    print("\n=== Step 3: Verification ===")
    conn = sqlite3.connect(DB_PATH)
    success = verify_migration(conn)
    conn.close()

    # Final report
    print("\n" + "="*60)
    if success:
        print("✓ MIGRATION COMPLETED SUCCESSFULLY")
        print(f"✓ Backup saved at: {backup_path}")
        print("✓ All systems ready for enhanced team management")
    else:
        print("⚠ MIGRATION COMPLETED WITH WARNINGS")
        print("Please review the issues above")
        print(f"Backup available at: {backup_path}")

    print("\nNext steps:")
    print("1. Restart the Flask application: sudo systemctl restart field-trainer-server")
    print("2. Test team creation with new fields")
    print("3. Verify existing teams still work correctly")
    print("="*60)

if __name__ == "__main__":
    main()
