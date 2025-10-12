#!/bin/bash
# Interactive touch threshold tuning

if [ $# -lt 1 ]; then
    echo "Usage: $0 <device_number>"
    echo "Example: $0 101"
    exit 1
fi

DEVICE=$1
IP="192.168.99.$DEVICE"

echo "================================================"
echo "Interactive Touch Tuning - Device $DEVICE"
echo "================================================"
echo ""
echo "Commands:"
echo "  up     - Increase threshold by 0.5"
echo "  down   - Decrease threshold by 0.5"
echo "  test   - Run 5 second test"
echo "  status - Show current readings"
echo "  quit   - Exit"
echo ""

ssh -t pi@$IP "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor
import time

sensor = TouchSensor('192.168.99.$DEVICE')

if not sensor.hardware_available:
    print('❌ Hardware not available')
    sys.exit(1)

print(f'Current threshold: {sensor.threshold}')
print('')

while True:
    try:
        # Show current magnitude
        reading = sensor._get_sensor_reading()
        if reading:
            magnitude = sensor._calculate_magnitude(reading)
            status = '🔴 TOUCH' if magnitude > sensor.threshold else '🟢 idle'
            print(f'\r{status} | Magnitude: {magnitude:.3f} | Threshold: {sensor.threshold:.1f}', end='', flush=True)
        
        time.sleep(0.1)
        
    except KeyboardInterrupt:
        print('\n\nStopped')
        break
    except Exception as e:
        print(f'\nError: {e}')
        break
PYTHON_EOF
"
