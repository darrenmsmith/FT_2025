#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Field Trainer Unified Provisioner v2.0 (Controller or Client)
# Fixed BSSID enforcement to prevent IBSS split-brain
# Raspberry Pi OS Bookworm (Lite), NetworkManager present
# - IBSS (ad-hoc) + B.A.T.M.A.N. adv mesh on wlan0 -> bat0 (STATIC IPs)
# - ENFORCED fixed BSSID to prevent IBSS split-brain
# - Chrony time sync (Controller = master; Clients sync to controller)
# - Controller (Device0) can NAT to uplink on wlan1
# - Installs robust systemd services with autostart
# - Standardized logs
# ----------------------------------------------------------------------------
# Usage examples:
#  Controller (Device0, static 192.168.99.100/24, uplink via wlan1):
#    sudo bash unified_provisioner_v2.sh \
#      --role controller --ip 192.168.99.100 --ssid ft_mesh \
#      --bssid 1A:E2:20:EF:07:7B --freq 2412 --uplink-if wlan1
#
#  Client (Node1, static 192.168.99.101/24, controller at .100):
#    sudo bash unified_provisioner_v2.sh \
#      --role client --ip 192.168.99.101 --controller 192.168.99.100 \
#      --ssid ft_mesh --bssid 1A:E2:20:EF:07:7B --freq 2412
#
# Optional: seed params via /boot/field.env (ROLE, IP, SSID, BSSID, FREQ, CONTROLLER, UPLINK_IF, BOOT_DELAY)
# ----------------------------------------------------------------------------
set -euo pipefail

# Log both to console and file
LOG_FILE=/var/log/field-provision.log
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[+] Starting Field Trainer Provisioner v2.0 at $(date -u +%FT%TZ)"

# ---------------- Defaults ----------------
ROLE="client"                # controller|client
IP=""                        # e.g. 192.168.99.101
CIDR="/24"                   # single subnet
IFACE="wlan0"               # mesh radio
UPLINK_IF="wlan1"           # controller only
SSID="ft_mesh"              # Updated default SSID
BSSID="1A:E2:20:EF:07:7B"   # ENFORCED fixed BSSID for IBSS
FREQ=2412                    # MHz (ch1 2.4GHz)
CONTROLLER="192.168.99.100" # controller IP (for clients)
HEARTBEAT_SEC=5
BOOT_DELAY=8                 # seconds (grace for Pi Zero)

# Seed from /boot/field.env if present
if [[ -f /boot/field.env ]]; then
  # shellcheck disable=SC1091
  source /boot/field.env
fi

# ---------------- Parse args ----------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --role) ROLE="$2"; shift 2;;
    --ip) IP="$2"; shift 2;;
    --ssid) SSID="$2"; shift 2;;
    --bssid) BSSID="$2"; shift 2;;
    --freq) FREQ="$2"; shift 2;;
    --iface) IFACE="$2"; shift 2;;
    --controller) CONTROLLER="$2"; shift 2;;
    --uplink-if) UPLINK_IF="$2"; shift 2;;
    --heartbeat) HEARTBEAT_SEC="$2"; shift 2;;
    --boot-delay) BOOT_DELAY="$2"; shift 2;;
    *) echo "[!] Unknown arg: $1"; exit 2;;
  esac
done

if [[ -z "$IP" ]]; then
  echo "[!] --ip is required (e.g., 192.168.99.100)"; exit 2
fi
if [[ "$ROLE" != "controller" && "$ROLE" != "client" ]]; then
  echo "[!] --role must be controller|client"; exit 2
fi

echo "[+] Configuration:"
echo "    Role: $ROLE"
echo "    IP: $IP$CIDR"
echo "    SSID: $SSID"
echo "    BSSID: $BSSID (ENFORCED)"
echo "    Frequency: $FREQ MHz"
echo "    Controller: $CONTROLLER"

# ---------------- Packages ----------------
echo "[+] Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y batctl iw iproute2 chrony python3 python3-pip

if [[ "$ROLE" == "controller" ]]; then
  # NAT persistence
  apt-get install -y iptables-persistent
fi

# ---------------- NetworkManager: ignore mesh ifaces ----------------
echo "[+] Configuring NetworkManager unmanaged devices (wlan0, bat0)"
mkdir -p /etc/NetworkManager/conf.d
cat >/etc/NetworkManager/conf.d/99-field-unmanaged.conf <<EOF
[keyfile]
unmanaged-devices=interface-name:${IFACE};interface-name:bat0
EOF
systemctl reload NetworkManager 2>/dev/null || true

# ---------------- Ensure batman-adv loads at boot ----------------
mkdir -p /etc/modules-load.d
if ! grep -q '^batman-adv$' /etc/modules-load.d/batman-adv.conf 2>/dev/null; then
  echo batman-adv >/etc/modules-load.d/batman-adv.conf
fi

# ---------------- Mesh defaults ----------------
cat >/etc/default/mesh-ibss <<EOF
IFACE="${IFACE}"
MESH_SSID="${SSID}"
FREQ=${FREQ}
BSSID="${BSSID}"
BAT_IP="${IP}${CIDR}"
CONTROLLER_IP="${CONTROLLER}"
BOOT_DELAY="${BOOT_DELAY}"
EOF

