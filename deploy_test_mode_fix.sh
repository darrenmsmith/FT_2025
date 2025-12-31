#!/bin/bash
# Deploy test mode fix to all cones
# Run this after re-enabling mesh network

echo "================================================"
echo "Deploying Test Mode Fix to All Cones"
echo "================================================"
echo ""

for i in {1..5}; do
    echo "Deploying to Cone $i (192.168.99.10$i)..."

    if scp -o ConnectTimeout=5 -o StrictHostKeyChecking=no /opt/field_client_connection.py pi@192.168.99.10$i:/opt/ 2>&1 | grep -q "100%"; then
        if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no pi@192.168.99.10$i 'sudo systemctl restart field-trainer-client' 2>&1; then
            echo "✓ Cone $i deployed and restarted"
        else
            echo "✗ Cone $i - restart failed"
        fi
    else
        echo "✗ Cone $i - not reachable or copy failed"
    fi
    echo ""
done

echo "================================================"
echo "Deployment Complete"
echo "================================================"
echo ""
echo "Waiting 10 seconds for connections to stabilize..."
sleep 10

echo ""
echo "Checking logs for Cone 3..."
ssh -o ConnectTimeout=5 pi@192.168.99.103 'sudo journalctl -u field-trainer-client --since "30 seconds ago" --no-pager | tail -5' 2>/dev/null

echo ""
echo "✅ Done! Test mode should now beep when touched."
