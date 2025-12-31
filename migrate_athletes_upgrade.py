"""
Upgrade Athletes Database Migration for Field Trainer
Migrates from simple athletes table to full-featured athletes management
Preserves existing athlete data
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate_athletes_upgrade(db_path):
    """Upgrade existing athletes table to full-featured version"""

    # Backup database first
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = OFF")  # Disable during migration
        cursor.execute("BEGIN TRANSACTION")

        # Check if old athletes table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='athletes'")
        old_table_exists = cursor.fetchone() is not None

        if old_table_exists:
            # Get existing data
            cursor.execute("SELECT * FROM athletes")
            existing_athletes = cursor.fetchall()
            print(f"✓ Found {len(existing_athletes)} existing athletes")

            # Rename old table
            cursor.execute("ALTER TABLE athletes RENAME TO athletes_old")
            print("✓ Renamed existing athletes table")

        # Create new enhanced athletes table
        cursor.execute("""
            CREATE TABLE athletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_number VARCHAR(20) UNIQUE NOT NULL,

                -- Basic Info
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                display_name VARCHAR(100),
                birthdate DATE,
                gender VARCHAR(20) CHECK(gender IN ('male', 'female', 'non-binary', NULL)),

                -- Photo (simple path storage)
                photo_filename VARCHAR(255),
                photo_size_kb REAL,
                photo_upload_date TIMESTAMP,
                photo_type VARCHAR(20),

                -- Medical Clearance
                medical_clearance_date DATE,
                medical_clearance_expires DATE,

                -- Privacy (COPPA compliance)
                photo_consent BOOLEAN DEFAULT 0,
                consent_given_by VARCHAR(100),
                consent_date DATE,

                -- Status
                active BOOLEAN DEFAULT 1,
                inactive_date DATE,

                -- Metadata
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Soft delete
                deleted BOOLEAN DEFAULT 0,
                deleted_date TIMESTAMP,

                -- Legacy compatibility
                legacy_athlete_id TEXT,
                legacy_team_id TEXT
            )
        """)
        print("✓ Created new athletes table")

        # Migrate existing data if any
        if old_table_exists and existing_athletes:
            athlete_number = 1000  # Start numbering from 1000
            for old_athlete in existing_athletes:
                # Parse name (handle single name or "FirstName LastName")
                name = old_athlete['name'] or 'Unknown'
                name_parts = name.split(None, 1)
                first_name = name_parts[0] if name_parts else 'Unknown'
                last_name = name_parts[1] if len(name_parts) > 1 else ''

                # Determine birthdate from age if available
                birthdate = None
                if old_athlete['age']:
                    current_year = datetime.now().year
                    birth_year = current_year - old_athlete['age']
                    birthdate = f"{birth_year}-01-01"

                cursor.execute("""
                    INSERT INTO athletes (
                        athlete_number, first_name, last_name, birthdate,
                        legacy_athlete_id, legacy_team_id, created_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"ATH{athlete_number:04d}",
                    first_name,
                    last_name,
                    birthdate,
                    old_athlete['athlete_id'],
                    old_athlete['team_id'],
                    old_athlete['created_at']
                ))
                athlete_number += 1

            print(f"✓ Migrated {len(existing_athletes)} athletes to new structure")

        # Create contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athlete_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id INTEGER NOT NULL,

                -- Basic contact info
                relationship VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                email VARCHAR(100),

                -- Permissions
                is_primary BOOLEAN DEFAULT 0,
                can_pickup BOOLEAN DEFAULT 1,
                emergency_contact BOOLEAN DEFAULT 1,

                -- Metadata
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
            )
        """)
        print("✓ Created athlete_contacts table")

        # Create medical table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athlete_medical (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id INTEGER NOT NULL UNIQUE,

                -- Essential medical info
                allergies TEXT,
                allergy_severity VARCHAR(20),
                medical_conditions TEXT,
                medications TEXT,
                physician_name VARCHAR(100),
                physician_phone VARCHAR(20),

                -- Metadata
                last_updated DATE,

                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
            )
        """)
        print("✓ Created athlete_medical table")

        # Update or create team_athletes table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_athletes'")
        team_athletes_exists = cursor.fetchone() is not None

        if not team_athletes_exists:
            cursor.execute("""
                CREATE TABLE team_athletes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    athlete_id INTEGER NOT NULL,

                    -- Team-specific info
                    jersey_number VARCHAR(10),
                    position VARCHAR(50),

                    -- Dates
                    joined_date DATE DEFAULT CURRENT_DATE,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                    FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
                    UNIQUE(team_id, athlete_id)
                )
            """)
            print("✓ Created team_athletes table")

            # Migrate team associations from old table
            if old_table_exists and existing_athletes:
                cursor.execute("SELECT id, legacy_athlete_id, legacy_team_id FROM athletes WHERE legacy_team_id IS NOT NULL")
                for row in cursor.fetchall():
                    if row['legacy_team_id']:
                        cursor.execute("""
                            INSERT OR IGNORE INTO team_athletes (team_id, athlete_id, added_date)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        """, (row['legacy_team_id'], row['id']))
                print("✓ Migrated team associations")

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_athletes_number ON athletes(athlete_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_athletes_active ON athletes(active, deleted)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_athletes_legacy ON athletes(legacy_athlete_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_athletes_team ON team_athletes(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_athletes_athlete ON team_athletes(athlete_id)")
        print("✓ Created indexes")

        # Create triggers
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_athletes_modified
            AFTER UPDATE ON athletes
            BEGIN
                UPDATE athletes SET modified_date = CURRENT_TIMESTAMP
                WHERE id = NEW.id;
            END
        """)
        print("✓ Created triggers")

        # Create photo directory
        os.makedirs('/field_trainer_data/athlete_photos', exist_ok=True)

        cursor.execute("COMMIT")
        cursor.execute("PRAGMA foreign_keys = ON")  # Re-enable

        print("✓ Athletes database upgrade completed successfully")

        # Verify
        cursor.execute("SELECT COUNT(*) FROM athletes")
        count = cursor.fetchone()[0]
        print(f"✓ Total athletes in new table: {count}")

        # Keep old table for reference
        print(f"\nNote: Original table preserved as 'athletes_old'")
        print(f"      You can drop it later with: DROP TABLE athletes_old")

        return True

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else '/opt/data/field_trainer.db'

    if not os.path.exists(db_path):
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)

    success = migrate_athletes_upgrade(db_path)
    sys.exit(0 if success else 1)
