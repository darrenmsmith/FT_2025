#!/bin/bash
###############################################################################
# optimize_cone.sh
#
# Apply Field Trainer cone boot-time optimizations on Pi Zero W mesh cones:
#   - Cloud-init disable marker file
#   - Mask 17 unnecessary units (cloud-init suite + ModemManager + Bucket-B
#     services + systemd-rfkill)
#   - Drop a completion marker file
#
# Idempotent: safe to run multiple times. Skips actions already applied.
# Intended for cones already migrated to Dev pattern (post-migration). The
# migrate_cone_to_dev_pattern.sh script invokes this as its final step; you
# can also run it standalone on already-migrated cones.
#
# Expected boot-time impact on Pi Zero W mesh cones: ~50-55s (down from
# 70-120s on un-optimized Beta cones).
#
# Session reference: SESSION_2026_05_18_NOTES.md (2026-05-18 session)
###############################################################################

set -e

# ---------- options ----------
DRY_RUN=0
QUIET=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --quiet)   QUIET=1 ;;
        -h|--help)
            cat <<'HELP_EOF'
Usage: sudo bash optimize_cone.sh [--dry-run] [--quiet]

Apply Field Trainer cone boot-time optimizations. Idempotent.

Options:
  --dry-run    Print actions without making changes
  --quiet      Suppress per-service "already masked" / "not installed" messages
  --help, -h   Show this help

What it does:
  1. Creates /etc/cloud/cloud-init.disabled (if cloud-init present)
  2. Masks 17 units: 7 cloud-init + ModemManager + 7 Bucket-B + systemd-rfkill
  3. Touches /var/log/ft-optimize-complete.<timestamp> as marker

Recommended after running: sudo reboot
HELP_EOF
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $arg" >&2
            echo "Run with --help for usage" >&2
            exit 2
            ;;
    esac
done

# ---------- safety checks ----------
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: must be run as root (or via sudo)" >&2
    exit 1
fi

# Warn if not on a migrated cone (but don't block — could be a re-run or future variant)
if [ ! -f /etc/systemd/system/batman-mesh.service ]; then
    echo "WARNING: /etc/systemd/system/batman-mesh.service not found."
    echo "         optimize_cone.sh is designed for Dev-pattern (migrated) cones."
    echo "         If this is a freshly-imaged cone, run migrate_cone_to_dev_pattern.sh first."
    echo "         Continuing anyway in 5 seconds (Ctrl-C to abort)..."
    sleep 5
fi

# ---------- helpers ----------
section() {
    echo
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# ---------- [1/3] cloud-init disable marker ----------
section "[1/3] Cloud-init disable marker"
if [ -d /etc/cloud ]; then
    if [ -f /etc/cloud/cloud-init.disabled ]; then
        echo "  [skip] /etc/cloud/cloud-init.disabled already present"
    else
        if [ "$DRY_RUN" -eq 0 ]; then
            touch /etc/cloud/cloud-init.disabled
        fi
        echo "  [new]  /etc/cloud/cloud-init.disabled created"
    fi
else
    echo "  [n/a]  /etc/cloud directory not present; cloud-init not installed"
fi

# ---------- [2/3] mask unnecessary units ----------
section "[2/3] Mask unnecessary units (17 total)"

# Each entry: <unit>|<category>
SERVICES_TO_MASK=(
    "cloud-init-local.service|cloud-init"
    "cloud-init-network.service|cloud-init"
    "cloud-init-main.service|cloud-init"
    "cloud-config.service|cloud-init"
    "cloud-final.service|cloud-init"
    "cloud-init.target|cloud-init"
    "cloud-init-hotplugd.socket|cloud-init"
    "ModemManager.service|no-modem-hardware"
    "avahi-daemon.service|bucket-b mDNS-not-used"
    "avahi-daemon.socket|bucket-b mDNS-not-used"
    "keyboard-setup.service|bucket-b headless-cone"
    "rpi-resize-swap-file.service|bucket-b swap-already-sized"
    "rpi-eeprom-update.service|bucket-b firmware-managed-elsewhere"
    "e2scrub_reap.service|bucket-b scrub-cleanup-not-needed"
    "systemd-timesyncd.service|bucket-b no-internet-via-mesh"
    "systemd-rfkill.service|rfkill-managed-inline"
    "systemd-rfkill.socket|rfkill-managed-inline"
)

MASKED_COUNT=0
ALREADY_MASKED_COUNT=0
NOT_INSTALLED_COUNT=0

for entry in "${SERVICES_TO_MASK[@]}"; do
    svc="${entry%%|*}"
    cat="${entry##*|}"

    if ! systemctl list-unit-files --no-legend "$svc" 2>/dev/null | grep -q .; then
        [ "$QUIET" -eq 0 ] && echo "  [n/a]  $svc (not installed; $cat)"
        NOT_INSTALLED_COUNT=$((NOT_INSTALLED_COUNT + 1))
        continue
    fi

    state=$(systemctl is-enabled "$svc" 2>/dev/null || echo "unknown")
    if [ "$state" = "masked" ]; then
        [ "$QUIET" -eq 0 ] && echo "  [skip] $svc already masked"
        ALREADY_MASKED_COUNT=$((ALREADY_MASKED_COUNT + 1))
    else
        if [ "$DRY_RUN" -eq 0 ]; then
            if ! systemctl mask "$svc" >/dev/null 2>&1; then
                echo "  [WARN] failed to mask $svc; continuing"
                continue
            fi
        fi
        echo "  [mask] $svc ($cat)"
        MASKED_COUNT=$((MASKED_COUNT + 1))
    fi
done

echo
echo "  Summary: newly-masked=$MASKED_COUNT  already-masked=$ALREADY_MASKED_COUNT  not-installed=$NOT_INSTALLED_COUNT"

# ---------- [3/3] completion marker ----------
section "[3/3] Completion marker"
MARKER="/var/log/ft-optimize-complete.$(date +%Y%m%d_%H%M%S)"
if [ "$DRY_RUN" -eq 0 ]; then
    touch "$MARKER"
fi
echo "  [new]  $MARKER"

# ---------- summary ----------
section "optimize_cone.sh complete"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "  DRY-RUN: no changes made."
    echo "  To apply: sudo bash $0"
else
    if [ "$MASKED_COUNT" -eq 0 ] && [ "$ALREADY_MASKED_COUNT" -gt 0 ]; then
        echo "  All optimizations were already in place. No reboot needed."
    else
        echo "  Reboot to activate all boot-time changes:"
        echo "    sudo reboot"
    fi
fi
echo
