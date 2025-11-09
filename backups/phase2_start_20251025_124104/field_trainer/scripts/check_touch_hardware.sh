#!/bin/bash
# Check touch sensor hardware on all devices

echo "================================================"
echo "MPU6500 Hardware Check"
echo "================================================"
echo ""

for device in 100 101 102 103 104 105; do
    IP="192.168.99.$device"
    echo "=== Device $device ($IP) ==="
    
    if ! ping -c 1 -W 1 $IP > /dev/null 2>&1; then
        echo "  ❌ Not reachable"
        echo ""
        continue
    fi
    
    ssh pi@$IP "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor

sensor = TouchSensor('192.168.99.$device')

if sensor.hardware_available:
    print(f'  ✅ Hardware detected')
    print(f'     Address: 0x{sensor.mpu_address:02X}')
    print(f'     Calibrated: {sensor.calibrated}')
    if sensor.calibrated:
        print(f'     Threshold: {sensor.threshold}')
else:
    print('  ❌ Hardware not found')
    print('     Check I2C connections')
PYTHON_EOF
"
    echo ""
done

echo "================================================"
