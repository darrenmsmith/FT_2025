#!/usr/bin/env python3
"""
Field Trainer Client with LED Control
Connects to Device 0 and manages local LED hardware
"""

import os
import socket
import json
import time
import sys
sys.path.insert(0, '/opt/field_trainer')
sys.path.insert(0, '/opt')
from ft_touch import TouchSensor
try:
    from sonar_sensor import SonarSensor
    SONAR_AVAILABLE = True
except ImportError:
    SONAR_AVAILABLE = False
    print("⚠ sonar_sensor module not found — proximity detection unavailable")
import argparse
from audio_manager import AudioManager
from enum import Enum

print("Imports successful")

class LEDState(Enum):
    """LED status states matching server"""
    OFF = "off"
    MESH_CONNECTED = "mesh_connected"      # Orange solid
    COURSE_DEPLOYED = "course_deployed"    # Blue solid
    COURSE_ACTIVE = "course_active"        # Green solid
    SOFTWARE_ERROR = "software_error"      # Red solid
    NETWORK_ERROR = "network_error"        # Red blinking
    COURSE_COMPLETE = "course_complete"    # Rainbow animation
    # Simon Says solid color states
    SOLID_RED = "solid_red"
    SOLID_GREEN = "solid_green"
    SOLID_BLUE = "solid_blue"
    SOLID_YELLOW = "solid_yellow"
    SOLID_WHITE = "solid_white"
    SOLID_PURPLE = "solid_purple"
    SOLID_CYAN = "solid_cyan"
    # Simon Says chase animation states
    CHASE_RED = "chase_red"
    CHASE_GREEN = "chase_green"
    CHASE_BLUE = "chase_blue"
    CHASE_YELLOW = "chase_yellow"
    CHASE_AMBER = "chase_amber"
    CHASE_WHITE = "chase"
    CHASE_PURPLE = "chase_purple"

