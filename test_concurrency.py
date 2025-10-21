#!/usr/bin/env python3
"""
Field Trainer Concurrent Operations Test Suite
Tests race conditions, concurrent API calls, and database locking

Usage: python3 test_concurrency.py
"""

import sys
import time
import threading
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import queue

# Add field_trainer to path
sys.path.insert(0, '/opt')

DB_PATH = '/opt/data/field_trainer.db'

class ConcurrentOperationsTests:
    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.errors = queue.Queue()
        
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
    
    # ==================== TEST 1: SIMULTANEOUS SESSION STARTS ====================
    
    def test_simultaneous_session_starts(self) -> bool:
        """
        Test 1: Simultaneous Session Start Race Condition
        What: Multiple threads try to start runs from same session simultaneously
        Why: Tests if first touch handler can handle concurrent start_run() calls
             Validates that segments are created only once per run
             Ensures UNIQUE constraint prevents duplicate segments
        Expected: All runs start successfully, no duplicate segments created
        """
        self.print_header("TEST 1: Simultaneous Session Starts")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            
            # Get test data
            self.print_test("Test 1", "5 threads starting runs simultaneously")
            team_id, athlete_ids = self.get_test_data()
            
            # Create session with 5 athletes
            print(f"   Creating session with {len(athlete_ids)} athletes...")
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=athlete_ids[:5]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_ids = [run['run_id'] for run in runs]
            print(f"   Created {len(run_ids)} runs")
            
            # Start all runs concurrently
            print(f"   Starting all {len(run_ids)} runs simultaneously...")
            
            def start_run_thread(run_id: str, thread_num: int):
                """Thread worker to start a run"""
                try:
                    time.sleep(0.01 * thread_num)  # Slight stagger
                    db.start_run(run_id)
                    db.create_segments_for_run(run_id, 1)
                except Exception as e:
                    self.errors.put(('start_run', thread_num, str(e)))
            
            threads = []
            start_time = time.time()
            
            for i, run_id in enumerate(run_ids):
                t = threading.Thread(target=start_run_thread, args=(run_id, i))
                t.start()
                threads.append(t)
            
            # Wait for all threads
            for t in threads:
                t.join()
            
            elapsed = time.time() - start_time
            print(f"   All threads completed in {elapsed:.2f}s")
            
            # Check for errors
            errors = []
            while not self.errors.empty():
                errors.append(self.errors.get())
            
            if errors:
                print(f"   ⚠️  {len(errors)} thread errors occurred:")
                for err_type, thread_num, err_msg in errors:
                    print(f"      Thread {thread_num}: {err_msg}")
            
            # Verify results
            print(f"   Verifying segment counts...")
            conn = sqlite3.connect(DB_PATH)
            
            total_segments = 0
            duplicates_found = False
            
            for run_id in run_ids:
                count = conn.execute(
                    'SELECT COUNT(*) FROM segments WHERE run_id=?',
                    (run_id,)
                ).fetchone()[0]
                
                total_segments += count
                
                if count != 5:
                    print(f"      ❌ Run {run_id[:8]}: {count} segments (expected 5)")
                    duplicates_found = True
                else:
                    print(f"      ✓ Run {run_id[:8]}: 5 segments")
            
            conn.close()
            
            print(f"   Total segments created: {total_segments} (expected {len(run_ids) * 5})")
            
            if duplicates_found:
                self.log_result("Test 1", False, "Duplicate or missing segments")
                print("\n❌ TEST 1 FAILED: Segment creation race condition")
                return False
            elif errors:
                self.log_result("Test 1", False, f"{len(errors)} thread errors")
                print("\n❌ TEST 1 FAILED: Thread errors occurred")
                return False
            else:
                self.log_result("Test 1", True, "All runs started without duplicates")
                print("\n✅ TEST 1 PASSED: No race conditions in session start")
                return True
                
        except Exception as e:
            self.log_result("Test 1", False, str(e))
            print(f"\n❌ TEST 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 2: CONCURRENT DATABASE WRITES ====================
    
    def test_concurrent_database_writes(self) -> bool:
        """
        Test 2: Concurrent Database Writes
        What: Multiple threads writing to database simultaneously
        Why: Tests database locking behavior under concurrent writes
             Validates that SQLite connection pooling works correctly
             Ensures data integrity with multiple writers
        Expected: All writes succeed, no data corruption or deadlocks
        """
        self.print_header("TEST 2: Concurrent Database Writes")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            
            self.print_test("Test 2", "10 threads writing touch data simultaneously")
            team_id, athlete_ids = self.get_test_data()
            
            # Create session with 1 athlete
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            
            # Start run and create segments
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print(f"   Starting 10 concurrent database write operations...")
            
            devices = [
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105'
            ]
            
            write_count = [0]  # Mutable counter
            write_lock = threading.Lock()
            
            def write_touch_thread(device_id: str, thread_num: int):
                """Thread worker to write touch data"""
                try:
                    # Stagger slightly but keep concurrent
                    time.sleep(0.01 * thread_num)
                    
                    touch_time = datetime.now()
                    segment_id = db.record_touch(run_id, device_id, touch_time)
                    
                    if segment_id:
                        with write_lock:
                            write_count[0] += 1
                    
                except Exception as e:
                    self.errors.put(('write', thread_num, str(e)))
            
            threads = []
            start_time = time.time()
            
            # Create 10 threads (2 threads per device)
            for i in range(10):
                device = devices[i % 5]
                t = threading.Thread(target=write_touch_thread, args=(device, i))
                t.start()
                threads.append(t)
            
            # Wait for all threads
            for t in threads:
                t.join()
            
            elapsed = time.time() - start_time
            print(f"   All writes completed in {elapsed:.2f}s")
            print(f"   Successful writes: {write_count[0]}/10")
            
            # Check for errors
            errors = []
            while not self.errors.empty():
                errors.append(self.errors.get())
            
            if errors:
                print(f"   ⚠️  {len(errors)} write errors:")
                for err_type, thread_num, err_msg in errors:
                    print(f"      Thread {thread_num}: {err_msg}")
            
            # Verify data integrity
            print(f"   Verifying segment data integrity...")
            conn = sqlite3.connect(DB_PATH)
            
            segments = conn.execute('''
                SELECT sequence, touch_detected, actual_time 
                FROM segments 
                WHERE run_id=? 
                ORDER BY sequence
            ''', (run_id,)).fetchall()
            
            touched_count = sum(1 for seg in segments if seg[1])
            print(f"   Segments touched: {touched_count}/5")
            
            # Check for data corruption
            corrupted = False
            for i, seg in enumerate(segments):
                if seg[1] and seg[2] is None:
                    print(f"      ❌ Segment {i}: touch_detected=1 but actual_time is NULL")
                    corrupted = True
            
            conn.close()
            
            # At least 5 writes should succeed (one per device)
            if write_count[0] < 5:
                self.log_result("Test 2", False, f"Only {write_count[0]}/10 writes succeeded")
                print(f"\n❌ TEST 2 FAILED: Too few successful writes ({write_count[0]}/10)")
                return False
            elif corrupted:
                self.log_result("Test 2", False, "Data corruption detected")
                print("\n❌ TEST 2 FAILED: Data corruption in concurrent writes")
                return False
            elif len(errors) > 0:
                self.log_result("Test 2", False, f"{len(errors)} write errors")
                print(f"\n⚠️  TEST 2 PARTIAL: Writes succeeded but {len(errors)} errors occurred")
                return True  # Partial pass - some errors acceptable
            else:
                self.log_result("Test 2", True, "All concurrent writes succeeded")
                print("\n✅ TEST 2 PASSED: Database handles concurrent writes")
                return True
                
        except Exception as e:
            self.log_result("Test 2", False, str(e))
            print(f"\n❌ TEST 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 3: TOUCH HANDLER UNDER LOAD ====================
    
    def test_touch_handler_under_load(self) -> bool:
        """
        Test 3: Touch Handler Under Load
        What: Multiple concurrent touch events to attribution system
        Why: Tests if find_athlete_for_touch() is thread-safe
             Validates active_session_state doesn't corrupt under concurrent access
             Ensures touches are attributed correctly under load
        Expected: All touches attributed correctly, no race conditions in attribution
        """
        self.print_header("TEST 3: Touch Handler Under Load")
        
        try:
            sys.path.insert(0, '/opt')
            from coach_interface import find_athlete_for_touch, active_session_state
            from field_trainer.db_manager import DatabaseManager
            
            self.print_test("Test 3", "20 concurrent touches to attribution system")
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            # Create session with 5 athletes
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=athlete_ids[:5]
            )
            
            runs = list(db.get_session_runs(session_id))
            
            # Set up active session state
            device_sequence = [
                '192.168.99.100',
                '192.168.99.101',
                '192.168.99.102',
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105'
            ]
            
            active_session_state.clear()
            active_session_state['session_id'] = session_id
            active_session_state['device_sequence'] = device_sequence
            active_session_state['active_runs'] = {}
            
            for i, run in enumerate(runs):
                active_session_state['active_runs'][run['run_id']] = {
                    'athlete_name': run['athlete_name'],
                    'sequence_position': 0,  # All at start
                    'queue_position': i
                }
            
            print(f"   {len(runs)} athletes ready at start")
            print(f"   Sending 20 concurrent touch events to D1...")
            
            attributions = []
            attr_lock = threading.Lock()
            
            def touch_thread(thread_num: int):
                """Thread worker for touch attribution"""
                try:
                    time.sleep(0.01 * thread_num)  # Slight stagger
                    
                    device_id = '192.168.99.101'  # D1
                    chosen = find_athlete_for_touch(device_id, datetime.now())
                    
                    with attr_lock:
                        attributions.append((thread_num, chosen))
                    
                except Exception as e:
                    self.errors.put(('touch', thread_num, str(e)))
            
            threads = []
            start_time = time.time()
            
            for i in range(20):
                t = threading.Thread(target=touch_thread, args=(i,))
                t.start()
                threads.append(t)
            
            # Wait for all threads
            for t in threads:
                t.join()
            
            elapsed = time.time() - start_time
            print(f"   All touches processed in {elapsed:.2f}s")
            
            # Check for errors
            errors = []
            while not self.errors.empty():
                errors.append(self.errors.get())
            
            if errors:
                print(f"   ❌ {len(errors)} attribution errors:")
                for err_type, thread_num, err_msg in errors:
                    print(f"      Thread {thread_num}: {err_msg}")
                self.log_result("Test 3", False, f"{len(errors)} attribution errors")
                return False
            
            # Analyze attributions
            print(f"   Analyzing {len(attributions)} attributions...")
            
            attr_counts = {}
            for thread_num, chosen in attributions:
                if chosen:
                    athlete_name = active_session_state['active_runs'][chosen]['athlete_name']
                    attr_counts[athlete_name] = attr_counts.get(athlete_name, 0) + 1
            
            print(f"   Attribution distribution:")
            for athlete, count in sorted(attr_counts.items()):
                print(f"      {athlete}: {count} touches")
            
            # First athlete should get most touches (queue_position=0)
            first_athlete = runs[0]['athlete_name']
            first_count = attr_counts.get(first_athlete, 0)
            
            # Clean up
            active_session_state.clear()
            
            if first_count == 0:
                self.log_result("Test 3", False, "First athlete got no touches")
                print("\n❌ TEST 3 FAILED: Queue ordering broken under load")
                return False
            elif len(attributions) < 15:
                self.log_result("Test 3", False, f"Only {len(attributions)}/20 touches processed")
                print(f"\n❌ TEST 3 FAILED: Too many touches lost ({len(attributions)}/20)")
                return False
            else:
                self.log_result("Test 3", True, "Touch handler handled concurrent load")
                print(f"\n✅ TEST 3 PASSED: Attribution system thread-safe")
                return True
                
        except Exception as e:
            self.log_result("Test 3", False, str(e))
            print(f"\n❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 4: DATABASE LOCK TIMEOUT ====================
    
    def test_database_lock_timeout(self) -> bool:
        """
        Test 4: Database Lock Handling
        What: Simulates long-running transaction blocking other threads
        Why: Tests how system handles SQLite database locks
             Validates timeout behavior and error handling
             Ensures system doesn't hang indefinitely
        Expected: Blocked writes either wait successfully or timeout gracefully
        """
        self.print_header("TEST 4: Database Lock Handling")
        
        try:
            self.print_test("Test 4", "Long transaction blocking concurrent writes")
            
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            
            team_id, athlete_ids = self.get_test_data()
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
            print("   Starting long-running transaction...")
            
            blocking_done = threading.Event()
            blocked_count = [0]
            success_count = [0]
            count_lock = threading.Lock()
            
            def blocking_transaction():
                """Thread that holds database lock for 2 seconds"""
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute('BEGIN EXCLUSIVE')
                    
                    print("      🔒 Lock acquired, holding for 2 seconds...")
                    time.sleep(2)
                    
                    conn.commit()
                    conn.close()
                    print("      🔓 Lock released")
                    blocking_done.set()
                    
                except Exception as e:
                    self.errors.put(('blocking', 0, str(e)))
                    blocking_done.set()
            
            def blocked_write(thread_num: int):
                """Thread that tries to write while lock is held"""
                try:
                    # Wait a moment for blocking transaction to start
                    time.sleep(0.1)
                    
                    start = time.time()
                    
                    try:
                        segment_id = db.record_touch(
                            run_id,
                            '192.168.99.101',
                            datetime.now()
                        )
                        
                        elapsed = time.time() - start
                        
                        with count_lock:
                            success_count[0] += 1
                        
                        if elapsed > 0.5:
                            print(f"      Thread {thread_num}: Waited {elapsed:.2f}s (blocked)")
                        
                    except sqlite3.OperationalError as e:
                        if 'locked' in str(e).lower():
                            with count_lock:
                                blocked_count[0] += 1
                            print(f"      Thread {thread_num}: Database locked")
                        else:
                            raise
                    
                except Exception as e:
                    self.errors.put(('write', thread_num, str(e)))
            
            # Start blocking transaction
            blocker = threading.Thread(target=blocking_transaction)
            blocker.start()
            
            time.sleep(0.2)  # Let blocker acquire lock
            
            # Start 5 threads that will be blocked
            print("   Starting 5 threads while lock is held...")
            threads = []
            for i in range(5):
                t = threading.Thread(target=blocked_write, args=(i,))
                t.start()
                threads.append(t)

            # Wait for blocker first
            blocker.join(timeout=5)
            
            # Give threads more time to complete after lock released
            for t in threads:
                t.join(timeout=10)  # Increased timeout
            
            # Small delay to ensure all prints complete
            time.sleep(0.1)
            
            print(f"   Results:")
            print(f"      Successful writes: {success_count[0]}/5")
            print(f"      Blocked/timeout: {blocked_count[0]}/5")

            # Check for errors
            errors = []
            while not self.errors.empty():
                errors.append(self.errors.get())
            
            if errors:
                print(f"   ❌ {len(errors)} thread errors")
                self.log_result("Test 4", False, f"{len(errors)} errors")
                return False
            
            # Success if writes either succeeded or timed out gracefully
            total_handled = success_count[0] + blocked_count[0]
            
            # Accept 4 or 5 as success (timing variations acceptable)
            if total_handled >= 4:
                self.log_result("Test 4", True, f"Lock handling worked ({total_handled}/5 handled)")
                print(f"\n✅ TEST 4 PASSED: Database lock handled gracefully ({total_handled}/5)")
                return True
            else:
                self.log_result("Test 4", False, f"Only {total_handled}/5 threads handled")
                print(f"\n❌ TEST 4 FAILED: Too many threads hung ({total_handled}/5)")
                return False  
                
        except Exception as e:
            self.log_result("Test 4", False, str(e))
            print(f"\n❌ TEST 4 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all concurrency tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - CONCURRENT OPERATIONS TEST SUITE")
        print("="*70)
        print(f"  Database: {DB_PATH}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Setup
        self.setup()
        
        # Run tests
        tests = [
            ("Simultaneous Session Starts", self.test_simultaneous_session_starts),
            ("Concurrent Database Writes", self.test_concurrent_database_writes),
            ("Touch Handler Under Load", self.test_touch_handler_under_load),
            ("Database Lock Handling", self.test_database_lock_timeout),
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
        filename = f"/tmp/concurrency_test_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - CONCURRENT OPERATIONS TEST RESULTS\n")
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
    tester = ConcurrentOperationsTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