# ---------------- Enhanced Mesh bring-up script ----------------
cat >/usr/local/bin/mesh-ibss.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source /etc/default/mesh-ibss

echo "[$(date)] Starting mesh configuration for interface $IFACE"

# Grace for slow boots (Pi Zero)
sleep "${BOOT_DELAY:-8}" || true

# Power save off for stability (ignore failure if not supported)
iw dev "$IFACE" set power_save off 2>/dev/null || true

# Reset & configure interface
echo "[$(date)] Resetting interface $IFACE"
ip link set "$IFACE" down || true
ip addr flush dev "$IFACE" || true

# Load batman-adv module
modprobe batman-adv

# Leave any existing IBSS network first
echo "[$(date)] Leaving any existing IBSS network"
iw dev "$IFACE" ibss leave 2>/dev/null || true

# Set type ibss & bring up
echo "[$(date)] Setting $IFACE to IBSS mode"
iw "$IFACE" set type ibss
ip link set "$IFACE" up

# CRITICAL: Join IBSS with ENFORCED fixed BSSID to prevent split-brain
echo "[$(date)] Joining IBSS network: SSID=$MESH_SSID, FREQ=$FREQ MHz, BSSID=$BSSID (ENFORCED)"
iw "$IFACE" ibss join "$MESH_SSID" "$FREQ" fixed-freq "$BSSID"

# Verify IBSS join
sleep 2
CURRENT_CELL=$(iwconfig "$IFACE" 2>/dev/null | grep "Cell:" | awk '{print $4}' | cut -d: -f2-)
if [[ "$CURRENT_CELL" != "$BSSID" ]]; then
  echo "[$(date)] WARNING: IBSS join may have failed. Expected BSSID $BSSID, got $CURRENT_CELL"
  echo "[$(date)] Retrying IBSS join..."
  iw "$IFACE" ibss leave 2>/dev/null || true
  sleep 1
  iw "$IFACE" ibss join "$MESH_SSID" "$FREQ" fixed-freq "$BSSID"
  sleep 2
  CURRENT_CELL=$(iwconfig "$IFACE" 2>/dev/null | grep "Cell:" | awk '{print $4}' | cut -d: -f2-)
  echo "[$(date)] After retry: BSSID is now $CURRENT_CELL"
fi

# Attach to BATMAN
echo "[$(date)] Adding $IFACE to BATMAN mesh"
batctl if add "$IFACE" || true
ip link set up dev bat0

# Configure IP address
echo "[$(date)] Setting IP address $BAT_IP on bat0"
ip addr replace "$BAT_IP" dev bat0

# If we know a controller, set default route via it (clients only)
if [[ -n "${CONTROLLER_IP:-}" && "${CONTROLLER_IP}" != "" ]]; then
  # Only add if not controller IP itself
  if ! ip -4 addr show dev bat0 | grep -q "${CONTROLLER_IP}"; then
    echo "[$(date)] Setting default route via controller $CONTROLLER_IP"
    ip route replace default via "${CONTROLLER_IP}" dev bat0 || true
  fi
fi

echo "[$(date)] Mesh configuration complete"
echo "[$(date)] IBSS Status: $(iwconfig $IFACE 2>/dev/null | grep 'Mode:Ad-Hoc' || echo 'Not in Ad-Hoc mode')"
echo "[$(date)] BATMAN neighbors: $(batctl n 2>/dev/null | wc -l) devices"

EOF
chmod +x /usr/local/bin/mesh-ibss.sh

# ---------------- Mesh systemd unit ----------------
cat >/etc/systemd/system/mesh-ibss.service <<EOF
[Unit]
Description=Bring up IBSS + BATMAN-adv on ${IFACE}
After=NetworkManager.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=/etc/default/mesh-ibss
# Additional boot grace for Pi Zero
ExecStartPre=/bin/sleep ${BOOT_DELAY}
ExecStart=/usr/local/bin/mesh-ibss.sh
ExecStop=/bin/true
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now mesh-ibss

# ---------------- Chrony time sync ----------------
echo "[+] Configuring chrony..."
if [[ "$ROLE" == "controller" ]]; then
  if ! grep -q '# FieldTrainer allow' /etc/chrony/chrony.conf; then
    {
      echo '# FieldTrainer allow'
      echo 'allow 192.168.99.0/24'
      echo 'local stratum 10'
    } >> /etc/chrony/chrony.conf
  fi
else
  if ! grep -q '# FieldTrainer server' /etc/chrony/chrony.conf; then
    {
      echo '# FieldTrainer server'
      echo "server ${CONTROLLER} iburst"
    } >> /etc/chrony/chrony.conf
  fi
fi
systemctl restart chrony || systemctl restart chronyd || true

# ---------------- Controller gateway (NAT on wlan1) ----------------
if [[ "$ROLE" == "controller" ]]; then
  echo "[+] Enabling IPv4 forwarding & NAT via ${UPLINK_IF}"
  # Persist IP forwarding
  cat >/etc/sysctl.d/99-field-forward.conf <<EOF
