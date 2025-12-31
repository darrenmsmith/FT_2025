#!/usr/bin/env python3
"""
Database Initialization Script for Field Trainer Distributable

This script creates a clean Field Trainer database with:
- Complete schema (all 15 tables)
- Built-in training courses
- AI Team for testing
- NO user data (athletes, sessions, runs)

Usage:
    python3 init_clean_database.py [output_path]

Default output: /opt/data/field_trainer.db
"""

import sqlite3
import sys
import os
from datetime import datetime
import uuid

def create_schema(conn):
    """Create all database tables"""
    cursor = conn.cursor()

    print("Creating database schema...")

    # Teams table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age_group TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)

    # Athletes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS athletes (
            athlete_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            team_id TEXT,
            birth_date DATE,
            position TEXT,
            jersey_number INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)

    # Courses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            description TEXT,
            course_type TEXT NOT NULL,
            total_devices INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mode TEXT,
            category TEXT,
            num_devices INTEGER,
            distance_unit TEXT,
            total_distance INTEGER,
            diagram_svg TEXT,
            layout_instructions TEXT,
            is_builtin INTEGER DEFAULT 0,
            version TEXT
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            team_id TEXT,
            course_id INTEGER,
            drill_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            status TEXT DEFAULT 'setup',
            notes TEXT,
            FOREIGN KEY (team_id) REFERENCES teams(team_id),
            FOREIGN KEY (course_id) REFERENCES courses(course_id)
        )
    """)

    # Runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            athlete_id TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            total_time REAL,
            status TEXT DEFAULT 'pending',
            cone_touches TEXT,
            is_pr INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id),
            FOREIGN KEY (course_id) REFERENCES courses(course_id)
        )
    """)

    # Beep Test Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beep_test_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT,
            start_level INTEGER,
            distance_m INTEGER,
            device_count INTEGER,
            status TEXT,
            course_deployed INTEGER,
            started_at TEXT,
            ended_at TEXT,
            final_level INTEGER,
            final_shuttle INTEGER
        )
    """)

    # Beep Test Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beep_test_results (
            result_id TEXT PRIMARY KEY,
            session_id TEXT,
            athlete_id TEXT,
            athlete_name TEXT,
            level_achieved INTEGER,
            shuttle_completed INTEGER,
            status TEXT,
            failed_at TEXT,
            is_pr INTEGER,
            FOREIGN KEY (session_id) REFERENCES beep_test_sessions(session_id),
            FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id)
        )
    """)

    # Simon Says Patterns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simon_says_patterns (
            pattern_id TEXT PRIMARY KEY,
            pattern_name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_builtin INTEGER DEFAULT 0
        )
    """)

    # Simon Says Segments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simon_says_segments (
            segment_id TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            segment_order INTEGER NOT NULL,
            segment_type TEXT NOT NULL,
            device_ids TEXT,
            duration_ms INTEGER,
            color TEXT,
            inter_segment_delay_ms INTEGER DEFAULT 0,
            FOREIGN KEY (pattern_id) REFERENCES simon_says_patterns(pattern_id)
        )
    """)

    # Device Registry table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_registry (
            device_id TEXT PRIMARY KEY,
            device_name TEXT,
            ip_address TEXT,
            mac_address TEXT,
            last_seen TIMESTAMP,
            status TEXT DEFAULT 'offline',
            hardware_version TEXT,
            software_version TEXT,
            battery_level INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Coach Profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coach_profiles (
            coach_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)

    # Cone Layouts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cone_layouts (
            layout_id TEXT PRIMARY KEY,
            course_id INTEGER,
            device_number INTEGER,
            x_position REAL,
            y_position REAL,
            role TEXT,
            sequence_order INTEGER,
            FOREIGN KEY (course_id) REFERENCES courses(course_id)
        )
    """)

    # Calibration Data table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calibration_data (
            calibration_id TEXT PRIMARY KEY,
            device_id TEXT,
            sensor_type TEXT,
            calibration_values TEXT,
            calibrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            calibrated_by TEXT,
            notes TEXT,
            FOREIGN KEY (device_id) REFERENCES device_registry(device_id)
        )
    """)

    # Network Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_events (
            event_id TEXT PRIMARY KEY,
            device_id TEXT,
            event_type TEXT,
            event_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES device_registry(device_id)
        )
    """)

    # Failed Touches table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_touches (
            touch_id TEXT PRIMARY KEY,
            run_id TEXT,
            device_id TEXT,
            timestamp TIMESTAMP,
            reason TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (device_id) REFERENCES device_registry(device_id)
        )
    """)

    # Athlete Notes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS athlete_notes (
            note_id TEXT PRIMARY KEY,
            athlete_id TEXT,
            note_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id)
        )
    """)

    conn.commit()
    print("✅ Schema created successfully")


def insert_builtin_courses(conn):
    """Insert standard built-in training courses"""
    cursor = conn.cursor()

    print("\nInserting built-in courses...")

    now = datetime.now().isoformat()

    courses = [
        # Speed courses
        {
            'course_name': '40 Yard Sprint',
            'description': 'Standard 40-yard linear sprint test',
            'course_type': 'sequence',
            'category': 'speed',
            'total_devices': 2,
            'num_devices': 2,
            'distance_unit': 'yards',
            'total_distance': 40,
            'is_builtin': 1,
            'layout_instructions': 'Place Device 1 at start line, Device 2 at 40-yard finish line'
        },
        {
            'course_name': '60 Yard Sprint',
            'description': '60-yard linear sprint test',
            'course_type': 'sequence',
            'category': 'speed',
            'total_devices': 2,
            'num_devices': 2,
            'distance_unit': 'yards',
            'total_distance': 60,
            'is_builtin': 1,
            'layout_instructions': 'Place Device 1 at start line, Device 2 at 60-yard finish line'
        },
        {
            'course_name': '100m Sprint',
            'description': '100-meter linear sprint test',
            'course_type': 'sequence',
            'category': 'speed',
            'total_devices': 2,
            'num_devices': 2,
            'distance_unit': 'meters',
            'total_distance': 100,
            'is_builtin': 1,
            'layout_instructions': 'Place Device 1 at start line, Device 2 at 100m finish line'
        },

        # Agility courses
        {
            'course_name': 'Pro Agility 5-10-5',
            'description': 'Standard pro agility shuttle drill',
            'course_type': 'sequence',
            'category': 'agility',
            'total_devices': 3,
            'num_devices': 3,
            'distance_unit': 'yards',
            'total_distance': 20,
            'is_builtin': 1,
            'layout_instructions': 'Place 3 devices: Center (start), Left 5 yards, Right 5 yards'
        },
        {
            'course_name': '3-Cone Drill (L-Drill)',
            'description': 'NFL combine 3-cone agility test',
            'course_type': 'sequence',
            'category': 'agility',
            'total_devices': 3,
            'num_devices': 3,
            'distance_unit': 'yards',
            'total_distance': 15,
            'is_builtin': 1,
            'layout_instructions': 'L-shaped pattern: 5 yards between each cone'
        },
        {
            'course_name': 'T-Test Agility',
            'description': 'T-shaped agility test',
            'course_type': 'sequence',
            'category': 'agility',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'meters',
            'total_distance': 36,
            'is_builtin': 1,
            'layout_instructions': 'T-shape: 10m forward, 5m left/right, 5m center'
        },

        # Conditioning courses
        {
            'course_name': 'Beep Test - 20m',
            'description': 'Léger Protocol Beep Test (20 meter distance)',
            'course_type': 'beep_test',
            'category': 'conditioning',
            'total_devices': 2,
            'num_devices': 2,
            'distance_unit': 'meters',
            'total_distance': 20,
            'is_builtin': 1,
            'layout_instructions': '20 meters apart: START and END markers'
        },
        {
            'course_name': 'Beep Test - 15m',
            'description': 'Léger Protocol Beep Test (15 meter distance, modified)',
            'course_type': 'beep_test',
            'category': 'conditioning',
            'total_devices': 2,
            'num_devices': 2,
            'distance_unit': 'meters',
            'total_distance': 15,
            'is_builtin': 1,
            'layout_instructions': '15 meters apart: START and END markers'
        },
        {
            'course_name': 'Suicide Sprint',
            'description': 'Multi-distance shuttle sprint',
            'course_type': 'sequence',
            'category': 'conditioning',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'yards',
            'total_distance': 100,
            'is_builtin': 1,
            'layout_instructions': 'Start line + markers at 5yd, 10yd, 15yd'
        },

        # Warm-up sequences
        {
            'course_name': 'Warm-up: Round 1',
            'description': 'Progressive warm-up sequence - Round 1',
            'course_type': 'sequence',
            'category': 'warmup',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'meters',
            'total_distance': 20,
            'is_builtin': 1,
            'layout_instructions': 'Linear arrangement: 5m spacing between devices'
        },
        {
            'course_name': 'Warm-up: Round 2',
            'description': 'Progressive warm-up sequence - Round 2',
            'course_type': 'sequence',
            'category': 'warmup',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'meters',
            'total_distance': 25,
            'is_builtin': 1,
            'layout_instructions': 'Linear arrangement: 5m spacing between devices'
        },
        {
            'course_name': 'Warm-up: Round 3',
            'description': 'Progressive warm-up sequence - Round 3',
            'course_type': 'sequence',
            'category': 'warmup',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'meters',
            'total_distance': 30,
            'is_builtin': 1,
            'layout_instructions': 'Linear arrangement: 5m spacing between devices'
        },

        # Simon Says patterns
        {
            'course_name': 'Simon Says - Random',
            'description': 'Random device activation for reaction training',
            'course_type': 'state_changing',
            'category': 'reaction',
            'total_devices': 5,
            'num_devices': 5,
            'distance_unit': 'meters',
            'total_distance': 0,
            'is_builtin': 1,
            'mode': 'random',
            'layout_instructions': 'Arrange devices in a pattern (circle, line, or custom)'
        },
        {
            'course_name': 'Simon Says - 4 Colors',
            'description': 'Pattern-based Simon Says with 4 color segments',
            'course_type': 'state_changing',
            'category': 'reaction',
            'total_devices': 4,
            'num_devices': 4,
            'distance_unit': 'meters',
            'total_distance': 0,
            'is_builtin': 1,
            'mode': 'pattern',
            'layout_instructions': 'Square or diamond pattern, equidistant spacing'
        }
    ]

    for course in courses:
        course['created_at'] = now
        course['updated_at'] = now

        columns = ', '.join(course.keys())
        placeholders = ', '.join(['?' for _ in course])

        cursor.execute(
            f"INSERT INTO courses ({columns}) VALUES ({placeholders})",
            list(course.values())
        )

    conn.commit()
    print(f"✅ Inserted {len(courses)} built-in courses")


def insert_ai_team(conn):
    """Insert AI Team for testing"""
    cursor = conn.cursor()

    print("\nInserting AI Team...")

    team_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO teams (team_id, name, age_group, created_at, updated_at, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (team_id, 'AI Team', 'All Ages', now, now, 1))

    conn.commit()
    print(f"✅ AI Team inserted (ID: {team_id})")

    return team_id


def create_indexes(conn):
    """Create database indexes for performance"""
    cursor = conn.cursor()

    print("\nCreating indexes...")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_athletes_team ON athletes(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_athletes_active ON athletes(active)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_team ON sessions(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_course ON sessions(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)",
        "CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_runs_athlete ON runs(athlete_id)",
        "CREATE INDEX IF NOT EXISTS idx_runs_course ON runs(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_beep_results_session ON beep_test_results(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_beep_results_athlete ON beep_test_results(athlete_id)",
        "CREATE INDEX IF NOT EXISTS idx_simon_segments_pattern ON simon_says_segments(pattern_id)",
        "CREATE INDEX IF NOT EXISTS idx_device_registry_status ON device_registry(status)",
        "CREATE INDEX IF NOT EXISTS idx_courses_builtin ON courses(is_builtin)",
        "CREATE INDEX IF NOT EXISTS idx_courses_category ON courses(category)",
    ]

    for idx_sql in indexes:
        cursor.execute(idx_sql)

    conn.commit()
    print(f"✅ Created {len(indexes)} indexes")


def verify_database(conn):
    """Verify database integrity"""
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("DATABASE VERIFICATION")
    print("="*60)

    # Count tables
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    table_count = cursor.fetchone()[0]
    print(f"✅ Tables: {table_count}")

    # Count built-in courses
    cursor.execute("SELECT COUNT(*) FROM courses WHERE is_builtin = 1")
    course_count = cursor.fetchone()[0]
    print(f"✅ Built-in courses: {course_count}")

    # List built-in courses by category
    cursor.execute("""
        SELECT category, COUNT(*)
        FROM courses
        WHERE is_builtin = 1
        GROUP BY category
        ORDER BY category
    """)
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} course(s)")

    # Count teams
    cursor.execute("SELECT COUNT(*) FROM teams")
    team_count = cursor.fetchone()[0]
    print(f"✅ Teams: {team_count}")

    # Verify AI Team
    cursor.execute("SELECT name FROM teams WHERE name = 'AI Team'")
    ai_team = cursor.fetchone()
    if ai_team:
        print(f"✅ AI Team: Present")
    else:
        print(f"❌ AI Team: MISSING!")

    # Verify no user data
    cursor.execute("SELECT COUNT(*) FROM athletes")
    athlete_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM runs")
    run_count = cursor.fetchone()[0]

    print(f"✅ Athletes: {athlete_count} (should be 0)")
    print(f"✅ Sessions: {session_count} (should be 0)")
    print(f"✅ Runs: {run_count} (should be 0)")

    if athlete_count > 0 or session_count > 0 or run_count > 0:
        print("⚠️  WARNING: User data detected! This should be a clean database.")

    # Get database file size
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    size = cursor.fetchone()[0]
    print(f"✅ Database size: {size:,} bytes ({size/1024:.1f} KB)")

    print("="*60)


def main():
    """Main initialization function"""

    # Get output path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = '/opt/data/field_trainer_clean.db'

    print("="*60)
    print("FIELD TRAINER - DATABASE INITIALIZATION")
    print("="*60)
    print(f"Output: {db_path}")
    print()

    # Check if file exists
    if os.path.exists(db_path):
        response = input(f"⚠️  {db_path} already exists. Overwrite? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)
        os.remove(db_path)
        print(f"Removed existing file")

    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Create database
    print(f"\nCreating database at: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        # Create schema
        create_schema(conn)

        # Insert built-in data
        insert_builtin_courses(conn)
        insert_ai_team(conn)

        # Create indexes
        create_indexes(conn)

        # Verify
        verify_database(conn)

        print("\n✅ DATABASE INITIALIZATION COMPLETE!\n")
        print(f"Clean database created at: {db_path}")
        print("\nTo use this database:")
        print(f"  cp {db_path} /opt/data/field_trainer.db")
        print("  sudo systemctl restart field-trainer")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
