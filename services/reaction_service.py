#!/usr/bin/env python3
"""
Reaction Sprint Service - Manages reaction time training sessions
Isolated from SessionService (no impact on Warm-up/Simon Says/Beep Test)
"""

import sys
import threading
import time
import random
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.insert(0, '/opt')
from field_trainer.ft_registry import REGISTRY


class ReactionService:
    """
    Manages Reaction Sprint sessions.

    Features:
    - Random cone selection (no repeats within run)
    - Per-touch split time tracking
    - Timeout monitoring (10s configurable)
    - Multi-athlete with countdown transitions
    - Chase animations for success/fail

    Isolation:
    - Completely separate from SessionService
    - No impact on Warm-up, Simon Says, or Beep Test
    """

    def __init__(self, db, registry):
        self.db = db
        self.registry = registry

        # Active session state
        # Structure: {
        #   'session_id': str,
        #   'course_id': int,
        #   'timeout_seconds': int,
        #   'current_run_id': str or None,
        #   'device_ids': [str],  # Client cones only (C1-C5)
        #   'runs': {
        #       run_id: {
        #           'run_id': str,
        #           'athlete_name': str,
        #           'available_pool': [str],  # Untouched cones
        #           'current_target': str or None,
        #           'target_activated_at': float or None,
        #           'splits': [float],  # List of split times
        #           'run_start_time': float,
        #           'status': 'running' or 'completed' or 'failed',
        #           'touches_completed': int,
        #           'timeout_thread': threading.Thread or None
        #       }
        #   }
        # }
        self.session_state: Dict[str, Any] = {}
        self.state_lock = threading.Lock()

    def start_session(self, session_id: str) -> Dict[str, Any]:
        """
        Initialize Reaction Sprint session and start first athlete.

        Flow:
        1. Load session and course from database
        2. Get device IDs from course_actions (C1-C5)
        3. Get timeout config from behavior_config
        4. Set all cones to AMBER
        5. Initialize session state
        6. Start first athlete

        Returns:
            {'success': bool, 'error': str (if failed)}
        """
        print(f"\n{'='*60}")
        print(f"REACTION SPRINT - START SESSION")
        print(f"Session ID: {session_id}")
        print(f"{'='*60}\n")

        try:
            # Load session data
            session = self.db.get_session(session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}

            course = self.db.get_course(session['course_id'])
            if not course:
                return {'success': False, 'error': 'Course not found'}

            # Verify course type
            if course.get('course_type') != 'reaction_sprint':
                return {'success': False, 'error': 'Invalid course type for Reaction Sprint'}

            # Get device IDs from course_actions (exclude D0)
            course_actions = self.db.get_course_actions(session['course_id'])
            device_ids = [
                action['device_id']
                for action in course_actions
                if action['device_id'] != '192.168.99.100'  # Exclude Device 0
            ]

            if len(device_ids) != 5:
                return {'success': False, 'error': f'Reaction Sprint requires exactly 5 client cones, found {len(device_ids)}'}

            print(f"✅ Device IDs: {device_ids}")

            # Get timeout config from behavior_config
            timeout_seconds = 10  # Default
            d0_action = next((a for a in course_actions if a['device_id'] == '192.168.99.100'), None)
            if d0_action and d0_action.get('behavior_config'):
                try:
                    config = json.loads(d0_action['behavior_config']) if isinstance(d0_action['behavior_config'], str) else d0_action['behavior_config']
                    timeout_seconds = config.get('timeout_seconds', 10)
                except:
                    pass

            print(f"⏱️  Timeout: {timeout_seconds}s")

            # Initialize session state
            with self.state_lock:
                self.session_state = {
                    'session_id': session_id,
                    'course_id': session['course_id'],
                    'timeout_seconds': timeout_seconds,
                    'current_run_id': None,
                    'device_ids': device_ids,
                    'runs': {},
                    'countdown': {'active': False}
                }

            # Cones are already GREEN from deploy - no need to change them here
            print(f"\n💡 Cones already GREEN from deploy")

            # Update session status to ACTIVE
            with self.db.get_connection() as conn:
                conn.execute('''
                    UPDATE sessions
                    SET status = 'active'
                    WHERE session_id = ?
                ''', (session_id,))
            print(f"✅ Session status → ACTIVE")

            # Start first athlete
            runs = self.db.get_session_runs(session_id)
            active_runs = [r for r in runs if r['status'] not in ['absent', 'completed', 'incomplete']]

            if not active_runs:
                return {'success': False, 'error': 'No active athletes in session'}

            first_run = active_runs[0]
            print(f"\n👤 Starting first athlete: {first_run['athlete_name']}")

            # Start athlete in background to allow API to return
            threading.Thread(
                target=self.start_athlete_run,
                args=(first_run['run_id'],),
                daemon=True
            ).start()

            return {'success': True}

        except Exception as e:
            print(f"❌ Error starting Reaction Sprint session: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def start_athlete_run(self, run_id: str):
        """
        Start an athlete's run with countdown and first cone selection.

        Flow:
        1. Display 5-second countdown modal
        2. D0 beeps "GO"
        3. All cones turn OFF
        4. Select first random cone → GREEN + BEEP
        5. Start timeout monitor thread
        """
        print(f"\n{'='*60}")
        print(f"ATHLETE RUN START")
        print(f"{'='*60}\n")

        try:
            # Get run data
            runs = self.db.get_session_runs(self.session_state['session_id'])
            run = next((r for r in runs if r['run_id'] == run_id), None)
            if not run:
                print(f"❌ Run not found: {run_id}")
                return

            print(f"👤 Athlete: {run['athlete_name']}")

            # Generate random sequence of all 5 cones upfront
            random_sequence = self.session_state['device_ids'].copy()
            random.shuffle(random_sequence)
            print(f"🎲 Random sequence: {random_sequence}")

            # Pre-create segments in database (for db.record_touch API)
            print(f"📝 Pre-creating segments...")
            with self.db.get_connection() as conn:
                for i, cone_id in enumerate(random_sequence):
                    conn.execute('''
                        INSERT INTO segments
                        (run_id, from_device, to_device, sequence, expected_min_time, expected_max_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        run_id,
                        '192.168.99.100',  # All touches from D0 (start)
                        cone_id,           # To this random cone
                        i,                 # Sequence 0-4
                        0.0,               # No min time for Reaction Sprint
                        self.session_state['timeout_seconds']  # Max time = timeout
                    ))
            print(f"✅ Created {len(random_sequence)} segments")

            # Initialize run state
            with self.state_lock:
                self.session_state['current_run_id'] = run_id
                self.session_state['runs'][run_id] = {
                    'run_id': run_id,
                    'athlete_name': run['athlete_name'],
                    'random_sequence': random_sequence,  # Pre-generated sequence
                    'current_index': 0,                   # Index into random_sequence
                    'current_target': None,
                    'target_activated_at': None,
                    'splits': [],
                    'run_start_time': None,
                    'status': 'running',
                    'touches_completed': 0,
                    'timeout_thread': None
                }

            # All cones turn OFF FIRST (before countdown starts)
            print(f"\n💡 All cones → OFF (before countdown)")
            print(f"   DEBUG: Device IDs: {self.session_state['device_ids']}")
            for device_id in self.session_state['device_ids']:
                print(f"   DEBUG: Setting {device_id} to OFF...")
                self.registry.set_led(device_id, 'off')
                print(f"   ⚫ {device_id} → OFF")

            # Wait for cones to physically turn OFF (network delay + LED update)
            print(f"   ⏳ Waiting for cones to turn OFF...")
            time.sleep(1.0)
            print(f"   ✅ Cones should be OFF now\n")

            # 5-second countdown modal (cones already OFF)
            print(f"⏱️  Starting countdown (5s)...")
            print(f"   DEBUG: Thread ID = {threading.current_thread().ident}")
            for remaining in range(5, 0, -1):
                print(f"   DEBUG: Countdown tick - {remaining}s remaining")
                with self.state_lock:
                    self.session_state['countdown'] = {
                        'active': True,
                        'athlete_name': run['athlete_name'],
                        'seconds_remaining': remaining
                    }
                    print(f"   DEBUG: Countdown state set: {self.session_state['countdown']}")
                print(f"   Next up: {run['athlete_name']} in {remaining}...")
                time.sleep(1.0)

            # Clear countdown
            with self.state_lock:
                self.session_state['countdown'] = {'active': False}
            print(f"   ✅ Countdown complete!")
            print(f"   DEBUG: Countdown cleared\n")

            # D0 beeps "GO"
            print(f"\n🔊 D0 beep GO")
            print(f"   DEBUG: Calling _play_d0_beep()")
            self._play_d0_beep()
            print(f"   DEBUG: D0 beep complete")
            time.sleep(0.2)

            # Record run start time
            with self.state_lock:
                self.session_state['runs'][run_id]['run_start_time'] = time.time()

            # Select first random cone
            self._activate_next_cone(run_id)

        except Exception as e:
            print(f"❌ Error starting athlete run: {e}")
            import traceback
            traceback.print_exc()

    def _activate_next_cone(self, run_id: str):
        """
        Activate the next cone in the pre-generated random sequence.

        Flow:
        1. Get next cone from random_sequence
        2. Turn cone GREEN + BEEP
        3. Record activation timestamp
        4. Start timeout monitor thread
        """
        with self.state_lock:
            run_state = self.session_state['runs'].get(run_id)
            if not run_state:
                print(f"❌ Run state not found: {run_id}")
                return

            # Get next cone from pre-generated sequence
            current_index = run_state['current_index']
            random_sequence = run_state['random_sequence']

            if current_index >= len(random_sequence):
                print(f"❌ No more cones in sequence (should not happen)")
                return

            target_cone = random_sequence[current_index]
            run_state['current_target'] = target_cone
            activation_time = time.time()
            run_state['target_activated_at'] = activation_time

            print(f"\n🎯 Target selected: {target_cone} (#{current_index + 1}/5)")
            print(f"   DEBUG: Activation time set to: {activation_time}")

        # Turn cone GREEN + BEEP
        print(f"💡 {target_cone} → GREEN + BEEP")
        self.registry.set_led(target_cone, 'solid_green')
        time.sleep(0.1)
        self._play_cone_beep(target_cone)

        # Start timeout monitor thread
        timeout_thread = threading.Thread(
            target=self._timeout_monitor,
            args=(run_id, target_cone),
            daemon=True
        )
        timeout_thread.start()

        with self.state_lock:
            run_state['timeout_thread'] = timeout_thread

    def _timeout_monitor(self, run_id: str, device_id: str):
        """
        Monitor for timeout on current target cone.
        Runs in background thread, checks every 0.5s.
        """
        timeout_seconds = self.session_state['timeout_seconds']

        while True:
            time.sleep(0.5)

            with self.state_lock:
                run_state = self.session_state['runs'].get(run_id)
                if not run_state:
                    return  # Run ended

                if run_state['current_target'] != device_id:
                    return  # Different target now (touch was detected)

                if run_state['status'] != 'running':
                    return  # Run ended

                elapsed = time.time() - run_state['target_activated_at']
                if elapsed >= timeout_seconds:
                    # TIMEOUT!
                    print(f"\n⏱️  TIMEOUT on {device_id} ({elapsed:.1f}s)")
                    break

        # Handle timeout
        self.handle_timeout(run_id, device_id)

    def handle_timeout(self, run_id: str, device_id: str):
        """
        Handle timeout event (athlete failed to touch within timeout).

        Flow:
        1. Mark run as failed
        2. All cones → CHASE RED
        3. D0 double beep
        4. All cones → AMBER
        5. Move to next athlete
        """
        print(f"\n{'='*60}")
        print(f"TIMEOUT - RUN FAILED")
        print(f"{'='*60}\n")

        with self.state_lock:
            run_state = self.session_state['runs'].get(run_id)
            if not run_state or run_state['status'] != 'running':
                return  # Already handled

            run_state['status'] = 'failed'
            athlete_name = run_state['athlete_name']

        print(f"👤 Athlete: {athlete_name}")
        print(f"🎯 Failed on: {device_id}")

        # All cones → CHASE RED
        print(f"\n💡 All cones → CHASE RED")
        for cone_id in self.session_state['device_ids']:
            self.registry.set_led(cone_id, 'chase_red')

        # D0 double beep
        print(f"🔊 D0 double beep (error)")
        self._play_d0_beep(count=2)

        # Wait for chase animation
        time.sleep(4.0)

        # All cones → AMBER
        print(f"\n💡 All cones → AMBER (standby)")
        for cone_id in self.session_state['device_ids']:
            self.registry.set_led(cone_id, 'solid_amber')

        # Update database
        with self.db.get_connection() as conn:
            conn.execute('''
                UPDATE runs
                SET status = 'incomplete',
                    completed_at = ?
                WHERE run_id = ?
            ''', (datetime.utcnow().isoformat(), run_id))

        print(f"✅ Run marked as FAILED in database")

        # Move to next athlete
        self.move_to_next_athlete()

    def handle_successful_touch(self, run_id: str, device_id: str, timestamp: datetime):
        """
        Handle successful touch after db.record_touch() was called by session_service.

        Flow:
        1. Update run state (increment index, clear target)
        2. Turn cone OFF
        3. If all 5 cones touched: Complete run (SUCCESS)
        4. Else: Activate next cone

        NOTE: Database recording is done by session_service via db.record_touch()
        """
        print(f"\n✅ SUCCESSFUL TOUCH")

        with self.state_lock:
            run_state = self.session_state['runs'].get(run_id)
            if not run_state:
                print(f"⚠️  Run state not found")
                return

            # Increment index to next cone
            run_state['current_index'] += 1
            run_state['touches_completed'] += 1

            # Clear current target (stops timeout thread)
            run_state['current_target'] = None

            athlete_name = run_state['athlete_name']
            touches = run_state['touches_completed']

        print(f"👤 Athlete: {athlete_name}")
        print(f"🎯 Cone: {device_id}")
        print(f"📊 Progress: {touches}/5 cones")

        # Turn cone OFF
        print(f"💡 {device_id} → OFF")
        self.registry.set_led(device_id, 'off')

        # Check if all 5 cones touched
        if touches >= 5:
            # SUCCESS - All 5 cones touched!
            self.complete_run(run_id, success=True)
        else:
            # Continue to next cone
            time.sleep(0.3)  # Brief pause before next cone
            self._activate_next_cone(run_id)

    def complete_run(self, run_id: str, success: bool):
        """
        Complete an athlete's run (success or fail).

        For SUCCESS:
        1. All cones → CHASE GREEN
        2. D0 TTS: "Done! Total time: X.X seconds"
        3. All cones → AMBER
        4. Move to next athlete
        """
        print(f"\n{'='*60}")
        print(f"RUN COMPLETE - {'SUCCESS' if success else 'FAILED'}")
        print(f"{'='*60}\n")

        with self.state_lock:
            run_state = self.session_state['runs'].get(run_id)
            if not run_state:
                return

            run_state['status'] = 'completed' if success else 'failed'
            athlete_name = run_state['athlete_name']
            total_time = time.time() - run_state['run_start_time']

        print(f"👤 Athlete: {athlete_name}")
        print(f"⏱️  Total time: {total_time:.2f}s")

        if success:
            # All cones → CHASE GREEN
            print(f"\n💡 All cones → CHASE GREEN (success)")
            for cone_id in self.session_state['device_ids']:
                self.registry.set_led(cone_id, 'chase_green')

            # D0 TTS announcement
            print(f"🔊 D0 TTS: Done! Total time: {total_time:.2f} seconds")
            tts_text = f"Done! Total time: {total_time:.1f} seconds"
            # TTS will be handled later if needed - for now just beep
            self._play_d0_beep()

            # Wait for animation
            time.sleep(4.0)

        # All cones → AMBER
        print(f"\n💡 All cones → AMBER (standby)")
        for cone_id in self.session_state['device_ids']:
            self.registry.set_led(cone_id, 'solid_amber')

        # Update database
        status = 'completed' if success else 'incomplete'
        with self.db.get_connection() as conn:
            conn.execute('''
                UPDATE runs
                SET status = ?,
                    total_time = ?,
                    completed_at = ?
                WHERE run_id = ?
            ''', (status, total_time, datetime.utcnow().isoformat(), run_id))

        print(f"✅ Run marked as {status.upper()} in database")

        # Move to next athlete
        self.move_to_next_athlete()

    def move_to_next_athlete(self):
        """
        Transition to the next athlete in the queue.

        Flow:
        1. Find next queued athlete
        2. If found: Start their run
        3. If not found: Complete session
        """
        print(f"\n{'='*60}")
        print(f"MOVE TO NEXT ATHLETE")
        print(f"{'='*60}\n")

        # Get all runs
        runs = self.db.get_session_runs(self.session_state['session_id'])

        # Find next queued athlete
        next_run = None
        for run in runs:
            if run['status'] == 'queued':
                next_run = run
                break

        if next_run:
            print(f"👤 Next athlete: {next_run['athlete_name']}")
            self.start_athlete_run(next_run['run_id'])
        else:
            print(f"✅ No more athletes - session complete")
            self.complete_session()

    def complete_session(self):
        """
        Mark session as completed and clean up.
        """
        print(f"\n{'='*60}")
        print(f"SESSION COMPLETE")
        print(f"{'='*60}\n")

        session_id = self.session_state['session_id']

        # Update session status
        with self.db.get_connection() as conn:
            conn.execute('''
                UPDATE sessions
                SET status = 'completed',
                    completed_at = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), session_id))

        print(f"✅ Session marked as COMPLETED in database")

        # Deactivate course completely
        print(f"🏁 Deactivating course...")
        self.registry.course_status = "Inactive"

        # Send stop commands to all devices
        for device_id in self.session_state['device_ids']:
            try:
                self.registry.send_to_node(device_id, {
                    "cmd": "stop",
                    "action": None,
                    "course_status": "Inactive"
                })
            except:
                pass

        # Clear assignments and course selection
        self.registry.assignments.clear()
        self.registry.selected_course = None
        if hasattr(self.registry, 'device_0_action'):
            self.registry.device_0_action = None

        # Set all devices to AMBER (standby)
        print(f"💡 Resetting LEDs to amber...")
        for device_id in self.session_state['device_ids']:
            try:
                self.registry.set_led(device_id, 'solid_amber')
            except:
                pass

        # Set D0 to AMBER
        if self.registry._server_led:
            try:
                from field_trainer.ft_led import LEDState
                self.registry._server_led.set_state(LEDState.SOLID_ORANGE)
            except:
                pass

        # Clear session state
        with self.state_lock:
            self.session_state.clear()

        print(f"🏁 Session complete!")

    def get_session_status(self) -> Dict[str, Any]:
        """
        Get current session status for API.

        Returns:
            {
                'active': bool,
                'session_id': str,
                'current_run_id': str or None,
                'current_athlete': str or None,
                'current_target': str or None,
                'touches_completed': int,
                'countdown': {'active': bool, 'athlete_name': str, 'seconds_remaining': int}
            }
        """
        with self.state_lock:
            if not self.session_state:
                print(f"   DEBUG: get_session_status() - NO session state")
                return {'active': False}

            current_run_id = self.session_state.get('current_run_id')
            current_athlete = None
            current_target = None
            touches_completed = 0

            if current_run_id:
                run_state = self.session_state['runs'].get(current_run_id)
                if run_state:
                    current_athlete = run_state['athlete_name']
                    current_target = run_state['current_target']
                    touches_completed = run_state['touches_completed']

            countdown_state = self.session_state.get('countdown', {'active': False})

            status = {
                'active': True,
                'session_id': self.session_state['session_id'],
                'current_run_id': current_run_id,
                'current_athlete': current_athlete,
                'current_target': current_target,
                'touches_completed': touches_completed,
                'countdown': countdown_state
            }

            print(f"   DEBUG: get_session_status() returning: countdown={countdown_state}, athlete={current_athlete}, target={current_target}")

            return status

    def _play_d0_beep(self, count=1):
        """Play beep(s) on Device 0 using server audio."""
        for i in range(count):
            if i > 0:
                time.sleep(0.3)
            try:
                if self.registry._audio:
                    self.registry._audio.play('default_beep')
                    print(f"   🔊 D0 beep {i+1}/{count}")
                    time.sleep(0.15)
            except Exception as e:
                print(f"   ⚠️ Failed to play D0 beep: {e}")

    def _play_cone_beep(self, device_id):
        """Play beep on a specific cone device."""
        try:
            # Send beep command to the device
            self.registry.send_to_node(device_id, {
                "cmd": "play_audio",
                "audio_clip": "default_beep"
            })
            print(f"   🔊 {device_id} beep sent")
        except Exception as e:
            print(f"   ⚠️ Failed to send beep to {device_id}: {e}")


# Singleton instance
reaction_service = None

def get_reaction_service():
    """Get or create the singleton ReactionService instance."""
    global reaction_service
    if reaction_service is None:
        from field_trainer.db_manager import DatabaseManager
        db = DatabaseManager('/opt/data/field_trainer.db')
        reaction_service = ReactionService(db, REGISTRY)
    return reaction_service
