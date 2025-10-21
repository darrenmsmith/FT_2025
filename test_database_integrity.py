#!/usr/bin/env python3
"""
Field Trainer Database Integrity Test Suite
Tests database constraints, foreign keys, and data integrity

Usage: python3 test_database_integrity.py
"""

import sys
import sqlite3
import time
from datetime import datetime, timedelta 
from typing import Tuple

# Add field_trainer to path
sys.path.insert(0, '/opt')

DB_PATH = '/opt/data/field_trainer.db'

class DatabaseIntegrityTests:
    def __init__(self):
        self.db_path = DB_PATH
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
    def get_test_data(self) -> tuple:
        """Get real team_id and athlete_ids from database"""
        conn = sqlite3.connect(self.db_path)
    
        # Get any team
        team = conn.execute('SELECT team_id FROM teams LIMIT 1').fetchone()
        if not team:
            conn.close()
            raise Exception("No teams in database. Create a team first.")
        team_id = team[0]
    
        # Get athlete IDs for Billie, Jill, Sarah, Bobby, Ella
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
            raise Exception("No athletes found. Create Billie, Jill, Sarah, Bobby, or Ella first.")
    
        return team_id, athlete_ids
        
    def print_header(self, title: str):
        """Print formatted test header"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
        
    def print_test(self, step: str):
        """Print test step"""
        print(f"\n{step}")
        
    def setup(self):
        """Clean database before tests"""
        print("\n🧹 Setting up test environment...")
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM segments')
        conn.execute('DELETE FROM runs')
        conn.execute('DELETE FROM sessions')
        conn.commit()
        conn.close()
        print("   ✅ Database cleaned")
        
    def teardown(self):
        """Cleanup after tests"""
        print("\n🧹 Cleaning up test data...")
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM segments WHERE 1=1')  # Clean test data
        conn.execute('DELETE FROM runs WHERE 1=1')
        conn.execute('DELETE FROM sessions WHERE 1=1')
        conn.commit()
        conn.close()
        print("   ✅ Cleanup complete")
    
    # ==================== TEST 1: DUPLICATE SEGMENT PREVENTION ====================
    def test_duplicate_segment_prevention(self) -> bool:
        """
        Test 1: Verify UNIQUE(run_id, sequence) constraint prevents duplicates
        """
        self.print_header("TEST 1: Duplicate Segment Prevention")
        
        try:
            # Enable foreign keys
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
            
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(self.db_path)
            conn = sqlite3.connect(self.db_path)
            
            # Get real test data
            self.print_test("Step 1: Getting test team and athletes...")
            team_id, athlete_ids = self.get_test_data()
            print(f"   Using team: {team_id[:8]}...")
            print(f"   Using athlete: {athlete_ids[0]}")
            
            # Create test session and run
            self.print_test("Step 2: Creating test session...")
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            print(f"   Created session: {session_id[:8]}...")
            print(f"   Created run: {run_id[:8]}...")
            
            # First segment creation
            self.print_test("Step 2: Creating segments (first time)...")
            db.create_segments_for_run(run_id, 1)
            
            count1 = conn.execute(
                'SELECT COUNT(*) FROM segments WHERE run_id=?',
                (run_id,)
            ).fetchone()[0]
            print(f"   Segments created: {count1}")
            
            if count1 != 5:
                self.log_result("Test 1", False, f"Expected 5 segments, got {count1}")
                return False
            
            # Second segment creation (should be prevented)
            self.print_test("Step 3: Attempting duplicate creation...")
            db.create_segments_for_run(run_id, 1)
            
            count2 = conn.execute(
                'SELECT COUNT(*) FROM segments WHERE run_id=?',
                (run_id,)
            ).fetchone()[0]
            print(f"   Segments after duplicate attempt: {count2}")
            
            if count2 != 5:
                self.log_result("Test 1", False, f"Duplicates created! Expected 5, got {count2}")
                return False
            
            # Direct SQL duplicate attempt (test UNIQUE constraint)
            self.print_test("Step 4: Testing UNIQUE constraint at database level...")
            duplicate_blocked = False
            try:
                conn.execute('''
                    INSERT INTO segments (run_id, from_device, to_device, sequence,
                                        expected_min_time, expected_max_time)
                    VALUES (?, '192.168.99.100', '192.168.99.101', 0, 0, 999)
                ''', (run_id,))
                conn.commit()
                print("   ❌ UNIQUE constraint FAILED to block duplicate!")
            except sqlite3.IntegrityError as e:
                if 'UNIQUE constraint failed' in str(e):
                    print(f"   ✅ UNIQUE constraint blocked duplicate: {e}")
                    duplicate_blocked = True
                else:
                    raise
            
            conn.close()
            
            if not duplicate_blocked:
                self.log_result("Test 1", False, "UNIQUE constraint not working")
                return False
            
            self.log_result("Test 1", True, "Duplicate prevention working correctly")
            print("\n✅ TEST 1 PASSED: Duplicate segments prevented")
            return True
            
        except Exception as e:
            self.log_result("Test 1", False, str(e))
            print(f"\n❌ TEST 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 2: FOREIGN KEY CASCADE ====================
    def test_foreign_key_cascades(self) -> bool:
        """
        Test 2: Verify foreign key cascades delete orphaned data
        """
        self.print_header("TEST 2: Foreign Key Cascade Deletion")
        
        try:
            # Enable foreign keys
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
            
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(self.db_path)
            conn = sqlite3.connect(self.db_path)
            
            # Get real test data
            self.print_test("Step 1: Getting test team and athletes...")
            team_id, athlete_ids = self.get_test_data()
            print(f"   Using team: {team_id[:8]}...")
            print(f"   Using athletes: {athlete_ids[:2]}")
            
            # Create test data
            self.print_test("Step 2: Creating test session with runs and segments...")
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=athlete_ids[:2]  # Use first 2 athletes
            )
            
            runs = list(db.get_session_runs(session_id))
            print(f"   Created session: {session_id[:8]}...")
            print(f"   Created {len(runs)} runs")
            
            # Create segments for both runs
            for run in runs:
                db.create_segments_for_run(run['run_id'], 1)
            
            # Count before deletion
            run_count_before = conn.execute(
                'SELECT COUNT(*) FROM runs WHERE session_id=?',
                (session_id,)
            ).fetchone()[0]
            
            segment_count_before = conn.execute('''
                SELECT COUNT(*) FROM segments 
                WHERE run_id IN (
                    SELECT run_id FROM runs WHERE session_id=?
                )
            ''', (session_id,)).fetchone()[0]
            
            print(f"   Runs before deletion: {run_count_before}")
            print(f"   Segments before deletion: {segment_count_before}")
     
            # Delete session (enable foreign keys on this connection!)
            self.print_test("Step 2: Deleting session (should cascade to runs and segments)...")
            conn.execute('PRAGMA foreign_keys = ON')  # <-- ADD THIS LINE
            conn.execute('DELETE FROM sessions WHERE session_id=?', (session_id,))
            conn.commit()
            print("   Session deleted")
       
            # Count after deletion
            self.print_test("Step 3: Checking for orphaned data...")
            run_count_after = conn.execute(
                'SELECT COUNT(*) FROM runs WHERE session_id=?',
                (session_id,)
            ).fetchone()[0]
            
            segment_count_after = conn.execute('''
                SELECT COUNT(*) FROM segments
                WHERE run_id IN (
                    SELECT run_id FROM runs WHERE session_id=?
                )
            ''', (session_id,)).fetchone()[0]
            
            print(f"   Runs after deletion: {run_count_after}")
            print(f"   Segments after deletion: {segment_count_after}")
            
            conn.close()
            
            if run_count_after > 0:
                self.log_result("Test 2", False, f"{run_count_after} orphaned runs found")
                print(f"\n❌ TEST 2 FAILED: Found {run_count_after} orphaned runs")
                return False
            
            if segment_count_after > 0:
                self.log_result("Test 2", False, f"{segment_count_after} orphaned segments found")
                print(f"\n❌ TEST 2 FAILED: Found {segment_count_after} orphaned segments")
                return False
            
            self.log_result("Test 2", True, "Foreign key cascades working correctly")
            print("\n✅ TEST 2 PASSED: No orphaned data, cascades working")
            return True
            
        except Exception as e:
            self.log_result("Test 2", False, str(e))
            print(f"\n❌ TEST 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    # ==================== TEST 3: DATA INTEGRITY CHECKS ====================
    
    def test_data_integrity(self) -> bool:
        """
        Test 3: Verify data integrity rules
        - Segment sequence numbers are unique per run
        - Segment times are non-negative
        - Run total_time matches sum of segments
        """
        self.print_header("TEST 3: Data Integrity Validation")
        
        try:
            # Enable foreign keys
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
            
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(self.db_path)
            conn = sqlite3.connect(self.db_path)
            
            # Get real test data
            self.print_test("Step 1: Getting test team and athletes...")
            team_id, athlete_ids = self.get_test_data()
            print(f"   Using team: {team_id[:8]}...")
            print(f"   Using athlete: {athlete_ids[0]}")
            
            # Create test session
            self.print_test("Step 2: Creating test session and populating with data...")
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]  # Use first athlete
            )
            runs = list(db.get_session_runs(session_id))
            run_id = runs[0]['run_id']
            
            # Start the run before recording touches
            db.start_run(run_id)
     
            db.create_segments_for_run(run_id, 1)
            print(f"   Created session with run: {run_id[:8]}...")
            
            # Simulate touches with realistic times
            self.print_test("Step 3: Simulating athlete touches with timing data...")
            devices = [
                '192.168.99.101',
                '192.168.99.102', 
                '192.168.99.103',
                '192.168.99.104',
                '192.168.99.105'
            ]
            
            # Get actual started_at from database to ensure positive times
            run_data = conn.execute(
                'SELECT started_at FROM runs WHERE run_id=?',
                (run_id,)
            ).fetchone()
            started_at = datetime.fromisoformat(run_data[0])
            
            segment_times = []

            for i, device in enumerate(devices):
                # Generate touches 5 seconds apart, starting 1 second after run start
                touch_time = started_at + timedelta(seconds=(i + 1) * 5.0)
                segment_id = db.record_touch(run_id, device, touch_time)

                if segment_id and i > 0:  # First touch is segment 0 completion
                    seg = conn.execute(
                        'SELECT actual_time FROM segments WHERE segment_id=?',
                        (segment_id,)
                    ).fetchone()
                    if seg and seg[0]:
                        segment_times.append(seg[0])
                        print(f"   Segment {i-1}: {seg[0]:.2f}s")
            
            # Check sequence uniqueness
            self.print_test("Step 4: Checking sequence number uniqueness...")
            duplicate_sequences = conn.execute('''
                SELECT run_id, sequence, COUNT(*) as cnt
                FROM segments
                WHERE run_id=?
                GROUP BY run_id, sequence
                HAVING COUNT(*) > 1
            ''', (run_id,)).fetchall()
            
            if duplicate_sequences:
                self.log_result("Test 3", False, f"Found duplicate sequences: {duplicate_sequences}")
                print(f"   ❌ Found duplicate sequences: {duplicate_sequences}")
                return False
            print("   ✅ All sequence numbers unique")
            
            # Check for negative times
            self.print_test("Step 5: Checking for negative times...")
            negative_times = conn.execute('''
                SELECT COUNT(*) FROM segments
                WHERE run_id=? AND actual_time < 0
            ''', (run_id,)).fetchone()[0]
            
            if negative_times > 0:
                self.log_result("Test 3", False, f"Found {negative_times} negative times")
                print(f"   ❌ Found {negative_times} segments with negative times")
                return False
            print("   ✅ No negative times found")
            
            # Check total time consistency
            self.print_test("Step 6: Validating total time calculation...")
            if segment_times:
                calculated_total = sum(segment_times)
                print(f"   Sum of segment times: {calculated_total:.2f}s")
                
                # Note: total_time may not be set yet, this is just a validation check
                run_data = conn.execute(
                    'SELECT total_time FROM runs WHERE run_id=?',
                    (run_id,)
                ).fetchone()
                
                if run_data[0] is not None:
                    db_total = run_data[0]
                    print(f"   Database total_time: {db_total:.2f}s")
                    
                    # Allow small floating point difference
                    if abs(calculated_total - db_total) > 0.1:
                        self.log_result("Test 3", False, f"Total time mismatch: {calculated_total} vs {db_total}")
                        print(f"   ❌ Total time mismatch!")
                        return False
                    print("   ✅ Total time matches segment sum")
                else:
                    print("   ⚠️  Run not completed yet (total_time not set)")
            
            conn.close()
            
            self.log_result("Test 3", True, "Data integrity checks passed")
            print("\n✅ TEST 3 PASSED: Data integrity validated")
            return True
            
        except Exception as e:
            self.log_result("Test 3", False, str(e))
            print(f"\n❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST 4: CONSTRAINT VALIDATION ====================
    
    def test_database_constraints(self) -> bool:
        """
        Test 4: Verify database schema constraints
        - NOT NULL constraints
        - CHECK constraints
        - Data types
        """
        self.print_header("TEST 4: Database Constraint Validation")
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Test NOT NULL constraints
            self.print_test("Step 1: Testing NOT NULL constraints...")
            
            # Try to insert segment with NULL required field
            try:
                conn.execute('''
                    INSERT INTO segments (run_id, from_device, to_device, sequence,
                                        expected_min_time, expected_max_time)
                    VALUES (NULL, '192.168.99.101', '192.168.99.102', 0, 0, 999)
                ''')
                conn.commit()
                print("   ❌ NOT NULL constraint failed (run_id accepted NULL)")
                self.log_result("Test 4", False, "NOT NULL constraint not working")
                return False
            except sqlite3.IntegrityError:
                print("   ✅ NOT NULL constraint working (run_id)")
                conn.rollback()
            
            # Test CHECK constraints
            self.print_test("Step 2: Testing CHECK constraints...")
            
            # Try to insert invalid alert_type
            try:
                conn.execute('''
                    INSERT INTO segments (run_id, from_device, to_device, sequence,
                                        expected_min_time, expected_max_time, alert_type)
                    VALUES ('test_run', '192.168.99.101', '192.168.99.102', 0, 
                           0, 999, 'invalid_alert_type')
                ''')
                conn.commit()
                print("   ❌ CHECK constraint failed (invalid alert_type accepted)")
                self.log_result("Test 4", False, "CHECK constraint not working")
                return False
            except sqlite3.IntegrityError:
                print("   ✅ CHECK constraint working (alert_type)")
                conn.rollback()
            
            # Verify schema
            self.print_test("Step 3: Verifying segments table schema...")
            schema = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='segments'"
            ).fetchone()[0]
            
            required_elements = [
                'UNIQUE(run_id, sequence)',
                'FOREIGN KEY',
                'CHECK'
            ]
            
            missing = []
            for element in required_elements:
                if element not in schema:
                    missing.append(element)
            
            if missing:
                print(f"   ❌ Missing schema elements: {missing}")
                self.log_result("Test 4", False, f"Schema incomplete: {missing}")
                return False
            
            print("   ✅ Schema contains all required constraints")
            
            conn.close()
            
            self.log_result("Test 4", True, "All constraints validated")
            print("\n✅ TEST 4 PASSED: Database constraints working")
            return True
            
        except Exception as e:
            self.log_result("Test 4", False, str(e))
            print(f"\n❌ TEST 4 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all database integrity tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - DATABASE INTEGRITY TEST SUITE")
        print("="*70)
        print(f"  Database: {self.db_path}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Setup
        self.setup()
        
        # Run tests
        tests = [
            ("Duplicate Segment Prevention", self.test_duplicate_segment_prevention),
            ("Foreign Key Cascades", self.test_foreign_key_cascades),
            ("Data Integrity", self.test_data_integrity),
            ("Database Constraints", self.test_database_constraints),
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
        
        # Save results to file
        self.save_results(passed, failed, elapsed)
    
    def save_results(self, passed: int, failed: int, elapsed: float):
        """Save test results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"/tmp/db_test_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - DATABASE INTEGRITY TEST RESULTS\n")
                f.write("="*70 + "\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Database: {self.db_path}\n")
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
    tester = DatabaseIntegrityTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
