-- PYFP schema — Phase 1
-- Per FT convention: TEXT timestamps via Python isoformat(), not CURRENT_TIMESTAMP
-- Per FT convention: TEXT athlete_id (ATH-2025-NNNN), gender lowercase ('male'/'female')
-- Create pyfp_scoring_table_version first — referenced by pyfp_assessment_battery

CREATE TABLE IF NOT EXISTS pyfp_scoring_table_version (
    version_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    rubric             TEXT NOT NULL,
    source_url         TEXT,
    effective_from     TEXT,
    json_path          TEXT NOT NULL,
    is_default         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pyfp_assessment_battery (
    battery_id          TEXT PRIMARY KEY,
    athlete_id          TEXT NOT NULL REFERENCES athletes(athlete_id),
    school_year         TEXT NOT NULL,
    test_window         TEXT NOT NULL CHECK (test_window IN ('fall','spring')),
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    age_at_test         INTEGER NOT NULL,
    gender              TEXT NOT NULL CHECK (gender IN ('female','male')),
    rubric              TEXT NOT NULL CHECK (rubric IN ('fitnessgram_hfz','pft_2026','both')),
    scoring_table_id    INTEGER REFERENCES pyfp_scoring_table_version(version_id),
    notes               TEXT,
    UNIQUE (athlete_id, school_year, test_window)
);

CREATE TABLE IF NOT EXISTS pyfp_event_result (
    event_result_id        TEXT PRIMARY KEY,
    battery_id             TEXT NOT NULL REFERENCES pyfp_assessment_battery(battery_id) ON DELETE CASCADE,
    course_type            TEXT NOT NULL,
    raw_value              REAL NOT NULL,
    raw_unit               TEXT NOT NULL,
    secondary_value        REAL,
    attempt_number         INTEGER DEFAULT 1,
    recorded_at            TEXT NOT NULL,
    beep_test_session_id   TEXT REFERENCES beep_test_sessions(session_id),
    sessions_session_id    TEXT REFERENCES sessions(session_id),
    run_id                 TEXT REFERENCES runs(run_id),
    is_best                INTEGER DEFAULT 1,
    notes                  TEXT,
    UNIQUE (battery_id, course_type, attempt_number)
);

CREATE TABLE IF NOT EXISTS pyfp_cone_assignment (
    assignment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    event_result_id    TEXT NOT NULL REFERENCES pyfp_event_result(event_result_id) ON DELETE CASCADE,
    role               TEXT NOT NULL,
    device_id          TEXT NOT NULL,
    distance_m         REAL,
    UNIQUE (event_result_id, role, device_id)
);

CREATE TABLE IF NOT EXISTS pyfp_award (
    award_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id         TEXT NOT NULL REFERENCES pyfp_assessment_battery(battery_id) ON DELETE CASCADE,
    award_type         TEXT NOT NULL,
    awarded_at         TEXT NOT NULL,
    criteria_met       TEXT NOT NULL,
    UNIQUE (battery_id, award_type)
);

CREATE INDEX IF NOT EXISTS idx_pyfp_battery_athlete ON pyfp_assessment_battery(athlete_id);
CREATE INDEX IF NOT EXISTS idx_pyfp_battery_year    ON pyfp_assessment_battery(school_year, test_window);
CREATE INDEX IF NOT EXISTS idx_pyfp_result_battery  ON pyfp_event_result(battery_id);
CREATE INDEX IF NOT EXISTS idx_pyfp_result_beep     ON pyfp_event_result(beep_test_session_id);
CREATE INDEX IF NOT EXISTS idx_pyfp_cone_event      ON pyfp_cone_assignment(event_result_id);
