#!/usr/bin/env python3
"""
SVG Manager - Import/Export utility for course diagrams
Manages SVG files in /opt/static/svg/courses/
"""

import sqlite3
import os
import re
import sys
from pathlib import Path

SVG_DIR = Path('/opt/static/svg/courses')
DB_PATH = '/opt/data/field_trainer.db'

def sanitize_filename(name):
    """Convert course name to safe filename"""
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[-\s]+', '_', name)
    return f"{name}.svg"

def export_all():
    """Export all SVGs from database to files"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT course_id, course_name, diagram_svg 
        FROM courses 
        WHERE diagram_svg IS NOT NULL AND diagram_svg != ''
    """)
    
    courses = cursor.fetchall()
    conn.close()
    
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    exported = 0
    
    for course_id, course_name, svg_content in courses:
        # Check if it's a filename or content
        if svg_content.endswith('.svg') and len(svg_content) < 100:
            # Already a filename, check if file exists
            filepath = SVG_DIR / svg_content
            if filepath.exists():
                print(f"✓ {course_name}: File already exists ({svg_content})")
                continue
            else:
                print(f"⚠ {course_name}: Referenced file missing ({svg_content})")
                continue
        
        # It's SVG content, export it
        filename = sanitize_filename(course_name)
        filepath = SVG_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        
        # Update database to store filename
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE courses SET diagram_svg = ? WHERE course_id = ?", 
                      (filename, course_id))
        conn.commit()
        conn.close()
        
        print(f"✓ Exported: {course_name} → {filename}")
        exported += 1
    
    print(f"\n✅ Exported {exported} SVG files")
    return exported

def import_course(course_name, svg_file):
    """Import SVG file for a specific course"""
    if not os.path.exists(svg_file):
        print(f"❌ Error: File not found: {svg_file}")
        return False
    
    # Copy to SVG directory
    filename = sanitize_filename(course_name)
    dest_path = SVG_DIR / filename
    
    with open(svg_file, 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE courses 
        SET diagram_svg = ?
        WHERE course_name = ?
    """, (filename, course_name))
    
    if cursor.rowcount == 0:
        conn.close()
        print(f"❌ Error: Course '{course_name}' not found in database")
        return False
    
    conn.commit()
    conn.close()
    
    print(f"✅ Imported: {course_name} → {filename}")
    return True

def list_svgs():
    """List all SVG files and their associations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT course_id, course_name, diagram_svg 
        FROM courses 
        ORDER BY course_id
    """)
    
    courses = cursor.fetchall()
    conn.close()
    
    print("Course SVG Associations:")
    print("-" * 80)
    
    for course_id, course_name, svg_file in courses:
        if svg_file:
            filepath = SVG_DIR / svg_file
            exists = "✓" if filepath.exists() else "✗"
            size = filepath.stat().st_size if filepath.exists() else 0
            print(f"{exists} {course_id:3d}: {course_name:30s} → {svg_file} ({size} bytes)")
        else:
            print(f"  {course_id:3d}: {course_name:30s} → (no diagram)")

def main():
    if len(sys.argv) < 2:
        print("SVG Manager - Course Diagram Utility")
        print("\nUsage:")
        print("  svg_manager.py export              - Export all SVGs from database")
        print("  svg_manager.py import <course> <file> - Import SVG for course")
        print("  svg_manager.py list                - List all SVG associations")
        print("\nExamples:")
        print("  svg_manager.py export")
        print("  svg_manager.py import 'Simon Says - 4 Colors' my_diagram.svg")
        print("  svg_manager.py list")
        return
    
    command = sys.argv[1]
    
    if command == 'export':
        export_all()
    elif command == 'list':
        list_svgs()
    elif command == 'import':
        if len(sys.argv) < 4:
            print("❌ Error: import requires course name and file path")
            print("Usage: svg_manager.py import <course_name> <svg_file>")
            return
        course_name = sys.argv[2]
        svg_file = sys.argv[3]
        import_course(course_name, svg_file)
    else:
        print(f"❌ Unknown command: {command}")
        print("Use: export, import, or list")

if __name__ == '__main__':
    main()
