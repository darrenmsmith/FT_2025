#!/usr/bin/env python3
"""
Create example advanced courses demonstrating the new advanced fields
"""

import sys
sys.path.insert(0, '/opt/field_trainer')

from db_manager import DatabaseManager

# Initialize database
db = DatabaseManager('/opt/data/field_trainer.db')

print("Creating example advanced courses...")
print("=" * 60)

# Example 1: Yo-Yo Intermittent Recovery Test (IR1)
print("\n1. Creating 'Yo-Yo IR Test Level 1'...")
course_1 = db.create_advanced_course(
    course_name="Yo-Yo IR Test Level 1",
    description="Progressive shuttle run with active recovery periods",
    category="Conditioning",
    mode="sequential",
    course_type="advanced",
    actions=[
        {
            'sequence': 0,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'audio_start',
            'audio_file': 'sprint.mp3',
            'instruction': 'Explode forward from a low stance using powerful leg drive',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'start_line',
            'behavior_config': None
        },
        {
            'sequence': 1,
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch and sprint back immediately',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': False,
            'distance': 20,
            'device_function': 'turnaround',
            'detection_method': 'touch',
            'group_identifier': 'turnaround_point',
            'behavior_config': None
        },
        {
            'sequence': 2,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'jog',
            'action_type': 'touch_checkpoint',
            'audio_file': 'jog.mp3',
            'instruction': 'Active recovery - light jog for 10 seconds',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': True,
            'distance': 20,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'start_line',
            'behavior_config': 'min_time: 8.0, max_time: 12.0, recovery_period: true'
        }
    ]
)
print(f"✓ Created course ID: {course_1}")

# Example 2: 5-10-5 Agility Drill (NFL Combine)
print("\n2. Creating '5-10-5 Pro Agility Test'...")
course_2 = db.create_advanced_course(
    course_name="5-10-5 Pro Agility Test",
    description="NFL Combine standard agility test - sprint 5 yards, 10 yards back, 5 yards return",
    category="Agility",
    mode="sequential",
    course_type="advanced",
    actions=[
        {
            'sequence': 0,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'audio_start',
            'audio_file': 'sprint.mp3',
            'instruction': 'Start in 3-point stance, explode to your right',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'center_line',
            'behavior_config': 'timer: true, split_timing: true'
        },
        {
            'sequence': 1,
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch cone with hand, change direction quickly',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 5,
            'device_function': 'turnaround',
            'detection_method': 'touch',
            'group_identifier': 'right_cone',
            'behavior_config': 'split_timing: true'
        },
        {
            'sequence': 2,
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch cone with hand, change direction back to center',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10,
            'device_function': 'turnaround',
            'detection_method': 'touch',
            'group_identifier': 'left_cone',
            'behavior_config': 'split_timing: true'
        },
        {
            'sequence': 3,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint through finish line at full speed',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': True,
            'distance': 5,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'center_line',
            'behavior_config': 'timer: true, split_timing: true, scoring: true'
        }
    ]
)
print(f"✓ Created course ID: {course_2}")

# Example 3: Simon Says Reaction Drill
print("\n3. Creating 'Simon Says Reaction Drill'...")
course_3 = db.create_advanced_course(
    course_name="Simon Says Reaction Drill",
    description="Random pattern reaction training - devices light up in sequence, athlete must follow",
    category="Reaction",
    mode="pattern",
    course_type="advanced",
    actions=[
        {
            'sequence': 0,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'default_beep',
            'action_type': 'audio_start',
            'audio_file': 'default_beep.mp3',
            'instruction': 'Wait for pattern to display, then follow the sequence',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'home_base',
            'behavior_config': 'pattern_type: simon_says, difficulty: 3, sequence_length: 4'
        },
        {
            'sequence': 1,
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch when lit, return to home',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 5,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'pattern_group',
            'behavior_config': 'pattern_member: true'
        },
        {
            'sequence': 2,
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch when lit, return to home',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 5,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'pattern_group',
            'behavior_config': 'pattern_member: true'
        },
        {
            'sequence': 3,
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch when lit, return to home',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 5,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'pattern_group',
            'behavior_config': 'pattern_member: true'
        },
        {
            'sequence': 4,
            'device_id': '192.168.99.104',
            'device_name': 'Device 4',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch when lit, return to home',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': True,
            'distance': 5,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'pattern_group',
            'behavior_config': 'pattern_member: true, scoring: true'
        }
    ]
)
print(f"✓ Created course ID: {course_3}")

