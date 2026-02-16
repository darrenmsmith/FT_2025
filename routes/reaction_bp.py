#!/usr/bin/env python3
"""
Reaction Sprint Blueprint - Flask routes for Reaction Sprint functionality
Isolated from existing session routes (no impact on Warm-up/Simon Says/Beep Test)
"""

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
import sys

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY
from services.reaction_service import get_reaction_service

# Create blueprint
reaction_bp = Blueprint('reaction', __name__)

# Initialize database
db = DatabaseManager('/opt/data/field_trainer.db')


# ==================== UI ROUTES ====================

@reaction_bp.route('/reaction/monitor/<session_id>')
def monitor(session_id):
    """Reaction Sprint monitor page"""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404

    course = db.get_course(session['course_id'])
    if not course:
        return "Course not found", 404

    team = db.get_team(session['team_id'])
    if not team:
        return "Team not found", 404

    # Get runs for this session
    runs = db.get_session_runs(session_id)

    return render_template('reaction_monitor.html',
                         session=session,
                         course=course,
                         team=team,
                         runs=runs)


# ==================== API ROUTES ====================

@reaction_bp.route('/api/reaction/start/<session_id>', methods=['POST'])
def start_session(session_id):
    """Start Reaction Sprint session"""
    try:
        print(f"🚀 API: /api/reaction/start/{session_id} called")
        service = get_reaction_service()
        result = service.start_session(session_id)
        print(f"   DEBUG: Start result = {result}")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Error starting Reaction Sprint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@reaction_bp.route('/api/reaction/status/<session_id>')
def get_status(session_id):
    """Get current Reaction Sprint session status"""
    try:
        print(f"🔍 API: /api/reaction/status/{session_id} called")

        # Get service status
        service = get_reaction_service()
        service_status = service.get_session_status()
        print(f"   DEBUG: Service status = {service_status}")

        # Get session data from database
        session = db.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        # Get runs with segments
        runs = db.get_session_runs(session_id)
        for run in runs:
            run['segments'] = db.get_run_segments(run['run_id'])

        return jsonify({
            'session': session,
            'runs': runs,
            'service_status': service_status
        })

    except Exception as e:
        print(f"❌ Error getting Reaction Sprint status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@reaction_bp.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    """Stop Reaction Sprint session early"""
    try:
        data = request.json
        reason = data.get('reason', 'Stopped by coach')

        # Update session status
        with db.get_connection() as conn:
            conn.execute('''
                UPDATE sessions
                SET status = 'incomplete',
                    completed_at = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), session_id))

        # Clear service state
        service = get_reaction_service()
        service.session_state.clear()

        # Deactivate course
        print(f"🏁 Deactivating course...")
        REGISTRY.course_status = "Inactive"

        # Send stop commands to all devices
        session_data = db.get_session(session_id)
        if session_data:
            course_data = db.get_course(session_data['course_id'])
            actions = db.get_course_actions(session_data['course_id'])

            for action in actions:
                device_id = action['device_id']
                try:
                    REGISTRY.send_to_node(device_id, {
                        "cmd": "stop",
                        "action": None,
                        "course_status": "Inactive"
                    })
                    # Set to amber for visual feedback
                    if device_id != '192.168.99.100':
                        REGISTRY.set_led(device_id, 'solid_amber')
                except Exception as e:
                    print(f"⚠️  Failed to stop {device_id}: {e}")

        print(f"✅ Course deactivated")

        return jsonify({'success': True})

    except Exception as e:
        print(f"❌ Error stopping Reaction Sprint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
