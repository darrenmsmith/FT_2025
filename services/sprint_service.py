#!/usr/bin/env python3
"""
Sprint Service — manual sprint timing with client-side JS clock.
One start cone (LED + beep). Coach presses STOP at finish line.
"""

import threading
import time
from datetime import datetime

from field_trainer.db_manager import DatabaseManager
from field_trainer.ft_registry import REGISTRY


class SprintService:
    def __init__(self, db: DatabaseManager, registry):
        self.db = db
        self.registry = registry
        self.session_state = {}
        self.state_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Session lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def start_session(self, session_id: str) -> dict:
        """Called when coach presses GO on the monitor (session in 'setup' state)."""
        session = self.db.get_session(session_id)
        if not session:
            return {'success': False, 'error': 'Session not found'}

        course = self.db.get_course(session['course_id'])
        if not course:
            return {'success': False, 'error': 'Course not found'}

        # Get start cone — first device in course_actions (gateway for sprint)
        actions = self.db.get_course_actions(course['course_id'])
        start_cone_id = actions[0]['device_id'] if actions else None
        if not start_cone_id:
            return {'success': False, 'error': 'No start cone found in course actions'}

        # Mark session active in DB
        self.db.start_session(session_id)

        # Set start cone to amber (ready/waiting)
        self.registry.set_led(start_cone_id, 'solid_amber')

        # Get first queued run
        next_run = self.db.get_next_queued_run(session_id)

        with self.state_lock:
            self.session_state = {
                'session_id': session_id,
                'start_cone_id': start_cone_id,
                'countdown_interval': course.get('countdown_interval') or 5,
                'distance': course.get('distance'),
                'distance_unit': course.get('distance_unit', 'yards'),
                'status': 'active',
                'current_run_id': next_run['run_id'] if next_run else None,
                'beep_fired_at': None,
                'countdown_active': False,
                'countdown_remaining': 0,
            }

        self.registry.log(f"[SPRINT] Session started — cone {start_cone_id}, "
                          f"{course.get('distance')} {course.get('distance_unit')}", source='sprint')

        return {'success': True, 'next_run': next_run}

    def end_session(self, session_id: str, reason: str = 'completed') -> dict:
        """End session — mark DB, turn off cone."""
        with self.state_lock:
            start_cone_id = self.session_state.get('start_cone_id')
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}

        if reason == 'completed':
            self.db.complete_session(session_id)
        else:
            self.db.mark_session_incomplete(session_id, reason)

        if start_cone_id:
            self.registry.set_led(start_cone_id, 'off')

        self.registry.log(f"[SPRINT] Session ended ({reason})", source='sprint')

        with self.state_lock:
            self.session_state = {}

        return {'success': True}

    # ------------------------------------------------------------------ #
    # Per-athlete flow                                                     #
    # ------------------------------------------------------------------ #

    def go(self, session_id: str) -> dict:
        """Coach taps GO — start countdown for the current athlete."""
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            if self.session_state.get('countdown_active'):
                return {'success': False, 'error': 'Countdown already running'}
            if self.session_state.get('status') != 'active':
                return {'success': False, 'error': 'Session is not active'}

            # Find next queued run and mark it running
            next_run = self.db.get_next_queued_run(session_id)
            if not next_run:
                return {'success': False, 'error': 'No athletes in queue'}

            run_id = next_run['run_id']
            interval = self.session_state['countdown_interval']
            self.session_state['current_run_id'] = run_id
            self.session_state['countdown_active'] = True
            self.session_state['countdown_remaining'] = interval
            self.session_state['beep_fired_at'] = None

        self.db.start_run(run_id)

        self.registry.log(
            f"[SPRINT] GO — {next_run['athlete_name']}, {interval}s countdown",
            source='sprint'
        )

        # Run countdown in background
        t = threading.Thread(
            target=self._run_countdown,
            args=(session_id, run_id, interval),
            daemon=True
        )
        t.start()

        return {'success': True, 'run_id': run_id, 'athlete_name': next_run['athlete_name']}

    def _run_countdown(self, session_id: str, run_id: str, interval: int):
        """Background thread: count down, then beep + green LED + set beep_fired_at."""
        for remaining in range(interval, 0, -1):
            with self.state_lock:
                if self.session_state.get('session_id') != session_id:
                    return  # Session ended
                self.session_state['countdown_remaining'] = remaining
            time.sleep(1)

        # Fire the beep
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return
            start_cone_id = self.session_state.get('start_cone_id')

        beep_ts = datetime.now().isoformat(timespec='milliseconds')

        try:
            self.registry.play_audio(start_cone_id, 'default_beep')
            self.registry.set_led(start_cone_id, 'solid_green')
        except Exception as e:
            self.registry.log(f"[SPRINT] Warning: registry call failed in countdown: {e}", source='sprint')

        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return
            self.session_state['beep_fired_at'] = beep_ts
            self.session_state['countdown_active'] = False
            self.session_state['countdown_remaining'] = 0

        self.registry.log(f"[SPRINT] Beep fired for run {run_id[:8]}", source='sprint')

    def stop(self, session_id: str, time_seconds: float) -> dict:
        """Coach taps STOP — record time, check PB, advance to next athlete."""
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            run_id = self.session_state.get('current_run_id')
            start_cone_id = self.session_state.get('start_cone_id')
            distance = self.session_state.get('distance')
            distance_unit = self.session_state.get('distance_unit', 'yards')
            if not run_id:
                return {'success': False, 'error': 'No active run'}

        # Record the time
        self.db.complete_run(run_id, total_time=time_seconds)

        # Store distance on run so rankings stay correct if course is re-deployed at a different distance
        if distance:
            with self.db.get_connection() as conn:
                conn.execute(
                    'UPDATE runs SET sprint_distance = ?, sprint_distance_unit = ? WHERE run_id = ?',
                    (distance, distance_unit, run_id)
                )

        # Cone back to amber
        self.registry.set_led(start_cone_id, 'solid_amber')

        # Check personal best
        run = self.db.get_run(run_id)
        is_new_pb = False
        if distance and run:
            is_new_pb = self.db.check_and_update_sprint_pb(
                run['athlete_id'], distance, distance_unit, time_seconds, session_id
            )

        self.registry.log(
            f"[SPRINT] STOP — {run.get('athlete_name', run_id[:8]) if run else run_id[:8]} — {time_seconds:.2f}s"
            + (" ★ NEW PB!" if is_new_pb else ""),
            source='sprint'
        )

        # Advance to next athlete
        next_run = self.db.get_next_queued_run(session_id)

        with self.state_lock:
            self.session_state['current_run_id'] = next_run['run_id'] if next_run else None
            self.session_state['beep_fired_at'] = None

        # Auto-complete session if no more athletes
        if not next_run:
            self.registry.log("[SPRINT] All athletes done — completing session", source='sprint')
            self.db.complete_session(session_id)
            self.registry.set_led(start_cone_id, 'off')
            with self.state_lock:
                self.session_state['status'] = 'completed'

        return {
            'success': True,
            'time_seconds': time_seconds,
            'is_new_pb': is_new_pb,
            'next_run': next_run,
            'session_complete': next_run is None,
        }

    # ------------------------------------------------------------------ #
    # Pause / Resume                                                       #
    # ------------------------------------------------------------------ #

    def pause(self, session_id: str) -> dict:
        """Pause — abort current run (if any), move athlete to end of queue."""
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            run_id = self.session_state.get('current_run_id')
            start_cone_id = self.session_state.get('start_cone_id')

        aborted_athlete = None
        if run_id:
            run = self.db.get_run(run_id)
            if run and run['status'] == 'running':
                aborted_athlete = run.get('athlete_name')
                self.db.move_run_to_end_of_queue(session_id, run_id)
                self.registry.log(
                    f"[SPRINT] Pause — aborted {aborted_athlete}, moved to end of queue",
                    source='sprint'
                )

        self.registry.set_led(start_cone_id, 'blink_amber')

        with self.state_lock:
            self.session_state['status'] = 'paused'
            self.session_state['current_run_id'] = None
            self.session_state['countdown_active'] = False
            self.session_state['beep_fired_at'] = None

        return {'success': True, 'aborted_athlete': aborted_athlete}

    def resume(self, session_id: str) -> dict:
        """Resume — cone back to amber, find next queued athlete."""
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            start_cone_id = self.session_state.get('start_cone_id')

        self.registry.set_led(start_cone_id, 'solid_amber')

        next_run = self.db.get_next_queued_run(session_id)

        with self.state_lock:
            self.session_state['status'] = 'active'
            self.session_state['current_run_id'] = next_run['run_id'] if next_run else None

        self.registry.log("[SPRINT] Session resumed", source='sprint')
        return {'success': True, 'next_run': next_run}

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    def get_status(self, session_id: str) -> dict:
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'active': False}
            return dict(self.session_state)


# ------------------------------------------------------------------ #
# Singleton                                                            #
# ------------------------------------------------------------------ #

_sprint_service = None


def get_sprint_service() -> SprintService:
    global _sprint_service
    if _sprint_service is None:
        db = DatabaseManager('/opt/data/field_trainer.db')
        _sprint_service = SprintService(db, REGISTRY)
    return _sprint_service
