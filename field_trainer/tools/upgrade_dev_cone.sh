#!/bin/bash
###############################################################################
# upgrade_dev_cone.sh
#
# Apply post-migration boot-time upgrades to an already-migrated cone (Dev OR Beta):
#   - Patch /usr/local/bin/start-batman-mesh.sh:
#     * add inline 'rfkill unblock wifi' (defense against systemd-rfkill race)
#     * trim Stage 1 sleeps (sleep 2 -> 0.3 x2, sleep 5 -> polling loop)
#   - Mask wlan1-internet.service if present (stray gateway-only service)
#   - Run optimize_cone.sh (idempotent - masks 20 units, drops marker)
#   - Drop /var/log/ft-upgrade-complete.<TS> marker
#
# Idempotent: safe to re-run. Patches are no-ops if already applied.
# Intended for already-migrated cones (hostname ending 'pi'), regardless of which
# heredoc generated their start-batman-mesh.sh:
#   - Dev cones: 'ibss_timeout' variable + literal "ft_mesh" + multi-line || { }
#   - Beta cones: 'ASSOC_TIMEOUT' variable + "$MESH_SSID" (ft_mesh2) + compact || {;}
# Verification accepts both forms; atomic guard still refuses partial writes.
# For un-migrated Beta cones, use migrate_cone_to_dev_pattern.sh instead.
#
# Session reference: 2026-05-19 D1pi-D5pi Dev fleet upgrade
###############################################################################

set -e

# ---------- safety checks ----------

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: must be run as root (or via sudo)" >&2
    exit 1
fi

HN=$(hostname)
case "$HN" in
    *pi)
        echo "Target: $HN (migrated cone)"
        ;;
    *)
        echo "ERROR: hostname '$HN' doesn't end in 'pi'." >&2
        echo "       This script is for already-migrated cones." >&2
        echo "       Use migrate_cone_to_dev_pattern.sh for un-migrated Beta cones." >&2
        exit 1
        ;;
esac

MESH_SCRIPT="/usr/local/bin/start-batman-mesh.sh"
if [ ! -f "$MESH_SCRIPT" ]; then
    echo "ERROR: $MESH_SCRIPT not found." >&2
    exit 1
fi

# ---------- [1/4] backup ----------

TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/ft-upgrade-${TS}"

echo
echo "=========================================="
echo "[1/4] Backing up to $BACKUP_DIR"
echo "=========================================="
mkdir -p "$BACKUP_DIR"
cp "$MESH_SCRIPT" "$BACKUP_DIR/start-batman-mesh.sh"
echo "  backed up: $MESH_SCRIPT"

# ---------- [2/4] patch start-batman-mesh.sh ----------

echo
echo "=========================================="
echo "[2/4] Patching start-batman-mesh.sh (rfkill + Stage 1 sleeps)"
echo "=========================================="

python3 - << 'PYEOF'
import re
from pathlib import Path

p = Path("/usr/local/bin/start-batman-mesh.sh")
src = p.read_text()
orig = src
already_done = []

# Normalize trailing whitespace from each line. Cosmetic cleanup AND robustness
# fix - D1pi had a stray trailing space after "|| {" that broke literal matching.
normalized = re.sub(r'[ \t]+$', '', src, flags=re.MULTILINE)
if normalized != src:
    print(f"    (normalized trailing whitespace: {len(src)} -> {len(normalized)} bytes)")
src = normalized

# Patch A: insert rfkill unblock after set -e
if "rfkill unblock wifi" in src:
    already_done.append("rfkill line already present")
else:
    rfkill_block = """
# Defense against rfkill blocking wifi at boot.
# rfkill-unblock-wifi.service runs at boot but may race with systemd-rfkill
# (which restores saved rfkill state). Doing it here too guarantees correct
# state at the moment we actually need wlan0 up. Belt and suspenders.
rfkill unblock wifi 2>/dev/null || echo "WARNING: rfkill unblock failed (continuing)"
"""
    src = src.replace("set -e\n", "set -e\n" + rfkill_block, 1)

# Patch B: sleep 2 after pkill -> sleep 0.3
old_b = 'pkill -f "wpa_supplicant.*$MESH_IFACE" 2>/dev/null || true\nsleep 2\n'
new_b = 'pkill -f "wpa_supplicant.*$MESH_IFACE" 2>/dev/null || true\nsleep 0.3\n'
if old_b in src:
    src = src.replace(old_b, new_b, 1)
elif new_b in src:
    already_done.append("sleep 0.3 after pkill already in place")

# Patch C: sleep 5 + verify -> polling loop
#   Dev cone heredoc uses 'ibss_timeout' variable + literal "ft_mesh"
#   Beta cone heredoc uses 'ASSOC_TIMEOUT' variable + "$MESH_SSID" (= ft_mesh2)
#   Either is acceptable; both replace the fixed 5s sleep with a polling loop
old_c = '''sleep 5

# Verify joined
if ! iwconfig $MESH_IFACE 2>/dev/null | grep -q "ft_mesh"; then
    echo "ERROR: Not connected to ft_mesh"
    exit 1
fi'''
new_c = '''# Poll for IBSS join (replaces fixed 5s sleep; faster on most boots)
ibss_timeout=30   # 30 iterations x 0.2s = 6 seconds max
while [ $ibss_timeout -gt 0 ]; do
    if iwconfig $MESH_IFACE 2>/dev/null | grep -q "ft_mesh"; then
        break
    fi
    sleep 0.2
    ibss_timeout=$((ibss_timeout - 1))
done

if [ $ibss_timeout -eq 0 ]; then
    echo "ERROR: Not connected to ft_mesh (timed out after 6s)"
    exit 1
fi'''
if old_c in src:
    src = src.replace(old_c, new_c, 1)
