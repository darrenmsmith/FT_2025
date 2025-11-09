#!/bin/bash
# Apply saved MAC filter state on boot

sleep 15  # Wait for mesh to be fully up

if [ -f /etc/field-trainer-mac-filter-state ]; then
    STATE=$(python3 -c "import json; print(json.load(open('/etc/field-trainer-mac-filter-state'))['mac_filtering'])" 2>/dev/null)

    if [ "$STATE" = "True" ] || [ "$STATE" = "true" ]; then
        /opt/scripts/manage_mac_filter.sh enable
    fi
fi
