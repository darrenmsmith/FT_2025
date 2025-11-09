#!/usr/bin/env python3
"""
Field Trainer Network Manager
Handles automatic switching between online and AP (offline) modes
"""

import json
import subprocess
import time
import os
import sys
import signal
import logging
from datetime import datetime
import socket

# Configuration
CONFIG_FILE = '/opt/data/network-config.json'
STATUS_FILE = '/opt/data/network-status.json'
LOG_FILE = '/var/log/ft_network_manager.log'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class NetworkManager:
    def __init__(self):
        self.config = self.load_config()
        self.running = True
        self.current_mode = self.config['network_mode']['current']

    def load_config(self):
        """Load or create default configuration"""
        if not os.path.exists(CONFIG_FILE):
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            default = {
                "network_mode": {
                    "current": "online",
                    "auto_switch": True
                },
                "monitoring": {
                    "internet_check_interval": 60,
                    "internet_check_retries": 3,
                    "failback_delay": 300
                },
                "access_point": {
                    "enabled": False,
                    "ssid": "Field_Trainer",
                    "password": "RaspberryField2025",
                    "ip": "192.168.10.1"
                }
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default, f, indent=4)
            logging.info("Created default configuration")
            return default

        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)

    def save_config(self):
        """Save configuration to file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        # Ensure pi user can write to it
        try:
            import pwd
            pi_uid = pwd.getpwnam('pi').pw_uid
            pi_gid = pwd.getpwnam('pi').pw_gid
            os.chown(CONFIG_FILE, pi_uid, pi_gid)
        except:
            pass

    def save_status(self, mode, message=""):
        """Save current status to file"""
        status = {
            'mode': mode,
            'timestamp': datetime.now().isoformat(),
            'message': message
        }
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=4)
        # Ensure pi user can write to it
        try:
            import pwd
            pi_uid = pwd.getpwnam('pi').pw_uid
            pi_gid = pwd.getpwnam('pi').pw_gid
            os.chown(STATUS_FILE, pi_uid, pi_gid)
        except:
            pass

    def check_internet(self):
        """Check if internet is reachable"""
        for host in ['8.8.8.8', '1.1.1.1']:
            try:
                socket.create_connection((host, 53), timeout=3)
                return True
            except:
                continue
        return False

    def run_command(self, cmd, check=False):
        """Run shell command and return result"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {cmd}\n{e}")
            return False

    def start_ap_mode(self):
        """Switch to Access Point mode"""
        logging.info("="*60)
        logging.info("Switching to AP mode (offline)")
        logging.info("="*60)

        try:
            # Stop wpa_supplicant on wlan1
            logging.info("Step 1: Stopping wpa_supplicant...")
            self.run_command('sudo systemctl stop wpa_supplicant@wlan1')
            time.sleep(1)

            # Flush IP and bring interface down
            logging.info("Step 2: Resetting wlan1...")
            self.run_command('sudo ip link set dev wlan1 down')
            self.run_command('sudo ip addr flush dev wlan1')
            time.sleep(1)

            # Set static IP for AP mode
            logging.info("Step 3: Setting static IP 192.168.10.1...")
            self.run_command('sudo ip addr add 192.168.10.1/24 dev wlan1')
            self.run_command('sudo ip link set dev wlan1 up')
            time.sleep(1)

            # Start hostapd (Access Point)
            logging.info("Step 4: Starting hostapd...")
            self.run_command('sudo systemctl start hostapd-ft')
            time.sleep(2)

            # Start dnsmasq (DHCP/DNS)
            logging.info("Step 5: Starting dnsmasq...")
            self.run_command('sudo systemctl start dnsmasq-ft')
            time.sleep(1)

            # Update configuration
            self.current_mode = 'offline'
            self.config['network_mode']['current'] = 'offline'
            self.config['access_point']['enabled'] = True
            self.save_config()
            self.save_status('offline', 'AP mode active - Network: Field_Trainer')

            logging.info("="*60)
            logging.info("AP mode active!")
            logging.info(f"WiFi SSID: {self.config['access_point']['ssid']}")
            logging.info(f"Password: {self.config['access_point']['password']}")
            logging.info(f"AP IP: {self.config['access_point']['ip']}")
            logging.info("Access: http://fieldtrainer.local:5001")
            logging.info("="*60)

            return True

        except Exception as e:
            logging.error(f"Failed to start AP mode: {e}")
            self.save_status('error', f'Failed to start AP mode: {e}')
            return False

    def stop_ap_mode(self):
        """Return to online mode"""
        logging.info("="*60)
        logging.info("Switching to online mode")
        logging.info("="*60)

        try:
            # Stop AP services
            logging.info("Step 1: Stopping AP services...")
            self.run_command('sudo systemctl stop dnsmasq-ft')
            self.run_command('sudo systemctl stop hostapd-ft')
            time.sleep(1)

            # Reset interface
            logging.info("Step 2: Resetting wlan1...")
            self.run_command('sudo ip link set dev wlan1 down')
            self.run_command('sudo ip addr flush dev wlan1')
            time.sleep(1)

            # Restart wpa_supplicant (reconnect to smithhome)
            logging.info("Step 3: Restarting wpa_supplicant...")
            self.run_command('sudo systemctl restart wpa_supplicant@wlan1')
            time.sleep(2)

            # Restart DHCP client
            logging.info("Step 4: Restarting DHCP client...")
            self.run_command('sudo systemctl restart dhcpcd')
            time.sleep(5)

            # Update configuration
            self.current_mode = 'online'
            self.config['network_mode']['current'] = 'online'
            self.config['access_point']['enabled'] = False
            self.save_config()
            self.save_status('online', 'Connected to smithhome WiFi')

            logging.info("="*60)
            logging.info("Online mode active!")
            logging.info("Reconnected to smithhome WiFi")
            logging.info("="*60)

            return True

        except Exception as e:
            logging.error(f"Failed to return to online mode: {e}")
            self.save_status('error', f'Failed to return to online mode: {e}')
            return False

    def monitor_loop(self):
        """Main monitoring loop"""
        consecutive_failures = 0

        logging.info("Network monitoring started")
        logging.info(f"Current mode: {self.current_mode}")
        logging.info(f"Auto-switch: {self.config['network_mode']['auto_switch']}")

        while self.running:
            try:
                # Reload config in case it was changed
                self.config = self.load_config()

                if not self.config['network_mode']['auto_switch']:
                    # Auto-switch disabled, just sleep
                    time.sleep(self.config['monitoring']['internet_check_interval'])
                    continue

                if self.current_mode == 'online':
                    # Check internet connectivity
                    if self.check_internet():
                        consecutive_failures = 0
                        logging.info("Internet check: OK")
                    else:
                        consecutive_failures += 1
                        logging.warning(
                            f"Internet check failed "
                            f"({consecutive_failures}/{self.config['monitoring']['internet_check_retries']})"
                        )

                        # Switch to AP mode after 3 failures
                        if consecutive_failures >= self.config['monitoring']['internet_check_retries']:
                            logging.warning("Internet lost - switching to AP mode")
                            self.start_ap_mode()
                            consecutive_failures = 0

                elif self.current_mode == 'offline':
                    # Check if internet has returned
                    if self.check_internet():
                        logging.info("Internet detected, waiting for stability...")
                        time.sleep(self.config['monitoring']['failback_delay'])

                        # Check again to ensure it's stable
                        if self.check_internet():
                            logging.info("Internet stable - switching back to online mode")
                            self.stop_ap_mode()

                # Sleep before next check
                time.sleep(self.config['monitoring']['internet_check_interval'])

            except Exception as e:
                logging.error(f"Monitor loop error: {e}")
                time.sleep(10)

    def run(self):
        """Main run method"""
        # Setup signal handlers
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

        logging.info("Field Trainer Network Manager starting...")
        logging.info(f"Mode: {self.current_mode}")

        # Start monitoring
        self.monitor_loop()


def main():
    """Main entry point"""
    if os.geteuid() != 0:
        print("ERROR: This script must be run as root")
        print("Usage: sudo python3 /opt/scripts/ft-network-manager.py")
        sys.exit(1)

    # Handle command line arguments
    if len(sys.argv) > 1:
        nm = NetworkManager()
        command = sys.argv[1]

        if command == 'force-online':
            print("Forcing online mode...")
            nm.stop_ap_mode()

        elif command == 'force-offline':
            print("Forcing AP mode (offline)...")
            nm.start_ap_mode()

        elif command == 'status':
            print("\n" + "="*60)
            print("Field Trainer Network Manager - Status")
            print("="*60)
            print(json.dumps(nm.config, indent=2))
            print("="*60)
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    status = json.load(f)
                print("\nCurrent Status:")
                print(json.dumps(status, indent=2))
            print("="*60 + "\n")

        else:
            print(f"Unknown command: {command}")
            print("Available commands: force-online, force-offline, status")
            sys.exit(1)
    else:
        # Run monitoring service
        manager = NetworkManager()
        manager.run()


if __name__ == "__main__":
    main()
