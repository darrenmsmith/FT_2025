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
