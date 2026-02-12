# Course SVG Diagrams

This directory contains SVG layout diagrams for Field Trainer courses.

## File Organization

- Each course can have an associated SVG diagram stored here
- Filenames use snake_case based on course names
- Multiple courses can share the same diagram file
- SVG files are version controlled with git (database is not)

## Current Diagrams

| File | Used By | Description |
|------|---------|-------------|
| `warm_up_shared.svg` | Warm-up Rounds 1-3 | Shared 6-cone sequential layout |
| `simon_says_4_colors.svg` | Simon Says - 4 Colors | 4-color pattern layout |
| `course_a.svg` | Course A | Custom layout |
| `course_b.svg` | Course B | Custom layout |

## Managing SVG Diagrams

### Using the SVG Manager Utility

```bash
# List all course-diagram associations
python3 /opt/scripts/svg_manager.py list

# Export all SVGs from database to files
python3 /opt/scripts/svg_manager.py export

# Import/Update SVG for a course
python3 /opt/scripts/svg_manager.py import "Course Name" path/to/diagram.svg
```

### Using the Web Interface

1. Go to http://192.168.7.116:5001/courses/design
2. Create or edit a course
3. Use the SVG editor in the "Course Diagram" section
4. Save the course - SVG is automatically saved to this directory

### Manual File Management

1. Create your SVG file (any SVG editor)
2. Save it to `/opt/static/svg/courses/your_diagram.svg`
3. Update database to reference it:
   ```sql
   UPDATE courses 
   SET diagram_svg = 'your_diagram.svg' 
   WHERE course_name = 'Your Course';
   ```

## File Naming Convention

- Use lowercase with underscores
- Match course name: "Simon Says - 4 Colors" → `simon_says_4_colors.svg`
- Shared diagrams: Use descriptive name like `warm_up_shared.svg`

## Git Tracking

✅ **SVG files ARE tracked** by git - commit and push changes  
❌ **Database is NOT tracked** - only SVG files are version controlled

This keeps your diagrams in version control while excluding runtime data.
