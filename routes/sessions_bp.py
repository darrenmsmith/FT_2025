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
        course_id = int(data['course_id'])  # Convert to int for database lookup
        athlete_queue = data['athlete_queue']  # List of athlete_ids in order
        audio_voice = data.get('audio_voice', 'male')

        # Get course details to check type
        course = db.get_course(course_id)
        if not course:
            return jsonify({'success': False, 'error': 'Course not found'}), 404

        # Check if this is a Beep Test course
        if course.get('course_type') == 'beep_test':
            # Redirect to beep test setup with team pre-selected
            # Beep test has its own flow with dynamic layout based on configuration
            return jsonify({
                'success': True,
                'redirect': f'/beep-test/setup?team_id={team_id}'
            })

        # Regular course - create session and proceed to cone setup
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

    # Extract pattern_length from session's pattern_config (for Simon Says)
    pattern_length = 4  # Default
    if session.get('pattern_config'):
        import json
        try:
            config = json.loads(session['pattern_config']) if isinstance(session['pattern_config'], str) else session['pattern_config']
            pattern_length = config.get('pattern_length', 4)
        except:
            pass

    return render_template(
        'session_setup_cones.html',
        session_id=session_id,
        session=session,
        course=course,
        timeout_minutes=timeout_minutes,
        pattern_length=pattern_length
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
    if course_mode == 'pattern':
        # Try to get pattern from active session first (session is running)
        if session_service.session_state.get('active_runs'):
            # Get pattern from ACTIVE athlete's run_info (each athlete has unique pattern!)
            for run_id, run_info in session_service.session_state.get('active_runs', {}).items():
                if run_info.get('is_active', False) and 'pattern_data' in run_info:
                    pattern_data = run_info['pattern_data']
                    # DEBUG: Log what pattern is being sent to UI
                    if pattern_data and pattern_data.get('pattern'):
                        pattern_str = ' → '.join([f"{step['color'].upper()} ({step['device_id'].split('.')[-1]})"
                                                 for step in pattern_data['pattern']])
                        print(f"📱 UI Pattern Data (active): {pattern_str}")
                    break

        # If no active pattern, check pre-generated patterns (session is in 'setup' status)
        if not pattern_data and hasattr(session_service, 'pre_generated_patterns'):
            pre_gen = session_service.pre_generated_patterns.get(session_id)
            if pre_gen and pre_gen.get('athlete_patterns'):
                # Get first athlete's pattern (first run in queue)
                first_run = session['runs'][0] if session['runs'] else None
                if first_run:
                    first_pattern = pre_gen['athlete_patterns'].get(first_run['run_id'])
                    if first_pattern:
                        pattern_data = first_pattern
                        # DEBUG: Log what pattern is being sent to UI
                        if pattern_data and pattern_data.get('pattern'):
                            pattern_str = ' → '.join([f"{step['color'].upper()} ({step['device_id'].split('.')[-1]})"
                                                     for step in pattern_data['pattern']])
                            print(f"📱 UI Pattern Data (pre-generated): {pattern_str}")

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


@sessions_bp.route('/<session_id>/next-athlete', methods=['POST'])
def next_athlete(session_id):
    """Continue to Next Athlete button - advance to next athlete in pattern mode"""
    try:
        print(f"\n{'='*80}")
        print(f"👥 NEXT ATHLETE BUTTON CLICKED")
        print(f"   Session ID: {session_id}")
        print(f"{'='*80}\n")

        # Call the move to next athlete function
        has_next_athlete = session_service._move_to_next_athlete()

        if has_next_athlete:
            print(f"   ✅ Advanced to next athlete")
            return jsonify({'success': True, 'message': 'Advanced to next athlete'})
        else:
            # No more athletes - session should complete
            print(f"   🎉 No more athletes - completing session")
            session_service._complete_session(session_id)
            return jsonify({'success': True, 'message': 'Session completed - no more athletes'})

    except Exception as e:
        print(f"❌ Next athlete error: {e}")
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

                # Set allow_repeats based on pattern_length vs number of devices
                if int(pattern_length) > colored_device_count:
                    # MUST allow repeats - can't have 6-step pattern with 4 devices without repeats
                    allow_repeats = True
                    print(f"   ⚠️  Pattern length ({pattern_length}) > devices ({colored_device_count}), forcing allow_repeats=True")
                else:
                    # Pattern length <= devices - each cone should appear exactly once (no repeats)
                    allow_repeats = False
                    print(f"   ✓ Pattern length ({pattern_length}) <= devices ({colored_device_count}), setting allow_repeats=False")

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
        
        # Deploy the course first (loads into REGISTRY on admin interface)
        course_name = course['course_name']
        import requests
        try:
            deploy_resp = requests.post(
                'http://localhost:5000/api/course/deploy',
                json={'course_name': course_name},
                timeout=5
            )
            print(f"Deploy API (admin): {deploy_resp.status_code}")
        except Exception as e:
            print(f"Deploy API error: {e}")

        # Activate course on admin interface (port 5000) - this controls the devices
        try:
            activate_resp = requests.post(
                'http://localhost:5000/api/course/activate',
                json={'course_name': course_name},
                timeout=5
            )
            print(f"Activate API (admin): {activate_resp.status_code}")
            if activate_resp.status_code == 200:
                print("✅ Course activated on admin REGISTRY (devices will receive LED commands)")
        except Exception as e:
            print(f"❌ Activate API error: {e}")

        # DON'T activate in local coach REGISTRY - it has no device connections
        # Only the admin REGISTRY (port 5000) can control devices via heartbeat

        # LED commands are now sent by the admin interface (port 5000) via the activate API
        # The coach interface (port 5001) has no device connections and should not send LED commands

        # Check if this is a Simon Says course (mode='pattern')
        is_simon_says = course.get('mode') == 'pattern'

        if is_simon_says:
            print("📍 Simon Says course detected - colors will be set by admin interface")
        
        # Mark course as deployed
        db.mark_course_deployed(session_id)

        REGISTRY.log(f"Course deployed: {course['course_name']}")

        # If Simon Says, IMMEDIATELY set assigned colors after deploy
        if is_simon_says:
            print("\n🎨 Simon Says detected - setting assigned colors NOW...")
            try:
                import requests
                color_response = requests.post(
                    f'http://localhost:5001/session/{session_id}/set-simon-colors',
                    timeout=30
                )
                print(f"   Color setting response: {color_response.status_code}")
                if color_response.status_code == 200:
                    print(f"   ✅ Assigned colors set successfully")
                else:
                    print(f"   ⚠️  Color setting returned: {color_response.text}")
            except Exception as e:
                print(f"   ❌ Failed to set colors: {e}")

            # GENERATE PATTERNS FOR ALL ATHLETES NOW (before session starts)
            print("\n🎲 Generating patterns for all athletes...")
            try:
                from field_trainer.pattern_generator import pattern_generator
                import json

                # Get colored devices from course actions
                colored_devices = []
                for action in actions:
                    if action['device_id'] == '192.168.99.100':  # Skip start device
                        continue

                    behavior_config = action.get('behavior_config')
                    if behavior_config:
                        try:
                            config = json.loads(behavior_config) if isinstance(behavior_config, str) else behavior_config
                            color = config.get('color')
                            if color:
                                colored_devices.append({
                                    'device_id': action['device_id'],
                                    'device_name': action['device_name'],
                                    'color': color
                                })
                        except (json.JSONDecodeError, TypeError):
                            pass

                if colored_devices:
                    # Get pattern config from session (with override from pattern_length dropdown)
                    session_pattern_config_str = session.get('pattern_config')
                    pattern_length = 4
                    allow_repeats = True
                    error_feedback_duration = 4.0
                    debounce_ms = 1000

                    if session_pattern_config_str:
                        try:
                            config = json.loads(session_pattern_config_str) if isinstance(session_pattern_config_str, str) else session_pattern_config_str
                            pattern_length = config.get('pattern_length', 4)
                            allow_repeats = config.get('allow_repeats', True)
                            error_feedback_duration = config.get('error_feedback_duration', 4.0)
                            debounce_ms = config.get('debounce_ms', 1000)
                        except:
                            pass

                    # Get all athletes/runs for this session
                    all_runs = db.get_session_runs(session_id)

                    # Initialize session_state structure for pre-generated patterns
                    if not hasattr(session_service, 'pre_generated_patterns'):
                        session_service.pre_generated_patterns = {}

                    session_service.pre_generated_patterns[session_id] = {
                        'pattern_config': {
                            'colored_devices': colored_devices,
                            'pattern_length': pattern_length,
                            'allow_repeats': allow_repeats,
                            'error_feedback_duration': error_feedback_duration,
                            'debounce_ms': debounce_ms
                        },
                        'athlete_patterns': {}
                    }

                    # Generate unique pattern for each athlete
                    previous_pattern = None
                    for idx, run in enumerate(all_runs):
                        # Generate pattern, avoiding consecutive duplicates
                        max_attempts = 100
                        for attempt in range(max_attempts):
                            pattern = pattern_generator.generate_simon_says_pattern(
                                colored_devices,
                                sequence_length=pattern_length,
                                allow_repeats=allow_repeats
                            )

                            # Check if this pattern is same as previous athlete's pattern
                            if previous_pattern is None or not session_service._patterns_match(pattern, previous_pattern):
                                break  # Found unique pattern

                        pattern_description = pattern_generator.get_pattern_description(pattern)
                        pattern_device_ids = pattern_generator.get_pattern_device_ids(pattern)

                        # Store pattern for this athlete
                        pattern_data = {
                            'pattern': pattern,
                            'description': pattern_description,
                            'device_ids': pattern_device_ids,
                            'colored_devices': colored_devices
                        }

                        session_service.pre_generated_patterns[session_id]['athlete_patterns'][run['run_id']] = pattern_data

                        # Log pattern to System Log for coach
                        REGISTRY.log(f"📋 {run['athlete_name']}: {pattern_description}", source="session")
                        print(f"   ✓ Pattern for {run['athlete_name']}: {pattern_description}")

                        # Create segments for this run so boxes appear in UI immediately
                        try:
                            db.create_pattern_segments_for_run(run['run_id'], pattern_device_ids)
                            print(f"   ✓ Created segments for {run['athlete_name']}")
                        except Exception as seg_error:
                            print(f"   ⚠️  Failed to create segments for {run['athlete_name']}: {seg_error}")

                        previous_pattern = pattern

                    print(f"   ✅ Generated {len(all_runs)} unique patterns and created segments")
                else:
                    print(f"   ⚠️  No colored devices found for pattern generation")
            except Exception as e:
                print(f"   ❌ Failed to generate patterns: {e}")
                import traceback
                traceback.print_exc()

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
                        time.sleep(0.1)  # Small delay for command processing
                except Exception as e:
                    print(f"      ⚠️  Error with {device_id}: {e}")

        print(f"\n   ⏱️  Waiting for colors to be sent...")
        time.sleep(0.5)
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

        # Get pattern_config from original session (preserve pattern length for Simon Says)
        pattern_config_str = session.get('pattern_config')  # Already JSON string or None

        # Get athlete queue from original runs (exclude absent athletes)
        athlete_queue = []
        for run in session['runs']:
            if run['status'] != 'absent':
                athlete_queue.append(run['athlete_id'])

        if not athlete_queue:
            return jsonify({'success': False, 'error': 'No athletes to repeat session with'}), 400

        # Create new session with SAME pattern_config (preserves pattern length)
        new_session_id = db.create_session(
            team_id=team_id,
            course_id=course_id,
            athlete_queue=athlete_queue,
            audio_voice=audio_voice,
            pattern_config=pattern_config_str
        )

        # Store in global state
        active_session_state['session_id'] = new_session_id

        # Log with pattern length if applicable
        log_msg = f"Session {session_id[:8]} repeated as {new_session_id[:8]}"
        if pattern_config_str:
            import json
            try:
                config = json.loads(pattern_config_str)
                pattern_length = config.get('pattern_length')
                if pattern_length:
                    log_msg += f" ({pattern_length} colors)"
            except:
                pass
        REGISTRY.log(log_msg)

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

        # Count colored devices in course (exclude D0)
        colored_devices_count = sum(1 for action in course['actions']
                                    if action['sequence'] > 0)

        # Determine allow_repeats: must be True if pattern length > number of devices
        # (Pattern generator already prevents consecutive repeats)
        if next_length > colored_devices_count:
            allow_repeats = True
            print(f"   ℹ️  Pattern length ({next_length}) > devices ({colored_devices_count}), enabling allow_repeats")
        else:
            allow_repeats = pattern_config.get('allow_repeats', True)

        import json
        pattern_config_override = json.dumps({
            'pattern_length': next_length,
            'allow_repeats': allow_repeats,
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

        repeat_mode = "with repeats" if allow_repeats else "no repeats"
        REGISTRY.log(f"Session {session_id[:8]} continued to {next_length} cones ({repeat_mode}) as {new_session_id[:8]} ({len(successful_athletes)} athletes)")

        # Redirect to setup-cones page so coach can review athletes before starting
        return jsonify({
            'success': True,
            'new_session_id': new_session_id,
            'redirect_url': url_for('sessions.session_setup_cones', session_id=new_session_id),
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
