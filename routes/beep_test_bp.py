#!/usr/bin/env python3
"""
Beep Test Blueprint - Flask routes for Beep Test functionality
Completely isolated from existing session routes (no impact on Warm-up/Simon Says)
"""

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
import sys

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY
from services.beep_test_service import BeepTestService

# Create blueprint
beep_test_bp = Blueprint('beep_test', __name__)

# Initialize database and service
db = DatabaseManager('/opt/data/field_trainer.db')
beep_service = BeepTestService(db, REGISTRY)


# ==================== UI ROUTES ====================

@beep_test_bp.route('/beep-test/setup')
def setup():
    """Beep test setup page"""
    teams = db.get_all_teams()
    return render_template('beep_test_setup.html', teams=teams)


@beep_test_bp.route('/beep-test/monitor/<session_id>')
def monitor(session_id):
    """Beep test monitor page"""
    session = db.get_beep_test_session(session_id)
    if not session:
        return "Session not found", 404

    return render_template('beep_test_monitor.html', session=session)


@beep_test_bp.route('/beep-test/results/<session_id>')
def results(session_id):
    """Beep test results page"""
    # Get session from regular sessions table (integrated approach)
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404

    # Parse beep test config from pattern_config JSON field
    import json
    config = {}
    if session.get('pattern_config'):
        try:
            config = json.loads(session['pattern_config'])
        except:
            pass

    # Add config fields to session dict for template compatibility
    session['distance_meters'] = config.get('distance_meters', 20)
    session['start_level'] = config.get('start_level', 1)
    session['device_count'] = config.get('device_count', 4)
    session['date_time'] = session.get('created_at')  # Map created_at to date_time for template

    # Get team
    team = db.get_team(session['team_id'])

    # Get results
    results_list = db.get_beep_test_athletes(session_id)

    # Calculate statistics
    total_athletes = len(results_list)
    passed_count = len([r for r in results_list if r['status'] == 'passed'])
    failed_count = len([r for r in results_list if r['status'] == 'failed'])

    # Highest level completed
    levels = [r['level_completed'] for r in results_list if r['level_completed']]
    highest_level = max(levels) if levels else 0

    # Average VO2 max
    vo2_values = [r['vo2_max_estimate'] for r in results_list if r['vo2_max_estimate']]
    avg_vo2_max = sum(vo2_values) / len(vo2_values) if vo2_values else 0

    return render_template(
        'beep_test_results.html',
        session=session,
        team=team,
        results=results_list,
        total_athletes=total_athletes,
        passed_count=passed_count,
        failed_count=failed_count,
        highest_level=highest_level,
        avg_vo2_max=avg_vo2_max,
        get_vo2_rating=get_vo2_rating
    )


# ==================== API ROUTES ====================

@beep_test_bp.route('/api/beep-test/create-session', methods=['POST'])
def api_create_session():
    """Create a new beep test session"""
    data = request.json

    try:
        # Create session
        session_id = db.create_beep_test_session(
            team_id=data['team_id'],
            distance_meters=data['distance_meters'],
            device_count=data['device_count'],
            start_level=data['start_level']
        )

        # Add athletes
        for athlete_id in data['athlete_ids']:
            db.add_athlete_to_beep_test(session_id, athlete_id)

        return jsonify({
            'success': True,
            'session_id': session_id
        })

    except Exception as e:
        print(f"Error creating beep test session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@beep_test_bp.route('/api/beep-test/start', methods=['POST'])
def api_start():
    """Start a beep test"""
    data = request.json
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'success': False, 'error': 'session_id required'}), 400

    result = beep_service.start_beep_test(session_id)
    return jsonify(result)


@beep_test_bp.route('/api/beep-test/status/<session_id>')
def api_status(session_id):
    """Get current beep test status"""
    state = beep_service.get_current_state()
    return jsonify(state)


@beep_test_bp.route('/api/beep-test/athletes/<session_id>')
def api_athletes(session_id):
    """Get athletes in beep test session"""
    athletes = db.get_beep_test_athletes(session_id)
    return jsonify(athletes)


@beep_test_bp.route('/api/beep-test/toggle-athlete', methods=['POST'])
def api_toggle_athlete():
    """Toggle athlete active/failed status"""
    data = request.json

    result = beep_service.toggle_athlete_status(
        session_id=data['session_id'],
        athlete_id=data['athlete_id'],
        current_status=data['current_status']
    )

    return jsonify(result)


@beep_test_bp.route('/api/beep-test/stop', methods=['POST'])
def api_stop():
    """Stop beep test early"""
    data = request.json

    result = beep_service.stop_test_early(
        session_id=data['session_id'],
        reason=data.get('reason', 'Stopped by coach')
    )

    return jsonify(result)


@beep_test_bp.route('/api/beep-test/last-test/<team_id>')
def api_last_test(team_id):
    """Get last beep test for a team (for Continue feature)"""
    last_test = db.get_team_last_beep_test(team_id)

    if last_test:
        return jsonify(last_test)
    else:
        return jsonify({'max_level_completed': 0}), 404


# ==================== HELPER FUNCTIONS ====================

def get_vo2_rating(vo2_max):
    """
    Get VO2 max rating based on value.
    Returns: {'label': str, 'color': str}
    """
    if vo2_max < 35:
        return {'label': 'Poor', 'color': 'danger'}
    elif vo2_max < 40:
        return {'label': 'Fair', 'color': 'warning'}
    elif vo2_max < 45:
        return {'label': 'Average', 'color': 'info'}
    elif vo2_max < 50:
        return {'label': 'Good', 'color': 'primary'}
    elif vo2_max < 55:
        return {'label': 'Excellent', 'color': 'success'}
    else:
        return {'label': 'Superior', 'color': 'dark'}


# Template filter for datetime formatting
@beep_test_bp.app_template_filter('format_datetime')
def format_datetime(value):
    """Format datetime for display"""
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except:
            return value
    else:
        dt = value

    return dt.strftime('%Y-%m-%d %H:%M')
