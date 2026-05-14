"""
PYFP Mile Run / Walk Service — Phase 6.

Manages a single active mile run. Coach assigns a start_finish cone;
athlete loops N times (default 4). Each cone touch = one completed lap.
On the Nth touch the run is finalised and pyfp_event_result is updated.

Uses the existing sessions/runs/segments DB primitives so per-lap timing
is stored in the standard segments table and `record_touch()` timing logic
is reused unchanged.
"""
import sys
import threading
from datetime import datetime, timezone

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY

_DB_PATH = '/opt/data/field_trainer.db'
_svc = None
_lock = threading.Lock()


def get_pyfp_mile_service():
    global _svc
    if _svc is None:
        db = DatabaseManager(_DB_PATH)
        _svc = PyfpMileService(db, REGISTRY)
    return _svc


class PyfpMileService:
    def __init__(self, db: DatabaseManager, registry):
        self.db = db
        self.registry = registry
        self._state: dict = {}
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def is_active(self) -> bool:
        return bool(self._state.get('status') == 'active')

    def get_status(self) -> dict:
        with self._state_lock:
            return dict(self._state)

    def start(self, battery_id: str, course_type: str,
              start_finish_cone_id: str, target_laps: int = 4,
              lap_marker_cone_id: str | None = None) -> dict:
        """
        Set up session/run/segments in DB, register touch handler, light cone.
        Returns {'ok': True, 'session_id': ..., 'run_id': ...}
        """
        if self.is_active():
            return {'ok': False, 'error': 'A mile run is already in progress'}

        battery = self.db.get_pyfp_battery(battery_id)
        if not battery:
            return {'ok': False, 'error': 'Battery not found'}

        athlete = self.db.get_athlete(battery['athlete_id'])
        team_id = athlete['team_id']

        # Resolve pyfp course_id
        courses = {c['course_type']: c for c in self.db.get_pyfp_courses()}
        if course_type not in courses:
            return {'ok': False, 'error': f'Course type {course_type!r} not found'}
        course_id = courses[course_type]['course_id']

        # Create session + run
        session_id = self.db.create_session(
            team_id=team_id,
            course_id=course_id,
            athlete_queue=[battery['athlete_id']],
        )
        self.db.start_session(session_id)
        run = self.db.get_next_queued_run(session_id)
        run_id = run['run_id']
        now = datetime.utcnow()
        self.db.start_run(run_id, timestamp=now)

        # Create lap segments (all pointing to start_finish cone)
        self.db.create_pyfp_segments(run_id, [start_finish_cone_id] * target_laps)

        # Create placeholder pyfp_event_result
        pyfp_db = DatabaseManager(_DB_PATH)
        # Reuse existing placeholder row (created by cone_assignment_save) if present
        existing = [r for r in pyfp_db.get_pyfp_event_results_for_battery(battery_id)
                    if r['course_type'] == course_type]
        if existing:
            event_result_id = existing[0]['event_result_id']
        else:
            event_result_id = pyfp_db.create_pyfp_event_result(
                battery_id=battery_id,
                course_type=course_type,
                raw_value=0.0,
                raw_unit='seconds',
                attempt_number=1,
                is_best=0,
            )
        with pyfp_db.get_connection() as conn:
            conn.execute(
                """UPDATE pyfp_event_result
                   SET sessions_session_id=?, run_id=?, notes=?, raw_value=0.0, is_best=0
                   WHERE event_result_id=?""",
                (session_id, run_id, f'session_id={session_id}', event_result_id),
            )

        with self._state_lock:
            self._state = {
                'status': 'active',
                'battery_id': battery_id,
                'course_type': course_type,
                'session_id': session_id,
                'run_id': run_id,
                'event_result_id': event_result_id,
                'start_finish_cone_id': start_finish_cone_id,
                'lap_marker_cone_id': lap_marker_cone_id,
                'target_laps': target_laps,
                'lap_count': 0,
                'lap_times': [],
                'started_at': now.isoformat(),
            }

        # Light the start_finish cone green
        try:
            self.registry.set_led(start_finish_cone_id, 'solid_green')
        except Exception:
            pass

        return {'ok': True, 'session_id': session_id, 'run_id': run_id,
                'event_result_id': event_result_id}

    def handle_touch(self, device_id: str, timestamp: datetime) -> None:
        with self._state_lock:
            if self._state.get('status') != 'active':
                return
            sf = self._state['start_finish_cone_id']
            lm = self._state.get('lap_marker_cone_id')

        if device_id == sf:
            self._on_lap_touch(timestamp)
        elif lm and device_id == lm:
            self._on_lap_marker_touch(timestamp)

    def abort(self) -> None:
        with self._state_lock:
            cone = self._state.get('start_finish_cone_id')
            run_id = self._state.get('run_id')
            session_id = self._state.get('session_id')
            self._state = {}

        if run_id:
            try:
                self.db.complete_run(run_id, status='incomplete')
                self.db.mark_session_incomplete(session_id, 'aborted')
            except Exception:
                pass
        if cone:
            try:
                self.registry.set_led(cone, 'solid_amber')
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _on_lap_touch(self, timestamp: datetime) -> None:
        with self._state_lock:
            segment_id = None
            try:
                segment_id = self.db.record_touch(
                    self._state['run_id'],
                    self._state['start_finish_cone_id'],
                    timestamp,
                )
            except Exception as e:
                print(f"[PYFP MILE] record_touch error: {e}")

            self._state['lap_count'] += 1
            lap_count = self._state['lap_count']
            target = self._state['target_laps']
            self._state['lap_times'].append(timestamp.isoformat())

            print(f"[PYFP MILE] Lap {lap_count}/{target} — segment_id={segment_id}")

        if lap_count >= target:
            self._finish(timestamp)

    def _on_lap_marker_touch(self, timestamp: datetime) -> None:
        with self._state_lock:
            lm = self._state.get('lap_marker_cone_id')
            if not lm:
                return
            print(f"[PYFP MILE] Lap-marker touch at {timestamp.isoformat()}")

    def _finish(self, end_time: datetime) -> None:
        with self._state_lock:
            state = dict(self._state)
            self._state['status'] = 'done'

        run_id          = state['run_id']
        session_id      = state['session_id']
        event_result_id = state['event_result_id']
        battery_id      = state['battery_id']
        started_at      = datetime.fromisoformat(state['started_at'])
        total_seconds   = round((end_time - started_at).total_seconds(), 2)

        # Finalise run in DB
        self.db.complete_run(run_id, timestamp=end_time, total_time=total_seconds)
        self.db.complete_session(session_id)

        # Update pyfp_event_result
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE pyfp_event_result SET raw_value=?, is_best=1 WHERE event_result_id=?",
                (total_seconds, event_result_id),
            )

        # Write performance_history
        battery   = self.db.get_pyfp_battery(battery_id)
        courses   = {c['course_type']: c for c in self.db.get_pyfp_courses()}
        course_id = courses.get(state['course_type'], {}).get('course_id')
        self.db.write_pyfp_performance_history(
            athlete_id=battery['athlete_id'],
            metric_name=f"pyfp_{state['course_type'].replace('pyfp_', '')}_seconds",
            metric_value=total_seconds,
            metric_unit='seconds',
            course_id=course_id,
            notes=f"PYFP battery {battery_id}; laps={state['target_laps']}",
            is_better_higher=False,
        )

        # Turn cone amber
        try:
            self.registry.set_led(state['start_finish_cone_id'], 'solid_amber')
        except Exception:
            pass

        print(f"[PYFP MILE] Run complete — {total_seconds}s for {state['target_laps']} laps")
