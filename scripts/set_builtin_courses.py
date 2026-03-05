#!/usr/bin/env python3
"""
Set built-in courses in the Field Trainer database.
Courses matching the patterns below will be marked as is_builtin = 1.
All others will be marked as is_builtin = 0.
"""

import sqlite3
import sys

DB_PATH = '/opt/data/field_trainer.db'

BUILTIN_PATTERNS = [
    'Warm-up:',
    'Simon Says',
    'Beep Test',
]

def matches_builtin(name):
    return any(name.startswith(p) or p in name for p in BUILTIN_PATTERNS)

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    courses = conn.execute('SELECT course_id, course_name, is_builtin FROM courses ORDER BY course_name').fetchall()

    print(f"{'Course':<35} {'Was':>8} {'Now':>8}")
    print('-' * 55)

    changes = 0
    for row in courses:
        name = row['course_name']
        was = row['is_builtin'] or 0
        now = 1 if matches_builtin(name) else 0

        status = ''
        if was != now:
            conn.execute('UPDATE courses SET is_builtin = ? WHERE course_id = ?', (now, row['course_id']))
            status = '  <-- changed'
            changes += 1

        label_was = 'built-in' if was else 'custom'
        label_now = 'built-in' if now else 'custom'
        print(f"{name:<35} {label_was:>8} {label_now:>8}{status}")

    conn.commit()
    conn.close()

    print()
    print(f"{changes} course(s) updated.")

if __name__ == '__main__':
    main()
