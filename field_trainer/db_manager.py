#!/usr/bin/env python3
"""
Database Manager for Field Trainer Phase 1
Handles all CRUD operations for teams, athletes, courses, sessions, runs, and segments
"""

import sqlite3
import uuid
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

# Device name mapping (hardcoded for 6-device system)
DEVICE_NAMES = {
    "192.168.99.100": "Device 0",
    "192.168.99.101": "Device 1",
    "192.168.99.102": "Device 2",
    "192.168.99.103": "Device 3",
    "192.168.99.104": "Device 4",
    "192.168.99.105": "Device 5",
}


class DatabaseManager:
    """Thread-safe database manager for Field Trainer"""
    
    def __init__(self, db_path: str = '/opt/data/field_trainer.db'):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=20.0)  # 20 second timeout for locks (increased for concurrent touch operations)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute('PRAGMA journal_mode=WAL')  # Enable Write-Ahead Logging for better concurrency
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """Create all tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Teams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    age_group TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Athletes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS athletes (
                    athlete_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    jersey_number INTEGER,
                    age INTEGER,
                    position TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_athletes_team ON athletes(team_id)')
            
            # Courses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    course_type TEXT DEFAULT 'conditioning',
                    total_devices INTEGER DEFAULT 6,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Course actions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    device_name TEXT,
                    action TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    audio_file TEXT,
                    instruction TEXT,
                    min_time REAL DEFAULT 1.0,
                    max_time REAL DEFAULT 30.0,
                    triggers_next_athlete BOOLEAN DEFAULT 0,
                    marks_run_complete BOOLEAN DEFAULT 0,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
                    UNIQUE(course_id, sequence)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_actions_course ON course_actions(course_id)')
            
            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'setup',
                    audio_voice TEXT DEFAULT 'male',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id),
                    FOREIGN KEY (course_id) REFERENCES courses(course_id),
                    CHECK (audio_voice IN ('male', 'female')),
                    CHECK (status IN ('setup', 'active', 'completed', 'incomplete'))
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_team ON sessions(team_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)')
            
            # Runs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    athlete_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    queue_position INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_time REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id),
                    FOREIGN KEY (course_id) REFERENCES courses(course_id),
                    UNIQUE(session_id, queue_position),
                    CHECK (status IN ('queued', 'running', 'completed', 'incomplete', 'dropped', 'absent'))
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_athlete ON runs(athlete_id)')
            
            # Segments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS segments (
                    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    from_device TEXT NOT NULL,
                    to_device TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    expected_min_time REAL NOT NULL,
                    expected_max_time REAL NOT NULL,
                    actual_time REAL,
                    touch_detected BOOLEAN DEFAULT 0,
                    touch_timestamp TIMESTAMP,
                    alert_raised BOOLEAN DEFAULT 0,
                    alert_type TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                    CHECK (alert_type IS NULL OR alert_type IN ('missed_touch', 'too_slow', 'too_fast'))
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_segments_run ON segments(run_id)')

            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(setting_key)')

            # Initialize default settings if table is empty
            settings_count = conn.execute('SELECT COUNT(*) FROM settings').fetchone()[0]
            if settings_count == 0:
                default_settings = {
                    'distance_unit': 'yards',
                    'voice_gender': 'male',
                    'system_volume': '60',
                    'ready_audio_file': 'default.mp3',
                    'min_travel_time': '1',
                    'max_travel_time': '15',
                    'ready_led_color': 'orange',
                    'ready_audio_target': 'all',
                    'wifi_ssid': '',
                    'wifi_password': ''
                }
                for key, value in default_settings.items():
                    conn.execute('''
                        INSERT INTO settings (setting_key, setting_value)
                        VALUES (?, ?)
                    ''', (key, value))

            # Beep Test Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS beep_test_sessions (
                    session_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    distance_meters INTEGER NOT NULL CHECK (distance_meters IN (15, 20)),
                    device_count INTEGER NOT NULL CHECK (device_count IN (2, 4, 6)),
                    start_level INTEGER NOT NULL DEFAULT 1 CHECK (start_level >= 1 AND start_level <= 21),
                    status TEXT NOT NULL DEFAULT 'setup' CHECK (status IN ('setup', 'active', 'completed', 'stopped')),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_beep_sessions_team ON beep_test_sessions(team_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_beep_sessions_status ON beep_test_sessions(status)')

            # Beep Test Results table (per athlete)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS beep_test_results (
                    result_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    athlete_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'failed', 'passed', 'did_not_start')),
                    level_completed INTEGER CHECK (level_completed >= 0 AND level_completed <= 21),
                    level_failed INTEGER CHECK (level_failed >= 1 AND level_failed <= 21),
                    shuttle_failed_on INTEGER,
                    vo2_max_estimate REAL,
                    failed_at TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES beep_test_sessions(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_beep_results_session ON beep_test_results(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_beep_results_athlete ON beep_test_results(athlete_id)')

    # ==================== DASHBOARD QUERIES ====================
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for coach dashboard"""
        from datetime import datetime, timedelta
        
        with self.get_connection() as conn:
            stats = {}
            
            # Total athletes and teams
            stats['total_athletes'] = conn.execute('SELECT COUNT(*) FROM athletes').fetchone()[0]
            stats['total_teams'] = conn.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
            
            # Today's activity
            today = datetime.now().date().isoformat()
            stats['sessions_today'] = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(created_at) = ?", (today,)
            ).fetchone()[0]
            
            stats['runs_today'] = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE DATE(started_at) = ?", (today,)
            ).fetchone()[0]
            
            # PRs this week
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            stats['prs_this_week'] = conn.execute(
                "SELECT COUNT(*) FROM personal_records WHERE achieved_at > ?",
                (week_ago,)
            ).fetchone()[0]
            
            return stats

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent completed runs for dashboard (includes both regular runs and beep tests)"""
        from datetime import datetime

        with self.get_connection() as conn:
            # UNION regular runs with beep test results
            rows = conn.execute('''
                SELECT
                    r.run_id as activity_id,
                    r.total_time,
                    r.completed_at,
                    COALESCE(ph.is_personal_record, 0) as is_pr,
                    a.name as athlete_name,
                    c.course_name,
                    'run' as activity_type
                FROM runs r
                JOIN athletes a ON r.athlete_id = a.athlete_id
                JOIN courses c ON r.course_id = c.course_id
                LEFT JOIN performance_history ph ON r.run_id = ph.run_id
                WHERE r.status = 'completed'

                UNION ALL

                SELECT
                    btr.result_id as activity_id,
                    NULL as total_time,
                    s.created_at as completed_at,
                    0 as is_pr,
                    a.name as athlete_name,
                    'Beep Test - Level ' || COALESCE(btr.level_completed, 0) as course_name,
                    'beep_test' as activity_type
                FROM beep_test_results btr
                JOIN athletes a ON btr.athlete_id = a.athlete_id
                JOIN sessions s ON btr.session_id = s.session_id
                WHERE s.status IN ('completed', 'incomplete')

                ORDER BY completed_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()

            activity = []
            now = datetime.utcnow()  # Use UTC to match database timestamps

            for row in rows:
                item = dict(row)

                # Calculate "time ago"
                completed = datetime.fromisoformat(item['completed_at'])
                delta = now - completed

                if delta.days > 0:
                    item['time_ago'] = f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
                elif delta.seconds >= 3600:
                    hours = delta.seconds // 3600
                    item['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
                elif delta.seconds >= 60:
                    minutes = delta.seconds // 60
                    item['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                else:
                    item['time_ago'] = "just now"

                activity.append(item)

            return activity

    def get_course_rankings(self, team_id: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get course rankings showing each athlete's PR for each course (includes Beep Test)"""
        with self.get_connection() as conn:
            # Build WHERE clause for filters
            where_clauses = ["r.status = 'completed'", "r.total_time IS NOT NULL"]
            params = []

            if team_id:
                where_clauses.append("a.team_id = ?")
                params.append(team_id)

            if category:
                where_clauses.append("c.category = ?")
                params.append(category)

            where_clause = " AND ".join(where_clauses)

            # Get best time for each athlete on each course
            rows = conn.execute(f'''
                SELECT
                    c.course_id,
                    c.course_name,
                    c.category,
                    a.athlete_id,
                    a.name as athlete_name,
                    t.name as team_name,
                    MIN(r.total_time) as best_time,
                    MAX(CASE WHEN r.total_time = (
                        SELECT MIN(total_time)
                        FROM runs
                        WHERE athlete_id = a.athlete_id
                        AND course_id = c.course_id
                        AND status = 'completed'
                    ) THEN r.completed_at END) as pr_date,
                    'course' as ranking_type
                FROM runs r
                JOIN athletes a ON r.athlete_id = a.athlete_id
                JOIN teams t ON a.team_id = t.team_id
                JOIN courses c ON r.course_id = c.course_id
                WHERE {where_clause}
                GROUP BY c.course_id, c.course_name, c.category, a.athlete_id, a.name, t.name
                ORDER BY c.course_name, best_time ASC
            ''', params).fetchall()

            # Organize by course
            courses = {}
            for row in rows:
                course_id = row['course_id']
                if course_id not in courses:
                    courses[course_id] = {
                        'course_id': course_id,
                        'course_name': row['course_name'],
                        'category': row['category'],
                        'ranking_type': 'course',
                        'rankings': []
                    }

                courses[course_id]['rankings'].append({
                    'athlete_id': row['athlete_id'],
                    'athlete_name': row['athlete_name'],
                    'team_name': row['team_name'],
                    'best_time': row['best_time'],
                    'best_level': None,
                    'pr_date': row['pr_date']
                })

            # Add Beep Test rankings (if not filtering by category, or category is fitness/cardio)
            if not category or category.lower() in ['fitness', 'cardio']:
                beep_params = []
                beep_where = ["s.status IN ('completed', 'incomplete')"]

                if team_id:
                    beep_where.append("a.team_id = ?")
                    beep_params.append(team_id)

                beep_where_clause = " AND ".join(beep_where)

                beep_rows = conn.execute(f'''
                    SELECT
                        a.athlete_id,
                        a.name as athlete_name,
                        t.name as team_name,
                        MAX(btr.level_completed) as best_level,
                        MAX(CASE WHEN btr.level_completed = (
                            SELECT MAX(level_completed)
                            FROM beep_test_results
                            WHERE athlete_id = a.athlete_id
                        ) THEN s.created_at END) as pr_date
                    FROM beep_test_results btr
                    JOIN athletes a ON btr.athlete_id = a.athlete_id
                    JOIN teams t ON a.team_id = t.team_id
                    JOIN sessions s ON btr.session_id = s.session_id
                    WHERE {beep_where_clause}
                    GROUP BY a.athlete_id, a.name, t.name
                    ORDER BY best_level DESC
                ''', beep_params).fetchall()

                if beep_rows:
                    courses['beep_test'] = {
                        'course_id': 'beep_test',
                        'course_name': 'Beep Test',
                        'category': 'Fitness',
                        'ranking_type': 'beep_test',
                        'rankings': []
                    }

                    for row in beep_rows:
                        courses['beep_test']['rankings'].append({
                            'athlete_id': row['athlete_id'],
                            'athlete_name': row['athlete_name'],
                            'team_name': row['team_name'],
                            'best_time': None,
                            'best_level': row['best_level'],
                            'pr_date': row['pr_date']
                        })

            return list(courses.values())

    def check_and_mark_pr(self, run_id: str) -> bool:
        """Check if a completed run is a PR and mark it"""
        with self.get_connection() as conn:
            # Get the run details
            run = conn.execute(
                'SELECT athlete_id, course_id, total_time FROM runs WHERE run_id = ?',
                (run_id,)
            ).fetchone()
            
            if not run or not run['total_time']:
                return False
            
            athlete_id = run['athlete_id']
            course_id = run['course_id']
            current_time = run['total_time']
            
            # Find best previous time for this athlete on this course
            best_prev = conn.execute('''
                SELECT MIN(total_time) as best_time
                FROM runs
                WHERE athlete_id = ? 
                AND course_id = ?
                AND run_id != ?
                AND status = 'completed'
                AND total_time IS NOT NULL
            ''', (athlete_id, course_id, run_id)).fetchone()
            
            is_pr = False
            if best_prev['best_time'] is None or current_time < best_prev['best_time']:
                # This is a PR!
                is_pr = True
                conn.execute(
                    'UPDATE runs SET is_pr = 1 WHERE run_id = ?',
                    (run_id,)
                )
            
            return is_pr

    # ==================== TEAM OPERATIONS ====================
    
    def create_team(self, name: str, age_group: Optional[str] = None,
                   sport: Optional[str] = None, gender: Optional[str] = None,
                   season: Optional[str] = None, coach_name: Optional[str] = None,
                   notes: Optional[str] = None, active: bool = True) -> str:
        """Create a new team - using simple schema (only team_id, name, age_group)"""
        team_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            # Simple schema: only team_id, name, age_group, created_at, updated_at
            conn.execute(
                '''INSERT INTO teams (team_id, name, age_group, created_at, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                (team_id, name, age_group or '')
            )
        return team_id
    
    def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get team by ID"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM teams WHERE team_id = ?', (team_id,)).fetchone()
            return dict(row) if row else None
    
    def get_all_teams(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get all teams, optionally filtering by active status"""
        with self.get_connection() as conn:
            if active_only:
                rows = conn.execute('SELECT * FROM teams WHERE active = 1 ORDER BY name').fetchall()
            else:
                rows = conn.execute('SELECT * FROM teams ORDER BY name').fetchall()
            return [dict(row) for row in rows]
    
    def update_team(self, team_id: str, **kwargs):
        """Update team fields - simple schema (name, age_group, active)"""
        # Allow fields that exist in the schema
        allowed_fields = {'name', 'age_group', 'active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return

        updates['updated_at'] = datetime.utcnow().isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())

        with self.get_connection() as conn:
            conn.execute(
                f'UPDATE teams SET {set_clause} WHERE team_id = ?',
                (*updates.values(), team_id)
            )
    
    def delete_team(self, team_id: str):
        """Delete team (cascades to athletes)"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM teams WHERE team_id = ?', (team_id,))

    def archive_team(self, team_id: str):
        """Archive team (soft delete by setting active=0)"""
        self.update_team(team_id, active=0)

    def reactivate_team(self, team_id: str):
        """Reactivate an archived team"""
        self.update_team(team_id, active=1)

    def duplicate_team(self, team_id: str, new_name: Optional[str] = None,
                      new_season: Optional[str] = None) -> Optional[str]:
        """Create a copy of a team (useful for new seasons), including athletes"""
        original = self.get_team(team_id)
        if not original:
            return None

        # Prepare new team data
        new_team_name = new_name or f"{original['name']} (Copy)"
        new_team_season = new_season or original.get('season')

        new_team_id = self.create_team(
            name=new_team_name,
            age_group=original.get('age_group'),
            sport=original.get('sport'),
            gender=original.get('gender'),
            season=new_team_season,
            coach_name=original.get('coach_name'),
            notes=f"Duplicated from team {original['name']}. {original.get('notes', '')}",
            active=True
        )

        # Copy athletes from original team to new team
        if new_team_id:
            original_athletes = self.get_athletes_by_team(team_id)
            for athlete in original_athletes:
                self.create_athlete(
                    team_id=new_team_id,
                    name=athlete['name'],
                    jersey_number=athlete.get('jersey_number'),
                    age=athlete.get('age'),
                    position=athlete.get('position')
                )

        return new_team_id

    def search_teams(self, search_term: Optional[str] = None,
                    sport: Optional[str] = None, gender: Optional[str] = None,
                    coach_name: Optional[str] = None,
                    active_only: bool = False) -> List[Dict[str, Any]]:
        """Search and filter teams - simple schema (only name, age_group)"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM teams WHERE 1=1'
            params = []

            # Note: active, sport, gender, coach_name columns don't exist in simple schema
            # Only search by name and age_group

            if search_term:
                query += ' AND (name LIKE ? OR age_group LIKE ?)'
                search_pattern = f'%{search_term}%'
                params.extend([search_pattern, search_pattern])

            query += ' ORDER BY name'

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def export_team_csv(self, team_id: str) -> Optional[str]:
        """Export team data as CSV string"""
        import csv
        from io import StringIO

        team = self.get_team(team_id)
        if not team:
            return None

        # Get athlete count
        athletes = self.get_athletes_by_team(team_id)
        team['athlete_count'] = len(athletes)

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['Field', 'Value'])

        # Data
        fields = [
            ('Team ID', 'team_id'),
            ('Team Name', 'name'),
            ('Age Group', 'age_group'),
            ('Sport', 'sport'),
            ('Gender', 'gender'),
            ('Season', 'season'),
            ('Status', lambda t: 'Active' if t.get('active') else 'Archived'),
            ('Coach Name', 'coach_name'),
            ('Athlete Count', 'athlete_count'),
            ('Notes', 'notes'),
            ('Created Date', 'created_at'),
            ('Last Modified', 'updated_at')
        ]

        for label, key in fields:
            if callable(key):
                value = key(team)
            else:
                value = team.get(key, '')
            writer.writerow([label, value or ''])

        return output.getvalue()

    def export_all_teams_csv(self) -> str:
        """Export all teams as CSV"""
        import csv
        from io import StringIO

        teams = self.get_all_teams(active_only=False)

        output = StringIO()
        writer = csv.writer(output)

        # Header
        headers = ['ID', 'Name', 'Age Group', 'Sport', 'Gender', 'Season',
                  'Status', 'Coach', 'Created', 'Modified']
        writer.writerow(headers)

        # Data rows
        for team in teams:
            row = [
                team.get('team_id'),
                team.get('name'),
                team.get('age_group', ''),
                team.get('sport', ''),
                team.get('gender', ''),
                team.get('season', ''),
                'Active' if team.get('active') else 'Archived',
                team.get('coach_name', ''),
                team.get('created_at', ''),
                team.get('updated_at', '')
            ]
            writer.writerow(row)

        return output.getvalue()
    
    # ==================== ATHLETE OPERATIONS ====================
    
    def create_athlete(self, team_id: str, name: str, jersey_number: Optional[int] = None,
                      age: Optional[int] = None, position: Optional[str] = None) -> str:
        """Create a new athlete, return athlete_id"""
        athlete_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                '''INSERT INTO athletes (athlete_id, team_id, name, jersey_number, age, position)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (athlete_id, team_id, name, jersey_number, age, position)
            )
        return athlete_id
    
    def get_athlete(self, athlete_id: str) -> Optional[Dict[str, Any]]:
        """Get athlete by ID"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM athletes WHERE athlete_id = ?', (athlete_id,)).fetchone()
            return dict(row) if row else None
    
    def get_athletes_by_team(self, team_id: str) -> List[Dict[str, Any]]:
        """Get all athletes for a team"""
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM athletes WHERE team_id = ? ORDER BY jersey_number, name',
                (team_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def update_athlete(self, athlete_id: str, **kwargs):
        """Update athlete fields"""
        allowed_fields = {'name', 'jersey_number', 'age', 'position', 'team_id'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return
        
        updates['updated_at'] = datetime.utcnow().isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        
        with self.get_connection() as conn:
            conn.execute(
                f'UPDATE athletes SET {set_clause} WHERE athlete_id = ?',
                (*updates.values(), athlete_id)
            )
    
    def delete_athlete(self, athlete_id: str):
        """Delete athlete"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM athletes WHERE athlete_id = ?', (athlete_id,))
    
    # ==================== COURSE OPERATIONS ====================
    
    def create_course(self, name: str, description: str, course_type: str,
                     actions: List[Dict[str, Any]], mode: Optional[str] = None,
                     category: Optional[str] = None, total_devices: Optional[int] = None) -> int:
        """Create course with actions, return course_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Use provided total_devices or default to action count
            device_count = total_devices if total_devices is not None else len(actions)

            # Create course
            cursor.execute(
                '''INSERT INTO courses (course_name, description, course_type, total_devices, mode, category)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (name, description, course_type, device_count, mode, category)
            )
            course_id = cursor.lastrowid

            # Create actions
            for seq, action_data in enumerate(actions):
                device_id = action_data['device_id']
                cursor.execute(
                    '''INSERT INTO course_actions
                       (course_id, sequence, device_id, device_name, action, action_type,
                        audio_file, instruction, min_time, max_time, triggers_next_athlete,
                        marks_run_complete, distance, behavior_config, group_identifier)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        course_id, seq, device_id, action_data.get('device_name') or DEVICE_NAMES.get(device_id),
                        action_data['action'], action_data.get('action_type', 'touch_checkpoint'),
                        action_data.get('audio_file'), action_data.get('instruction'),
                        action_data.get('min_time', 1.0), action_data.get('max_time', 30.0),
                        action_data.get('triggers_next_athlete', False),
                        action_data.get('marks_run_complete', False),
                        action_data.get('distance', 0),
                        action_data.get('behavior_config'),
                        action_data.get('group_identifier')
                    )
                )

        return course_id
    
    def get_course(self, course_id_or_name) -> Optional[Dict[str, Any]]:
        """Get course with actions by ID or name"""
        with self.get_connection() as conn:
            # Try by ID first
            if isinstance(course_id_or_name, int):
                row = conn.execute('SELECT * FROM courses WHERE course_id = ?', (course_id_or_name,)).fetchone()
            else:
                row = conn.execute('SELECT * FROM courses WHERE course_name = ?', (course_id_or_name,)).fetchone()
            
            if not row:
                return None
            
            course = dict(row)
            
            # Get actions
            actions = conn.execute(
                '''SELECT * FROM course_actions WHERE course_id = ? ORDER BY sequence''',
                (course['course_id'],)
            ).fetchall()
            course['actions'] = [dict(a) for a in actions]
            
            return course
    
    def get_all_courses(self) -> List[Dict[str, Any]]:
        """Get all courses (without actions for list view)"""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM courses ORDER BY course_name').fetchall()
            return [dict(row) for row in rows]
    
    def update_course(self, course_id: int, **kwargs):
        """Update course fields"""
        allowed_fields = {'course_name', 'description', 'course_type', 'mode', 'category',
                         'num_devices', 'distance_unit', 'total_distance', 'diagram_svg',
                         'layout_instructions'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return

        updates['updated_at'] = datetime.utcnow().isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())

        with self.get_connection() as conn:
            conn.execute(
                f'UPDATE courses SET {set_clause} WHERE course_id = ?',
                (*updates.values(), course_id)
            )
    
    def delete_course(self, course_id: int):
        """Delete course (cascades to actions)"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM courses WHERE course_id = ?', (course_id,))
    
    # ==================== SESSION OPERATIONS ====================
    
    def create_session(self, team_id: str, course_id: int, athlete_queue: List[str],
                      audio_voice: str = 'male', pattern_config: Optional[str] = None) -> str:
        """Create session with athlete queue, return session_id

        Args:
            team_id: Team identifier
            course_id: Course identifier
            athlete_queue: List of athlete IDs in queue order
            audio_voice: Voice for audio feedback ('male' or 'female')
            pattern_config: Optional JSON string with pattern configuration override
                           (for Simon Says pattern length progression)
        """
        session_id = str(uuid.uuid4())

        with self.get_connection() as conn:
            # Create session
            conn.execute(
                '''INSERT INTO sessions (session_id, team_id, course_id, status, audio_voice, pattern_config)
                   VALUES (?, ?, ?, 'setup', ?, ?)''',
                (session_id, team_id, course_id, audio_voice, pattern_config)
            )
            
            # Create runs for each athlete in queue
            for position, athlete_id in enumerate(athlete_queue):
                run_id = str(uuid.uuid4())
                conn.execute(
                    '''INSERT INTO runs (run_id, session_id, athlete_id, course_id, queue_position, status)
                       VALUES (?, ?, ?, ?, ?, 'queued')''',
                    (run_id, session_id, athlete_id, course_id, position)
                )
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session with runs"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,)).fetchone()
            if not row:
                return None
            
            session = dict(row)
            
            # Get runs with athlete info
            runs = conn.execute(
                '''SELECT r.*, a.name as athlete_name, a.jersey_number
                   FROM runs r
                   JOIN athletes a ON r.athlete_id = a.athlete_id
                   WHERE r.session_id = ?
                   ORDER BY r.queue_position''',
                (session_id,)
            ).fetchall()
            session['runs'] = [dict(run) for run in runs]
            
            return session
    
    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Get currently active session if any"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE status IN ('setup', 'active') ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
    
    def start_session(self, session_id: str, timestamp: Optional[datetime] = None):
        """Mark session as active (GO button clicked)"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE sessions SET status = ?, started_at = ? WHERE session_id = ?',
                ('active', timestamp.isoformat(), session_id)
            )
    
    def complete_session(self, session_id: str, timestamp: Optional[datetime] = None):
        """Mark session as completed"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE sessions SET status = ?, completed_at = ? WHERE session_id = ?',
                ('completed', timestamp.isoformat(), session_id)
            )
    
    def mark_session_incomplete(self, session_id: str, reason: str):
        """Mark session as incomplete with reason"""
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE sessions SET status = ?, notes = ?, completed_at = ? WHERE session_id = ?',
                ('incomplete', reason, datetime.utcnow().isoformat(), session_id)
            )
    
    # ==================== RUN OPERATIONS ====================
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run with segments"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            if not row:
                return None
            
            run = dict(row)
            
            # Get segments
            segments = conn.execute(
                'SELECT * FROM segments WHERE run_id = ? ORDER BY sequence',
                (run_id,)
            ).fetchall()
            run['segments'] = [dict(seg) for seg in segments]
            
            return run
    
    def update_run_status(self, run_id: str, status: str):
        """Update run status"""
        with self.get_connection() as conn:
            conn.execute('UPDATE runs SET status = ? WHERE run_id = ?', (status, run_id))
    
    def start_run(self, run_id: str, timestamp: Optional[datetime] = None):
        """Mark run as started"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE runs SET status = ?, started_at = ? WHERE run_id = ?',
                ('running', timestamp.isoformat(), run_id)
            )
            # Force immediate commit to prevent race conditions
            conn.commit()

    def complete_run(self, run_id: str, timestamp: Optional[datetime] = None, total_time: Optional[float] = None, status: str = 'completed'):
        """Mark run as completed or incomplete

        Args:
            run_id: The run ID
            timestamp: Completion timestamp (defaults to now)
            total_time: Total time in seconds
            status: Run status ('completed' for success, 'incomplete' for failure)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        with self.get_connection() as conn:
            conn.execute(
                'UPDATE runs SET status = ?, completed_at = ?, total_time = ? WHERE run_id = ?',
                (status, timestamp.isoformat(), total_time, run_id)
            )

    def update_run_timer_start(self, run_id: str, timer_start: datetime):
        """Update the timer_start_at timestamp for a run (when D0 beeps in pattern mode)"""
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE runs SET timer_start_at = ? WHERE run_id = ?',
                (timer_start.isoformat(), run_id)
            )

    def get_session_runs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all runs for a session"""
        with self.get_connection() as conn:
            rows = conn.execute(
                '''SELECT r.*, a.name as athlete_name, a.jersey_number
                   FROM runs r
                   JOIN athletes a ON r.athlete_id = a.athlete_id
                   WHERE r.session_id = ?
                   ORDER BY r.queue_position''',
                (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_next_queued_run(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get next queued run in session"""
        with self.get_connection() as conn:
            row = conn.execute(
                '''SELECT r.*, a.name as athlete_name
                   FROM runs r
                   JOIN athletes a ON r.athlete_id = a.athlete_id
                   WHERE r.session_id = ? AND r.status = 'queued'
                   ORDER BY r.queue_position
                   LIMIT 1''',
                (session_id,)
            ).fetchone()
            return dict(row) if row else None
    
    # ==================== SEGMENT OPERATIONS ====================
    
    def create_segments_for_run(self, run_id: str, course_id: int):
        """Pre-create all segments for a run based on course actions"""
        with self.get_connection() as conn:
            # Check if segments already exist (prevent duplicates)
            existing = conn.execute(
                'SELECT COUNT(*) as count FROM segments WHERE run_id = ?',
                (run_id,)
             ).fetchone()

            if existing['count'] > 0:
                print(f"⚠️  Segments already exist for run {run_id[:8]}... (skipping creation)")
                return

            # Get course actions
            actions = conn.execute(
                'SELECT * FROM course_actions WHERE course_id = ? ORDER BY sequence',
                (course_id,)
            ).fetchall()

            # Create segments (device N to device N+1)
            for i in range(len(actions) - 1):
                from_action = actions[i]
                to_action = actions[i + 1]

                conn.execute(
                    '''INSERT INTO segments
                       (run_id, from_device, to_device, sequence, expected_min_time, expected_max_time)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (
                        run_id,
                        from_action['device_id'],
                        to_action['device_id'],
                        i,
                        to_action['min_time'],
                        to_action['max_time']
                    )
                )

    def create_pattern_segments_for_run(self, run_id: str, pattern_device_ids: list):
        """Create segments for pattern mode based on actual pattern sequence"""
        with self.get_connection() as conn:
            # Check if segments already exist (prevent duplicates)
            existing = conn.execute(
                'SELECT COUNT(*) as count FROM segments WHERE run_id = ?',
                (run_id,)
             ).fetchone()

            if existing['count'] > 0:
                print(f"⚠️  Pattern segments already exist for run {run_id[:8]}... (skipping creation)")
                return

            # Create one segment per pattern step
            # Segment represents the transition from previous step to current step
            from_device = '192.168.99.100'  # Start from D0

            for i, to_device in enumerate(pattern_device_ids):
                conn.execute(
                    '''INSERT INTO segments
                       (run_id, from_device, to_device, sequence, expected_min_time, expected_max_time)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (
                        run_id,
                        from_device,
                        to_device,
                        i,
                        0.0,    # Pattern mode doesn't use time constraints
                        999.9   # Pattern mode doesn't use time constraints
                    )
                )
                # Next segment starts from this device
                from_device = to_device

            print(f"   ✓ Created {len(pattern_device_ids)} pattern segments for run {run_id[:8]}")
    
    def record_touch(self, run_id: str, device_id: str, timestamp: datetime) -> Optional[int]:
        """Record a touch event and update segment timing"""
        with self.get_connection() as conn:
            # Find the segment ending at this device
            segment = conn.execute(
                '''SELECT * FROM segments 
                   WHERE run_id = ? AND to_device = ? AND touch_detected = 0
                   ORDER BY sequence LIMIT 1''',
                (run_id, device_id)
            ).fetchone()
            
            if not segment:
                return None
            
            segment_id = segment['segment_id']

            # Calculate actual time from previous touch
            run = conn.execute('SELECT started_at, timer_start_at FROM runs WHERE run_id = ?', (run_id,)).fetchone()

            # Get previous segment's touch time, or run start time
            prev_segment = conn.execute(
                '''SELECT touch_timestamp FROM segments
                   WHERE run_id = ? AND sequence < ? AND touch_detected = 1
                   ORDER BY sequence DESC LIMIT 1''',
                (run_id, segment['sequence'])
            ).fetchone()

            if prev_segment and prev_segment['touch_timestamp']:
                start_time = datetime.fromisoformat(prev_segment['touch_timestamp'])
            else:
                start_time = datetime.fromisoformat(run['started_at'])

            actual_time = (timestamp - start_time).total_seconds()

            # Calculate cumulative time from timer_start (D0 beep) if available
            cumulative_time = None
            if run['timer_start_at']:
                timer_start = datetime.fromisoformat(run['timer_start_at'])
                cumulative_time = (timestamp - timer_start).total_seconds()

            # Update segment with retry logic for concurrent touches
            import time
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    conn.execute(
                        '''UPDATE segments
                           SET touch_detected = 1, touch_timestamp = ?, actual_time = ?, cumulative_time = ?
                           WHERE segment_id = ?''',
                        (timestamp.isoformat(), actual_time, cumulative_time, segment_id)
                    )
                    break  # Success - exit retry loop
                except sqlite3.OperationalError as e:
                    if 'database is locked' in str(e) and attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))  # 100ms, 200ms, 300ms, 400ms, 500ms
                        continue
                    # On final attempt or different error, log and return None
                    if 'database is locked' in str(e):
                        print(f"⚠️  Database lock persisted after {max_retries} retries - touch not recorded")
                        return None
                    raise

            # Check for alerts
            self.check_segment_alerts(segment_id)

            return segment_id

    def mark_segment_missed(self, segment_id: int):
        """Mark a segment as having a missed touch"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE segments 
                SET alert_raised = 1, 
                    alert_type = 'missed_touch'
                WHERE segment_id = ?
            ''', (segment_id,))
            conn.commit()

    def check_segment_alerts(self, segment_id: int) -> Tuple[bool, Optional[str]]:
        """Check if segment timing triggers alerts"""
        with self.get_connection() as conn:
            segment = conn.execute(
                'SELECT * FROM segments WHERE segment_id = ?',
                (segment_id,)
            ).fetchone()
            
            if not segment or not segment['touch_detected']:
                return False, None
            
            actual = segment['actual_time']
            min_time = segment['expected_min_time']
            max_time = segment['expected_max_time']
            
            alert_type = None
            if actual < min_time:
                alert_type = 'too_fast'
            elif actual > max_time:
                alert_type = 'too_slow'
            
            if alert_type:
                # Retry logic for database locking with increased timeout
                import time
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        conn.execute(
                            'UPDATE segments SET alert_raised = 1, alert_type = ? WHERE segment_id = ?',
                            (alert_type, segment_id)
                        )
                        return True, alert_type
                    except sqlite3.OperationalError as e:
                        if 'database is locked' in str(e) and attempt < max_retries - 1:
                            time.sleep(0.1 * (attempt + 1))  # 100ms, 200ms, 300ms, 400ms backoff
                            continue
                        # On final attempt, log warning and continue instead of crashing
                        if 'database is locked' in str(e):
                            print(f"⚠️  Database lock persisted after {max_retries} retries - alert not saved")
                            return False, None
                        raise  # Re-raise if it's a different error

                return True, alert_type  # Fallback if all retries exhausted
            
            return False, None
    
    def get_run_segments(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all segments for a run"""
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM segments WHERE run_id = ? ORDER BY sequence',
                (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    # ==================== COURSE MIGRATION ====================
    
    def migrate_courses_from_json(self, courses_data: Dict[str, Any]):
        """One-time migration of existing courses to database"""
        courses = courses_data.get('courses', [])
        
        for course in courses:
            name = course['name']
            
            # Check if already exists
            if self.get_course(name):
                print(f"Course '{name}' already exists, skipping")
                continue
            
            # Convert stations to actions format
            stations = course.get('stations', [])
            actions = []
            
            for i, station in enumerate(stations):
                device_id = station['node_id']
                action_type = 'audio_start' if i == 0 else 'touch_checkpoint'
                
                # Last device marks run complete
                marks_complete = (i == len(stations) - 1)
                
                # Second device (Device1) triggers next athlete
                triggers_next = (i == 1)
                
                actions.append({
                    'device_id': device_id,
                    'action': station['action'],
                    'action_type': action_type,
                    'audio_file': f"{station['action']}.mp3",
                    'instruction': station.get('instruction', ''),
                    'min_time': 1.0,  # Default, can be tuned
                    'max_time': 30.0,  # Default, can be tuned
                    'triggers_next_athlete': triggers_next,
                    'marks_run_complete': marks_complete
                })
            
            # Create course
            course_id = self.create_course(
                name=name,
                description=course.get('description', ''),
                course_type='conditioning',
                actions=actions
            )
            
            print(f"Migrated course '{name}' (ID: {course_id}) with {len(actions)} actions")

    def get_coach_preferences(self, coach_id='default_coach'):
        """Get coach preferences"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM coach_preferences WHERE coach_id = ?',
                (coach_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                'distance_unit': 'yards',
                'deployment_timeout': 300,
                'audio_voice': 'male'
            }
    
    def mark_course_deployed(self, session_id):
        """Mark course as deployed in session"""
        from datetime import datetime
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE sessions SET course_deployed = 1, deployment_timestamp = ? WHERE session_id = ?',
                (datetime.utcnow().isoformat(), session_id)
            )
    
    def get_course_actions(self, course_id):
        """Get all actions for a course in sequence order"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                '''SELECT * FROM course_actions 
                   WHERE course_id = ? 
                   ORDER BY sequence''',
                (course_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_builtin_courses(self):
        """Get all built-in courses"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM courses WHERE is_builtin = 1 ORDER BY course_name'
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_custom_courses(self):
        """Get all custom (user-created) courses"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM courses WHERE is_builtin = 0 OR is_builtin IS NULL ORDER BY course_name'
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_course(self, course_id):
        """Delete a course and its actions"""
        with self.get_connection() as conn:
            # Delete actions first
            conn.execute('DELETE FROM course_actions WHERE course_id = ?', (course_id,))
            # Delete course
            conn.execute('DELETE FROM courses WHERE course_id = ?', (course_id,))

    def duplicate_course(self, course_id: int) -> int:
        """Duplicate a course with all its actions, return new course_id"""
        with self.get_connection() as conn:
            # Get original course
            original_course = conn.execute(
                'SELECT * FROM courses WHERE course_id = ?',
                (course_id,)
            ).fetchone()

            if not original_course:
                raise ValueError(f"Course with ID {course_id} not found")

            original_course = dict(original_course)

            # Create new course name with " (Copy)" suffix
            base_name = original_course['course_name']
            new_name = f"{base_name} (Copy)"

            # Check if name already exists and add number if needed
            counter = 2
            while conn.execute('SELECT COUNT(*) FROM courses WHERE course_name = ?', (new_name,)).fetchone()[0] > 0:
                new_name = f"{base_name} (Copy {counter})"
                counter += 1

            # Insert new course with all properties from original
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO courses (
                    course_name, description, course_type, total_devices,
                    mode, category, num_devices, distance_unit, total_distance,
                    diagram_svg, layout_instructions, is_builtin, version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_name,
                original_course.get('description'),
                original_course.get('course_type', 'conditioning'),
                original_course.get('total_devices', 6),
                original_course.get('mode', 'sequential'),
                original_course.get('category', 'Custom'),
                original_course.get('num_devices', 6),
                original_course.get('distance_unit', 'yards'),
                original_course.get('total_distance', 0),
                original_course.get('diagram_svg'),
                original_course.get('layout_instructions'),
                0,  # Never mark copies as built-in
                original_course.get('version', '1.0'),
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))

            new_course_id = cursor.lastrowid

            # Get all actions from original course
            actions = conn.execute(
                'SELECT * FROM course_actions WHERE course_id = ? ORDER BY sequence',
                (course_id,)
            ).fetchall()

            # Copy all actions to new course
            for action in actions:
                action = dict(action)
                cursor.execute('''
                    INSERT INTO course_actions (
                        course_id, sequence, device_id, device_name,
                        action, action_type, audio_file, instruction,
                        min_time, max_time, triggers_next_athlete, marks_run_complete,
                        distance, behavior_config, device_function, detection_method, group_identifier
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_course_id,
                    action['sequence'],
                    action['device_id'],
                    action['device_name'],
                    action['action'],
                    action['action_type'],
                    action['audio_file'],
                    action['instruction'],
                    action['min_time'],
                    action['max_time'],
                    action['triggers_next_athlete'],
                    action['marks_run_complete'],
                    action.get('distance', 0),
                    action.get('behavior_config'),
                    action.get('device_function'),
                    action.get('detection_method'),
                    action.get('group_identifier')
                ))

            return new_course_id
    
    def get_course_by_name(self, course_name):
        """Get course by name"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM courses WHERE course_name = ?',
                (course_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    def create_course_from_import(self, data):
        """Create course from imported JSON data"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO courses (
                    course_name, description, course_type, total_devices,
                    mode, category, num_devices, distance_unit, total_distance,
                    diagram_svg, layout_instructions, is_builtin, version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['course_name'],
                data.get('description', ''),
                data.get('category', 'Custom'),
                data.get('num_devices', 6),
                data.get('mode', 'sequential'),
                data.get('category', 'Custom'),
                data.get('num_devices', 6),
                data.get('distance_unit', 'yards'),
                data.get('total_distance', 0),
                data.get('diagram_svg'),
                data.get('layout_instructions'),
                0,  # Not built-in
                data.get('version', '1.0'),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            course_id = cursor.lastrowid
            
            # Insert actions
            if 'actions' in data:
                for action in data['actions']:
                    conn.execute('''
                        INSERT INTO course_actions (
                            course_id, sequence, device_id, device_name,
                            action, action_type, audio_file, instruction,
                            min_time, max_time, triggers_next_athlete, marks_run_complete,
                            distance, behavior_config, device_function, detection_method, group_identifier
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        course_id,
                        action['sequence'],
                        action['device_id'],
                        action['device_name'],
                        action['action'],
                        action.get('action_type', 'audio_start'),
                        action['audio_file'],
                        action.get('instruction', ''),
                        action.get('min_time', 0.1),
                        action.get('max_time', 30.0),
                        action.get('triggers_next_athlete', 0),
                        action.get('marks_run_complete', 0),
                        action.get('distance', 0),
                        action.get('behavior_config'),
                        action.get('device_function'),
                        action.get('detection_method'),
                        action.get('group_identifier')
                    ))
            
            return course_id

    # ==================== BEEP TEST OPERATIONS ====================

    def create_beep_test_session(self, team_id: str, distance_meters: int,
                                 device_count: int, start_level: int = 1) -> str:
        """Create a new beep test session"""
        session_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO beep_test_sessions (
                    session_id, team_id, distance_meters, device_count, start_level, status
                ) VALUES (?, ?, ?, ?, ?, 'setup')
            ''', (session_id, team_id, distance_meters, device_count, start_level))
        return session_id

    def get_beep_test_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get beep test session by ID"""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM beep_test_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_athlete_to_beep_test(self, session_id: str, athlete_id: str) -> str:
        """Add an athlete to a beep test session"""
        result_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO beep_test_results (
                    result_id, session_id, athlete_id, status
                ) VALUES (?, ?, ?, 'active')
            ''', (result_id, session_id, athlete_id))
        return result_id

    def get_beep_test_athletes(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all athletes in a beep test session with their results"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT
                    r.result_id,
                    r.session_id,
                    r.athlete_id,
                    a.name as athlete_name,
                    r.status,
                    r.level_completed,
                    r.level_failed,
                    r.shuttle_failed_on,
                    r.vo2_max_estimate,
                    r.failed_at
                FROM beep_test_results r
                JOIN athletes a ON r.athlete_id = a.athlete_id
                WHERE r.session_id = ?
                ORDER BY
                    CASE r.status
                        WHEN 'active' THEN 0
                        WHEN 'failed' THEN 1
                        WHEN 'passed' THEN 2
                        ELSE 3
                    END,
                    a.name
            ''', (session_id,)).fetchall()
            return [dict(row) for row in rows]

    def start_beep_test_session(self, session_id: str) -> None:
        """Mark beep test session as active"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE beep_test_sessions
                SET status = 'active', started_at = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), session_id))

    def mark_beep_test_athlete_failed(self, session_id: str, athlete_id: str,
                                     level_failed: int, shuttle_failed_on: int) -> None:
        """Mark an athlete as failed at a specific level"""
        level_completed = max(0, level_failed - 1)
        vo2_max = self._calculate_vo2_max(level_completed)

        with self.get_connection() as conn:
            conn.execute('''
                UPDATE beep_test_results
                SET status = 'failed',
                    level_completed = ?,
                    level_failed = ?,
                    shuttle_failed_on = ?,
                    vo2_max_estimate = ?,
                    failed_at = ?
                WHERE session_id = ? AND athlete_id = ?
            ''', (level_completed, level_failed, shuttle_failed_on, vo2_max,
                  datetime.utcnow().isoformat(), session_id, athlete_id))

    def mark_beep_test_athlete_active(self, session_id: str, athlete_id: str) -> None:
        """Reactivate an athlete (undo failed status)"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE beep_test_results
                SET status = 'active',
                    level_completed = NULL,
                    level_failed = NULL,
                    shuttle_failed_on = NULL,
                    vo2_max_estimate = NULL,
                    failed_at = NULL
                WHERE session_id = ? AND athlete_id = ?
            ''', (session_id, athlete_id))

    def complete_beep_test_session(self, session_id: str, final_level: int) -> None:
        """Complete beep test session - mark remaining active athletes as passed"""
        vo2_max = self._calculate_vo2_max(final_level)

        with self.get_connection() as conn:
            # Mark all still-active athletes as passed at final level
            conn.execute('''
                UPDATE beep_test_results
                SET status = 'passed',
                    level_completed = ?,
                    vo2_max_estimate = ?
                WHERE session_id = ? AND status = 'active'
            ''', (final_level, vo2_max, session_id))

            # Mark session as completed
            conn.execute('''
                UPDATE beep_test_sessions
                SET status = 'completed', completed_at = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), session_id))

    def stop_beep_test_session(self, session_id: str, reason: str = '') -> None:
        """Stop beep test session early"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE beep_test_sessions
                SET status = 'stopped', completed_at = ?, notes = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), reason, session_id))

    def get_team_last_beep_test(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent completed beep test for a team"""
        with self.get_connection() as conn:
            # Get last session
            session = conn.execute('''
                SELECT * FROM beep_test_sessions
                WHERE team_id = ? AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            ''', (team_id,)).fetchone()

            if not session:
                return None

            session_dict = dict(session)

            # Get highest level completed in that session
            max_level = conn.execute('''
                SELECT MAX(level_completed) as max_level
                FROM beep_test_results
                WHERE session_id = ?
            ''', (session_dict['session_id'],)).fetchone()

            session_dict['max_level_completed'] = max_level['max_level'] if max_level else 0

            return session_dict

    def get_athlete_beep_test_history(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get all beep test results for an athlete"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT
                    s.session_id,
                    s.date_time,
                    s.distance_meters,
                    r.status,
                    r.level_completed,
                    r.level_failed,
                    r.vo2_max_estimate
                FROM beep_test_results r
                JOIN beep_test_sessions s ON r.session_id = s.session_id
                WHERE r.athlete_id = ?
                ORDER BY s.date_time DESC
            ''', (athlete_id,)).fetchall()
            return [dict(row) for row in rows]

    def _calculate_vo2_max(self, level_completed: int) -> float:
        """Calculate VO2 max from completed level using Léger formula"""
        if level_completed <= 0:
            return 0.0

        # Speed = 8.5 + (0.5 × (level - 1))
        speed_km_h = 8.5 + (0.5 * (level_completed - 1))

        # VO2_max = (speed × 6.65) - 35.8
        vo2_max = (speed_km_h * 6.65) - 35.8

        return round(vo2_max, 1)

