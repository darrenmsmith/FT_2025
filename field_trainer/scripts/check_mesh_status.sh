#!/bin/bash
echo "================================================"
echo "BATMAN Mesh Network Status"
echo "================================================"
echo ""
echo "=== Device 0 (Gateway) ==="
echo "Neighbors:"
sudo batctl n
echo ""
echo "Originator Table:"
sudo batctl o
echo ""
echo "=== Ping Test ==="
for device in 101 102 103 104 105; do
    echo -n "Device $device: "
    if ping -c 1 -W 1 192.168.99.$device > /dev/null 2>&1; then
        echo "✅ Reachable"
    else
        echo "❌ Not reachable"
    fi
done
