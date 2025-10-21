#!/usr/bin/env python3
"""
Field Trainer Touch Sequence Test Suite
Tests end-to-end touch flows with database integration

Usage: python3 test_touch_sequences.py
"""

import sys
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add field_trainer to path
sys.path.insert(0, '/opt')

DB_PATH = '/opt/data/field_trainer.db'

class TouchSequenceTests:
    def __init__(self):
        self.test_results = []
        self.start_time = None
        
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Record test result"""
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def print_header(self, title: str):
        """Print formatted test header"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    
    def print_test(self, test_num: str, description: str):
        """Print test description"""
        print(f"\n{test_num}: {description}")
    
    def setup(self):
        """Clean database before tests"""
        print("\n🧹 Setting up test environment...")
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('DELETE FROM segments')
        conn.execute('DELETE FROM runs')
        conn.execute('DELETE FROM sessions')
        conn.commit()
        conn.close()
        print("   ✅ Database cleaned")
    
    def teardown(self):
        """Cleanup after tests"""
        print("\n🧹 Cleaning up test data...")
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM segments WHERE 1=1')
        conn.execute('DELETE FROM runs WHERE 1=1')
        conn.execute('DELETE FROM sessions WHERE 1=1')
        conn.commit()
        conn.close()
        print("   ✅ Cleanup complete")
    
    def get_test_data(self) -> tuple:
        """Get real team_id and athlete_ids from database"""
        conn = sqlite3.connect(DB_PATH)
        
        team = conn.execute('SELECT team_id FROM teams LIMIT 1').fetchone()
        if not team:
            conn.close()
            raise Exception("No teams in database")
        team_id = team[0]
        
        athlete_names = ['Billie', 'Jill', 'Sarah', 'Bobby', 'Ella']
        athlete_ids = []
        
        for name in athlete_names:
            athlete = conn.execute(
                'SELECT athlete_id FROM athletes WHERE name=? LIMIT 1',
                (name,)
            ).fetchone()
            if athlete:
                athlete_ids.append(athlete[0])
        
        conn.close()
        
        if not athlete_ids:
            raise Exception("No athletes found")
        
        return team_id, athlete_ids

    def simulate_touch_sequence(self, run_id: str, device_sequence: List[str], 
                                touch_pattern: List[bool]) -> List[Dict]:
        """
        Simulate a sequence of touches for an athlete
        
        Args:
            run_id: The run to touch for
            device_sequence: List of device IDs
            touch_pattern: List of bools - True=touch device, False=skip
        
        Returns:
            List of segment states after all touches
        """
        from field_trainer.db_manager import DatabaseManager
        from coach_interface import find_athlete_for_touch, active_session_state
        
        db = DatabaseManager(DB_PATH)
        
        base_time = datetime.now()
        touch_count = 0
        
        for i, should_touch in enumerate(touch_pattern):
            if should_touch and i < len(device_sequence):
                device_id = device_sequence[i]
                touch_time = base_time + timedelta(seconds=touch_count * 5)
                
                # Call attribution logic
                chosen_run = find_athlete_for_touch(device_id, touch_time)
                
                # If attributed to this run, record the touch and UPDATE POSITION
                if chosen_run == run_id:
                    db.record_touch(run_id, device_id, touch_time)
                    # CRITICAL: Update sequence_position after successful touch
                    if run_id in active_session_state['active_runs']:
                        active_session_state['active_runs'][run_id]['sequence_position'] = i
                    touch_count += 1
        
        # Get final segment states
        conn = sqlite3.connect(DB_PATH)
        segments = conn.execute('''
            SELECT sequence, from_device, to_device, touch_detected, alert_type, actual_time
            FROM segments
            WHERE run_id = ?
            ORDER BY sequence
        ''', (run_id,)).fetchall()
        conn.close()
        
        return [dict(zip(['sequence', 'from_device', 'to_device', 'touch_detected', 
                         'alert_type', 'actual_time'], seg)) for seg in segments]
 
    # ==================== TEST 1: SEQUENTIAL COMPLETION ====================
    
    def test_sequential_completion(self) -> bool:
        """
        Test 1: Sequential Course Completion
        What: Athlete touches all devices in correct order (D1→D2→D3→D4→D5)
        Why: Validates the happy path - normal course progression
        Expected: All 5 segments marked as touched, no missed segments
        """
        self.print_header("TEST 1: Sequential Course Completion")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 1", "Single athlete completes course sequentially")
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            athlete_name = runs[0]['athlete_name']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Athlete: {athlete_name}")
            print(f"   Pattern: D1 → D2 → D3 → D4 → D5 (all sequential)")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',  # D0
                '192.168.99.101',  # D1
                '192.168.99.102',  # D2
                '192.168.99.103',  # D3
                '192.168.99.104',  # D4
                '192.168.99.105',  # D5
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                run_id: {
                    'athlete_name': athlete_name,
                    'sequence_position': 0,  # At start
                    'queue_position': 0
                }
            }
            
            # Simulate touches: [D0, D1, D2, D3, D4, D5] - all touched
            touch_pattern = [True, True, True, True, True, True]
            segments = self.simulate_touch_sequence(run_id, device_sequence, touch_pattern)
            
            # Clean up state
            active_session_state.clear()
            
            # Verify results
            print(f"\n   Segment Results:")
            all_touched = True
            any_missed = False
            
            for seg in segments:
                status = "✓" if seg['touch_detected'] else "○"
                alert = f" [{seg['alert_type']}]" if seg['alert_type'] else ""
                print(f"      {status} Seq {seg['sequence']}: {seg['from_device'][-3:]} → {seg['to_device'][-3:]}{alert}")
                
                if not seg['touch_detected']:
                    all_touched = False
                if seg['alert_type'] == 'missed_touch':
                    any_missed = True
            
            if all_touched and not any_missed:
                self.log_result("Test 1", True, "All segments touched, no missed")
                print("\n✅ TEST 1 PASSED: Sequential completion works correctly")
                return True
            else:
                self.log_result("Test 1", False, f"touched={all_touched}, missed={any_missed}")
                print(f"\n❌ TEST 1 FAILED: Expected all touched, got touched={all_touched}")
                return False
                
        except Exception as e:
            self.log_result("Test 1", False, str(e))
            print(f"\n❌ TEST 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 2: SKIP ONE DEVICE ====================
    
    def test_skip_one_device(self) -> bool:
        """
        Test 2: Skip Single Device
        What: Athlete skips exactly one device (D1→D2→skip D3→D4→D5)
        Why: Tests skip detection and missed segment marking
        Expected: Segment D2→D3 marked as missed_touch, others touched
        """
        self.print_header("TEST 2: Skip Single Device")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 2", "Athlete skips D3 in sequence")
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            athlete_name = runs[0]['athlete_name']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Athlete: {athlete_name}")
            print(f"   Pattern: D1 → D2 → SKIP D3 → D4 → D5")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105',
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                run_id: {
                    'athlete_name': athlete_name,
                    'sequence_position': 0,
                    'queue_position': 0
                }
            }
            
            # Simulate touches: [D0, D1, D2, skip D3, D4, D5]
            touch_pattern = [True, True, True, False, True, True]
            segments = self.simulate_touch_sequence(run_id, device_sequence, touch_pattern)
            
            # Clean up state
            active_session_state.clear()
            
            # Verify results
            print(f"\n   Segment Results:")
            skip_segment_correct = False
            other_segments_correct = True
            
            for seg in segments:
                status = "✓" if seg['touch_detected'] else "○"
                alert = f" [{seg['alert_type']}]" if seg['alert_type'] else ""
                print(f"      {status} Seq {seg['sequence']}: {seg['from_device'][-3:]} → {seg['to_device'][-3:]}{alert}")
                
                # Check if D2→D3 (sequence 2) is marked missed
                if seg['sequence'] == 2:
                    if not seg['touch_detected'] and seg['alert_type'] == 'missed_touch':
                        skip_segment_correct = True
                    else:
                        print(f"         ❌ Expected missed_touch, got touch={seg['touch_detected']}, alert={seg['alert_type']}")
                        other_segments_correct = False
                else:
                    # Other segments should be touched
                    if not seg['touch_detected']:
                        print(f"         ❌ Segment {seg['sequence']} should be touched")
                        other_segments_correct = False
            
            if skip_segment_correct and other_segments_correct:
                self.log_result("Test 2", True, "Skip detected and marked correctly")
                print("\n✅ TEST 2 PASSED: Single skip detected and marked")
                return True
            else:
                self.log_result("Test 2", False, f"skip_correct={skip_segment_correct}, others={other_segments_correct}")
                print(f"\n❌ TEST 2 FAILED: Skip marking incorrect")
                return False
                
        except Exception as e:
            self.log_result("Test 2", False, str(e))
            print(f"\n❌ TEST 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 3: SKIP MULTIPLE DEVICES ====================
    
    def test_skip_multiple_devices(self) -> bool:
        """
        Test 3: Skip Multiple Consecutive Devices
        What: Athlete skips 2 devices (D1→D2→skip D3,D4→D5)
        Why: Tests handling of large gaps and multiple missed segments
        Expected: Segments D2→D3 and D3→D4 both marked as missed_touch
        """
        self.print_header("TEST 3: Skip Multiple Devices")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 3", "Athlete skips D3 and D4")
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            athlete_name = runs[0]['athlete_name']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Athlete: {athlete_name}")
            print(f"   Pattern: D1 → D2 → SKIP D3 → SKIP D4 → D5")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105',
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                run_id: {
                    'athlete_name': athlete_name,
                    'sequence_position': 0,
                    'queue_position': 0
                }
            }
            
            # Simulate touches: [D0, D1, D2, skip D3, skip D4, D5]
            touch_pattern = [True, True, True, False, False, True]
            segments = self.simulate_touch_sequence(run_id, device_sequence, touch_pattern)
            
            # Clean up state
            active_session_state.clear()
            
            # Verify results
            print(f"\n   Segment Results:")
            skip_seq2_correct = False
            skip_seq3_correct = False
            other_segments_correct = True
            
            for seg in segments:
                status = "✓" if seg['touch_detected'] else "○"
                alert = f" [{seg['alert_type']}]" if seg['alert_type'] else ""
                print(f"      {status} Seq {seg['sequence']}: {seg['from_device'][-3:]} → {seg['to_device'][-3:]}{alert}")
                
                # Check if D2→D3 (sequence 2) is marked missed
                if seg['sequence'] == 2:
                    if not seg['touch_detected'] and seg['alert_type'] == 'missed_touch':
                        skip_seq2_correct = True
                    else:
                        print(f"         ❌ Seq 2 should be missed_touch")
                        other_segments_correct = False
                
                # Check if D3→D4 (sequence 3) is marked missed
                elif seg['sequence'] == 3:
                    if not seg['touch_detected'] and seg['alert_type'] == 'missed_touch':
                        skip_seq3_correct = True
                    else:
                        print(f"         ❌ Seq 3 should be missed_touch")
                        other_segments_correct = False
                
                # Other segments should be touched
                elif seg['sequence'] in [0, 1, 4]:
                    if not seg['touch_detected']:
                        print(f"         ❌ Segment {seg['sequence']} should be touched")
                        other_segments_correct = False
            
            if skip_seq2_correct and skip_seq3_correct and other_segments_correct:
                self.log_result("Test 3", True, "Multiple skips detected correctly")
                print("\n✅ TEST 3 PASSED: Multiple skips detected and marked")
                return True
            else:
                self.log_result("Test 3", False, f"seq2={skip_seq2_correct}, seq3={skip_seq3_correct}, others={other_segments_correct}")
                print(f"\n❌ TEST 3 FAILED: Multiple skip marking incorrect")
                return False
                
        except Exception as e:
            self.log_result("Test 3", False, str(e))
            print(f"\n❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 4: SAME DEVICE TWICE ====================
    
    def test_same_device_twice(self) -> bool:
        """
        Test 4: Same Device Touched Twice
        What: Athlete touches D2, then D2 again before moving to D3
        Why: Tests rejection of duplicate touches on same device (gap=0)
        Expected: Only first D2 touch counted, second touch rejected/ignored
        """
        self.print_header("TEST 4: Same Device Twice")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 4", "Athlete touches D2 twice before moving on")
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            athlete_name = runs[0]['athlete_name']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Athlete: {athlete_name}")
            print(f"   Pattern: D1 → D2 → D2 (again) → D3 → D4 → D5")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105',
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                run_id: {
                    'athlete_name': athlete_name,
                    'sequence_position': 0,
                    'queue_position': 0
                }
            }
            
            # Manually simulate with duplicate D2 touch
            from coach_interface import find_athlete_for_touch
            
            base_time = datetime.now()
            devices_to_touch = [
                ('192.168.99.101', 0),   # D1
                ('192.168.99.102', 5),   # D2
                ('192.168.99.102', 7),   # D2 again (should be rejected!)
                ('192.168.99.103', 10),  # D3
                ('192.168.99.104', 15),  # D4
                ('192.168.99.105', 20),  # D5
            ]

            touch_count = 0
            for device_id, offset in devices_to_touch:
                touch_time = base_time + timedelta(seconds=offset)
                chosen = find_athlete_for_touch(device_id, touch_time)
                
                if chosen:
                    db.record_touch(run_id, device_id, touch_time)
                    touch_count += 1
                    print(f"      Touch {touch_count}: {device_id[-3:]} attributed")
                    # UPDATE POSITION
                    device_position = device_sequence.index(device_id)
                    active_session_state['active_runs'][run_id]['sequence_position'] = device_position
                else:
                    print(f"      Touch rejected: {device_id[-3:]} (gap<0, backwards)")

            # Clean up state
            active_session_state.clear()
            
            # Verify segment results
            conn = sqlite3.connect(DB_PATH)
            segments = conn.execute('''
                SELECT sequence, touch_detected
                FROM segments
                WHERE run_id = ?
                ORDER BY sequence
            ''', (run_id,)).fetchall()
            conn.close()
            
            all_touched = all(seg[1] for seg in segments)

            # Should have exactly 5 touches (duplicate rejected)
            if touch_count == 5 and all_touched:
                self.log_result("Test 4", True, "Duplicate touch rejected correctly")
                print(f"\n✅ TEST 4 PASSED: Duplicate D2 touch rejected (5/6 touches counted)")
                return True
            else:
                self.log_result("Test 4", False, f"touch_count={touch_count}, all_touched={all_touched}")
                print(f"\n❌ TEST 4 FAILED: Expected 5 touches, got {touch_count}")
                return False
                
        except Exception as e:
            self.log_result("Test 4", False, str(e))
            print(f"\n❌ TEST 4 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 5: BACKWARDS TOUCH ====================
    
    def test_backwards_touch(self) -> bool:
        """
        Test 5: Backwards Touch Rejection
        What: Athlete at D4 touches D2 (going backwards)
        Why: Tests rejection of backwards movement (gap<0)
        Expected: D2 touch rejected, athlete stays at D4
        """
        self.print_header("TEST 5: Backwards Touch")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state, find_athlete_for_touch
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 5", "Athlete at D4 touches D2 (backwards)")
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            athlete_name = runs[0]['athlete_name']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Athlete: {athlete_name}")
            print(f"   Pattern: D1 → D2 → D3 → D4 → D2 (backwards) → D5")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105',
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                run_id: {
                    'athlete_name': athlete_name,
                    'sequence_position': 0,
                    'queue_position': 0
                }
            }
            
            # Simulate touches with backwards attempt
            base_time = datetime.now()
            devices_to_touch = [
                ('192.168.99.101', 0),   # D1
                ('192.168.99.102', 5),   # D2
                ('192.168.99.103', 10),  # D3
                ('192.168.99.104', 15),  # D4
                ('192.168.99.102', 18),  # D2 (backwards! should be rejected)
                ('192.168.99.105', 20),  # D5
            ]
            touch_count = 0
            for device_id, offset in devices_to_touch:
                touch_time = base_time + timedelta(seconds=offset)
                chosen = find_athlete_for_touch(device_id, touch_time)
                
                if chosen:
                    db.record_touch(run_id, device_id, touch_time)
                    touch_count += 1
                    print(f"      Touch {touch_count}: {device_id[-3:]} attributed")
                    # UPDATE POSITION
                    device_position = device_sequence.index(device_id)
                    active_session_state['active_runs'][run_id]['sequence_position'] = device_position
                else:
                    print(f"      Touch rejected: {device_id[-3:]} (gap<0, backwards)")

            # Clean up state
            active_session_state.clear()
            
            # Verify results
            conn = sqlite3.connect(DB_PATH)
            segments = conn.execute('''
                SELECT sequence, touch_detected, actual_time
                FROM segments
                WHERE run_id = ?
                ORDER BY sequence
            ''', (run_id,)).fetchall()
            conn.close()
            
            # Calculate all_touched BEFORE using it
            all_touched = all(seg[1] for seg in segments)
            
            print(f"\n   Segment Results:")
            for i, seg in enumerate(segments):
                status = "✓" if seg[1] else "○"
                print(f"      {status} Segment {seg[0]}")
            
            # Should have exactly 5 touches (backwards rejected)
            if touch_count == 5 and all_touched:
                self.log_result("Test 5", True, "Backwards touch rejected correctly")
                print(f"\n✅ TEST 5 PASSED: Backwards touch rejected (5/6 touches counted)")
                return True
            else:
                self.log_result("Test 5", False, f"touch_count={touch_count}, all_touched={all_touched}")
                print(f"\n❌ TEST 5 FAILED: Expected 5 touches, got {touch_count}")
                return False
                
        except Exception as e:
            self.log_result("Test 5", False, str(e))
            print(f"\n❌ TEST 5 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 6: MULTI-ATHLETE SEQUENCE ====================
    
    def test_multi_athlete_sequence(self) -> bool:
        """
        Test 6: Two Athletes with Different Patterns
        What: Billie completes sequentially, Jill skips D3
        Why: Tests system handles multiple athletes with different touch patterns
        Expected: Both runs tracked correctly with appropriate segment marking
        """
        self.print_header("TEST 6: Multi-Athlete Touch Sequences")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state, find_athlete_for_touch
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 6", "Billie sequential, Jill skips D3")
            
            # Create session with 2 athletes
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=athlete_ids[:2]
            )
            
            runs = list(db.get_session_runs(session_id))
            billie_run = runs[0]
            jill_run = runs[1]
            
            # Start both runs
            db.start_run(billie_run['run_id'])
            db.create_segments_for_run(billie_run['run_id'], 1)
            
            db.start_run(jill_run['run_id'])
            db.create_segments_for_run(jill_run['run_id'], 1)
            
            print(f"   Billie: D1 → D2 → D3 → D4 → D5 (sequential)")
            print(f"   Jill:   D1 → D2 → SKIP D3 → D4 → D5")
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105',
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {
                billie_run['run_id']: {
                    'athlete_name': billie_run['athlete_name'],
                    'sequence_position': 0,
                    'queue_position': 0
                },
                jill_run['run_id']: {
                    'athlete_name': jill_run['athlete_name'],
                    'sequence_position': 0,
                    'queue_position': 1
                }
            }
            
            # Simulate interleaved touches
            base_time = datetime.now()
            touches = [
                ('192.168.99.101', 0, billie_run['run_id']),   # Billie D1
                ('192.168.99.101', 2, jill_run['run_id']),     # Jill D1
                ('192.168.99.102', 5, billie_run['run_id']),   # Billie D2
                ('192.168.99.102', 7, jill_run['run_id']),     # Jill D2
                ('192.168.99.103', 10, billie_run['run_id']),  # Billie D3
                # Jill skips D3
                ('192.168.99.104', 12, jill_run['run_id']),    # Jill D4 (skip!)
                ('192.168.99.104', 15, billie_run['run_id']),  # Billie D4
                ('192.168.99.105', 17, jill_run['run_id']),    # Jill D5
                ('192.168.99.105', 20, billie_run['run_id']),  # Billie D5
            ]
            print(f"\n   Processing touches...")
            for device_id, offset, expected_run in touches:
                touch_time = base_time + timedelta(seconds=offset)
                chosen = find_athlete_for_touch(device_id, touch_time)
                
                if chosen:
                    athlete = active_session_state['active_runs'][chosen]['athlete_name']
                    db.record_touch(chosen, device_id, touch_time)
                    # UPDATE POSITION
                    device_position = device_sequence.index(device_id)
                    active_session_state['active_runs'][chosen]['sequence_position'] = device_position
                    print(f"      {device_id[-3:]} → {athlete}")
            
            # Clean up state
            active_session_state.clear()
            
            # Verify Billie's results (all sequential)
            conn = sqlite3.connect(DB_PATH)
            
            print(f"\n   Billie's Segments:")
            billie_segs = conn.execute('''
                SELECT sequence, touch_detected, alert_type
                FROM segments
                WHERE run_id = ?
                ORDER BY sequence
            ''', (billie_run['run_id'],)).fetchall()
            
            billie_correct = all(seg[1] for seg in billie_segs) and \
                            all(seg[2] is None for seg in billie_segs)
            
            for seg in billie_segs:
                status = "✓" if seg[1] else "○"
                alert = f" [{seg[2]}]" if seg[2] else ""
                print(f"      {status} Segment {seg[0]}{alert}")
            
            # Verify Jill's results (skip at seq 2)
            print(f"\n   Jill's Segments:")
            jill_segs = conn.execute('''
                SELECT sequence, touch_detected, alert_type
                FROM segments
                WHERE run_id = ?
                ORDER BY sequence
            ''', (jill_run['run_id'],)).fetchall()
            
            jill_seq2_missed = jill_segs[2][1] == 0 and jill_segs[2][2] == 'missed_touch'
            jill_others_touched = all(seg[1] for i, seg in enumerate(jill_segs) if i != 2)
            jill_correct = jill_seq2_missed and jill_others_touched
            
            for seg in jill_segs:
                status = "✓" if seg[1] else "○"
                alert = f" [{seg[2]}]" if seg[2] else ""
                print(f"      {status} Segment {seg[0]}{alert}")
            
            conn.close()
            
            if billie_correct and jill_correct:
                self.log_result("Test 6", True, "Multi-athlete patterns handled correctly")
                print(f"\n✅ TEST 6 PASSED: Both athletes tracked correctly")
                return True
            else:
                self.log_result("Test 6", False, f"billie={billie_correct}, jill={jill_correct}")
                print(f"\n❌ TEST 6 FAILED: Tracking incorrect")
                return False
                
        except Exception as e:
            self.log_result("Test 6", False, str(e))
            print(f"\n❌ TEST 6 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all touch sequence tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - TOUCH SEQUENCE TEST SUITE")
        print("="*70)
        print(f"  Database: {DB_PATH}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Setup
        self.setup()
        
        # Run tests
        tests = [
            ("Sequential Completion", self.test_sequential_completion),
            ("Skip One Device", self.test_skip_one_device),
            ("Skip Multiple Devices", self.test_skip_multiple_devices),
            ("Same Device Twice", self.test_same_device_twice),
            ("Backwards Touch", self.test_backwards_touch),
            ("Multi-Athlete Sequence", self.test_multi_athlete_sequence),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                # Clean between tests
                conn = sqlite3.connect(DB_PATH)
                conn.execute('DELETE FROM segments')
                conn.execute('DELETE FROM runs')
                conn.execute('DELETE FROM sessions')
                conn.commit()
                conn.close()
                
                if test_func():
                    passed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                print(f"\n❌ {test_name} crashed: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        # Teardown
        self.teardown()
        
        # Summary
        elapsed = time.time() - self.start_time
        self.print_summary(passed, failed, elapsed)
        
        return failed == 0
    
    def print_summary(self, passed: int, failed: int, elapsed: float):
        """Print test summary"""
        total = passed + failed
        
        print("\n" + "="*70)
        print("  TEST SUMMARY")
        print("="*70)
        print(f"  Total Tests: {total}")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏱️  Time: {elapsed:.2f}s")
        print("="*70)
        
        if failed == 0:
            print("  🎉 ALL TESTS PASSED!")
        else:
            print(f"  ⚠️  {failed} TEST(S) FAILED")
        
        print("="*70)
        
        # Save results
        self.save_results(passed, failed, elapsed)
    
    def save_results(self, passed: int, failed: int, elapsed: float):
        """Save test results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"/tmp/touch_sequence_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - TOUCH SEQUENCE TEST RESULTS\n")
                f.write("="*70 + "\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Database: {DB_PATH}\n")
                f.write(f"Duration: {elapsed:.2f}s\n")
                f.write(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}\n")
                f.write("="*70 + "\n\n")
                
                for result in self.test_results:
                    status = "✅ PASS" if result['passed'] else "❌ FAIL"
                    f.write(f"{status}: {result['test']}\n")
                    if result['message']:
                        f.write(f"  Message: {result['message']}\n")
                    f.write(f"  Time: {result['timestamp']}\n\n")
            
            print(f"\n📄 Results saved to: {filename}")
        except Exception as e:
            print(f"\n⚠️  Could not save results: {e}")


def main():
    """Main entry point"""
    tester = TouchSequenceTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
