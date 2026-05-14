"""
PYFP Shuttle Run Service — Phase 6.

Manages a single active 4×30ft shuttle. Two cones (endpoint_a, endpoint_b).
Touch sequence: B, A, B, A (4 legs). Total time = sum of leg segments.
"""
import sys
import threading
from datetime import datetime

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY

_DB_PATH = '/opt/data/field_trainer.db'
_svc = None
_lock = threading.Lock()


def get_pyfp_shuttle_service():
    global _svc
    if _svc is None:
        db = DatabaseManager(_DB_PATH)
        _svc = PyfpShuttleService(db, REGISTRY)
    return _svc


class PyfpShuttleService:
    def __init__(self, db: DatabaseManager, registry):
        self.db = db
        self.registry = registry
        self._state: dict = {}
        self._state_lock = threading.Lock()

    def is_active(self) -> bool:
        return bool(self._state.get('status') == 'active')

    def get_status(self) -> dict:
        with self._state_lock:
            return dict(self._state)

    def start(self, battery_id: str, endpoint_a: str, endpoint_b: str) -> dict:
        if self.is_active():
            return {'ok': False, 'error': 'A shuttle run is already in progress'}

        battery = self.db.get_pyfp_battery(battery_id)
        if not battery:
            return {'ok': False, 'error': 'Battery not found'}
        if endpoint_a == endpoint_b:
            return {'ok': False, 'error': 'endpoint_a and endpoint_b must be different cones'}

        athlete  = self.db.get_athlete(battery['athlete_id'])
        team_id  = athlete['team_id']
        courses  = {c['course_type']: c for c in self.db.get_pyfp_courses()}
        course_id = courses['pyfp_shuttle_run']['course_id']

        session_id = self.db.create_session(
            team_id=team_id, course_id=course_id,
            athlete_queue=[battery['athlete_id']],
        )
        self.db.start_session(session_id)
        run = self.db.get_next_queued_run(session_id)
        run_id = run['run_id']
        now = datetime.utcnow()
        self.db.start_run(run_id, timestamp=now)

        # Shuttle touch sequence: B, A, B, A (4 legs)
        self.db.create_pyfp_segments(
            run_id, [endpoint_b, endpoint_a, endpoint_b, endpoint_a]
        )

        pyfp_db = DatabaseManager(_DB_PATH)
        existing = [r for r in pyfp_db.get_pyfp_event_results_for_battery(battery_id)
                    if r['course_type'] == 'pyfp_shuttle_run']
        if existing:
            event_result_id = existing[0]['event_result_id']
        else:
            event_result_id = pyfp_db.create_pyfp_event_result(
                battery_id=battery_id, course_type='pyfp_shuttle_run',
                raw_value=0.0, raw_unit='seconds',
                attempt_number=1, is_best=0,
            )
        with pyfp_db.get_connection() as conn:
            conn.execute(
                """UPDATE pyfp_event_result
                   SET sessions_session_id=?, run_id=?, notes=?, raw_value=0.0, is_best=0
                   WHERE event_result_id=?""",
                (session_id, run_id, f'session_id={session_id}', event_result_id),
            )

        # Expected sequence: B first, then A, then B, then A
        expected = [endpoint_b, endpoint_a, endpoint_b, endpoint_a]

        with self._state_lock:
            self._state = {
                'status': 'active',
                'battery_id': battery_id,
                'session_id': session_id,
                'run_id': run_id,
                'event_result_id': event_result_id,
                'endpoint_a': endpoint_a,
                'endpoint_b': endpoint_b,
                'expected_sequence': expected,
                'touch_count': 0,
                'touch_times': [],
                'started_at': now.isoformat(),
            }

        for ep in (endpoint_a, endpoint_b):
            try:
                self.registry.set_led(ep, 'solid_green')
            except Exception:
                pass

        return {'ok': True, 'session_id': session_id, 'run_id': run_id,
                'event_result_id': event_result_id}

    def handle_touch(self, device_id: str, timestamp: datetime) -> None:
        with self._state_lock:
            if self._state.get('status') != 'active':
                return
            touch_count = self._state['touch_count']
            expected    = self._state['expected_sequence']

        if touch_count >= len(expected):
            return
        if device_id != expected[touch_count]:
            print(f"[PYFP SHUTTLE] Wrong cone: expected {expected[touch_count]}, got {device_id}")
            return

        with self._state_lock:
            try:
                self.db.record_touch(self._state['run_id'], device_id, timestamp)
            except Exception as e:
                print(f"[PYFP SHUTTLE] record_touch error: {e}")

            self._state['touch_count'] += 1
            self._state['touch_times'].append(timestamp.isoformat())
            new_count = self._state['touch_count']
            print(f"[PYFP SHUTTLE] Touch {new_count}/4 at {device_id}")

        if new_count >= 4:
            self._finish(timestamp)

    def abort(self) -> None:
        with self._state_lock:
            endpoints = [self._state.get('endpoint_a'), self._state.get('endpoint_b')]
            run_id = self._state.get('run_id')
            session_id = self._state.get('session_id')
            self._state = {}

        if run_id:
            try:
                self.db.complete_run(run_id, status='incomplete')
                self.db.mark_session_incomplete(session_id, 'aborted')
            except Exception:
                pass
        for ep in filter(None, endpoints):
            try:
                self.registry.set_led(ep, 'solid_amber')
            except Exception:
                pass

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

        self.db.complete_run(run_id, timestamp=end_time, total_time=total_seconds)
        self.db.complete_session(session_id)

        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE pyfp_event_result SET raw_value=?, is_best=1 WHERE event_result_id=?",
                (total_seconds, event_result_id),
            )

        battery   = self.db.get_pyfp_battery(battery_id)
        courses   = {c['course_type']: c for c in self.db.get_pyfp_courses()}
        course_id = courses.get('pyfp_shuttle_run', {}).get('course_id')
        self.db.write_pyfp_performance_history(
            athlete_id=battery['athlete_id'],
            metric_name='pyfp_shuttle_run_seconds',
            metric_value=total_seconds,
            metric_unit='seconds',
            course_id=course_id,
            notes=f"PYFP battery {battery_id}; 4x shuttle",
            is_better_higher=False,
        )

        for ep in (state['endpoint_a'], state['endpoint_b']):
            try:
                self.registry.set_led(ep, 'solid_amber')
            except Exception:
                pass

        print(f"[PYFP SHUTTLE] Run complete — {total_seconds}s total")
