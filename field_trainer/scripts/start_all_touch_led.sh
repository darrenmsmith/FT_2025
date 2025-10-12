#!/bin/bash
# Start touch LED service on all devices

echo "================================================"
echo "Starting Touch LED Service on All Devices"
echo "================================================"
echo ""

for device in 100 101 102 103 104 105; do
    echo "Starting Device $device..."
    /opt/field_trainer/scripts/touch_led_control.sh $device start
    echo ""
done

echo "================================================"
echo "All services started"
echo "================================================"
echo ""
echo "Check status: ./check_touch_led_status.sh"
echo "Stop all: ./stop_all_touch_led.sh"
