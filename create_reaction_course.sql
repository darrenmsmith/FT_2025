-- Create Reaction Sprint Course
-- Run this SQL script to add the Reaction Sprint course to the database

-- Insert course (ID 13)
INSERT INTO courses (
    course_id,
    course_name,
    course_type,
    category,
    num_devices,
    mode,
    is_builtin,
    description
) VALUES (
    13,
    'Reaction',
    'reaction_sprint',
    'agility',
    6,
    'pattern',
    0,
    'Random reaction sprint drill. Touch all 5 cones as fast as possible. Each cone can only be touched once per run. 10 second timeout per cone.'
);

-- Insert course actions for all 6 devices (D0 + C1-C5)
INSERT INTO course_actions (course_id, device_id, device_name, sequence, action, behavior_config)
VALUES
    (13, '192.168.99.100', 'Device 0 (Start)', 0, 'beep', '{"drill_type": "reaction", "timeout_seconds": 10}'),
    (13, '192.168.99.101', 'Cone 1', 1, 'beep', '{"drill_type": "reaction"}'),
    (13, '192.168.99.102', 'Cone 2', 2, 'beep', '{"drill_type": "reaction"}'),
    (13, '192.168.99.103', 'Cone 3', 3, 'beep', '{"drill_type": "reaction"}'),
    (13, '192.168.99.104', 'Cone 4', 4, 'beep', '{"drill_type": "reaction"}'),
    (13, '192.168.99.105', 'Cone 5', 5, 'beep', '{"drill_type": "reaction"}');

-- Verify insertion
SELECT 'Course created:' as status;
SELECT * FROM courses WHERE course_id = 13;

SELECT 'Course actions created:' as status;
SELECT * FROM course_actions WHERE course_id = 13 ORDER BY sequence;
