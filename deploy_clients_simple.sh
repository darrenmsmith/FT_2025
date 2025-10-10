#!/bin/bash
DEVICES="101 102 103 104 105"  

for device in $DEVICES; do
    DEVICE_IP="192.168.99.${device}"
    echo "=== Deploying to Device${device} ==="
    
    ssh pi@${DEVICE_IP} "mkdir -p /tmp/from-device0"
    scp -q -r /opt/* pi@${DEVICE_IP}:/tmp/from-device0/
    ssh pi@${DEVICE_IP} "sudo cp -r /tmp/from-device0/* /opt/ && sudo chown -R pi:pi /opt && rm -rf /tmp/from-device0"
    
    echo "  ✓ Device${device} ready"
done

echo "Now start clients on each device"
