#!/usr/bin/env python3
"""
Update all existing courses with action descriptions
Run this once to populate blank instruction fields with default descriptions
"""

import sqlite3
import sys

# Action descriptions mapping
ACTION_DESCRIPTIONS = {
    'bounds': 'Push off forcefully from one leg and extend the opposite leg forward in a long, exaggerated stride. Land softly and repeat with rhythm and control.',
    'butt_kicks': 'Jog forward while driving heels up toward the glutes. Keep knees low and maintain a steady cadence.',
    'carioca_left': 'Cross one leg over the other while moving laterally, rotating hips with each step. Stay light on your feet and maintain fluid motion.',
    'carioca_right': 'Cross one leg over the other while moving laterally, rotating hips with each step. Stay light on your feet and maintain fluid motion.',
    'external_hip': 'Lift the knee and rotate the leg outward in a circular motion. Engage hip muscles and maintain balance throughout.',
    'high_knees': 'Drive knees up toward the chest with each step while staying tall. Use fast, rhythmic arm swings to match leg speed.',
    'high_skips': 'Skip forward with exaggerated vertical lift and arm drive. Focus on height, rhythm, and soft landings.',
    'icky_shuffle': 'Step quickly in and out of an agility ladder with alternating feet. Stay low and maintain fast, precise footwork.',
    'internal_hip': 'Lift the knee and rotate the leg inward across the body. Keep core engaged and movement controlled.',
    'jog': 'Run at a light, steady pace with relaxed arms and even strides. Maintain upright posture and breathing rhythm.',
    'ladder': 'Perform quick foot patterns through each box of the ladder. Stay light, fast, and coordinated.',
    'side_shuffle_left': 'Move laterally by pushing off the trailing foot and keeping feet shoulder-width apart. Stay low and avoid crossing feet.',
    'side_shuffle_right': 'Move laterally by pushing off the trailing foot and keeping feet shoulder-width apart. Stay low and avoid crossing feet.',
    'sprint': 'Explode forward from a low stance using powerful leg drive. Maintain forward lean and maximum effort over short distance.',
    'two_in_two_out': 'Step both feet into and out of each ladder box in a quick, rhythmic pattern. Focus on speed, timing, and control.',
    'walking_lunge': 'Step forward into a deep lunge, lowering the rear knee toward the ground. Push off the front foot to rise and repeat with the opposite leg.',
    'backpedal': 'Run backward while maintaining balance and looking over your shoulder. Keep steps quick and controlled.'
}

def update_course_descriptions(db_path='/opt/data/field_trainer.db'):
    """Update all course actions with blank instructions"""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all course actions with blank or null instructions
    cursor.execute('''
        SELECT action_id, action, instruction
        FROM course_actions
        WHERE instruction IS NULL OR instruction = ''
    ''')

    actions_to_update = cursor.fetchall()

    if not actions_to_update:
        print("✓ No actions need updating - all have descriptions already")
        conn.close()
        return

    print(f"Found {len(actions_to_update)} actions with blank descriptions")
    print("Updating...")

    updated_count = 0
    skipped_count = 0

    for row in actions_to_update:
        action_id = row['action_id']
        action = row['action']

        # Get default description for this action
        description = ACTION_DESCRIPTIONS.get(action)

        if description:
            cursor.execute('''
                UPDATE course_actions
                SET instruction = ?
                WHERE action_id = ?
            ''', (description, action_id))
            updated_count += 1
            print(f"  ✓ Updated action_id {action_id}: {action}")
        else:
            skipped_count += 1
            print(f"  ⚠ Skipped action_id {action_id}: {action} (no default description)")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"✓ Update complete!")
    print(f"  Updated: {updated_count} actions")
    if skipped_count > 0:
        print(f"  Skipped: {skipped_count} actions (no default description)")
    print(f"{'='*60}")

if __name__ == '__main__':
    print("Field Trainer - Course Description Update")
    print("=" * 60)

    try:
        update_course_descriptions()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
