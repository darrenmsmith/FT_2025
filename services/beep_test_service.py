#!/usr/bin/env python3
"""
Beep Test Service - Manages Léger Protocol beep test sessions
Completely isolated from SessionService (no impact on Warm-up/Simon Says)
"""

import sys
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.insert(0, '/opt')
from field_trainer.ft_registry import REGISTRY


# Léger Protocol Timing Tables
# Source: Original Léger & Lambert 1982 protocol

LEGER_20M_TABLE = [
    {'level': 1, 'speed_kmh': 8.5, 'shuttle_time_sec': 8.47, 'shuttles': 7, 'level_duration_sec': 59.29},
    {'level': 2, 'speed_kmh': 9.0, 'shuttle_time_sec': 8.00, 'shuttles': 8, 'level_duration_sec': 64.00},
    {'level': 3, 'speed_kmh': 9.5, 'shuttle_time_sec': 7.58, 'shuttles': 8, 'level_duration_sec': 60.63},
    {'level': 4, 'speed_kmh': 10.0, 'shuttle_time_sec': 7.20, 'shuttles': 8, 'level_duration_sec': 57.60},
    {'level': 5, 'speed_kmh': 10.5, 'shuttle_time_sec': 6.86, 'shuttles': 9, 'level_duration_sec': 61.71},
    {'level': 6, 'speed_kmh': 11.0, 'shuttle_time_sec': 6.55, 'shuttles': 9, 'level_duration_sec': 58.91},
    {'level': 7, 'speed_kmh': 11.5, 'shuttle_time_sec': 6.26, 'shuttles': 10, 'level_duration_sec': 62.61},
    {'level': 8, 'speed_kmh': 12.0, 'shuttle_time_sec': 6.00, 'shuttles': 10, 'level_duration_sec': 60.00},
    {'level': 9, 'speed_kmh': 12.5, 'shuttle_time_sec': 5.76, 'shuttles': 10, 'level_duration_sec': 57.60},
    {'level': 10, 'speed_kmh': 13.0, 'shuttle_time_sec': 5.54, 'shuttles': 11, 'level_duration_sec': 60.92},
    {'level': 11, 'speed_kmh': 13.5, 'shuttle_time_sec': 5.33, 'shuttles': 11, 'level_duration_sec': 58.67},
    {'level': 12, 'speed_kmh': 14.0, 'shuttle_time_sec': 5.14, 'shuttles': 12, 'level_duration_sec': 61.71},
    {'level': 13, 'speed_kmh': 14.5, 'shuttle_time_sec': 4.97, 'shuttles': 12, 'level_duration_sec': 59.63},
    {'level': 14, 'speed_kmh': 15.0, 'shuttle_time_sec': 4.80, 'shuttles': 13, 'level_duration_sec': 62.40},
    {'level': 15, 'speed_kmh': 15.5, 'shuttle_time_sec': 4.65, 'shuttles': 13, 'level_duration_sec': 60.39},
    {'level': 16, 'speed_kmh': 16.0, 'shuttle_time_sec': 4.50, 'shuttles': 13, 'level_duration_sec': 58.50},
    {'level': 17, 'speed_kmh': 16.5, 'shuttle_time_sec': 4.36, 'shuttles': 14, 'level_duration_sec': 61.09},
    {'level': 18, 'speed_kmh': 17.0, 'shuttle_time_sec': 4.24, 'shuttles': 14, 'level_duration_sec': 59.29},
    {'level': 19, 'speed_kmh': 17.5, 'shuttle_time_sec': 4.11, 'shuttles': 15, 'level_duration_sec': 61.71},
    {'level': 20, 'speed_kmh': 18.0, 'shuttle_time_sec': 4.00, 'shuttles': 15, 'level_duration_sec': 60.00},
    {'level': 21, 'speed_kmh': 18.5, 'shuttle_time_sec': 3.89, 'shuttles': 15, 'level_duration_sec': 58.38},
]

