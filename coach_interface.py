#!/usr/bin/env python3
"""
Coach Interface for Field Trainer - Port 5001
Separate from admin interface, focused on team/athlete/session management
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from typing import Optional
import sys
import os

# Add field_trainer to path
sys.path.insert(0, '/opt')

from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY

app = Flask(__name__, template_folder='/opt/templates/coach')
app.config['SECRET_KEY'] = 'field-trainer-coach-2025'

# Initialize database
db = DatabaseManager('/opt/data/field_trainer.db')

# Store active session state - supports multiple simultaneous athletes
active_session_state = {
    'session_id': None,
    'active_runs': {},  # {run_id: {'athlete_name', 'athlete_id', 'started_at', 'last_device', 'sequence_position'}}
    'device_sequence': [],  # Ordered list of device_ids in course
    'total_queued': 0  # Total athletes in queue at session start
}

# Helper function to find which athlete should receive a touch
def find_athlete_for_touch(device_id: str, timestamp: datetime) -> Optional[str]:
    """
    Determine which active athlete should be attributed a touch on device_id.
    Priority 1: Athletes at correct sequential position (gap == 1)
    Priority 2: Athletes who skipped devices (gap > 1)
    Ignores: Same device twice (gap == 0) or backwards (gap < 0)
    """
    if not active_session_state['active_runs']:
        print(f"   ❌ No active runs")
        return None
    
    session_id = active_session_state.get('session_id')
    if not session_id:
        return None
    
    # Find device position in sequence
    device_sequence = active_session_state['device_sequence']
    if device_id not in device_sequence:
        print(f"   ❌ Device {device_id} not in course sequence")
        return None
    
    device_position = device_sequence.index(device_id)
    
    # Categorize athletes by gap
    priority_1 = []  # gap == 1 (sequential)
    priority_2 = []  # gap > 1 (skipped devices)
    
    print(f"   🔍 Checking {len(active_session_state['active_runs'])} active athletes for device {device_id} (position {device_position}):")
    
    for run_id, run_info in active_session_state['active_runs'].items():
        last_position = run_info.get('sequence_position', -1)
        gap = device_position - last_position
        
        print(f"      {run_info['athlete_name']}: last_position={last_position}, gap={gap}")
        
        if gap == 0:
            print(f"         ⚠️  Same device twice - IGNORE")
            continue
        elif gap < 0:
            print(f"         ⚠️  Backwards touch - IGNORE")
            continue
        elif gap == 1:
            print(f"         ✅ Sequential (Priority 1)")
            priority_1.append((run_id, run_info, gap))
        elif gap > 1:
            print(f"         ⚠️  Skipped {gap-1} device(s) (Priority 2)")
            priority_2.append((run_id, run_info, gap))
    
    # Attribution logic
    chosen = None
    skipped_count = 0
    
    if priority_1:
        # Choose first athlete in queue order
        priority_1.sort(key=lambda x: x[1].get('queue_position', 999))
        chosen, chosen_info, _ = priority_1[0]
        print(f"   ✅ Attributed to {chosen_info['athlete_name']} (sequential)")
        
    elif priority_2:
        # Choose athlete with smallest gap, then by queue order
        priority_2.sort(key=lambda x: (x[2], x[1].get('queue_position', 999)))
        chosen, chosen_info, gap = priority_2[0]
        skipped_count = gap - 1
        print(f"   ⚠️  Attributed to {chosen_info['athlete_name']} (skipped {skipped_count} device(s))")
        
    else:
        print(f"   ⚠️  No valid candidates for device {device_id}")
        return None
    
    # Mark skipped segments if applicable
    if skipped_count > 0:
        mark_skipped_segments(chosen, device_position, skipped_count)
    
    return chosen


def mark_skipped_segments(run_id: str, current_position: int, skipped_count: int):
    """Mark segments as missed when athlete skips devices"""
    run_info = active_session_state['active_runs'].get(run_id)
    if not run_info:
        return
    
    last_position = run_info.get('sequence_position', -1)
    print(f"   📝 Marking {skipped_count} skipped segment(s) for {run_info['athlete_name']}:")
    
    # Mark each skipped segment
    for pos in range(last_position + 1, current_position):
        device_sequence = active_session_state['device_sequence']
        from_device = device_sequence[pos - 1] if pos > 0 else '192.168.99.100'
        to_device = device_sequence[pos]
        
        # Find and mark the segment
        segments = db.get_run_segments(run_id)
        for seg in segments:
            if seg['from_device'] == from_device and seg['to_device'] == to_device:
                db.mark_segment_missed(seg['segment_id'])
                print(f"      ❌ {from_device} → {to_device} marked as missed")
                break
@app.route("/")
@app.route("/teams")



def index():
    """Team list homepage"""
    teams = db.get_all_teams()
    return render_template('team_list.html', teams=teams)


@app.route('/team/create', methods=['GET', 'POST'])
def create_team():
    """Create new team"""
    if request.method == 'POST':
        name = request.form.get('name')
        age_group = request.form.get('age_group')
        
        try:
            team_id = db.create_team(name=name, age_group=age_group)
            return redirect(url_for('team_detail', team_id=team_id))
        except Exception as e:
            return render_template('team_create.html', error=str(e))
    
    return render_template('team_create.html')


@app.route('/team/<team_id>')
def team_detail(team_id):
    """Team detail with roster"""
    team = db.get_team(team_id)
    if not team:
        return "Team not found", 404
    
    athletes = db.get_athletes_by_team(team_id)
    return render_template('team_detail.html', team=team, athletes=athletes)


@app.route('/team/<team_id>/athlete/add', methods=['POST'])
def add_athlete(team_id):
    """Add athlete to team"""
    try:
        athlete_id = db.create_athlete(
            team_id=team_id,
            name=request.form.get('name'),
            jersey_number=request.form.get('jersey_number', type=int),
            age=request.form.get('age', type=int),
            position=request.form.get('position')
        )
        return redirect(url_for('team_detail', team_id=team_id))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/athlete/<athlete_id>/update', methods=['POST'])
def update_athlete(athlete_id):
    """Update athlete info"""
    try:
        data = request.get_json()
        db.update_athlete(athlete_id, **data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/athlete/<athlete_id>/delete', methods=['POST'])
def delete_athlete(athlete_id):
    """Delete athlete"""
    try:
        athlete = db.get_athlete(athlete_id)
        team_id = athlete['team_id']
        db.delete_athlete(athlete_id)
        return redirect(url_for('team_detail', team_id=team_id))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== COURSES ====================

@app.route('/courses')
def courses():
    """Course list"""
    courses = db.get_all_courses()
    return render_template('course_list.html', courses=courses)


@app.route('/course/<int:course_id>')
def course_detail(course_id):
    """Course detail with actions"""
    course = db.get_course(course_id)
    if not course:
        return "Course not found", 404
    
    return render_template('course_detail.html', course=course)


# ==================== SESSION SETUP ====================

@app.route('/session/setup')
def session_setup():
    """Session setup page - select team, course, order athletes"""
    teams = db.get_all_teams()
    courses = db.get_all_courses()
    return render_template('session_setup.html', teams=teams, courses=courses)


@app.route('/api/team/<team_id>/athletes')
def get_team_athletes(team_id):
    """API: Get athletes for team (for session setup)"""
    athletes = db.get_athletes_by_team(team_id)
    return jsonify(athletes)


@app.route('/session/create', methods=['POST'])
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

        # Deploy course to devices via API (but don't activate yet)
        course = db.get_course(int(course_id))
        if course:
            print(f"📤 Deploying course via API: {course['course_name']}")
            import requests
            try:
                response = requests.post(
                    'http://localhost:5000/api/course/deploy',
                    json={'course_name': course['course_name']},
                    timeout=5
                )
                print(f"   Deploy response: {response.status_code} - {response.json()}")

                # Activate immediately after successful deploy
                if response.status_code == 200:
                    print(f"🟢 Activating course immediately...")
                    activate_response = requests.post(
                        'http://localhost:5000/api/course/activate',
                        json={'course_name': course['course_name']},
                        timeout=5
                    )
                    print(f"   Activate response: {activate_response.status_code} - {activate_response.json()}")
            except Exception as e:
                print(f"   ❌ Deploy failed: {e}")
        else:
            print(f"❌ Course not found in database!")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': url_for('session_monitor', session_id=session_id)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== SESSION MONITORING ====================

@app.route('/session/<session_id>/monitor')
def session_monitor(session_id):
    """Live session monitoring page"""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404
    
    course = db.get_course(session['course_id'])
    team = db.get_team(session['team_id'])
    
    return render_template(
        'session_monitor.html',
        session=session,
        course=course,
        team=team
    )


@app.route('/api/session/<session_id>/status')
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


@app.route('/session/<session_id>/start', methods=['POST'])
def start_session(session_id):
    """GO button - start session and first athlete"""
    import requests
    print(f"\n{'='*80}")
    print(f"🎬 START_SESSION CALLED - Session ID: {session_id}")
    print(f"{'='*80}\n")
    try:
        # Mark session as active
        print(f"Step 1: Marking session as active...")
        db.start_session(session_id)
        
        # Get first queued run
        first_run = db.get_next_queued_run(session_id)
        if not first_run:
            return jsonify({'success': False, 'error': 'No athletes in queue'}), 400
        
        # Start first run
        start_time = datetime.utcnow()
        db.start_run(first_run['run_id'], start_time)
        
        # Small delay to ensure segments are committed before touches arrive
        import time
        time.sleep(0.1)
        
        # Pre-create segments for this run
        session = db.get_session(session_id)
        db.create_segments_for_run(first_run['run_id'], session['course_id'])
        
        # Get course device sequence for multi-athlete tracking
        course = db.get_course(session['course_id'])
        device_sequence = [action['device_id'] for action in course['actions'] if action['device_id'] != '192.168.99.100']
        
        # Count total athletes
        all_runs = db.get_session_runs(session_id)
        total_athletes = len(all_runs)
        
        # Initialize multi-athlete state
        active_session_state['session_id'] = session_id
        active_session_state['device_sequence'] = device_sequence
        active_session_state['total_queued'] = total_athletes
        active_session_state['active_runs'] = {
            first_run['run_id']: {
                'athlete_name': first_run['athlete_name'],
                'athlete_id': first_run['athlete_id'],
                'started_at': start_time.isoformat(),
                'last_device': None,
                'sequence_position': -1  # Haven't touched any device yet
            }
        }
        
        print(f"✅ Multi-athlete state initialized:")
        print(f"   Active athletes: 1/{total_athletes}")
        print(f"   Device sequence: {device_sequence}")
        print(f"   First athlete: {first_run['athlete_name']}")

        # Set audio voice
        audio_voice = session.get('audio_voice', 'male')
        # TODO: Send audio voice setting to devices

        # Get course for audio playback
        session = db.get_session(session_id)
        course = db.get_course(session['course_id'])    
    
        # Course already activated during session creation
        print(f"\nStep 5: Course already active, proceeding with audio...")

        # Wait for activation to propagate
        import time
        time.sleep(0.5)

        # Play first audio on Device 0 via API
        first_action = course['actions'][0]
        print(f"🔊 Playing Device 0 audio via API: {first_action['audio_file']}")
        try:
            audio_response = requests.post(
                'http://localhost:5000/api/audio/play',
                json={
                    'node_id': '192.168.99.100',
                    'clip': first_action['audio_file'].replace('.mp3', '')
                },
                timeout=2
            )
            print(f"   Audio response: {audio_response.status_code}")
        except Exception as e:
            print(f"   ❌ Audio command failed: {e}")
        
        return jsonify({
            'success': True,
            'message': f"{first_run['athlete_name']} started",
            'current_run': first_run
        })
    except Exception as e:
        REGISTRY.log(f"Session start error: {e}", level="error")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    """Stop session (mark incomplete)"""
    try:
        reason = request.get_json().get('reason', 'Stopped by coach')
        db.mark_session_incomplete(session_id, reason)
        
        # Deactivate course
        REGISTRY.deactivate_course()
        
        # Clear global state
        active_session_state['session_id'] = None
        active_session_state['current_run_id'] = None
        active_session_state['waiting_for_device'] = None
        
        REGISTRY.log(f"Session stopped: {reason}")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/session/<session_id>/athlete/<run_id>/absent', methods=['POST'])
def mark_athlete_absent(session_id, run_id):
    """Mark athlete as absent (remove from queue but note absence)"""
    try:
        db.update_run_status(run_id, 'absent')
        
        run = db.get_run(run_id)
        REGISTRY.log(f"Athlete marked absent: {run.get('athlete_name', 'Unknown')}")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ==================== SESSION HISTORY ====================

@app.route('/sessions')
def sessions():
    """Session history list"""
    # Get recent sessions
    with db.get_connection() as conn:
        rows = conn.execute('''
            SELECT s.*, t.name as team_name, c.course_name
            FROM sessions s
            JOIN teams t ON s.team_id = t.team_id
            JOIN courses c ON s.course_id = c.course_id
            ORDER BY s.created_at DESC
            LIMIT 50
        ''').fetchall()
        sessions = [dict(row) for row in rows]
    
    return render_template('session_history.html', sessions=sessions)


@app.route('/session/<session_id>/results')
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


@app.route('/session/<session_id>/export')
def export_session(session_id):
    """Export session results as CSV"""
    import csv
    from io import StringIO
    
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
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=session_{session_id[:8]}.csv'}
    )


# ==================== TOUCH EVENT HANDLER ====================

def handle_touch_event_from_registry(device_id: str, timestamp: datetime):
    """
    Called by REGISTRY when a device touch is detected.
    Supports multiple simultaneous athletes on course.
    """
    session_id = active_session_state.get('session_id')
    
    if not session_id:
        REGISTRY.log(f"Touch on {device_id} but no active session", level="warning")
        return
    
    print(f"\n{'='*80}")
    print(f"👆 MULTI-ATHLETE TOUCH HANDLER")
    print(f"   Device: {device_id}")
    print(f"   Active athletes: {len(active_session_state.get('active_runs', {}))}")
    print(f"{'='*80}")
    
    # Find which athlete should receive this touch
    run_id = find_athlete_for_touch(device_id, timestamp)
    
    if not run_id:
        REGISTRY.log(f"Touch on {device_id} - no valid athlete found", level="warning")
        print(f"❌ Could not attribute touch to any athlete")
        print(f"{'='*80}\n")
        return
    
    # Record the touch
    segment_id = db.record_touch(run_id, device_id, timestamp)
    
    if not segment_id:
        REGISTRY.log(f"Touch on {device_id} but no matching segment for run {run_id}", level="warning")
        print(f"⚠️  No segment found for this touch")
        print(f"{'='*80}\n")
        return
    
    # Update athlete's progression
    run_info = active_session_state['active_runs'][run_id]
    device_sequence = active_session_state['device_sequence']
    new_position = device_sequence.index(device_id)
    
    run_info['last_device'] = device_id
    run_info['sequence_position'] = new_position
    
    print(f"✅ Touch recorded: {run_info['athlete_name']} → Device {device_id}")
    print(f"   Segment ID: {segment_id}")
    print(f"   Sequence position: {new_position + 1}/{len(device_sequence)}")
    
    # Check for alerts
    alert_raised, alert_type = db.check_segment_alerts(segment_id)
    if alert_raised:
        REGISTRY.log(f"ALERT: Segment {segment_id} - {alert_type}", level="warning")
        print(f"⚠️  ALERT: {alert_type}")
    
    # Get session and course info
    session = db.get_session(session_id)
    course = db.get_course(session['course_id'])
    
    # Find the action for this device
    action = next((a for a in course['actions'] if a['device_id'] == device_id), None)
    
    if not action:
        print(f"⚠️  No action found for device {device_id}")
        print(f"{'='*80}\n")
        return
    
    # Check if this action triggers next athlete
    if action.get('triggers_next_athlete'):
        print(f"🔔 Device triggers next athlete")
        next_run = db.get_next_queued_run(session_id)
        if next_run:
            # CRITICAL: Double-check status to prevent race conditions
            current_status = db.get_run(next_run['run_id'])['status']
            if current_status != 'queued':
                print(f"ℹ️  {next_run['athlete_name']} already started (status: {current_status})")
                return
            
            # Check if already started (in-memory check)
            if next_run['run_id'] in active_session_state['active_runs']:
                print(f"ℹ️  {next_run['athlete_name']} already in active_runs")
                return
    
            # Check if we're at max capacity (5 active athletes)
            elif len(active_session_state['active_runs']) >= 5:
                print(f"⏸️  At max capacity (5 athletes) - next athlete will wait")

            else:
                # Start next athlete
                start_time = datetime.utcnow()
                
                print(f"   🎬 Starting run for {next_run['athlete_name']}...")
                try:
                    db.start_run(next_run['run_id'], start_time)
                    print(f"      ✅ Run started successfully")
                except Exception as e:
                    print(f"      ❌ start_run FAILED: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"{'='*80}\n")
                    return
                
                # Add to active runs IMMEDIATELY to prevent duplicate triggers
                active_session_state['active_runs'][next_run['run_id']] = {
                    'athlete_name': next_run['athlete_name'],
                    'athlete_id': next_run['athlete_id'],
                    'started_at': start_time.isoformat(),
                    'last_device': None,
                    'sequence_position': -1
                }
                print(f"      ✅ Added to active_runs")
                
                # Create segments for next athlete
                print(f"   📋 Creating segments for {next_run['athlete_name']}...")
                print(f"      run_id: {next_run['run_id'][:8]}...")
                print(f"      course_id: {session['course_id']}")
                
                try:
                    db.create_segments_for_run(next_run['run_id'], session['course_id'])
                    
                    # Verify segments were created
                    segments = db.get_run_segments(next_run['run_id'])
                    print(f"      ✅ Created {len(segments)} segments")
                    for seg in segments:
                        print(f"         {seg['from_device']} → {seg['to_device']}")
                    
                    # Small delay to ensure segments are committed
                    import time
                    time.sleep(0.1)
                except Exception as e:
                    print(f"      ❌ Segment creation failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                print(f"🏃 Next athlete started: {next_run['athlete_name']}")
                print(f"   Active: {len(active_session_state['active_runs'])}/{active_session_state['total_queued']}")

                # Play audio on Device 0 for next athlete
                first_action = course['actions'][0]
                print(f"🔊 Playing Device 0 audio for next athlete via API")
                try:
                    import requests
                    audio_response = requests.post(
                        'http://localhost:5000/api/audio/play',
                        json={
                            'node_id': '192.168.99.100',
                            'clip': first_action['audio_file'].replace('.mp3', '')
                        },
                        timeout=2
                    )
                    print(f"   Audio response: {audio_response.status_code}")
                except Exception as e:
                    print(f"   ❌ Audio failed: {e}")
                
                REGISTRY.log(f"Next athlete started: {next_run['athlete_name']}")
        else:
            print(f"ℹ️  No more athletes queued")
    
    # Check if this marks run complete
    if action.get('marks_run_complete'):
        print(f"🏁 Device marks run complete")
        
        # Complete this athlete's run
        run = db.get_run(run_id)
        start_time = datetime.fromisoformat(run['started_at'])
        total_time = (timestamp - start_time).total_seconds()
        
        db.complete_run(run_id, timestamp, total_time)
        
        # Remove from active runs
        completed_athlete = active_session_state['active_runs'].pop(run_id)
        
        print(f"✅ Run completed: {completed_athlete['athlete_name']} in {total_time:.2f}s")
        print(f"   Remaining active: {len(active_session_state['active_runs'])}")
        
        REGISTRY.log(f"Run completed: {run.get('athlete_name')} in {total_time:.2f}s")
        
        # Check if session is complete
        next_run = db.get_next_queued_run(session_id)
        no_queued = (next_run is None)
        no_active = (len(active_session_state['active_runs']) == 0)
        
        print(f"   Queued remaining: {not no_queued}")
        print(f"   Active athletes: {len(active_session_state['active_runs'])}")
        
        if no_queued and no_active:
            print(f"🎉 SESSION COMPLETE - All athletes finished!")
            
            # Complete session
            db.complete_session(session_id)
            
            # Deactivate course
            import requests
            try:
                requests.post('http://localhost:5000/api/deactivate', timeout=2)
                print(f"   ✅ Course deactivated - devices returning to standby")
            except Exception as e:
                print(f"   ⚠️  Deactivate failed: {e}")
            
            # Rainbow celebration on Device 0
            try:
                requests.post(
                    'http://localhost:5000/api/device/192.168.99.100/led',
                    json={'pattern': 'rainbow'},
                    timeout=2
                )
                print(f"   🌈 Rainbow celebration started on Device 0")
                
                # Turn off rainbow after 10 seconds
                import threading
                def stop_rainbow():
                    import time
                    time.sleep(10)
                    try:
                        requests.post(
                            'http://localhost:5000/api/device/192.168.99.100/led',
                            json={'pattern': 'off'},
                            timeout=2
                        )
                        print(f"   ✅ Rainbow celebration ended")
                    except:
                        pass
                
                threading.Thread(target=stop_rainbow, daemon=True).start()
            except Exception as e:
                print(f"   ⚠️  Rainbow failed: {e}")
            
            # Clear state
            active_session_state['session_id'] = None
            active_session_state['active_runs'] = {}
            active_session_state['device_sequence'] = []
            active_session_state['total_queued'] = 0
            
            REGISTRY.log("🎉 Session completed - all athletes finished")
    
    print(f"{'='*80}\n")

# Export handler for REGISTRY integration
app.handle_touch_event = handle_touch_event_from_registry

# ==================== REGISTRY INTEGRATION ====================

def register_touch_handler():
    """
    Register our touch handler with REGISTRY
    This allows REGISTRY to call us when device touches occur
    """
    try:
        # Set the touch handler
        REGISTRY.set_touch_handler(handle_touch_event_from_registry)
        
        # Verify registration
        print("✅ Touch handler registered with REGISTRY")
        print(f"   Handler function: {handle_touch_event_from_registry}")
#        print(f"   REGISTRY handler: {getattr(REGISTRY, '_touch_handler', 'NOT SET')}")
        
        # Quick test to ensure it works
        test_timestamp = datetime.now()
        print(f"🧪 Testing handler with dummy call (should see warning about no active session)...")
        handle_touch_event_from_registry("test_device", test_timestamp)  

      # Test the handler with a dummy call
 #       test_timestamp = datetime.now()
 #       print(f"🧪 Testing handler with dummy call...")
 #       handle_touch_event_from_registry("test_device", test_timestamp)
 #       print("✅ Handler test complete")
        
        return True
    except Exception as e:
        print(f"❌ Failed to register touch handler: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("Field Trainer Coach Interface")
    print("=" * 60)
    print("Starting on http://0.0.0.0:5001")
    print("Use this interface for:")
    print("  - Team and athlete management")
    print("  - Session setup and monitoring")
    print("  - Viewing results and history")
    print("=" * 60)
    
    # Register touch handler with REGISTRY
    print("\n🔗 Registering touch handler with REGISTRY...")
    if register_touch_handler():
        print("=" * 60)
        print("✅ READY: Touch events will trigger athlete relay")
        print("=" * 60)
    else:
        print("=" * 60)
        print("⚠️  WARNING: Touch handler registration failed!")
        print("   Relay system will not work properly")
        print("=" * 60)
    print()  # blank line before Flask output
    app.run(host='0.0.0.0', port=5001, debug=True)