class ClientLEDManager:
    """Client-side LED management"""

    def __init__(self):
        self.led_enabled = False
        self.strip = None
        self.current_state = LEDState.OFF
        self.blink_state = False
        self.animation_running = False  # Flag to prevent LED changes during animations
        self.pending_state = None  # State to apply after animation completes
        self.chase_pattern = 'alternating'  # Default chase pattern

        # Initialize LED hardware
        try:
            from rpi_ws281x import PixelStrip, Color
            self.Color = Color
            self.strip = PixelStrip(15, 12, 800000, 10, False, 128, 0)
            self.strip.begin()
            self.led_enabled = True
            print("LED hardware initialized")
            self.set_state(LEDState.MESH_CONNECTED)
        except ImportError:
            print("LED: rpi_ws281x not available")
        except Exception as e:
            print(f"LED hardware init failed: {e}")

    def set_state(self, state: LEDState):
        """Set LED state"""
        if not self.led_enabled:
            return

        # Store pending LED commands during chase animations (except for new chase commands)
        if self.animation_running and state not in [LEDState.CHASE_RED, LEDState.CHASE_GREEN,
                                                      LEDState.CHASE_BLUE, LEDState.CHASE_YELLOW,
                                                      LEDState.CHASE_AMBER, LEDState.CHASE_WHITE,
                                                      LEDState.CHASE_PURPLE]:
            self.pending_state = state
            print(f"⏸️  Storing LED command for after animation: {state.value}")
            return

        self.current_state = state

        try:
            if state == LEDState.OFF:
                color = self.Color(0, 0, 0)
            elif state == LEDState.MESH_CONNECTED:
                color = self.Color(255, 165, 0)  # Orange
            elif state == LEDState.COURSE_DEPLOYED:
                color = self.Color(0, 0, 255)    # Blue
            elif state == LEDState.COURSE_ACTIVE:
                color = self.Color(0, 255, 0)    # Green
            elif state == LEDState.SOFTWARE_ERROR:
                color = self.Color(255, 0, 0)    # Red
            elif state == LEDState.NETWORK_ERROR:
                color = self.Color(255, 0, 0)    # Red
            elif state == LEDState.COURSE_COMPLETE:
                color = self.Color(128, 0, 255)  # Purple
            # Simon Says colors
            elif state == LEDState.SOLID_RED:
                color = self.Color(255, 0, 0)    # Red
            elif state == LEDState.SOLID_GREEN:
                color = self.Color(0, 255, 0)    # Green
            elif state == LEDState.SOLID_BLUE:
                color = self.Color(0, 0, 255)    # Blue
            elif state == LEDState.SOLID_YELLOW:
                color = self.Color(255, 255, 0)  # Yellow
            elif state == LEDState.SOLID_WHITE:
                color = self.Color(255, 255, 255)  # White
            elif state == LEDState.SOLID_PURPLE:
                color = self.Color(128, 0, 255)  # Purple
            elif state == LEDState.SOLID_CYAN:
                color = self.Color(0, 255, 255)  # Cyan
            # Simon Says chase animations
            elif state in [LEDState.CHASE_RED, LEDState.CHASE_GREEN, LEDState.CHASE_BLUE,
                          LEDState.CHASE_YELLOW, LEDState.CHASE_AMBER, LEDState.CHASE_WHITE,
                          LEDState.CHASE_PURPLE]:
                # Chase patterns are animated - start the animation
                self._start_chase_animation(state)
                return  # Animation handles its own display
            else:
                color = self.Color(0, 0, 0)

            # Set all LEDs to the color
            for i in range(15):
                self.strip.setPixelColor(i, color)
            self.strip.show()

            print(f"LED state set to {state.value}")

        except Exception as e:
            print(f"LED update error: {e}")

    def _start_chase_animation(self, state: LEDState):
        """Start a chase animation in a background thread"""
        import threading

        # Map chase state to color
        chase_colors = {
            LEDState.CHASE_RED: self.Color(255, 0, 0),
            LEDState.CHASE_GREEN: self.Color(0, 255, 0),
            LEDState.CHASE_BLUE: self.Color(0, 0, 255),
            LEDState.CHASE_YELLOW: self.Color(255, 255, 0),
            LEDState.CHASE_AMBER: self.Color(255, 165, 0),
            LEDState.CHASE_WHITE: self.Color(255, 255, 255),
            LEDState.CHASE_PURPLE: self.Color(128, 0, 255)
        }

        color = chase_colors.get(state, self.Color(255, 255, 255))

        def alternating_pattern():
            """Pattern 1: Alternating LEDs (odd/even switching)"""
            cycles = 10  # Number of alternations
            delay = 0.15  # seconds per cycle

            for cycle in range(cycles):
                # Clear all LEDs
                for i in range(15):
                    self.strip.setPixelColor(i, self.Color(0, 0, 0))

                # Light up even LEDs (0, 2, 4, 6, ...)
                if cycle % 2 == 0:
                    for i in range(0, 15, 2):
                        self.strip.setPixelColor(i, color)
                # Light up odd LEDs (1, 3, 5, 7, ...)
                else:
                    for i in range(1, 15, 2):
                        self.strip.setPixelColor(i, color)

                self.strip.show()
                time.sleep(delay)

            # Clear at end
            for i in range(15):
                self.strip.setPixelColor(i, self.Color(0, 0, 0))
            self.strip.show()

        def triple_flash_pattern():
            """Pattern 2: Triple Flash (all LEDs flash 3 times)"""
            flashes = 3
            on_time = 0.1  # seconds
            off_time = 0.1  # seconds

            for flash in range(flashes):
                # All on
                for i in range(15):
                    self.strip.setPixelColor(i, color)
                self.strip.show()
                time.sleep(on_time)

                # All off
                for i in range(15):
                    self.strip.setPixelColor(i, self.Color(0, 0, 0))
                self.strip.show()
                time.sleep(off_time)

        def animate():
            """Run chase animation based on configured pattern"""
            self.animation_running = True  # Block LED commands during animation
            print(f"Starting chase animation: {state.value}")
            try:
                # Get chase pattern from settings (default to alternating)
                pattern = getattr(self, 'chase_pattern', 'alternating')

                if pattern == 'triple_flash':
                    triple_flash_pattern()
                else:  # default to alternating
                    alternating_pattern()

                print(f"Chase animation complete: {state.value}")

            except Exception as e:
                print(f"Chase animation error: {e}")
            finally:
                self.animation_running = False  # Re-enable LED commands
                print(f"✓ Animation lock released")

                # Apply pending LED state if one was received during animation
                if self.pending_state:
                    print(f"▶️  Applying pending LED command: {self.pending_state.value}")
                    pending = self.pending_state
                    self.pending_state = None
                    self.set_state(pending)

        # Run animation in background thread
        thread = threading.Thread(target=animate, daemon=True)
        thread.start()

    def process_led_command(self, led_command):
        """Process LED command from server"""
        if not led_command or not self.led_enabled:
            return

        try:
            # Update chase pattern if provided
            if 'chase_pattern' in led_command:
                pattern = led_command['chase_pattern']
                if pattern in ['alternating', 'triple_flash']:
                    self.chase_pattern = pattern
                    print(f"Chase pattern updated to: {pattern}")

            state_name = led_command.get("state", "off")
            led_state = LEDState(state_name)
            self.set_state(led_state)
        except ValueError:
            print(f"Unknown LED state: {state_name}")
        except Exception as e:
            print(f"LED command error: {e}")


