-- PYFP course seed — Phase 1
-- 16 rows (spec §7.2 states 14; event catalog + events_registry have 16 — all inserted)
-- category='PYFP' used as secondary filter; main dashboard excludes via course_type LIKE 'pyfp_%'
-- num_devices: 2 for cone-based events, 0 for D0-only events

-- Aerobic capacity
INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - PACER', 'FitnessGram/PFT PACER 20m shuttle (beep test bridge)', 'PYFP', 'sequential', 'pyfp_pacer', 2, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - One-Mile Run', 'FitnessGram/PFT one-mile run with lap counting', 'PYFP', 'sequential', 'pyfp_mile_run', 2, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - One-Mile Walk', 'FitnessGram one-mile walk (coach-observed, no enforcement)', 'PYFP', 'sequential', 'pyfp_mile_walk', 2, 1, '1.0');

-- Muscular strength & endurance
INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Curl-Ups', 'FitnessGram/PFT curl-ups at 3-sec cadence', 'PYFP', 'sequential', 'pyfp_curl_up', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Right-Angle Push-Ups', 'FitnessGram/PFT right-angle push-ups at 3-sec cadence', 'PYFP', 'sequential', 'pyfp_push_up', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Pull-Ups', 'FitnessGram/PFT pull-ups, manual count entry', 'PYFP', 'sequential', 'pyfp_pull_up', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Modified Pull-Ups', 'FitnessGram modified pull-ups, manual count entry', 'PYFP', 'sequential', 'pyfp_modified_pull_up', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Flexed-Arm Hang', 'FitnessGram flexed-arm hang with D0 timer', 'PYFP', 'sequential', 'pyfp_flexed_arm_hang', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Plank', 'PFT plank hold with 30-sec interval cues', 'PYFP', 'sequential', 'pyfp_plank', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Trunk Lift', 'FitnessGram trunk lift, manual measurement entry (max 12 in)', 'PYFP', 'sequential', 'pyfp_trunk_lift', 0, 1, '1.0');

-- Flexibility
INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Back-Saver Sit-and-Reach', 'FitnessGram sit-and-reach, best of 3 per side', 'PYFP', 'sequential', 'pyfp_sit_and_reach', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Shoulder Stretch', 'FitnessGram shoulder stretch, pass/fail per side', 'PYFP', 'sequential', 'pyfp_shoulder_stretch', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - V-Sit Reach', 'FitnessGram v-sit reach alternate, best of 3 signed inches', 'PYFP', 'sequential', 'pyfp_v_sit_reach', 0, 1, '1.0');

-- Agility
INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Shuttle Run (4x30ft)', 'FitnessGram 4x30ft shuttle run with cone timing', 'PYFP', 'sequential', 'pyfp_shuttle_run', 2, 1, '1.0');

-- Body composition
INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - BMI', 'FitnessGram BMI from height + weight form entry', 'PYFP', 'sequential', 'pyfp_bmi', 0, 1, '1.0');

INSERT OR IGNORE INTO courses (course_name, description, category, mode, course_type, num_devices, is_builtin, version)
VALUES ('PYFP - Skinfold', 'FitnessGram skinfold (triceps + calf, Slaughter equation)', 'PYFP', 'sequential', 'pyfp_skinfold', 0, 1, '1.0');
