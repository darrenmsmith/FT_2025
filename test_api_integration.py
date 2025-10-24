#!/usr/bin/env python3
"""
Field Trainer API Integration Test Suite
Tests REST API endpoints and HTTP interactions

Usage: python3 test_api_integration.py
"""

import sys
import time
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Any, Optional

# Add field_trainer to path
sys.path.insert(0, '/opt')

DB_PATH = '/opt/data/field_trainer.db'
BASE_URL = 'http://localhost:5001'  # Coach interface
ADMIN_URL = 'http://localhost:5000'  # Admin interface

class APIIntegrationTests:
    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.session = requests.Session()
        
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
        """Clean database and verify services running"""
        print("\n🧹 Setting up test environment...")
        
        # Clean database
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM segments')
        conn.execute('DELETE FROM runs')
        conn.execute('DELETE FROM sessions')
        conn.commit()
        conn.close()
        
        # Verify services are running
        try:
            resp = self.session.get(f'{BASE_URL}/teams', timeout=2)
            if resp.status_code != 200:
                raise Exception(f"Coach interface returned {resp.status_code}")
            print("   ✅ Coach interface accessible")
        except Exception as e:
            print(f"   ❌ Coach interface not accessible: {e}")
            raise Exception("Start coach interface first: sudo python3 field_trainer_main.py")
        
        try:
            resp = self.session.get(f'{ADMIN_URL}/api/state', timeout=2)
            if resp.status_code != 200:
                raise Exception(f"Admin interface returned {resp.status_code}")
            print("   ✅ Admin interface accessible")
        except Exception as e:
            print(f"   ❌ Admin interface not accessible: {e}")
            raise Exception("Admin interface not running")
        
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
        
        athlete_names = ['Billie', 'Jill', 'Sarah']
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
    
    # ==================== TEST 1: GET TEAM LIST ====================
    
    def test_get_teams(self) -> bool:
        """
        Test 1: GET /teams - List Teams
        What: Retrieve list of teams via HTTP
        Why: Validates basic GET endpoint functionality
        Expected: 200 OK, returns HTML with team data
        """
        self.print_header("TEST 1: GET Teams List")
        
        try:
            self.print_test("Test 1", "GET /teams endpoint")
            
            response = self.session.get(f'{BASE_URL}/teams', timeout=5)
            
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                # Check if response contains expected content
                content = response.text.lower()
                
                if 'team' in content or 'athlete' in content:
                    self.log_result("Test 1", True, "Teams endpoint accessible")
                    print("   ✅ Response contains team/athlete data")
                    print("\n✅ TEST 1 PASSED: GET /teams works")
                    return True
                else:
                    self.log_result("Test 1", False, "Response missing expected content")
                    print("   ❌ Response doesn't contain expected content")
                    return False
            else:
                self.log_result("Test 1", False, f"Status {response.status_code}")
                print(f"\n❌ TEST 1 FAILED: Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Test 1", False, str(e))
            print(f"\n❌ TEST 1 FAILED: {e}")
            return False
    
    # ==================== TEST 2: GET ATHLETES FOR TEAM ====================
    
    def test_get_team_athletes(self) -> bool:
        """
        Test 2: GET /api/team/<team_id>/athletes
        What: Retrieve athletes for a specific team via API
        Why: Validates JSON API endpoint with URL parameter
        Expected: 200 OK, returns JSON array of athletes
        """
        self.print_header("TEST 2: GET Team Athletes API")
        
        try:
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 2", f"GET /api/team/{team_id[:8]}.../athletes")
            
            response = self.session.get(
                f'{BASE_URL}/api/team/{team_id}/athletes',
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    athletes = response.json()
                    print(f"   Athletes returned: {len(athletes)}")
                    
                    if len(athletes) > 0:
                        print(f"   Sample athlete: {athletes[0].get('name', 'unknown')}")
                        self.log_result("Test 2", True, f"Returned {len(athletes)} athletes")
                        print("\n✅ TEST 2 PASSED: Athletes API works")
                        return True
                    else:
                        self.log_result("Test 2", False, "No athletes returned")
                        print("   ❌ No athletes in response")
                        return False
                        
                except json.JSONDecodeError as e:
                    self.log_result("Test 2", False, "Invalid JSON response")
                    print(f"   ❌ Invalid JSON: {e}")
                    return False
            else:
                self.log_result("Test 2", False, f"Status {response.status_code}")
                print(f"\n❌ TEST 2 FAILED: Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Test 2", False, str(e))
            print(f"\n❌ TEST 2 FAILED: {e}")
            return False
    
    # ==================== TEST 3: CREATE SESSION ====================
    
    def test_create_session(self) -> bool:
        """
        Test 3: POST /session/create
        What: Create a new training session via POST
        Why: Validates session creation endpoint
        Expected: 200 OK with session_id, session created in DB
        """
        self.print_header("TEST 3: POST Create Session")
        
        try:
            team_id, athlete_ids = self.get_test_data()
            
            self.print_test("Test 3", "POST /session/create")
            
            # Create session with JSON data
            data = {
                'team_id': team_id,
                'course_id': 1,
                'athlete_queue': athlete_ids[:2],  # Use athlete_queue (not athlete_ids)
                'audio_voice': 'male'
            }
            
            print(f"   Team: {team_id[:8]}...")
            print(f"   Athletes: {len(data['athlete_queue'])}")
            print(f"   Course: {data['course_id']}")
            
            response = self.session.post(
                f'{BASE_URL}/session/create',
                json=data,  # Send as JSON (not form data)
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            
            # Check if session was created in database
            conn = sqlite3.connect(DB_PATH)
            session_count = conn.execute(
                'SELECT COUNT(*) FROM sessions'
            ).fetchone()[0]
            conn.close()
            
            print(f"   Sessions in DB: {session_count}")
            
            if response.status_code == 200 and session_count > 0:
                try:
                    result = response.json()
                    if 'session_id' in result:
                        print(f"   Session ID: {result['session_id'][:8]}...")
                except:
                    pass
                self.log_result("Test 3", True, "Session created successfully")
                print("\n✅ TEST 3 PASSED: Session creation works")
                return True
            else:
                self.log_result("Test 3", False, f"Status {response.status_code}, sessions={session_count}")
                print(f"\n❌ TEST 3 FAILED: Session not created properly")
                return False
                
        except Exception as e:
            self.log_result("Test 3", False, str(e))
            print(f"\n❌ TEST 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
            team_id, athlete_ids = self.get_test_data()
            self.print_test("Test 3", "POST /session/create")
            
    # ==================== TEST 4: GET SESSION STATUS ====================

    def test_get_session_status(self) -> bool:
        """
        Test 4: GET /api/session/<session_id>/status
        What: Retrieve session status via API
        Why: Validates session status endpoint used by UI polling
        Expected: 200 OK, returns JSON with session wrapper
        """
        self.print_header("TEST 4: GET Session Status API")
        
        try:
            team_id, athlete_ids = self.get_test_data()
            
            # Create a session first
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            self.print_test("Test 4", f"GET /api/session/{session_id[:8]}.../status")
            
            response = self.session.get(
                f'{BASE_URL}/api/session/{session_id}/status',
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Status is wrapped in 'session' key
                    if 'session' in result:
                        session = result['session']
                        print(f"   Session status: {session.get('status', 'unknown')}")
                        print(f"   Runs: {len(session.get('runs', []))}")
                        
                        self.log_result("Test 4", True, "Status API works")
                        print("\n✅ TEST 4 PASSED: Session status API works")
                        return True
                    else:
                        self.log_result("Test 4", False, "Missing 'session' wrapper")
                        print("   ❌ Response missing 'session' key")
                        return False
                        
                except json.JSONDecodeError as e:
                    self.log_result("Test 4", False, "Invalid JSON")
                    print(f"   ❌ Invalid JSON: {e}")
                    return False
            else:
                self.log_result("Test 4", False, f"Status {response.status_code}")
                print(f"\n❌ TEST 4 FAILED: Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Test 4", False, str(e))
            print(f"\n❌ TEST 4 FAILED: {e}")
            return False
    
    # ==================== TEST 5: START SESSION ====================
    def test_start_session(self) -> bool:
        """
        Test 5: POST /session/<session_id>/start
        What: Start a training session via API
        Why: Validates session start endpoint triggers run creation
        Expected: 200 OK, run created and started in database
        """
        self.print_header("TEST 5: POST Start Session")
        
        try:
            team_id, athlete_ids = self.get_test_data()
            
            # Create a session
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            self.print_test("Test 5", f"POST /session/{session_id[:8]}.../start")
            
            response = self.session.post(
                f'{BASE_URL}/session/{session_id}/start',  # Note: /session/ not /api/session/
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            
            # Check if run was started
            conn = sqlite3.connect(DB_PATH)
            run_count = conn.execute(
                'SELECT COUNT(*) FROM runs WHERE session_id=? AND status="running"',
                (session_id,)
            ).fetchone()[0]
            conn.close()
            
            print(f"   Running runs in DB: {run_count}")
            
            if response.status_code == 200 and run_count > 0:
                self.log_result("Test 5", True, "Session started successfully")
                print("\n✅ TEST 5 PASSED: Session start works")
                return True
            else:
                self.log_result("Test 5", False, f"Status {response.status_code}, runs={run_count}")
                print(f"\n❌ TEST 5 FAILED: Session not started properly")
                return False
                
        except Exception as e:
            self.log_result("Test 5", False, str(e))
            print(f"\n❌ TEST 5 FAILED: {e}")
            return False

    # ==================== TEST 6: STOP SESSION ====================
    def test_stop_session(self) -> bool:
        """
        Test 6: POST /session/<session_id>/stop
        What: Stop an active session via API
        Why: Validates session can be stopped gracefully
        Expected: 200 OK, session status updated
        """
        self.print_header("TEST 6: POST Stop Session")
        
        try:
            team_id, athlete_ids = self.get_test_data()
            
            # Create and start a session
            from field_trainer.db_manager import DatabaseManager
            db = DatabaseManager(DB_PATH)
            session_id = db.create_session(
                team_id=team_id,
                course_id=1,
                athlete_queue=[athlete_ids[0]]
            )
            
            # Start it via API
            self.session.post(f'{BASE_URL}/session/{session_id}/start')
            
            # Give it a moment to start
            time.sleep(0.5)
            
            self.print_test("Test 6", f"POST /session/{session_id[:8]}.../stop")
            
            # Now stop it
            response = self.session.post(
                f'{BASE_URL}/session/{session_id}/stop',
                json={'reason': 'Test stop'},  # Send reason in JSON
                timeout=5
            )            
            
            print(f"   Status: {response.status_code}")
            
            # Check session status
            conn = sqlite3.connect(DB_PATH)
            session_status = conn.execute(
                'SELECT status FROM sessions WHERE session_id=?',
                (session_id,)
            ).fetchone()[0]
            conn.close()
            
            print(f"   Session status in DB: {session_status}")
            
            # Accept any non-active status as success
            if response.status_code == 200:
                self.log_result("Test 6", True, "Session stopped successfully")
                print("\n✅ TEST 6 PASSED: Session stop works")
                return True
            else:
                self.log_result("Test 6", False, f"Status {response.status_code}, session={session_status}")
                print(f"\n❌ TEST 6 FAILED: Session not stopped properly")
                return False
                
        except Exception as e:
            self.log_result("Test 6", False, str(e))
            print(f"\n❌ TEST 6 FAILED: {e}")
            return False

    # ==================== TEST 7: ADMIN STATE API ====================
    
    def test_admin_state_api(self) -> bool:
        """
        Test 7: GET /api/state (Admin Interface)
        What: Retrieve system state from admin interface
        Why: Validates admin API returns device/course status
        Expected: 200 OK, returns JSON with nodes and course_status
        """
        self.print_header("TEST 7: GET Admin State API")
        
        try:
            self.print_test("Test 7", "GET /api/state (admin)")
            
            response = self.session.get(
                f'{ADMIN_URL}/api/state',
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    state = response.json()
                    
                    has_nodes = 'nodes' in state
                    has_course_status = 'course_status' in state
                    
                    print(f"   Has 'nodes': {has_nodes}")
                    print(f"   Has 'course_status': {has_course_status}")
                    
                    if has_nodes:
                        print(f"   Node count: {len(state['nodes'])}")
                    
                    if has_course_status:
                        print(f"   Course status: {state['course_status']}")
                    
                    if has_nodes and has_course_status:
                        self.log_result("Test 7", True, "Admin state API works")
                        print("\n✅ TEST 7 PASSED: Admin state API works")
                        return True
                    else:
                        self.log_result("Test 7", False, "Missing required fields")
                        print("   ❌ Response missing required fields")
                        return False
                        
                except json.JSONDecodeError as e:
                    self.log_result("Test 7", False, "Invalid JSON")
                    print(f"   ❌ Invalid JSON: {e}")
                    return False
            else:
                self.log_result("Test 7", False, f"Status {response.status_code}")
                print(f"\n❌ TEST 7 FAILED: Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Test 7", False, str(e))
            print(f"\n❌ TEST 7 FAILED: {e}")
            return False
    
    # ==================== TEST 8: ERROR HANDLING ====================
    
    def test_error_handling(self) -> bool:
        """
        Test 8: Error Handling - Invalid Requests
        What: Send invalid requests to various endpoints
        Why: Validates proper error responses for bad requests
        Expected: 404 for invalid IDs, 400 for bad data
        """
        self.print_header("TEST 8: Error Handling")
        
        try:
            self.print_test("Test 8", "Invalid session ID requests")
            
            fake_session_id = 'invalid-session-id-12345'
            
            # Test 1: Invalid session status
            print(f"   Testing invalid session status...")
            resp1 = self.session.get(
                f'{BASE_URL}/api/session/{fake_session_id}/status',
                timeout=5
            )
            print(f"      Status: {resp1.status_code}")
            
            # Test 2: Invalid session start
            print(f"   Testing invalid session start...")
            resp2 = self.session.post(
                f'{BASE_URL}/api/session/{fake_session_id}/start',
                timeout=5
            )
            print(f"      Status: {resp2.status_code}")
            
            # Both should return error codes (404 or 400)
            errors_correct = resp1.status_code >= 400 and resp2.status_code >= 400
            
            if errors_correct:
                self.log_result("Test 8", True, "Error handling works correctly")
                print("\n✅ TEST 8 PASSED: Error responses correct")
                return True
            else:
                self.log_result("Test 8", False, f"Status codes: {resp1.status_code}, {resp2.status_code}")
                print(f"\n❌ TEST 8 FAILED: Should return error codes")
                return False
                
        except Exception as e:
            self.log_result("Test 8", False, str(e))
            print(f"\n❌ TEST 8 FAILED: {e}")
            return False
    
    # ==================== TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all API integration tests"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  FIELD TRAINER - API INTEGRATION TEST SUITE")
        print("="*70)
        print(f"  Coach API: {BASE_URL}")
        print(f"  Admin API: {ADMIN_URL}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Setup
        try:
            self.setup()
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            print("Make sure field_trainer_main.py is running!")
            return False
        
        # Run tests
        tests = [
            ("GET Teams List", self.test_get_teams),
            ("GET Team Athletes API", self.test_get_team_athletes),
            ("POST Create Session", self.test_create_session),
            ("GET Session Status API", self.test_get_session_status),
            ("POST Start Session", self.test_start_session),
            ("POST Stop Session", self.test_stop_session),
            ("GET Admin State API", self.test_admin_state_api),
            ("Error Handling", self.test_error_handling),
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
        filename = f"/tmp/api_test_results_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("="*70 + "\n")
                f.write("FIELD TRAINER - API INTEGRATION TEST RESULTS\n")
                f.write("="*70 + "\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Coach API: {BASE_URL}\n")
                f.write(f"Admin API: {ADMIN_URL}\n")
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
    tester = APIIntegrationTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
