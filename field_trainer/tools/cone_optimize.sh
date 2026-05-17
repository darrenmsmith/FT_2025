#!/bin/bash
#
# Pi Zero W cone optimization script
# Applies the validated recipe from D1 (Bucket B + Plan A NM removal)
#
# Effects:
#   - Disable cloud-init (file marker)
#   - Disable ModemManager, keyboard-setup, rpi-eeprom-update
#   - Disable + mask apt-daily timers/services
#   - Mask NetworkManager + dependencies
#
# Does NOT reboot — operator must do so manually after reviewing output.
#
# Idempotent. Safe to re-run.

set -e   # fail fast

echo "=========================================="
echo "Cone optimization script"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "=========================================="

echo ""
echo "=== BASELINE BEFORE CHANGES ==="
systemd-analyze
echo ""

echo "=== APPLYING CHANGES ==="

echo "[1/4] Disable cloud-init via marker file..."
sudo touch /etc/cloud/cloud-init.disabled

echo "[2/4] Disable unused services..."
sudo systemctl disable ModemManager.service       || true
sudo systemctl disable keyboard-setup.service     || true
sudo systemctl disable rpi-eeprom-update.service  || true

echo "[3/4] Disable apt-daily timers + mask services..."
sudo systemctl disable apt-daily.timer apt-daily-upgrade.timer  || true
sudo systemctl mask    apt-daily.service apt-daily-upgrade.service

echo "[4/4] Mask NetworkManager stack..."
sudo systemctl mask NetworkManager.service
sudo systemctl mask NetworkManager-wait-online.service
sudo systemctl mask NetworkManager-dispatcher.service

echo ""
echo "=== VERIFICATION ==="
for svc in ModemManager keyboard-setup rpi-eeprom-update \
           apt-daily.timer apt-daily-upgrade.timer \
           apt-daily.service apt-daily-upgrade.service \
           NetworkManager NetworkManager-wait-online NetworkManager-dispatcher; do
  printf "  %-40s %s\n" "$svc" "$(systemctl is-enabled $svc 2>&1)"
done
echo "  cloud-init.disabled file:                $(test -f /etc/cloud/cloud-init.disabled && echo present || echo MISSING)"

echo ""
echo "=========================================="
echo "Changes applied. Review output above."
echo ""
echo "To activate: sudo reboot"
echo ""
echo "To roll back, run:"
echo "  sudo rm /etc/cloud/cloud-init.disabled"
echo "  sudo systemctl enable ModemManager keyboard-setup rpi-eeprom-update"
echo "  sudo systemctl enable apt-daily.timer apt-daily-upgrade.timer"
echo "  sudo systemctl unmask apt-daily.service apt-daily-upgrade.service"
echo "  sudo systemctl unmask NetworkManager.service NetworkManager-wait-online.service NetworkManager-dispatcher.service"
echo "  sudo systemctl enable NetworkManager.service"
echo "  sudo reboot"
echo "=========================================="
