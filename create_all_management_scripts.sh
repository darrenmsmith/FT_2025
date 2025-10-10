#!/bin/bash
# Master script to create all Field Trainer management scripts on Device0
# Run this after git clone to set up complete management infrastructure

echo "Creating Field Trainer management scripts..."

# 1. Deploy all clients script
cat > /opt/deploy_all_clients.sh << 'EOF1'
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
EOF1

# 2. Restart all clients script
cat > /opt/restart_all_clients.sh << 'EOF2'
#!/bin/bash
DEVICES="101 102 103 104 105"
echo "Stopping all clients..."
for device in $DEVICES; do
    ssh pi@192.168.99.${device} "sudo pkill -f field_client_connection" 2>/dev/null
done
sleep 2
echo "Starting all clients with sudo (for LED access)..."
for device in $DEVICES; do
    ssh -f pi@192.168.99.${device} "cd /opt && sudo python3 field_client_connection.py --node-id 192.168.99.${device} > /tmp/client.log 2>&1 &"
    echo "  Started Device${device}"
done
sleep 3
echo ""
echo "Connected devices:"
curl -s http://localhost:5000/api/state | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f'  - {n[\"node_id\"]} ({n[\"status\"]})') for n in data['nodes']]"
EOF2

# 3. Setup client services script
cat > /opt/setup_client_services.sh << 'EOF3'
#!/bin/bash
DEVICES="101 102 103 104 105"
for device in $DEVICES; do
    DEVICE_IP="192.168.99.${device}"
    echo "=== Setting up service on Device${device} ==="
    ssh pi@${DEVICE_IP} "sudo tee /etc/systemd/system/field-trainer-client.service > /dev/null" << 'SVCEOF'
[Unit]
Description=Field Trainer Client
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt
ExecStart=/usr/bin/python3 /opt/field_client_connection.py --node-id 192.168.99.DEVICE_NUM
ExecStop=/bin/bash -c 'python3 /opt/shutdown_leds.py; pkill -TERM -f field_client_connection; sleep 1'
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=10
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

    ssh pi@${DEVICE_IP} "sudo sed -i 's/DEVICE_NUM/${device}/g' /etc/systemd/system/field-trainer-client.service"
    ssh pi@${DEVICE_IP} "sudo pkill -9 -f field_client_connection" 2>/dev/null
    ssh pi@${DEVICE_IP} "sudo systemctl daemon-reload && sudo systemctl enable field-trainer-client.service && sudo systemctl start field-trainer-client.service"
    echo "  Service status:"
    ssh pi@${DEVICE_IP} "sudo systemctl is-active field-trainer-client.service"
    echo "  ✓ Device${device} configured"
    echo ""
done
echo "All services configured!"
EOF3

# 4. LED shutdown script
cat > /opt/shutdown_leds.py << 'EOF4'
#!/usr/bin/env python3
"""Turn off LEDs on shutdown"""
try:
    from rpi_ws281x import PixelStrip, Color
    strip = PixelStrip(15, 12, 800000, 10, False, 128, 0)
    strip.begin()
    for i in range(15):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
    print("LEDs turned off")
except Exception as e:
    print(f"LED shutdown error: {e}")
EOF4

# Make all scripts executable
chmod +x /opt/deploy_all_clients.sh
chmod +x /opt/restart_all_clients.sh
chmod +x /opt/setup_client_services.sh
chmod +x /opt/shutdown_leds.py

echo ""
echo "======================================"
echo "✓ All management scripts created!"
echo "======================================"
echo ""
echo "Available commands:"
echo "  /opt/deploy_all_clients.sh      - Deploy code to all clients"
echo "  /opt/restart_all_clients.sh     - Restart all client services"
echo "  /opt/setup_client_services.sh   - Setup systemd on all clients"
echo "  /opt/shutdown_leds.py           - Turn off LEDs (used by services)"
echo ""
