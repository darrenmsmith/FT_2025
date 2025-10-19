#!/bin/bash
# Control touch LED service on a device

if [ $# -lt 2 ]; then
    echo "Usage: $0 <device_number> <start|stop|status>"
    echo "Example: $0 101 start"
    exit 1
fi

DEVICE=$1
ACTION=$2
IP="192.168.99.$DEVICE"

case $ACTION in
    start)
        echo "Starting touch LED service on Device $DEVICE..."
        ssh pi@$IP "cd /opt/field_trainer && sudo nohup python3 ft_touch_led_service.py --device-id 192.168.99.$DEVICE > /tmp/touch_led.log 2>&1 &"
        sleep 1
        echo "Service started. Check status with: $0 $DEVICE status"
        ;;
    
    stop)
        echo "Stopping touch LED service on Device $DEVICE..."
        ssh pi@$IP "sudo pkill -f ft_touch_led_service"
        echo "Service stopped"
        ;;
    
    status)
        echo "Checking Device $DEVICE status..."
        ssh pi@$IP "ps aux | grep ft_touch_led_service | grep -v grep || echo 'Service not running'"
        ;;
    
    log)
        echo "Showing logs from Device $DEVICE..."
        ssh pi@$IP "tail -30 /tmp/touch_led.log"
        ;;
    
    *)
        echo "Invalid action: $ACTION"
        echo "Use: start, stop, status, or log"
        exit 1
        ;;
esac
