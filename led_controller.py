#!/usr/bin/env python3
"""
Field Trainer LED Controller v1.0
- Controls WS2811/WS2812 LED strips for Field Trainer status indication
- Supports the defined color states: Orange, Blue, Green, Red, Rainbow
- Thread-safe LED control with state management
- Compatible with rpi_ws281x library

LED Status Definitions:
- Orange (solid): Connected to mesh network
- Blue (solid): Course deployed
- Green (solid): Course active/training
- Red (solid): Software errors
- Red (blinking): Network errors (1 second interval)
- Rainbow: Individual device course completion (10 seconds)
"""

import threading
import time
from enum import Enum
from typing import Optional, Tuple, List
import colorsys

# LED Hardware Configuration
LED_COUNT = 15          # Number of LED pixels
LED_PIN = 18           # GPIO pin connected to the pixels (BCM numbering)
LED_FREQ_HZ = 800000   # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10           # DMA channel to use for generating signal
LED_BRIGHTNESS = 128   # Set to 0 for darkest and 255 for brightest (50% brightness)
LED_INVERT = False     # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0        # Set to '1' for GPIOs 13, 19, 41, 45 or 53


class LEDState(Enum):
    """LED status states for Field Trainer devices"""
    OFF = "off"
    MESH_CONNECTED = "mesh_connected"      # Orange solid
    COURSE_DEPLOYED = "course_deployed"    # Blue solid  
    COURSE_ACTIVE = "course_active"        # Green solid
    SOFTWARE_ERROR = "software_error"      # Red solid
    NETWORK_ERROR = "network_error"        # Red blinking
    COURSE_COMPLETE = "course_complete"    # Rainbow animation


