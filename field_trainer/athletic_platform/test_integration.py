"""
Test Athletic Training Platform Integration
Run this to verify everything works before modifying coach_interface.py
"""

import sys
sys.path.insert(0, '/opt')
sys.path.insert(0, '/opt/field_trainer')
sys.path.insert(0, '/opt/field_trainer/athletic_platform')

from field_trainer.db_manager import DatabaseManager
from models_extended import ExtendedDatabaseManager
from bridge_layer import initialize_bridge


def test_database_setup():
    """Test 1: Verify extended tables exist"""
    print("\n" + "="*80)
    print("TEST 1: Database Setup")
    print("="*80)
    
    try:
        ext_db = ExtendedDatabaseManager('/opt/data/field_trainer.db')
        conn = ext_db.get_connection()
        cursor = conn.cursor()
        
        # Check for new tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND (
                name LIKE '%performance%' OR 
                name LIKE '%achievement%' OR 
                name LIKE '%personal_record%'
            )
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"✅ Found {len(tables)} extended tables:")
        for table in tables:
            print(f"   - {table}")
        
        return len(tables) >= 3
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bridge_initialization():
    """Test 2: Verify bridge can initialize"""
    print("\n" + "="*80)
    print("TEST 2: Bridge Initialization")
    print("="*80)
    
    try:
        db = DatabaseManager('/opt/data/field_trainer.db')
        perf_bridge, touch_bridge = initialize_bridge(db)
        
        print("✅ Performance bridge initialized")
        print("✅ Touch bridge initialized")
        print(f"   Course metrics configured: {len(perf_bridge.course_metrics)}")
        print(f"   Achievement criteria: {list(perf_bridge.achievement_criteria.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bridge initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simulated_run():
    """Test 3: Simulate a completed run"""
    print("\n" + "="*80)
    print("TEST 3: Simulated Run Processing")
    print("="*80)
    
    try:
        db = DatabaseManager('/opt/data/field_trainer.db')
        perf_bridge, touch_bridge = initialize_bridge(db)
        
        # Get a recent completed run - use context manager
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT run_id, athlete_id, total_time, status 
                FROM runs 
                WHERE status = 'completed' AND total_time IS NOT NULL
                ORDER BY started_at DESC
                LIMIT 1
            """)
            
            run = cursor.fetchone()
        
        if not run:
            print("⚠️  No completed runs found in database")
            print("   Create a test run in the coach interface first")
            return None
        
        run_id = run[0]
        print(f"\n📋 Found completed run: {run_id[:8]}...")
        print(f"   Athlete ID: {run[1][:8]}...")
        print(f"   Total Time: {run[2]:.3f}s")
        print(f"\n🔄 Processing with bridge...")
        
        # Process the run
        result = touch_bridge.on_run_completed(run_id)
        
        if result:
            print(f"\n✅ Run processed successfully!")
            print(f"   Metrics recorded: {result['metrics_recorded']}")
            print(f"   New PR: {result['is_new_pr']}")
            print(f"   Achievements: {len(result['achievements_awarded'])}")
            
            if result['achievements_awarded']:
                for achievement in result['achievements_awarded']:
                    print(f"      🏆 {achievement}")
            
            return True
        else:
            print("❌ Run processing returned no result")
            return False
        
    except Exception as e:
        print(f"❌ Simulated run test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_athlete_stats():
    """Test 4: Retrieve athlete statistics"""
    print("\n" + "="*80)
    print("TEST 4: Athlete Statistics Retrieval")
    print("="*80)
    
    try:
        db = DatabaseManager('/opt/data/field_trainer.db')
        ext_db = ExtendedDatabaseManager('/opt/data/field_trainer.db')
        perf_bridge, _ = initialize_bridge(db)
        
        # Get an athlete with performance data
        conn = ext_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT athlete_id 
            FROM performance_history 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("⚠️  No performance data found")
            print("   Run Test 3 first to create performance data")
            return None
        
        athlete_id = row[0]
        
        # Get stats
        stats = perf_bridge.get_athlete_dashboard_stats(athlete_id)
        
        print(f"✅ Retrieved stats for athlete: {athlete_id[:8]}...")
        print(f"\n📊 Statistics Summary:")
        print(f"   Total runs tracked: {stats['statistics']['total_runs']}")
        print(f"   Personal records: {stats['statistics']['total_prs']}")
        print(f"   Achievements earned: {stats['statistics']['total_achievements']}")
        
        if stats['personal_records']:
            print(f"\n🏆 Personal Records:")
            for pr in stats['personal_records'][:5]:
                print(f"   - {pr['metric_name']}: {pr['current_best']:.3f}s")
        
        if stats['achievements']:
            print(f"\n⭐ Achievements:")
            for achievement in stats['achievements'][:5]:
                print(f"   - {achievement['badge_name']}: {achievement['description']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Stats retrieval failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*80)
    print("ATHLETIC TRAINING PLATFORM - INTEGRATION TEST SUITE")
    print("="*80)
    
    results = {
        'Database Setup': test_database_setup(),
        'Bridge Initialization': test_bridge_initialization(),
        'Simulated Run': test_simulated_run(),
        'Athlete Statistics': test_athlete_stats()
    }
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0 and passed > 0:
        print("\n🎉 All tests passed! Ready to integrate with coach_interface.py")
        print("\nNext steps:")
        print("1. Add 3 imports to coach_interface.py")
        print("2. Initialize bridge after db = DatabaseManager(...)")
        print("3. Add touch_bridge.on_run_completed(run_id) in handle_touch_event_from_registry")
        return True
    else:
        print("\n⚠️  Some tests failed. Fix issues before integrating.")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
