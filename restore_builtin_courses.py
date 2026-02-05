#!/usr/bin/env python3
"""
Restore built-in courses - automatically creates built-in courses on new systems
- Warm-up Round 1, 2, 3
- Simon Says - 4 Colors
- Beep Test (Léger Protocol)

This script is called automatically on app startup to ensure all built-in courses exist.
It checks for existing courses and only creates missing ones.
"""

import sys
sys.path.insert(0, '/opt/field_trainer')
from db_manager import DatabaseManager
import json

db = DatabaseManager('/opt/data/field_trainer.db')

def course_exists(name):
    """Check if course already exists as a built-in course"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT course_id FROM courses WHERE course_name = ? AND is_builtin = 1', (name,))
        result = cursor.fetchone()
        return result is not None

print("="*80)
print("RESTORING BUILT-IN COURSES")
print("="*80)

# Warm-up Round 1
print("\n1. Checking Warm-up: Round 1...")
if course_exists("Warm-up: Round 1"):
    print("   ✓ Already exists - skipping")
    course_id_1 = None
else:
    print("   Creating...")
    course_id_1 = db.create_course(
    name="Warm-up: Round 1",
    description="Goal is to increases blood flow, muscle temperature, and joint mobility to prepare the body for movement. It reduces injury risk and improves performance by activating muscles and enhancing coordination.",
    course_type="conditioning",
    mode="sequential",
    category="warmup",
    total_devices=6,
    actions=[
        {
            'device_id': '192.168.99.100',
            'device_name': 'Device 0',
            'action': 'high_knees',
            'action_type': 'audio_start',
            'audio_file': 'high_knees.mp3',
            'instruction': 'Drive knees up toward the chest with each step while staying tall. Use fast, rhythmic arm swings to match leg speed.',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10.0
        },
        {
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'walking_lunge',
            'action_type': 'touch_checkpoint',
            'audio_file': 'walking_lunge.mp3',
            'instruction': 'Step forward into a deep lunge, lowering the rear knee toward the ground. Push off the front foot to rise and repeat with the opposite leg.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'backpedal',
            'action_type': 'touch_checkpoint',
            'audio_file': 'backpedal.mp3',
            'instruction': 'Running backward with controlled steps, maintaining balance and awareness.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'high_skips',
            'action_type': 'touch_checkpoint',
            'audio_file': 'high_skips.mp3',
            'instruction': 'Skip forward with exaggerated vertical lift and arm drive. Focus on height, rhythm, and soft landings.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 25.0
        },
        {
            'device_id': '192.168.99.104',
            'device_name': 'Device 4',
            'action': 'butt_kicks',
            'action_type': 'touch_checkpoint',
            'audio_file': 'butt_kicks.mp3',
            'instruction': 'Jog forward while driving heels up toward the glutes. Keep knees low and maintain a steady cadence.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.105',
            'device_name': 'Device 5',
            'action': 'jog',
            'action_type': 'touch_checkpoint',
            'audio_file': 'jog.mp3',
            'instruction': 'Run at a light, steady pace with relaxed arms and even strides. Maintain upright posture and breathing rhythm.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': True,
            'distance': 40.0
        }
    ]
    )
    # Mark as built-in
    with db.get_connection() as conn:
        conn.execute('UPDATE courses SET is_builtin = 1 WHERE course_id = ?', (course_id_1,))
    print(f"   ✓ Created Warm-up Round 1 (ID: {course_id_1})")

# Warm-up Round 2
print("\n2. Checking Warm-up: Round 2...")
if course_exists("Warm-up: Round 2"):
    print("   ✓ Already exists - skipping")
    course_id_2 = None
else:
    print("   Creating...")
    course_id_2 = db.create_course(
    name="Warm-up: Round 2",
    description="Goal is to increases blood flow, muscle temperature, and joint mobility to prepare the body for movement. It reduces injury risk and improves performance by activating muscles and enhancing coordination.",
    course_type="conditioning",
    mode="sequential",
    category="warmup",
    total_devices=6,
    actions=[
        {
            'device_id': '192.168.99.100',
            'device_name': 'Device 0',
            'action': 'walking_lunge',
            'action_type': 'audio_start',
            'audio_file': 'walking_lunge.mp3',
            'instruction': 'Step forward into a deep lunge, lowering the rear knee toward the ground. Push off the front foot to rise and repeat with the opposite leg.',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10.0
        },
        {
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'internal_hip',
            'action_type': 'touch_checkpoint',
            'audio_file': 'internal_hip.mp3',
            'instruction': 'Hip rotation exercise moving inward',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'external_hip',
            'action_type': 'touch_checkpoint',
            'audio_file': 'external_hip.mp3',
            'instruction': 'Hip rotation exercise moving outward',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'carioca_right',
            'action_type': 'touch_checkpoint',
            'audio_file': 'carioca_right.mp3',
            'instruction': 'Lateral movement crossing feet, moving to the right',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 25.0
        },
        {
            'device_id': '192.168.99.104',
            'device_name': 'Device 4',
            'action': 'carioca_left',
            'action_type': 'touch_checkpoint',
            'audio_file': 'carioca_left.mp3',
            'instruction': 'Lateral movement crossing feet, moving to the left',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.105',
            'device_name': 'Device 5',
            'action': 'jog',
            'action_type': 'touch_checkpoint',
            'audio_file': 'jog.mp3',
            'instruction': 'Run at a light, steady pace with relaxed arms and even strides. Maintain upright posture and breathing rhythm.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': True,
            'distance': 40.0
        }
    ]
    )
    with db.get_connection() as conn:
        conn.execute('UPDATE courses SET is_builtin = 1 WHERE course_id = ?', (course_id_2,))
    print(f"   ✓ Created Warm-up Round 2 (ID: {course_id_2})")

# Warm-up Round 3
print("\n3. Checking Warm-up: Round 3...")
if course_exists("Warm-up: Round 3"):
    print("   ✓ Already exists - skipping")
    course_id_3 = None
else:
    print("   Creating...")
    course_id_3 = db.create_course(
    name="Warm-up: Round 3",
    description="Goal is to increases blood flow, muscle temperature, and joint mobility to prepare the body for movement. It reduces injury risk and improves performance by activating muscles and enhancing coordination.",
    course_type="conditioning",
    mode="sequential",
    category="warmup",
    total_devices=6,
    actions=[
        {
            'device_id': '192.168.99.100',
            'device_name': 'Device 0',
            'action': 'backpedal',
            'action_type': 'audio_start',
            'audio_file': 'backpedal.mp3',
            'instruction': 'Running backward with controlled steps, maintaining balance and awareness.',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 10.0
        },
        {
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'side_shuffle_left',
            'action_type': 'touch_checkpoint',
            'audio_file': 'side_shuffle_left.mp3',
            'instruction': 'Shuffle laterally to the left maintaining athletic stance',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': True,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.102',
            'device_name': 'Device 2',
            'action': 'side_shuffle_right',
            'action_type': 'touch_checkpoint',
            'audio_file': 'side_shuffle_right.mp3',
            'instruction': 'Shuffle laterally to the right maintaining athletic stance',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.103',
            'device_name': 'Device 3',
            'action': 'backpedal',
            'action_type': 'touch_checkpoint',
            'audio_file': 'backpedal.mp3',
            'instruction': 'Running backward with controlled steps, maintaining balance and awareness.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 25.0
        },
        {
            'device_id': '192.168.99.104',
            'device_name': 'Device 4',
            'action': 'bounds',
            'action_type': 'touch_checkpoint',
            'audio_file': 'bounds.mp3',
            'instruction': 'Explosive forward bounds with maximum extension',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.105',
            'device_name': 'Device 5',
            'action': 'jog',
            'action_type': 'touch_checkpoint',
            'audio_file': 'jog.mp3',
            'instruction': 'Run at a light, steady pace with relaxed arms and even strides. Maintain upright posture and breathing rhythm.',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': True,
            'distance': 40.0
        }
    ]
    )
    with db.get_connection() as conn:
        conn.execute('UPDATE courses SET is_builtin = 1 WHERE course_id = ?', (course_id_3,))
    print(f"   ✓ Created Warm-up Round 3 (ID: {course_id_3})")

# Simon Says - 4 Colors
print("\n4. Checking Simon Says - 4 Colors...")
if course_exists("Simon Says - 4 Colors"):
    print("   ✓ Already exists - skipping")
    course_id_4 = None
else:
    print("   Creating...")

    # Interactive SVG diagram with draggable cones
    simon_says_svg = '''<svg id="courseSvg" viewBox="0 0 800 500" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:100%; cursor:default;"><!-- CONE_POSITIONS:[{"x":36.69155598715713,"y":253.47344459210672,"arrowAngle":0},{"x":474.1910043658405,"y":30.624124394226822,"arrowAngle":45},{"x":665.084958433693,"y":250.1962487068438,"arrowAngle":180},{"x":471.73314229629733,"y":470,"arrowAngle":225},{"x":266.0920158111859,"y":243.6418569363179,"arrowAngle":180}] --><rect width="800" height="500" fill="white"/><defs><pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#e0e0e0" stroke-width="1"/></pattern></defs><rect width="800" height="500" fill="url(#grid)"/><line x1="36.69155598715713" y1="253.47344459210672" x2="474.1910043658405" y2="30.624124394226822" stroke="#2196F3" stroke-width="2" stroke-dasharray="5,5" opacity="0.5"/><line x1="474.1910043658405" y1="30.624124394226822" x2="665.084958433693" y2="250.1962487068438" stroke="#2196F3" stroke-width="2" stroke-dasharray="5,5" opacity="0.5"/><line x1="665.084958433693" y1="250.1962487068438" x2="471.73314229629733" y2="470" stroke="#2196F3" stroke-width="2" stroke-dasharray="5,5" opacity="0.5"/><line x1="471.73314229629733" y1="470" x2="266.0920158111859" y2="243.6418569363179" stroke="#2196F3" stroke-width="2" stroke-dasharray="5,5" opacity="0.5"/><g class="cone-group" data-idx="0" style="cursor:grab;"><circle cx="36.69155598715713" cy="253.47344459210672" r="25" fill="white" stroke="#4CAF50" stroke-width="3"/><text x="36.69155598715713" y="259.4734445921067" text-anchor="middle" font-size="18" font-weight="bold" fill="#4CAF50" pointer-events="none">S</text></g><g class="arrow-group" data-idx="0" style="cursor:pointer;"><line x1="61.69155598715713" y1="253.47344459210672" x2="91.69155598715713" y2="253.47344459210672" stroke="#4CAF50" stroke-width="4"/><polygon points="91.69155598715713,253.47344459210672 79.55630107153291,262.2902233764938 79.55630107153291,244.6566658077196" fill="#4CAF50"/></g><rect x="96.69155598715713" y="243.47344459210672" width="80" height="20" fill="white" stroke="#2196F3" rx="3"/><text x="136.69155598715713" y="258.4734445921067" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">0 yards</text><g class="cone-group" data-idx="1" style="cursor:grab;"><circle cx="474.1910043658405" cy="30.624124394226822" r="25" fill="white" stroke="#FF9800" stroke-width="3"/><text x="474.1910043658405" y="36.624124394226826" text-anchor="middle" font-size="18" font-weight="bold" fill="#FF9800" pointer-events="none">1</text></g><g class="arrow-group" data-idx="1" style="cursor:pointer;"><line x1="491.86867389550423" y1="48.30179392389051" x2="513.0818773311006" y2="69.51499735948693" stroke="#FF9800" stroke-width="4"/><polygon points="513.0818773311006,69.51499735948693 498.2665522221735,67.16848038388346 510.73536035549716,54.69967225055986" fill="#FF9800"/></g><rect x="504.90168248449527" y="91.33480251288157" width="80" height="20" fill="white" stroke="#2196F3" rx="3"/><text x="544.9016824844953" y="106.33480251288157" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">10 yards</text><g class="cone-group" data-idx="2" style="cursor:grab;"><circle cx="665.084958433693" cy="250.1962487068438" r="25" fill="white" stroke="#FF9800" stroke-width="3"/><text x="665.084958433693" y="256.1962487068438" text-anchor="middle" font-size="18" font-weight="bold" fill="#FF9800" pointer-events="none">2</text></g><g class="arrow-group" data-idx="2" style="cursor:pointer;"><line x1="640.084958433693" y1="250.1962487068438" x2="610.084958433693" y2="250.1962487068438" stroke="#FF9800" stroke-width="4"/><polygon points="610.084958433693,250.1962487068438 622.2202133493172,241.37946992245668 622.2202133493172,259.0130274912309" fill="#FF9800"/></g><rect x="525.084958433693" y="240.1962487068438" width="80" height="20" fill="white" stroke="#2196F3" rx="3"/><text x="565.084958433693" y="255.1962487068438" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">10 yards</text><g class="cone-group" data-idx="3" style="cursor:grab;"><circle cx="471.73314229629733" cy="470" r="25" fill="white" stroke="#FF9800" stroke-width="3"/><text x="471.73314229629733" y="476" text-anchor="middle" font-size="18" font-weight="bold" fill="#FF9800" pointer-events="none">3</text></g><g class="arrow-group" data-idx="3" style="cursor:pointer;"><line x1="454.0554727666336" y1="452.32233047033634" x2="432.8422693310372" y2="431.1091270347399" stroke="#FF9800" stroke-width="4"/><polygon points="432.8422693310372,431.1091270347399 447.65759443996427,433.45564401034335 435.1887863066407,445.924452143667" fill="#FF9800"/></g><rect x="361.0224641776426" y="389.28932188134524" width="80" height="20" fill="white" stroke="#2196F3" rx="3"/><text x="401.0224641776426" y="404.28932188134524" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">10 yards</text><g class="cone-group" data-idx="4" style="cursor:grab;"><circle cx="266.0920158111859" cy="243.6418569363179" r="25" fill="white" stroke="#FF9800" stroke-width="3"/><text x="266.0920158111859" y="249.6418569363179" text-anchor="middle" font-size="18" font-weight="bold" fill="#FF9800" pointer-events="none">4</text></g><g class="arrow-group" data-idx="4" style="cursor:pointer;"><line x1="241.0920158111859" y1="243.6418569363179" x2="211.0920158111859" y2="243.6418569363179" stroke="#FF9800" stroke-width="4"/><polygon points="211.0920158111859,243.6418569363179 223.2272707268101,234.8250781519308 223.2272707268101,252.458635720705" fill="#FF9800"/></g><rect x="126.09201581118589" y="233.6418569363179" width="80" height="20" fill="white" stroke="#2196F3" rx="3"/><text x="166.0920158111859" y="248.6418569363179" text-anchor="middle" font-size="12" font-weight="bold" fill="#2196F3">10 yards</text></svg>'''

    simon_says_layout = "Arrange 4 colored cones in a line or square pattern. Athletes must touch cones in the pattern shown by LED sequence.  To complete the pattern you much touch the start cone.  With each touch a beep will be played to tell you that the touch was registered."

    course_id_4 = db.create_course(
        name="Simon Says - 4 Colors",
        description="Pattern memory drill with 4 colored cones",
        course_type="pattern",
        mode="pattern",
        category="Pattern Drills",
        total_devices=5,
        diagram_svg=simon_says_svg,
        layout_instructions=simon_says_layout,
        actions=[
        {
            'device_id': '192.168.99.100',
            'device_name': 'Start',
            'action': 'default_beep',
            'action_type': 'audio_start',
            'audio_file': None,
            'instruction': 'Pattern submission point',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'behavior_config': json.dumps({
                "allowed_colors": ["red", "green", "blue", "yellow"],
                "pattern_length": 4,
                "show_pattern_duration": 3,
                "allow_repeats": False,
                "difficulty": "medium"
            })
        },
        {
            'device_id': '192.168.99.101',
            'device_name': 'Red',
            'action': 'high_knees',
            'action_type': 'touch_checkpoint',
            'audio_file': None,
            'instruction': 'Red cone',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'behavior_config': json.dumps({"color": "red"})
        },
        {
            'device_id': '192.168.99.102',
            'device_name': 'Green',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': None,
            'instruction': 'Green cone',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'behavior_config': json.dumps({"color": "green"})
        },
        {
            'device_id': '192.168.99.103',
            'device_name': 'Blue',
            'action': 'butt_kicks',
            'action_type': 'touch_checkpoint',
            'audio_file': None,
            'instruction': 'Blue cone',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'behavior_config': json.dumps({"color": "blue"})
        },
        {
            'device_id': '192.168.99.104',
            'device_name': 'Yellow',
            'action': 'jog',
            'action_type': 'touch_checkpoint',
            'audio_file': None,
            'instruction': 'Yellow cone',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 0,
            'behavior_config': json.dumps({"color": "yellow"})
        }
    ]
    )
    with db.get_connection() as conn:
        conn.execute('UPDATE courses SET is_builtin = 1 WHERE course_id = ?', (course_id_4,))
    print(f"   ✓ Created Simon Says - 4 Colors (ID: {course_id_4})")

# Beep Test (as a built-in course)
print("\n5. Checking Beep Test...")
if course_exists("Beep Test"):
    print("   ✓ Already exists - skipping")
    course_id_5 = None
else:
    print("   Creating...")
    course_id_5 = db.create_course(
    name="Beep Test",
    description="Multi-stage fitness test (Léger Protocol) - progressive shuttle run test used to estimate aerobic capacity",
    course_type="fitness",
    mode="sequential",
    category="fitness",
    total_devices=2,
    actions=[
        {
            'device_id': '192.168.99.100',
            'device_name': 'Device 0',
            'action': 'sprint',
            'action_type': 'audio_start',
            'audio_file': 'sprint.mp3',
            'instruction': 'Sprint to the opposite end before the beep',
            'min_time': 0.1,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': False,
            'distance': 20.0
        },
        {
            'device_id': '192.168.99.101',
            'device_name': 'Device 1',
            'action': 'sprint',
            'action_type': 'touch_checkpoint',
            'audio_file': 'sprint.mp3',
            'instruction': 'Touch and sprint back before the next beep',
            'min_time': 1.0,
            'max_time': 30.0,
            'triggers_next_athlete': False,
            'marks_run_complete': True,
            'distance': 20.0
        }
    ]
    )
    with db.get_connection() as conn:
        conn.execute('UPDATE courses SET is_builtin = 1 WHERE course_id = ?', (course_id_5,))
    print(f"   ✓ Created Beep Test (ID: {course_id_5})")

print("\n" + "="*80)
print("✅ BUILT-IN COURSES CHECK COMPLETE")
print("="*80)

created_count = sum(1 for cid in [course_id_1, course_id_2, course_id_3, course_id_4, course_id_5] if cid is not None)
skipped_count = 5 - created_count

print(f"\nSummary:")
print(f"  Created: {created_count}")
print(f"  Already existed: {skipped_count}")
print(f"\nCourses:")
print(f"  1. Warm-up: Round 1 {f'(ID: {course_id_1})' if course_id_1 else '(already exists)'}")
print(f"  2. Warm-up: Round 2 {f'(ID: {course_id_2})' if course_id_2 else '(already exists)'}")
print(f"  3. Warm-up: Round 3 {f'(ID: {course_id_3})' if course_id_3 else '(already exists)'}")
print(f"  4. Simon Says - 4 Colors {f'(ID: {course_id_4})' if course_id_4 else '(already exists)'}")
print(f"  5. Beep Test {f'(ID: {course_id_5})' if course_id_5 else '(already exists)'}")
