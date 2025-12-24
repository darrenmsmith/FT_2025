#!/usr/bin/env python3
"""
Session Service - Multi-athlete session management logic
Extracted from coach_interface.py during Phase 1 refactoring
"""

from datetime import datetime
from typing import Optional
import sys
import time

sys.path.insert(0, '/opt')
from field_trainer.ft_registry import REGISTRY


class SessionService:
    """Manages complex session logic including multi-athlete progression"""
    
    def __init__(self, db, registry, session_state):
        self.db = db
        self.registry = registry
        self.session_state = session_state
    
    def start_session(self, session_id: str) -> dict:
        """
        Start session and first athlete
        Returns: {'success': bool, 'message': str, 'current_run': dict}
        """
        import requests
        import time
        
        print(f"\n{'='*80}")
        print(f"🎬 START_SESSION CALLED - Session ID: {session_id}")
        print(f"{'='*80}\n")
        
        # Mark session as active
        print(f"Step 1: Marking session as active...")
        self.db.start_session(session_id)
        
        # Get first queued run
        first_run = self.db.get_next_queued_run(session_id)
        if not first_run:
            return {'success': False, 'error': 'No athletes in queue'}
        
        # Start first run
        start_time = datetime.utcnow()
        self.db.start_run(first_run['run_id'], start_time)

        # Small delay to ensure segments are committed before touches arrive
        time.sleep(0.1)

        # Get session and course (segments will be created after pattern generation)
        session = self.db.get_session(session_id)

        # Get course device sequence for multi-athlete tracking
        course = self.db.get_course(session['course_id'])
        device_sequence = [action['device_id'] for action in course['actions']
                          if action['device_id'] != '192.168.99.100']

        # Check if this is a pattern-based course (e.g., Simon Says)
        course_mode = course.get('mode', 'sequential')

        # Get ALL athletes/runs for this session
        all_runs = self.db.get_session_runs(session_id)
        total_athletes = len(all_runs)

        print(f"\n📊 Session has {total_athletes} athletes queued")

        # Pattern mode setup - generate unique pattern for EACH athlete
        colored_devices = []
        pattern_config = {}

        if course_mode == 'pattern':
            print(f"\n🎲 Pattern-based course detected - generating patterns for all athletes...")
            from field_trainer.pattern_generator import pattern_generator
            import json

            # Get colored devices from course actions
            for action in course['actions']:
                if action['sequence'] == 0:  # Skip start device
                    continue

                # Try to get color from behavior_config
                behavior_config = action.get('behavior_config')
                if behavior_config:
                    try:
                        config = json.loads(behavior_config) if isinstance(behavior_config, str) else behavior_config
                        color = config.get('color')
                        if color:
                            colored_devices.append({
                                'device_id': action['device_id'],
                                'device_name': action['device_name'],
                                'color': color
                            })
                    except (json.JSONDecodeError, TypeError):
                        pass

            if colored_devices:
                # Check for session-level pattern_config override first (for "Continue to n" feature)
                session_pattern_config_str = session.get('pattern_config')

                if session_pattern_config_str:
                    # Session has pattern override (from "Continue to n")
                    print(f"✓ Using session-level pattern config override")
                    try:
                        session_override = json.loads(session_pattern_config_str) if isinstance(session_pattern_config_str, str) else session_pattern_config_str
                        pattern_length = session_override.get('pattern_length', 4)
                        allow_repeats = session_override.get('allow_repeats', True)
                        error_feedback_duration = session_override.get('error_feedback_duration', 4.0)
                        debounce_ms = session_override.get('debounce_ms', 1000)
                    except (json.JSONDecodeError, TypeError):
                        # Fall back to course config
                        print(f"⚠️  Failed to parse session pattern_config, using course defaults")
                        session_pattern_config_str = None

                if not session_pattern_config_str:
                    # Get pattern config from first action (start device)
                    first_action = course['actions'][0]
                    pattern_config_str = first_action.get('behavior_config')
                    pattern_length = 4  # Default
                    allow_repeats = True  # Default
                    error_feedback_duration = 4.0  # Default
                    debounce_ms = 1000  # Default debounce window in milliseconds (1 second)

                    if pattern_config_str:
                        try:
                            pattern_config = json.loads(pattern_config_str) if isinstance(pattern_config_str, str) else pattern_config_str
                            pattern_length = pattern_config.get('pattern_length', 4)
                            allow_repeats = pattern_config.get('allow_repeats', True)
                            error_feedback_duration = pattern_config.get('error_feedback_duration', 4.0)
                            debounce_ms = pattern_config.get('debounce_ms', 1000)
                        except (json.JSONDecodeError, TypeError):
                            pass

                # Validate pattern_length is in valid range (3-8)
                if pattern_length < 3:
                    pattern_length = 3
                elif pattern_length > 8:
                    pattern_length = 8

                # Store colored devices and config for all athletes
                pattern_config = {
                    'colored_devices': colored_devices,
                    'pattern_length': pattern_length,
                    'allow_repeats': allow_repeats,
                    'error_feedback_duration': error_feedback_duration,
                    'debounce_ms': debounce_ms
                }

                print(f"✓ Pattern config: length={pattern_length}, allow_repeats={allow_repeats}, error_feedback_duration={error_feedback_duration}s, debounce={debounce_ms}ms")
            else:
                print(f"⚠️  No colored devices found for pattern generation, using sequential mode")
                course_mode = 'sequential'

        # Initialize multi-athlete state with ALL athletes
        self.session_state['session_id'] = session_id
        self.session_state['device_sequence'] = device_sequence
        self.session_state['total_queued'] = total_athletes
        self.session_state['course_mode'] = course_mode
        self.session_state['pattern_config'] = pattern_config  # Store config for all athletes
        self.session_state['active_runs'] = {}

        # PATTERN MODE: Load ALL athletes upfront with unique patterns
        # SEQUENTIAL MODE: Load ONLY first athlete (others triggered by D1 touch)
        previous_pattern = None

        # Determine which athletes to load at session start
        if course_mode == 'pattern':
            # Pattern mode: Load all athletes upfront
            athletes_to_load = all_runs
        else:
            # Sequential mode: Load only first athlete
            athletes_to_load = [all_runs[0]]

        for idx, run in enumerate(athletes_to_load):
            # Find actual index in all_runs for proper is_active setting
            actual_idx = all_runs.index(run)

            # Start this run in the database
            if actual_idx == 0:
                # First run already started above
                run_start_time = start_time
            else:
                # Start other runs (pattern mode only - they'll be in 'waiting' state until their turn)
                run_start_time = datetime.utcnow()
                self.db.start_run(run['run_id'], run_start_time)

            run_info = {
                'athlete_name': run['athlete_name'],
                'athlete_id': run['athlete_id'],
                'started_at': run_start_time.isoformat(),
                'last_device': None,
                'sequence_position': -1,  # Haven't touched any device yet
                'is_active': (actual_idx == 0),  # Only first athlete is active initially
                'visual_feedback': {
                    'correct_devices': [],  # Devices turned green
                    'failed_device': None   # Device turned red (if failed)
                }
            }

            # Generate unique pattern for this athlete (pattern mode only)
            if course_mode == 'pattern' and colored_devices:
                from field_trainer.pattern_generator import pattern_generator

                # Generate pattern, avoiding consecutive duplicates
                max_attempts = 100
                for attempt in range(max_attempts):
                    pattern = pattern_generator.generate_simon_says_pattern(
                        colored_devices,
                        sequence_length=pattern_config['pattern_length'],
                        allow_repeats=pattern_config['allow_repeats']
                    )

                    # Check if this pattern is same as previous athlete's pattern
                    if previous_pattern is None or not self._patterns_match(pattern, previous_pattern):
                        break  # Found unique pattern

                # Even if we couldn't find unique, use the last generated one (rare edge case)
                pattern_description = pattern_generator.get_pattern_description(pattern)
                pattern_device_ids = pattern_generator.get_pattern_device_ids(pattern)

                # Store pattern in run_info (per-athlete, not session-wide)
                run_info['pattern_data'] = {
                    'pattern': pattern,
                    'description': pattern_description,
                    'device_ids': pattern_device_ids,
                    'colored_devices': colored_devices
                }

                # Log pattern to System Log for coach
                self.registry.log(f"📋 {run['athlete_name']}: {pattern_description}", source="session")
                print(f"✓ Pattern for {run['athlete_name']}: {pattern_description}")

                previous_pattern = pattern

                # Override device_sequence for pattern mode
                if idx == 0:
                    device_sequence = pattern_device_ids

            # Create segments for this run (after pattern generation for pattern mode)
            if course_mode == 'pattern' and 'pattern_data' in run_info:
                # Pattern mode: Create segments based on actual pattern sequence
                self.db.create_pattern_segments_for_run(run['run_id'], run_info['pattern_data']['device_ids'])
            else:
                # Sequential mode: Create segments based on course devices
                self.db.create_segments_for_run(run['run_id'], session['course_id'])

            # Add to active_runs
            self.session_state['active_runs'][run['run_id']] = run_info

        print(f"\n✅ Multi-athlete state initialized:")
        print(f"   Mode: {course_mode.upper()}")
        print(f"   Total athletes: {total_athletes}")
        print(f"   Device sequence: {device_sequence}")
        print(f"   First athlete (active): {first_run['athlete_name']}")
        if total_athletes > 1:
            if course_mode == 'pattern':
                print(f"   Remaining athletes (loaded, waiting): {', '.join([r['athlete_name'] for r in all_runs[1:]])}")
            else:
                print(f"   Remaining athletes (queued, will start on D1 trigger): {', '.join([r['athlete_name'] for r in all_runs[1:]])}")

        # Set audio voice
        audio_voice = session.get('audio_voice', 'male')

        # Course already activated during session creation
        print(f"\nStep 5: Course already active, proceeding with audio...")

        # Wait for activation to propagate
        time.sleep(0.5)

        # Play first audio on Device 0 via API (SKIP in pattern mode - pattern display handles audio)
        if course_mode != 'pattern':
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

        # If pattern mode, display the pattern using LEDs for first athlete
        if course_mode == 'pattern':
            # Get first athlete's pattern
            first_athlete_pattern = self.session_state['active_runs'][first_run['run_id']].get('pattern_data')
            if first_athlete_pattern:
                print(f"\n💡 Displaying pattern sequence with LEDs...")
                self._display_pattern_sequence(first_athlete_pattern)

                # PHASE 3: Start completion timer after pattern display
                timer_start = datetime.utcnow()
                self.session_state['active_runs'][first_run['run_id']]['timer_start'] = timer_start
                # Store timer_start in database for cumulative timing
                self.db.update_run_timer_start(first_run['run_id'], timer_start)
                print(f"⏱️  Timer started for {first_run['athlete_name']}")
            else:
                print(f"⚠️  No pattern data for first athlete")

        return {
            'success': True,
            'message': f"{first_run['athlete_name']} started",
            'current_run': first_run
        }
    
    def stop_session(self, session_id: str, reason: str = 'Stopped by coach') -> dict:
        """
        Stop session and deactivate course
        Returns: {'success': bool, 'message': str}
        """
        print(f"\n{'='*80}")
        print(f"🛑 STOP_SESSION CALLED - Session ID: {session_id}")
        print(f"   Reason: {reason}")
        print(f"{'='*80}\n")

        # Get session to verify it exists
        session = self.db.get_session(session_id)
        if not session:
            return {'success': False, 'error': 'Session not found'}

        # Mark all active runs as incomplete
        with self.db.get_connection() as conn:
            for run in session.get('runs', []):
                if run['status'] == 'running':
                    conn.execute('''
                        UPDATE runs
                        SET status = 'incomplete',
                            completed_at = ?
                        WHERE run_id = ?
                    ''', (datetime.utcnow().isoformat(), run['run_id']))

        # Mark session as incomplete
        with self.db.get_connection() as conn:
            conn.execute('''
                UPDATE sessions
                SET status = 'incomplete',
                    completed_at = ?,
                    notes = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), reason, session_id))

        # Return course to standby (deployed but not active)
        print("Returning to standby...")
        self.registry.course_status = "Deployed"  # Keep course deployed, just not active

        # Clear assignments and send stop command to all devices
        for node_id in list(self.registry.assignments.keys()):
            if node_id != "192.168.99.100":
                self.registry.send_to_node(node_id, {
                    "cmd": "stop",
                    "action": None,
                    "course_status": "Deployed"
                })

        self.registry.assignments.clear()

        # Set all devices to AMBER (standby)
        course = self.db.get_course(session['course_id'])
        for action in course['actions']:
            device_id = action['device_id']
            if device_id != "192.168.99.100":
                self.registry.set_led(device_id, pattern='solid_amber')

        # Set Device 0 LED to amber (standby)
        if self.registry._server_led:
            from field_trainer.ft_led import LEDState
            self.registry._server_led.set_state(LEDState.SOLID_ORANGE)

        # Clear active session state
        self.session_state.clear()

        self.registry.log(f"Session {session_id} stopped: {reason}")
        print(f"✅ Session stopped successfully")
        print("="*80 + "\n")

        return {
            'success': True,
            'message': 'Session stopped and devices deactivated'
        }

    def _patterns_match(self, pattern1: list, pattern2: list) -> bool:
        """
        Check if two patterns are identical (helper for avoiding consecutive duplicates)

        Args:
            pattern1: First pattern (list of device dicts)
            pattern2: Second pattern (list of device dicts)

        Returns:
            True if patterns are identical, False otherwise
        """
        if len(pattern1) != len(pattern2):
            return False

        for i in range(len(pattern1)):
            if pattern1[i]['device_id'] != pattern2[i]['device_id']:
                return False

        return True

    def _move_to_next_athlete(self) -> bool:
        """
        Move to the next athlete in Simon Says pattern mode.

        Returns:
            True if there's a next athlete, False if all athletes are done
        """
        print(f"\n{'='*60}")
        print(f"⏭️  MOVING TO NEXT ATHLETE")
        print(f"{'='*60}")

        # Find current active athlete and next waiting athlete
        current_run_id = None
        next_run_id = None

        athlete_list = list(self.session_state['active_runs'].items())

        for idx, (run_id, run_info) in enumerate(athlete_list):
            if run_info.get('is_active', False):
                current_run_id = run_id
                # Mark current as inactive
                run_info['is_active'] = False
                print(f"✓ Current athlete: {run_info['athlete_name']} (finished)")

                # Find next athlete
                if idx + 1 < len(athlete_list):
                    next_run_id = athlete_list[idx + 1][0]
                    next_run_info = athlete_list[idx + 1][1]
                    next_run_info['is_active'] = True
                    print(f"✓ Next athlete: {next_run_info['athlete_name']}")
                else:
                    print(f"✓ No more athletes - session complete!")
                break

        if not next_run_id:
            # No more athletes
            return False

        # Get next athlete's pattern
        next_run_info = self.session_state['active_runs'][next_run_id]
        pattern_data = next_run_info.get('pattern_data')

        if not pattern_data:
            print(f"⚠️  No pattern data for next athlete!")
            return False

        # Restore all devices to assigned colors (2 second pause between athletes)
        print(f"\n🔄 Restoring assigned colors between athletes...")
        colored_devices = pattern_data['colored_devices']
        for dev in colored_devices:
            color = dev.get('color', 'red')
            pattern = f"solid_{color.lower()}"
            # Send command immediately to device (don't just set registry state)
            self.registry.set_led(dev['device_id'], pattern)
            print(f"   {dev['device_id']} → {color.upper()} ({pattern})")
            time.sleep(0.2)  # Brief delay between commands

        time.sleep(2.0)  # Pause to show assigned colors between athletes

        # Display pattern for next athlete
        print(f"\n💡 Displaying pattern for {next_run_info['athlete_name']}...")
        print(f"   Pattern: {pattern_data['description']}")
        self._display_pattern_sequence(pattern_data)

        # PHASE 3: Start completion timer after pattern display
        timer_start = datetime.utcnow()
        next_run_info['timer_start'] = timer_start
        # Store timer_start in database for cumulative timing
        self.db.update_run_timer_start(next_run_info['run_id'], timer_start)
        print(f"⏱️  Timer started for {next_run_info['athlete_name']}")

        print(f"{'='*60}\n")
        return True

    def _complete_session(self, session_id: str):
        """
        Mark session as completed when all athletes are done.
        Deactivates course and resets devices.
        """
        # Mark session as completed
        with self.db.get_connection() as conn:
            conn.execute('''
                UPDATE sessions
                SET status = 'completed',
                    completed_at = ?
                WHERE session_id = ?
            ''', (datetime.utcnow().isoformat(), session_id))

        # Get course info for device reset
        session = self.db.get_session(session_id)
        course = self.db.get_course(session['course_id'])

        # Return course to standby (deployed but not active)
        print("🏁 Session complete - returning to standby...")
        self.registry.course_status = "Deployed"  # Keep course deployed, just not active

        # Clear assignments and send stop command to all devices
        for node_id in list(self.registry.assignments.keys()):
            if node_id != "192.168.99.100":
                self.registry.send_to_node(node_id, {
                    "cmd": "stop",
                    "action": None,
                    "course_status": "Deployed"
                })

        self.registry.assignments.clear()

        # Set all devices to AMBER (standby)
        for action in course['actions']:
            device_id = action['device_id']
            if device_id != "192.168.99.100":
                self.registry.set_led(device_id, pattern='solid_amber')

        # Set Device 0 LED to amber (standby)
        if self.registry._server_led:
            from field_trainer.ft_led import LEDState
            self.registry._server_led.set_state(LEDState.SOLID_ORANGE)

        # Clear active session state
        self.session_state.clear()

        self.registry.log(f"Session {session_id} completed - all athletes done")
        print(f"✅ Session completed successfully\n")

    def handle_touch_event(self, device_id: str, timestamp: datetime):
        """
        Called by REGISTRY when a device touch is detected.
        Supports multiple simultaneous athletes on course.
        """
        import requests
        import time
        
        session_id = self.session_state.get('session_id')
        
        if not session_id:
            self.registry.log(f"Touch on {device_id} but no active session", level="warning")
            return
        
        print(f"\n{'='*80}")
        print(f"👆 MULTI-ATHLETE TOUCH HANDLER")
        print(f"   Device: {device_id}")
        print(f"   Active athletes: {len(self.session_state.get('active_runs', {}))}")
        print(f"{'='*80}")

        # Log touch to System Log with device name and athlete context
        device_name = "Start (D0)" if device_id == "192.168.99.100" else f"Cone {int(device_id.split('.')[-1]) - 100}"

        # Find which athlete is currently active (pattern mode) or might have touched (sequential mode)
        course_mode = self.session_state.get('course_mode', 'sequential')
        active_athlete_name = None

        if course_mode == 'pattern':
            # In pattern mode, find the currently active athlete
            for run_id, run_info in self.session_state.get('active_runs', {}).items():
                if run_info.get('is_active', False):
                    active_athlete_name = run_info.get('athlete_name')
                    break

        # Log with athlete context if available
        if active_athlete_name:
            self.registry.log(f"👆 Touch: {device_name} - {active_athlete_name} at {timestamp.strftime('%H:%M:%S.%f')[:-3]}", source="session")
        else:
            self.registry.log(f"👆 Touch: {device_name} at {timestamp.strftime('%H:%M:%S.%f')[:-3]}", source="session")

        # SPECIAL HANDLING: D0 touch in pattern mode = pattern completion/submit
        if device_id == "192.168.99.100" and course_mode == 'pattern':
            print(f"🟢 D0 TOUCHED - Pattern completion attempt")

            # Find which athlete completed the pattern (most recent active)
            if not self.session_state.get('active_runs'):
                print(f"   ❌ No active runs")
                print(f"{'='*80}\n")
                return

            # Get the currently active athlete
            run_id = None
            run_info = None
            for rid, rinfo in self.session_state['active_runs'].items():
                if rinfo.get('is_active', False):
                    run_id = rid
                    run_info = rinfo
                    break

            if not run_id or not run_info:
                print(f"   ❌ No active athlete found")
                print(f"{'='*80}\n")
                return

            pattern_data = run_info.get('pattern_data')

            if not pattern_data:
                print(f"   ❌ No pattern data")
                print(f"{'='*80}\n")
                return

            # Check if all pattern touches are complete BEFORE beeping
            current_position = run_info.get('sequence_position', -1)
            pattern_length = len(pattern_data['device_ids'])

            print(f"   Athlete: {run_info['athlete_name']}")
            print(f"   Pattern progress: {current_position + 1}/{pattern_length}")
            print(f"   DEBUG: current_position={current_position}, pattern_length={pattern_length}")
            print(f"   DEBUG: pattern_data['device_ids']={pattern_data.get('device_ids', [])}")
            print(f"   DEBUG: Check: {current_position + 1} < {pattern_length} = {current_position + 1 < pattern_length}")

            if current_position + 1 < pattern_length:
                print(f"   ❌ Pattern incomplete! Still need to touch:")
                remaining = pattern_length - (current_position + 1)
                for i in range(current_position + 1, pattern_length):
                    color = pattern_data['pattern'][i]['color']
                    device = pattern_data['device_ids'][i]
                    print(f"      Step {i+1}: {color.upper()} ({device})")
                print(f"   ⚠️  D0 touched too early - no beep (pattern not complete)")
                print(f"{'='*80}\n")
                return

            # Pattern complete! Play beep to confirm submission
            try:
                self.registry.play_audio("192.168.99.100", "default_beep")
                print(f"   🔊 Beep played on D0 - submission confirmed")
            except Exception as e:
                print(f"   ⚠️  Beep failed: {e}")

            # Show chase green and finish run
            print(f"   ✅ PATTERN COMPLETE! All {pattern_length} touches done")
            print(f"   🎉 Chase GREEN for success...")

            try:
                # Block heartbeat LED commands during success feedback
                self.registry.error_feedback_active = True
                print(f"   🚫 Success feedback active - heartbeat LED commands blocked")

                # OPTION C: Send chase_green ONLY - clients will auto-terminate and return to amber
                colored_devices = pattern_data.get('colored_devices', pattern_data['pattern'])
                print(f"   💚 Sending chase_green to {len(colored_devices)} devices...")
                for dev in colored_devices:
                    self.registry.set_led(dev['device_id'], 'chase_green')
                    time.sleep(0.3)  # Delay between commands to prevent TCP congestion

                # Wait for client-side auto-termination (3s chase + 0.5s buffer)
                time.sleep(3.5)
                print(f"   ✅ Chase complete (clients auto-returned to amber)")

                # BUG FIX #2: Restore assigned colors after success feedback
                print(f"   🧹 Restoring assigned colors after success...")
                for dev in colored_devices:
                    node = self.registry.nodes.get(dev['device_id'])
                    if node:
                        # Restore to assigned color (or amber if session ending)
                        color = dev.get('color', 'red')
                        node.led_pattern = f"solid_{color.lower()}"
                        print(f"      {dev['device_id']} → restored to {color.upper()}")

                # Re-enable heartbeat LED commands
                self.registry.error_feedback_active = False
                print(f"   ✅ Heartbeat re-enabled - devices restored to assigned colors")
            except Exception as e:
                print(f"   ⚠️  LED feedback failed: {e}")
                # BUG FIX #2: Restore assigned colors even on error
                try:
                    colored_devices = pattern_data.get('colored_devices', pattern_data['pattern'])
                    for dev in colored_devices:
                        node = self.registry.nodes.get(dev['device_id'])
                        if node:
                            # Restore to assigned color
                            color = dev.get('color', 'red')
                            node.led_pattern = f"solid_{color.lower()}"
                except:
                    pass
                # Re-enable heartbeat even on error
                self.registry.error_feedback_active = False

            # PHASE 3: Calculate completion time
            completion_time = None
            timer_start = run_info.get('timer_start')
            if timer_start:
                completion_time_seconds = (datetime.utcnow() - timer_start).total_seconds()
                completion_time = completion_time_seconds
                print(f"   ⏱️  Completion time: {completion_time_seconds:.2f} seconds")
                self.registry.log(f"✅ {run_info['athlete_name']} completed in {completion_time_seconds:.2f} seconds", source="session")
            else:
                print(f"   ⚠️  No timer_start found for completion time calculation")

            # Complete the run in database
            print(f"   🏁 Completing run in database...")
            try:
                self.db.complete_run(run_id, datetime.utcnow(), total_time=completion_time)
                print(f"   ✅ Run completed for {run_info['athlete_name']}")

                # Move to next athlete or complete session
                # NOTE: _move_to_next_athlete() will handle marking current as inactive
                has_next_athlete = self._move_to_next_athlete()

                if not has_next_athlete:
                    # No more athletes - complete the session
                    session_id = self.session_state.get('session_id')
                    if session_id:
                        print(f"   🎉 All athletes complete - completing session {session_id[:8]}...")
                        self._complete_session(session_id)
                    else:
                        print(f"   ⚠️  No session_id in session_state!")
            except Exception as e:
                print(f"   ❌ Failed to complete run: {e}")
                import traceback
                traceback.print_exc()

            print(f"{'='*80}\n")
            return  # D0 touch handled, exit

        # PATTERN MODE VALIDATION
        course_mode = self.session_state.get('course_mode', 'sequential')
        if course_mode == 'pattern':
            # Pattern mode: Find currently active athlete
            run_id = None
            run_info = None
            for rid, rinfo in self.session_state['active_runs'].items():
                if rinfo.get('is_active', False):
                    run_id = rid
                    run_info = rinfo
                    break

            if not run_id or not run_info:
                print(f"⚠️  No active pattern run found")
                print(f"{'='*80}\n")
                return

            # Block touches during error feedback (athlete is still marked active, but feedback is playing)
            if self.registry.error_feedback_active:
                print(f"🚫 ERROR FEEDBACK ACTIVE - Touch ignored (feedback animation playing)")
                print(f"{'='*80}\n")
                return

            # GLOBAL DEBOUNCE: Prevent ANY touch within 500ms of the last touch (any device)
            # This prevents accidental double-touches, spurious touches, or rapid unintentional contacts
            global_debounce_key = f"{run_id}_last_touch_time"
            global_debounce_window = 0.5  # 500ms global debounce

            if global_debounce_key in self.session_state:
                last_global_touch = self.session_state[global_debounce_key]
                time_since_last_global = (timestamp - last_global_touch).total_seconds()

                if time_since_last_global < global_debounce_window:
                    device_name = f"Cone {int(device_id.split('.')[-1]) - 100}"
                    print(f"🔇 GLOBAL DEBOUNCE: Ignoring touch on {device_name} ({time_since_last_global*1000:.0f}ms since last ANY touch, threshold={global_debounce_window*1000:.0f}ms)")
                    print(f"{'='*80}\n")
                    return

            # DEBOUNCE: Check for rapid repeated touches on same device (hardware bounce)
            # This prevents accidental double-taps from causing false failures
            # BUT still allows intentional repeated touches if they match the pattern
            debounce_key = f"{run_id}_debounce"
            debounce_step_key = f"{run_id}_debounce_step"  # Track which step the debounce is for

            if debounce_key not in self.session_state:
                self.session_state[debounce_key] = {}  # Track {device_id: last_touch_time}
            if debounce_step_key not in self.session_state:
                self.session_state[debounce_step_key] = {}  # Track {device_id: last_step_position}

            debounce_tracking = self.session_state[debounce_key]
            debounce_step_tracking = self.session_state[debounce_step_key]
            debounce_window = self.session_state.get('pattern_config', {}).get('debounce_ms', 1000) / 1000.0  # Convert to seconds

            # Get current expected position to check if this is a different pattern step
            current_position = run_info.get('sequence_position', -1)
            expected_position = current_position + 1

            if device_id in debounce_tracking:
                last_touch_time = debounce_tracking[device_id]
                last_step_position = debounce_step_tracking.get(device_id, -1)
                time_since_last = (timestamp - last_touch_time).total_seconds()

                # Only debounce if it's the SAME pattern step (rapid double-tap)
                # Don't debounce if it's a different step (intentional repeated cone in pattern)
                if time_since_last < debounce_window and last_step_position == expected_position:
                    # This is a bounce on the same step - ignore it
                    print(f"🔇 DEBOUNCE: Ignoring rapid repeat on {device_id} ({time_since_last*1000:.0f}ms since last touch, threshold={debounce_window*1000:.0f}ms, same step={expected_position})")
                    device_name = f"Cone {int(device_id.split('.')[-1]) - 100}"
                    print(f"{'='*80}\n")
                    return
                elif time_since_last < debounce_window and last_step_position != expected_position:
                    # Rapid repeat but different pattern step - this is intentional, allow it
                    print(f"✓ Rapid repeat on {device_id} ({time_since_last*1000:.0f}ms) but different pattern step (was {last_step_position}, now {expected_position}) - ALLOWING")

            device_sequence = self.session_state['device_sequence']
            pattern_data = run_info.get('pattern_data')
            if pattern_data:
                # Validate touch matches expected pattern step
                current_position = run_info.get('sequence_position', -1)
                expected_position = current_position + 1

                if expected_position >= len(pattern_data['device_ids']):
                    print(f"⚠️  Pattern already complete - ignoring extra touch")
                    print(f"{'='*80}\n")
                    return

                expected_device = pattern_data['device_ids'][expected_position]
                expected_color = pattern_data['pattern'][expected_position]['color']

                # Validate: is this the expected device?
                if device_id != expected_device:
                    print(f"❌ WRONG DEVICE!")
                    print(f"   Expected: {expected_color.upper()} ({expected_device})")
                    print(f"   Got: {device_id}")
                    print(f"   Pattern: {pattern_data['description']}")

                    # Log error to System Log with detailed device info
                    touched_device_name = f"Cone {int(device_id.split('.')[-1]) - 100}"
                    expected_device_name = f"Cone {int(expected_device.split('.')[-1]) - 100}"
                    self.registry.log(f"❌ Pattern Error: {run_info['athlete_name']} touched {touched_device_name} but expected {expected_color.upper()} ({expected_device_name}) - Step {expected_position + 1}/{len(pattern_data['device_ids'])}", level="warning", source="session")

                    # Set error_feedback_active to block further touches during error animation
                    # This also blocks heartbeat LED commands during error feedback
                    self.registry.error_feedback_active = True
                    print(f"   🚫 Error feedback active - touches blocked, heartbeat LED commands blocked")

                    # NOTE: We do NOT mark athlete as inactive here - _move_to_next_athlete() will do that
                    # Marking inactive early would prevent _move_to_next_athlete() from finding current athlete

                    # Play error feedback: chase RED on all devices, beep on D0, then return to assigned colors
                    try:
                        # Get error feedback duration from config (default 4.0s)
                        pattern_config = self.session_state.get('pattern_config', {})
                        error_duration = pattern_config.get('error_feedback_duration', 4.0)

                        # OPTION C: Send chase_red ONLY - clients will auto-terminate and return to amber
                        colored_devices = pattern_data.get('colored_devices', pattern_data['pattern'])
                        print(f"   ❤️  Sending chase_red to {len(colored_devices)} devices...")
                        for dev in colored_devices:
                            self.registry.set_led(dev['device_id'], 'chase_red')
                            time.sleep(0.3)  # Delay between commands to prevent TCP congestion

                        # Wait for all chases to start before beeping
                        time.sleep(0.5)

                        # Beep on D0 for error feedback
                        self.registry.play_audio("192.168.99.100", "default_beep")

                        # Wait for error feedback duration
                        print(f"   ⏱️  Error feedback duration: {error_duration}s")
                        time.sleep(error_duration)
                        print(f"   ✅ Error feedback complete")

                        # BUG FIX #2: Restore assigned colors after error feedback
                        print(f"   🧹 Restoring assigned colors after error...")
                        for dev in colored_devices:
                            node = self.registry.nodes.get(dev['device_id'])
                            if node:
                                # Restore to assigned color
                                color = dev.get('color', 'red')
                                node.led_pattern = f"solid_{color.lower()}"
                                print(f"      {dev['device_id']} → restored to {color.upper()}")

                        # Re-enable heartbeat LED commands
                        self.registry.error_feedback_active = False
                        print(f"   ✅ Heartbeat re-enabled - devices restored to assigned colors")
                    except Exception as e:
                        print(f"⚠️  Error feedback failed: {e}")
                        # BUG FIX #2: Restore assigned colors even on error
                        try:
                            colored_devices = pattern_data.get('colored_devices', pattern_data['pattern'])
                            for dev in colored_devices:
                                node = self.registry.nodes.get(dev['device_id'])
                                if node:
                                    # Restore to assigned color
                                    color = dev.get('color', 'red')
                                    node.led_pattern = f"solid_{color.lower()}"
                        except:
                            pass
                        # Make sure to re-enable heartbeat even on error
                        self.registry.error_feedback_active = False

                    # PHASE 3: Calculate completion time (even for failures)
                    completion_time = None
                    timer_start = run_info.get('timer_start')
                    if timer_start:
                        completion_time_seconds = (datetime.utcnow() - timer_start).total_seconds()
                        completion_time = completion_time_seconds
                        print(f"   ⏱️  Time until failure: {completion_time_seconds:.2f} seconds")
                        self.registry.log(f"❌ {run_info['athlete_name']} failed after {completion_time_seconds:.2f} seconds", source="session")
                    else:
                        print(f"   ⚠️  No timer_start found for completion time calculation")

                    # Mark run as failed in database
                    try:
                        self.db.complete_run(run_id, datetime.utcnow(), total_time=completion_time, status='incomplete')
                        print(f"   ❌ Run failed for {run_info['athlete_name']} - pattern error")

                        # Move to next athlete or complete session
                        # NOTE: _move_to_next_athlete() will handle marking current as inactive
                        has_next_athlete = self._move_to_next_athlete()

                        if not has_next_athlete:
                            # No more athletes - complete the session
                            session_id = self.session_state.get('session_id')
                            if session_id:
                                print(f"   🎉 All athletes complete - completing session {session_id[:8]}...")
                                self._complete_session(session_id)
                    except Exception as e:
                        print(f"   ❌ Failed to complete run: {e}")
                        import traceback
                        traceback.print_exc()

                    print(f"{'='*80}\n")
                    return
                else:
                    print(f"✓ Correct! {expected_color.upper()} (Step {expected_position + 1}/{len(pattern_data['device_ids'])})")

                    # Log to System Log for web UI visibility with device name
                    device_name = f"Cone {int(device_id.split('.')[-1]) - 100}"
                    self.registry.log(f"✓ Correct: {run_info['athlete_name']} touched {expected_color.upper()} ({device_name}) - Step {expected_position + 1}/{len(pattern_data['device_ids'])}", source="session")

                    # CRITICAL: Update sequence_position immediately after validation
                    # This prevents issues if database recording is slow/fails
                    print(f"   DEBUG: Before update - sequence_position = {run_info.get('sequence_position', -1)}")
                    run_info['sequence_position'] = expected_position
                    print(f"   DEBUG: After update - sequence_position = {run_info['sequence_position']}")
                    print(f"   Updated position: {expected_position + 1}/{len(pattern_data['device_ids'])}")

                    # Update debounce timestamp AND step position for this device (successful touch)
                    debounce_tracking[device_id] = timestamp
                    debounce_step_tracking[device_id] = expected_position

                    # Update global debounce timestamp (last touch across ALL devices)
                    global_debounce_key = f"{run_id}_last_touch_time"
                    self.session_state[global_debounce_key] = timestamp

                    # Check if all pattern touches are done
                    if expected_position + 1 >= len(pattern_data['device_ids']):
                        print(f"\n✅ All pattern touches complete! Touch D0 (Start) to submit.")
                        self.registry.log(f"✅ {run_info['athlete_name']} completed pattern! Touch D0 to submit", source="session")

            # Record the touch
            segment_id = self.db.record_touch(run_id, device_id, timestamp)

            if not segment_id:
                self.registry.log(f"Touch on {device_id} but no matching segment for run {run_id}",
                                level="warning")
                print(f"⚠️  No segment found for this touch")
                print(f"{'='*80}\n")
                return

            print(f"{'='*80}\n")
            return  # Pattern mode handled, exit

        # SEQUENTIAL MODE
        # Find which athlete should receive this touch
        run_id = self.find_athlete_for_touch(device_id, timestamp)

        if not run_id:
            self.registry.log(f"Touch on {device_id} - no valid athlete found", level="warning")
            print(f"❌ Could not attribute touch to any athlete")
            print(f"{'='*80}\n")
            return

        run_info = self.session_state['active_runs'][run_id]
        device_sequence = self.session_state['device_sequence']

        # Record the touch
        segment_id = self.db.record_touch(run_id, device_id, timestamp)

        if not segment_id:
            self.registry.log(f"Touch on {device_id} but no matching segment for run {run_id}",
                            level="warning")
            print(f"⚠️  No segment found for this touch")
            print(f"{'='*80}\n")
            return

        # Update athlete's progression
        new_position = device_sequence.index(device_id)

        run_info['last_device'] = device_id
        run_info['sequence_position'] = new_position

        print(f"✅ Touch recorded: {run_info['athlete_name']} → Device {device_id}")
        print(f"   Segment ID: {segment_id}")
        print(f"   Sequence position: {new_position + 1}/{len(device_sequence)}")

        # Log to System Log for web UI visibility
        self.registry.log(f"Touch: {run_info['athlete_name']} → {device_id} (pos {new_position + 1}/{len(device_sequence)})", source="session")
        
        # Check for alerts
        alert_raised, alert_type = self.db.check_segment_alerts(segment_id)
        if alert_raised:
            self.registry.log(f"ALERT: Segment {segment_id} - {alert_type}", level="warning")
            print(f"⚠️  ALERT: {alert_type}")
        
        # Get session and course info
        session = self.db.get_session(session_id)
        course = self.db.get_course(session['course_id'])
        
        # Find the action for this device
        action = next((a for a in course['actions'] if a['device_id'] == device_id), None)
        
        if not action:
            print(f"⚠️  No action found for device {device_id}")
            print(f"{'='*80}\n")
            return
        
        # Check if this action triggers next athlete
        if action.get('triggers_next_athlete'):
            print(f"🔔 Device triggers next athlete")
            next_run = self.db.get_next_queued_run(session_id)
            if next_run:
                # CRITICAL: Double-check status to prevent race conditions
                current_status = self.db.get_run(next_run['run_id'])['status']
                if current_status != 'queued':
                    print(f"ℹ️  {next_run['athlete_name']} already started (status: {current_status})")
                    return
                
                # Check if already started (in-memory check)
                if next_run['run_id'] in self.session_state['active_runs']:
                    print(f"ℹ️  {next_run['athlete_name']} already in active_runs")
                    return
        
                # Check if we're at max capacity (5 active athletes)
                elif len(self.session_state['active_runs']) >= 5:
                    print(f"⏸️  At max capacity (5 athletes) - next athlete will wait")

                else:
                    # Start next athlete
                    start_time = datetime.utcnow()
                    
                    print(f"   🎬 Starting run for {next_run['athlete_name']}...")
                    try:
                        self.db.start_run(next_run['run_id'], start_time)
                        print(f"      ✅ Run started successfully")
                    except Exception as e:
                        print(f"      ❌ start_run FAILED: {e}")
                        import traceback
                        traceback.print_exc()
                        print(f"{'='*80}\n")
                        return
                    
                    # Add to active runs IMMEDIATELY to prevent duplicate triggers
                    self.session_state['active_runs'][next_run['run_id']] = {
                        'athlete_name': next_run['athlete_name'],
                        'athlete_id': next_run['athlete_id'],
                        'started_at': start_time.isoformat(),
                        'last_device': None,
                        'sequence_position': -1
                    }
                    print(f"      ✅ Added to active_runs")
                    
                    # Create segments for next athlete
                    print(f"   📋 Creating segments for {next_run['athlete_name']}...")
                    try:
                        self.db.create_segments_for_run(next_run['run_id'], session['course_id'])
                        
                        # Verify segments were created
                        segments = self.db.get_run_segments(next_run['run_id'])
                        print(f"      ✅ Created {len(segments)} segments")
                        
                        # Small delay to ensure segments are committed
                        time.sleep(0.1)
                    except Exception as e:
                        print(f"      ❌ Segment creation failed: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    print(f"🏃 Next athlete started: {next_run['athlete_name']}")
                    print(f"   Active: {len(self.session_state['active_runs'])}/{self.session_state['total_queued']}")

                    # Play audio on Device 0 for next athlete
                    first_action = course['actions'][0]
                    print(f"🔊 Playing Device 0 audio for next athlete via API")
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
                        print(f"   ❌ Audio failed: {e}")
                    
                    self.registry.log(f"Next athlete started: {next_run['athlete_name']}")
        
        # Check if athlete completed course
        if new_position == len(device_sequence) - 1:
            print(f"🏁 {run_info['athlete_name']} completed the course!")

            # Calculate total time from segments
            segments = self.db.get_run_segments(run_id)
            total_time = sum(seg.get('actual_time', 0) or 0 for seg in segments if seg.get('touch_detected'))

            # Mark run as completed
            completion_time = datetime.utcnow()
            self.db.complete_run(run_id, completion_time, total_time)

            print(f"   Total time: {total_time:.2f}s")

            # Remove from active runs
            del self.session_state['active_runs'][run_id]

            print(f"   Remaining active: {len(self.session_state['active_runs'])}")
            self.registry.log(f"Athlete completed: {run_info['athlete_name']}")

            # Check if all athletes are done
            next_queued = self.db.get_next_queued_run(session_id)
            active_count = len(self.session_state['active_runs'])

            if not next_queued and active_count == 0:
                print(f"🎉 All athletes completed! Auto-completing session...")
                self._complete_session(session_id)

        print(f"{'='*80}\n")
    
    def find_athlete_for_touch(self, device_id: str, timestamp: datetime) -> Optional[str]:
        """
        Determine which active athlete should be attributed a touch on device_id.
        Priority 1: Athletes at correct sequential position (gap == 1)
        Priority 2: Athletes who skipped devices (gap > 1)
        Ignores: Same device twice (gap == 0) or backwards (gap < 0)
        """
        if not self.session_state.get('active_runs'):
            print(f"   ❌ No active runs")
            return None
        
        session_id = self.session_state.get('session_id')
        if not session_id:
            return None
        
        # Find device position in sequence
        device_sequence = self.session_state['device_sequence']
        if device_id not in device_sequence:
            print(f"   ❌ Device {device_id} not in course sequence")
            return None
        
        device_position = device_sequence.index(device_id)
        
        # Categorize athletes by gap
        priority_1 = []  # gap == 1 (sequential)
        priority_2 = []  # gap > 1 (skipped devices)
        
        print(f"   🔍 Checking {len(self.session_state['active_runs'])} active athletes for device {device_id} (position {device_position}):")
        
        for run_id, run_info in self.session_state['active_runs'].items():
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
            self.mark_skipped_segments(chosen, device_position, skipped_count)
        
        return chosen
    
    def mark_skipped_segments(self, run_id: str, current_position: int, skipped_count: int):
        """Mark segments as missed when athlete skips devices"""
        run_info = self.session_state['active_runs'].get(run_id)
        if not run_info:
            return
        
        last_position = run_info.get('sequence_position', -1)
        print(f"   📝 Marking {skipped_count} skipped segment(s) for {run_info['athlete_name']}:")
        
        # Mark each skipped segment
        for pos in range(last_position + 1, current_position):
            device_sequence = self.session_state['device_sequence']
            from_device = device_sequence[pos - 1] if pos > 0 else '192.168.99.100'
            to_device = device_sequence[pos]
            
            # Find and mark the segment
            segments = self.db.get_run_segments(run_id)
            for seg in segments:
                if seg['from_device'] == from_device and seg['to_device'] == to_device:
                    self.db.mark_segment_missed(seg['segment_id'])
                    print(f"      ❌ {from_device} → {to_device} marked as missed")
                    break

    def _display_pattern_sequence(self, pattern_data: dict):
        """
        Display the pattern sequence for Simon Says per spec:
        1. D0 beeps (signals pattern about to display)
        2. Chase each cone in pattern, return to assigned color after
        3. D0 beeps (signals athlete to GO)

        NOTE: Cones are ALREADY at their assigned colors from Deploy step.
        """
        import time

        pattern = pattern_data['pattern']
        colored_devices = pattern_data['colored_devices']
        description = pattern_data['description']

        print(f"   Pattern to display: {description}")

        # Color mapping for solid colors
        solid_color_map = {
            'red': 'solid_red',
            'green': 'solid_green',
            'blue': 'solid_blue',
            'yellow': 'solid_yellow',
            'orange': 'solid_orange',
            'white': 'solid_white',
            'purple': 'solid_purple',
            'cyan': 'solid_cyan'
        }

        # Color mapping for chase animations
        chase_color_map = {
            'red': 'chase_red',
            'green': 'chase_green',
            'blue': 'chase_blue',
            'yellow': 'chase_yellow',   # Fixed: use chase_yellow for Simon Says
            'orange': 'chase_amber',
            'white': 'chase',
            'purple': 'chase_purple',
            'cyan': 'chase_blue'
        }

        try:
            # STEP 1: Play beep on D0 (signals pattern about to display)
            print(f"\n🔊 Playing beep - pattern about to display...")
            try:
                import requests
                requests.post(
                    'http://localhost:5000/api/audio/play',
                    json={
                        'node_id': '192.168.99.100',
                        'clip': 'default_beep'
                    },
                    timeout=2
                )
                print(f"   ✅ Beep played")
            except Exception as beep_err:
                print(f"   ⚠️ Beep failed: {beep_err}")

            time.sleep(0.5)  # Brief pause after beep

            # STEP 2: Show pattern using chase animations
            print(f"\n🔄 Displaying pattern sequence...")

            # OPTION C: Clients auto-terminate chases after 3s, no stop commands needed
            for i, device in enumerate(pattern):
                color = device.get('color', 'white')
                device_id = device['device_id']
                chase_pattern = chase_color_map.get(color.lower(), 'chase')

                print(f"   💡 Step {i+1}/{len(pattern)}: {color.upper()} ({device_id})")

                # Send chase command only - client will auto-terminate after 3s
                self.registry.set_led(device_id, chase_pattern)
                print(f"      {chase_pattern} → {device_id}")

                # Wait for client auto-termination (3s) + buffer to prevent overlap
                # NOTE: We sleep AFTER every chase, including the last one
                time.sleep(5.0)  # Increased from 4.0s to compensate for slow clients

            print(f"   ✓ Pattern display complete (all chases finished)\n")

            # Log reminder to System Log
            self.registry.log(f"🎯 Touch pattern: {description}, then touch D0 (Start) to submit", source="session")

            # BUG FIX #1: Restore assigned colors instead of clearing patterns
            print(f"🧹 Restoring assigned colors after pattern display...")
            for device in pattern_data['colored_devices']:
                device_id = device['device_id']
                node = self.registry.nodes.get(device_id)
                if node:
                    # Restore to assigned color
                    color = device.get('color', 'red')
                    node.led_pattern = f"solid_{color.lower()}"
                    print(f"   {device_id} → restored to {color.upper()} (solid_{color.lower()})")

            print(f"   ✅ All chase patterns cleared\n")

            # STEP 3: Play GO beep on D0 (signals athlete can start)
            print(f"🔊 Playing GO beep...")
            try:
                requests.post(
                    'http://localhost:5000/api/audio/play',
                    json={
                        'node_id': '192.168.99.100',
                        'clip': 'default_beep'
                    },
                    timeout=2
                )
                print(f"   ✅ GO beep played - athlete can now begin\n")
            except Exception as beep_err:
                print(f"   ⚠️ GO beep failed: {beep_err}\n")

        except Exception as e:
            print(f"   ❌ Error displaying pattern: {e}")
            import traceback
            traceback.print_exc()
            # Continue anyway - don't block session start
