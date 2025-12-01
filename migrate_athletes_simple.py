"""
Simplified Athletes Database Migration for Field Trainer
Tailored to actual requirements: <100 athletes, <20 per team
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate_athletes_simple(db_path):
    """Simplified migration focusing on essential features"""
    
    # Backup database first
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("BEGIN TRANSACTION")
        
        # 1. Core athletes table (simplified)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_number VARCHAR(20) UNIQUE NOT NULL,
                
                -- Basic Info
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                display_name VARCHAR(100),
                birthdate DATE NOT NULL,
                gender VARCHAR(20) CHECK(gender IN ('male', 'female', 'non-binary', NULL)),
                
                -- Photo (simple path storage)
                photo_filename VARCHAR(255),
                
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
                deleted_date TIMESTAMP
            )
        """)
        
        # 2. Contacts table (guardians only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athlete_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id INTEGER NOT NULL,
                
                -- Basic contact info
                relationship VARCHAR(50) NOT NULL, -- parent/guardian/emergency
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
        
        # 3. Medical info (allergies and conditions only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athlete_medical (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id INTEGER NOT NULL UNIQUE,
                
                -- Essential medical info
                allergies TEXT,
                medical_conditions TEXT,
                physician_name VARCHAR(100),
                physician_phone VARCHAR(20),
                
                -- Metadata
                last_updated DATE,
                
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
            )
        """)
        
        # 4. Update team_athletes for multi-team support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_athletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                athlete_id INTEGER NOT NULL,
                
                -- Team-specific info
                jersey_number VARCHAR(10),
                position VARCHAR(50),
                
                -- Dates
                joined_date DATE DEFAULT CURRENT_DATE,
                
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
                UNIQUE(team_id, athlete_id)
            )
        """)
        
        # 5. Create essential indexes only
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_athletes_number ON athletes(athlete_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_athletes_active ON athletes(active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_athletes ON team_athletes(team_id, athlete_id)")
        
        # 6. Auto-update trigger for modified_date
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_athletes_modified 
            AFTER UPDATE ON athletes 
            BEGIN
                UPDATE athletes SET modified_date = CURRENT_TIMESTAMP 
                WHERE id = NEW.id;
            END
        """)
        
        # Create photo directory
        os.makedirs('/field_trainer_data/athlete_photos', exist_ok=True)
        
        cursor.execute("COMMIT")
        print("✓ Athletes database migration completed")
        
        # Verify
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%athlete%'")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"✓ Tables created: {tables}")
        
        return True
        
    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"✗ Migration failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'field_trainer.db'
    migrate_athletes_simple(db_path)
