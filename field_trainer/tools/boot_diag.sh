#!/usr/bin/env bash
# tools/boot_diag.sh
# Read-only boot diagnostic for Field Trainer fleet.
# Captures boot timing, mesh state, FT dependencies, and hardware config.
# Safe to run multiple times. No system changes. No sudo required.

set -u

HOST=$(hostname)
TS=$(date +%Y%m%d_%H%M%S)
OUT="/tmp/boot_diag_${HOST}_${TS}.txt"

section() {
  echo ""
  echo "=================================================================="
  echo "== $1"
  echo "=================================================================="
}

# Detect FT units once for reuse throughout the script
FT_UNITS=$(systemctl list-unit-files --no-pager 2>/dev/null \
           | grep -iE "field|ft[-_]" | awk '{print $1}')

{
  section "DEVICE INFO"
  echo "Hostname:    $HOST"
  echo "Date:        $(date -Iseconds)"
  echo "Model:       $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)"
  echo "Kernel:      $(uname -r)"
  echo "OS:          $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"')"
  echo "Uptime:      $(uptime -p)"

  section "BOOT TIMING SUMMARY"
  systemd-analyze 2>&1

  section "TOP 25 SLOWEST UNITS (blame)"
  systemd-analyze blame 2>&1 | head -25

  section "CRITICAL CHAIN (actual boot-blocking path)"
  systemd-analyze critical-chain 2>&1

  section "FAILED UNITS"
  systemctl list-units --failed --no-pager 2>&1

  section "NETWORK-WAIT SERVICES (common boot blockers)"
  for svc in systemd-networkd-wait-online NetworkManager-wait-online dhcpcd; do
    en=$(systemctl is-enabled "$svc" 2>/dev/null || echo "n/a")
    ac=$(systemctl is-active  "$svc" 2>/dev/null || echo "n/a")
    printf "  %-35s enabled=%-10s active=%s\n" "$svc" "$en" "$ac"
  done

  section "POTENTIALLY UNUSED SERVICES (status check only)"
  for svc in bluetooth hciuart triggerhappy ModemManager avahi-daemon \
             cups cups-browsed rpi-eeprom-update keyboard-setup \
             plymouth-quit-wait apt-daily.timer apt-daily-upgrade.timer \
             man-db.timer e2scrub_all.timer fstrim.timer logrotate.timer; do
    en=$(systemctl is-enabled "$svc" 2>/dev/null || echo "n/a")
    printf "  %-35s %s\n" "$svc" "$en"
  done

  section "MESH INTERFACE STATE"
  echo "-- IP addresses --"
  ip -br addr 2>&1
  echo ""
  echo "-- bat0 link --"
  ip link show bat0 2>&1 || echo "bat0 not present"
  echo ""
  echo "-- Mesh-related boot journal lines --"
  journalctl -b 0 --no-pager 2>/dev/null \
    | grep -iE "batman|bat0|ft_mesh2|wpa_supplicant|wlan0.*(UP|associated)" \
    | head -40

  section "FT SERVICE DISCOVERY"
  echo "-- Unit files matching field/ft --"
  if [ -n "$FT_UNITS" ]; then
    echo "$FT_UNITS"
  else
    echo "  (none found)"
  fi
  echo ""
  echo "-- Active units matching field/ft --"
  systemctl list-units --type=service --no-pager 2>&1 \
    | grep -iE "field|ft[-_]" || echo "  (none active)"

  section "FT SERVICE TIMING"
  if [ -z "$FT_UNITS" ]; then
    echo "  (no FT units detected to time)"
  else
    for u in $FT_UNITS; do
      echo "-- $u --"
      systemctl show "$u" --no-pager \
        -p ActiveState,SubState,ActiveEnterTimestamp,ExecMainStartTimestamp \
        2>&1
      echo ""
    done
  fi

  section "FT SERVICE DEPENDENCIES (what FT needs)"
  if [ -z "$FT_UNITS" ]; then
    echo "  (no FT units detected)"
  else
    for u in $FT_UNITS; do
      echo "-- Forward deps of $u (units it pulls in) --"
      systemctl list-dependencies "$u" --no-pager 2>&1 | head -60
      echo ""
      echo "-- Reverse deps of $u (what pulls in FT) --"
      systemctl list-dependencies --reverse "$u" --no-pager 2>&1 | head -30
      echo ""
    done
  fi

  section "FT UNIT FILE CONTENTS"
  if [ -z "$FT_UNITS" ]; then
    echo "  (no FT units detected)"
  else
    for u in $FT_UNITS; do
      path=$(systemctl show "$u" -p FragmentPath --value 2>/dev/null)
      if [ -n "$path" ] && [ -f "$path" ]; then
        echo "-- $u  ($path) --"
        cat "$path"
        echo ""
      fi
    done
  fi

  section "BOOT CONFIG (hardware interfaces enabled)"
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    if [ -f "$cfg" ]; then
      echo "-- $cfg (active hardware lines) --"
      grep -E "^[^#]*(dtparam|dtoverlay|enable_|start_x|gpu_mem)" "$cfg" 2>/dev/null
      break
    fi
  done

  section "KERNEL MODULES"
  echo "-- Loaded modules (lsmod) --"
  lsmod 2>&1
  echo ""
  echo "-- /etc/modules --"
  cat /etc/modules 2>/dev/null || echo "(not present)"
  echo ""
  echo "-- /etc/modules-load.d/ --"
  for f in /etc/modules-load.d/*.conf; do
    [ -f "$f" ] && echo "$f: $(tr '\n' ' ' < "$f")"
  done

  section "LISTENING PORTS"
  ss -tlnp 2>/dev/null | head -30 || netstat -tlnp 2>/dev/null | head -30

  section "ENABLED UNIT COUNT"
  n=$(systemctl list-unit-files --state=enabled --no-pager 2>/dev/null \
      | grep -c "enabled")
  echo "Total enabled unit files: $n"

  section "BOOT WARNINGS/ERRORS (last boot, priority >= warning)"
  journalctl -b 0 -p warning --no-pager 2>/dev/null | head -50 \
    || echo "(journalctl access limited)"

} | tee "$OUT"

echo ""
echo "Saved to: $OUT"