# Example 4: Box Drill with Timing Zones
print("\n4. Creating 'Box Drill - Timed Zones'...")
course_4 = db.create_advanced_course(
    course_name="Box Drill - Timed Zones",
    description="4-corner box drill with minimum time requirements per zone",
    category="Agility",
    mode="sequential",
    course_type="advanced",
    actions=[
        {
            'sequence': 0,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'audio_start',
            'audio_file': 'sprint.mp3',
            'instruction': 'Start position - Corner 1',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'corner_1',
            'behavior_config': 'zone: 1, timer: true'
        },
        {
            'sequence': 1,
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'side_shuffle_right',
            'action_type': 'touch_checkpoint',
            'audio_file': 'side_shuffle_right.mp3',
            'instruction': 'Side shuffle right to Corner 2 (min 2 seconds)',
            'min_time': 2.0,
            'max_time': 5.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'corner_2',
            'behavior_config': 'zone: 2, min_time: 2.0, max_time: 5.0'
        },
        {
            'sequence': 2,
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'backpedal',
            'action_type': 'touch_checkpoint',
            'audio_file': 'backpedal.mp3',
            'instruction': 'Backpedal to Corner 3 (min 2.5 seconds)',
            'min_time': 2.5,
            'max_time': 6.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'corner_3',
            'behavior_config': 'zone: 3, min_time: 2.5, max_time: 6.0'
        },
        {
            'sequence': 3,
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'side_shuffle_left',
            'action_type': 'touch_checkpoint',
            'audio_file': 'side_shuffle_left.mp3',
            'instruction': 'Side shuffle left to Corner 4 (min 2 seconds)',
            'min_time': 2.0,
            'max_time': 5.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10,
            'device_function': 'waypoint',
            'detection_method': 'touch',
            'group_identifier': 'corner_4',
            'behavior_config': 'zone: 4, min_time: 2.0, max_time: 5.0'
        },
        {
            'sequence': 4,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint back to start - finish!',
            'min_time': 1.0,
            'max_time': 3.0,
            'triggers_next_athlete': True,
            'marks_run_complete': True,
            'distance': 10,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'corner_1',
            'behavior_config': 'zone: 5, timer: true, scoring: true'
        }
    ]
)
print(f"✓ Created course ID: {course_4}")

# Example 5: Proximity Detection Drill
print("\n5. Creating 'Proximity Detection Sprint'...")
course_5 = db.create_advanced_course(
    course_name="Proximity Detection Sprint",
    description="Sprint drill using proximity sensors - no physical touch required",
    category="Speed",
    mode="sequential",
    course_type="advanced",
    actions=[
        {
            'sequence': 0,
            'device_id': '192.168.99.100',
            'device_name': 'Device 0 (Gateway)',
            'action': 'sprint',
            'action_type': 'audio_start',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint start - physical touch to begin',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'device_function': 'start_finish',
            'detection_method': 'touch',
            'group_identifier': 'start_gate',
            'behavior_config': None
        },
        {
            'sequence': 1,
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint past (proximity detection - no touch needed)',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10,
            'device_function': 'waypoint',
            'detection_method': 'proximity',
            'group_identifier': 'speed_gate_1',
            'behavior_config': 'proximity_threshold: 1.5, split_timing: true'
        },
        {
            'sequence': 2,
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint past (proximity detection)',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20,
            'device_function': 'waypoint',
            'detection_method': 'proximity',
            'group_identifier': 'speed_gate_2',
            'behavior_config': 'proximity_threshold: 1.5, split_timing: true'
        },
        {
            'sequence': 3,
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint through finish line (proximity)',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': True,
            'distance': 40,
            'device_function': 'start_finish',
            'detection_method': 'proximity',
            'group_identifier': 'finish_gate',
            'behavior_config': 'proximity_threshold: 1.5, timer: true, scoring: true'
        }
    ]
)
print(f"✓ Created course ID: {course_5}")

print("\n" + "=" * 60)
print("✓ All 5 example advanced courses created successfully!")
print("\nCourses created:")
print("  1. Yo-Yo IR Test Level 1 - Recovery intervals with turnaround points")
print("  2. 5-10-5 Pro Agility Test - NFL Combine drill with split timing")
print("  3. Simon Says Reaction Drill - Pattern-based reaction training")
print("  4. Box Drill - Timed Zones - Minimum time requirements per zone")
print("  5. Proximity Detection Sprint - No-touch speed gates")
print("\nView them at: http://192.168.7.116:5001/courses")
print("=" * 60)
