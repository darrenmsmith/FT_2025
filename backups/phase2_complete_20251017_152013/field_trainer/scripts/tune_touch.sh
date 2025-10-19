#!/bin/bash
# Tune touch threshold for a device

if [ $# -lt 2 ]; then
    echo "Usage: $0 <device_number> <up|down|set VALUE>"
    echo "Examples:"
    echo "  $0 101 up       # Increase threshold by 0.5"
    echo "  $0 101 down     # Decrease threshold by 0.5"
    echo "  $0 101 set 3.0  # Set threshold to 3.0"
    exit 1
fi

DEVICE=$1
ACTION=$2
VALUE=${3:-0.5}
IP="192.168.99.$DEVICE"

echo "Tuning Device $DEVICE ($IP)"

ssh pi@$IP "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor

sensor = TouchSensor('192.168.99.$DEVICE')

if not sensor.hardware_available:
    print('❌ Hardware not available')
    sys.exit(1)

print(f'Current threshold: {sensor.threshold}')

action = '$ACTION'
if action == 'up':
    new_threshold = sensor.threshold + 0.5
    sensor.update_threshold(new_threshold)
    print(f'Increased to: {sensor.threshold}')
elif action == 'down':
    new_threshold = max(0.5, sensor.threshold - 0.5)
    sensor.update_threshold(new_threshold)
    print(f'Decreased to: {sensor.threshold}')
elif action == 'set':
    new_threshold = float('$VALUE')
    sensor.update_threshold(new_threshold)
    print(f'Set to: {sensor.threshold}')
else:
    print('Invalid action')
PYTHON_EOF
"

echo ""
echo "Test the new threshold: ./test_touch.sh $DEVICE"
