"""
Dashboard Routes
Handles the main dashboard view with stats and recent activity
"""

from flask import Blueprint, render_template
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '/opt/field_trainer')
sys.path.insert(0, '/opt/field_trainer/athletic_platform')

from field_trainer.db_manager import DatabaseManager
from models_extended import ExtendedDatabaseManager

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    """Main dashboard view"""
    
    db = DatabaseManager('/opt/data/field_trainer.db')
    ext_db = ExtendedDatabaseManager('/opt/data/field_trainer.db')
    
    # Get quick stats
    stats = get_dashboard_stats(db, ext_db)
    
    # Get recent activity (last 10 runs)
    recent_activity = get_recent_activity(db, ext_db, limit=10)
    
    # Get device status
    devices = get_device_status()
    
    # Get top performers
    top_performers = get_top_performers(db, ext_db, limit=5)
    
    # System info
    uptime = get_system_uptime()
    db_size = get_database_size()
    
    return render_template('dashboard/index.html',
                         stats=stats,
                         recent_activity=recent_activity,
                         devices=devices,
                         top_performers=top_performers,
                         uptime=uptime,
                         db_size=db_size)


def get_dashboard_stats(db, ext_db):
    """Calculate dashboard statistics"""
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Total athletes
        cursor.execute("SELECT COUNT(DISTINCT athlete_id) FROM athletes")
        total_athletes = cursor.fetchone()[0] or 0
        
        # Total teams
        cursor.execute("SELECT COUNT(DISTINCT team_id) FROM teams")
        total_teams = cursor.fetchone()[0] or 0
        
        # Sessions today
        today = datetime.now().date()
        cursor.execute("""
            SELECT COUNT(*) FROM sessions 
            WHERE DATE(created_at) = ?
        """, (today,))
        sessions_today = cursor.fetchone()[0] or 0
        
        # Runs today
        cursor.execute("""
            SELECT COUNT(*) FROM runs 
            WHERE DATE(completed_at) = ? AND status = 'completed'
        """, (today,))
        runs_today = cursor.fetchone()[0] or 0
    
    # PRs this week
    week_ago = datetime.now() - timedelta(days=7)
    with ext_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM personal_records 
            WHERE achieved_at >= ?
        """, (week_ago,))
        prs_this_week = cursor.fetchone()[0] or 0
    
    # Device status (mock for now - replace with real device check)
    devices_online = 4
    total_devices = 5
    
    return {
        'total_athletes': total_athletes,
        'total_teams': total_teams,
        'sessions_today': sessions_today,
        'runs_today': runs_today,
        'prs_this_week': prs_this_week,
        'devices_online': devices_online,
        'total_devices': total_devices
    }


def get_recent_activity(db, ext_db, limit=10):
    """Get recent completed runs with PR information"""
    
    activities = []
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.run_id,
                r.athlete_id,
                r.course_id,
                r.total_time,
                r.completed_at,
                a.name as athlete_name,
                c.course_name
            FROM runs r
            JOIN athletes a ON r.athlete_id = a.athlete_id
            JOIN courses c ON r.course_id = c.course_id
            WHERE r.status = 'completed' AND r.total_time IS NOT NULL
            ORDER BY r.completed_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
    
    # Check if each run was a PR
    for row in rows:
        run_id = row[0]
        athlete_id = row[1]
        completed_at = datetime.fromisoformat(row[4]) if row[4] else None
        
        # Check if this run was a PR
        is_pr = False
        improvement = None
        
        with ext_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_personal_record FROM performance_history
                WHERE run_id = ?
            """, (run_id,))
            pr_row = cursor.fetchone()
            if pr_row:
                is_pr = bool(pr_row[0])
        
        # Calculate time ago
        time_ago = get_relative_time(completed_at) if completed_at else 'Unknown'
        
        activities.append({
            'athlete_name': row[5],
            'course_name': row[6],
            'total_time': row[3],
            'completed_at': completed_at.isoformat() if completed_at else None,
            'time_ago': time_ago,
            'is_pr': is_pr,
            'improvement': improvement
        })
    
    return activities


def get_device_status():
    """Get status of training devices"""
    # TODO: Integrate with REGISTRY to get real device status
    return [
        {'name': 'Device 1', 'ip': '192.168.99.101', 'online': True},
        {'name': 'Device 2', 'ip': '192.168.99.102', 'online': True},
        {'name': 'Device 3', 'ip': '192.168.99.103', 'online': True},
        {'name': 'Device 4', 'ip': '192.168.99.104', 'online': True},
        {'name': 'Device 5', 'ip': '192.168.99.105', 'online': False},
    ]


def get_top_performers(db, ext_db, limit=5):
    """Get athletes with most PRs this month"""
    
    month_ago = datetime.now() - timedelta(days=30)
    
    with ext_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                athlete_id,
                COUNT(*) as pr_count
            FROM personal_records
            WHERE achieved_at >= ?
            GROUP BY athlete_id
            ORDER BY pr_count DESC
            LIMIT ?
        """, (month_ago, limit))
        
        pr_data = cursor.fetchall()
    
    performers = []
    for athlete_id, pr_count in pr_data:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.name, t.team_name
                FROM athletes a
                LEFT JOIN teams t ON a.team_id = t.team_id
                WHERE a.athlete_id = ?
            """, (athlete_id,))
            
            row = cursor.fetchone()
            if row:
                performers.append({
                    'name': row[0],
                    'team_name': row[1] or 'No Team',
                    'prs_count': pr_count
                })
    
    return performers


def get_system_uptime():
    """Get system uptime"""
    # TODO: Calculate actual uptime from service start
    return "2h 15m"


def get_database_size():
    """Get database file size"""
    import os
    try:
        size_bytes = os.path.getsize('/opt/data/field_trainer.db')
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.1f} MB"
    except:
        return "Unknown"


def get_relative_time(dt):
    """Convert datetime to relative time string"""
    if not dt:
        return "Unknown"
    
    now = datetime.now()
    if dt.tzinfo:
        # Make now timezone aware
        from datetime import timezone
        now = now.replace(tzinfo=timezone.utc)
    
    diff = (now - dt).total_seconds()
    
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff / 60)}m ago"
    elif diff < 86400:
        return f"{int(diff / 3600)}h ago"
    elif diff < 604800:
        return f"{int(diff / 86400)}d ago"
    else:
        return dt.strftime("%b %d")