elif "ibss_timeout=30" in src or "ASSOC_TIMEOUT=30" in src:
    already_done.append("polling loop already in place (Dev or Beta style)")

# Patch D: sleep 2 after bat0 up -> sleep 0.3
#   Dev cone heredoc: multi-line braced format
#       ip link set dev bat0 up || {
#           echo "ERROR: Cannot bring up bat0"
#           exit 1
#       }
#   Beta cone heredoc: compact one-liner format
#       ip link set dev bat0 up || { echo "ERROR: Cannot bring up bat0"; exit 1; }
#   Regex below recognizes both forms followed by 'sleep 0.3' as "already trimmed"
old_d = '''ip link set dev bat0 up || {
    echo "ERROR: Cannot bring up bat0"
    exit 1
}
sleep 2
'''
new_d = '''ip link set dev bat0 up || {
    echo "ERROR: Cannot bring up bat0"
    exit 1
}
sleep 0.3
'''
bat0_trimmed_re = re.compile(
    r'ip link set dev bat0 up \|\| \{[^}]*\}\s*\n\s*sleep 0\.3',
    re.DOTALL
)
if old_d in src:
    src = src.replace(old_d, new_d, 1)
elif bat0_trimmed_re.search(src):
    already_done.append("sleep 0.3 after bat0 up already in place (Dev or Beta style)")

# Verify all patches landed (accept either Dev or Beta form for C and D)
checks = [
    ('A: rfkill line', 'rfkill unblock wifi' in src),
    ('B: sleep 0.3 after pkill', 'pkill -f "wpa_supplicant.*$MESH_IFACE" 2>/dev/null || true\nsleep 0.3\n' in src),
    ('C: IBSS polling loop', 'ibss_timeout=30' in src or 'ASSOC_TIMEOUT=30' in src),
    ('D: sleep 0.3 after bat0 up', bool(bat0_trimmed_re.search(src))),
]

print()
all_ok = True
for name, ok in checks:
    print(f"    [{'OK' if ok else 'FAIL'}] {name}")
    if not ok:
        all_ok = False

if not all_ok:
    print("\n    One or more patches did not land. NOT writing file.")
    print(f"    Inspect manually: {p}")
    raise SystemExit(1)

if src != orig:
    p.write_text(src)
    print(f"\n    File updated ({len(src)} bytes, was {len(orig)})")
else:
    print(f"\n    No changes needed (all patches already applied)")

if already_done:
    print()
    print("    Skipped (already in place):")
    for msg in already_done:
        print(f"      - {msg}")
PYEOF

# ---------- [3/4] handle wlan1-internet.service ----------

echo
echo "=========================================="
echo "[3/4] Remove wlan1-internet.service (gateway-only — no wlan1 on cones)"
echo "=========================================="

UNIT="wlan1-internet.service"
UNIT_PATH="/etc/systemd/system/$UNIT"

if systemctl list-unit-files --no-legend "$UNIT" 2>/dev/null | grep -q .; then
    state=$(systemctl is-enabled "$UNIT" 2>/dev/null)
    state="${state:-unknown}"
    if [ "$state" = "masked" ]; then
        echo "    [skip] already masked"
    else
        # Stop if running (safe no-op if not running or already failed)
        systemctl stop "$UNIT" >/dev/null 2>&1 || true
        # Disable to remove boot-time enable
        if systemctl disable "$UNIT" >/dev/null 2>&1; then
            echo "    [disable] removed boot-time enable"
        fi
        # Move real unit file aside (backup-before-edit per user preference)
        if [ -f "$UNIT_PATH" ] && [ ! -L "$UNIT_PATH" ]; then
            mv "$UNIT_PATH" "$UNIT_PATH.removed.$TS"
            systemctl daemon-reload
            echo "    [move]    $UNIT_PATH -> $UNIT_PATH.removed.$TS"
        fi
        # Mask (now possible since real file is moved aside)
        if systemctl mask "$UNIT" >/dev/null 2>&1; then
            echo "    [mask]    $UNIT"
        else
            echo "    [WARN]    mask failed — manual cleanup may be needed"
        fi
    fi
else
    echo "    [n/a]  $UNIT not installed"
fi

# ---------- [4/4] run optimize_cone.sh ----------

echo
echo "=========================================="
echo "[4/4] Run optimize_cone.sh (idempotent - masks 20 units)"
echo "=========================================="

OPTIMIZE_SCRIPT="$(dirname "$0")/optimize_cone.sh"
if [ -f "$OPTIMIZE_SCRIPT" ]; then
    bash "$OPTIMIZE_SCRIPT" --quiet
else
    echo "    WARNING: optimize_cone.sh not found at $OPTIMIZE_SCRIPT"
    echo "             Boot optimization masks NOT applied this run."
fi

# ---------- marker ----------

MARKER="/var/log/ft-upgrade-complete.${TS}"
touch "$MARKER"

# ---------- summary ----------

echo
echo "=========================================="
echo "upgrade_dev_cone.sh complete"
echo "=========================================="
echo "  Backup:  $BACKUP_DIR/start-batman-mesh.sh"
echo "  Marker:  $MARKER"
echo
echo "Reboot to activate all changes:"
echo "  sudo reboot"
echo
