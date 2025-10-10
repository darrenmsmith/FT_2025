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
