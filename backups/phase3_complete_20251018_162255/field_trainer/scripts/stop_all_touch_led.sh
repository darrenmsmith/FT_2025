#!/bin/bash
# Stop touch LED service on all devices

echo "Stopping Touch LED service on all devices..."

for device in 100 101 102 103 104 105; do
    echo "Stopping Device $device..."
    /opt/field_trainer/scripts/touch_led_control.sh $device stop
done

echo "All services stopped"
