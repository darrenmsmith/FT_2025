"""
Central configuration and tunables.

If you need to change ports, timeouts, or file paths, do it here.
Prefer environment overrides where sensible.
"""

import os

# Network
HOST: str = os.getenv("FIELD_TRAINER_HOST", "0.0.0.0")
HEARTBEAT_TCP_PORT: int = int(os.getenv("FIELD_TRAINER_HEARTBEAT_PORT", "6000"))

# Timeouts / thresholds
OFFLINE_SECS: int = int(os.getenv("FIELD_TRAINER_OFFLINE_SECS", "15"))
READ_TIMEOUT_SECS: float = float(os.getenv("FIELD_TRAINER_READ_TIMEOUT", "45.0"))

# Logs
LOG_MAX: int = int(os.getenv("FIELD_TRAINER_LOG_MAX", "1000"))

# Courses
COURSE_FILE: str = os.getenv("FIELD_TRAINER_COURSE_FILE", "courses.json")
