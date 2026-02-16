#!/usr/bin/env python3
"""
Coach Interface for Field Trainer - Port 5001
Separate from admin interface, focused on team/athlete/session management
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, Response
from datetime import datetime
from typing import Optional
import sys
import os
import subprocess
import json
import logging
import re

# Add field_trainer to path
sys.path.insert(0, '/opt')

from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY
from field_trainer.ft_version import VERSION
from field_trainer.settings_manager import SettingsManager
from field_trainer.calibration import calibration_logic
sys.path.insert(0, '/opt/field_trainer/athletic_platform')
from bridge_layer import initialize_bridge
sys.path.insert(0, "/opt/field_trainer")
# from routes.dashboard import dashboard_bp

app = Flask(__name__, template_folder='/opt/field_trainer/templates', static_folder='/opt/field_trainer/static')
# Register dashboard blueprint
# app.register_blueprint(dashboard_bp)

# Register athlete management blueprint
from athlete_routes import athlete_bp

# Register sessions blueprint
from routes.sessions_bp import sessions_bp
app.register_blueprint(sessions_bp)
app.register_blueprint(athlete_bp)

# Register Beep Test blueprint
from routes.beep_test_bp import beep_test_bp
app.register_blueprint(beep_test_bp)

# Register Reaction Sprint blueprint
from routes.reaction_bp import reaction_bp
app.register_blueprint(reaction_bp)

app.config['SECRET_KEY'] = 'field-trainer-coach-2025'

# Configure logging
logger = logging.getLogger(__name__)

# Track when this process started
START_TIME = datetime.utcnow().isoformat()

# Initialize database
db = DatabaseManager('/opt/data/field_trainer.db')
perf_bridge, touch_bridge = initialize_bridge(db)

# Initialize session service
from services.session_service import SessionService
from models.session_state import active_session_state
session_service = SessionService(db, REGISTRY, active_session_state)

# Initialize settings manager
settings_mgr = SettingsManager(db)

# Sync audio settings from database to AudioManager on startup
try:
    if REGISTRY._audio:
        settings = settings_mgr.load_settings()
        voice_gender = settings.get('voice_gender', 'male')
        system_volume = int(settings.get('system_volume', '60'))

        REGISTRY._audio.set_voice_gender(voice_gender)
        REGISTRY._audio.set_volume(system_volume)
        print(f"✓ AudioManager initialized from settings: {voice_gender} voice, {system_volume}% volume")
except Exception as e:
    print(f"⚠ Failed to sync settings to AudioManager on startup: {e}")

# Store active session state - supports multiple simultaneous athletes
active_session_state = {
    'session_id': None,
    'active_runs': {},  # {run_id: {'athlete_name', 'athlete_id', 'started_at', 'last_device', 'sequence_position'}}
    'device_sequence': [],  # Ordered list of device_ids in course
    'total_queued': 0  # Total athletes in queue at session start
}

# Context processor to add version to all templates
@app.context_processor
def inject_version():
    return {'version': VERSION}

# Helper function to find which athlete should receive a touch
@app.route("/")
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard'))

@app.route("/health")
def health():
    """Health check endpoint - shows version and service status"""
    # If JSON requested, return JSON
    if request.args.get('format') == 'json':
        return jsonify({
            'service': 'field-trainer-coach',
            'version': VERSION,
            'pid': os.getpid(),
            'started_at': START_TIME,
            'port': 5001,
            'courses_loaded': len(REGISTRY.courses.get('courses', [])),
            'registry_id': id(REGISTRY),
            'active_session': active_session_state.get('session_id'),
            'status': 'healthy'
        })

    # Otherwise return HTML page
    def calculate_uptime(start_time_iso):
        try:
            start = datetime.fromisoformat(start_time_iso)
            now = datetime.utcnow()
            delta = now - start
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}h {minutes}m {seconds}s"
        except:
            return "Unknown"

    health_data = {
        'service_name': 'Coach Interface',
        'version': VERSION,
        'pid': os.getpid(),
        'started_at': START_TIME,
        'port': 5001,
        'courses_loaded': len(REGISTRY.courses.get('courses', [])),
        'registry_id': id(REGISTRY),
        'course_status': REGISTRY.course_status,
        'nodes_connected': len(REGISTRY.nodes),
        'active_session': active_session_state.get('session_id'),
        'active_runs': len(active_session_state.get('active_runs', {})),
        'uptime': calculate_uptime(START_TIME)
    }
    return render_template('health.html', **health_data)

@app.route('/dashboard')
def dashboard():
    """Coach dashboard with stats and recent activity"""
    try:
        # Get filter parameters
        team_id = request.args.get('team')
        category = request.args.get('category')

        stats = db.get_dashboard_stats()
        recent_activity = db.get_recent_activity(limit=5)  # Limited to 5 as requested
        course_rankings = db.get_course_rankings(team_id=team_id, category=category)

        # Get filter options
        teams = db.get_all_teams()
        with db.get_connection() as conn:
            categories = conn.execute('SELECT DISTINCT category FROM courses WHERE category IS NOT NULL ORDER BY category').fetchall()
        categories = [row['category'] for row in categories]

        return render_template('dashboard/index.html',
                             stats=stats,
                             recent_activity=recent_activity,
                             course_rankings=course_rankings,
                             teams=teams,
                             categories=categories,
                             selected_team=team_id,
                             selected_category=category)
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        import traceback
        traceback.print_exc()
        return render_template('dashboard/index.html',
                             stats={
                                 'total_athletes': 0,
                                 'total_teams': 0,
                                 'sessions_today': 0,
                                 'runs_today': 0,
                                 'prs_this_week': 0
                             },
                             recent_activity=[],
                             course_rankings=[],
                             teams=[],
                             categories=[],
                             selected_team=None,
                             selected_category=None)

@app.route('/api/dashboard/stats')
def dashboard_stats_api():
    """API: Get dashboard statistics for auto-refresh"""
    try:
        stats = db.get_dashboard_stats()
        recent_activity = db.get_recent_activity(limit=5)
        return jsonify({
            'success': True,
            'stats': stats,
            'recent_activity': recent_activity
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/teams")
def teams_list():
    """Team list page with filtering"""
    # Get filter parameters from query string
    search = request.args.get('search')
    sport = request.args.get('sport')
    gender = request.args.get('gender')
    coach = request.args.get('coach')
    active_only = request.args.get('active_only', '1') == '1'  # Default to active only

    # Use search if any filters are present, otherwise get all teams
    if any([search, sport, gender, coach]) or not active_only:
        teams = db.search_teams(
            search_term=search,
            sport=sport,
            gender=gender,
            coach_name=coach,
            active_only=active_only
        )
    else:
        teams = db.get_all_teams(active_only=active_only)

    return render_template('team_list.html', teams=teams)

@app.route('/team/create', methods=['GET', 'POST'])
def create_team():
    """Create new team with enhanced fields"""
    if request.method == 'POST':
        try:
            team_id = db.create_team(
                name=request.form.get('name'),
                age_group=request.form.get('age_group'),
                sport=request.form.get('sport') or None,
                gender=request.form.get('gender') or None,
                season=request.form.get('season') or None,
                coach_name=request.form.get('coach_name') or None,
                notes=request.form.get('notes') or None,
                active=request.form.get('active', 'on') == 'on'
            )
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


@app.route('/team/<team_id>/edit', methods=['GET', 'POST'])
def edit_team(team_id):
    """Edit team details"""
    team = db.get_team(team_id)
    if not team:
        return "Team not found", 404

    if request.method == 'POST':
        try:
            db.update_team(
                team_id,
                name=request.form.get('name'),
                age_group=request.form.get('age_group'),
                sport=request.form.get('sport') or None,
                gender=request.form.get('gender') or None,
                season=request.form.get('season') or None,
                coach_name=request.form.get('coach_name') or None,
                notes=request.form.get('notes') or None,
                active=request.form.get('active', 'on') == 'on'
            )
            return redirect(url_for('team_detail', team_id=team_id))
        except Exception as e:
            return render_template('team_edit.html', team=team, error=str(e))

    return render_template('team_edit.html', team=team)


@app.route('/team/<team_id>/archive', methods=['POST'])
def archive_team_route(team_id):
    """Archive a team"""
    try:
        db.archive_team(team_id)
        return redirect(url_for('teams_list'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/team/<team_id>/reactivate', methods=['POST'])
def reactivate_team_route(team_id):
    """Reactivate an archived team"""
    try:
        db.reactivate_team(team_id)
        return redirect(url_for('teams_list'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/team/<team_id>/duplicate', methods=['POST'])
def duplicate_team_route(team_id):
    """Duplicate a team"""
    try:
        new_name = request.form.get('new_name')
        new_season = request.form.get('new_season')
        new_team_id = db.duplicate_team(team_id, new_name, new_season)
        if new_team_id:
            return redirect(url_for('team_detail', team_id=new_team_id))
        else:
            return "Failed to duplicate team", 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/team/<team_id>/export/csv')
def export_team_csv_route(team_id):
    """Export single team as CSV"""
    try:
        csv_data = db.export_team_csv(team_id)
        if not csv_data:
            return "Team not found", 404

        team = db.get_team(team_id)
        safe_name = "".join(c for c in team['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"team_{safe_name}_{datetime.now().strftime('%Y%m%d')}.csv"

        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/teams/export/csv')
def export_all_teams_csv_route():
    """Export all teams as CSV"""
    try:
        csv_data = db.export_all_teams_csv()
        filename = f"all_teams_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/teams')
def api_teams():
    """API endpoint to get all teams"""
    try:
        active_only = request.args.get('active', 'true').lower() == 'true'
        teams = db.get_all_teams(active_only=active_only)
        return jsonify(teams)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ====== Mesh Network Security ======

# Configuration paths
MAC_CONFIG = '/etc/field-trainer-macs.conf'
MAC_STATE = '/etc/field-trainer-mac-filter-state'
MAC_SCRIPT = '/opt/scripts/manage_mac_filter.sh'

@app.route('/api/mesh/security', methods=['GET', 'POST'])
def mesh_security():
    """Manage mesh network MAC filtering"""

    if request.method == 'GET':
        # Get current filter status
        try:
            # Check if ebtables chain exists
            result = subprocess.run(
                ['sudo', 'ebtables', '-t', 'filter', '-L', 'FT_MAC_FILTER'],
                capture_output=True, text=True, timeout=5
            )

            enabled = result.returncode == 0

            # Count authorized MACs from config
            mac_count = 0
            if os.path.exists(MAC_CONFIG):
                with open(MAC_CONFIG, 'r') as f:
                    for line in f:
                        if line.startswith('DEVICE_') and 'MAC=' in line:
                            mac_count += 1

            # Load saved state
            saved_state = False
            if os.path.exists(MAC_STATE):
                try:
                    with open(MAC_STATE, 'r') as f:
                        state_data = json.load(f)
                        saved_state = state_data.get('mac_filtering', False)
                except:
                    pass

            return jsonify({
                'success': True,
                'enabled': enabled,
                'saved_state': saved_state,
                'mac_count': mac_count,
                'status': 'Filtered' if enabled else 'Open'
            })

        except Exception as e:
            logger.error(f"Error getting mesh security status: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        # Toggle MAC filtering
        data = request.get_json()
        enabled = data.get('enabled', False)

        try:
            # Run management script
            cmd = ['sudo', MAC_SCRIPT, 'enable' if enabled else 'disable']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Propagate to other devices
                propagate_mac_filter(enabled)

                return jsonify({
                    'success': True,
                    'enabled': enabled,
                    'message': f"MAC filtering {'enabled' if enabled else 'disabled'}"
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.stderr or 'Failed to change MAC filtering'
                }), 500

        except Exception as e:
            logger.error(f"Error updating mesh security: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mesh/devices', methods=['GET'])
def get_mesh_devices():
    """Get authorized device MACs"""
    devices = []

    if os.path.exists(MAC_CONFIG):
        try:
            with open(MAC_CONFIG, 'r') as f:
                for line in f:
                    if line.startswith('DEVICE_') and '=' in line:
                        parts = line.strip().split('=')
                        if len(parts) == 2:
                            device_num = parts[0].replace('DEVICE_', '').replace('_MAC', '')
                            mac = parts[1].strip('"').strip("'")
                            devices.append({
                                'device_num': device_num,
                                'device': f'D{device_num}',
                                'mac': mac,
                                'ip': f'192.168.99.10{device_num}' if device_num != '0' else '192.168.99.100'
                            })
        except Exception as e:
            logger.error(f"Error reading MAC config: {e}")

    return jsonify({'success': True, 'devices': devices})

@app.route('/api/mesh/devices', methods=['POST'])
def update_mesh_devices():
    """Update device MAC addresses (for hardware replacement)"""
    try:
        data = request.get_json()
        devices = data.get('devices', [])

        if not devices or len(devices) != 6:
            return jsonify({'success': False, 'error': 'Invalid device data - need exactly 6 devices'}), 400

        # Validate MAC addresses
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')

        for device in devices:
            mac = device.get('mac', '')
            if not mac_pattern.match(mac):
                return jsonify({
                    'success': False,
                    'error': f'Invalid MAC address for Device {device.get("device_num")}: {mac}'
                }), 400

        # Write new config
        with open(MAC_CONFIG, 'w') as f:
            f.write("# Field Trainer Device MAC Addresses\n")
            f.write(f"# Updated: {datetime.now().isoformat()}\n")
            f.write("\n")
            for device in sorted(devices, key=lambda d: int(d['device_num'])):
                f.write(f"# Device {device['device_num']}\n")
                f.write(f"DEVICE_{device['device_num']}_MAC=\"{device['mac']}\"\n")
                f.write("\n")
            f.write("# Total devices configured: 6\n")

        logger.info(f"Updated MAC configuration with {len(devices)} devices")

        # If filtering is enabled, re-apply
        result = subprocess.run(
            ['sudo', 'ebtables', '-t', 'filter', '-L', 'FT_MAC_FILTER'],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            subprocess.run(['sudo', MAC_SCRIPT, 'enable'], timeout=10)
            logger.info("Re-applied MAC filtering with new addresses")

        return jsonify({'success': True, 'message': 'Device MACs updated successfully'})

    except Exception as e:
        logger.error(f"Error updating device MACs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def propagate_mac_filter(enabled):
    """Propagate MAC filter state to all client devices"""
    client_ips = ['192.168.99.101', '192.168.99.102', '192.168.99.103',
                  '192.168.99.104', '192.168.99.105']

    for ip in client_ips:
        try:
            action = 'enable' if enabled else 'disable'
            cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no pi@{ip} 'sudo {MAC_SCRIPT} {action}' 2>/dev/null"
            subprocess.run(cmd, shell=True, timeout=5)
            logger.info(f"Updated MAC filter on {ip}: {action}")
        except Exception as e:
            logger.warning(f"Could not update MAC filter on {ip}: {e}")

# ====== End Mesh Network Security ======

@app.route('/api/teams/search')
def search_teams_api():
    """API: Search and filter teams"""
    try:
        search_term = request.args.get('search')
        sport = request.args.get('sport')
        gender = request.args.get('gender')
        coach = request.args.get('coach')
        active_only = request.args.get('active', 'true').lower() == 'true'

        teams = db.search_teams(
            search_term=search_term,
            sport=sport,
            gender=gender,
            coach_name=coach,
            active_only=active_only
        )

        return jsonify(teams)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


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
        return jsonify({
            'success': True,
            'session_id': session_id,
            'redirect': url_for('session_setup_cones', session_id=session_id)
        })
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

def get_team_athletes(team_id):
    """API: Get athletes for team (for session setup)"""
    athletes = db.get_athletes_by_team(team_id)
    return jsonify(athletes)



@app.route('/api/team/<team_id>/athletes')
def get_team_athletes(team_id):
    """API: Get athletes for team (for session setup)"""
    athletes = db.get_athletes_by_team(team_id)
    return jsonify(athletes)

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

# ==================== TOUCH EVENT HANDLER ====================

# ==================== REGISTRY INTEGRATION ====================

def register_touch_handler():
    """
    Register our touch handler with REGISTRY
    This allows REGISTRY to call us when device touches occur
    """
    try:
        # Set the touch handler
        REGISTRY.set_touch_handler(session_service.handle_touch_event)

        # Verify registration
        print("✅ Touch handler registered with REGISTRY")
        print(f"   Handler function: {session_service.handle_touch_event}")
#        print(f"   REGISTRY handler: {getattr(REGISTRY, '_touch_handler', 'NOT SET')}")

        # Quick test to ensure it works
        test_timestamp = datetime.now()
        print(f"🧪 Testing handler with dummy call (should see warning about no active session)...")
        session_service.handle_touch_event("test_device", test_timestamp)  

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
#    app.run(host='0.0.0.0', port=5001, debug=True)
    # app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)


# ==================== DASHBOARD PLACEHOLDER ROUTES ====================
# These will be implemented in Phase 1


# Profile and Settings placeholders
@app.route('/profile')
def profile():
    return render_template_string('''
        {% extends "base.html" %}
        {% block content %}
        <h1>Coach Profile</h1>
        <p>Profile management coming soon in Phase 2</p>
        <a href="/dashboard" class="btn btn-primary">Back to Dashboard</a>
        {% endblock %}
    ''')

# ============================================================================
# PHASE 2: CONE VERIFICATION & DEPLOYMENT
# ============================================================================

@app.route('/api/session/<session_id>/status')
def api_session_status(session_id):
    """API: Get session status (proxy to blueprint)"""
    from routes.sessions_bp import session_status
    return session_status(session_id)

@app.route('/session/<session_id>/setup/cones')
@app.route('/api/session/<session_id>/prepare-course', methods=['POST'])
def api_prepare_course(session_id):
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

@app.route('/api/session/<session_id>/deploy-course', methods=['POST'])
def api_deploy_course(session_id):
    """Deploy course - set devices to GREEN and activate"""
    print(f"\n{'='*80}")
    print(f"🚨 API_DEPLOY_COURSE CALLED - Session: {session_id}")
    print(f"{'='*80}\n")
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

        # NOTE: Do NOT activate here - activation happens when GO is pressed
        # Activating here sends {"cmd": "start"} which overrides colors

        # Check if Simon Says - DON'T set to green, we'll set assigned colors separately
        is_simon_says = course.get('mode') == 'pattern'

        if not is_simon_says:
            # Regular courses: Set all devices to GREEN
            for device in devices:
                try:
                    REGISTRY.set_led(device['device_id'], pattern='solid_green')
                except Exception as e:
                    print(f"⚠️  Failed to set {device['device_id']} to green: {e}")
        else:
            print(f"📍 Simon Says detected - skipping green, will set assigned colors")

        # Mark course as deployed
        db.mark_course_deployed(session_id)

        REGISTRY.log(f"Course deployed: {course['course_name']}")

        # If Simon Says, set assigned colors NOW
        if is_simon_says:
            print("\n🎨 Calling set-simon-colors endpoint...")
            try:
                import requests
                color_response = requests.post(
                    f'http://localhost:5001/session/{session_id}/set-simon-colors',
                    timeout=30
                )
                print(f"   Response: {color_response.status_code}")
            except Exception as e:
                print(f"   ⚠️  Error: {e}")

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

# ============================================================================
# PHASE 2B: COURSE DESIGN & MANAGEMENT
# ============================================================================

@app.route('/courses')
def courses_list():
    """List all courses"""
    builtin_courses = db.get_builtin_courses()
    custom_courses = db.get_custom_courses()
    
    return render_template(
        'courses.html',
        builtin_courses=builtin_courses,
        custom_courses=custom_courses
    )


@app.route('/courses/<int:course_id>/view')
def view_course(course_id):
    """View course details"""
    course = db.get_course(course_id)
    if not course:
        return "Course not found", 404

    # Load SVG content from file if filename is stored
    if course.get('diagram_svg'):
        svg_content = db.get_course_svg_content(course_id)
        if svg_content:
            course['diagram_svg'] = svg_content

    actions = db.get_course_actions(course_id)
    course['actions'] = actions

    return render_template('course_view.html', course=course)

@app.route('/courses/design')
def course_design():
    """Course design accordion interface (v5)"""
    edit_id = request.args.get('edit')
    duplicate_id = request.args.get('duplicate')

    course = None
    if edit_id:
        course = db.get_course(int(edit_id))
        course['actions'] = db.get_course_actions(int(edit_id))
        # Load SVG content from file for editing
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(edit_id))
            if svg_content:
                course['diagram_svg'] = svg_content
    elif duplicate_id:
        course = db.get_course(int(duplicate_id))
        course['actions'] = db.get_course_actions(int(duplicate_id))
        course['course_name'] = f"{course['course_name']} (Copy)"
        course['is_builtin'] = 0
        # Load SVG content from file for duplication
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(duplicate_id))
            if svg_content:
                course['diagram_svg'] = svg_content

    return render_template('course_design_v5.html', course=course, mode='edit' if edit_id else 'duplicate' if duplicate_id else 'new')

@app.route('/courses/design/v2')
def course_design_v2():
    """Course design accordion prototype"""
    edit_id = request.args.get('edit')
    duplicate_id = request.args.get('duplicate')

    course = None
    if edit_id:
        course = db.get_course(int(edit_id))
        course['actions'] = db.get_course_actions(int(edit_id))
        # Load SVG content from file for editing
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(edit_id))
            if svg_content:
                course['diagram_svg'] = svg_content
    elif duplicate_id:
        course = db.get_course(int(duplicate_id))
        course['actions'] = db.get_course_actions(int(duplicate_id))
        course['course_name'] = f"{course['course_name']} (Copy)"
        course['is_builtin'] = 0
        # Load SVG content from file for duplication
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(duplicate_id))
            if svg_content:
                course['diagram_svg'] = svg_content

    return render_template('course_design_v2.html', course=course, mode='edit' if edit_id else 'duplicate' if duplicate_id else 'new')

@app.route('/courses/design/v3')
def course_design_v3():
    """Course design accordion v3 - side-by-side layout"""
    edit_id = request.args.get('edit')
    duplicate_id = request.args.get('duplicate')

    course = None
    if edit_id:
        course = db.get_course(int(edit_id))
        course['actions'] = db.get_course_actions(int(edit_id))
        # Load SVG content from file for editing
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(edit_id))
            if svg_content:
                course['diagram_svg'] = svg_content
    elif duplicate_id:
        course = db.get_course(int(duplicate_id))
        course['actions'] = db.get_course_actions(int(duplicate_id))
        course['course_name'] = f"{course['course_name']} (Copy)"
        course['is_builtin'] = 0
        # Load SVG content from file for duplication
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(duplicate_id))
            if svg_content:
                course['diagram_svg'] = svg_content

    return render_template('course_design_v3.html', course=course, mode='edit' if edit_id else 'duplicate' if duplicate_id else 'new')

@app.route('/courses/design/v4')
def course_design_v4():
    """Course design accordion v4 - reorganized sections"""
    edit_id = request.args.get('edit')
    duplicate_id = request.args.get('duplicate')

    course = None
    if edit_id:
        course = db.get_course(int(edit_id))
        course['actions'] = db.get_course_actions(int(edit_id))
        # Load SVG content from file for editing
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(edit_id))
            if svg_content:
                course['diagram_svg'] = svg_content
    elif duplicate_id:
        course = db.get_course(int(duplicate_id))
        course['actions'] = db.get_course_actions(int(duplicate_id))
        course['course_name'] = f"{course['course_name']} (Copy)"
        course['is_builtin'] = 0
        # Load SVG content from file for duplication
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(duplicate_id))
            if svg_content:
                course['diagram_svg'] = svg_content

    return render_template('course_design_v4.html', course=course, mode='edit' if edit_id else 'duplicate' if duplicate_id else 'new')

@app.route('/api/courses', methods=['POST'])
def save_course():
    """Create new course from design wizard (or update existing in edit mode)"""
    try:
        data = request.get_json()

        course_mode = data.get('mode', 'sequential')  # sequential or pattern
        course_id = data.get('course_id')
        is_editing = course_id is not None  # If course_id exists, we're editing

        print(f"💾 SAVE COURSE REQUEST: course_mode={course_mode}, course_id={course_id}, is_editing={is_editing}, name={data.get('course_name')}")
        print(f"   Stations count: {len(data.get('stations', []))}")
        if data.get('stations'):
            print(f"   First station distance: {data['stations'][0].get('distance')}")

        # Check if course name exists (skip if editing the same course)
        existing = db.get_course_by_name(data['course_name'])
        if existing:
            # Allow saving if we're editing the same course
            if is_editing and existing['course_id'] == course_id:
                # This is fine - editing the same course, can keep the same name
                print(f"   ✓ Editing existing course {course_id}, name unchanged")
                pass
            else:
                return jsonify({
                    'success': False,
                    'error': f"Course '{data['course_name']}' already exists. Please use a different name."
                }), 400

        # Transform stations to actions format
        actions = []
        for station in data.get('stations', []):
            seq = station['sequence']

            # Determine action_type
            if seq == 0:
                action_type = 'audio_start'
            else:
                action_type = 'touch_checkpoint'

            # Determine triggers and completion flags
            triggers_next = (seq == 1)  # Second device triggers next athlete
            marks_complete = (seq == len(data['stations']) - 1)  # Last device marks completion

            # Build action
            action = {
                'sequence': seq,
                'device_id': station['device_id'],
                'device_name': station.get('device_name', station['device_id']),
                'action': station.get('action', 'default_beep'),
                'action_type': action_type,
                'audio_file': station.get('action', 'default_beep') + '.mp3',
                'instruction': station.get('instruction', ''),
                'min_time': 0.1 if seq == 0 else 1.0,
                'max_time': 30.0,
                'triggers_next_athlete': triggers_next,
                'marks_run_complete': marks_complete,
                'distance': station.get('distance', 0),
                'behavior_config': station.get('behavior_config'),
                'device_function': station.get('device_function'),
                'detection_method': station.get('detection_method'),
                'group_identifier': station.get('group_identifier')
            }
            actions.append(action)

        # Calculate total distance
        total_distance = sum(a.get('distance', 0) for a in actions)

        # Handle SVG diagram - save to file instead of database
        svg_filename = None
        svg_content = data.get('diagram_svg')
        if svg_content:
            import os
            import re

            # Generate filename from course name (sanitize)
            safe_name = re.sub(r'[^\w\s-]', '', data['course_name']).strip()
            safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
            svg_filename = f"{safe_name}.svg"

            # Save SVG to file
            svg_dir = '/opt/static/svg/courses'
            os.makedirs(svg_dir, exist_ok=True)
            svg_path = os.path.join(svg_dir, svg_filename)

            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)

            print(f"   ✓ Saved SVG diagram to {svg_path}")

        # Prepare course data for import
        course_data = {
            'course_name': data['course_name'],
            'description': data.get('description', ''),
            'category': data.get('category', 'Custom'),
            'mode': data.get('mode', 'sequential'),  # Get mode from UI, default to sequential
            'num_devices': data.get('num_devices', len(actions)),
            'distance_unit': data.get('distance_unit', 'yards'),
            'total_distance': total_distance,
            'diagram_svg': svg_filename,  # Store filename, not content
            'layout_instructions': data.get('instruction', ''),
            'version': '2.0',
            'actions': actions
        }

        # If editing, update the existing course in place
        if is_editing and course_id:
            # Verify the course exists and is not built-in
            old_course = db.get_course(course_id)
            if not old_course:
                return jsonify({
                    'success': False,
                    'error': f'Course {course_id} not found'
                }), 404
            if old_course.get('is_builtin'):
                return jsonify({
                    'success': False,
                    'error': 'Cannot edit built-in courses'
                }), 400

            # Update the course in place (preserving course_id)
            with db.get_connection() as conn:
                # Update main course record
                conn.execute('''
                    UPDATE courses
                    SET course_name = ?,
                        description = ?,
                        category = ?,
                        mode = ?,
                        num_devices = ?,
                        distance_unit = ?,
                        total_distance = ?,
                        diagram_svg = ?,
                        layout_instructions = ?,
                        version = ?,
                        updated_at = ?
                    WHERE course_id = ?
                ''', (
                    course_data['course_name'],
                    course_data['description'],
                    course_data['category'],
                    course_data['mode'],
                    course_data['num_devices'],
                    course_data['distance_unit'],
                    course_data['total_distance'],
                    course_data['diagram_svg'],
                    course_data['layout_instructions'],
                    course_data['version'],
                    datetime.utcnow().isoformat(),
                    course_id
                ))

                # Delete existing actions
                conn.execute('DELETE FROM course_actions WHERE course_id = ?', (course_id,))

                # Insert updated actions
                for action in actions:
                    conn.execute('''
                        INSERT INTO course_actions (
                            course_id, sequence, device_id, device_name, action, action_type,
                            audio_file, instruction, min_time, max_time,
                            triggers_next_athlete, marks_run_complete, distance
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        course_id,
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
                        action['distance']
                    ))

            # Reload courses in REGISTRY so new/edited course is immediately available
            REGISTRY.reload_courses()
            return jsonify({'success': True, 'course_id': course_id})

        # For new courses, create using import method
        new_course_id = db.create_course_from_import(course_data)

        # Reload courses in REGISTRY so new course is immediately available
        REGISTRY.reload_courses()
        return jsonify({'success': True, 'course_id': new_course_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    """Delete a custom course"""
    try:
        course = db.get_course(course_id)
        if course and course.get('is_builtin'):
            return jsonify({'success': False, 'error': 'Cannot delete built-in courses'}), 400

        db.delete_course(course_id)

        # Reload courses in REGISTRY so deleted course is removed
        REGISTRY.reload_courses()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/courses/<int:course_id>/export')
def export_course_api(course_id):
    """Export course as JSON"""
    try:
        course = db.get_course(course_id)
        actions = db.get_course_actions(course_id)
        
        export_data = {
            'course_name': course['course_name'],
            'description': course['description'],
            'category': course['category'],
            'mode': course['mode'],
            'num_devices': course['num_devices'],
            'distance_unit': course['distance_unit'],
            'total_distance': course['total_distance'],
            'diagram_svg': course['diagram_svg'],
            'layout_instructions': course['layout_instructions'],
            'version': course['version'],
            'actions': actions
        }
        
        return jsonify(export_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/courses/import', methods=['POST'])
def import_course_api():
    """Import course from JSON"""
    try:
        data = request.get_json()
        
        # Check if course name exists
        existing = db.get_course_by_name(data['course_name'])
        if existing:
            return jsonify({
                'success': False, 
                'error': f"Course '{data['course_name']}' already exists. Please rename in the JSON file."
            }), 400
        
        # Create course
        course_id = db.create_course_from_import(data)
        
        return jsonify({'success': True, 'course_id': course_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/devices/available')
def get_available_devices():
    """Get list of available devices from registry"""
    try:
        # Get snapshot from REGISTRY (same as Admin page)
        snap = REGISTRY.snapshot()
        nodes = snap.get('nodes', [])
        
        available = []
        
        # Device 0
        device_0 = next((n for n in nodes if n['node_id'] == '192.168.99.100'), None)
        available.append({
            'device_id': '192.168.99.100',
            'device_name': 'Device 0',
            'display_name': 'Start',
            # 'online': device_0 is not None and device_0.get('status') != 'Offline'
            'online': True  # Start (Device 0) is always online when server is running, changed for course_design
        })
        
        # Cones 1-5
        for i in range(1, 6):
            device_id = f'192.168.99.{100 + i}'
            node = next((n for n in nodes if n['node_id'] == device_id), None)
            online = node is not None and node.get('status') != 'Offline'
            
            available.append({
                'device_id': device_id,
                'device_name': f'Device {i}',
                'display_name': f'Cone {i}',
                'online': online
            })
        
        return jsonify({
            'success': True,
            'devices': available
        })
    except Exception as e:
        print(f"Error getting devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/courses/design/v5')
def course_design_v5():
    """Course design accordion v5 - final layout with colorful dividers"""
    edit_id = request.args.get('edit')
    duplicate_id = request.args.get('duplicate')

    course = None
    if edit_id:
        course = db.get_course(int(edit_id))
        course['actions'] = db.get_course_actions(int(edit_id))
        # Load SVG content from file for editing
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(edit_id))
            if svg_content:
                course['diagram_svg'] = svg_content
    elif duplicate_id:
        course = db.get_course(int(duplicate_id))
        course['actions'] = db.get_course_actions(int(duplicate_id))
        course['course_name'] = f"{course['course_name']} (Copy)"
        course['is_builtin'] = 0
        # Load SVG content from file for duplication
        if course.get('diagram_svg'):
            svg_content = db.get_course_svg_content(int(duplicate_id))
            if svg_content:
                course['diagram_svg'] = svg_content

    return render_template('course_design_v5.html', course=course, mode='edit' if edit_id else 'duplicate' if duplicate_id else 'new')


# ==================== SETTINGS ROUTES ====================

@app.route('/settings')
def settings_page():
    """Settings management page"""
    return render_template('settings.html')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all current settings"""
    try:
        settings = settings_mgr.load_settings()
        audio_files = settings_mgr.get_audio_files()
        root_audio_files = settings_mgr.get_root_audio_files()

        return jsonify({
            'success': True,
            'settings': settings,
            'audio_files': audio_files,
            'root_audio_files': root_audio_files
        })
    except Exception as e:
        print(f"Error loading settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save individual setting"""
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')

        if not key:
            return jsonify({'success': False, 'error': 'Missing key'}), 400

        success = settings_mgr.save_setting(key, str(value))

        # Sync audio settings to AudioManager (for MAX98357A)
        if success and REGISTRY._audio:
            try:
                if key == 'voice_gender' and value in ('male', 'female'):
                    REGISTRY._audio.set_voice_gender(value)
                    print(f"✓ Voice gender set to '{value}' via AudioManager")
                elif key == 'system_volume':
                    REGISTRY._audio.set_volume(int(value))
                    print(f"✓ Volume set to {value}% via AudioManager")
            except Exception as audio_err:
                print(f"⚠ Failed to sync {key} to AudioManager: {audio_err}")

        return jsonify({'success': success})
    except Exception as e:
        print(f"Error saving setting: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """Reset all settings to defaults"""
    try:
        success = settings_mgr.reset_to_defaults()

        # Sync default audio settings to AudioManager
        if success and REGISTRY._audio:
            try:
                REGISTRY._audio.set_voice_gender('male')  # Default from SettingsManager
                REGISTRY._audio.set_volume(60)  # Default from SettingsManager
                print(f"✓ AudioManager reset to defaults (male voice, 60% volume)")
            except Exception as audio_err:
                print(f"⚠ Failed to reset AudioManager: {audio_err}")

        return jsonify({'success': success})
    except Exception as e:
        print(f"Error resetting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/audio-files', methods=['GET'])
def get_audio_files():
    """Get list of audio files"""
    try:
        files = settings_mgr.get_audio_files()
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/test-audio', methods=['POST'])
def test_audio():
    """Play audio file through selected device speaker (server-side playback)"""
    try:
        data = request.get_json()
        filename = data.get('filename', '')
        device_id = data.get('device_id', '192.168.99.100')  # Default to Device 0

        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'}), 400

        # Remove .mp3 extension if present (AudioManager/devices add it)
        clip_name = filename.replace('.mp3', '').replace('.wav', '')

        print(f"\n{'='*60}")
        print(f"🔊 AUDIO TEST REQUEST")
        print(f"   Device: {device_id}")
        print(f"   Clip: {clip_name}")
        print(f"{'='*60}")

        # Handle "ALL" - play sequentially on all devices
        if device_id == 'ALL':
            import threading
            import time as time_module

            print(f"   Playing on ALL devices sequentially...")

            all_devices = [
                ('192.168.99.100', 'Start'),
                ('192.168.99.101', 'Cone 1'),
                ('192.168.99.102', 'Cone 2'),
                ('192.168.99.103', 'Cone 3'),
                ('192.168.99.104', 'Cone 4'),
                ('192.168.99.105', 'Cone 5'),
            ]

            results = {'success': [], 'failed': []}

            def play_sequential():
                """Play audio on each device with delay between"""
                print(f"\n   🎵 Starting sequential playback thread...")
                print(f"   Clip: {clip_name}")
                print(f"   Devices: Start → Cone 1 → Cone 2 → Cone 3 → Cone 4 → Cone 5")

                for dev_id, dev_name in all_devices:
                    try:
                        print(f"\n   → Playing on {dev_name}...")

                        # Play on device
                        if dev_id == '192.168.99.100':
                            # Device 0 - local AudioManager
                            if REGISTRY._audio:
                                success = REGISTRY._audio.play(clip_name)
                                if success:
                                    results['success'].append(dev_name)
                                    print(f"   ✓ {dev_name} - audio playing")
                                else:
                                    results['failed'].append(dev_name)
                                    print(f"   ✗ {dev_name} - audio file not found")
                            else:
                                results['failed'].append(dev_name)
                                print(f"   ✗ {dev_name} - AudioManager not available")
                        else:
                            # Remote cones - check status first, then send command
                            # IMPORTANT: Check status outside of play_audio to avoid deadlock
                            is_online = False
                            with REGISTRY.nodes_lock:
                                node = REGISTRY.nodes.get(dev_id)
                                if node and node.status not in ('Offline', 'Unknown') and node._writer:
                                    is_online = True

                            # Release lock before calling play_audio (which also needs the lock)
                            if is_online:
                                success = REGISTRY.play_audio(dev_id, clip_name)
                                if success:
                                    results['success'].append(dev_name)
                                    print(f"   ✓ {dev_name} - command sent")
                                else:
                                    results['failed'].append(dev_name)
                                    print(f"   ✗ {dev_name} - send failed")
                            else:
                                results['failed'].append(dev_name)
                                print(f"   ⊘ {dev_name} - offline/not connected")

                        # Wait 3 seconds before next device (typical audio clip length)
                        time_module.sleep(3)

                    except Exception as e:
                        results['failed'].append(dev_name)
                        print(f"   ✗ {dev_name} - error: {e}")
                        import traceback
                        traceback.print_exc()

                print(f"\n   Sequential playback complete:")
                print(f"   Success: {len(results['success'])} devices")
                print(f"   Failed: {len(results['failed'])} devices")

            # Start sequential playback in background thread
            thread = threading.Thread(target=play_sequential, daemon=True)
            thread.start()

            # Return immediately
            return jsonify({
                'success': True,
                'message': f'Playing {filename} sequentially on all devices (Start → Cone 5)',
                'mode': 'sequential'
            })

        # Handle single device (original code)

        # Route based on device
        if device_id == '192.168.99.100':
            # Device 0 (Start) - Play through local AudioManager
            if REGISTRY._audio:
                success = REGISTRY._audio.play(clip_name)
                if success:
                    print(f"✓ Playing '{clip_name}' on Start (local AudioManager)")
                    return jsonify({'success': True, 'message': f'Playing {filename} on Start'})
                else:
                    print(f"✗ Audio file not found: {clip_name}")
                    return jsonify({'success': False, 'error': f'Audio file not found: {filename}'}), 404
            else:
                print(f"✗ AudioManager not available")
                return jsonify({'success': False, 'error': 'AudioManager not available on Start'}), 503
        else:
            # Remote device (Cones 1-5) - Send command via REGISTRY
            cone_num = int(device_id.split('.')[-1]) - 100

            # Check if device is online and connected
            with REGISTRY.nodes_lock:
                node = REGISTRY.nodes.get(device_id)
                if not node:
                    print(f"✗ Cone {cone_num} not found in registry")
                    return jsonify({
                        'success': False,
                        'error': f'Cone {cone_num} is not connected to the heartbeat server. Make sure cone is powered on and running client software.'
                    }), 404

                if node.status in ('Offline', 'Unknown'):
                    print(f"✗ Cone {cone_num} is {node.status}")
                    return jsonify({
                        'success': False,
                        'error': f'Cone {cone_num} is {node.status}. Check power and network connection.'
                    }), 503

                if not node._writer:
                    print(f"✗ Cone {cone_num} has no TCP writer (connection lost)")
                    return jsonify({
                        'success': False,
                        'error': f'Cone {cone_num} lost TCP connection. Try restarting the cone.'
                    }), 503

            # Send audio command to remote device
            print(f"   Sending audio command to Cone {cone_num} via TCP...")
            success = REGISTRY.play_audio(device_id, clip_name)
            if success:
                print(f"✓ Audio command sent to Cone {cone_num}")
                return jsonify({'success': True, 'message': f'Playing {filename} on Cone {cone_num}'})
            else:
                print(f"✗ Failed to send audio command to Cone {cone_num}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to send command to Cone {cone_num}. Check TCP connection and cone client logs.'
                }), 500

    except Exception as e:
        print(f"Error playing test audio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files from voice-specific subdirectories or root"""
    import os
    from flask import send_file, abort

    audio_dir = '/opt/field_trainer/audio'

    # Get user's voice gender preference
    try:
        voice_gender = settings_mgr.get_setting('voice_gender') or 'male'
    except:
        voice_gender = 'male'

    # Try voice-specific directory first (male/female)
    gender_path = os.path.join(audio_dir, voice_gender, filename)
    if os.path.exists(gender_path) and os.path.getsize(gender_path) > 0:
        return send_file(gender_path, mimetype='audio/mpeg')

    # Try opposite gender as fallback
    other_gender = 'female' if voice_gender == 'male' else 'male'
    other_path = os.path.join(audio_dir, other_gender, filename)
    if os.path.exists(other_path) and os.path.getsize(other_path) > 0:
        return send_file(other_path, mimetype='audio/mpeg')

    # Try root directory as last resort
    root_path = os.path.join(audio_dir, filename)
    if os.path.exists(root_path) and os.path.getsize(root_path) > 0:
        return send_file(root_path, mimetype='audio/mpeg')

    # File not found or empty
    abort(404)


@app.route('/api/settings/devices', methods=['GET'])
def get_devices():
    """Get list of devices and their status"""
    try:
        devices = []

        # Always include Device 0 (controller) as online
        devices.append({
            'device_id': '192.168.99.100',
            'name': 'Start',
            'status': 'online'
        })

        # Check status of Cones 1-5
        for i in range(1, 6):
            device_id = f'192.168.99.{100 + i}'
            status = 'offline'

            with REGISTRY.nodes_lock:
                node = REGISTRY.nodes.get(device_id)
                if node and node.status not in ('Offline', 'Unknown'):
                    status = 'online'

            devices.append({
                'device_id': device_id,
                'name': f'Cone {i}',
                'status': status
            })

        return jsonify({'success': True, 'devices': devices})
    except Exception as e:
        print(f"Error getting devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/network-info', methods=['GET'])
def get_network_info():
    """Get current network SSID"""
    try:
        # Try to get current SSID from iwgetid command
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            ssid = result.stdout.strip()
            return jsonify({'success': True, 'ssid': ssid})
        else:
            return jsonify({'success': True, 'ssid': 'Not connected'})
    except Exception as e:
        print(f"Error getting network info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/network/status', methods=['GET'])
def get_network_status():
    """Get current network mode status"""
    try:
        import json
        import os

        config_file = '/opt/data/network-config.json'
        status_file = '/opt/data/network-status.json'

        # Default response
        response = {
            'mode': 'unknown',
            'auto_switch': True,
            'ssid': 'Unknown',
            'message': 'Network status unavailable'
        }

        # Load config
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                response['mode'] = config.get('network_mode', {}).get('current', 'unknown')
                response['auto_switch'] = config.get('network_mode', {}).get('auto_switch', True)

        # Load status (contains the message with connection info and IP)
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status = json.load(f)
                # Get the message field (e.g., "Connected via Ethernet (192.168.7.116)")
                if 'message' in status:
                    response['message'] = status['message']
                # Override mode from status if present
                if 'mode' in status:
                    response['mode'] = status['mode']

        # Get current SSID (fallback if message not in status file)
        if 'Ethernet' not in response.get('message', ''):
            try:
                result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    response['ssid'] = result.stdout.strip()
                elif response['mode'] == 'offline':
                    response['ssid'] = 'Field_Trainer (AP Mode)'
            except:
                pass

        return jsonify(response)
    except Exception as e:
        print(f"Error getting network status: {e}")
        return jsonify({'mode': 'unknown', 'auto_switch': True, 'error': str(e)}), 400


@app.route('/api/network/force-mode', methods=['POST'])
def force_network_mode():
    """Force switch to online or offline mode"""
    try:
        data = request.get_json()
        mode = data.get('mode')  # 'online' or 'offline'

        if mode not in ['online', 'offline']:
            return jsonify({'success': False, 'error': 'Invalid mode. Must be "online" or "offline"'}), 400

        # Run network manager script to force mode
        result = subprocess.run(
            ['sudo', '/usr/bin/python3', '/opt/scripts/ft-network-manager.py', f'force-{mode}'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Switched to {mode} mode',
                'mode': mode
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to switch mode: {result.stderr}'
            }), 500
    except Exception as e:
        print(f"Error forcing network mode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/auto-switch', methods=['POST'])
def set_auto_switch():
    """Enable or disable automatic network mode switching"""
    try:
        import json

        data = request.get_json()
        enabled = data.get('enabled', True)

        config_file = '/opt/data/network-config.json'

        # Load existing config
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {
                "network_mode": {"current": "online", "auto_switch": True},
                "monitoring": {"internet_check_interval": 60, "internet_check_retries": 3, "failback_delay": 300},
                "access_point": {"enabled": False, "ssid": "Field_Trainer", "password": "RaspberryField2025", "ip": "192.168.10.1"}
            }

        # Update auto_switch setting
        config['network_mode']['auto_switch'] = bool(enabled)

        # Save config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)

        return jsonify({
            'success': True,
            'auto_switch': bool(enabled)
        })
    except Exception as e:
        print(f"Error setting auto-switch: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/test-led', methods=['POST'])
def test_led():
    """Test LED color on selected device(s)"""
    import threading
    import time

    try:
        data = request.get_json()
        color = data.get('color', 'orange')
        device = data.get('device', 'ALL')  # Get device parameter

        print(f"\n{'='*60}")
        print(f"🔦 LED TEST STARTED - Device: {device}, Color: {color}")
        print(f"{'='*60}")

        # Map color names to LED patterns
        color_map = {
            'orange': 'solid_amber',
            'red': 'solid_red',
            'green': 'solid_green',
            'blue': 'solid_blue',
            'yellow': 'solid_yellow',
            'white': 'solid_white',
            'purple': 'solid_purple',
            'cyan': 'solid_cyan',
            'chase_red': 'chase_red',
            'chase_green': 'chase_green',
            'chase_blue': 'chase_blue',
            'chase_yellow': 'chase_yellow',
            'chase_amber': 'chase_amber',
            'chase_white': 'chase_white',
            'chase_purple': 'chase_purple'
        }

        pattern = color_map.get(color, 'solid_amber')
        print(f"LED Pattern: {pattern}")

        # Determine which devices to test
        if device == 'ALL':
            device_ips = [f'192.168.99.{100 + i}' for i in range(6)]
            print(f"Testing ALL devices")
        else:
            device_ips = [device]
            device_name = "Start" if device == "192.168.99.100" else f"Cone {int(device.split('.')[-1]) - 100}"
            print(f"Testing single device: {device_name}")

        # Track results
        results = {'success': [], 'failed': []}

        # Turn on LEDs with detailed logging
        for device_ip in device_ips:
            try:
                print(f"\n--- Testing device {device_ip} ---")

                # Check device status first
                with REGISTRY.nodes_lock:
                    node = REGISTRY.nodes.get(device_ip)
                    if node:
                        print(f"Device status: {node.status}")
                        print(f"Has writer: {node._writer is not None}")
                    else:
                        print(f"Device not found in REGISTRY.nodes")

                # Send LED command
                success = REGISTRY.set_led(device_ip, pattern)

                if success:
                    results['success'].append(device_ip)
                    print(f"✅ LED command sent successfully to {device_ip}")
                else:
                    results['failed'].append(device_ip)
                    print(f"❌ LED command failed for {device_ip}")

            except Exception as e:
                results['failed'].append(device_ip)
                print(f"❌ Exception setting LED for {device_ip}: {e}")
                import traceback
                traceback.print_exc()

        # Summary
        print(f"\n{'='*60}")
        print(f"LED TEST SUMMARY:")
        print(f"  Success: {len(results['success'])} devices - {results['success']}")
        print(f"  Failed:  {len(results['failed'])} devices - {results['failed']}")
        print(f"{'='*60}\n")

        # Schedule LEDs to turn off after 5 seconds (DISABLED for Simon Says)
        # NOTE: Commented out so colors stay on for Simon Says testing
        # def turn_off_leds():
        #     time.sleep(5)
        #     print(f"\n🔦 Turning off LEDs...")
        #     for device_ip in device_ips:
        #         try:
        #             REGISTRY.set_led(device_ip, 'off')
        #         except Exception as e:
        #             print(f"Error turning off LED for {device_ip}: {e}")
        #     print(f"🔦 LED test complete\n")
        #
        # threading.Thread(target=turn_off_leds, daemon=True).start()
        print(f"\n💡 LEDs will stay on (auto-off disabled for Simon Says)")

        return jsonify({
            'success': True,
            'message': f'LED test started with color {color}',
            'results': results
        })
    except Exception as e:
        print(f"❌ Error testing LED: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/apply-volume', methods=['POST'])
def apply_volume():
    """Apply volume setting to system (MAX98357A I2S amplifier)"""
    try:
        data = request.get_json()
        volume = int(data.get('volume', 60))

        # Clamp volume to 0-100
        volume = max(0, min(100, volume))

        # Update AudioManager volume (controls mpg123 -f parameter)
        # MAX98357A uses software volume control via mpg123, not ALSA mixer
        volume_set = False
        if REGISTRY._audio:
            try:
                REGISTRY._audio.set_volume(volume)
                volume_set = True
                print(f"✓ Volume set to {volume}% via AudioManager (mpg123 -f parameter)")
            except Exception as audio_err:
                print(f"⚠ AudioManager volume update failed: {audio_err}")
        else:
            print(f"⚠ No AudioManager available - volume not applied to hardware")

        # Also save to settings database for persistence
        settings_mgr.save_setting('system_volume', str(volume))

        return jsonify({
            'success': True,
            'volume': volume,
            'hardware_applied': volume_set
        })

    except Exception as e:
        print(f"Error setting volume: {e}")
        import traceback
        traceback.print_exc()
        # Return success anyway - don't block UI
        return jsonify({
            'success': True,
            'volume': volume if 'volume' in locals() else 60,
            'hardware_applied': False,
            'note': 'Volume saved but hardware control unavailable'
        })


# ============================================
# TOUCH SENSOR CALIBRATION API ENDPOINTS
# ============================================

@app.route('/api/calibration/devices/status', methods=['GET'])
def calibration_devices_status():
    """Get status of all devices for calibration"""
    try:
        devices = []
        for device_num in range(6):  # Devices 0-5
            info = calibration_logic.get_device_info(device_num)
            status = calibration_logic.get_device_status(device_num)
            threshold_data = calibration_logic.get_current_threshold(device_num)

            devices.append({
                'device_num': device_num,
                'name': info['name'],
                'ip': info['ip'],
                'online': status['online'],
                'threshold': threshold_data.get('threshold', 0.0) if threshold_data.get('success') else None
            })

        return jsonify({
            'success': True,
            'devices': devices
        })
    except Exception as e:
        logger.error(f"Error getting calibration device status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/threshold', methods=['GET'])
def get_device_threshold(device_num):
    """Get current threshold for a device"""
    try:
        result = calibration_logic.get_current_threshold(device_num)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting threshold for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/threshold', methods=['POST'])
def set_device_threshold(device_num):
    """Set threshold for a device"""
    try:
        data = request.get_json()
        threshold = float(data.get('threshold', 0))

        result = calibration_logic.set_threshold(device_num, threshold)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting threshold for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/reading', methods=['GET'])
def get_device_reading(device_num):
    """Get current accelerometer reading from device"""
    try:
        result = calibration_logic.get_accelerometer_reading(device_num)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting reading for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/test-mode', methods=['POST'])
def device_test_mode(device_num):
    """Start/stop test mode on device"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)

        if enabled:
            threshold = float(data.get('threshold', 2.0))
            duration = int(data.get('duration', 10))
            result = calibration_logic.start_test_mode(device_num, threshold, duration)
        else:
            result = calibration_logic.stop_test_mode(device_num)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error controlling test mode for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/live-reading', methods=['POST'])
def device_live_reading(device_num):
    """Start/stop live reading mode on remote device"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        duration = int(data.get('duration', 10))

        if enabled:
            result = calibration_logic.start_live_reading(device_num, duration)
        else:
            result = calibration_logic.stop_live_reading(device_num)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error controlling live reading for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/calibration/device/<int:device_num>/calibrate', methods=['POST'])
def calibrate_device(device_num):
    """Run full calibration wizard on device"""
    try:
        result = calibration_logic.run_calibration_wizard(device_num)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error calibrating device {device_num}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/device0/touch', methods=['POST'])
def device0_touch():
    """Simulate touch event for Device 0 (192.168.99.100)"""
    try:
        from datetime import datetime

        # Trigger touch event for D0
        device_id = "192.168.99.100"
        timestamp = datetime.utcnow()

        # Call session service touch handler
        session_service.handle_touch_event(device_id, timestamp)

        print(f"✓ D0 touch event triggered at {timestamp.isoformat()}")

        return jsonify({
            'success': True,
            'device_id': device_id,
            'timestamp': timestamp.isoformat()
        })
    except Exception as e:
        logger.error(f"Error handling D0 touch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("Starting Flask app on port 5001...")
    app.run(host='0.0.0.0', port=5001, debug=False)
