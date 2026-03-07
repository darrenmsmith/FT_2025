#!/usr/bin/env python3
"""
Sync built-in courses to the Field Trainer database.

Safe to run on any system - only inserts/updates built-in course definitions.
Does NOT touch session data, teams, or athletes.

Usage:
    python3 /opt/scripts/sync_builtin_courses.py
    python3 /opt/scripts/sync_builtin_courses.py /path/to/other.db
"""

import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else '/opt/data/field_trainer.db'

# ---------------------------------------------------------------------------
# Built-in course definitions
# Each entry: (course dict, [action dicts])
# ---------------------------------------------------------------------------

BUILTIN_COURSES = [

    # ------------------------------------------------------------------
    # Warm-up: Round 1
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Warm-up: Round 1',
            'description': 'Basic warm-up circuit. Touch each cone in sequence.',
            'course_type': 'conditioning',
            'mode': 'sequential',
            'category': 'Agility',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'yards',
            'total_distance': 0,
            'version': '1.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'start',        'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 3, 'device_id': '192.168.99.103', 'device_name': 'Cone 3',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 4, 'device_id': '192.168.99.104', 'device_name': 'Cone 4',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 5, 'device_id': '192.168.99.105', 'device_name': 'Cone 5',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 5.0},
        ]
    ),

    # ------------------------------------------------------------------
    # Warm-up: Round 2
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Warm-up: Round 2',
            'description': 'Intermediate warm-up circuit. Touch each cone in sequence.',
            'course_type': 'conditioning',
            'mode': 'sequential',
            'category': 'Agility',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'yards',
            'total_distance': 0,
            'version': '1.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'start',        'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 3, 'device_id': '192.168.99.103', 'device_name': 'Cone 3',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 4, 'device_id': '192.168.99.104', 'device_name': 'Cone 4',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 5, 'device_id': '192.168.99.105', 'device_name': 'Cone 5',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 5.0},
        ]
    ),

    # ------------------------------------------------------------------
    # Warm-up: Round 3
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Warm-up: Round 3',
            'description': 'Advanced warm-up circuit. Touch each cone in sequence.',
            'course_type': 'conditioning',
            'mode': 'sequential',
            'category': 'Agility',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'yards',
            'total_distance': 0,
            'version': '1.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'start',        'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 3, 'device_id': '192.168.99.103', 'device_name': 'Cone 3',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 4, 'device_id': '192.168.99.104', 'device_name': 'Cone 4',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 5, 'device_id': '192.168.99.105', 'device_name': 'Cone 5',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 5.0},
        ]
    ),

    # ------------------------------------------------------------------
    # Simon Says - 4 Colors
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Simon Says - 4 Colors',
            'description': 'Pattern-based drill. Watch the sequence, then repeat it by touching the correct cones.',
            'course_type': 'pattern',
            'mode': 'pattern',
            'category': 'Agility',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'yards',
            'total_distance': 0,
            'version': '1.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'default_beep', 'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0, 'behavior_config': None},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0, 'behavior_config': '{"color": "red"}'},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0, 'behavior_config': '{"color": "blue"}'},
            {'sequence': 3, 'device_id': '192.168.99.103', 'device_name': 'Cone 3',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0, 'behavior_config': '{"color": "green"}'},
            {'sequence': 4, 'device_id': '192.168.99.104', 'device_name': 'Cone 4',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 3.0, 'behavior_config': '{"color": "yellow"}'},
        ]
    ),

    # ------------------------------------------------------------------
    # Beep Test
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Beep Test (Léger Protocol)',
            'description': 'Progressive aerobic capacity test. Run between two cones 20m apart in time with the beeps.',
            'course_type': 'beep_test',
            'mode': 'sequential',
            'category': 'Fitness',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'meters',
            'total_distance': 20,
            'version': '1.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'start',        'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 20.0},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 20.0},
            {'sequence': 3, 'device_id': '192.168.99.105', 'device_name': 'Cone 5',           'action': 'touch',         'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 20.0},
        ]
    ),

    # ------------------------------------------------------------------
    # Reaction
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Reaction',
            'description': 'Random reaction sprint drill. Touch all 5 cones as fast as possible. Each cone can only be touched once per run. 10 second timeout per cone.',
            'course_type': 'reaction_sprint',
            'mode': 'pattern',
            'category': 'agility',
            'num_devices': 6,
            'total_devices': 6,
            'distance_unit': 'yards',
            'total_distance': 20,
            'version': '2.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Device 0 (Start)', 'action': 'default_beep', 'action_type': 'audio_start',       'audio_file': 'default_beep.mp3', 'min_time': 0.1, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 5.0},
            {'sequence': 1, 'device_id': '192.168.99.101', 'device_name': 'Cone 1',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 1, 'marks_run_complete': 0, 'distance': 3.0},
            {'sequence': 2, 'device_id': '192.168.99.102', 'device_name': 'Cone 2',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0},
            {'sequence': 3, 'device_id': '192.168.99.103', 'device_name': 'Cone 3',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0},
            {'sequence': 4, 'device_id': '192.168.99.104', 'device_name': 'Cone 4',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 3.0},
            {'sequence': 5, 'device_id': '192.168.99.105', 'device_name': 'Cone 5',           'action': 'default_beep', 'action_type': 'touch_checkpoint',  'audio_file': 'default_beep.mp3', 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 1, 'distance': 3.0},
        ]
    ),

    # ------------------------------------------------------------------
    # Sprint
    # ------------------------------------------------------------------
    (
        {
            'course_name': 'Sprint',
            'description': 'Sprint can be setup for any distance. Each session will be save to the specific distance.  Athletes will line up and a beep will sound from the Start cone.  A second cone will be placed at the desired distance. A coach will press Stop to capture the time.',
            'course_type': 'sprint',
            'mode': '',
            'category': 'speed',
            'num_devices': 2,
            'total_devices': 1,
            'distance_unit': 'yards',
            'total_distance': 40,
            'version': '2.0',
            'countdown_interval': 5,
            'timing_mode': 'manual',
            'distance': 40,
        },
        [
            {'sequence': 0, 'device_id': '192.168.99.100', 'device_name': 'Gateway', 'action': 'start', 'action_type': 'sprint_start', 'audio_file': None, 'min_time': 1.0, 'max_time': 30.0, 'triggers_next_athlete': 0, 'marks_run_complete': 0, 'distance': 0.0},
        ]
    ),
]


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    added = 0
    updated = 0

    for course_def, actions in BUILTIN_COURSES:
        name = course_def['course_name']
        existing = conn.execute(
            'SELECT course_id FROM courses WHERE course_name = ?', (name,)
        ).fetchone()

        distance = course_def.pop('distance', None)

        if existing:
            course_id = existing['course_id']
            conn.execute('''
                UPDATE courses SET
                    description=:description, course_type=:course_type, mode=:mode,
                    category=:category, num_devices=:num_devices, total_devices=:total_devices,
                    distance_unit=:distance_unit, total_distance=:total_distance,
                    version=:version, countdown_interval=:countdown_interval,
                    timing_mode=:timing_mode, is_builtin=1
                WHERE course_id=:course_id
            ''', {**course_def, 'course_id': course_id})
            if distance is not None:
                conn.execute('UPDATE courses SET distance=? WHERE course_id=?', (distance, course_id))
            # Replace actions
            conn.execute('DELETE FROM course_actions WHERE course_id=?', (course_id,))
            updated += 1
            label = 'updated'
        else:
            cur = conn.execute('''
                INSERT INTO courses
                    (course_name, description, course_type, mode, category, num_devices,
                     total_devices, distance_unit, total_distance, version,
                     countdown_interval, timing_mode, is_builtin)
                VALUES
                    (:course_name, :description, :course_type, :mode, :category, :num_devices,
                     :total_devices, :distance_unit, :total_distance, :version,
                     :countdown_interval, :timing_mode, 1)
            ''', course_def)
            course_id = cur.lastrowid
            if distance is not None:
                conn.execute('UPDATE courses SET distance=? WHERE course_id=?', (distance, course_id))
            added += 1
            label = 'added'

        for a in actions:
            conn.execute('''
                INSERT INTO course_actions
                    (course_id, sequence, device_id, device_name, action, action_type,
                     audio_file, instruction, min_time, max_time,
                     triggers_next_athlete, marks_run_complete, distance, behavior_config)
                VALUES
                    (:course_id, :sequence, :device_id, :device_name, :action, :action_type,
                     :audio_file, :instruction, :min_time, :max_time,
                     :triggers_next_athlete, :marks_run_complete, :distance, :behavior_config)
            ''', {**a, 'course_id': course_id, 'instruction': a.get('instruction'), 'behavior_config': a.get('behavior_config')})

        print(f'  {label:<8} {name}')

    conn.commit()
    conn.close()
    print(f'\nDone: {added} added, {updated} updated.')


if __name__ == '__main__':
    print(f'Syncing built-in courses to: {DB_PATH}')
    sync(DB_PATH)
