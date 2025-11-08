#!/bin/bash
# MAC filter management script for Field Trainer
# Uses ebtables for MAC filtering on bat0 interface

set -e

# Load configuration
source /etc/field-trainer-macs.conf 2>/dev/null || {
    echo "ERROR: MAC configuration not found at /etc/field-trainer-macs.conf"
    exit 1
}

ACTION=${1:-status}
LOG_FILE="/var/log/ft_mac_filter.log"
CHAIN_NAME="FT_MAC_FILTER"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

case $ACTION in
    enable)
        log "Enabling MAC filtering on bat0..."

        # Create custom chain if it doesn't exist
        sudo ebtables -t filter -N "$CHAIN_NAME" 2>/dev/null || true
        sudo ebtables -t filter -F "$CHAIN_NAME"

        # Add all authorized device MACs to allow list
        for i in {0..5}; do
            MAC_VAR="DEVICE_${i}_MAC"
            MAC="${!MAC_VAR}"

            if [ -n "$MAC" ]; then
                log "  Authorizing Device $i: $MAC"
                # Allow traffic from this MAC
                sudo ebtables -t filter -A "$CHAIN_NAME" -s "$MAC" -j ACCEPT
                sudo ebtables -t filter -A "$CHAIN_NAME" -d "$MAC" -j ACCEPT
            fi
        done

        # Drop all other traffic (default deny)
        sudo ebtables -t filter -A "$CHAIN_NAME" -j DROP

        # Apply chain to INPUT on bat0
        sudo ebtables -t filter -D INPUT -i bat0 -j "$CHAIN_NAME" 2>/dev/null || true
        sudo ebtables -t filter -I INPUT -i bat0 -j "$CHAIN_NAME"

        # Apply chain to FORWARD on bat0
        sudo ebtables -t filter -D FORWARD -i bat0 -j "$CHAIN_NAME" 2>/dev/null || true
        sudo ebtables -t filter -I FORWARD -i bat0 -j "$CHAIN_NAME"

        # Save state
        sudo mkdir -p /etc
        echo "{\"mac_filtering\": true, \"timestamp\": \"$(date -Iseconds)\"}" | sudo tee /etc/field-trainer-mac-filter-state > /dev/null
        log "MAC filtering ENABLED on bat0"
        ;;

    disable)
        log "Disabling MAC filtering on bat0..."

        # Remove rules from INPUT and FORWARD
        sudo ebtables -t filter -D INPUT -i bat0 -j "$CHAIN_NAME" 2>/dev/null || true
        sudo ebtables -t filter -D FORWARD -i bat0 -j "$CHAIN_NAME" 2>/dev/null || true

        # Flush and delete custom chain
        sudo ebtables -t filter -F "$CHAIN_NAME" 2>/dev/null || true
        sudo ebtables -t filter -X "$CHAIN_NAME" 2>/dev/null || true

        # Save state
        echo "{\"mac_filtering\": false, \"timestamp\": \"$(date -Iseconds)\"}" | sudo tee /etc/field-trainer-mac-filter-state > /dev/null
        log "MAC filtering DISABLED on bat0"
        ;;

    status)
        echo "=== MAC Filter Status (ebtables) ==="
        echo ""

        if sudo ebtables -t filter -L "$CHAIN_NAME" 2>/dev/null; then
            echo ""
            echo "Chain $CHAIN_NAME exists - MAC filtering appears to be ENABLED"
            echo ""
            echo "Rules applied to INPUT:"
            sudo ebtables -t filter -L INPUT | grep -A 2 "$CHAIN_NAME" || echo "  Not applied to INPUT"
            echo ""
            echo "Rules applied to FORWARD:"
            sudo ebtables -t filter -L FORWARD | grep -A 2 "$CHAIN_NAME" || echo "  Not applied to FORWARD"
        else
            echo "Chain $CHAIN_NAME does not exist - MAC filtering is DISABLED"
        fi

        if [ -f /etc/field-trainer-mac-filter-state ]; then
            echo ""
            echo "=== Saved State ==="
            cat /etc/field-trainer-mac-filter-state
        fi

        echo ""
        echo "=== Current Mesh Neighbors ==="
        sudo batctl meshif bat0 neighbors
        ;;

    *)
        echo "Usage: $0 {enable|disable|status}"
        exit 1
        ;;
esac
