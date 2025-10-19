#!/bin/bash
# Check touch LED service status on all devices

echo "================================================"
echo "Touch LED Service Status"
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
    
    STATUS=$(ssh pi@$IP "ps aux | grep ft_touch_led_service | grep -v grep" 2>/dev/null)
    
    if [ -z "$STATUS" ]; then
        echo "  ⚪ Service not running"
    else
        echo "  ✅ Service running"
        # Get touch count
        TOUCHES=$(ssh pi@$IP "grep 'Touch detected' /tmp/touch_led.log 2>/dev/null | wc -l" 2>/dev/null)
        echo "  Touches detected: $TOUCHES"
    fi
    
    echo ""
done

echo "================================================"
