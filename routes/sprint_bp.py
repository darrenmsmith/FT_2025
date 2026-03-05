#!/usr/bin/env python3
"""
Sprint Blueprint — routes for Sprint course type.
"""

import json
import time
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, Response, stream_with_context

from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY
from services.sprint_service import get_sprint_service

sprint_bp = Blueprint('sprint', __name__)
db = DatabaseManager('/opt/data/field_trainer.db')

DEVICE_0 = '192.168.99.100'
START_CONE_DEFAULT = '192.168.99.100'  # Gateway — at the start line with the coach


# ===========================================================================
# Course creation
# ===========================================================================

@sprint_bp.route('/sprint/course/new')
def course_new():
    """Sprint course creation form."""
    settings = db.get_coach_preferences()
    distance_unit = settings.get('distance_unit', 'yards')
    return render_template('sprint_course_new.html', distance_unit=distance_unit)


def _sprint_diagram_svg():
    """Generate inline SVG diagram for a sprint course."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 160" '
        'style="max-width:100%;font-family:Arial,sans-serif;">'
        # Start cone (triangle)
        '<polygon points="55,118 95,118 75,52" fill="#FF9800" stroke="#E65100" stroke-width="2"/>'
        '<text x="75" y="138" text-anchor="middle" font-size="13" fill="#555">Start Cone</text>'
        # Dashed distance line
        '<line x1="100" y1="88" x2="415" y2="88" stroke="#495057" stroke-width="2.5" stroke-dasharray="10,5"/>'
        '<polygon points="415,88 403,82 403,94" fill="#495057"/>'
        # Distance label
        '<text x="257" y="76" text-anchor="middle" font-size="13" fill="#495057">'
        'Distance (set at session setup)'
        '</text>'
        # Finish line
        '<line x1="430" y1="44" x2="430" y2="128" stroke="#28a745" stroke-width="4"/>'
        '<text x="448" y="92" text-anchor="start" font-size="13" fill="#28a745">Finish</text>'
        '</svg>'
    )


@sprint_bp.route('/sprint/course/create', methods=['POST'])
def course_create():
    """Create a sprint course record."""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'error': 'Course name is required'}), 400

        # Create the base course with one action for the gateway (start line)
        actions = [{
            'device_id': START_CONE_DEFAULT,
            'device_name': 'Gateway',
            'action': 'start',
            'action_type': 'sprint_start',
        }]
        course_id = db.create_course(
            name=name,
            description='Sprint course — distance and countdown configured at session setup',
            course_type='sprint',
            actions=actions,
            mode='sprint',
            category='speed',
            total_devices=1,
        )

        # Set sprint-specific columns and diagram (not in create_course signature)
        settings = db.get_coach_preferences()
        distance_unit = settings.get('distance_unit', 'yards')
        with db.get_connection() as conn:
            conn.execute(
                'UPDATE courses SET distance_unit = ?, countdown_interval = ?, timing_mode = ?, diagram_svg = ? WHERE course_id = ?',
                (distance_unit, 5, 'manual', _sprint_diagram_svg(), course_id)
            )

        REGISTRY.log(f"[SPRINT] Course created: {name}", source='sprint')
        return jsonify({'success': True, 'course_id': course_id, 'redirect': url_for('sessions.session_setup')})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


# ===========================================================================
# Monitor UI
# ===========================================================================

@sprint_bp.route('/sprint/monitor/<session_id>')
def monitor(session_id):
    """Sprint session monitor page."""
    session = db.get_session(session_id)
    if not session:
        return "Session not found", 404

    course = db.get_course(session['course_id'])
    if not course:
        return "Course not found", 404

    team = db.get_team(session['team_id'])
    runs = db.get_session_runs(session_id)

    return render_template(
        'sprint_monitor.html',
        session=session,
        course=course,
        team=team,
        runs=runs,
    )


# ===========================================================================
# SSE — start signal stream
# ===========================================================================

def _timer_event_generator(session_id):
    """Generator for SSE stream — yields beep_fired event when GO fires."""
    last_beep_ts = None
    deadline = time.time() + 3600  # 1-hour max connection

    while time.time() < deadline:
        svc = get_sprint_service()
        state = svc.get_status(session_id)

        beep_ts = state.get('beep_fired_at')
        if beep_ts and beep_ts != last_beep_ts:
            last_beep_ts = beep_ts
            yield f"event: beep_fired\ndata: {json.dumps({'beep_ts': beep_ts})}\n\n"

        yield ": keepalive\n\n"
        time.sleep(0.1)


@sprint_bp.route('/session/sprint/<session_id>/timer-stream')
def timer_stream(session_id):
    """SSE endpoint — browser connects here to receive beep_fired events."""
    return Response(
        stream_with_context(_timer_event_generator(session_id)),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ===========================================================================
# API — session lifecycle
# ===========================================================================

@sprint_bp.route('/api/sprint/start/<session_id>', methods=['POST'])
def start_session(session_id):
    """Start sprint session (GO on setup screen)."""
    svc = get_sprint_service()
    result = svc.start_session(session_id)
    return jsonify(result)


@sprint_bp.route('/api/sprint/status/<session_id>')
def get_status(session_id):
    """Live status — polled every second by the monitor."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    runs = db.get_session_runs(session_id)
    svc = get_sprint_service()
    state = svc.get_status(session_id)

    return jsonify({
        'session_status': session['status'],
        'sprint_status': state.get('status', 'idle'),
        'countdown_active': state.get('countdown_active', False),
        'countdown_remaining': state.get('countdown_remaining', 0),
        'current_run_id': state.get('current_run_id'),
        'beep_fired_at': state.get('beep_fired_at'),
        'runs': runs,
    })


