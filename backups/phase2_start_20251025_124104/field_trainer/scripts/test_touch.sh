#!/bin/bash
# Test touch detection on devices

echo "================================================"
echo "Field Trainer Touch Detection Test"
echo "================================================"
echo ""

# Check if device ID provided
if [ $# -eq 1 ]; then
    DEVICE=$1
else
    echo "Usage: $0 <device_number>"
    echo "Example: $0 101"
    exit 1
fi

IP="192.168.99.$DEVICE"

echo "Testing Device $DEVICE ($IP)"
echo "Tap the device 5 times in 10 seconds"
echo ""

ssh pi@$IP "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor
import time

sensor = TouchSensor('192.168.99.$DEVICE')

if not sensor.hardware_available:
    print('❌ Hardware not available')
    sys.exit(1)

if not sensor.calibrated:
    print('⚠️  Device not calibrated - calibrating now...')
    sensor.calibrate()

print(f'Current threshold: {sensor.threshold}')
print('Ready to test... tap 5 times in 10 seconds')
time.sleep(2)

# Run test
result = sensor.test_detection(duration=10.0)

print('')
print('Test Results:')
print(f'  Touches detected: {result[\"touches_detected\"]}')
print(f'  Max magnitude: {result[\"max_magnitude\"]:.2f}')
print(f'  Avg magnitude: {result[\"avg_magnitude\"]:.2f}')
print('')

if result['touches_detected'] >= 4 and result['touches_detected'] <= 7:
    print('✅ Touch detection looks good!')
elif result['touches_detected'] > 10:
    print('⚠️  Too sensitive - increase threshold to 3.5-4.0')
    print(f'   Run: ./tune_touch.sh $DEVICE up')
elif result['touches_detected'] < 3:
    print('⚠️  Not sensitive enough - decrease threshold to 1.5-2.0')
    print(f'   Run: ./tune_touch.sh $DEVICE down')
else:
    print('ℹ️  Threshold may need adjustment')
PYTHON_EOF
"
