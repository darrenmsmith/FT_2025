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

    # Get course details to include mode
    course = db.get_course(session['course_id'])
    course_mode = course.get('mode', 'sequential') if course else 'sequential'

    # Get pattern_length from DATABASE session record if pattern mode
    pattern_length = None
    if course_mode == 'pattern':
        # Read from database pattern_config (for "Continue to n" sessions)
        # or fall back to session_state (for normal sessions)
        import json
        session_pattern_config = session.get('pattern_config')
        if session_pattern_config:
            # Session has database-stored pattern_config (from "Continue to n")
            try:
                config = json.loads(session_pattern_config)
                pattern_length = config.get('pattern_length', 4)
            except (json.JSONDecodeError, TypeError):
                pass

        if pattern_length is None:
            # Fall back to session_state for normal sessions
            pattern_config = session_service.session_state.get('pattern_config', {})
            pattern_length = pattern_config.get('pattern_length', 4)

    # Get runs with segment details
    runs_with_segments = []
    for run in session['runs']:
        segments = db.get_run_segments(run['run_id'])
        run['segments'] = segments
        runs_with_segments.append(run)

    session['runs'] = runs_with_segments

    # Get pattern data for pattern mode (to show step-by-step layout)
    pattern_data = None
    if course_mode == 'pattern' and session_service.session_state.get('active_runs'):
        # Get pattern from ACTIVE athlete's run_info (each athlete has unique pattern!)
        for run_id, run_info in session_service.session_state.get('active_runs', {}).items():
            if run_info.get('is_active', False) and 'pattern_data' in run_info:
                pattern_data = run_info['pattern_data']
                break

    return jsonify({
        'session': session,
        'course_mode': course_mode,  # NEW: Include course mode for frontend
        'pattern_length': pattern_length,  # NEW: Pattern length for "Continue to n" button
        'pattern_data': pattern_data,  # NEW: Pattern sequence for step-based layout
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
    print(f"\n{'='*80}")
    print(f"🔵 SESSIONS_BP.DEPLOY_COURSE CALLED (Blueprint route)")
    print(f"   Session ID: {session_id}")
    print(f"{'='*80}\n")
    try:
        session = db.get_session(session_id)
        course = db.get_course(session['course_id'])
        print(f"   Course: {course['course_name']}")
        print(f"   Mode: {course.get('mode')}")

        # For Simon Says courses, check if pattern_length was specified
        if course.get('mode') == 'pattern':
            from flask import request
            import json

            request_data = request.get_json() or {}
            pattern_length = request_data.get('pattern_length')

            if pattern_length:
                print(f"   📏 Pattern length specified: {pattern_length} cones")

                # Get course-level defaults for other settings
                first_action = db.get_course_actions(course['course_id'])[0]
                course_config = {}
                if first_action.get('behavior_config'):
                    try:
                        course_config = json.loads(first_action['behavior_config']) if isinstance(first_action['behavior_config'], str) else first_action['behavior_config']
                    except:
                        pass

                # Count number of colored devices in course
                colored_device_count = len([a for a in db.get_course_actions(course['course_id']) if a['device_id'] != '192.168.99.100'])

                # Force allow_repeats=True if pattern_length > number of devices
                # (Can't have 6-step pattern with 4 devices without repeats!)
                allow_repeats = course_config.get('allow_repeats', True)
                if int(pattern_length) > colored_device_count:
                    allow_repeats = True
                    print(f"   ⚠️  Pattern length ({pattern_length}) > devices ({colored_device_count}), forcing allow_repeats=True")

                # Create pattern_config override
                pattern_config = {
                    'pattern_length': int(pattern_length),
                    'allow_repeats': allow_repeats,
                    'error_feedback_duration': course_config.get('error_feedback_duration', 4.0),
                    'debounce_ms': course_config.get('debounce_ms', 1000)
                }

                # Update session in database
                with db.get_connection() as conn:
                    conn.execute('''
                        UPDATE sessions
                        SET pattern_config = ?
                        WHERE session_id = ?
                    ''', (json.dumps(pattern_config), session_id))

                print(f"   ✅ Pattern config saved to session: {pattern_config}")

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

        # Check if this is a Simon Says course (mode='pattern')
        is_simon_says = course.get('mode') == 'pattern'

        if is_simon_says:
            # Simon Says: Set cones directly to assigned colors
            import time
            import json

            print("📍 Simon Says Deploy:")
            print("   Setting cones to assigned colors...")

            # Set each device to its assigned color from behavior_config
            for action in actions:
                device_id = action['device_id']
                behavior_config = action.get('behavior_config', '')

                # Skip home base (Device 0)
                if device_id == '192.168.99.100':
                    continue

                # Parse behavior_config as JSON: {"color": "red"}
                color = None
                if behavior_config:
                    try:
                        if isinstance(behavior_config, str):
                            config_dict = json.loads(behavior_config)
                        else:
                            config_dict = behavior_config
                        color = config_dict.get('color')
                    except (json.JSONDecodeError, AttributeError) as e:
                        print(f"   ⚠️  Failed to parse behavior_config for {device_id}: {e}")
                        continue

                # Map color name to LED pattern
                if color:
                    pattern_map = {
                        'red': 'solid_red',
                        'green': 'solid_green',
                        'blue': 'solid_blue',
                        'yellow': 'solid_yellow',
                        'orange': 'solid_orange',
                        'white': 'solid_white',
                        'purple': 'solid_purple',
                        'cyan': 'solid_cyan'
                    }
                    led_pattern = pattern_map.get(color.lower(), 'solid_green')
                    try:
                        REGISTRY.set_led(device_id, pattern=led_pattern)
                        print(f"      {device_id} → {color.upper()} ({led_pattern})")
                        time.sleep(2.0)  # Delay between commands
                    except Exception as e:
                        print(f"   ⚠️  Failed to set {device_id} to {color}: {e}")

            # Wait for heartbeat delivery (up to 10 seconds for all devices)
            print("   ⏱️  Waiting 12 seconds for devices to display assigned colors...")
            time.sleep(12.0)
            print("   ✅ Deploy complete - cones should be at assigned colors")
        else:
            # Regular courses: Set all devices to GREEN
            for device in devices:
                try:
                    REGISTRY.set_led(device['device_id'], pattern='solid_green')
                except Exception as e:
                    print(f"⚠️  Failed to set {device['device_id']} to green: {e}")
        
        # Mark course as deployed
        db.mark_course_deployed(session_id)

        REGISTRY.log(f"Course deployed: {course['course_name']}")

        # If Simon Says, IMMEDIATELY set assigned colors after deploy
        if is_simon_says:
            print("\n🎨 Simon Says detected - setting assigned colors NOW...")
            try:
                import requests
                color_response = requests.post(
                    f'http://localhost:5001/api/session/{session_id}/set-simon-colors',
                    timeout=30
                )
                print(f"   Color setting response: {color_response.status_code}")
                if color_response.status_code == 200:
                    print(f"   ✅ Assigned colors set successfully")
                else:
                    print(f"   ⚠️  Color setting returned: {color_response.text}")
            except Exception as e:
                print(f"   ❌ Failed to set colors: {e}")

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


@sessions_bp.route('/<session_id>/set-simon-colors', methods=['POST'])
def set_simon_colors(session_id):
    """EXPLICITLY set Simon Says cones to assigned colors - called after deploy"""
    import time
    import json

    print(f"\n{'='*80}")
    print(f"🎨 SET_SIMON_COLORS CALLED")
    print(f"   Session ID: {session_id}")
    print(f"{'='*80}\n")

    try:
        session = db.get_session(session_id)
        course = db.get_course(session['course_id'])
        actions = db.get_course_actions(course['course_id'])

        print(f"   Course: {course['course_name']}")
        print(f"   Mode: {course.get('mode')}")

        # Color mapping
        pattern_map = {
            'red': 'solid_red',
            'green': 'solid_green',
            'blue': 'solid_blue',
            'yellow': 'solid_yellow',
            'orange': 'solid_orange',
            'white': 'solid_white',
            'purple': 'solid_purple',
            'cyan': 'solid_cyan'
        }

        print(f"\n   Setting assigned colors:")
        colors_set = []

        for action in actions:
            device_id = action['device_id']

            # Skip home base
            if device_id == '192.168.99.100':
                continue

            # Parse behavior_config
            behavior_config = action.get('behavior_config', '')
            if behavior_config:
                try:
                    if isinstance(behavior_config, str):
                        config_dict = json.loads(behavior_config)
                    else:
                        config_dict = behavior_config

                    color = config_dict.get('color')
                    if color:
                        led_pattern = pattern_map.get(color.lower(), 'solid_green')
                        REGISTRY.set_led(device_id, pattern=led_pattern)
                        print(f"      {device_id} → {color.upper()} ({led_pattern})")
                        colors_set.append({'device': device_id, 'color': color})
                        time.sleep(2.0)  # Spacing between commands
                except Exception as e:
                    print(f"      ⚠️  Error with {device_id}: {e}")

        print(f"\n   ⏱️  Waiting 12 seconds for colors to display...")
        time.sleep(12.0)
        print(f"   ✅ Colors set complete\n")

        return jsonify({
            'success': True,
            'colors_set': colors_set,
            'message': f'Set {len(colors_set)} device colors'
        })

    except Exception as e:
        print(f"   ❌ Error: {e}")
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


@sessions_bp.route('/<session_id>/continue', methods=['POST'])
def continue_session(session_id):
    """Continue session - create new session with successful athletes and incremented pattern length"""
    try:
        # Get original session
        session = db.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Only allow continuing completed or incomplete sessions
        if session['status'] not in ['completed', 'incomplete', 'failed']:
            return jsonify({'success': False, 'error': f'Cannot continue {session["status"]} session'}), 400

        # Verify this is a pattern mode session
        course = db.get_course(session['course_id'])
        if not course or course.get('mode') != 'pattern':
            return jsonify({'success': False, 'error': 'Can only continue pattern mode sessions'}), 400

        # Get pattern_length from DATABASE session record
        import json
        current_length = 4  # Default
        pattern_config = {}  # Initialize for both branches

        session_pattern_config = session.get('pattern_config')
        if session_pattern_config:
            # Session has database-stored pattern_config (from previous "Continue to n")
            try:
                pattern_config = json.loads(session_pattern_config)
                current_length = pattern_config.get('pattern_length', 4)
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # Fall back to session_state for normal sessions
            pattern_config = session_service.session_state.get('pattern_config', {})
            current_length = pattern_config.get('pattern_length', 4)

        # Check if we can increment (max 8)
        if current_length >= 8:
            return jsonify({'success': False, 'error': 'Already at maximum pattern length (8 cones)'}), 400

        # Filter successful athletes only (status='completed')
        successful_athletes = []
        for run in session['runs']:
            if run['status'] == 'completed':
                successful_athletes.append(run['athlete_id'])

        if not successful_athletes:
            return jsonify({'success': False, 'error': 'No successful athletes to continue with'}), 400

        # Extract session parameters
        team_id = session['team_id']
        course_id = session['course_id']
        audio_voice = session.get('audio_voice', 'male')

        # Create pattern_config override with incremented length
        next_length = current_length + 1
        import json
        pattern_config_override = json.dumps({
            'pattern_length': next_length,
            'allow_repeats': pattern_config.get('allow_repeats', True),
            'error_feedback_duration': pattern_config.get('error_feedback_duration', 4.0),
            'debounce_ms': pattern_config.get('debounce_ms', 1000)
        })

        # Create new session with pattern_config override
        new_session_id = db.create_session(
            team_id=team_id,
            course_id=course_id,
            athlete_queue=successful_athletes,
            audio_voice=audio_voice,
            pattern_config=pattern_config_override
        )

        # Store in global state
        active_session_state['session_id'] = new_session_id

        REGISTRY.log(f"Session {session_id[:8]} continued to {next_length} cones as {new_session_id[:8]} ({len(successful_athletes)} athletes)")

        # Deactivate the old session's course first (important!)
        # This ensures the new session can properly deploy/activate the course
        try:
            REGISTRY.deactivate_course()
            print(f"✓ Deactivated course from previous session {session_id[:8]}")
        except Exception as deactivate_error:
            print(f"⚠️  Course deactivation warning: {deactivate_error}")

        # Small delay to let deactivation propagate
        import time
        time.sleep(0.5)

        # Deploy and activate the course (assigns colors to cones)
        # Call REGISTRY methods directly instead of HTTP API (faster, no timeout issues)
        course_name = course['course_name']
        try:
            # Deploy the course directly (loads into REGISTRY)
            # This sets each cone to its assigned color with 2-second delays between each
            print(f"📤 Deploying course: {course_name}")
            deploy_result = REGISTRY.deploy_course(course_name)
            print(f"✓ Deploy result: {deploy_result}")

            if not deploy_result.get('success'):
                raise Exception(f"Deploy failed: {deploy_result.get('error')}")

            # CRITICAL: Wait for all cone colors to be displayed
            # Deploy sends colors with 2s delay between each (4 cones = ~8s)
            # Need to wait for the LAST color command to complete
            print(f"⏳ Waiting for cone colors to display...")
            time.sleep(3.0)  # Wait for colors to settle

            # Activate course (enables touch detection)
            print(f"📤 Activating course: {course_name}")
            activate_result = REGISTRY.activate_course(course_name)
            print(f"✓ Activate result: {activate_result}")

            if not activate_result.get('success'):
                raise Exception(f"Activate failed: {activate_result.get('error')}")

            # Wait for activation {"cmd": "start"} to propagate to all devices
            print(f"⏳ Waiting for activation to propagate...")
            time.sleep(2.0)
            print(f"✓ Course deployed and activated - cones showing assigned colors")
        except Exception as deploy_error:
            print(f"❌ Course deploy/activate error: {deploy_error}")
            import traceback
            traceback.print_exc()
            # Don't continue - this is critical
            return jsonify({'success': False, 'error': f'Course activation failed: {str(deploy_error)}'}), 500

        # Auto-start the session (generates pattern, displays it)
        try:
            print(f"📤 Calling start_session for: {new_session_id[:8]}")
            session_service.start_session(new_session_id)
            REGISTRY.log(f"Session {new_session_id[:8]} auto-started (continue to {next_length})")
            print(f"✓ Session started successfully")
        except Exception as start_error:
            print(f"❌ Auto-start failed: {start_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Session start failed: {str(start_error)}'}), 500

        return jsonify({
            'success': True,
            'new_session_id': new_session_id,
            'redirect_url': url_for('sessions.session_monitor', session_id=new_session_id),
            'pattern_length': next_length,
            'athlete_count': len(successful_athletes)
        })

    except Exception as e:
        print(f"❌ Continue session error: {e}")
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