# Global variable to track last touch event (Phase 1)
last_touch_time = 0

def touch_detected_callback(audio_manager, current_action):
    """Callback function when touch is detected"""
    global last_touch_time
    current_time = time.time()
    last_touch_time = current_time  # Record touch timestamp for heartbeat
    print(f"Touch detected at {current_time:.3f}")

    # Play audio for current action
    if current_action:
        audio_file = f"{current_action}.mp3"
        print(f"Playing audio: {audio_file}")
        audio_manager.play(audio_file, blocking=False)
    else:
        print("No action assigned, playing default beep")
        audio_manager.play("default_beep.mp3", blocking=False)

def connect_to_device0(node_id):
    """Connect to Device 0 with LED support"""
    print("Starting client connection...")
    led_manager = ClientLEDManager()
    print("LED manager created")

    # Initialize audio manager
    audio_manager = AudioManager(audio_dir="/opt/field_trainer/audio")
    print("Audio manager initialized")

    # Initialize touch sensor
    touch_sensor = TouchSensor(node_id)
    print(f"Touch sensor created for {node_id}")
    print(f"Touch sensor hardware available: {touch_sensor.hardware_available}")

    # Initialize sonar sensor (GPIO only allocated when active)
    sonar_sensor = SonarSensor(device_id=node_id) if SONAR_AVAILABLE else None
    if sonar_sensor:
        sonar_sensor.set_detection_callback(lambda: touch_detected_callback(audio_manager, current_action[0]))
        # Load saved sonar config if it exists
        ip_suffix = node_id.split('.')[-1]
        _sonar_config_file = f"/opt/field_trainer/config/sonar_config_device{ip_suffix}.json"
        if os.path.exists(_sonar_config_file):
            try:
                with open(_sonar_config_file, 'r') as f:
                    _sc = json.load(f)
                if 'threshold_cm' in _sc:
                    sonar_sensor.set_threshold(_sc['threshold_cm'])
                if 'read_interval_s' in _sc:
                    sonar_sensor.set_read_interval(_sc['read_interval_s'])
                if 'confirm_readings' in _sc:
                    sonar_sensor.set_confirm_readings(_sc['confirm_readings'])
                print(f"Sonar config loaded: threshold={sonar_sensor.threshold_cm}cm, "
                      f"interval={int(sonar_sensor.read_interval_s*1000)}ms, "
                      f"confirm={sonar_sensor.confirm_readings}")
            except Exception as e:
                print(f"Failed to load sonar config: {e}")
        print("Sonar sensor initialized (GPIO not yet allocated)")

    # Track current action assignment (use list for mutable reference in lambda)
    current_action = [None]
    touch_detection_active = [False]
    sonar_detection_active = [False]
    current_detection_method = ['touch']  # 'touch' | 'proximity' | 'none'
    test_mode_active = [False]  # True while calibration test mode is running
    sonar_test_active = [False]  # True while sonar test mode is running (from settings page)
    ir_armed = [False]           # True while IR sensor is armed for sprint finish detection
    ir_test_active = [False]     # True while IR test mode active (settings page)
    ir_trip_pending = [False]    # Set by IR callback to send immediate trip message
    ir_trip_event = __import__('threading').Event()  # Interrupts heartbeat sleep on trip
    _ir_test_break_count = [0]       # Number of beam breaks detected during test mode
    _ir_test_last_break_ts = [None]  # Epoch timestamp of most recent test-mode beam break
    _beam_ok_misses = [0]     # consecutive heartbeats where beam appears broken
    _beam_ok_streak = [0]    # consecutive heartbeats where beam appears intact (used to clear lost state)
    _beam_lost      = [False] # latched True once BEAM_LOST_MISSES reached; clears only after BEAM_RESTORE_STREAK
    _post_test_suppress = [False]  # True after IR test stops; suppresses beam errors until first athlete completes
    BEAM_LOST_MISSES    = 3  # consecutive broken reads to declare lost  (~15s at 5s heartbeat)
    BEAM_RESTORE_STREAK = 3  # consecutive intact reads to declare restored (~15s at 5s heartbeat)
    _last_clock_sync = [0.0]     # epoch of last clock correction — rate-limit to once/minute
    _clock_sync_pending = [False]  # True = sync requested (e.g. at deploy); use next fresh master_time
    heartbeat_interval = [5]  # Default 5 seconds, can be changed by deployment

    # Load per-device IR config (sensor_type / role)
    _ir_config = {'sensor_type': 'mh_flying_fish', 'role': 'receiver', 'gpio_pin': 17,
                  'enabled': True, 'debounce_ms': 200}
    try:
        import json as _json
        _ip_suffix = node_id.split('.')[-1]
        _cfg_path = f'/opt/field_trainer/config/ir_config_device{_ip_suffix}.json'
        with open(_cfg_path) as _f:
            _ir_config.update(_json.load(_f))
        print(f"IR config loaded: type={_ir_config['sensor_type']}, role={_ir_config['role']}")
    except FileNotFoundError:
        print("No IR config file — using defaults (mh_flying_fish / receiver)")
    except Exception as _e:
        print(f"IR config load error: {_e}")

    # Initialise IR sensor (GPIO 17)
    ir_sensor = None
    try:
        from ft_ir import IrSensor as _IrSensorClass, _load_ir_config, ROLE_EMITTER
        ir_sensor = _IrSensorClass(
            gpio_pin=_ir_config.get('gpio_pin', 17),
            sensor_type=_ir_config.get('sensor_type', 'mh_flying_fish'),
            role=_ir_config.get('role', 'receiver'),
            debounce_s=_ir_config.get('debounce_ms', 200) / 1000.0,
        )
        print(f"IR sensor initialized: type={ir_sensor.sensor_type}, role={ir_sensor.role}, available={ir_sensor.available}")
    except Exception as _e:
        print(f"IR sensor not available: {_e}")

    # Set touch callback with audio manager and current action
    touch_sensor.set_touch_callback(lambda: touch_detected_callback(audio_manager, current_action[0]))
    print("Touch sensor initialized (detection disabled until course deployed)")

    ir_trip_time = [None]  # Timestamp captured at the exact moment of beam break

    def _on_ir_trip(trip_time):
        """Fires from gpiozero callback thread when beam breaks while armed."""
        if ir_armed[0]:
            ir_armed[0] = False  # Disarm immediately — prevent any double-count
            ir_trip_time[0] = trip_time
            audio_manager.play("default_beep.mp3", blocking=False)
            ir_trip_pending[0] = True
            ir_trip_event.set()
            print("🚦 IR trip — sending to gateway")

    # Only wire detection callback on receiver cones — emitters have no GPIO
    if ir_sensor and ir_sensor.role != 'emitter':
        ir_sensor.set_detection_callback(_on_ir_trip)

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("192.168.99.100", 6000))
            print(f"Connected to Device 0")
            led_manager.set_state(LEDState.MESH_CONNECTED)

            while True:
                # Send heartbeat
                # Get current sensor reading
                sensor_reading = touch_sensor._get_sensor_reading() if touch_sensor.hardware_available else None
                sensor_magnitude = touch_sensor._calculate_magnitude(sensor_reading) if sensor_reading else 0.0

                heartbeat = {
                    "node_id": node_id,
                    "status": "Active",
                    "timestamp": time.time(),
                    "sensors": {
                        "accelerometer": sensor_reading or {"x": 0.0, "y": 0.0, "z": 0.0},
                        "touch_magnitude": sensor_magnitude,
                        "touch_threshold": touch_sensor.threshold,
                        "touch_sensor_available": touch_sensor.hardware_available,
                        "temperature": 25.0,
                        "humidity": 50.0
                    },
                    "battery_level": 85.0,
                    "accelerometer_working": True,
                    "audio_working": True,
                    "action": current_action[0]  # Report current action assignment
                }

                # Report detection event (touch or sonar, same field for compatibility)
                global last_touch_time
                current_time = time.time()
                if last_touch_time > 0 and (current_time - last_touch_time) < 5.0:
                    heartbeat["touch_detected"] = True
                    heartbeat["touch_timestamp"] = last_touch_time
                    last_touch_time = 0  # Reset after reporting
                else:
                    heartbeat["touch_detected"] = False
                    heartbeat["touch_timestamp"] = None

                # Always report IR sensor config so D0 knows type/role
                heartbeat["ir_sensor_type"] = _ir_config.get('sensor_type', 'mh_flying_fish')
                heartbeat["ir_role"] = _ir_config.get('role', 'receiver')

                # Report beam health for adafruit break-beam receiver
                # Skip only during test mode (deliberate breaks); run even while armed so
                # sustained loss (emitter moved) is detected across countdown and run.
                # A real athlete trip lasts <1s, adding at most 1 miss — below 3-miss threshold.
                if (ir_sensor and ir_sensor.available and
                        not ir_test_active[0] and
                        _ir_config.get('sensor_type') == 'adafruit_breakbeam' and
                        _ir_config.get('role') == 'receiver'):
                    if _post_test_suppress[0]:
                        # IR test confirmed alignment — trust it until first athlete completes
                        heartbeat['ir_beam_ok'] = True
                    else:
                        _beam_intact = ir_sensor.is_beam_intact()
                        if _beam_intact:
                            _beam_ok_misses[0] = 0
                            _beam_ok_streak[0] += 1
                            if _beam_lost[0] and _beam_ok_streak[0] >= BEAM_RESTORE_STREAK:
                                _beam_lost[0] = False
                                _beam_ok_streak[0] = 0
                        else:
                            _beam_ok_streak[0] = 0
                            _beam_ok_misses[0] += 1
                            if _beam_ok_misses[0] >= BEAM_LOST_MISSES:
                                _beam_lost[0] = True
                        heartbeat['ir_beam_ok'] = not _beam_lost[0]

                # Report current volume so D0 can display it in Settings
                heartbeat["volume"] = audio_manager.current_volume

                # Include IR live data when test mode active (for settings page)
                if ir_sensor and ir_test_active[0]:
                    heartbeat["ir"] = {
                        "break_count": _ir_test_break_count[0],
                        "last_break_ts": _ir_test_last_break_ts[0],
                    }

                # Include sonar live data when active (for remote monitoring / test UI)
                heartbeat["detection_method"] = current_detection_method[0]
                if sonar_sensor and sonar_detection_active[0]:
                    s = sonar_sensor.get_status()
                    heartbeat["sonar"] = {
                        "distance_cm":   s["distance_cm"],
                        "baseline_cm":   s["baseline_cm"],
                        "threshold_cm":  s["threshold_cm"],
                        "detection_count": s["detection_count"],
                        "recent_detection": s["recent_detection"],
                        "last_detection_distance_cm": s["last_detection_distance_cm"],
                        "last_detection_baseline_cm": s["last_detection_baseline_cm"],
                    }

                sock.send((json.dumps(heartbeat) + "\n").encode())

                # Receive response - may contain multiple newline-delimited JSON messages
                response = sock.recv(1024).decode().strip()
                if response:
                    # Split by newlines to handle multiple messages
                    messages = [msg.strip() for msg in response.split('\n') if msg.strip()]

                    for message in messages:
                        try:
                            data = json.loads(message)

                            # Process LED command if present (heartbeat format)
                            if "led_command" in data:
                                led_manager.process_led_command(data["led_command"])

                            # Process led_pattern from heartbeat (Simon Says assigned colors)
                            if "led_pattern" in data:
                                pattern = data["led_pattern"]
                                # Use same state_map as direct commands
                                state_map = {
                                    "off": LEDState.OFF,
                                    "solid_green": LEDState.SOLID_GREEN,
                                    "solid_blue": LEDState.SOLID_BLUE,
                                    "solid_red": LEDState.SOLID_RED,
                                    "solid_yellow": LEDState.SOLID_YELLOW,
                                    "solid_white": LEDState.SOLID_WHITE,
                                    "solid_purple": LEDState.SOLID_PURPLE,
                                    "solid_cyan": LEDState.SOLID_CYAN,
                                    "solid_amber": LEDState.MESH_CONNECTED,
                                    "chase_red": LEDState.CHASE_RED,
                                    "chase_green": LEDState.CHASE_GREEN,
                                    "chase_blue": LEDState.CHASE_BLUE,
                                    "chase_yellow": LEDState.CHASE_YELLOW
                                }
                                led_state = state_map.get(pattern, LEDState.OFF)
                                led_manager.set_state(led_state)

                            # Process direct LED command (test format)
                            if "cmd" in data and data["cmd"] == "led":
                                pattern = data.get("pattern", "off")
                                print(f"💡 Received LED command: {pattern}")
                                # Map pattern to LED state - UPDATED for Simon Says with chase support
                                state_map = {
                                    "off": LEDState.OFF,
                                    "solid_green": LEDState.SOLID_GREEN,
                                    "solid_blue": LEDState.SOLID_BLUE,
                                    "solid_red": LEDState.SOLID_RED,
                                    "solid_yellow": LEDState.SOLID_YELLOW,
                                    "solid_white": LEDState.SOLID_WHITE,
                                    "solid_purple": LEDState.SOLID_PURPLE,
                                    "solid_cyan": LEDState.SOLID_CYAN,
                                    "solid_amber": LEDState.MESH_CONNECTED,
                                    "blink_amber": LEDState.MESH_CONNECTED,
                                    "rainbow": LEDState.COURSE_COMPLETE,
                                    # Chase patterns for Simon Says
                                    "chase_red": LEDState.CHASE_RED,
                                    "chase_green": LEDState.CHASE_GREEN,
                                    "chase_blue": LEDState.CHASE_BLUE,
                                    "chase_yellow": LEDState.CHASE_YELLOW,
                                    "chase_amber": LEDState.CHASE_AMBER,
                                    "chase": LEDState.CHASE_WHITE,
                                    "chase_purple": LEDState.CHASE_PURPLE
                                }
                                led_state = state_map.get(pattern, LEDState.OFF)
                                led_manager.set_state(led_state)
                                print(f"✓ LED set to: {pattern} -> {led_state.value}")

                            # Process volume command
                            if "cmd" in data and data["cmd"] == "set_volume":
                                new_vol = data.get("volume")
                                if isinstance(new_vol, (int, float)):
                                    new_vol = max(0, min(100, int(new_vol)))
                                    audio_manager.set_volume(new_vol)
                                    audio_manager._save_config()
                                    print(f"🔊 Volume set to {new_vol}%")

                            # Process audio command if present
                            if "cmd" in data and data["cmd"] == "audio":
                                clip = data.get("clip", "")
                                if clip:
                                    print(f"🔊 Received audio command: {clip}")
                                    audio_file = f"{clip}.mp3"
                                    success = audio_manager.play(audio_file, blocking=False)
                                    if success:
                                        print(f"✓ Playing audio: {audio_file}")
                                    else:
                                        print(f"✗ Failed to play audio: {audio_file}")

                            # Process calibration command if present
                            if "cmd" in data and data["cmd"] == "calibrate":
                                action = data.get("action", "")
                                if action == "set_threshold":
                                    new_threshold = data.get("threshold")
                                    if new_threshold:
                                        print(f"📐 Received calibration command: set threshold to {new_threshold}")
                                        try:
                                            # Update touch sensor threshold
                                            touch_sensor.threshold = new_threshold

                                            # Save to calibration file
                                            os.makedirs("/opt/field_trainer/config", exist_ok=True)
                                            ip_suffix = node_id.split('.')[-1]  # "101" from "192.168.99.101"
                                            cal_file = f"/opt/field_trainer/config/touch_cal_device{ip_suffix}.json"

                                            # Read existing calibration or create new
                                            cal_data = {}
                                            if os.path.exists(cal_file):
                                                with open(cal_file, 'r') as f:
                                                    cal_data = json.load(f)

                                            # Update threshold
                                            cal_data['threshold'] = new_threshold
                                            cal_data['device_id'] = node_id

                                            # Write back
                                            with open(cal_file, 'w') as f:
                                                json.dump(cal_data, f, indent=2)

                                            print(f"✓ Threshold updated to {new_threshold} and saved to {cal_file}")
                                        except Exception as e:
                                            print(f"✗ Failed to update threshold: {e}")

                                elif action == "test_mode":
                                    enabled = data.get("enabled", False)
                                    if enabled:
                                        test_mode_active[0] = True
                                        if not touch_detection_active[0]:
                                            touch_sensor.start_detection()
                                            touch_detection_active[0] = True
                                        print(f"🧪 Test mode started (threshold: {touch_sensor.threshold})")
                                    else:
                                        test_mode_active[0] = False
                                        print("🧪 Test mode stopped")

                            # Process IR test mode command (settings page)
                            if "cmd" in data and data["cmd"] == "ir_test":
                                enabled = data.get("enabled", False)
                                if enabled:
                                    ir_test_active[0] = True
                                    _ir_test_break_count[0] = 0
                                    _ir_test_last_break_ts[0] = None
                                    if ir_sensor:
                                        def _ir_test_cb(event):
                                            _ir_test_break_count[0] += 1
                                            _ir_test_last_break_ts[0] = event.get('timestamp')
                                            ir_trip_event.set()  # wake heartbeat immediately
                                        ir_sensor.start_test_mode(_ir_test_cb)
                                    print("🚦 IR test mode started")
                                else:
                                    ir_test_active[0] = False
                                    if ir_sensor:
                                        ir_sensor.stop_test_mode()
                                        ir_sensor.reset_beam_state()
                                    _beam_ok_misses[0] = 0
                                    _beam_ok_streak[0] = 0
                                    _beam_lost[0] = False
                                    _post_test_suppress[0] = True
                                    print("🚦 IR test mode stopped — beam errors suppressed until first athlete completes")

                            # Process IR arm/disarm command (sprint finish line)
                            if "cmd" in data and data["cmd"] == "beam_reset":
                                # Do NOT reset miss counter — carry-over misses from a moved
                                # emitter should persist so the alert fires on the next athlete.
                                # D0 already clears the stale registry value to suppress the
                                # immediate false alarm. Miss counter only resets on a good read.
                                print("🚦 Beam health state reset (miss counter preserved)")

                            if "cmd" in data and data["cmd"] == "ir_arm":
                                if ir_sensor and ir_sensor.available:
                                    ir_armed[0] = True
                                    ir_sensor.arm()
                                    # Do NOT reset miss counter — see beam_reset comment above
                                    print("🚦 IR sensor armed (sprint finish)")
                                else:
                                    print("🚦 IR arm command received but sensor unavailable")

                            if "cmd" in data and data["cmd"] == "ir_disarm":
                                ir_armed[0] = False
                                if ir_sensor:
                                    ir_sensor.disarm()
                                ir_trip_pending[0] = False
                                if _post_test_suppress[0]:
                                    _post_test_suppress[0] = False
                                    print("🚦 IR sensor disarmed — post-test suppression lifted, beam monitoring active")
                                else:
                                    print("🚦 IR sensor disarmed")

                            # Clock sync — uses fresh master_time from each heartbeat ACK.
                            # clock_sync command sets a pending flag; actual correction runs on
                            # the next heartbeat using that response's master_time (< 10ms old).
                            # Fallback: also correct extreme drift (>30s) from cold boot.
                            _master_time_ms = data.get("master_time")
                            if _master_time_ms and not ir_armed[0]:
                                _now = time.time()
                                _server_time = _master_time_ms / 1000.0
                                _drift_s = _now - _server_time
                                _routine_due = (_now - _last_clock_sync[0] >= 60.0) and abs(_drift_s) > 30.0
                                if (_clock_sync_pending[0] or _routine_due):
                                    if abs(_drift_s) > 0.05:
                                        try:
                                            import subprocess as _sp
                                            _t0 = time.monotonic()
                                            _sp.run(["sudo", "date", "-s", f"@{_server_time:.3f}"],
                                                    check=True, capture_output=True)
                                            _elapsed = time.monotonic() - _t0
                                            if _elapsed > 0.5:
                                                _sp.run(["sudo", "date", "-s",
                                                         f"@{(_server_time + _elapsed):.3f}"],
                                                        capture_output=True)
                                            print(f"🕐 Clock synced: drift was {_drift_s:+.2f}s, sudo took {_elapsed:.1f}s")
                                        except Exception as _e:
                                            print(f"🕐 Clock sync failed: {_e}")
                                    else:
                                        print(f"🕐 Clock OK: drift {_drift_s*1000:.0f}ms")
                                    _clock_sync_pending[0] = False
                                    _last_clock_sync[0] = _now

                            # clock_sync command — just sets pending flag; sync runs on next
                            # heartbeat ACK so master_time is always fresh, never stale.
                            if "cmd" in data and data["cmd"] == "clock_sync":
                                _clock_sync_pending[0] = True
                                print("🕐 Clock sync requested — will apply on next heartbeat ACK")

                            # Process sonar test command (from settings page)
                            if "cmd" in data and data["cmd"] == "sonar_test":
                                enabled = data.get("enabled", False)
                                if enabled and sonar_sensor:
                                    settings_changed = False
                                    if data.get("threshold_cm"):
                                        sonar_sensor.set_threshold(float(data["threshold_cm"]))
                                        settings_changed = True
                                    if data.get("read_interval_s"):
                                        sonar_sensor.set_read_interval(float(data["read_interval_s"]))
                                        settings_changed = True
                                    if data.get("confirm_readings"):
                                        sonar_sensor.set_confirm_readings(int(data["confirm_readings"]))
                                        settings_changed = True
                                    if settings_changed:
                                        try:
                                            os.makedirs("/opt/field_trainer/config", exist_ok=True)
                                            _suffix = node_id.split('.')[-1]
                                            with open(f"/opt/field_trainer/config/sonar_config_device{_suffix}.json", 'w') as f:
                                                json.dump({
                                                    'device_id': node_id,
                                                    'threshold_cm': sonar_sensor.threshold_cm,
                                                    'read_interval_s': sonar_sensor.read_interval_s,
                                                    'confirm_readings': sonar_sensor.confirm_readings,
                                                }, f, indent=2)
                                        except Exception as e:
                                            print(f"Failed to save sonar config: {e}")
                                    sonar_test_active[0] = True
                                    if not sonar_detection_active[0]:
                                        sonar_sensor.start_monitoring()
                                        sonar_detection_active[0] = True
                                    print(f"🔊 Sonar test started (threshold: {sonar_sensor.threshold_cm}cm)")
                                elif not enabled and sonar_sensor:
                                    sonar_test_active[0] = False
                                    if sonar_detection_active[0] and not (current_detection_method[0] == 'proximity' and
                                            current_action[0] is not None):
                                        sonar_sensor.stop_monitoring()
                                        sonar_detection_active[0] = False
                                        print("🔊 Sonar test stopped")

                            # Process reboot command
                            if "cmd" in data and data["cmd"] == "reboot":
                                print("🔄 Reboot command received - rebooting device...")
                                import subprocess
                                subprocess.Popen(["sudo", "reboot"])
                                return

                            # Update heartbeat interval if deployment message includes it
                            if "heartbeat_interval" in data:
                                new_interval = data["heartbeat_interval"]
                                if new_interval != heartbeat_interval[0]:
                                    heartbeat_interval[0] = new_interval
                                    print(f"📡 Heartbeat interval changed to {new_interval}s")

                            # Update detection method from deploy command
                            if "detection_method" in data:
                                new_method = data["detection_method"] or "touch"
                                if new_method != current_detection_method[0]:
                                    current_detection_method[0] = new_method
                                    print(f"🎯 Detection method set to: {new_method}")

                            # Update current action assignment
                            action = data.get("action")
                            course_status = data.get("course_status", "Inactive")

                            if action != current_action[0]:
                                current_action[0] = action
                                if action:
                                    print(f"Assigned action: {action}")
                                else:
                                    print(f"Action cleared (device inactive)")

                            # Start/stop the correct sensor based on detection_method
                            method = current_detection_method[0]
                            if course_status == "Active" and action:
                                if method == "proximity":
                                    # Use sonar — stop touch if running
                                    if touch_detection_active[0]:
                                        touch_sensor.stop_detection()
                                        touch_detection_active[0] = False
                                    if sonar_sensor and not sonar_detection_active[0]:
                                        sonar_sensor.start_monitoring()
                                        sonar_detection_active[0] = True
                                        print("🔊 Sonar detection started (course active)")
                                elif method == "none":
                                    # No detection — stop both
                                    if touch_detection_active[0]:
                                        touch_sensor.stop_detection()
                                        touch_detection_active[0] = False
                                    if sonar_sensor and sonar_detection_active[0]:
                                        sonar_sensor.stop_monitoring()
                                        sonar_detection_active[0] = False
                                else:
                                    # Default: touch — stop sonar if running
                                    if sonar_sensor and sonar_detection_active[0]:
                                        sonar_sensor.stop_monitoring()
                                        sonar_detection_active[0] = False
                                    if not touch_detection_active[0]:
                                        touch_sensor.start_detection()
                                        touch_detection_active[0] = True
                                        print("Touch detection started (course active)")
                            elif not test_mode_active[0] and not sonar_test_active[0] and not ir_armed[0] and not ir_test_active[0]:
                                # Course inactive — stop all detection sensors
                                if touch_detection_active[0]:
                                    touch_sensor.stop_detection()
                                    touch_detection_active[0] = False
                                    print("Touch detection stopped (course inactive)")
                                if sonar_sensor and sonar_detection_active[0]:
                                    sonar_sensor.stop_monitoring()
                                    sonar_detection_active[0] = False
                                    print("🔊 Sonar detection stopped (course inactive)")

                        except json.JSONDecodeError as e:
                            print(f"JSON decode error for message '{message}': {e}")

                # Sleep until next heartbeat, but wake immediately if IR trips.
                # Use short interval during IR test mode so UI sees live beam state.
                wait_s = 0.2 if ir_test_active[0] else heartbeat_interval[0]
                ir_trip_event.wait(timeout=wait_s)
                ir_trip_event.clear()

                # If IR tripped during sleep, send immediate notification to gateway
                if ir_trip_pending[0]:
                    ir_trip_pending[0] = False
                    try:
                        trip_msg = json.dumps({"node_id": node_id, "ir_trip": True, "trip_time": ir_trip_time[0]}) + "\n"
                        sock.sendall(trip_msg.encode("utf-8"))
                        sock.recv(1024)  # consume gateway ACK
                    except Exception as _e:
                        print(f"🚦 Failed to send IR trip to gateway: {_e}")

        except ConnectionRefusedError:
            print("Connection refused - Device 0 server not available")
            led_manager.set_state(LEDState.NETWORK_ERROR)
            time.sleep(10)
        except Exception as e:
            print(f"Connection error: {e}")
            led_manager.set_state(LEDState.NETWORK_ERROR)
            time.sleep(10)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", required=True, help="Node ID (e.g., 192.168.99.101)")
    args = parser.parse_args()

    print(f"Starting Field Trainer Client for {args.node_id}")
    connect_to_device0(args.node_id)
