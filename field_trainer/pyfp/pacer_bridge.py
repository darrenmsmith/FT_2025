"""
PACER bridge — D26.

start_pacer(battery_id):
  Creates a beep_test session (20m, all team athletes) via db primitives,
  stores the session_id on a placeholder pyfp_event_result (raw_value=0),
  returns {'session_id': ..., 'redirect_url': ...}.

import_pacer_result(battery_id):
  Reads beep_test_results for the linked session, computes total_laps
  using the Léger 20m shuttle table, updates pyfp_event_result.raw_value,
  writes performance_history.
"""
import json
import sys

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager

_DB_PATH = '/opt/data/field_trainer.db'

# Shuttles per level — Léger 20m protocol (from beep_test_service.py)
_SHUTTLES_20M = {
    1: 7,  2: 8,  3: 8,  4: 8,  5: 9,  6: 9,  7: 10,
    8: 10, 9: 10, 10: 11, 11: 11, 12: 12, 13: 12, 14: 13,
    15: 13, 16: 13, 17: 14, 18: 14, 19: 15, 20: 15, 21: 15,
}


def compute_total_laps(level_completed: int, shuttle_failed_on: int | None,
                       start_level: int = 1) -> int:
    """Sum shuttles from start_level through level_completed + partial shuttles on failure."""
    first = max(1, start_level)
    total = sum(_SHUTTLES_20M.get(lv, 0) for lv in range(first, (level_completed or 0) + 1))
    if shuttle_failed_on and shuttle_failed_on > 1:
        total += shuttle_failed_on - 1
    return total


def start_pacer(battery_id: str, start_level: int = 1) -> dict:
    """
    Create a beep_test session for the battery's team.
    If a session is already linked, return its info without creating a new one.
    Returns {'session_id': str, 'redirect_url': str, 'created': bool}.
    """
    db = DatabaseManager(_DB_PATH)

    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        raise ValueError(f"Battery {battery_id!r} not found")

    # Check for existing linked session
    existing = db.get_pyfp_event_results_for_battery(battery_id)
    pacer_row = next((r for r in existing
                      if r['course_type'] == 'pyfp_pacer' and r['beep_test_session_id']), None)
    if pacer_row:
        sid = pacer_row['beep_test_session_id']
        return {'session_id': sid, 'redirect_url': f'/beep-test/monitor/{sid}', 'created': False}

    # Individual athlete only — the beep-test session is for this one athlete
    athlete    = db.get_athlete(battery['athlete_id'])
    team_id    = athlete['team_id']
    athlete_ids = [battery['athlete_id']]

    # Resolve beep_test course_id
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT course_id FROM courses WHERE course_type = 'beep_test' LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("Beep Test course not found — cannot create PACER session")
        beep_course_id = row['course_id']

    # Create session in sessions table (beep_test integrated approach)
    beep_config = {'distance_meters': 20, 'device_count': 2, 'start_level': start_level}
    session_id = db.create_session(
        team_id=team_id,
        course_id=beep_course_id,
        athlete_queue=athlete_ids,
        audio_voice='male',
        pattern_config=json.dumps(beep_config),
    )

    # Populate beep_test_results rows (one per athlete)
    for aid in athlete_ids:
        db.add_athlete_to_beep_test(session_id, aid)

    db.mark_course_deployed(session_id)

    # Create placeholder pyfp_event_result (raw_value=0; is_best=0 until import)
    event_result_id = db.create_pyfp_event_result(
        battery_id=battery_id,
        course_type='pyfp_pacer',
        raw_value=0.0,
        raw_unit='laps',
        attempt_number=1,
        is_best=0,
    )

    # Store the session_id on the result row
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE pyfp_event_result SET beep_test_session_id=? WHERE event_result_id=?",
            (session_id, event_result_id),
        )

    return {'session_id': session_id, 'redirect_url': f'/beep-test/monitor/{session_id}', 'created': True}


def import_pacer_result(battery_id: str) -> dict:
    """
    Read beep_test_results for the linked session, compute this athlete's
    total_laps, update pyfp_event_result, write performance_history.
    Returns summary dict.
    """
    db = DatabaseManager(_DB_PATH)

    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        raise ValueError(f"Battery {battery_id!r} not found")

    # Find the linked pyfp_event_result
    existing = db.get_pyfp_event_results_for_battery(battery_id)
    pacer_row = next((r for r in existing
                      if r['course_type'] == 'pyfp_pacer' and r['beep_test_session_id']), None)
    if not pacer_row:
        raise ValueError("No PACER session linked to this battery — run PACER first")

    session_id = pacer_row['beep_test_session_id']
    athlete_id = battery['athlete_id']

    # Read this athlete's result from beep_test_results
    beep_athletes = db.get_beep_test_athletes(session_id)
    athlete_bt = next((a for a in beep_athletes if a['athlete_id'] == athlete_id), None)
    if not athlete_bt:
        raise ValueError(f"Athlete not found in beep_test session {session_id!r}")

    level_completed = athlete_bt.get('level_completed') or 0
    shuttle_failed  = athlete_bt.get('shuttle_failed_on')

    # Read start_level from the session's stored pattern_config
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT pattern_config FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
    try:
        start_level = json.loads(row['pattern_config']).get('start_level', 1) if row else 1
    except Exception:
        start_level = 1

    total_laps = compute_total_laps(level_completed, shuttle_failed, start_level)

    # Update pyfp_event_result
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE pyfp_event_result SET raw_value=?, is_best=1 WHERE event_result_id=?",
            (float(total_laps), pacer_row['event_result_id']),
        )

    # Write performance_history
    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    course_id = pyfp_courses.get('pyfp_pacer', {}).get('course_id')
    db.write_pyfp_performance_history(
        athlete_id=athlete_id,
        metric_name='pyfp_pacer_laps',
        metric_value=float(total_laps),
        metric_unit='laps',
        course_id=course_id,
        notes=f"PYFP battery {battery_id}; level_completed={level_completed}; shuttle_failed_on={shuttle_failed}",
        is_better_higher=True,
    )

    return {
        'athlete_id':       athlete_id,
        'session_id':       session_id,
        'level_completed':  level_completed,
        'shuttle_failed_on': shuttle_failed,
        'total_laps':       total_laps,
        'status':           athlete_bt.get('status'),
    }
