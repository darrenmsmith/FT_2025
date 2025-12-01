-- Field Trainer Advanced Course Features - SAFE Database Migration
-- Version: 0.5.2-SAFE
-- Date: November 2025
-- Description: Adds support for device functions, detection methods, groups, and behavior configs
-- CRITICAL: Keeps existing courses with NULL values for backwards compatibility

-- Backup command (run before migration):
-- cp /opt/data/field_trainer.db /opt/data/field_trainer.db.backup_$(date +%Y%m%d_%H%M%S)

-- SAFE: Add new columns with NULL defaults (not 'waypoint'/'touch')
-- This ensures existing courses continue using original behavior
ALTER TABLE course_actions ADD COLUMN device_function TEXT DEFAULT NULL
    CHECK(device_function IS NULL OR device_function IN ('start_finish', 'waypoint', 'turnaround', 'boundary', 'timer'));

ALTER TABLE course_actions ADD COLUMN detection_method TEXT DEFAULT NULL
    CHECK(detection_method IS NULL OR detection_method IN ('touch', 'proximity', 'none'));

ALTER TABLE course_actions ADD COLUMN group_identifier TEXT DEFAULT NULL;

ALTER TABLE course_actions ADD COLUMN behavior_config TEXT DEFAULT NULL;

-- DO NOT UPDATE existing courses - let them stay NULL for backwards compatibility
-- Only new advanced courses will have these fields populated

-- Create new table for tracking athlete patterns (for Simon Says and similar games)
CREATE TABLE IF NOT EXISTS athlete_patterns (
    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    athlete_id TEXT NOT NULL,
    course_id INTEGER NOT NULL,
    pattern_type TEXT NOT NULL CHECK(pattern_type IN ('simon_says', 'random_sequence', 'custom')),
    pattern_data TEXT NOT NULL,  -- JSON array of device/color sequences
    difficulty_level INTEGER DEFAULT 3,
    completed BOOLEAN DEFAULT 0,
    completion_time REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (athlete_id) REFERENCES athletes(athlete_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- Create index for faster pattern lookups
CREATE INDEX IF NOT EXISTS idx_athlete_patterns_run ON athlete_patterns(run_id);
CREATE INDEX IF NOT EXISTS idx_athlete_patterns_athlete ON athlete_patterns(athlete_id);

-- Verification queries (run these to check migration success)
-- Verify columns were added:
-- SELECT sql FROM sqlite_master WHERE name = 'course_actions';

-- Verify existing courses have NULL values (CRITICAL):
-- SELECT COUNT(*) as existing_courses_safe FROM course_actions
-- WHERE device_function IS NULL AND detection_method IS NULL AND group_identifier IS NULL AND behavior_config IS NULL;

-- Verify new table was created:
-- SELECT name FROM sqlite_master WHERE type='table' AND name='athlete_patterns';
