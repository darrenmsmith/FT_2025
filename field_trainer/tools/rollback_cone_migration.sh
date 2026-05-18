#!/bin/bash
# tools/rollback_cone_migration.sh
#
# Roll back changes made by migrate_cone_to_dev_pattern.sh.
# Restores files from the backup directory created during migration.
#
# RUN THIS ON THE CONE. NOT ON THE GATEWAY.
#
# Usage:
#   sudo bash rollback_cone_migration.sh <backup-dir>

set -u

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script needs sudo. Run with: sudo $0 $*" >&2
    exit 1
fi

if [ $# -ne 1 ]; then
    echo "Usage: sudo bash $0 <backup-dir>" >&2
    echo "  e.g.: sudo bash $0 /var/backups/ft-migration-20260518_123456" >&2
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: Backup directory not found: $BACKUP_DIR" >&2
    exit 1
fi

echo "=========================================="
echo "Cone Migration Rollback"
echo "=========================================="
echo "Backup directory: $BACKUP_DIR"
echo

if [ -f "$BACKUP_DIR/MIGRATION_METADATA.txt" ]; then
    echo "Backup metadata:"
    cat "$BACKUP_DIR/MIGRATION_METADATA.txt"
    echo
fi

echo "Files available in backup:"
ls "$BACKUP_DIR" | grep -v MIGRATION_METADATA.txt | sed 's/^/  /'
echo

read -p "Proceed with rollback? (yes/no): " ANS
if [ "$ANS" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo
echo "[1/5] Stopping new services"
for svc in field-trainer-client.service batman-mesh.service rfkill-unblock-wifi.service; do
    if systemctl list-unit-files --no-pager 2>/dev/null | grep -q "^$svc"; then
        echo "  stopping: $svc"
        systemctl stop "$svc" 2>/dev/null || true
    fi
done

echo
echo "[2/5] Disabling new services"
for svc in field-trainer-client.service batman-mesh.service rfkill-unblock-wifi.service; do
    if systemctl list-unit-files --no-pager 2>/dev/null | grep -q "^$svc"; then
        echo "  disabling: $svc"
        systemctl disable "$svc" 2>/dev/null || true
    fi
done

echo
echo "[3/5] Removing new files"
for f in \
    /etc/systemd/system/batman-mesh.service \
    /etc/systemd/system/field-trainer-client.service \
    /etc/systemd/system/rfkill-unblock-wifi.service \
    /usr/local/bin/start-batman-mesh.sh
do
    if [ -e "$f" ]; then
        echo "  removing: $f"
        rm -f "$f"
    fi
done

echo
echo "[4/5] Restoring backed-up files"
for f in batman-mesh-client.service field-client.service; do
    if [ -f "$BACKUP_DIR/$f" ]; then
        cp -p "$BACKUP_DIR/$f" "/etc/systemd/system/$f"
        echo "  restored: /etc/systemd/system/$f"
    fi
done
for f in start-batman-mesh-client.sh stop-batman-mesh-client.sh; do
    if [ -f "$BACKUP_DIR/$f" ]; then
        cp -p "$BACKUP_DIR/$f" "/usr/local/bin/$f"
        chmod 755 "/usr/local/bin/$f"
        echo "  restored: /usr/local/bin/$f"
    fi
done
if [ -d "$BACKUP_DIR/batman-mesh-client.service.d" ]; then
    cp -rp "$BACKUP_DIR/batman-mesh-client.service.d" /etc/systemd/system/
    echo "  restored: /etc/systemd/system/batman-mesh-client.service.d/"
fi
for f in hostname hosts; do
    if [ -f "$BACKUP_DIR/$f" ]; then
        cp -p "$BACKUP_DIR/$f" "/etc/$f"
        echo "  restored: /etc/$f"
    fi
done
if [ -f /etc/hostname ]; then
    hostnamectl set-hostname "$(cat /etc/hostname)" 2>/dev/null || true
fi

echo
echo "[5/5] Reloading systemd and re-enabling restored services"
systemctl daemon-reload
echo "  daemon-reload"
for svc in batman-mesh-client.service field-client.service; do
    if [ -f "/etc/systemd/system/$svc" ]; then
        echo "  enabling: $svc"
        systemctl enable "$svc" 2>/dev/null || true
    fi
done

echo
echo "=========================================="
echo "Rollback complete."
echo "=========================================="
echo
echo "Hostname restored to: $(cat /etc/hostname)"
echo "REBOOT to fully activate: sudo reboot"
echo
echo "After reboot, verify with:"
echo "  hostname"
echo "  systemctl is-active batman-mesh-client.service"
echo "  systemctl is-active field-client.service"
echo "  ping -c 3 192.168.99.100"