class LEDController:
    """Thread-safe LED controller for Field Trainer status indication"""
    
    def __init__(self, led_count=LED_COUNT, led_pin=LED_PIN, brightness=LED_BRIGHTNESS):
        self.led_count = led_count
        self.led_pin = led_pin
        self.brightness = brightness
        
        # Control variables
        self.current_state = LEDState.OFF
        self.animation_thread = None
        self.running = True
        self.state_lock = threading.Lock()
        
        # WS281x strip object
        self.strip = None
        self.initialized = False
        
        # Color definitions (RGB values 0-255)
        self.colors = {
            LEDState.OFF: (0, 0, 0),
            LEDState.MESH_CONNECTED: (255, 165, 0),    # Orange
            LEDState.COURSE_DEPLOYED: (0, 0, 255),     # Blue
            LEDState.COURSE_ACTIVE: (0, 255, 0),       # Green
            LEDState.SOFTWARE_ERROR: (255, 0, 0),      # Red
            LEDState.NETWORK_ERROR: (255, 0, 0),       # Red (will blink)
        }
        
        # Initialize LED hardware
        self._initialize_hardware()
        
    def _initialize_hardware(self):
        """Initialize the WS281x LED hardware"""
        try:
            # Import rpi_ws281x library
            from rpi_ws281x import PixelStrip, Color
            self.PixelStrip = PixelStrip
            self.Color = Color
            
            # Create PixelStrip object
            self.strip = PixelStrip(
                self.led_count,
                self.led_pin,
                LED_FREQ_HZ,
                LED_DMA,
                LED_INVERT,
                self.brightness,
                LED_CHANNEL
            )
            
            # Initialize the library
            self.strip.begin()
            self.initialized = True
            
            # Set all LEDs to off initially
            self._set_all_pixels((0, 0, 0))
            self.strip.show()
            
        except ImportError:
            print("Warning: rpi_ws281x library not available. LED control disabled.")
            self.initialized = False
        except Exception as e:
            print(f"Error initializing LED hardware: {e}")
            self.initialized = False
    
    def _rgb_to_color(self, rgb: Tuple[int, int, int]) -> int:
        """Convert RGB tuple to rpi_ws281x Color format"""
        if not self.initialized:
            return 0
        return self.Color(rgb[0], rgb[1], rgb[2])
    
    def _set_all_pixels(self, rgb: Tuple[int, int, int]):
        """Set all pixels to the same RGB color"""
        if not self.initialized:
            return
            
        color = self._rgb_to_color(rgb)
        for i in range(self.led_count):
            self.strip.setPixelColor(i, color)
    
    def _rainbow_color(self, position: float) -> Tuple[int, int, int]:
        """Generate rainbow color based on position (0.0 to 1.0)"""
        # Use HSV color space for smooth rainbow transitions
        hue = position
        saturation = 1.0
        value = 1.0
        
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
    
    def set_state(self, state: LEDState):
        """Set the LED state - thread safe"""
        with self.state_lock:
            if state == self.current_state:
                return  # No change needed
                
            old_state = self.current_state
            self.current_state = state
            
            # Stop any running animation
            if self.animation_thread and self.animation_thread.is_alive():
                # Animation thread will check current_state and stop
                pass
                
            # Start new state display
            if state in [LEDState.MESH_CONNECTED, LEDState.COURSE_DEPLOYED, 
                        LEDState.COURSE_ACTIVE, LEDState.SOFTWARE_ERROR, LEDState.OFF]:
                # Solid colors
                self._display_solid_color(state)
            elif state == LEDState.NETWORK_ERROR:
                # Blinking red
                self._start_blinking_animation()
            elif state == LEDState.COURSE_COMPLETE:
                # Rainbow animation
                self._start_rainbow_animation()
    
    def _display_solid_color(self, state: LEDState):
        """Display a solid color for the given state"""
        if not self.initialized:
            return
            
        color = self.colors.get(state, (0, 0, 0))
        self._set_all_pixels(color)
        self.strip.show()
    
    def _start_blinking_animation(self):
        """Start blinking red animation for network errors"""
        if self.animation_thread and self.animation_thread.is_alive():
            return
            
        self.animation_thread = threading.Thread(target=self._blink_animation_loop, daemon=True)
        self.animation_thread.start()
    
    def _blink_animation_loop(self):
        """Animation loop for blinking red LEDs"""
        blink_on = True
        while self.current_state == LEDState.NETWORK_ERROR and self.running:
            if not self.initialized:
                time.sleep(0.1)
                continue
                
            if blink_on:
                self._set_all_pixels(self.colors[LEDState.NETWORK_ERROR])  # Red
            else:
                self._set_all_pixels((0, 0, 0))  # Off
                
            self.strip.show()
            blink_on = not blink_on
            time.sleep(1.0)  # 1 second interval
    
    def _start_rainbow_animation(self):
        """Start rainbow animation for course completion"""
        if self.animation_thread and self.animation_thread.is_alive():
            return
            
        self.animation_thread = threading.Thread(target=self._rainbow_animation_loop, daemon=True)
        self.animation_thread.start()
    
    def _rainbow_animation_loop(self):
        """Animation loop for rainbow course completion display"""
        animation_duration = 10.0  # 10 seconds
        animation_speed = 0.05     # Update every 50ms
        total_steps = int(animation_duration / animation_speed)
        
        start_time = time.time()
        step = 0
        
        while (self.current_state == LEDState.COURSE_COMPLETE and 
               self.running and 
               time.time() - start_time < animation_duration):
            
            if not self.initialized:
                time.sleep(animation_speed)
                continue
            
            # Create rainbow pattern that moves across the strip
            for i in range(self.led_count):
                # Calculate color position for this LED
                position = (step + i * 3) % 256 / 256.0
                color = self._rainbow_color(position)
                pixel_color = self._rgb_to_color(color)
                self.strip.setPixelColor(i, pixel_color)
            
            self.strip.show()
            step += 1
            time.sleep(animation_speed)
        
        # After animation, return to previous appropriate state
        # This should be handled by the main application logic
    
    def get_current_state(self) -> LEDState:
        """Get the current LED state - thread safe"""
        with self.state_lock:
            return self.current_state
    
    def shutdown(self):
        """Clean shutdown of LED controller"""
        self.running = False
        
        # Wait for animation thread to complete
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=2.0)
        
        # Turn off all LEDs
        if self.initialized:
            self._set_all_pixels((0, 0, 0))
            self.strip.show()


# LED command protocol integration
def create_led_command(state: LEDState) -> dict:
    """Create LED command for TCP heartbeat protocol"""
    return {
        "led_command": {
            "state": state.value,
            "timestamp": time.time()
        }
    }


# Test function for development
def test_led_controller():
    """Test all LED states - for development and debugging"""
    controller = LEDController()
    
    if not controller.initialized:
        print("LED hardware not available - test skipped")
        return
    
    states = [
        (LEDState.MESH_CONNECTED, "Orange - Mesh Connected", 3),
        (LEDState.COURSE_DEPLOYED, "Blue - Course Deployed", 3),
        (LEDState.COURSE_ACTIVE, "Green - Course Active", 3),
        (LEDState.SOFTWARE_ERROR, "Red - Software Error", 3),
        (LEDState.NETWORK_ERROR, "Red Blinking - Network Error", 5),
        (LEDState.COURSE_COMPLETE, "Rainbow - Course Complete", 10),
        (LEDState.OFF, "Off", 2)
    ]
    
    print("Testing LED Controller - cycling through all states...")
    
    for state, description, duration in states:
        print(f"Setting state: {description}")
        controller.set_state(state)
        time.sleep(duration)
    
    controller.shutdown()
    print("LED test complete")


if __name__ == "__main__":
    test_led_controller()
