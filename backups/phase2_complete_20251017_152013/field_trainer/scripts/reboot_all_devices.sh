#!/bin/bash
echo "Rebooting all client devices (1-5)..."
for device in 101 102 103 104 105; do
    echo "Rebooting Device $device..."
    ssh pi@192.168.99.$device 'sudo reboot' &
done
wait
echo ""
echo "All devices rebooting. Wait 60 seconds before testing."