LEGER_15M_TABLE = [
    {'level': 1, 'speed_kmh': 8.5, 'shuttle_time_sec': 6.35, 'shuttles': 9, 'level_duration_sec': 57.18},
    {'level': 2, 'speed_kmh': 9.0, 'shuttle_time_sec': 6.00, 'shuttles': 10, 'level_duration_sec': 60.00},
    {'level': 3, 'speed_kmh': 9.5, 'shuttle_time_sec': 5.68, 'shuttles': 11, 'level_duration_sec': 62.53},
    {'level': 4, 'speed_kmh': 10.0, 'shuttle_time_sec': 5.40, 'shuttles': 11, 'level_duration_sec': 59.40},
    {'level': 5, 'speed_kmh': 10.5, 'shuttle_time_sec': 5.14, 'shuttles': 12, 'level_duration_sec': 61.71},
    {'level': 6, 'speed_kmh': 11.0, 'shuttle_time_sec': 4.91, 'shuttles': 12, 'level_duration_sec': 58.91},
    {'level': 7, 'speed_kmh': 11.5, 'shuttle_time_sec': 4.70, 'shuttles': 13, 'level_duration_sec': 61.04},
    {'level': 8, 'speed_kmh': 12.0, 'shuttle_time_sec': 4.50, 'shuttles': 13, 'level_duration_sec': 58.50},
    {'level': 9, 'speed_kmh': 12.5, 'shuttle_time_sec': 4.32, 'shuttles': 14, 'level_duration_sec': 60.48},
    {'level': 10, 'speed_kmh': 13.0, 'shuttle_time_sec': 4.15, 'shuttles': 14, 'level_duration_sec': 58.15},
    {'level': 11, 'speed_kmh': 13.5, 'shuttle_time_sec': 4.00, 'shuttles': 15, 'level_duration_sec': 60.00},
    {'level': 12, 'speed_kmh': 14.0, 'shuttle_time_sec': 3.86, 'shuttles': 16, 'level_duration_sec': 61.71},
    {'level': 13, 'speed_kmh': 14.5, 'shuttle_time_sec': 3.72, 'shuttles': 16, 'level_duration_sec': 59.59},
    {'level': 14, 'speed_kmh': 15.0, 'shuttle_time_sec': 3.60, 'shuttles': 17, 'level_duration_sec': 61.20},
    {'level': 15, 'speed_kmh': 15.5, 'shuttle_time_sec': 3.48, 'shuttles': 17, 'level_duration_sec': 59.23},
    {'level': 16, 'speed_kmh': 16.0, 'shuttle_time_sec': 3.38, 'shuttles': 18, 'level_duration_sec': 60.75},
    {'level': 17, 'speed_kmh': 16.5, 'shuttle_time_sec': 3.27, 'shuttles': 18, 'level_duration_sec': 58.91},
    {'level': 18, 'speed_kmh': 17.0, 'shuttle_time_sec': 3.18, 'shuttles': 19, 'level_duration_sec': 60.35},
    {'level': 19, 'speed_kmh': 17.5, 'shuttle_time_sec': 3.09, 'shuttles': 19, 'level_duration_sec': 58.63},
    {'level': 20, 'speed_kmh': 18.0, 'shuttle_time_sec': 3.00, 'shuttles': 20, 'level_duration_sec': 60.00},
    {'level': 21, 'speed_kmh': 18.5, 'shuttle_time_sec': 2.92, 'shuttles': 21, 'level_duration_sec': 61.24},
]


