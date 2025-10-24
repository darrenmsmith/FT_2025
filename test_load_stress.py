#!/usr/bin/env python3
"""
Field Trainer Load & Stress Test Suite
Tests performance, scalability, and system limits

Usage: python3 test_load_stress.py
"""

import sys
import time
import sqlite3
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, List

# Add field_trainer to path
sys.path.insert(0, '/opt')

DB_PATH = '/opt/data/field_trainer.db'

class LoadStressTests:
    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.process = None
        
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
    
    def get_memory_usage(self) -> float:
        """Get current process memory usage in MB"""
        if self.process is None:
            # Try to find field_trainer_main process
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and 'field_trainer_main.py' in ' '.join(cmdline):
                        self.process = psutil.Process(proc.info['pid'])
                        break
                except:
                    continue
        
        if self.process:
            try:
                mem_info = self.process.memory_info()
                return mem_info.rss / 1024 / 1024  # Convert to MB
            except:
                return 0.0
        return 0.0
    
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
        
        # Get baseline memory
        initial_mem = self.get_memory_usage()
        if initial_mem > 0:
            print(f"   📊 Baseline memory: {initial_mem:.1f} MB")
    
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
        
        # Get up to 10 athletes for load testing
        athletes = conn.execute(
            'SELECT athlete_id, name FROM athletes LIMIT 10'
        ).fetchall()
        conn.close()
        
        if not athletes:
            raise Exception("No athletes found")
        
        athlete_ids = [a[0] for a in athletes]
        return team_id, athlete_ids
    
    # ==================== TEST 1: 10 SIMULTANEOUS ATHLETES ====================
    
    def test_10_simultaneous_athletes(self) -> bool:
        """
        Test 1: 10 Athletes Completing Simultaneously
        What: Create session with 10 athletes, simulate all completing course
        Why: Tests system handles maximum expected concurrent load
        Expected: All 10 runs tracked correctly, no performance degradation
        """
        self.print_header("TEST 1: 10 Simultaneous Athletes")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state, find_athlete_for_touch
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            athlete_count = min(10, len(athlete_ids))
            
            self.print_test("Test 1", f"Creating session with {athlete_count} athletes")
            
            mem_start = self.get_memory_usage()
            time_start = time.time()
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=athlete_ids[:athlete_count]
            )
            
            print(f"   Session created: {session_id[:8]}...")
            
            # Get all runs
            runs = list(db.get_session_runs(session_id))
            print(f"   Runs created: {len(runs)}")
            
            # Start all runs and create segments
            for run in runs:
                db.start_run(run['run_id'])
                db.create_segments_for_run(run['run_id'], 1)
            
            print(f"   All runs started with segments")
            
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
            active_session_state['active_runs'] = {}
            
            for i, run in enumerate(runs):
                active_session_state['active_runs'][run['run_id']] = {
                    'athlete_name': run['athlete_name'],
                    'sequence_position': 0,
                    'queue_position': i
                }
            
            print(f"   Simulating {athlete_count} athletes completing course...")
            
            # Simulate all athletes completing sequentially
            base_time = datetime.now()
            touch_count = 0
            
            for device_idx in range(1, 6):  # D1 through D5
                device_id = device_sequence[device_idx]
                
                # Each athlete touches this device
                for i, run in enumerate(runs):
                    touch_time = base_time + timedelta(seconds=touch_count)
                    
                    chosen = find_athlete_for_touch(device_id, touch_time)
                    if chosen:
                        db.record_touch(chosen, device_id, touch_time)
                        # Update position
                        if chosen in active_session_state['active_runs']:
                            active_session_state['active_runs'][chosen]['sequence_position'] = device_idx
                        touch_count += 1
            
            active_session_state.clear()
            
            time_elapsed = time.time() - time_start
            mem_end = self.get_memory_usage()
            mem_delta = mem_end - mem_start if mem_start > 0 else 0
            
            print(f"\n   Performance Metrics:")
            print(f"      Total time: {time_elapsed:.2f}s")
            print(f"      Touches processed: {touch_count}")
            print(f"      Avg time per touch: {(time_elapsed/touch_count)*1000:.1f}ms")
            if mem_start > 0:
                print(f"      Memory delta: {mem_delta:+.1f} MB")
            
            # Verify all runs completed
            conn = sqlite3.connect(DB_PATH)
            
            completed_count = 0
            total_segments = 0
            
            for run in runs:
                segments = conn.execute('''
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN touch_detected=1 THEN 1 ELSE 0 END) as touched
                    FROM segments
                    WHERE run_id=?
                ''', (run['run_id'],)).fetchone()
                
                total_segments += segments[0]
                if segments[1] == 5:  # All 5 segments touched
                    completed_count += 1
            
            conn.close()
            
            print(f"\n   Results:")
            print(f"      Athletes completed: {completed_count}/{athlete_count}")
            print(f"      Total segments: {total_segments}")
            
            # Success if all athletes completed and performance acceptable
            if completed_count == athlete_count and time_elapsed < 5.0:
                self.log_result("Test 1", True, f"{athlete_count} athletes, {time_elapsed:.2f}s")
                print(f"\n✅ TEST 1 PASSED: {athlete_count} athletes handled successfully")
                return True
            else:
                self.log_result("Test 1", False, f"Only {completed_count}/{athlete_count} completed")
                print(f"\n❌ TEST 1 FAILED: Performance or completion issues")
                return False
                
        except Exception as e:
            self.log_result("Test 1", False, str(e))
            print(f"\n❌ TEST 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 2: MARATHON SESSION ====================
    
    def test_marathon_session(self) -> bool:
        """
        Test 2: Marathon Session - 100+ Touches
        What: Single athlete, 20 complete runs through course (100 touches)
        Why: Tests sustained performance and memory stability
        Expected: Consistent performance, no memory leaks
        """
        self.print_header("TEST 2: Marathon Session")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state, find_athlete_for_touch
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 2", "Single athlete, 20 complete runs (100 touches)")
            
            mem_start = self.get_memory_usage()
            time_start = time.time()
            
            # Create session
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            
            # Start run
            db.start_run(run_id)
            db.create_segments_for_run(run_id, 1)
            
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
                    'athlete_name': runs[0]['athlete_name'],
                    'sequence_position': 0,
                    'queue_position': 0
                }
            }
            
            print(f"   Processing 100 touches (20 complete runs)...")
            
            base_time = datetime.now()
            touch_times = []
            
            for run_num in range(20):
                if run_num % 5 == 0:
                    print(f"      Run {run_num}/20...")
                
                for device_idx in range(1, 6):
                    device_id = device_sequence[device_idx]
                    touch_time = base_time + timedelta(seconds=run_num * 25 + device_idx * 5)
                    
                    touch_start = time.time()
                    chosen = find_athlete_for_touch(device_id, touch_time)
                    if chosen:
                        db.record_touch(chosen, device_id, touch_time)
                        active_session_state['active_runs'][chosen]['sequence_position'] = device_idx
                    touch_elapsed = time.time() - touch_start
                    touch_times.append(touch_elapsed)
                
                # Reset position for next run
                active_session_state['active_runs'][run_id]['sequence_position'] = 0
            
            active_session_state.clear()
            
            time_elapsed = time.time() - time_start
            mem_end = self.get_memory_usage()
            mem_delta = mem_end - mem_start if mem_start > 0 else 0
            
            # Calculate performance metrics
            avg_touch_time = sum(touch_times) / len(touch_times)
            max_touch_time = max(touch_times)
            min_touch_time = min(touch_times)
            
            print(f"\n   Performance Metrics:")
            print(f"      Total time: {time_elapsed:.2f}s")
            print(f"      Total touches: {len(touch_times)}")
            print(f"      Avg touch time: {avg_touch_time*1000:.1f}ms")
            print(f"      Min touch time: {min_touch_time*1000:.1f}ms")
            print(f"      Max touch time: {max_touch_time*1000:.1f}ms")
            if mem_start > 0:
                print(f"      Memory delta: {mem_delta:+.1f} MB")
                print(f"      Memory growth: {(mem_delta/mem_start)*100:+.1f}%")
            
            # Check for performance degradation
            first_10 = sum(touch_times[:10]) / 10
            last_10 = sum(touch_times[-10:]) / 10
            degradation = ((last_10 - first_10) / first_10) * 100
            
            print(f"      First 10 avg: {first_10*1000:.1f}ms")
            print(f"      Last 10 avg: {last_10*1000:.1f}ms")
            print(f"      Performance change: {degradation:+.1f}%")
            
            # Success criteria: < 30% performance degradation (worse), < 50% memory growth
            # Negative degradation means improvement (faster), which is good!
            mem_growth_ok = mem_delta < (mem_start * 0.5) if mem_start > 0 else True
            perf_ok = degradation < 30  # Only fail if getting slower (positive degradation)
            
            if mem_growth_ok and perf_ok:
                self.log_result("Test 2", True, f"100 touches, {degradation:+.1f}% perf change")
                print(f"\n✅ TEST 2 PASSED: Marathon session stable")
                return True
            else:
                self.log_result("Test 2", False, f"Degradation {degradation:.1f}%, mem {mem_delta:.1f}MB")
                print(f"\n❌ TEST 2 FAILED: Performance degradation detected")
                return False
                
        except Exception as e:
            self.log_result("Test 2", False, str(e))
            print(f"\n❌ TEST 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 3: DATABASE PERFORMANCE ====================
    
    def test_database_performance(self) -> bool:
        """
        Test 3: Database Performance Under Load
        What: Create 50 sessions with runs and segments
        Why: Tests database query performance at scale
        Expected: Queries remain fast, no significant slowdown
        """
        self.print_header("TEST 3: Database Performance")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 3", "Create 50 sessions with segments")
            
            time_start = time.time()
            
            print(f"   Creating 50 sessions...")
            session_ids = []
            
            for i in range(50):
                if i % 10 == 0:
                    print(f"      Session {i}/50...")
                
                session_id = db.create_session(
                    team_id=team_id,
                    course_id=1,
                    athlete_queue=[athlete_ids[i % len(athlete_ids)]]
                )
                session_ids.append(session_id)
                
                # Start run and create segments
                runs = list(db.get_session_runs(session_id))
                db.start_run(runs[0]['run_id'])
                db.create_segments_for_run(runs[0]['run_id'], 1)
            
            create_time = time.time() - time_start
            print(f"   Creation complete: {create_time:.2f}s")
            
            # Measure query performance
            print(f"\n   Testing query performance...")
            
            query_times = []
            
            for session_id in session_ids[:10]:  # Test 10 queries
                query_start = time.time()
                
                # Complex query: get session with all runs and segments
                session = db.get_session(session_id)
                for run in session['runs']:
                    segments = db.get_run_segments(run['run_id'])
                
                query_elapsed = time.time() - query_start
                query_times.append(query_elapsed)
            
            avg_query_time = sum(query_times) / len(query_times)
            max_query_time = max(query_times)
            
            print(f"      Avg query time: {avg_query_time*1000:.1f}ms")
            print(f"      Max query time: {max_query_time*1000:.1f}ms")
            
            # Count total records
            conn = sqlite3.connect(DB_PATH)
            total_sessions = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
            total_runs = conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
            total_segments = conn.execute('SELECT COUNT(*) FROM segments').fetchone()[0]
            conn.close()
            
            print(f"\n   Database size:")
            print(f"      Sessions: {total_sessions}")
            print(f"      Runs: {total_runs}")
            print(f"      Segments: {total_segments}")
            
            # Success if query times reasonable (< 100ms avg)
            if avg_query_time < 0.1 and create_time < 30:
                self.log_result("Test 3", True, f"50 sessions, {avg_query_time*1000:.1f}ms avg query")
                print(f"\n✅ TEST 3 PASSED: Database performance acceptable")
                return True
            else:
                self.log_result("Test 3", False, f"Slow queries: {avg_query_time*1000:.1f}ms")
                print(f"\n❌ TEST 3 FAILED: Database too slow")
                return False
                
        except Exception as e:
            self.log_result("Test 3", False, str(e))
            print(f"\n❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 4: MEMORY STABILITY ====================
    
    def test_memory_stability(self) -> bool:
        """
        Test 4: Memory Stability Check
        What: Monitor memory usage over multiple operations
        Why: Detect memory leaks or excessive memory growth
        Expected: Memory stable, < 100MB total growth
        """
        self.print_header("TEST 4: Memory Stability")
        
        try:
            from field_trainer.db_manager import DatabaseManager
            from coach_interface import active_session_state
            
            db = DatabaseManager(DB_PATH)
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 4", "Memory usage over 20 session cycles")
            
            mem_baseline = self.get_memory_usage()
            
            if mem_baseline == 0:
                print("   ⚠️  Cannot measure memory (process not found)")
                print("   Skipping memory test")
                self.log_result("Test 4", True, "Memory test skipped")
                return True
            
            print(f"   Baseline memory: {mem_baseline:.1f} MB")
            
            memory_readings = [mem_baseline]
            
            print(f"   Running 20 session create/cleanup cycles...")
            
            for i in range(20):
                # Create session with active state
                session_id = db.create_session(
                    team_id=team_id,
                    course_id=1,
                    athlete_queue=athlete_ids[:3]
                )
                
                runs = list(db.get_session_runs(session_id))
                for run in runs:
                    db.start_run(run['run_id'])
                    db.create_segments_for_run(run['run_id'], 1)
                
                # Populate active state
                active_session_state['session_id'] = session_id
                active_session_state['active_runs'] = {
                    run['run_id']: {'athlete_name': run['athlete_name'], 'sequence_position': 0}
                    for run in runs
                }
                
                # Clear it
                active_session_state.clear()
                
                # Delete from database
                conn = sqlite3.connect(DB_PATH)
                conn.execute('DELETE FROM segments WHERE run_id IN (SELECT run_id FROM runs WHERE session_id=?)', (session_id,))
                conn.execute('DELETE FROM runs WHERE session_id=?', (session_id,))
                conn.execute('DELETE FROM sessions WHERE session_id=?', (session_id,))
                conn.commit()
                conn.close()
                
                # Measure memory every 5 cycles
                if (i + 1) % 5 == 0:
                    mem = self.get_memory_usage()
                    memory_readings.append(mem)
                    print(f"      Cycle {i+1}: {mem:.1f} MB")
            
            mem_final = self.get_memory_usage()
            memory_readings.append(mem_final)
            
            mem_growth = mem_final - mem_baseline
            mem_growth_pct = (mem_growth / mem_baseline) * 100
            
            print(f"\n   Memory Analysis:")
            print(f"      Baseline: {mem_baseline:.1f} MB")
            print(f"      Final: {mem_final:.1f} MB")
            print(f"      Growth: {mem_growth:+.1f} MB ({mem_growth_pct:+.1f}%)")
            print(f"      Max reading: {max(memory_readings):.1f} MB")
            
            # Success if memory growth < 100MB and < 50%
            if abs(mem_growth) < 100 and abs(mem_growth_pct) < 50:
                self.log_result("Test 4", True, f"Memory stable: {mem_growth:+.1f}MB")
                print(f"\n✅ TEST 4 PASSED: Memory stable")
                return True
            else:
                self.log_result("Test 4", False, f"Memory leak: {mem_growth:+.1f}MB")
                print(f"\n❌ TEST 4 FAILED: Excessive memory growth")
                return False
                
        except Exception as e:
            self.log_result("Test 4", False, str(e))
            print(f"\n❌ TEST 4 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all load and stress tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - LOAD & STRESS TEST SUITE")
        print("="*70)
        print(f"  Database: {DB_PATH}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Setup
        self.setup()
        
        # Run tests
        tests = [
            ("10 Simultaneous Athletes", self.test_10_simultaneous_athletes),
            ("Marathon Session", self.test_marathon_session),
            ("Database Performance", self.test_database_performance),
            ("Memory Stability", self.test_memory_stability),
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
        filename = f"/tmp/load_stress_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - LOAD & STRESS TEST RESULTS\n")
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
    tester = LoadStressTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
