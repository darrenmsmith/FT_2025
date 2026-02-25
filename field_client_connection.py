#!/usr/bin/env python3
"""
Field Trainer Client with LED Control
Connects to Device 0 and manages local LED hardware
"""

import socket
import json
import time
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor
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

    # Track current action assignment (use list for mutable reference in lambda)
    current_action = [None]
    touch_detection_active = [False]
    test_mode_active = [False]  # True while calibration test mode is running
    heartbeat_interval = [5]  # Default 5 seconds, can be changed by deployment

    # Set touch callback with audio manager and current action
    touch_sensor.set_touch_callback(lambda: touch_detected_callback(audio_manager, current_action[0]))
    print("Touch sensor initialized (detection disabled until course deployed)")

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

                # Phase 1: Add touch event reporting
                global last_touch_time
                current_time = time.time()
                if last_touch_time > 0 and (current_time - last_touch_time) < 5.0:
                    # Touch occurred within last 5 seconds, report it
                    heartbeat["touch_detected"] = True
                    heartbeat["touch_timestamp"] = last_touch_time
                    last_touch_time = 0  # Reset after reporting
                else:
                    heartbeat["touch_detected"] = False
                    heartbeat["touch_timestamp"] = None

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
                                            import os
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

                            # Update heartbeat interval if deployment message includes it
                            if "heartbeat_interval" in data:
                                new_interval = data["heartbeat_interval"]
                                if new_interval != heartbeat_interval[0]:
                                    heartbeat_interval[0] = new_interval
                                    print(f"📡 Heartbeat interval changed to {new_interval}s")

                            # Update current action assignment and touch detection state
                            action = data.get("action")
                            course_status = data.get("course_status", "Inactive")

                            # Update action if changed
                            if action != current_action[0]:
                                current_action[0] = action
                                if action:
                                    print(f"Assigned action: {action}")
                                else:
                                    print(f"Action cleared (device inactive)")

                            # Control touch detection based on course status
                            if course_status == "Active" and action:
                                # Start touch detection only when course is Active
                                if not touch_detection_active[0]:
                                    touch_sensor.start_detection()
                                    touch_detection_active[0] = True
                                    print("Touch detection started (course active)")
                            elif not test_mode_active[0]:
                                # Stop touch detection when course not active, no action,
                                # and calibration test mode is not running
                                if touch_detection_active[0]:
                                    touch_sensor.stop_detection()
                                    touch_detection_active[0] = False
                                    print("Touch detection stopped (course inactive)")

                        except json.JSONDecodeError as e:
                            print(f"JSON decode error for message '{message}': {e}")

                time.sleep(heartbeat_interval[0])

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
