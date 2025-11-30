#!/usr/bin/env python3
"""
Sessions Blueprint - Session setup, monitoring, and control
Extracted from coach_interface.py during Phase 1 refactoring
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from typing import Optional
import sys

# Add field_trainer to path
sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY

# Import session service and state
from services.session_service import SessionService
from models.session_state import active_session_state

sessions_bp = Blueprint('sessions', __name__, url_prefix='/session')

# Initialize database (shared with main app)
db = DatabaseManager('/opt/data/field_trainer.db')

# Initialize session service
session_service = SessionService(db, REGISTRY, active_session_state)


# ==================== SESSION SETUP ====================

@sessions_bp.route('/setup')
def session_setup():
    """Session setup page - select team, course, order athletes"""
    teams = db.get_all_teams()
    courses = db.get_all_courses()
    return render_template('session_setup.html', teams=teams, courses=courses)


@sessions_bp.route('/create', methods=['POST'])
def create_session():
    """Create session with athlete queue"""
    try:
        data = request.get_json()
        team_id = data['team_id']
        course_id = data['course_id']
        athlete_queue = data['athlete_queue']  # List of athlete_ids in order
        audio_voice = data.get('audio_voice', 'male')
        
        # Create session
        session_id = db.create_session(
            team_id=team_id,
            course_id=course_id,
            athlete_queue=athlete_queue,
            audio_voice=audio_voice
        )
        
        # Store in global state
        active_session_state['session_id'] = session_id

        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': url_for('sessions.session_setup_cones', session_id=session_id)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@sessions_bp.route('/<session_id>/setup-cones')
def session_setup_cones(session_id):
    """Cone setup verification page"""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404
    
    course = db.get_course(session['course_id'])
    if not course:
        return "Course not found", 404
    
    # Get timeout from preferences
    prefs = db.get_coach_preferences()
    timeout_minutes = prefs.get('deployment_timeout', 300) // 60
    
    return render_template(
        'session_setup_cones.html',
        session_id=session_id,
        course=course,
        timeout_minutes=timeout_minutes
    )


@sessions_bp.route('/<session_id>/athlete/<run_id>/absent', methods=['POST'])
def mark_athlete_absent(session_id, run_id):
    """Mark athlete as absent (remove from queue but note absence)"""
    try:
        db.update_run_status(run_id, 'absent')
        
        run = db.get_run(run_id)
        REGISTRY.log(f"Athlete marked absent: {run.get('athlete_name', 'Unknown')}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': url_for('sessions.session_setup_cones', session_id=session_id)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== SESSION MONITORING ====================

@sessions_bp.route('/<session_id>/monitor')
def session_monitor(session_id):
    """Session monitoring page"""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404
    
    team = db.get_team(session['team_id'])
    course = db.get_course(session['course_id'])
    
    return render_template(
        'session_monitor.html',
        session=session,
        team=team,
        course=course
    )


@sessions_bp.route('/<session_id>/status')
def session_status(session_id):
    """API: Get current session status"""
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Get runs with segment details
    runs_with_segments = []
    for run in session['runs']:
        segments = db.get_run_segments(run['run_id'])
        run['segments'] = segments
        runs_with_segments.append(run)
    
    session['runs'] = runs_with_segments
    
    return jsonify({
        'session': session,
        'active_run': active_session_state.get('current_run_id'),
        'waiting_for_device': active_session_state.get('waiting_for_device')
    })


# ==================== SESSION CONTROL ====================

@sessions_bp.route('/<session_id>/start', methods=['POST'])
def start_session(session_id):
    """GO button - start session and first athlete"""
    try:
        result = session_service.start_session(session_id)
        return jsonify(result)
    except Exception as e:
        REGISTRY.log(f"Session start error: {e}", level="error")
        return jsonify({'success': False, 'error': str(e)}), 400


@sessions_bp.route('/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    """Stop Session button - deactivate course and mark session incomplete"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Stopped by coach')
        
        result = session_service.stop_session(session_id, reason)
        return jsonify(result)
    except Exception as e:
        print(f"❌ Stop session error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== COURSE DEPLOYMENT ====================

@sessions_bp.route('/<session_id>/prepare-course', methods=['POST'])
def prepare_course(session_id):
    """Set all course devices to AMBER for verification"""
    try:
        session = db.get_session(session_id)
        course = db.get_course(session['course_id'])
        
        # Get devices from course_actions
        actions = db.get_course_actions(course['course_id'])
        devices = []
        device_ids_seen = set()
        
        for action in actions:
            device_id = action['device_id']
            if device_id not in device_ids_seen:
                devices.append({'device_id': device_id, 'device_name': action['device_name']})
                device_ids_seen.add(device_id)
        
        # Set all devices to AMBER using REGISTRY
        for device in devices:
            try:
                REGISTRY.set_led(device['device_id'], pattern='solid_amber')
            except Exception as e:
                print(f"⚠️  Failed to set {device['device_id']} to amber: {e}")
        
        REGISTRY.log(f"Course prepared for deployment: {course['course_name']}")
        
        return jsonify({
            'success': True,
            'devices': devices
        })
    except Exception as e:
        print(f"❌ Prepare course error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@sessions_bp.route('/<session_id>/deploy-course', methods=['POST'])
def deploy_course(session_id):
    """Deploy course - set devices to GREEN and activate"""
    try:
        session = db.get_session(session_id)
        course = db.get_course(session['course_id'])
        
        # Get devices from course_actions
        actions = db.get_course_actions(course['course_id'])
        devices = []
        device_ids_seen = set()
        
        for action in actions:
            device_id = action['device_id']
            if device_id not in device_ids_seen:
                devices.append({'device_id': device_id, 'device_name': action['device_name']})
                device_ids_seen.add(device_id)
        
        # Deploy the course first (loads into REGISTRY)
        course_name = course['course_name']
        import requests
        try:
            deploy_resp = requests.post(
                'http://localhost:5000/api/course/deploy',
                json={'course_name': course_name},
                timeout=5
            )
            print(f"Deploy API: {deploy_resp.status_code}")
        except Exception as e:
            print(f"Deploy API error: {e}")
        
        # Activate course using existing REGISTRY method
        REGISTRY.activate_course(course_name)
        
        # Set all devices to GREEN
        for device in devices:
            try:
                REGISTRY.set_led(device['device_id'], pattern='solid_green')
            except Exception as e:
                print(f"⚠️  Failed to set {device['device_id']} to green: {e}")
        
        # Mark course as deployed
        db.mark_course_deployed(session_id)
        
        REGISTRY.log(f"Course deployed: {course['course_name']}")
        
        return jsonify({
            'success': True,
            'devices': devices,
            'deployed': True
        })
    except Exception as e:
        print(f"❌ Deploy course error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== SESSION HISTORY ====================
# Note: /sessions route is in main coach_interface.py for simplicity


@sessions_bp.route('/<session_id>/results')
def session_results(session_id):
    """View completed session results"""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404
    
    course = db.get_course(session['course_id'])
    team = db.get_team(session['team_id'])
    
    # Get all runs with segments
    runs = session['runs']
    for run in runs:
        run['segments'] = db.get_run_segments(run['run_id'])
    
    return render_template(
        'session_results.html',
        session=session,
        course=course,
        team=team,
        runs=runs
    )


@sessions_bp.route('/<session_id>/repeat', methods=['POST'])
def repeat_session(session_id):
    """Repeat session - create new session with same team, course, and athletes"""
    try:
        # Get original session
        session = db.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Only allow repeating completed or incomplete sessions
        if session['status'] not in ['completed', 'incomplete', 'failed']:
            return jsonify({'success': False, 'error': f'Cannot repeat {session["status"]} session'}), 400

        # Extract session parameters
        team_id = session['team_id']
        course_id = session['course_id']
        audio_voice = session.get('audio_voice', 'male')

        # Get athlete queue from original runs (exclude absent athletes)
        athlete_queue = []
        for run in session['runs']:
            if run['status'] != 'absent':
                athlete_queue.append(run['athlete_id'])

        if not athlete_queue:
            return jsonify({'success': False, 'error': 'No athletes to repeat session with'}), 400

        # Create new session
        new_session_id = db.create_session(
            team_id=team_id,
            course_id=course_id,
            athlete_queue=athlete_queue,
            audio_voice=audio_voice
        )

        # Store in global state
        active_session_state['session_id'] = new_session_id

        REGISTRY.log(f"Session {session_id[:8]} repeated as {new_session_id[:8]}")

        return jsonify({
            'success': True,
            'new_session_id': new_session_id,
            'redirect_url': url_for('sessions.session_setup_cones', session_id=new_session_id)
        })

    except Exception as e:
        print(f"❌ Repeat session error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


@sessions_bp.route('/<session_id>/export')
def export_session(session_id):
    """Export session results as CSV"""
    import csv
    from io import StringIO
    from flask import Response

    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404

    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Athlete Name', 'Jersey Number', 'Queue Position',
        'Status', 'Total Time', 'Started At', 'Completed At'
    ])

    # Rows
    for run in session['runs']:
        writer.writerow([
            run['athlete_name'],
            run.get('jersey_number', ''),
            run['queue_position'],
            run['status'],
            run.get('total_time', ''),
            run.get('started_at', ''),
            run.get('completed_at', '')
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=session_{session_id[:8]}.csv'}
    )
