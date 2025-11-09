"""
Athletic Training Platform - Extended Database Models
Adds performance tracking tables to existing field_trainer.db

NEW TABLES (11 total):
- coaches, athlete_profiles, emergency_contacts
- performance_history, personal_records, achievements
- media_gallery, training_programs, program_assignments
- session_notes_extended, team_coaches, team_rankings

EXISTING TABLES (preserved unchanged):
- teams, athletes, courses, sessions, runs, segments
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any
import json
import uuid


class ExtendedDatabaseManager:
    """Extends existing field_trainer database with athletic training features"""
    
    def __init__(self, db_path: str = '/opt/data/field_trainer.db'):
        self.db_path = db_path
        self.init_extended_tables()
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_extended_tables(self):
        """Create new tables (safe - only if not exists)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Performance History - every run recorded
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_history (
                record_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                run_id TEXT,
                session_id TEXT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_unit TEXT,
                is_personal_record BOOLEAN DEFAULT 0,
                course_id INTEGER,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                segment_data TEXT,
                
                FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id) ON DELETE CASCADE,
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        ''')
        
        # Personal Records - best times
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personal_records (
                pr_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                current_best REAL NOT NULL,
                metric_unit TEXT,
                achieved_at TIMESTAMP NOT NULL,
                run_id TEXT,
                previous_best REAL,
                improvement REAL,
                
                UNIQUE(athlete_id, metric_name),
                FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id) ON DELETE CASCADE
            )
        ''')
        
        # Achievements/Badges
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                badge_type TEXT NOT NULL,
                badge_name TEXT NOT NULL,
                description TEXT,
                criteria TEXT,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_id TEXT,
                metric_value REAL,
                
                FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_performance_athlete 
            ON performance_history(athlete_id, metric_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_personal_records_athlete 
            ON personal_records(athlete_id)
        ''')
        
        conn.commit()
        conn.close()
    
    # ==================== PERFORMANCE METHODS ====================
    
    def record_performance(self, athlete_id: str, metric_name: str, 
                          metric_value: float, **kwargs) -> tuple:
        """
        Record a performance metric
        Returns: (record_id, is_new_pr)
        """
        record_id = str(uuid.uuid4())
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if this is a new PR (lower is better for time metrics)
        cursor.execute('''
            SELECT current_best FROM personal_records 
            WHERE athlete_id = ? AND metric_name = ?
        ''', (athlete_id, metric_name))
        
        pr_row = cursor.fetchone()
        is_pr = False
        
        metric_unit = kwargs.get('metric_unit', 'seconds')
        if metric_unit in ['seconds', 'milliseconds']:
            is_pr = (pr_row is None) or (metric_value < pr_row[0])
        else:
            is_pr = (pr_row is None) or (metric_value > pr_row[0])
        
        # Record performance
        cursor.execute('''
            INSERT INTO performance_history (
                record_id, athlete_id, run_id, session_id, metric_name,
                metric_value, metric_unit, is_personal_record, course_id,
                notes, segment_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_id, athlete_id,
            kwargs.get('run_id'), kwargs.get('session_id'),
            metric_name, metric_value, metric_unit, is_pr,
            kwargs.get('course_id'), kwargs.get('notes'),
            json.dumps(kwargs.get('segment_data', {}))
        ))
        
        # Update PR if needed
        if is_pr:
            previous_best = pr_row[0] if pr_row else None
            improvement = (previous_best - metric_value) if previous_best else None
            
            cursor.execute('''
                INSERT OR REPLACE INTO personal_records (
                    pr_id, athlete_id, metric_name, current_best, metric_unit,
                    achieved_at, run_id, previous_best, improvement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), athlete_id, metric_name, metric_value,
                metric_unit, datetime.now(), kwargs.get('run_id'),
                previous_best, improvement
            ))
        
        conn.commit()
        conn.close()
        
        return record_id, is_pr
    
    def get_athlete_performance_history(self, athlete_id: str, 
                                       metric_name: Optional[str] = None,
                                       limit: int = 100) -> List[Dict]:
        """Get athlete's performance history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if metric_name:
            cursor.execute('''
                SELECT * FROM performance_history 
                WHERE athlete_id = ? AND metric_name = ?
                ORDER BY recorded_at DESC
                LIMIT ?
            ''', (athlete_id, metric_name, limit))
        else:
            cursor.execute('''
                SELECT * FROM performance_history 
                WHERE athlete_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
            ''', (athlete_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_athlete_prs(self, athlete_id: str) -> List[Dict]:
        """Get all personal records for athlete"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM personal_records 
            WHERE athlete_id = ?
            ORDER BY achieved_at DESC
        ''', (athlete_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def award_achievement(self, athlete_id: str, badge_type: str, 
                         badge_name: str, **kwargs) -> str:
        """Award achievement badge to athlete"""
        achievement_id = str(uuid.uuid4())
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO achievements (
                achievement_id, athlete_id, badge_type, badge_name,
                description, criteria, run_id, metric_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            achievement_id, athlete_id, badge_type, badge_name,
            kwargs.get('description'), kwargs.get('criteria'),
            kwargs.get('run_id'), kwargs.get('metric_value')
        ))
        
        conn.commit()
        conn.close()
        
        return achievement_id
    
    def get_athlete_achievements(self, athlete_id: str) -> List[Dict]:
        """Get all achievements for athlete"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM achievements 
            WHERE athlete_id = ?
            ORDER BY earned_at DESC
        ''', (athlete_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]


def initialize_extended_db(db_path: str = '/opt/data/field_trainer.db'):
    """Initialize extended database tables"""
    manager = ExtendedDatabaseManager(db_path)
    print("✅ Extended database initialized")
    return manager


if __name__ == '__main__':
    # Test initialization
    manager = initialize_extended_db()
    print("Extended tables ready!")
