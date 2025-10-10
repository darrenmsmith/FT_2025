#!/bin/bash
DEVICES="101 102 103 104 105"
echo "======================================"
echo "Field Trainer Client Deployment"
echo "======================================"
for device in $DEVICES; do
    DEVICE_IP="192.168.99.${device}"
    echo "=== Deploying to Device${device} ==="
    if ! ping -c 1 -W 2 ${DEVICE_IP} > /dev/null 2>&1; then
        echo "WARNING: Cannot reach ${DEVICE_IP} - skipping"
        continue
    fi
    ssh pi@${DEVICE_IP} "mkdir -p /tmp/from-device0" 2>/dev/null
    scp -q -r /opt/* pi@${DEVICE_IP}:/tmp/from-device0/
    ssh pi@${DEVICE_IP} "sudo cp -r /tmp/from-device0/* /opt/ && sudo chown -R pi:pi /opt && rm -rf /tmp/from-device0"
    ssh pi@${DEVICE_IP} "sudo pip3 install rpi-ws281x smbus2 --break-system-packages" 2>&1 | grep -v "WARNING:"
    if ssh pi@${DEVICE_IP} "test -f /opt/field_client_connection.py"; then
        echo "  ✓ Device${device} ready"
    else
        echo "  ✗ Device${device} FAILED"
    fi
    echo ""
done
echo "Deployment complete!"
