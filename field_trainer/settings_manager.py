#!/usr/bin/env python3
"""
Settings Manager for Field Trainer
Handles system settings and device configurations
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional


class SettingsManager:
    """Manages system settings and device configurations"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.audio_dir = '/opt/field_trainer/audio'
        self.config_dir = '/opt/field_trainer/config'

        # Ensure directories exist
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)

    def load_settings(self) -> Dict[str, str]:
        """Load all settings as dictionary"""
        with self.db.get_connection() as conn:
            cursor = conn.execute('SELECT setting_key, setting_value FROM settings')
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_setting(self, key: str) -> Optional[str]:
        """Get single setting value"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                'SELECT setting_value FROM settings WHERE setting_key = ?',
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def save_setting(self, key: str, value: str) -> bool:
        """Save single setting, update timestamp"""
        try:
            with self.db.get_connection() as conn:
                conn.execute('''
                    INSERT INTO settings (setting_key, setting_value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(setting_key) DO UPDATE SET
                        setting_value = excluded.setting_value,
                        updated_at = excluded.updated_at
                ''', (key, value, datetime.utcnow().isoformat()))
            return True
        except Exception as e:
            print(f"Error saving setting {key}: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Reset all settings to defaults"""
        default_settings = {
            'distance_unit': 'yards',
            'voice_gender': 'male',
            'system_volume': '60',
            'ready_audio_file': 'default.mp3',
            'min_travel_time': '1',
            'max_travel_time': '15',
            'ready_led_color': 'orange',
            'ready_audio_target': 'all',
            'wifi_ssid': '',
            'wifi_password': ''
        }

        try:
            with self.db.get_connection() as conn:
                # Delete all existing settings
                conn.execute('DELETE FROM settings')

                # Insert defaults
                for key, value in default_settings.items():
                    conn.execute('''
                        INSERT INTO settings (setting_key, setting_value)
                        VALUES (?, ?)
                    ''', (key, value))
            return True
        except Exception as e:
            print(f"Error resetting settings: {e}")
            return False

    def get_audio_files(self) -> List[str]:
        """Scan audio directory for .mp3/.wav files from voice subdirectories"""
        if not os.path.exists(self.audio_dir):
            return []

        files = []

        # Scan male and female subdirectories (where actual audio files live)
        for gender in ['male', 'female']:
            gender_dir = os.path.join(self.audio_dir, gender)
            if os.path.exists(gender_dir):
                for filename in os.listdir(gender_dir):
                    if filename.endswith(('.mp3', '.wav')):
                        # Only add if not already in list (avoid duplicates)
                        if filename not in files:
                            files.append(filename)

        # Also scan root directory for any standalone files (like default_beep.mp3)
        for filename in os.listdir(self.audio_dir):
            filepath = os.path.join(self.audio_dir, filename)
            if os.path.isfile(filepath) and filename.endswith(('.mp3', '.wav')):
                # Only include if file has content (not empty)
                if os.path.getsize(filepath) > 0 and filename not in files:
                    files.append(filename)

        return sorted(files)

    def get_root_audio_files(self) -> List[str]:
        """Get only audio files from root directory (for ready notifications, beeps, etc.)"""
        if not os.path.exists(self.audio_dir):
            return []

        files = []

        # Only scan root directory (not subdirectories)
        for filename in os.listdir(self.audio_dir):
            filepath = os.path.join(self.audio_dir, filename)
            if os.path.isfile(filepath) and filename.endswith(('.mp3', '.wav')):
                # Only include if file has content (not empty)
                if os.path.getsize(filepath) > 0:
                    files.append(filename)

        return sorted(files)

    def get_device_threshold(self, device_id: str) -> Dict:
        """Read device threshold from config JSON"""
        device_num = device_id.split('.')[-1]
        config_path = os.path.join(self.config_dir, f'touch_cal_device{device_num}.json')

        if not os.path.exists(config_path):
            return {
                'exists': False,
                'threshold': None,
                'last_calibrated': None
            }

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {
                'exists': True,
                'threshold': config.get('threshold'),
                'last_calibrated': config.get('last_calibrated')
            }
        except Exception as e:
            print(f"Error reading threshold for {device_id}: {e}")
            return {
                'exists': False,
                'threshold': None,
                'last_calibrated': None,
                'error': str(e)
            }

    def set_device_threshold(self, device_id: str, threshold: float) -> bool:
        """Write threshold to device config JSON"""
        device_num = device_id.split('.')[-1]
        config_path = os.path.join(self.config_dir, f'touch_cal_device{device_num}.json')

        try:
            # Read existing config or create new
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {
                    'baseline': {'x': 0, 'y': 0, 'z': 1.0}
                }

            # Update threshold and timestamp
            config['threshold'] = threshold
            config['last_calibrated'] = datetime.utcnow().isoformat()

            # Write back
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            return True
        except Exception as e:
            print(f"Error setting threshold for {device_id}: {e}")
            return False

    def check_device_online(self, device_id: str) -> bool:
        """Check if device is reachable via REGISTRY or ping"""
        # First check REGISTRY for faster response
        try:
            from field_trainer.ft_registry import REGISTRY
            if device_id in REGISTRY.nodes:
                node = REGISTRY.nodes[device_id]
                return node.status not in ('Offline', 'Unknown')
        except Exception:
            pass

        # Fall back to ping
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', device_id],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False
