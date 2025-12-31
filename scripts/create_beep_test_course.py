#!/usr/bin/env python3
"""
Create Beep Test course in database
This is a one-time setup script to add the Beep Test course
"""

import sys
import json
sys.path.insert(0, '/opt')

from field_trainer.db_manager import DatabaseManager

def create_beep_test_course():
    """Create the Beep Test course with mode='group'"""

    db = DatabaseManager('/opt/data/field_trainer.db')

    # Check if beep test course already exists
    existing_courses = db.get_all_courses()
    for course in existing_courses:
        if course['course_name'] == 'Beep Test - Léger Protocol':
            print(f"⚠️  Beep Test course already exists (ID: {course['course_id']})")
            response = input("Delete and recreate? (y/n): ")
            if response.lower() == 'y':
                db.delete_course(course['course_id'])
                print("✅ Deleted existing course")
            else:
                print("Aborting")
                return

    # Define course actions for a 6-device configuration (3 at each end)
    # These will be the template - actual device count is configured at session setup
    actions = []

    # START LINE devices (Device 0, 1, 2)
    # All START devices are in the same group and do the same thing
    for i in range(3):
        device_id = f"192.168.99.{100 + i}"
        device_name = f"Device {i}"

        actions.append({
            'sequence': i,
            'device_id': device_id,
            'device_name': device_name,
            'action': 'beep_start',
            'action_type': 'audio_beep',
            'audio_file': 'default_beep',
            'instruction': 'Start line - Run to opposite end when you hear the beep',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': 0,
            'marks_run_complete': 0,
            'group_identifier': 'start',  # Group identifier for START line
            'behavior_config': json.dumps({
                'mode': 'group',
                'course_type': 'beep_test',
                'protocol': 'leger',
                'distance_meters': 20,
                'start_level': 1,
                'max_level': 21
            }) if i == 0 else None  # Only first device has config
        })

    # END LINE devices (Device 3, 4, 5)
    # All END devices are in the same group and do the same thing
    for i in range(3, 6):
        device_id = f"192.168.99.{100 + i}"
        device_name = f"Device {i}"

        actions.append({
            'sequence': i,
            'device_id': device_id,
            'device_name': device_name,
            'action': 'beep_end',
            'action_type': 'audio_beep',
            'audio_file': 'default_beep',
            'instruction': 'End line - Run back to start when you hear the beep',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': 0,
            'marks_run_complete': 0,
            'group_identifier': 'end',  # Group identifier for END line
            'behavior_config': None
        })

    # Create the course
    course_id = db.create_course(
        name='Beep Test - Léger Protocol',
        description='Progressive shuttle run test - Athletes run between two lines at progressively faster speeds until exhaustion',
        course_type='beep_test',
        mode='group',
        category='conditioning',
        total_devices=6,  # Template uses 6, but can be configured at session setup
        actions=actions
    )

    print(f"✅ Created Beep Test course (ID: {course_id})")
    print(f"   Mode: group")
    print(f"   Course Type: beep_test")
    print(f"   Total Devices: 6 (configurable: 2, 4, or 6)")
    print(f"   Actions: {len(actions)}")
    print(f"   - START line (group): Devices 0, 1, 2")
    print(f"   - END line (group): Devices 3, 4, 5")

    # Verify course was created correctly
    course = db.get_course(course_id)
    print(f"\n✅ Verification:")
    print(f"   Course Name: {course['course_name']}")
    print(f"   Mode: {course.get('mode', 'NOT SET')}")
    print(f"   Course Type: {course.get('course_type', 'NOT SET')}")
    print(f"   Actions loaded: {len(course['actions'])}")

    # Check behavior_config
    first_action = course['actions'][0]
    if first_action.get('behavior_config'):
        config = json.loads(first_action['behavior_config'])
        print(f"   Behavior Config: {config}")

    return course_id

if __name__ == '__main__':
    create_beep_test_course()
