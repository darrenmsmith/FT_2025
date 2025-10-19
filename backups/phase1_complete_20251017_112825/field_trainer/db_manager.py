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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
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
    
    # ==================== TEAM OPERATIONS ====================
    
    def create_team(self, name: str, age_group: Optional[str] = None) -> str:
        """Create a new team, return team_id"""
        team_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                'INSERT INTO teams (team_id, name, age_group) VALUES (?, ?, ?)',
                (team_id, name, age_group)
            )
        return team_id
    
    def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get team by ID"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM teams WHERE team_id = ?', (team_id,)).fetchone()
            return dict(row) if row else None
    
    def get_all_teams(self) -> List[Dict[str, Any]]:
        """Get all teams"""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM teams ORDER BY name').fetchall()
            return [dict(row) for row in rows]
    
    def update_team(self, team_id: str, **kwargs):
        """Update team fields"""
        allowed_fields = {'name', 'age_group'}
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
                     actions: List[Dict[str, Any]]) -> int:
        """Create course with actions, return course_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create course
            cursor.execute(
                '''INSERT INTO courses (course_name, description, course_type, total_devices)
                   VALUES (?, ?, ?, ?)''',
                (name, description, course_type, len(actions))
            )
            course_id = cursor.lastrowid
            
            # Create actions
            for seq, action_data in enumerate(actions):
                device_id = action_data['device_id']
                cursor.execute(
                    '''INSERT INTO course_actions 
                       (course_id, sequence, device_id, device_name, action, action_type, 
                        audio_file, instruction, min_time, max_time, triggers_next_athlete, marks_run_complete)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        course_id, seq, device_id, DEVICE_NAMES.get(device_id),
                        action_data['action'], action_data.get('action_type', 'touch_checkpoint'),
                        action_data.get('audio_file'), action_data.get('instruction'),
                        action_data.get('min_time', 1.0), action_data.get('max_time', 30.0),
                        action_data.get('triggers_next_athlete', False),
                        action_data.get('marks_run_complete', False)
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
        allowed_fields = {'course_name', 'description', 'course_type'}
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
                      audio_voice: str = 'male') -> str:
        """Create session with athlete queue, return session_id"""
        session_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            # Create session
            conn.execute(
                '''INSERT INTO sessions (session_id, team_id, course_id, status, audio_voice)
                   VALUES (?, ?, ?, 'setup', ?)''',
                (session_id, team_id, course_id, audio_voice)
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

    def complete_run(self, run_id: str, timestamp: Optional[datetime] = None, total_time: Optional[float] = None):
        """Mark run as completed"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE runs SET status = ?, completed_at = ?, total_time = ? WHERE run_id = ?',
                ('completed', timestamp.isoformat(), total_time, run_id)
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
            run = conn.execute('SELECT started_at FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            
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
            
            # Update segment
            conn.execute(
                '''UPDATE segments 
                   SET touch_detected = 1, touch_timestamp = ?, actual_time = ?
                   WHERE segment_id = ?''',
                (timestamp.isoformat(), actual_time, segment_id)
            )
            
            # Check for alerts
            self.check_segment_alerts(segment_id)
            
            return segment_id
    
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
                conn.execute(
                    'UPDATE segments SET alert_raised = 1, alert_type = ? WHERE segment_id = ?',
                    (alert_type, segment_id)
                )
                return True, alert_type
            
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
