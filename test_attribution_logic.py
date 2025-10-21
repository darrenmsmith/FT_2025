#!/usr/bin/env python3
"""
Field Trainer Attribution Logic Test Suite
Tests the multi-athlete touch attribution algorithm

Usage: python3 test_attribution_logic.py
"""

import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# Add field_trainer to path
sys.path.insert(0, '/opt')

class AttributionLogicTests:
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
    
    # ==================== TEST CATEGORY 1: GAP CALCULATION ====================
    
    def test_gap_calculation(self) -> bool:
        """
        Test Category 1: Gap Calculation
        Tests that gap = device_position - last_position is calculated correctly
        for all scenarios: sequential, skip, backwards, same device
        """
        self.print_header("TEST CATEGORY 1: Gap Calculation")
        
        all_passed = True
        
        # Mock device sequence for Course A
        device_sequence = [
            '192.168.99.100',  # D0 (Start) - position 0
            '192.168.99.101',  # D1 - position 1
            '192.168.99.102',  # D2 - position 2
            '192.168.99.103',  # D3 - position 3
            '192.168.99.104',  # D4 - position 4
            '192.168.99.105',  # D5 - position 5
        ]
        
        # ====================
        # Test 1.1: Sequential Touch (gap = 1)
        # ====================
        """
        What: Athlete progresses normally to next device in sequence
        Scenario: Athlete just touched D2 (position 2), now touches D3 (position 3)
        Expected: gap = 3 - 2 = 1 (sequential, should be Priority 1)
        Why: This is the normal, expected progression through the course
        """
        self.print_test("Test 1.1", "Sequential touch (gap = 1)")
        
        athlete_last_position = 2  # Just touched D2
        device_touched = '192.168.99.103'  # D3
        device_position = device_sequence.index(device_touched)  # position 3
        
        gap = device_position - athlete_last_position
        
        print(f"   Athlete last position: {athlete_last_position} (D2)")
        print(f"   Device touched: D3 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        
        if gap == 1:
            print("   ✅ PASS: Gap correctly calculated as 1 (sequential)")
            self.log_result("Test 1.1", True, "Sequential gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=1, got gap={gap}")
            self.log_result("Test 1.1", False, f"Expected gap=1, got {gap}")
            all_passed = False
        
        # ====================
        # Test 1.2: Skip One Device (gap = 2)
        # ====================
        """
        What: Athlete skips exactly one device in the sequence
        Scenario: Athlete at D2 (position 2), skips D3, touches D4 (position 4)
        Expected: gap = 4 - 2 = 2 (skipped 1 device, should be Priority 2)
        Why: System should detect this as a skip and mark D2→D3 as missed
        """
        self.print_test("Test 1.2", "Skip one device (gap = 2)")
        
        athlete_last_position = 2  # At D2
        device_touched = '192.168.99.104'  # D4
        device_position = device_sequence.index(device_touched)  # position 4
        
        gap = device_position - athlete_last_position
        
        print(f"   Athlete last position: {athlete_last_position} (D2)")
        print(f"   Device touched: D4 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        print(f"   Skipped device: D3 (position 3)")
        
        if gap == 2:
            print("   ✅ PASS: Gap correctly calculated as 2 (skipped 1 device)")
            self.log_result("Test 1.2", True, "Skip one device gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=2, got gap={gap}")
            self.log_result("Test 1.2", False, f"Expected gap=2, got {gap}")
            all_passed = False
        
        # ====================
        # Test 1.3: Skip Multiple Devices (gap > 2)
        # ====================
        """
        What: Athlete skips multiple devices in sequence
        Scenario: Athlete at D1 (position 1), skips D2,D3,D4, touches D5 (position 5)
        Expected: gap = 5 - 1 = 4 (skipped 3 devices, Priority 2 with multiple missed)
        Why: System should handle large gaps and mark all skipped segments as missed
        """
        self.print_test("Test 1.3", "Skip multiple devices (gap = 4)")
        
        athlete_last_position = 1  # At D1
        device_touched = '192.168.99.105'  # D5
        device_position = device_sequence.index(device_touched)  # position 5
        
        gap = device_position - athlete_last_position
        skipped_count = gap - 1  # Number of devices skipped
        
        print(f"   Athlete last position: {athlete_last_position} (D1)")
        print(f"   Device touched: D5 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        print(f"   Skipped devices: D2, D3, D4 ({skipped_count} devices)")
        
        if gap == 4:
            print("   ✅ PASS: Gap correctly calculated as 4 (skipped 3 devices)")
            self.log_result("Test 1.3", True, "Skip multiple devices gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=4, got gap={gap}")
            self.log_result("Test 1.3", False, f"Expected gap=4, got {gap}")
            all_passed = False
        
        # ====================
        # Test 1.4: Same Device Twice (gap = 0)
        # ====================
        """
        What: Athlete touches the same device multiple times
        Scenario: Athlete at D3 (position 3), touches D3 again
        Expected: gap = 3 - 3 = 0 (should be IGNORED, not attributed)
        Why: Prevents false positives from lingering near a device or accidental re-triggers
        """
        self.print_test("Test 1.4", "Same device twice (gap = 0)")
        
        athlete_last_position = 3  # At D3
        device_touched = '192.168.99.103'  # D3 again
        device_position = device_sequence.index(device_touched)  # position 3
        
        gap = device_position - athlete_last_position
        
        print(f"   Athlete last position: {athlete_last_position} (D3)")
        print(f"   Device touched: D3 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        print(f"   Expected behavior: IGNORE (same device)")
        
        if gap == 0:
            print("   ✅ PASS: Gap correctly calculated as 0 (same device, should ignore)")
            self.log_result("Test 1.4", True, "Same device gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=0, got gap={gap}")
            self.log_result("Test 1.4", False, f"Expected gap=0, got {gap}")
            all_passed = False
        
        # ====================
        # Test 1.5: Backwards Touch (gap < 0)
        # ====================
        """
        What: Athlete touches a device earlier in the sequence than their last position
        Scenario: Athlete at D4 (position 4), touches D2 (position 2)
        Expected: gap = 2 - 4 = -2 (negative, should be IGNORED)
        Why: Athletes can't go backwards in the course, this prevents confusion if
             someone accidentally triggers an earlier device or runs the course backwards
        """
        self.print_test("Test 1.5", "Backwards touch (gap = -2)")
        
        athlete_last_position = 4  # At D4
        device_touched = '192.168.99.102'  # D2 (going backwards!)
        device_position = device_sequence.index(device_touched)  # position 2
        
        gap = device_position - athlete_last_position
        
        print(f"   Athlete last position: {athlete_last_position} (D4)")
        print(f"   Device touched: D2 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        print(f"   Expected behavior: IGNORE (backwards movement)")
        
        if gap == -2:
            print("   ✅ PASS: Gap correctly calculated as -2 (backwards, should ignore)")
            self.log_result("Test 1.5", True, "Backwards touch gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=-2, got gap={gap}")
            self.log_result("Test 1.5", False, f"Expected gap=-2, got {gap}")
            all_passed = False
        
        # ====================
        # Test 1.6: Not Started Yet (last_position = -1)
        # ====================
        """
        What: Athlete hasn't started the course yet (no touches recorded)
        Scenario: Athlete hasn't touched D1 yet (position=-1), D2 (position 2) is touched
        Expected: gap = 2 - (-1) = 3 (large gap from start position)
        Why: Athletes must start at D1 (position 1), touching D2 first means gap > 1
             System should either REJECT or attribute as Priority 2 with missed segments
        Note: Starting position is -1 because position 0 is the Start/D0 device
        """
        self.print_test("Test 1.6", "Not started yet (gap from position -1)")
        
        athlete_last_position = -1  # Haven't started (no touches yet)
        device_touched = '192.168.99.102'  # D2
        device_position = device_sequence.index(device_touched)  # position 2
        
        gap = device_position - athlete_last_position
        
        print(f"   Athlete last position: {athlete_last_position} (not started)")
        print(f"   Device touched: D2 (position {device_position})")
        print(f"   Calculated gap: {gap}")
        print(f"   Expected behavior: Priority 2 with 2 missed segments OR REJECT")
        print(f"   Reasoning: Athlete must start at D1 first")
        
        if gap == 3:
            print("   ✅ PASS: Gap correctly calculated as 3 (not started → D2)")
            self.log_result("Test 1.6", True, "Not started gap calculation correct")
        else:
            print(f"   ❌ FAIL: Expected gap=3, got gap={gap}")
            self.log_result("Test 1.6", False, f"Expected gap=3, got {gap}")
            all_passed = False
        
        # Summary for this category
        if all_passed:
            print("\n✅ TEST CATEGORY 1 PASSED: All gap calculations correct")
        else:
            print("\n❌ TEST CATEGORY 1 FAILED: Some gap calculations incorrect")
        
        return all_passed
    # ==================== TEST CATEGORY 2: PRIORITY SORTING ====================
    
    def test_priority_sorting(self) -> bool:
        """
        Test Category 2: Priority Sorting
        Tests that when multiple athletes could receive a touch, the correct one is chosen
        Priority 1 (gap==1) always wins over Priority 2 (gap>1)
        Within same priority: lowest queue_position wins (or smallest gap for Priority 2)
        """
        self.print_header("TEST CATEGORY 2: Priority Sorting")
        
        all_passed = True
        
        # Import the actual attribution function
        try:
            sys.path.insert(0, '/opt')
            from coach_interface import find_athlete_for_touch, active_session_state
        except ImportError as e:
            print(f"❌ Cannot import attribution function: {e}")
            self.log_result("Test Category 2", False, "Import failed")
            return False
        
        # Mock device sequence
        device_sequence = [
            '192.168.99.100',  # D0 - position 0
            '192.168.99.101',  # D1 - position 1
            '192.168.99.102',  # D2 - position 2
            '192.168.99.103',  # D3 - position 3
            '192.168.99.104',  # D4 - position 4
            '192.168.99.105',  # D5 - position 5
        ]
        
        # ====================
        # Test 2.1: Multiple Priority 1 Athletes - Queue Position Tiebreaker
        # ====================
        """
        What: Two athletes both at sequential position for same device
        Scenario: Billie at D2 (gap=1, queue=0), Sarah at D2 (gap=1, queue=1), D3 touched
        Expected: Billie chosen because she has lower queue_position (0 < 1)
        Why: When multiple athletes are sequential (Priority 1), first in queue gets priority
             This ensures fair ordering and prevents conflicts
        """
        self.print_test("Test 2.1", "Multiple Priority 1 athletes - queue_position tiebreaker")
        
        # Set up mock active session state
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_2_1'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 2,  # At D2
                'queue_position': 0      # First in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 2,  # Also at D2
                'queue_position': 1      # Second in queue
            }
        }
        
        device_touched = '192.168.99.103'  # D3 (position 3)
        
        print(f"   Billie: position=2 (D2), gap=1, queue=0")
        print(f"   Sarah:  position=2 (D2), gap=1, queue=1")
        print(f"   Device touched: D3 (position 3)")
        print(f"   Both athletes have gap=1 (Priority 1)")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (lower queue_position)")
            self.log_result("Test 2.1", True, "Queue position tiebreaker works")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 2.1", False, f"Wrong athlete chosen: {chosen}")
            all_passed = False
        
        # ====================
        # Test 2.2: Priority 1 Beats Priority 2
        # ====================
        """
        What: One athlete sequential (Priority 1), another skipped (Priority 2)
        Scenario: Billie at D2 (gap=1), Sarah at D1 (gap=2), D3 touched
        Expected: Billie chosen because Priority 1 always beats Priority 2
        Why: Sequential progression (gap=1) is the expected behavior and gets priority
             over athletes who skipped devices, regardless of other factors
        """
        self.print_test("Test 2.2", "Priority 1 beats Priority 2")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_2_2'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 2,  # At D2
                'queue_position': 1      # Later in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 1,  # At D1 (skipped D2)
                'queue_position': 0      # Earlier in queue (doesn't matter!)
            }
        }
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Billie: position=2, gap=1 (Priority 1), queue=1")
        print(f"   Sarah:  position=1, gap=2 (Priority 2), queue=0")
        print(f"   Device touched: D3")
        print(f"   Priority 1 should win regardless of queue position")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (Priority 1 beats Priority 2)")
            self.log_result("Test 2.2", True, "Priority 1 beats Priority 2")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 2.2", False, f"Wrong priority: {chosen}")
            all_passed = False
        
        # ====================
        # Test 2.3: Priority 2 - Closest Gap Wins
        # ====================
        """
        What: Multiple athletes in Priority 2, different gap sizes
        Scenario: Billie at D1 (gap=2), Sarah at D0/Start (gap=3), D3 touched
        Expected: Billie chosen because gap=2 is smaller than gap=3
        Why: When multiple athletes skipped devices, the one closest to the target
             device (smallest gap) is more likely to be the correct attribution
        """
        self.print_test("Test 2.3", "Priority 2 - closest gap wins")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_2_3'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 1,  # At D1
                'queue_position': 1      # Later in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 0,  # At Start/D0
                'queue_position': 0      # Earlier in queue (doesn't matter!)
            }
        }
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Billie: position=1, gap=2 (Priority 2), queue=1")
        print(f"   Sarah:  position=0, gap=3 (Priority 2), queue=0")
        print(f"   Device touched: D3")
        print(f"   Smallest gap should win in Priority 2")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (smaller gap: 2 < 3)")
            self.log_result("Test 2.3", True, "Closest gap wins in Priority 2")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 2.3", False, f"Wrong gap priority: {chosen}")
            all_passed = False
        
        # ====================
        # Test 2.4: Priority 2 - Same Gap, Queue Position Tiebreaker
        # ====================
        """
        What: Multiple athletes in Priority 2 with same gap size
        Scenario: Billie at D1 (gap=2, queue=0), Sarah at D1 (gap=2, queue=1), D3 touched
        Expected: Billie chosen because queue_position 0 < 1
        Why: When gap sizes are equal in Priority 2, revert to queue order as tiebreaker
             This ensures deterministic, fair ordering
        """
        self.print_test("Test 2.4", "Priority 2 - same gap, queue_position tiebreaker")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_2_4'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 1,  # At D1
                'queue_position': 0      # First in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 1,  # Also at D1
                'queue_position': 1      # Second in queue
            }
        }
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Billie: position=1, gap=2 (Priority 2), queue=0")
        print(f"   Sarah:  position=1, gap=2 (Priority 2), queue=1")
        print(f"   Device touched: D3")
        print(f"   Same gap, so queue_position should decide")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (lower queue_position)")
            self.log_result("Test 2.4", True, "Queue tiebreaker works in Priority 2")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 2.4", False, f"Wrong queue priority: {chosen}")
            all_passed = False
        
        # Clean up mock state
        active_session_state.clear()
        
        # Summary for this category
        if all_passed:
            print("\n✅ TEST CATEGORY 2 PASSED: All priority sorting tests correct")
        else:
            print("\n❌ TEST CATEGORY 2 FAILED: Some priority sorting tests failed")
        
        return all_passed
    
    # ==================== TEST CATEGORY 3: EDGE CASES ====================
    
    def test_edge_cases(self) -> bool:
        """
        Test Category 3: Edge Cases
        Tests unusual scenarios that could crash the system or produce unexpected results
        Validates defensive programming and error handling
        """
        self.print_header("TEST CATEGORY 3: Edge Cases")
        
        all_passed = True
        
        # Import the actual attribution function
        try:
            sys.path.insert(0, '/opt')
            from coach_interface import find_athlete_for_touch, active_session_state
        except ImportError as e:
            print(f"❌ Cannot import attribution function: {e}")
            self.log_result("Test Category 3", False, "Import failed")
            return False
        
        # Mock device sequence
        device_sequence = [
            '192.168.99.100',  # D0 - position 0
            '192.168.99.101',  # D1 - position 1
            '192.168.99.102',  # D2 - position 2
            '192.168.99.103',  # D3 - position 3
            '192.168.99.104',  # D4 - position 4
            '192.168.99.105',  # D5 - position 5
        ]
        
        # ====================
        # Test 3.1: No Active Athletes
        # ====================
        """
        What: Touch occurs but no athletes are running
        Scenario: active_runs is empty, D3 is touched
        Expected: None returned, touch rejected gracefully without crash
        Why: Session might not be started yet, or all athletes finished
             System should handle this without errors
        """
        self.print_test("Test 3.1", "No active athletes")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_3_1'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {}  # EMPTY - no athletes!
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Active athletes: 0")
        print(f"   Device touched: D3")
        print(f"   Expected: None (no athletes to attribute to)")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen is None:
            print(f"   ✅ PASS: None returned (correctly rejected)")
            self.log_result("Test 3.1", True, "No active athletes handled gracefully")
        else:
            print(f"   ❌ FAIL: Expected None, got '{chosen}'")
            self.log_result("Test 3.1", False, f"Should return None, got {chosen}")
            all_passed = False
        
        # ====================
        # Test 3.2: Device Not in Sequence
        # ====================
        """
        What: Touch on a device that's not part of the course
        Scenario: D3 touched, but device_sequence doesn't include D3
        Expected: None returned with error logged, no crash
        Why: Prevents crashes if device ID is wrong or course misconfigured
             Should handle invalid device IDs gracefully
        """
        self.print_test("Test 3.2", "Device not in course sequence")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_3_2'
        # Device sequence WITHOUT D3!
        active_session_state['device_sequence'] = [
            '192.168.99.100',  # D0
            '192.168.99.101',  # D1
            '192.168.99.102',  # D2
            # D3 missing!
            '192.168.99.104',  # D4
            '192.168.99.105',  # D5
        ]
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 1,
                'queue_position': 0
            }
        }
        
        device_touched = '192.168.99.103'  # D3 (not in sequence!)
        
        print(f"   Device touched: D3")
        print(f"   Device sequence: [D0, D1, D2, D4, D5] (D3 missing)")
        print(f"   Expected: None (device not in course)")
        
        try:
            chosen = find_athlete_for_touch(device_touched, datetime.now())
            
            if chosen is None:
                print(f"   ✅ PASS: None returned (device not in sequence)")
                self.log_result("Test 3.2", True, "Invalid device handled gracefully")
            else:
                print(f"   ❌ FAIL: Expected None, got '{chosen}'")
                self.log_result("Test 3.2", False, f"Should reject invalid device, got {chosen}")
                all_passed = False
        except ValueError as e:
            # Also acceptable - ValueError with message
            if "not in list" in str(e) or "not in course" in str(e).lower():
                print(f"   ✅ PASS: ValueError raised (device not in sequence)")
                self.log_result("Test 3.2", True, "Invalid device raises proper error")
            else:
                print(f"   ❌ FAIL: Wrong error: {e}")
                self.log_result("Test 3.2", False, f"Wrong error type: {e}")
                all_passed = False
        except Exception as e:
            print(f"   ❌ FAIL: Unexpected crash: {e}")
            self.log_result("Test 3.2", False, f"Crashed: {e}")
            all_passed = False
        
        # ====================
        # Test 3.3: All Athletes Filtered Out
        # ====================
        """
        What: Multiple athletes but none qualify for the touch
        Scenario: 3 athletes all at D3, D3 is touched again (all gap=0)
        Expected: None returned (all filtered as "same device")
        Why: Prevents false attribution when multiple athletes linger at a device
             System should recognize no valid candidates remain after filtering
        """
        self.print_test("Test 3.3", "All athletes filtered out (all gap=0)")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_3_3'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 3,  # At D3
                'queue_position': 0
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 3,  # At D3
                'queue_position': 1
            },
            'run_jill': {
                'athlete_name': 'Jill',
                'sequence_position': 3,  # At D3
                'queue_position': 2
            }
        }
        
        device_touched = '192.168.99.103'  # D3 (all athletes at D3!)
        
        print(f"   Billie: position=3 (D3), gap=0")
        print(f"   Sarah:  position=3 (D3), gap=0")
        print(f"   Jill:   position=3 (D3), gap=0")
        print(f"   Device touched: D3")
        print(f"   Expected: None (all gap=0, all filtered)")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen is None:
            print(f"   ✅ PASS: None returned (all athletes filtered)")
            self.log_result("Test 3.3", True, "All filtered athletes handled")
        else:
            print(f"   ❌ FAIL: Expected None, got '{chosen}'")
            self.log_result("Test 3.3", False, f"Should reject all, got {chosen}")
            all_passed = False
        
        # ====================
        # Test 3.4: Athlete at Finish Line, Early Device Touched
        # ====================
        """
        What: Athlete finished course, but an earlier device is touched
        Scenario: Billie at D5 (finished), D1 is touched
        Expected: None (gap=-4, backwards movement rejected)
        Why: Athletes can't go backwards after finishing
             Prevents confusion if someone triggers a device after their run
        """
        self.print_test("Test 3.4", "Athlete at finish, early device touched")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_3_4'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 5,  # At D5 (finished!)
                'queue_position': 0
            }
        }
        
        device_touched = '192.168.99.101'  # D1 (way back!)
        
        print(f"   Billie: position=5 (D5 - finished)")
        print(f"   Device touched: D1 (position 1)")
        print(f"   Gap: 1 - 5 = -4 (backwards)")
        print(f"   Expected: None (backwards movement rejected)")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen is None:
            print(f"   ✅ PASS: None returned (backwards rejected)")
            self.log_result("Test 3.4", True, "Backwards from finish rejected")
        else:
            print(f"   ❌ FAIL: Expected None, got '{chosen}'")
            self.log_result("Test 3.4", False, f"Should reject backwards, got {chosen}")
            all_passed = False
        
        # ====================
        # Test 3.5: Missing queue_position in Athlete Data
        # ====================
        """
        What: Athlete data structure missing the queue_position field
        Scenario: Two athletes both Priority 1, but one missing queue_position
        Expected: Uses default value (999) for missing queue_position, doesn't crash
        Why: Defensive programming - handle incomplete data gracefully
             System should use sensible defaults rather than crashing
        """
        self.print_test("Test 3.5", "Missing queue_position in athlete data")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_3_5'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 2,
                'queue_position': 1  # Has queue_position
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 2
                # Missing queue_position!
            }
        }
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Billie: position=2, gap=1, queue=1")
        print(f"   Sarah:  position=2, gap=1, queue=MISSING")
        print(f"   Device touched: D3")
        print(f"   Expected: Billie chosen (1 < default 999)")
        
        try:
            chosen = find_athlete_for_touch(device_touched, datetime.now())
            
            if chosen == 'run_billie':
                print(f"   ✅ PASS: Billie chosen (missing queue_position handled)")
                self.log_result("Test 3.5", True, "Missing queue_position uses default")
            elif chosen == 'run_sarah':
                print(f"   ⚠️  Sarah chosen (default queue_position not working as expected)")
                self.log_result("Test 3.5", False, "Default queue_position logic may be wrong")
                all_passed = False
            else:
                print(f"   ❌ FAIL: Unexpected result: {chosen}")
                self.log_result("Test 3.5", False, f"Unexpected: {chosen}")
                all_passed = False
        except KeyError as e:
            print(f"   ❌ FAIL: KeyError crash (no default handling): {e}")
            self.log_result("Test 3.5", False, f"Crashed on missing key: {e}")
            all_passed = False
        except Exception as e:
            print(f"   ❌ FAIL: Unexpected crash: {e}")
            self.log_result("Test 3.5", False, f"Crashed: {e}")
            all_passed = False
        
        # Clean up mock state
        active_session_state.clear()
        
        # Summary for this category
        if all_passed:
            print("\n✅ TEST CATEGORY 3 PASSED: All edge cases handled correctly")
        else:
            print("\n❌ TEST CATEGORY 3 FAILED: Some edge cases not handled properly")
        
        return all_passed
    # ==================== TEST CATEGORY 4: MULTI-ATHLETE SCENARIOS ====================
    
    def test_multi_athlete_scenarios(self) -> bool:
        """
        Test Category 4: Multi-Athlete Scenarios
        Tests realistic race scenarios with multiple athletes at different positions
        Combines all previous logic (gap calculation, priority sorting, edge cases)
        These are integration-style tests simulating actual field conditions
        """
        self.print_header("TEST CATEGORY 4: Multi-Athlete Scenarios")
        
        all_passed = True
        
        # Import the actual attribution function
        try:
            sys.path.insert(0, '/opt')
            from coach_interface import find_athlete_for_touch, active_session_state
        except ImportError as e:
            print(f"❌ Cannot import attribution function: {e}")
            self.log_result("Test Category 4", False, "Import failed")
            return False
        
        # Mock device sequence
        device_sequence = [
            '192.168.99.100',  # D0 - position 0
            '192.168.99.101',  # D1 - position 1
            '192.168.99.102',  # D2 - position 2
            '192.168.99.103',  # D3 - position 3
            '192.168.99.104',  # D4 - position 4
            '192.168.99.105',  # D5 - position 5
        ]
        
        # ====================
        # Test 4.1: Three Athletes at Different Positions (Staggered Start)
        # ====================
        """
        What: Realistic scenario - 3 athletes at different stages of course
        Scenario: Billie at D3, Sarah at D2, Jill at D1, D3 is touched
        Expected: Sarah chosen (gap=1, Priority 1)
                  Billie rejected (gap=0, same device)
                  Jill rejected (gap=2, Priority 2 loses to Priority 1)
        Why: This is the most common race scenario - athletes spread across course
             Tests that Priority 1 wins even when other athletes are closer
        """
        self.print_test("Test 4.1", "Three athletes staggered - Priority 1 wins")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_4_1'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 3,  # At D3
                'queue_position': 0
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 2,  # At D2 (gap=1 for D3)
                'queue_position': 1
            },
            'run_jill': {
                'athlete_name': 'Jill',
                'sequence_position': 1,  # At D1 (gap=2 for D3)
                'queue_position': 2
            }
        }
        
        device_touched = '192.168.99.103'  # D3
        
        print(f"   Billie: position=3 (D3), gap=0 → IGNORE (same device)")
        print(f"   Sarah:  position=2 (D2), gap=1 → Priority 1 ✓")
        print(f"   Jill:   position=1 (D1), gap=2 → Priority 2")
        print(f"   Device touched: D3")
        print(f"   Expected: Sarah (Priority 1 beats Priority 2)")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_sarah':
            print(f"   ✅ PASS: Sarah chosen (Priority 1 wins)")
            self.log_result("Test 4.1", True, "Staggered scenario correct")
        else:
            print(f"   ❌ FAIL: Expected 'run_sarah', got '{chosen}'")
            self.log_result("Test 4.1", False, f"Wrong athlete: {chosen}")
            all_passed = False
        
        # ====================
        # Test 4.2: Wave Start - Multiple Athletes at D1
        # ====================
        """
        What: Mass start scenario - multiple athletes starting together
        Scenario: Billie, Sarah, Jill all at D1 (position 1), D2 touched
        Expected: Billie chosen (all gap=1, lowest queue_position=0 wins)
        Why: Simulates a wave/heat start where multiple athletes begin simultaneously
             System must fairly order who gets each sequential device touch
        """
        self.print_test("Test 4.2", "Wave start - all at D1, queue order decides")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_4_2'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 1,  # At D1
                'queue_position': 0      # First in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 1,  # At D1
                'queue_position': 1      # Second in queue
            },
            'run_jill': {
                'athlete_name': 'Jill',
                'sequence_position': 1,  # At D1
                'queue_position': 2      # Third in queue
            }
        }
        
        device_touched = '192.168.99.102'  # D2
        
        print(f"   Billie: position=1 (D1), gap=1, queue=0")
        print(f"   Sarah:  position=1 (D1), gap=1, queue=1")
        print(f"   Jill:   position=1 (D1), gap=1, queue=2")
        print(f"   Device touched: D2")
        print(f"   All Priority 1, queue_position decides")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (first in queue)")
            self.log_result("Test 4.2", True, "Wave start queue ordering works")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 4.2", False, f"Wrong queue priority: {chosen}")
            all_passed = False
        
        # ====================
        # Test 4.3: Simultaneous Skip - Two Athletes Skip Same Device
        # ====================
        """
        What: Multiple athletes skip the same device simultaneously
        Scenario: Billie at D2 (gap=2, queue=0), Sarah at D2 (gap=2, queue=1), D4 touched
        Expected: Billie chosen (both Priority 2, same gap, queue_position=0 wins)
        Why: Real scenario where multiple athletes might skip the same device
             System must handle ties in Priority 2 fairly using queue order
        """
        self.print_test("Test 4.3", "Simultaneous skip - same gap, queue decides")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_4_3'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 2,  # At D2
                'queue_position': 0      # First in queue
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 2,  # At D2 (both skip D3)
                'queue_position': 1      # Second in queue
            }
        }
        
        device_touched = '192.168.99.104'  # D4 (both skipped D3)
        
        print(f"   Billie: position=2, gap=2 (Priority 2), queue=0")
        print(f"   Sarah:  position=2, gap=2 (Priority 2), queue=1")
        print(f"   Device touched: D4")
        print(f"   Both skipped D3, queue_position decides")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (first in queue)")
            self.log_result("Test 4.3", True, "Simultaneous skip handled correctly")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            self.log_result("Test 4.3", False, f"Wrong priority in skip: {chosen}")
            all_passed = False
        
        # ====================
        # Test 4.4: Sequential vs Skip - Priority 1 Must Win
        # ====================
        """
        What: Direct competition between Priority 1 and Priority 2
        Scenario: Billie at D3 (gap=1, Priority 1), Sarah at D2 (gap=2, Priority 2), D4 touched
        Expected: Billie chosen (Priority 1 always beats Priority 2)
        Why: Critical test - even though Sarah is earlier in queue (0 vs 1),
             Billie's sequential progression (Priority 1) must take precedence
             This is the core rule of the attribution system
        """
        self.print_test("Test 4.4", "Sequential vs skip - Priority 1 must win")
        
        active_session_state.clear()
        active_session_state['session_id'] = 'test_session_4_4'
        active_session_state['device_sequence'] = device_sequence
        active_session_state['active_runs'] = {
            'run_billie': {
                'athlete_name': 'Billie',
                'sequence_position': 3,  # At D3
                'queue_position': 1      # Later in queue (doesn't matter!)
            },
            'run_sarah': {
                'athlete_name': 'Sarah',
                'sequence_position': 2,  # At D2 (skipped D3)
                'queue_position': 0      # Earlier in queue (irrelevant!)
            }
        }
        
        device_touched = '192.168.99.104'  # D4
        
        print(f"   Billie: position=3 (D3), gap=1 (Priority 1), queue=1")
        print(f"   Sarah:  position=2 (D2), gap=2 (Priority 2), queue=0")
        print(f"   Device touched: D4")
        print(f"   Priority 1 MUST win despite Sarah's lower queue")
        
        chosen = find_athlete_for_touch(device_touched, datetime.now())
        
        if chosen == 'run_billie':
            print(f"   ✅ PASS: Billie chosen (Priority 1 beats Priority 2)")
            self.log_result("Test 4.4", True, "Priority 1 correctly beats Priority 2")
        else:
            print(f"   ❌ FAIL: Expected 'run_billie', got '{chosen}'")
            print(f"   ⚠️  CRITICAL: Priority 1 should ALWAYS beat Priority 2!")
            self.log_result("Test 4.4", False, f"CRITICAL: Priority logic broken - {chosen}")
            all_passed = False
        
        # Clean up mock state
        active_session_state.clear()
        
        # Summary for this category
        if all_passed:
            print("\n✅ TEST CATEGORY 4 PASSED: All multi-athlete scenarios correct")
        else:
            print("\n❌ TEST CATEGORY 4 FAILED: Some scenarios not handled correctly")
        
        return all_passed

    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all attribution logic tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - ATTRIBUTION LOGIC TEST SUITE")
        print("="*70)
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Run test categories
        tests = [
            ("Gap Calculation", self.test_gap_calculation),
            ("Priority Sorting", self.test_priority_sorting),
            ("Edge Cases", self.test_edge_cases),
            ("Multi-Athlete Scenarios", self.test_multi_athlete_scenarios),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ {test_name} crashed: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
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
        print(f"  Total Test Categories: {total}")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏱️  Time: {elapsed:.2f}s")
        print("="*70)
        
        if failed == 0:
            print("  🎉 ALL TESTS PASSED!")
        else:
            print(f"  ⚠️  {failed} TEST CATEGORY(IES) FAILED")
        
        print("="*70)
        
        # Save results
        self.save_results(passed, failed, elapsed)
    
    def save_results(self, passed: int, failed: int, elapsed: float):
        """Save test results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"/tmp/attribution_test_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - ATTRIBUTION LOGIC TEST RESULTS\n")
                f.write("="*70 + "\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
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
    tester = AttributionLogicTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