net.ipv4.ip_forward=1
EOF
  sysctl -p /etc/sysctl.d/99-field-forward.conf || true

  # Flush old rules (idempotent)
  iptables -t nat -F || true
  iptables -F FORWARD || true

  # NAT: bat0 -> uplink
  iptables -t nat -A POSTROUTING -o "$UPLINK_IF" -j MASQUERADE
  iptables -A FORWARD -i "$UPLINK_IF" -o bat0 -m state --state RELATED,ESTABLISHED -j ACCEPT
  iptables -A FORWARD -i bat0 -o "$UPLINK_IF" -j ACCEPT

  # Save rules
  if command -v netfilter-persistent >/dev/null 2>&1; then
    netfilter-persistent save || true
  else
    iptables-save > /etc/iptables/rules.v4 || true
  fi
fi

# ---------------- Controller service (Flask + heartbeat) ----------------
if [[ "$ROLE" == "controller" ]]; then
  echo "[+] Installing controller service"
  mkdir -p /opt/field-trainer
  # Copy app if present in /boot or current dir
  if [[ -f /boot/field_trainer.py ]]; then cp /boot/field_trainer.py /opt/field-trainer/; fi
  if [[ -f ./field_trainer.py ]]; then cp ./field_trainer.py /opt/field-trainer/; fi
  # Minimal deps
  apt install -y python3-flask

  # Seed sample courses.json if missing (192.168.99.x)
  if [[ ! -f /opt/field-trainer/courses.json ]]; then
    cat >/opt/field-trainer/courses.json <<'JSON'
{
  "courses": [
    {
      "name": "Course A",
      "stations": [
        {"node_id": "192.168.99.101", "role": "sprint_start"},
        {"node_id": "192.168.99.102", "role": "sprint_mid"},
        {"node_id": "192.168.99.103", "role": "sprint_finish"}
      ]
    }
  ]
}
JSON
  fi

  cat >/etc/systemd/system/field-controller.service <<'EOF'
[Unit]
Description=Field Trainer Controller (Flask + heartbeat)
After=NetworkManager.service mesh-ibss.service network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/opt/field-trainer
ExecStart=/usr/bin/python3 /opt/field-trainer/field_trainer.py
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now field-controller || true
fi

# ---------------- Client service ----------------
if [[ "$ROLE" == "client" ]]; then
  echo "[+] Installing client service"
  mkdir -p /opt/field-client
  # Copy client if present in /boot or current dir
  if [[ -f /boot/field_client.py ]]; then cp /boot/field_client.py /opt/field-client/; fi
  if [[ -f ./field_client.py ]]; then cp ./field_client.py /opt/field-client/; fi

  cat >/etc/default/field-client <<EOF
CONTROLLER_IP=${CONTROLLER}
CONTROLLER_PORT=6000
HEARTBEAT_SEC=${HEARTBEAT_SEC}
# NODE_ID=${IP}
EOF

  cat >/etc/systemd/system/field-client.service <<'EOF'
[Unit]
Description=Field Trainer Client (heartbeat)
After=NetworkManager.service mesh-ibss.service network-online.target
Wants=network-online.target
# Extra grace for Pi Zero
ExecStartPre=/bin/sleep 6

[Service]
User=pi
WorkingDirectory=/opt/field-client
EnvironmentFile=/etc/default/field-client
ExecStart=/usr/bin/python3 /opt/field-client/field_client.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now field-client || true
fi

# ---------------- SSH (keep enabled) ----------------
if systemctl list-unit-files | grep -q '^ssh\.service'; then
  systemctl enable --now ssh || true
fi

# ---------------- Final verification ----------------
echo "[+] Waiting for mesh to stabilize..."
sleep 10

echo "[+] Mesh status verification:"
echo "    Interface: $(iwconfig $IFACE 2>/dev/null | grep 'Mode:Ad-Hoc' || echo 'IBSS not active')"
CURRENT_CELL=$(iwconfig "$IFACE" 2>/dev/null | grep "Cell:" | awk '{print $4}' | cut -d: -f2- || echo "No cell")
echo "    Current BSSID: $CURRENT_CELL"
echo "    Expected BSSID: $BSSID"
if [[ "$CURRENT_CELL" == "$BSSID" ]]; then
  echo "    ✓ BSSID matches (IBSS join successful)"
else
  echo "    ✗ BSSID mismatch (IBSS join may have failed)"
fi
echo "    BATMAN neighbors: $(batctl n 2>/dev/null | wc -l || echo 0) devices"
echo "    bat0 IP: $(ip addr show bat0 2>/dev/null | grep 'inet ' | awk '{print $2}' || echo 'Not configured')"

# ---------------- Done ----------------
echo "[+] Provisioning v2.0 complete. Reboot recommended: sudo reboot"
echo "[+] To check mesh status: iwconfig wlan0 && batctl n -H"
echo "[+] Expected BSSID: $BSSID"