@sprint_bp.route('/api/sprint/go/<session_id>', methods=['POST'])
def go(session_id):
    """Coach taps GO — starts countdown."""
    svc = get_sprint_service()
    result = svc.go(session_id)
    return jsonify(result)


@sprint_bp.route('/api/sprint/stop/<session_id>', methods=['POST'])
def stop(session_id):
    """Browser sends elapsed time after coach taps STOP."""
    data = request.get_json() or {}
    time_seconds = data.get('time_seconds')
    if time_seconds is None:
        return jsonify({'success': False, 'error': 'time_seconds required'}), 400

    svc = get_sprint_service()
    result = svc.stop(session_id, float(time_seconds))

    # If session is complete, fetch ranked results
    if result.get('session_complete'):
        result['results'] = db.get_sprint_results(session_id)

    return jsonify(result)


@sprint_bp.route('/api/sprint/pause/<session_id>', methods=['POST'])
def pause(session_id):
    svc = get_sprint_service()
    result = svc.pause(session_id)
    return jsonify(result)


@sprint_bp.route('/api/sprint/resume/<session_id>', methods=['POST'])
def resume(session_id):
    svc = get_sprint_service()
    result = svc.resume(session_id)
    return jsonify(result)


@sprint_bp.route('/api/sprint/end/<session_id>', methods=['POST'])
def end_session(session_id):
    """Coach ends session early (with confirmation from UI)."""
    svc = get_sprint_service()
    result = svc.end_session(session_id, reason='incomplete')
    if result['success']:
        result['results'] = db.get_sprint_results(session_id)
    return jsonify(result)


# ===========================================================================
# API — roster management
# ===========================================================================

@sprint_bp.route('/api/sprint/restore/<session_id>/<run_id>', methods=['POST'])
def restore_athlete(session_id, run_id):
    """Restore an absent or paused athlete to end of pending queue."""
    try:
        db.move_run_to_end_of_queue(session_id, run_id)
        REGISTRY.log(f"[SPRINT] Athlete restored to queue: run {run_id[:8]}", source='sprint')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@sprint_bp.route('/api/sprint/reorder/<session_id>', methods=['POST'])
def reorder(session_id):
    """Swap queue positions for two adjacent pending athletes (up/down arrows)."""
    try:
        data = request.get_json() or {}
        run_id = data.get('run_id')
        direction = data.get('direction')  # 'up' or 'down'

        if not run_id or direction not in ('up', 'down'):
            return jsonify({'success': False, 'error': 'run_id and direction required'}), 400

        with db.get_connection() as conn:
            run = conn.execute(
                "SELECT queue_position FROM runs WHERE run_id = ? AND session_id = ?",
                (run_id, session_id)
            ).fetchone()
            if not run:
                return jsonify({'success': False, 'error': 'Run not found'}), 404

            pos = run['queue_position']
            op = '<' if direction == 'up' else '>'
            order = 'DESC' if direction == 'up' else 'ASC'

            neighbour = conn.execute(
                f"SELECT run_id, queue_position FROM runs "
                f"WHERE session_id = ? AND status = 'queued' AND queue_position {op} ? "
                f"ORDER BY queue_position {order} LIMIT 1",
                (session_id, pos)
            ).fetchone()

            if not neighbour:
                return jsonify({'success': True, 'swapped': False})

            # Swap positions
            conn.execute("UPDATE runs SET queue_position = -1 WHERE run_id = ?", (run_id,))
            conn.execute("UPDATE runs SET queue_position = ? WHERE run_id = ?", (pos, neighbour['run_id']))
            conn.execute("UPDATE runs SET queue_position = ? WHERE run_id = ?", (neighbour['queue_position'], run_id))

        return jsonify({'success': True, 'swapped': True})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400


@sprint_bp.route('/api/sprint/results/<session_id>')
def results(session_id):
    """Fetch ranked results for a completed session."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify({'results': db.get_sprint_results(session_id)})
