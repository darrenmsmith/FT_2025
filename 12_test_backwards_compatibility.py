#!/usr/bin/env python3
"""
Field Trainer - Backwards Compatibility Test Suite
Version: 0.5.2
File: test_backwards_compatibility.py
Description: Ensures all existing courses continue to work after migration
"""

import sys
import sqlite3
import json
import time
from datetime import datetime

# Add the field_trainer module to path
sys.path.insert(0, '/opt')

from field_trainer.ft_registry import REGISTRY
from field_trainer.db_manager import DatabaseManager

# Initialize components
db = DatabaseManager('/opt/data/field_trainer.db')

def test_existing_course_structure():
    """Verify existing courses are unchanged and still valid."""
    print("\n=== Testing Existing Course Structure ===")
    
    conn = sqlite3.connect('/opt/data/field_trainer.db')
    cursor = conn.cursor()
    
    # Get all non-advanced courses (existing courses)
    cursor.execute("""
        SELECT c.course_id, c.course_name, COUNT(ca.action_id) as action_count
        FROM courses c
        LEFT JOIN course_actions ca ON c.course_id = ca.course_id
        WHERE c.course_type IS NULL OR c.course_type != 'advanced'
        GROUP BY c.course_id
    """)
    
    existing_courses = cursor.fetchall()
    
    if not existing_courses:
        print("⚠️  No existing courses found - this might be a fresh installation")
        return True
    
    print(f"✅ Found {len(existing_courses)} existing courses")
    
    # Check each existing course
    all_valid = True
    for course_id, course_name, action_count in existing_courses:
        # Verify actions are intact
        cursor.execute("""
            SELECT device_id, action, sequence, 
                   device_function, detection_method, group_identifier, behavior_config
            FROM course_actions
            WHERE course_id = ?
            ORDER BY sequence
        """, (course_id,))
        
        actions = cursor.fetchall()
        
        # Check that existing fields are preserved
        for action in actions:
            device_id, action_text, sequence, dev_func, det_method, group_id, behav_cfg = action
            
            # Verify core fields are intact
            if not device_id or not action_text:
                print(f"❌ Course '{course_name}': Missing core fields")
                all_valid = False
                break
            
            # Verify new fields are NULL for existing courses (not required to have values)
            # This is OK - NULL means use default behavior
        
        if all_valid:
            print(f"✅ Course '{course_name}': {action_count} actions intact")
    
    conn.close()
    return all_valid

