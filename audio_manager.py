"""
Audio Manager for Field Trainer System
Handles MP3 playback through MAX98357A I2S amplifier
"""

import os
import subprocess
import logging
import json
from pathlib import Path
from threading import Thread, Lock
import time

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages audio playback through I2S amplifier (MAX98357A)"""
    
    def __init__(self, audio_dir="/opt/field-trainer/audio", 
                 config_file="/opt/field-trainer/config/audio_config.json",
                 default_volume=60):
        """
        Initialize audio manager
        
        Args:
            audio_dir: Directory containing MP3 files
            config_file: Path to audio configuration file
            default_volume: Default volume level (0-100) - Note: Currently runs at full volume
        """
        self.audio_dir = Path(audio_dir)
        self.config_file = Path(config_file)
        self.default_volume = default_volume
        self.current_volume = default_volume
        self.voice_gender = "female"  # Default voice ('male' or 'female')
        self.playback_lock = Lock()
        self.current_process = None
        
        # Ensure audio directory exists
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create configuration
        self._load_config()
        
        # Verify I2S audio device is available
        self._verify_audio_device()
        
        logger.info(f"AudioManager initialized - Volume: {self.current_volume}%, Voice: {self.voice_gender}")
    
    def _load_config(self):
        """Load audio configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.current_volume = config.get('volume', self.default_volume)
                    self.voice_gender = config.get('voice_gender', 'female')
                    logger.info(f"Loaded audio config: volume={self.current_volume}, voice={self.voice_gender}")
            else:
                # Create default config
                self._save_config()
        except Exception as e:
            logger.error(f"Error loading audio config: {e}")
            # Use defaults
    
    def _save_config(self):
        """Save current audio configuration to file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                'volume': self.current_volume,
                'voice_gender': self.voice_gender
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.debug(f"Saved audio config: {config}")
        except Exception as e:
            logger.error(f"Error saving audio config: {e}")
    
    def _verify_audio_device(self):
        """Verify I2S audio device is available"""
        try:
            # Check if I2S device exists in ALSA
            result = subprocess.run(['aplay', '-L'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            
            if 'snd_rpi_i2s' in result.stdout or 'default' in result.stdout:
                logger.info("I2S audio device detected")
                return True
            else:
                logger.warning("I2S audio device not found in ALSA output")
                return False
        except Exception as e:
            logger.error(f"Error verifying audio device: {e}")
            return False
    
    def _get_audio_path(self, filename):
        """
        Get full path to audio file, accounting for voice gender
        
        Args:
            filename: Name of audio file (e.g., 'butt_kicks.mp3')
        
        Returns:
            Path object to audio file, or None if not found
        """
        # Try voice-specific directory first
        voice_path = self.audio_dir / self.voice_gender / filename
        if voice_path.exists():
            return voice_path
        
        # Fall back to root audio directory
        root_path = self.audio_dir / filename
        if root_path.exists():
            return root_path
        
        # Try opposite gender as final fallback
        other_gender = "male" if self.voice_gender == "female" else "female"
        other_path = self.audio_dir / other_gender / filename
        if other_path.exists():
            logger.warning(f"Using {other_gender} voice for {filename} (preferred {self.voice_gender} not found)")
            return other_path
        
        return None
    
    def play(self, filename, blocking=False, callback=None):
        """
        Play an audio file
        
        Args:
            filename: Name of MP3 file to play (e.g., 'butt_kicks.mp3')
            blocking: If True, wait for playback to complete
            callback: Optional function to call when playback completes
        
        Returns:
            bool: True if playback started successfully, False otherwise
        """
        audio_path = self._get_audio_path(filename)
        
        if audio_path is None:
            logger.error(f"Audio file not found: {filename}")
            # Play default beep as fallback
            return self._play_default_beep(blocking, callback)
        
        if blocking:
            return self._play_sync(audio_path)
        else:
            return self._play_async(audio_path, callback)
    
    def _play_sync(self, audio_path):
        """Play audio file synchronously (blocking) with volume control"""
        try:
            # Stop any currently playing audio
            self.stop()
            
            # Calculate volume scaling for mpg123 -f parameter
            # Range: -32768 to 32767, where 32767 is maximum volume
            # We map 0-100% to 0-32767
            volume_scale = int((self.current_volume / 100.0) * 32767)
            
            # Play using mpg123 with I2S device
            cmd = [
                'mpg123',
                '-q',  # Quiet mode
                '-a', 'default',  # Use default ALSA device (I2S)
                '-f', str(volume_scale),  # Volume control via output scaling
                str(audio_path)
            ]
            
            with self.playback_lock:
                self.current_process = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30  # 30 second timeout
                )
                self.current_process = None
            
            logger.debug(f"Played audio (sync): {audio_path.name}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Audio playback timeout: {audio_path.name}")
            self.stop()
            return False
        except Exception as e:
            logger.error(f"Error playing audio {audio_path.name}: {e}")
            return False
    
    def _play_async(self, audio_path, callback=None):
        """Play audio file asynchronously (non-blocking)"""
        def play_thread():
            success = self._play_sync(audio_path)
            if callback:
                try:
                    callback(success)
                except Exception as e:
                    logger.error(f"Error in audio callback: {e}")
        
        try:
            thread = Thread(target=play_thread, daemon=True)
            thread.start()
            return True
        except Exception as e:
            logger.error(f"Error starting audio playback thread: {e}")
            return False
    
    def _play_default_beep(self, blocking=False, callback=None):
        """Play default beep sound when audio file is missing"""
        beep_path = self.audio_dir / 'default_beep.mp3'
        
        if not beep_path.exists():
            logger.error("Default beep file not found")
            # Generate beep using speaker-test as last resort
            return self._generate_beep()
        
        if blocking:
            return self._play_sync(beep_path)
        else:
            return self._play_async(beep_path, callback)
    
    def _generate_beep(self):
        """Generate a simple beep using speaker-test"""
        try:
            subprocess.run(
                ['speaker-test', '-t', 'sine', '-f', '1000', '-l', '1', '-c', '2'],
                capture_output=True,
                timeout=2
            )
            logger.debug("Generated fallback beep")
            return True
        except Exception as e:
            logger.error(f"Error generating beep: {e}")
            return False
    
    def stop(self):
        """Stop currently playing audio"""
        try:
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
                self.current_process.wait(timeout=1)
                logger.debug("Stopped audio playback")
        except Exception as e:
            logger.error(f"Error stopping audio: {e}")
    
    def set_volume(self, volume):
        """
        Set playback volume (0-100%)
        
        Args:
            volume: Volume level (0-100)
        
        Returns:
            bool: True if successful
        """
        try:
            volume = max(0, min(100, int(volume)))  # Clamp to 0-100
            self.current_volume = volume
            self._save_config()
            logger.info(f"Volume set to {self.current_volume}%")
            return True
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False
    
    def get_volume(self):
        """Get current volume level preference"""
        return self.current_volume
    
    def set_voice_gender(self, gender):
        """
        Set voice gender preference
        
        Args:
            gender: 'male' or 'female'
        
        Returns:
            bool: True if successful
        """
        if gender.lower() not in ['male', 'female']:
            logger.error(f"Invalid voice gender: {gender}")
            return False
        
        self.voice_gender = gender.lower()
        self._save_config()
        logger.info(f"Voice gender set to {self.voice_gender}")
        return True
    
    def get_voice_gender(self):
        """Get current voice gender preference"""
        return self.voice_gender
    
    def test_playback(self):
        """Test audio playback with a sample file"""
        test_file = 'default_beep.mp3'
        logger.info(f"Testing audio playback with {test_file}")
        return self.play(test_file, blocking=True)
    
    def list_available_audio(self):
        """
        List all available audio files
        
        Returns:
            dict: Audio files organized by gender and root directory
        """
        audio_files = {
            'male': [],
            'female': [],
            'root': []
        }
        
        try:
            # Check root directory
            for file in self.audio_dir.glob('*.mp3'):
                audio_files['root'].append(file.name)
            
            # Check male directory
            male_dir = self.audio_dir / 'male'
            if male_dir.exists():
                for file in male_dir.glob('*.mp3'):
                    audio_files['male'].append(file.name)
            
            # Check female directory
            female_dir = self.audio_dir / 'female'
            if female_dir.exists():
                for file in female_dir.glob('*.mp3'):
                    audio_files['female'].append(file.name)
            
            logger.debug(f"Available audio files: {audio_files}")
            return audio_files
            
        except Exception as e:
            logger.error(f"Error listing audio files: {e}")
            return audio_files
    
    def validate_audio_file(self, filename):
        """
        Check if an audio file exists and is accessible
        
        Args:
            filename: Name of audio file
        
        Returns:
            tuple: (exists: bool, path: str or None)
        """
        audio_path = self._get_audio_path(filename)
        if audio_path:
            return (True, str(audio_path))
        return (False, None)
