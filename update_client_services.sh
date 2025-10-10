#!/bin/bash
DEVICES="101 102 103 104 105"

for device in $DEVICES; do
    DEVICE_IP="192.168.99.${device}"
    echo "Updating service on Device${device}..."
    
    # Update service file with LED cleanup
    ssh pi@${DEVICE_IP} "sudo tee /etc/systemd/system/field-trainer-client.service > /dev/null" << 'EOF'
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
EOF

    # Replace DEVICE_NUM
    ssh pi@${DEVICE_IP} "sudo sed -i 's/DEVICE_NUM/${device}/g' /etc/systemd/system/field-trainer-client.service"
    
    # Reload and restart
    ssh pi@${DEVICE_IP} "sudo systemctl daemon-reload && sudo systemctl restart field-trainer-client.service"
    
    echo "  ✓ Device${device} updated"
done

echo "All services updated with LED cleanup!"
