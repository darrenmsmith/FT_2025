"""
Central configuration knobs with environment overrides.
Safe defaults are supplied for local dev.
"""

import os

# ---------------- Network / Ports ----------------
HOST: str = os.getenv("FIELD_TRAINER_HOST", "0.0.0.0")
HEARTBEAT_TCP_PORT: int = int(os.getenv("FIELD_TRAINER_HEARTBEAT_PORT", "6000"))

# ---------------- Timeouts / thresholds ----------
OFFLINE_SECS: int = int(os.getenv("FIELD_TRAINER_OFFLINE_SECS", "15"))
READ_TIMEOUT_SECS: float = float(os.getenv("FIELD_TRAINER_READ_TIMEOUT", "45.0"))

# ---------------- Logs ---------------------------
LOG_MAX: int = int(os.getenv("FIELD_TRAINER_LOG_MAX", "1000"))

# ---------------- Courses ------------------------
COURSE_FILE: str = os.getenv("FIELD_TRAINER_COURSE_FILE", "courses.json")

# ---------------- Simon Says / Pattern Mode ------
# Pause (in seconds) BEFORE countdown starts when transitioning between athletes
# Gives time to breathe after chase green/red feedback before next athlete
PAUSE_BETWEEN_ATHLETES: int = int(os.getenv("FIELD_TRAINER_PAUSE_BETWEEN_ATHLETES", "3"))

# Countdown duration (in seconds) for "Next up: Athlete" modal
ATHLETE_COUNTDOWN_DURATION: int = int(os.getenv("FIELD_TRAINER_COUNTDOWN_DURATION", "3"))

# ---------------- LED / Audio / Time Sync --------
AUDIO_CLIPS_DIR: str = os.getenv("FIELD_TRAINER_AUDIO_DIR", "/opt/field_trainer/audio")
TIME_SYNC_DRIFT_MS: int = int(os.getenv("FIELD_TRAINER_TIME_SYNC_DRIFT_MS", "250"))
TIME_SYNC_ON_CONNECT: bool = bool(int(os.getenv("FIELD_TRAINER_TIME_SYNC_ON_CONNECT", "1")))
DEFAULT_LED_PATTERN: str = os.getenv("FIELD_TRAINER_DEFAULT_LED_PATTERN", "off")

# Enable server-side (Device 0) LED driver (requires rpi_ws281x on that host)
ENABLE_SERVER_LED: bool = bool(int(os.getenv("FIELD_TRAINER_ENABLE_SERVER_LED", "0")))
SERVER_LED_PIN: int = int(os.getenv("FIELD_TRAINER_LED_PIN", "18"))
SERVER_LED_COUNT: int = int(os.getenv("FIELD_TRAINER_LED_COUNT", "8"))
SERVER_LED_BRIGHTNESS: int = int(os.getenv("FIELD_TRAINER_LED_BRIGHTNESS", "32"))

# ---------------- Audio (server-side Device 0) ----------------
# Enable controller audio playback via mpg123
ENABLE_SERVER_AUDIO: bool = bool(int(os.getenv("FIELD_TRAINER_ENABLE_SERVER_AUDIO", "0")))

# Optional overrides (ft_audio has sane defaults if you leave these unset)
AUDIO_DIR: str = os.getenv("FIELD_TRAINER_AUDIO_DIR", "/opt/field_trainer/audio")
AUDIO_CONFIG_PATH: str = os.getenv("FIELD_TRAINER_AUDIO_CONFIG", "/opt/field_trainer/config/audio_config.json")
AUDIO_VOICE_GENDER: str = os.getenv("FIELD_TRAINER_AUDIO_GENDER", "male")  # "male" | "female"
AUDIO_VOLUME_PERCENT: int = int(os.getenv("FIELD_TRAINER_AUDIO_VOLUME", "80"))  # 0..100
