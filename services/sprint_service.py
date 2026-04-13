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
        # Callbacks set by coach_interface to arm/disarm the finish-cone IR sensor
        self._arm_fn   = None   # called when beep fires (athlete leaves start)
        self._disarm_fn = None  # called when run ends

    def set_ir_callbacks(self, arm_fn, disarm_fn) -> None:
        """Register arm/disarm functions for the finish-cone IR sensor."""
        self._arm_fn   = arm_fn
        self._disarm_fn = disarm_fn

    def _get_finish_cone_ips(self, timing_mode: str, finish_cone_id: str) -> list:
        """Return list of IPs for finish-line cones (receiver + emitter) for LED commands."""
        ips = set()
        if timing_mode == 'ir_breakbeam':
            if finish_cone_id:
                ips.add(finish_cone_id)
            # Also include the emitter cone
            try:
                with self.registry.nodes_lock:
                    for ip, node in self.registry.nodes.items():
                        if (getattr(node, 'ir_role', None) == 'emitter' and
                                getattr(node, 'ir_sensor_type', None) == 'adafruit_breakbeam'):
                            ips.add(ip)
            except Exception:
                pass
        elif timing_mode == 'ir_single' and finish_cone_id:
            ips.add(finish_cone_id)
        return list(ips)

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

        # Set start cone to green — session is active
        self.registry.set_led(start_cone_id, 'solid_green')

        # Set finish-line cones to green if break-beam timing is configured
        timing_mode = course.get('timing_mode', 'manual')
        finish_cone_id = course.get('finish_cone_id')
        finish_cone_ips = self._get_finish_cone_ips(timing_mode, finish_cone_id)
        for ip in finish_cone_ips:
            self.registry.set_led(ip, 'solid_green')

        # Get first queued run
        next_run = self.db.get_next_queued_run(session_id)

        with self.state_lock:
            self.session_state = {
                'session_id': session_id,
                'start_cone_id': start_cone_id,
                'finish_cone_id': finish_cone_id,
                'finish_cone_ips': finish_cone_ips,
                'timing_mode': timing_mode,
                'countdown_interval': course.get('countdown_interval') or 5,
                'distance': course.get('distance'),
                'distance_unit': course.get('distance_unit', 'yards'),
                'status': 'active',
                'current_run_id': next_run['run_id'] if next_run else None,
                'beep_fired_at': None,
                'countdown_active': False,
                'countdown_remaining': 0,
                'ir_auto_stop_result': None,
            }

        self.registry.log(f"[SPRINT] Session started — cone {start_cone_id}, "
                          f"{course.get('distance')} {course.get('distance_unit')}", source='sprint')

        return {'success': True, 'next_run': next_run}

    def end_session(self, session_id: str, reason: str = 'completed') -> dict:
        """End session — mark DB, turn off cone."""
        with self.state_lock:
            start_cone_id = self.session_state.get('start_cone_id')
            finish_cone_ips = self.session_state.get('finish_cone_ips', [])
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}

        if reason == 'completed':
            self.db.complete_session(session_id)
        else:
            self.db.mark_session_incomplete(session_id, reason)

        if start_cone_id:
            self.registry.set_led(start_cone_id, 'solid_amber')

        # Set finish-line cones to amber
        for ip in finish_cone_ips:
            try:
                self.registry.set_led(ip, 'solid_amber')
            except Exception:
                pass

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
            self.session_state['ir_auto_stop_result'] = None  # clear any previous result

        self.registry.log(f"[SPRINT] Beep fired for run {run_id[:8]}", source='sprint')

        # Arm finish-cone IR sensor now that athlete is running
        if self._arm_fn:
            try:
                self._arm_fn()
            except Exception as e:
                self.registry.log(f"[SPRINT] IR arm failed: {e}", source='sprint')

    def stop(self, session_id: str, time_seconds: float) -> dict:
        """Coach taps STOP — record time, check PB, advance to next athlete."""
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            run_id = self.session_state.get('current_run_id')
            start_cone_id = self.session_state.get('start_cone_id')
            finish_cone_ips = self.session_state.get('finish_cone_ips', [])
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

        # Disarm finish-cone IR sensor — run is over
        if self._disarm_fn:
            try:
                self._disarm_fn()
            except Exception as e:
                self.registry.log(f"[SPRINT] IR disarm failed: {e}", source='sprint')

        # Cone stays green — session still active, waiting for next athlete
        self.registry.set_led(start_cone_id, 'solid_green')

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
            self.registry.set_led(start_cone_id, 'solid_amber')
            for ip in finish_cone_ips:
                try:
                    self.registry.set_led(ip, 'solid_amber')
                except Exception:
                    pass
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
    # IR auto-stop                                                         #
    # ------------------------------------------------------------------ #

    def auto_stop(self, session_id: str, from_device_id: str = None, trip_time: float = None) -> dict:
        """Called when finish-cone IR sensor is tripped — compute elapsed time server-side.

        trip_time: Unix timestamp captured on the field device at the exact moment of beam
                   break. Used in preference to time.time() to eliminate TCP transit latency
                   from the recorded split. Falls back to time.time() if not provided.
        """
        with self.state_lock:
            if self.session_state.get('session_id') != session_id:
                return {'success': False, 'error': 'Session not active'}
            beep_ts_str = self.session_state.get('beep_fired_at')
            if not beep_ts_str:
                return {'success': False, 'error': 'Timer not running — beep not yet fired'}
            finish_cone_id = self.session_state.get('finish_cone_id')
            # If a specific finish cone is designated, only accept trips from that device
            if from_device_id and finish_cone_id and from_device_id != finish_cone_id:
                return {'success': False, 'error': f'IR trip from {from_device_id}, expected {finish_cone_id}'}

        # Compute elapsed — prefer device timestamp to eliminate TCP transit latency
        try:
            from datetime import datetime as _dt
            beep_epoch = _dt.fromisoformat(beep_ts_str).timestamp()
            stop_epoch = trip_time if trip_time else time.time()
            time_seconds = round(stop_epoch - beep_epoch, 3)
        except Exception:
            return {'success': False, 'error': 'Could not parse beep timestamp'}

        result = self.stop(session_id, time_seconds)
        if result.get('success'):
            with self.state_lock:
                self.session_state['ir_auto_stop_result'] = {
                    'time_seconds': time_seconds,
                    'is_new_pb': result.get('is_new_pb', False),
                    'next_run': result.get('next_run'),
                    'session_complete': result.get('session_complete', False),
                }
        return result

    def get_active_session_id(self) -> str:
        """Return current session_id if one is active, else None."""
        with self.state_lock:
            if self.session_state.get('status') == 'active':
                return self.session_state.get('session_id')
        return None

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

        if self._disarm_fn:
            try:
                self._disarm_fn()
            except Exception:
                pass

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

        self.registry.set_led(start_cone_id, 'solid_green')

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
