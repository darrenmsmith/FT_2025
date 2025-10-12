#!/usr/bin/env python3
"""
Touch LED Service - Blinks LED green when device is touched
Runs continuously on each device to provide visual feedback
"""

import sys
import time
import signal
from typing import Optional

sys.path.insert(0, '/opt/field_trainer')

from ft_touch import TouchSensor
from ft_led import LEDManager, LEDState

class TouchLEDService:
    def __init__(self, device_id: str, num_pixels: int = 8):
        self.device_id = device_id
        self.running = False
        self.blink_active = False
        
        # Initialize touch sensor
        print(f"[{device_id}] Initializing touch sensor...")
        self.touch_sensor = TouchSensor(device_id)
        
        if not self.touch_sensor.hardware_available:
            raise RuntimeError("Touch sensor hardware not available")
        
        if not self.touch_sensor.calibrated:
            print(f"[{device_id}] Sensor not calibrated - auto-calibrating...")
            self.touch_sensor.calibrate()
        
        # Initialize LED manager
        print(f"[{device_id}] Initializing LED manager...")
        try:
            self.led = LEDManager(pin=18, led_count=num_pixels, brightness=16)
            self.led_available = True
            # Start with LEDs off
            self.led.set_state(LEDState.OFF)
        except Exception as e:
            print(f"[{device_id}] LED initialization failed: {e}")
            self.led_available = False
        
        # Set touch callback
        self.touch_sensor.set_touch_callback(self.on_touch)
        
        print(f"[{device_id}] Touch LED service initialized")
        print(f"[{device_id}] Threshold: {self.touch_sensor.threshold}")
    
    def on_touch(self):
        """Called when device is touched - blink LED green"""
        touch_time = time.time()
        print(f"[{self.device_id}] Touch detected at {touch_time:.2f}", flush=True)
        
        if self.led_available and not self.blink_active:
            self.blink_active = True
            try:
                # Turn on solid green
                self.led.set_state(LEDState.SOLID_GREEN)
                time.sleep(0.1)
                # Turn off
                self.led.set_state(LEDState.OFF)
            except Exception as e:
                print(f"[{self.device_id}] LED error: {e}")
            finally:
                self.blink_active = False
    
    def start(self):
        """Start the touch detection service"""
        if self.running:
            print(f"[{self.device_id}] Service already running")
            return
        
        self.running = True
        print(f"[{self.device_id}] Starting touch detection...")
        self.touch_sensor.start_detection()
        print(f"[{self.device_id}] Touch LED service is running")
        print(f"[{self.device_id}] Tap device to see green LED blink")
    
    def stop(self):
        """Stop the touch detection service"""
        if not self.running:
            return
        
        print(f"[{self.device_id}] Stopping touch detection...")
        self.touch_sensor.stop_detection()
        
        # Turn off LEDs
        if self.led_available:
            try:
                self.led.set_state(LEDState.OFF)
            except Exception:
                pass
        
        self.running = False
        print(f"[{self.device_id}] Service stopped")
    
    def get_status(self):
        """Get service status"""
        return {
            'device_id': self.device_id,
            'running': self.running,
            'touches': self.touch_sensor.touch_count,
            'threshold': self.touch_sensor.threshold,
            'hardware_available': self.touch_sensor.hardware_available,
            'led_available': self.led_available
        }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Touch LED Service')
    parser.add_argument('--device-id', required=True, help='Device ID (e.g., 192.168.99.101)')
    parser.add_argument('--pixels', type=int, default=8, help='Number of LED pixels')
    args = parser.parse_args()
    
    print(f"=== Touch LED Service for {args.device_id} ===")
    
    # Create service
    try:
        service = TouchLEDService(args.device_id, args.pixels)
    except Exception as e:
        print(f"ERROR: Failed to initialize service: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutdown requested...")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start service
    service.start()
    
    # Keep running
    try:
        while service.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        service.stop()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
