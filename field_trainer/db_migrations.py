"""
Database schema migrations for Field Trainer
Ensures database schema matches code expectations
"""
import sqlite3
from datetime import datetime

MIGRATIONS = [
    # Migration 001: Add pattern_config to sessions
    {
        'version': 1,
        'name': 'add_pattern_config_to_sessions',
        'sql': '''
            ALTER TABLE sessions ADD COLUMN pattern_config TEXT
        ''',
        'check': "SELECT COUNT(*) FROM pragma_table_info('sessions') WHERE name='pattern_config'"
    },
    # Migration 002: Add timer_start_at to runs
    {
        'version': 2,
        'name': 'add_timer_start_at_to_runs',
        'sql': '''
            ALTER TABLE runs ADD COLUMN timer_start_at TIMESTAMP
        ''',
        'check': "SELECT COUNT(*) FROM pragma_table_info('runs') WHERE name='timer_start_at'"
    },
    # Migration 003: Add cumulative_time to segments
    {
        'version': 3,
        'name': 'add_cumulative_time_to_segments',
        'sql': '''
            ALTER TABLE segments ADD COLUMN cumulative_time REAL
        ''',
        'check': "SELECT COUNT(*) FROM pragma_table_info('segments') WHERE name='cumulative_time'"
    },
    # Future migrations go here...
]


def apply_migrations(db_path: str):
    """Apply any pending migrations to the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create migrations tracking table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Get applied migrations
    cursor.execute('SELECT version FROM schema_migrations')
    applied = {row[0] for row in cursor.fetchall()}

    # Apply pending migrations
    for migration in MIGRATIONS:
        version = migration['version']

        if version in applied:
            continue

        # Check if migration is needed (column might already exist)
        cursor.execute(migration['check'])
        if cursor.fetchone()[0] > 0:
            print(f"Migration {version} ({migration['name']}) already applied manually - recording it")
            cursor.execute(
                'INSERT INTO schema_migrations (version, name) VALUES (?, ?)',
                (version, migration['name'])
            )
            conn.commit()
            continue

        # Apply migration
        print(f"Applying migration {version}: {migration['name']}")
        try:
            cursor.execute(migration['sql'])
            cursor.execute(
                'INSERT INTO schema_migrations (version, name) VALUES (?, ?)',
                (version, migration['name'])
            )
            conn.commit()
            print(f"✓ Migration {version} applied successfully")
        except Exception as e:
            print(f"✗ Migration {version} failed: {e}")
            conn.rollback()

    conn.close()


def get_schema_version(db_path: str) -> int:
    """Get current schema version"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(version) FROM schema_migrations')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] else 0
    except:
        return 0


if __name__ == '__main__':
    # Test migrations
    apply_migrations('/opt/data/field_trainer.db')
    version = get_schema_version('/opt/data/field_trainer.db')
    print(f"\nCurrent schema version: {version}")
