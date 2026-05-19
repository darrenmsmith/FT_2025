#!/bin/bash
# tools/migrate_cone_to_dev_pattern.sh
#
# Purpose: Migrate a Beta cone (hostname Device<N>, batman-mesh-client.service,
# field-client.service) to the Dev pattern (hostname Device<N>pi,
# batman-mesh.service, field-trainer-client.service with graceful shutdown).
#
# RUN THIS ON THE CONE (after scp'ing). NOT ON THE GATEWAY.
#
# Usage:
#   sudo bash migrate_cone_to_dev_pattern.sh [--dry-run] [--yes]

set -u

DRY_RUN=0
SKIP_CONFIRM=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --yes)     SKIP_CONFIRM=1 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

if [ "$EUID" -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    echo "ERROR: This script needs sudo. Run with: sudo $0" >&2
    exit 1
fi

section() { echo; echo "[$1] $2"; }

echo "=========================================="
echo "Beta Cone -> Dev Pattern Migration"
echo "=========================================="
echo "Mode: $([ "$DRY_RUN" -eq 1 ] && echo 'DRY-RUN (no changes)' || echo 'EXECUTE')"

HOST="$(hostname)"
if [[ "$HOST" =~ ^Device([1-5])$ ]]; then
    DEVICE_NUM="${BASH_REMATCH[1]}"
elif [[ "$HOST" =~ ^Device([1-5])pi$ ]]; then
    DEVICE_NUM="${BASH_REMATCH[1]}"
    echo "NOTE: Hostname is already Device${DEVICE_NUM}pi — script will run idempotently."
else
    echo "ERROR: Hostname '$HOST' does not match Device<1-5> or Device<1-5>pi" >&2
    exit 1
fi

DEVICE_IP="192.168.99.10${DEVICE_NUM}"
NEW_HOSTNAME="Device${DEVICE_NUM}pi"

echo
echo "Detected:"
echo "  Current hostname:  $HOST"
echo "  Device number:     $DEVICE_NUM"
echo "  Device IP:         $DEVICE_IP"
echo "  Target hostname:   $NEW_HOSTNAME"
echo

echo "Existing files of interest:"
for f in \
    /etc/systemd/system/batman-mesh-client.service \
    /etc/systemd/system/batman-mesh.service \
    /etc/systemd/system/field-client.service \
    /etc/systemd/system/field-trainer-client.service \
    /etc/systemd/system/rfkill-unblock-wifi.service \
    /etc/systemd/system/batman-mesh-client.service.d \
    /usr/local/bin/start-batman-mesh-client.sh \
    /usr/local/bin/start-batman-mesh.sh \
    /usr/local/bin/stop-batman-mesh-client.sh
do
    if [ -e "$f" ]; then echo "  EXISTS: $f"; fi
done
echo

if [ "$DRY_RUN" -eq 0 ] && [ "$SKIP_CONFIRM" -eq 0 ]; then
    echo "This will REPLACE service files, hostname, and the mesh script."
    echo "Backups will be saved before any change."
    read -p "Proceed? (yes/no): " ANS
    if [ "$ANS" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
fi

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/var/backups/ft-migration-${TS}"

section "1/10" "Backing up to $BACKUP_DIR"
if [ "$DRY_RUN" -eq 0 ]; then mkdir -p "$BACKUP_DIR"; fi

for f in \
    /etc/systemd/system/batman-mesh-client.service \
    /etc/systemd/system/batman-mesh.service \
    /etc/systemd/system/field-client.service \
    /etc/systemd/system/field-trainer-client.service \
    /etc/systemd/system/rfkill-unblock-wifi.service \
    /usr/local/bin/start-batman-mesh-client.sh \
    /usr/local/bin/start-batman-mesh.sh \
    /usr/local/bin/stop-batman-mesh-client.sh \
    /etc/hostname \
    /etc/hosts
do
    if [ -f "$f" ]; then
        if [ "$DRY_RUN" -eq 0 ]; then cp -p "$f" "$BACKUP_DIR/"; fi
        echo "  backed up: $f"
    fi
done

if [ -d /etc/systemd/system/batman-mesh-client.service.d ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
        cp -rp /etc/systemd/system/batman-mesh-client.service.d "$BACKUP_DIR/"
    fi
    echo "  backed up: /etc/systemd/system/batman-mesh-client.service.d/"
fi

if [ "$DRY_RUN" -eq 0 ]; then
    cat > "$BACKUP_DIR/MIGRATION_METADATA.txt" <<META_EOF
ft-migration backup
Date:           $(date)
Source host:    $HOST
Device number:  $DEVICE_NUM
Device IP:      $DEVICE_IP
Target host:    $NEW_HOSTNAME
META_EOF
fi

section "2/10" "Stopping old services"
for svc in field-client.service batman-mesh-client.service; do
    if systemctl list-unit-files --no-pager 2>/dev/null | grep -q "^$svc"; then
        echo "  stopping: $svc"
        if [ "$DRY_RUN" -eq 0 ]; then
            systemctl stop "$svc" 2>/dev/null || true
        fi
    fi
done

section "3/10" "Writing /etc/systemd/system/batman-mesh.service"
NEW_BATMAN_MESH='[Unit]
Description=BATMAN-adv Mesh Network Client
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/start-batman-mesh.sh
RemainAfterExit=yes
RestartSec=10
Restart=on-failure

[Install]
WantedBy=multi-user.target
'
if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s' "$NEW_BATMAN_MESH" > /etc/systemd/system/batman-mesh.service
fi
echo "  wrote: batman-mesh.service"

section "4/10" "Writing /etc/systemd/system/field-trainer-client.service (--node-id $DEVICE_IP)"
NEW_FT_CLIENT="[Unit]
Description=Field Trainer Client
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt
ExecStart=/usr/bin/python3 -u /opt/field_client_connection.py --node-id ${DEVICE_IP}
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
"
if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s' "$NEW_FT_CLIENT" > /etc/systemd/system/field-trainer-client.service
fi
echo "  wrote: field-trainer-client.service"

section "5/10" "Writing /usr/local/bin/start-batman-mesh.sh"
NEW_MESH_SCRIPT="$(cat <<'MESH_END'
#!/bin/bash
set -e

# Defense against rfkill blocking wifi at boot.
# rfkill-unblock-wifi.service runs at boot but may race with systemd-rfkill
# (which restores saved rfkill state). Doing it here too guarantees correct
# state at the moment we actually need wlan0 up. Belt and suspenders.
rfkill unblock wifi 2>/dev/null || echo "WARNING: rfkill unblock failed (continuing)"

DEVICE_NUM=__DEVICE_NUM__
DEVICE_IP="192.168.99.10${DEVICE_NUM}"

echo "Starting BATMAN mesh on Device $DEVICE_NUM (Client)..."

MESH_IFACE="wlan0"
MESH_SSID="ft_mesh2"
MESH_FREQ="2412"
MESH_BSSID="00:11:22:33:44:55"

timeout=30
while [ $timeout -gt 0 ]; do
    if ip link show $MESH_IFACE >/dev/null 2>&1; then
        break
    fi
    sleep 1
    timeout=$((timeout - 1))
done

if [ $timeout -eq 0 ]; then
    echo "ERROR: Timeout waiting for $MESH_IFACE"
    exit 1
fi

driver=$(basename $(readlink /sys/class/net/$MESH_IFACE/device/driver))
if [ "$driver" != "brcmfmac" ]; then
    echo "ERROR: $MESH_IFACE is not brcmfmac (got: $driver)"
    exit 1
fi

ip link set dev bat0 down 2>/dev/null || true
ip link set dev $MESH_IFACE down 2>/dev/null || true
pkill -f "wpa_supplicant.*$MESH_IFACE" 2>/dev/null || true
sleep 0.3

iw dev $MESH_IFACE set type ibss || { echo "ERROR: Cannot set IBSS mode"; exit 1; }
ip link set $MESH_IFACE up || { echo "ERROR: Cannot bring up $MESH_IFACE"; exit 1; }
iw dev $MESH_IFACE ibss join $MESH_SSID $MESH_FREQ fixed-freq $MESH_BSSID || { echo "ERROR: Cannot join IBSS network"; exit 1; }

# Poll for IBSS join (replaces fixed 5s sleep; faster on most boots)
ibss_timeout=30   # 30 iterations x 0.2s = 6 seconds max
while [ $ibss_timeout -gt 0 ]; do
    if iwconfig $MESH_IFACE 2>/dev/null | grep -q "$MESH_SSID"; then
        break
    fi
    sleep 0.2
    ibss_timeout=$((ibss_timeout - 1))
done

if [ $ibss_timeout -eq 0 ]; then
    echo "ERROR: Not connected to $MESH_SSID (timed out after 6s)"
    exit 1
fi

batctl meshif bat0 interface add $MESH_IFACE || { echo "ERROR: Cannot add to batman"; exit 1; }
ip link set dev bat0 up || { echo "ERROR: Cannot bring up bat0"; exit 1; }
sleep 0.3

ip addr flush dev bat0
ip addr add ${DEVICE_IP}/24 dev bat0
ip route add default via 192.168.99.100 dev bat0 || true
echo "nameserver 192.168.99.100" | tee /etc/resolv.conf

echo "BATMAN mesh started on Device $DEVICE_NUM. IP: $DEVICE_IP, SSID: $MESH_SSID"
batctl meshif bat0 if 2>/dev/null || true
ip addr show bat0 | grep "inet " || true
MESH_END
)"
NEW_MESH_SCRIPT="${NEW_MESH_SCRIPT//__DEVICE_NUM__/$DEVICE_NUM}"

if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s\n' "$NEW_MESH_SCRIPT" > /usr/local/bin/start-batman-mesh.sh
    chmod 755 /usr/local/bin/start-batman-mesh.sh
    chown root:root /usr/local/bin/start-batman-mesh.sh
fi
echo "  wrote: start-batman-mesh.sh"

section "6/10" "Writing /etc/systemd/system/rfkill-unblock-wifi.service (ENABLED)"
NEW_RFKILL_SVC='[Unit]
Description=Unblock wifi rfkill at boot
Before=batman-mesh.service
Wants=batman-mesh.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock wifi
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
'
if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s' "$NEW_RFKILL_SVC" > /etc/systemd/system/rfkill-unblock-wifi.service
fi
echo "  wrote: rfkill-unblock-wifi.service"

section "7/10" "Disabling and removing old files"
for svc in field-client.service batman-mesh-client.service; do
    if systemctl list-unit-files --no-pager 2>/dev/null | grep -q "^$svc"; then
        echo "  disabling: $svc"
        if [ "$DRY_RUN" -eq 0 ]; then
            systemctl disable "$svc" 2>/dev/null || true
        fi
    fi
done
for f in \
    /etc/systemd/system/batman-mesh-client.service \
    /etc/systemd/system/field-client.service \
    /usr/local/bin/start-batman-mesh-client.sh \
    /usr/local/bin/stop-batman-mesh-client.sh
do
    if [ -e "$f" ]; then
        echo "  removing: $f"
        if [ "$DRY_RUN" -eq 0 ]; then rm -f "$f"; fi
    fi
done
if [ -d /etc/systemd/system/batman-mesh-client.service.d ]; then
    echo "  removing: /etc/systemd/system/batman-mesh-client.service.d/"
    if [ "$DRY_RUN" -eq 0 ]; then
        rm -rf /etc/systemd/system/batman-mesh-client.service.d
    fi
fi

section "8/10" "Updating hostname -> $NEW_HOSTNAME"
if [ "$DRY_RUN" -eq 0 ]; then
    echo "$NEW_HOSTNAME" > /etc/hostname
    hostnamectl set-hostname "$NEW_HOSTNAME" 2>/dev/null || true
    sed -i "s/Device${DEVICE_NUM} Device${DEVICE_NUM}/Device${DEVICE_NUM}pi/g" /etc/hosts
    sed -i "s/Device${DEVICE_NUM}\([[:space:]]\|\$\)/Device${DEVICE_NUM}pi\1/g" /etc/hosts
fi
echo "  /etc/hostname and /etc/hosts updated"

section "9/10" "Reloading systemd and enabling new services"
if [ "$DRY_RUN" -eq 0 ]; then systemctl daemon-reload; fi
echo "  daemon-reload"
for svc in batman-mesh.service field-trainer-client.service rfkill-unblock-wifi.service; do
    echo "  enabling: $svc"
    if [ "$DRY_RUN" -eq 0 ]; then
        systemctl enable "$svc" 2>/dev/null
    fi
done

section "10/10" "Migration core complete"
echo "  Beta->Dev pattern migration done."

# ---------- POST-MIGRATION OPTIMIZATION ----------
section "Post-migration" "Applying boot optimizations via optimize_cone.sh"
OPTIMIZE_SCRIPT="$(dirname "$0")/optimize_cone.sh"
if [ -f "$OPTIMIZE_SCRIPT" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        bash "$OPTIMIZE_SCRIPT" --dry-run
    else
        bash "$OPTIMIZE_SCRIPT"
    fi
else
    echo "  WARNING: optimize_cone.sh not found at:"
    echo "           $OPTIMIZE_SCRIPT"
    echo "  Migration is complete, but boot-time optimizations were skipped."
    echo "  To apply manually:"
    echo "    sudo bash <path-to-optimize_cone.sh>"
fi

# Migration completion marker (resolves KU-12)
if [ "$DRY_RUN" -eq 0 ]; then
    MIGRATION_MARKER="/var/log/ft-migration-complete.$(date +%Y%m%d_%H%M%S)"
    touch "$MIGRATION_MARKER"
    echo
    echo "  Migration marker: $MIGRATION_MARKER"
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo
    echo "DRY-RUN complete. No changes made."
    echo "To apply, re-run without --dry-run: sudo bash $0"
    exit 0
fi

echo
echo "=========================================="
echo "Migration applied successfully."
echo "=========================================="
echo "Hostname is now: $NEW_HOSTNAME (active after reboot)"
echo "Backup at:       $BACKUP_DIR"
echo
echo "NEXT STEP: REBOOT to activate"
echo "  sudo reboot"
echo
echo "After reboot, verify with:"
echo "  hostname"
echo "  systemctl is-active batman-mesh.service field-trainer-client.service rfkill-unblock-wifi.service"
echo "  ping -c 3 192.168.99.100"
echo "  ip -br addr show bat0"
echo
echo "ROLLBACK (if needed):"
echo "  sudo bash rollback_cone_migration.sh $BACKUP_DIR"
