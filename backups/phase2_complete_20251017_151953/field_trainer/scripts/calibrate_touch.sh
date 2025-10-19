#!/bin/bash
# Calibrate touch sensors with automatic threshold tuning

echo "================================================"
echo "Field Trainer Touch Sensor Calibration"
echo "================================================"
echo ""

# Check if device ID provided
if [ $# -eq 1 ]; then
    DEVICES=($1)
    echo "Calibrating single device: $1"
else
    DEVICES=(100 101 102 103 104 105)
    echo "Calibrating all devices"
fi

for device in "${DEVICES[@]}"; do
    IP="192.168.99.$device"
    echo ""
    echo "========================================"
    echo "Calibrating Device $device ($IP)"
    echo "========================================"
    
    # Check if reachable
    if ! ping -c 1 -W 1 $IP > /dev/null 2>&1; then
        echo "  ❌ Device not reachable"
        continue
    fi
    
    # Run calibration with touch testing - use -u for unbuffered output
    ssh pi@$IP "python3 -u << 'PYTHON_EOF'
import sys
sys.path.insert(0, '/opt/field_trainer')
from ft_touch import TouchSensor
import time

def calibrate_with_testing(device_id):
    sensor = TouchSensor(device_id)
    
    if not sensor.hardware_available:
        print('❌ Hardware not available', flush=True)
        return False
    
    print(f'Hardware detected at 0x{sensor.mpu_address:02X}', flush=True)
    print('', flush=True)
    
    # Step 1: Baseline calibration
    print('Step 1: Baseline Calibration', flush=True)
    print('Keep device still for 3 seconds...', flush=True)
    sys.stdout.flush()
    time.sleep(1)
    
    if not sensor.calibrate(duration=3.0):
        print('❌ Baseline calibration failed', flush=True)
        return False
    
    print(f'✅ Baseline set', flush=True)
    print('', flush=True)
    sys.stdout.flush()
    
    # Step 2: Touch testing and threshold tuning
    max_attempts = 3
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f'Step 2: Touch Test (Attempt {attempt}/{max_attempts})', flush=True)
        print(f'Current threshold: {sensor.threshold}', flush=True)
        print('', flush=True)
        print('=' * 50, flush=True)
        print('TAP THE DEVICE 5 TIMES in the next 10 seconds', flush=True)
        print('=' * 50, flush=True)
        print('Get ready...', flush=True)
        sys.stdout.flush()
        time.sleep(2)
        
        print('3...', flush=True)
        sys.stdout.flush()
        time.sleep(1)
        
        print('2...', flush=True)
        sys.stdout.flush()
        time.sleep(1)
        
        print('1...', flush=True)
        sys.stdout.flush()
        time.sleep(1)
        
        print('', flush=True)
        print('*** GO! TAP NOW! ***', flush=True)
        print('', flush=True)
        sys.stdout.flush()
        
        # Run 10-second test (starts immediately after GO message)
        result = sensor.test_detection(duration=10.0)
        
        touches = result['touches_detected']
        max_mag = result['max_magnitude']
        avg_mag = result['avg_magnitude']
        
        print('', flush=True)
        print(f'Results: {touches} touches detected', flush=True)
        print(f'Max magnitude: {max_mag:.2f}', flush=True)
        print(f'Avg magnitude: {avg_mag:.2f}', flush=True)
        print('', flush=True)
        sys.stdout.flush()
        
        # Check if in acceptable range (4-8 touches)
        if touches >= 4 and touches <= 8:
            print('✅ Touch detection working well!', flush=True)
            print(f'Final threshold: {sensor.threshold}', flush=True)
            sys.stdout.flush()
            return True
        
        # Auto-adjust threshold
        if touches > 10:
            new_threshold = sensor.threshold + 1.0
            print(f'⚠️  Too sensitive ({touches} touches)', flush=True)
            print(f'Increasing threshold from {sensor.threshold} to {new_threshold}', flush=True)
            sensor.update_threshold(new_threshold)
        elif touches < 3:
            new_threshold = max(0.5, sensor.threshold - 0.5)
            print(f'⚠️  Not sensitive enough ({touches} touches)', flush=True)
            print(f'Decreasing threshold from {sensor.threshold} to {new_threshold}', flush=True)
            sensor.update_threshold(new_threshold)
        else:
            if touches < 4:
                new_threshold = max(0.5, sensor.threshold - 0.3)
                print(f'ℹ️  Slightly low ({touches} touches)', flush=True)
                print(f'Adjusting threshold from {sensor.threshold} to {new_threshold}', flush=True)
            else:
                new_threshold = sensor.threshold + 0.5
                print(f'ℹ️  Slightly high ({touches} touches)', flush=True)
                print(f'Adjusting threshold from {sensor.threshold} to {new_threshold}', flush=True)
            sensor.update_threshold(new_threshold)
        
        print('', flush=True)
        sys.stdout.flush()
        
        if attempt < max_attempts:
            print('Retrying with new threshold in 3 seconds...', flush=True)
            sys.stdout.flush()
            time.sleep(3)
    
    print(f'⚠️  Calibration complete with threshold: {sensor.threshold}', flush=True)
    print('You may need to manually tune later', flush=True)
    sys.stdout.flush()
    return True

# Run calibration
success = calibrate_with_testing('192.168.99.$device')
sys.exit(0 if success else 1)
PYTHON_EOF
"
    
    if [ $? -eq 0 ]; then
        echo "✅ Device $device calibration complete"
    else
        echo "❌ Device $device calibration failed"
    fi
    
done

echo ""
echo "================================================"
echo "Calibration Complete"
echo "================================================"
