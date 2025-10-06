"""
Server-side AudioManager (optional):
- Plays MP3 clips using `mpg123`
- Simple config: audio_dir, voice_gender, volume
- No dependencies beyond a system `mpg123` binary (sudo apt-get install mpg123)

This mirrors the contributor's device-side philosophy so the same clip
names work on both sides (e.g., "welcome", "pushups", etc.)
"""

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioSettings:
    audio_dir: str = "/opt/field-trainer/audio"
    voice_gender: str = "male"    # or "female"
    volume_percent: int = 80      # 0-100
    config_path: str = "/opt/field-trainer/config/audio_config.json"


class AudioManager:
    def __init__(self, settings: Optional[AudioSettings] = None):
        self.settings = settings or AudioSettings()
        # Load user settings if present
        try:
            if os.path.exists(self.settings.config_path):
                with open(self.settings.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.settings.audio_dir = data.get("audio_dir", self.settings.audio_dir)
                self.settings.voice_gender = data.get("voice_gender", self.settings.voice_gender)
                self.settings.volume_percent = int(data.get("volume_percent", self.settings.volume_percent))
        except Exception:
            pass

    def _clip_path(self, clip_name: str) -> Optional[str]:
        """
        Build a path like: <audio_dir>/<voice_gender>/<clip_name>.mp3
        Falls back to <audio_dir>/<clip_name>.mp3 if gender subfolder missing.
        """
        root = self.settings.audio_dir
        gdir = os.path.join(root, self.settings.voice_gender)
        if os.path.isdir(gdir):
            p = os.path.join(gdir, f"{clip_name}.mp3")
            if os.path.exists(p):
                return p
        # fallback
        p = os.path.join(root, f"{clip_name}.mp3")
        if os.path.exists(p):
            return p
        return None

    def _volume_to_mpg123_scale(self, percent: int) -> int:
        """
        Convert 0-100% to mpg123 -f scale (roughly 0-32768).
        The contributor used -f to attenuate; keep it simple/linear.
        """
        percent = max(0, min(100, percent))
        return int(32768 * (percent / 100.0))

    def play(self, clip_name: str, volume_percent: Optional[int] = None) -> bool:
        """
        Play a clip by logical name (without extension). Returns True if started.
        Requires `mpg123` installed on the controller.
        """
        path = self._clip_path(clip_name)
        if not path:
            return False

        vol = self._volume_to_mpg123_scale(volume_percent if volume_percent is not None else self.settings.volume_percent)
        cmd = f"mpg123 -q -f {vol} {shlex.quote(path)}"
        try:
            # Fire-and-forget so we don't block the server thread
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def set_voice_gender(self, gender: str) -> None:
        if gender in ("male", "female"):
            self.settings.voice_gender = gender
            self._persist()

    def set_volume(self, percent: int) -> None:
        self.settings.volume_percent = max(0, min(100, percent))
        self._persist()

    def _persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.settings.config_path), exist_ok=True)
            with open(self.settings.config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "audio_dir": self.settings.audio_dir,
                    "voice_gender": self.settings.voice_gender,
                    "volume_percent": self.settings.volume_percent
                }, f, indent=2)
        except Exception:
            pass