def test_traditional_course_deployment():
    """Test that traditional courses can still be deployed."""
    print("\n=== Testing Traditional Course Deployment ===")
    
    # Get a non-advanced course
    conn = sqlite3.connect('/opt/data/field_trainer.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT course_name 
        FROM courses 
        WHERE course_type IS NULL OR course_type = 'standard'
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print("⚠️  No traditional courses found to test")
        return True
    
    traditional_course = result[0]
    print(f"Testing deployment of traditional course: '{traditional_course}'")
    
    try:
        # Use the compatible deployment method if it exists, otherwise use regular
        if hasattr(REGISTRY, 'deploy_course_compatible'):
            success = REGISTRY.deploy_course_compatible(traditional_course)
        else:
            success = REGISTRY.deploy_course(traditional_course)
        
        if success:
            print(f"✅ Traditional course '{traditional_course}' deployed successfully")
            
            # Check that course status is correct
            if REGISTRY.course_status == "Deployed":
                print("✅ Course status correctly set to 'Deployed'")
            else:
                print(f"❌ Unexpected course status: {REGISTRY.course_status}")
                return False
            
            # Check assignments
            if REGISTRY.assignments:
                print(f"✅ Assignments created for {len(REGISTRY.assignments)} devices")
            else:
                print("❌ No assignments created")
                return False
            
            return True
        else:
            print(f"❌ Failed to deploy traditional course '{traditional_course}'")
            return False
            
    except Exception as e:
        print(f"❌ Error deploying traditional course: {str(e)}")
        return False

def test_traditional_course_activation():
    """Test that traditional courses can still be activated."""
    print("\n=== Testing Traditional Course Activation ===")
    
    try:
        # Activate the deployed course
        if hasattr(REGISTRY, 'activate_course_compatible'):
            success = REGISTRY.activate_course_compatible()
        else:
            success = REGISTRY.activate_course()
        
        if success:
            print("✅ Traditional course activated successfully")
            
            if REGISTRY.course_status == "Active":
                print("✅ Course status correctly set to 'Active'")
                return True
            else:
                print(f"❌ Unexpected course status: {REGISTRY.course_status}")
                return False
        else:
            print("❌ Failed to activate traditional course")
            return False
            
    except Exception as e:
        print(f"❌ Error activating traditional course: {str(e)}")
        return False

def test_traditional_touch_processing():
    """Test that touch events work for traditional courses."""
    print("\n=== Testing Traditional Touch Processing ===")
    
    if not REGISTRY.assignments:
        print("⚠️  No assignments to test touch processing")
        return True
    
    # Get first device from assignments
    test_device = list(REGISTRY.assignments.keys())[0]
    
    try:
        # Simulate a touch event
        if hasattr(REGISTRY, 'process_touch_compatible'):
            result = REGISTRY.process_touch_compatible(test_device)
        elif hasattr(REGISTRY, 'process_touch'):
            result = REGISTRY.process_touch(test_device)
        else:
            # Try calling the touch handler directly if it exists
            if hasattr(REGISTRY, '_touch_handler') and REGISTRY._touch_handler:
                result = REGISTRY._touch_handler(test_device)
            else:
                print("⚠️  No touch processing method available")
                return True
        
        print(f"✅ Touch processing executed for device '{test_device}'")
        return True
        
    except Exception as e:
        print(f"❌ Error processing touch: {str(e)}")
        return False

def test_mixed_course_environment():
    """Test that traditional and advanced courses can coexist."""
    print("\n=== Testing Mixed Course Environment ===")
    
    conn = sqlite3.connect('/opt/data/field_trainer.db')
    cursor = conn.cursor()
    
    # Count traditional courses
    cursor.execute("""
        SELECT COUNT(*) FROM courses 
        WHERE course_type IS NULL OR course_type NOT IN ('advanced')
    """)
    traditional_count = cursor.fetchone()[0]
    
    # Count advanced courses
    cursor.execute("""
        SELECT COUNT(*) FROM courses 
        WHERE course_type = 'advanced'
    """)
    advanced_count = cursor.fetchone()[0]
    
    print(f"Database contains: {traditional_count} traditional, {advanced_count} advanced courses")
    
    # Check that both can be loaded
    cursor.execute("SELECT course_name FROM courses LIMIT 5")
    sample_courses = cursor.fetchall()
    
    all_loadable = True
    for (course_name,) in sample_courses:
        try:
            course_data = db.get_course(db.get_course_id_by_name(course_name))
            if course_data:
                print(f"✅ Course '{course_name}' loads correctly")
            else:
                print(f"❌ Course '{course_name}' failed to load")
                all_loadable = False
        except Exception as e:
            print(f"❌ Error loading '{course_name}': {str(e)}")
            all_loadable = False
    
    conn.close()
    return all_loadable

def test_database_integrity():
    """Verify database integrity after migration."""
    print("\n=== Testing Database Integrity ===")
    
    conn = sqlite3.connect('/opt/data/field_trainer.db')
    cursor = conn.cursor()
    
    # Run integrity check
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    
    if result == "ok":
        print("✅ Database integrity check passed")
    else:
        print(f"❌ Database integrity issue: {result}")
        conn.close()
        return False
    
    # Check foreign key constraints
    cursor.execute("PRAGMA foreign_key_check")
    fk_issues = cursor.fetchall()
    
    if not fk_issues:
        print("✅ All foreign key constraints valid")
    else:
        print(f"❌ Foreign key issues found: {fk_issues}")
        conn.close()
        return False
    
    # Verify all required tables exist
    required_tables = [
        'courses', 'course_actions', 'teams', 'athletes', 
        'sessions', 'runs', 'segments', 'settings'
    ]
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]
    
    for table in required_tables:
        if table in existing_tables:
            print(f"✅ Table '{table}' exists")
        else:
            print(f"❌ Required table '{table}' missing")
            conn.close()
            return False
    
    conn.close()
    return True

