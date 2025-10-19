#!/bin/bash
# Check touch sensor status on all devices

echo "================================================"
echo "Touch Sensor Status - All Devices"
echo "================================================"
echo ""

for device in 100 101 102 103 104 105; do
    IP="192.168.99.$device"
    
    if ! ping -c 1 -W 1 $IP > /dev/null 2>&1; then
        echo "Device $device: ❌ Not reachable"
        continue
    fi
    
    echo -n "Device $device: "
    
    STATUS=$(ssh pi@$IP "python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor

sensor = TouchSensor('192.168.99.$device')
status = sensor.get_status()

if status['hardware_available']:
    cal = '✅ Cal' if status['calibrated'] else '❌ Not Cal'
    print(f\"{cal} | Threshold: {status['threshold']:.1f} | Touches: {status['touch_count']}\")
else:
    print('❌ No Hardware')
PYTHON_EOF
" 2>/dev/null)
    
    echo "$STATUS"
done

echo ""
echo "================================================"
