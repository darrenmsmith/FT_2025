#!/usr/bin/env python3
"""
LED Hardware Test Script for Field Trainer
Tests LED functionality with correct hardware configuration
GPIO 12, 15 LEDs, basic color sequence
"""

import time
import sys
from rpi_ws281x import PixelStrip, Color

# LED strip configuration for Field Trainer hardware
LED_COUNT = 15        # Number of LED pixels
LED_PIN = 12          # GPIO pin connected to the pixels (your hardware config)
LED_FREQ_HZ = 800000  # LED signal frequency in hertz
LED_DMA = 10          # DMA channel to use for generating signal
LED_BRIGHTNESS = 128  # Set to 0-255 (50% brightness for testing)
LED_INVERT = False    # True to invert signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # Set to '1' for GPIOs 13, 19, 41, 45 or 53

def test_led_hardware():
    """Test LED hardware with Field Trainer configurations"""
    print("Field Trainer LED Hardware Test")
    print("=" * 40)
    print(f"LED Count: {LED_COUNT}")
    print(f"GPIO Pin: {LED_PIN}")
    print(f"Brightness: {LED_BRIGHTNESS}")
    print("=" * 40)
    
    try:
        # Create NeoPixel object with appropriate configuration
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        
        # Initialize the library (must be called before other functions)
        strip.begin()
        print("LED strip initialized successfully!")
        
        # Test 1: All LEDs off
        print("\nTest 1: All LEDs OFF")
        color_wipe(strip, Color(0, 0, 0), 0)
        time.sleep(2)
        
        # Test 2: Field Trainer Orange (Mesh Connected)
        print("Test 2: ORANGE - Mesh Connected")
        color_wipe(strip, Color(255, 165, 0), 50)  # Orange
        time.sleep(3)
        
        # Test 3: Field Trainer Blue (Course Deployed)  
        print("Test 3: BLUE - Course Deployed")
        color_wipe(strip, Color(0, 0, 255), 50)  # Blue
        time.sleep(3)
        
        # Test 4: Field Trainer Green (Course Active)
        print("Test 4: GREEN - Course Active") 
        color_wipe(strip, Color(0, 255, 0), 50)  # Green
        time.sleep(3)
        
        # Test 5: Field Trainer Red (Error State)
        print("Test 5: RED - Error State")
        color_wipe(strip, Color(255, 0, 0), 50)  # Red
        time.sleep(3)
        
        # Test 6: Blinking Red (Network Error)
        print("Test 6: BLINKING RED - Network Error (5 seconds)")
        blink_test(strip, Color(255, 0, 0), 5)
        
        # Test 7: Rainbow animation (Course Complete)
        print("Test 7: RAINBOW - Course Complete (5 seconds)")
        rainbow_test(strip, 5)
        
        # Test 8: Individual LED test
        print("Test 8: Individual LED test")
        individual_led_test(strip)
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nPossible issues:")
        print("1. Run with sudo: sudo python3 led_test.py")
        print("2. Check wiring to GPIO 12")
        print("3. Ensure pi user is in gpio group")
        print("4. Verify LED strip power supply")
        return False
    
    finally:
        # Clean up - turn all LEDs off
        try:
            if 'strip' in locals():
                color_wipe(strip, Color(0, 0, 0), 0)
                print("LEDs turned off")
        except:
            pass
    
    return True

def color_wipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        if wait_ms > 0:
            strip.show()
            time.sleep(wait_ms / 1000.0)
    strip.show()

def blink_test(strip, color, duration_seconds):
    """Blink all LEDs for specified duration"""
    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        color_wipe(strip, color, 0)
        time.sleep(0.5)
        color_wipe(strip, Color(0, 0, 0), 0)
        time.sleep(0.5)

def rainbow_test(strip, duration_seconds):
    """Rainbow color animation"""
    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        for j in range(256):
            if time.time() - start_time >= duration_seconds:
                break
            for i in range(strip.numPixels()):
                color = wheel(strip, (i + j) & 255)
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(0.02)

def wheel(strip, pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def individual_led_test(strip):
    """Test each LED individually"""
    print("Testing individual LEDs...")
    color_wipe(strip, Color(0, 0, 0), 0)  # Start with all off
    
    for i in range(strip.numPixels()):
        print(f"  LED {i+1}/{strip.numPixels()}")
        strip.setPixelColor(i, Color(0, 255, 0))  # Green
        strip.show()
        time.sleep(0.3)
        strip.setPixelColor(i, Color(0, 0, 0))    # Off
        strip.show()
        time.sleep(0.1)

if __name__ == '__main__':
    print("Starting LED hardware test...")
    print("Press Ctrl+C to stop at any time")
    
    try:
        success = test_led_hardware()
        if success:
            print("\n✓ LED hardware test completed successfully")
            print("Your LED strip is working correctly!")
        else:
            print("\n✗ LED hardware test failed")
            print("Check the error messages above")
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        # Turn off LEDs on exit
        try:
            strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
            strip.begin()
            color_wipe(strip, Color(0, 0, 0), 0)
        except:
            pass
        print("LEDs turned off")
        sys.exit(0)