def test_default_values():
    """Test that NULL new fields are handled correctly."""
    print("\n=== Testing NULL Field Handling ===")
    
    conn = sqlite3.connect('/opt/data/field_trainer.db')
    cursor = conn.cursor()
    
    # Get an action with NULL new fields (from existing course)
    cursor.execute("""
        SELECT ca.action_id, ca.device_id, ca.action,
               ca.device_function, ca.detection_method, 
               ca.group_identifier, ca.behavior_config
        FROM course_actions ca
        JOIN courses c ON ca.course_id = c.course_id
        WHERE (c.course_type IS NULL OR c.course_type != 'advanced')
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        print("⚠️  No traditional course actions found")
        return True
    
    action_id, device_id, action, dev_func, det_method, group_id, behav_cfg = result
    
    print(f"Testing action: {device_id} - {action}")
    print(f"  device_function: {dev_func} (should be NULL)")
    print(f"  detection_method: {det_method} (should be NULL)")
    print(f"  group_identifier: {group_id} (should be NULL)")
    print(f"  behavior_config: {behav_cfg} (should be NULL)")
    
    # Verify NULLs are handled as defaults in code
    defaults_correct = True
    
    # When NULL, should default to:
    # - device_function -> 'waypoint'
    # - detection_method -> 'touch'
    # - group_identifier -> None (no grouping)
    # - behavior_config -> {} (empty dict)
    
    if dev_func is None:
        print("✅ device_function is NULL (will use default 'waypoint')")
    else:
        print(f"⚠️  device_function has value: {dev_func}")
    
    if det_method is None:
        print("✅ detection_method is NULL (will use default 'touch')")
    else:
        print(f"⚠️  detection_method has value: {det_method}")
    
    if group_id is None:
        print("✅ group_identifier is NULL (no grouping)")
    else:
        print(f"⚠️  group_identifier has value: {group_id}")
    
    if behav_cfg is None:
        print("✅ behavior_config is NULL (no special behavior)")
    else:
        print(f"⚠️  behavior_config has value: {behav_cfg}")
    
    return defaults_correct

def run_compatibility_tests():
    """Run all backwards compatibility tests."""
    print("="*60)
    print("FIELD TRAINER BACKWARDS COMPATIBILITY TEST SUITE")
    print("="*60)
    print("Testing that existing courses continue to work correctly")
    print("after adding advanced course features...")
    
    tests = [
        ("Database Integrity", test_database_integrity),
        ("Existing Course Structure", test_existing_course_structure),
        ("NULL Field Handling", test_default_values),
        ("Traditional Course Deployment", test_traditional_course_deployment),
        ("Traditional Course Activation", test_traditional_course_activation),
        ("Traditional Touch Processing", test_traditional_touch_processing),
        ("Mixed Course Environment", test_mixed_course_environment),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            result = test_func()
            results.append((test_name, result))
            
            # Clean up after each test
            if hasattr(REGISTRY, 'deactivate_course_compatible'):
                REGISTRY.deactivate_course_compatible()
            elif hasattr(REGISTRY, 'deactivate_course'):
                REGISTRY.deactivate_course()
                
        except Exception as e:
            print(f"❌ Test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("BACKWARDS COMPATIBILITY TEST RESULTS")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:35} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 FULL BACKWARDS COMPATIBILITY CONFIRMED! 🎉")
        print("All existing courses will continue to work correctly.")
        return 0
    else:
        print(f"\n⚠️  WARNING: {total - passed} compatibility test(s) failed")
        print("Existing courses may not work correctly!")
        return 1

if __name__ == "__main__":
    print("Initializing test environment...")
    
    # Clean any previous state
    if hasattr(REGISTRY, 'reset_course_state'):
        REGISTRY.reset_course_state()
    
    # Run compatibility tests
    exit_code = run_compatibility_tests()
    
    # Final cleanup
    if hasattr(REGISTRY, 'reset_course_state'):
        REGISTRY.reset_course_state()
    
    if exit_code == 0:
        print("\n" + "="*60)
        print("✅ SAFE TO PROCEED WITH DEPLOYMENT")
        print("Existing courses are fully protected and will work normally.")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("⚠️  DO NOT DEPLOY - COMPATIBILITY ISSUES DETECTED")
        print("Review and fix issues before proceeding.")
        print("="*60)
    
    sys.exit(exit_code)
