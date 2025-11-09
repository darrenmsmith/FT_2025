#!/bin/bash
# Test touch detection with LED feedback

if [ $# -lt 1 ]; then
    echo "Usage: $0 <device_number> [duration]"
    exit 1
fi

DEVICE=$1
DURATION=${2:-30}
IP="192.168.99.$DEVICE"

echo "Testing Device $DEVICE with LED feedback for $DURATION seconds"

ssh pi@$IP "python3 -u << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor
from ft_led import LEDController
import time

# Initialize touch sensor
sensor = TouchSensor('192.168.99.$DEVICE')

if not sensor.hardware_available:
    print('❌ Touch sensor not available')
    sys.exit(1)

if not sensor.calibrated:
    print('⚠️  Not calibrated - calibrating now...')
    sensor.calibrate()

# Initialize LED controller
try:
    led = LEDController(num_pixels=60, gpio_pin=18, brightness=128)
    led_available = True
    print('✅ LED controller initialized')
except Exception as e:
    print(f'⚠️  LED controller failed: {e}')
    led_available = False

print(f'Threshold: {sensor.threshold}')
print('Ready! Tap the device to see green LED blink')
print(f'Test will run for $DURATION seconds')
print('')

# Touch callback with LED feedback
def on_touch():
    print(f'🟢 Touch detected at {time.time():.2f}', flush=True)
    if led_available:
        # Blink green
        led.set_color((0, 255, 0))  # Green
        led.show()
        time.sleep(0.3)
        led.set_color((0, 0, 0))    # Off
        led.show()

# Set callback
sensor.set_touch_callback(on_touch)

# Start detection
sensor.start_detection()

try:
    # Run for specified duration
    time.sleep($DURATION)
except KeyboardInterrupt:
    print('\nStopped by user')

# Stop detection
sensor.stop_detection()

# Final stats
print('')
print(f'Total touches detected: {sensor.touch_count}')

# Turn off LEDs
if led_available:
    led.set_color((0, 0, 0))
    led.show()

PYTHON_EOF
"