class BeepTestService:
    """
    Manages Beep Test sessions with Léger protocol timing.

    Features:
    - Background timing thread for synchronized beeps
    - Parallel audio to all devices
    - Chase green LED pattern
    - Toggle athlete active/failed status
    - Real-time database updates

    Isolation:
    - Completely separate from SessionService
    - No impact on Warm-up or Simon Says
    """

    def __init__(self, db, registry):
        self.db = db
        self.registry = registry

        # Active test state
        self.active_session_id: Optional[str] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.stop_timer_event = threading.Event()

        # Current test state
        self.current_level: int = 0
        self.current_shuttle: int = 0
        self.distance_meters: int = 20
        self.start_level: int = 1
        self.device_ids: List[str] = []
        self.current_phase: str = 'running'  # 'running' or 'recovery'

        # Timing table (selected based on distance)
        self.timing_table: List[Dict[str, Any]] = []

    def start_beep_test(self, session_id: str) -> Dict[str, Any]:
        """
        Start a beep test session

        Returns:
            {'success': bool, 'message': str, 'session_id': str}
        """
        try:
            print(f"\n{'='*80}")
            print(f"🎬 START BEEP TEST - Session ID: {session_id}")
            print(f"{'='*80}\n")

            # Get session details from REGULAR sessions table (integrated approach)
            session = self.db.get_session(session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}

            # Get beep test config from pattern_config field
            import json
            config = {}
            if session.get('pattern_config'):
                try:
                    config = json.loads(session['pattern_config'])
                except:
                    pass

            if not config:
                return {'success': False, 'error': 'No beep test configuration found'}

            distance_meters = config.get('distance_meters', 20)
            device_count = config.get('device_count', 4)
            start_level = config.get('start_level', 1)

            # Get athletes
            athletes = self.db.get_beep_test_athletes(session_id)
            if not athletes:
                return {'success': False, 'error': 'No athletes in session'}

            print(f"✅ Session loaded:")
            print(f"   Distance: {distance_meters}m")
            print(f"   Device count: {device_count}")
            print(f"   Start level: {start_level}")
            print(f"   Athletes: {len(athletes)}")
            for athlete in athletes:
                print(f"      - {athlete['athlete_name']}")

            # Set active session state
            self.active_session_id = session_id
            self.distance_meters = distance_meters
            self.start_level = start_level
            self.current_level = self.start_level
            self.current_shuttle = 1

            # Select timing table based on distance
            if self.distance_meters == 15:
                self.timing_table = LEGER_15M_TABLE
            else:
                self.timing_table = LEGER_20M_TABLE

            # Calculate device IDs based on device count (including Device 0)
            self.device_ids = ["192.168.99.100"] + [f"192.168.99.{100 + i}" for i in range(1, device_count + 1)]

            print(f"\n✅ Timing configuration:")
            print(f"   Using {self.distance_meters}m Léger table")
            print(f"   Starting at Level {self.start_level}")
            level_data = self.timing_table[self.start_level - 1]
            print(f"   Level {self.start_level}: {level_data['speed_kmh']} km/h, {level_data['shuttles']} shuttles, {level_data['shuttle_time_sec']:.2f}s per shuttle")

            # Validate devices are connected
            print(f"\n📡 Checking device connectivity...")
            connected_devices = []
            for device_id in self.device_ids:
                if device_id == "192.168.99.100":
                    # Device 0 is always "connected" (virtual)
                    connected_devices.append(device_id)
                    print(f"   ✅ {device_id} (Device 0 - Gateway) - Virtual")
                else:
                    # Check if device is in REGISTRY
                    node = self.registry.nodes.get(device_id)
                    if node and node._writer:
                        connected_devices.append(device_id)
                        print(f"   ✅ {device_id} - Connected")
                    else:
                        print(f"   ⚠️  {device_id} - NOT connected")

            if len(connected_devices) < 2:
                return {
                    'success': False,
                    'error': f'Only {len(connected_devices)} devices connected. Minimum 2 required.'
                }

            print(f"\n✅ Device check: {len(connected_devices)}/{device_count} devices ready")

            # Mark session as active in regular sessions table
            with self.db.get_connection() as conn:
                conn.execute('UPDATE sessions SET status = ? WHERE session_id = ?', ('active', session_id))
            print(f"✅ Session marked as active in database")

            # Set all devices to solid_green LED (active test in progress)
            print(f"\n💡 Setting solid_green LED on all devices...")
            for device_id in connected_devices:
                self.registry.set_led(device_id, 'solid_green')
                time.sleep(0.1)
            print(f"✅ All devices showing solid_green (test active)")

            # Start background timing thread (it will handle all beeps including the first one)
            self.stop_timer_event.clear()
            self.timer_thread = threading.Thread(
                target=self._beep_timer_thread,
                daemon=True
            )
            self.timer_thread.start()
            print(f"✅ Background timing thread started (will play initial beep)")

            print(f"\n{'='*80}")
            print(f"✅ BEEP TEST STARTED - Level {self.current_level}, Shuttle {self.current_shuttle}")
            print(f"{'='*80}\n")

            return {
                'success': True,
                'message': f'Beep test started at level {self.start_level}',
                'session_id': session_id,
                'current_level': self.current_level,
                'current_shuttle': self.current_shuttle
            }

        except Exception as e:
            print(f"❌ Error starting beep test: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _beep_timer_thread(self):
        """
        Background thread that manages beep timing.
        Runs continuously until stop_timer_event is set.
        """
        try:
            print(f"\n🔄 Beep timer thread started")

            while not self.stop_timer_event.is_set():
                # Get timing data for current level
                if self.current_level > len(self.timing_table):
                    # Reached max level
                    print(f"\n🎉 Reached max level {len(self.timing_table)} - completing test")
                    self._complete_test(final_level=len(self.timing_table))
                    break

                level_data = self.timing_table[self.current_level - 1]
                shuttle_time = level_data['shuttle_time_sec']
                total_shuttles = level_data['shuttles']

                # Check if we're starting a new level
                if self.current_shuttle == 1 and self.current_level > self.start_level:
                    # Play triple beep for new level
                    print(f"\n📢 NEW LEVEL {self.current_level}")
                    print(f"   Speed: {level_data['speed_kmh']} km/h")
                    print(f"   Shuttles: {total_shuttles}")
                    print(f"   Shuttle time: {shuttle_time:.2f}s")
                    self.registry.log(f"📢 Level {self.current_level} START - {level_data['speed_kmh']} km/h, {total_shuttles} shuttles")
                    self._play_beep(beep_count=3)

                # Single beep to start shuttle
                print(f"🔊 Level {self.current_level}, Shuttle {self.current_shuttle}/{total_shuttles}")
                self.registry.log(f"🏃 Shuttle {self.current_shuttle}/{total_shuttles} (Level {self.current_level})")
                self.current_phase = 'running'

                # Set all devices to GREEN for RUNNING phase
                print(f"   💡 LEDs → GREEN (running)")
                for device_id in self.device_ids:
                    self.registry.set_led(device_id, 'solid_green')

                self._play_beep(beep_count=1)

                # Wait for shuttle time (RUNNING phase)
                time.sleep(shuttle_time)

                # Double beep when shuttle is complete
                print(f"   ✅ Shuttle {self.current_shuttle} complete (double beep)")
                self._play_beep(beep_count=2)

                # Recovery time: Athletes walk back and prepare (equal to shuttle time)
                print(f"   ⏱  Recovery time: {shuttle_time:.2f}s (walk back)")
                self.current_phase = 'recovery'

                # Set all devices to AMBER for RECOVERY phase
                print(f"   💡 LEDs → AMBER (recovery)")
                for device_id in self.device_ids:
                    self.registry.set_led(device_id, 'solid_amber')

                time.sleep(shuttle_time)

                # Increment shuttle and reset phase for next shuttle
                self.current_shuttle += 1
                self.current_phase = 'running'  # Reset phase immediately for next shuttle

                # Check if level is complete
                if self.current_shuttle > total_shuttles:
                    # Level complete - recovery period before next level
                    print(f"\n✅ Level {self.current_level} COMPLETE")
                    print(f"   💡 Recovery period: 3 seconds (chase_green flashing)")
                    self.registry.log(f"✅ Level {self.current_level} COMPLETE - 3s recovery")

                    # Flash chase_green during recovery to signal level completion
                    for device_id in self.device_ids:
                        self.registry.set_led(device_id, 'chase_green')

                    # 3-second recovery delay
                    time.sleep(3.0)

                    # Restore solid_green for next level
                    print(f"   💡 Restoring solid_green for Level {self.current_level + 1}")
                    for device_id in self.device_ids:
                        self.registry.set_led(device_id, 'solid_green')

                    # Move to next level
                    self.current_level += 1
                    self.current_shuttle = 1

            print(f"✅ Beep timer thread stopped")

        except Exception as e:
            print(f"❌ Beep timer thread error: {e}")
            import traceback
            traceback.print_exc()

    def _play_beep(self, beep_count=1):
        """
        Play beep on Device 0 (gateway) only.

        Beep pattern:
        - 1 beep: Start of each shuttle (signal to run)
        - 2 beeps: End of each shuttle (confirmation they made it)
        - 3 beeps: New level starting

        Shuttle cycle within a level (e.g., Level 1 with 7 shuttles):
        1. Single beep → athlete runs shuttle 1
        2. (shuttle time passes - e.g., 8.47s)
        3. Double beep → shuttle 1 complete!
        4. Single beep → athlete runs shuttle 2
        5. (shuttle time passes)
        6. Double beep → shuttle 2 complete!
        7. (repeat for all shuttles in level)
        8. After final shuttle: 3s recovery with chase_green LEDs
        9. Triple beep → new level starts at faster speed

        Args:
            beep_count: Number of beeps (1, 2, or 3)
        """
        # Only play on Device 0 (gateway)
        device_id = "192.168.99.100"

        # Log to system log for web interface visibility
        beep_type = {1: "SHUTTLE START", 2: "SHUTTLE COMPLETE", 3: "NEW LEVEL"}
        self.registry.log(f"🔊 BEEP: {beep_count}x beeps ({beep_type.get(beep_count, 'UNKNOWN')})")

        for i in range(beep_count):
            if i > 0:
                time.sleep(0.6)  # Gap between beeps (increased to ensure beep finishes)

            try:
                if self.registry._audio:
                    self.registry._audio.play('default_beep')
                    print(f"🔊 Beep {i+1}/{beep_count} on Device 0")
                    # Log each individual beep to system log for debugging
                    self.registry.log(f"   ▶ Beep #{i+1} of {beep_count} played")
                    # Small delay to ensure beep is queued before next iteration
                    time.sleep(0.15)
            except Exception as e:
                print(f"⚠️  Failed to play beep: {e}")
                self.registry.log(f"   ⚠️ Beep #{i+1} FAILED: {e}")

    def toggle_athlete_status(self, session_id: str, athlete_id: str, current_status: str) -> Dict[str, Any]:
        """
        Toggle athlete between active and failed status.

        Args:
            session_id: Beep test session ID
            athlete_id: Athlete ID
            current_status: Current status ('active' or 'failed')

        Returns:
            {'success': bool, 'new_status': str, 'message': str}
        """
        try:
            if current_status == 'active':
                # Mark as failed - use current level if test is running, otherwise use level 1
                level_failed = max(1, self.current_level) if self.active_session_id == session_id else 1
                shuttle_failed_on = self.current_shuttle if self.active_session_id == session_id else 1

                self.db.mark_beep_test_athlete_failed(
                    session_id=session_id,
                    athlete_id=athlete_id,
                    level_failed=level_failed,
                    shuttle_failed_on=shuttle_failed_on
                )
                new_status = 'failed'
                message = f"Athlete marked as failed at Level {level_failed}, Shuttle {shuttle_failed_on}"
                print(f"❌ {message}")

                # Check if ALL athletes have now failed
                athletes = self.db.get_beep_test_athletes(session_id)
                active_count = sum(1 for a in athletes if a['status'] == 'active')

                if active_count == 0 and self.active_session_id == session_id:
                    print(f"\n🛑 ALL ATHLETES FAILED - Completing test")
                    self._complete_test(final_level=level_failed)
            else:
                # Reactivate
                self.db.mark_beep_test_athlete_active(
                    session_id=session_id,
                    athlete_id=athlete_id
                )
                new_status = 'active'
                message = "Athlete reactivated"
                print(f"✅ {message}")

            return {
                'success': True,
                'new_status': new_status,
                'message': message
            }

        except Exception as e:
            print(f"❌ Error toggling athlete status: {e}")
            return {'success': False, 'error': str(e)}

    def stop_test_early(self, session_id: str, reason: str = 'Stopped by coach') -> Dict[str, Any]:
        """
        Stop beep test early.

        Args:
            session_id: Session ID
            reason: Reason for stopping

        Returns:
            {'success': bool, 'message': str}
        """
        try:
            print(f"\n🛑 STOPPING TEST EARLY: {reason}")

            # Play 2 beeps to signal test end
            print(f"🔊 Playing end beeps (2 beeps)...")
            self._play_beep(beep_count=2)

            # Stop timer thread
            if self.timer_thread and self.timer_thread.is_alive():
                self.stop_timer_event.set()
                self.timer_thread.join(timeout=2.0)
                print(f"✅ Timer thread stopped")

            # Stop session in regular sessions table (use 'incomplete' status)
            with self.db.get_connection() as conn:
                conn.execute('UPDATE sessions SET status = ? WHERE session_id = ?', ('incomplete', session_id))
            print(f"✅ Session marked as incomplete in database")

            # Deactivate course and return to standby
            print(f"🏁 Deactivating course - returning to standby...")
            self.registry.course_status = "Deployed"  # Keep course deployed, just not active

            # Send stop command to all devices
            for device_id in self.device_ids:
                if device_id != "192.168.99.100":
                    self.registry.send_to_node(device_id, {
                        "cmd": "stop",
                        "action": None,
                        "course_status": "Deployed"
                    })

            # Clear assignments
            self.registry.assignments.clear()

            # Reset LEDs to amber (standby)
            print(f"💡 Resetting LEDs to amber...")
            for device_id in self.device_ids:
                self.registry.set_led(device_id, 'solid_amber')
                time.sleep(0.05)
            print(f"✅ LEDs reset to standby")

            # Clear active session
            self.active_session_id = None

            print(f"✅ Test stopped successfully\n")

            return {
                'success': True,
                'message': f'Test stopped: {reason}'
            }

        except Exception as e:
            print(f"❌ Error stopping test: {e}")
            return {'success': False, 'error': str(e)}

    def _complete_test(self, final_level: int):
        """
        Complete test when max level reached or all athletes failed.
        Internal method called by timer thread.
        """
        try:
            if not self.active_session_id:
                return

            print(f"\n🎉 COMPLETING TEST - Final Level: {final_level}")

            # Play 2 beeps to signal test end
            print(f"🔊 Playing end beeps (2 beeps)...")
            self._play_beep(beep_count=2)

            # Stop timer
            self.stop_timer_event.set()

            # Complete session in regular sessions table
            with self.db.get_connection() as conn:
                conn.execute('UPDATE sessions SET status = ? WHERE session_id = ?', ('completed', self.active_session_id))
            print(f"✅ Session marked as completed in database")

            # Deactivate course and return to standby
            print(f"🏁 Deactivating course - returning to standby...")
            self.registry.course_status = "Deployed"  # Keep course deployed, just not active

            # Send stop command to all devices
            for device_id in self.device_ids:
                if device_id != "192.168.99.100":
                    self.registry.send_to_node(device_id, {
                        "cmd": "stop",
                        "action": None,
                        "course_status": "Deployed"
                    })

            # Clear assignments
            self.registry.assignments.clear()

            # Reset LEDs to amber
            print(f"💡 Resetting LEDs to amber...")
            for device_id in self.device_ids:
                self.registry.set_led(device_id, 'solid_amber')
                time.sleep(0.05)
            print(f"✅ LEDs reset to standby")

            # Clear active session
            self.active_session_id = None

            print(f"✅ Test completed successfully\n")

        except Exception as e:
            print(f"❌ Error completing test: {e}")
            import traceback
            traceback.print_exc()

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current test state for UI updates.

        Returns:
            {
                'is_active': bool,
                'session_id': str,
                'current_level': int,
                'current_shuttle': int,
                'max_shuttles': int,
                'speed_kmh': float,
                'shuttle_time_sec': float
            }
        """
        if not self.active_session_id:
            return {'is_active': False}

        level_data = self.timing_table[self.current_level - 1] if self.current_level <= len(self.timing_table) else None

        return {
            'is_active': True,
            'session_id': self.active_session_id,
            'current_level': self.current_level,
            'current_shuttle': self.current_shuttle,
            'max_shuttles': level_data['shuttles'] if level_data else 0,
            'speed_kmh': level_data['speed_kmh'] if level_data else 0,
            'shuttle_time_sec': level_data['shuttle_time_sec'] if level_data else 0,
            'phase': self.current_phase  # 'running' or 'recovery'
        }
