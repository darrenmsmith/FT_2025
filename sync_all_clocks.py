#!/usr/bin/env python3
"""
Sync All Device Clocks Script for Field Trainer
Run on Device 0 to synchronize time across all devices in the mesh
"""

import subprocess
import time
import sys

def run_ssh_command(device_ip, command, timeout=10):
    """Run SSH command on remote device"""
    try:
        result = subprocess.run([
            'ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no',
            f'pi@{device_ip}', command
        ], capture_output=True, text=True, timeout=timeout)
        
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "SSH timeout"
    except Exception as e:
        return False, "", str(e)

def get_device0_time():
    """Get Device 0's current time in format suitable for setting"""
    try:
        result = subprocess.run(['date', '+%Y-%m-%d %H:%M:%S'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None

def sync_device_time(device_ip, device_name, target_time):
    """Sync a single device's time"""
    print(f"Syncing {device_name} ({device_ip})...", end=" ", flush=True)
    
    # First, check if device is reachable
    success, output, error = run_ssh_command(device_ip, 'echo "ping"', timeout=5)
    if not success:
        print(f"FAILED - Cannot reach device: {error}")
        return False
    
    # Set the time on the remote device
    sync_command = f'sudo date -s "{target_time}"'
    success, output, error = run_ssh_command(device_ip, sync_command)
    
    if success:
        # Verify the time was set correctly
        success2, new_time, error2 = run_ssh_command(device_ip, 'date "+%H:%M:%S"')
        if success2:
            print(f"SUCCESS - New time: {new_time}")
            return True
        else:
            print(f"SUCCESS - Time set (verification failed)")
            return True
    else:
        print(f"FAILED - {error}")
        return False

def restart_field_clients():
    """Restart field-client services on all devices"""
    devices = [
        ("Device 1", "192.168.99.101"),
        ("Device 2", "192.168.99.102"), 
        ("Device 3", "192.168.99.103"),
        ("Device 4", "192.168.99.104"),
        ("Device 5", "192.168.99.105")
    ]
    
    print("\nRestarting field-client services...")
    for device_name, device_ip in devices:
        print(f"Restarting {device_name}...", end=" ", flush=True)
        success, output, error = run_ssh_command(
            device_ip, 
            'sudo systemctl restart field-client', 
            timeout=15
        )
        if success:
            print("SUCCESS")
        else:
            print(f"FAILED - {error}")

def main():
    print("=" * 60)
    print("Field Trainer Clock Synchronization Script")
    print("=" * 60)
    
    # Get Device 0's time
    target_time = get_device0_time()
    if not target_time:
        print("ERROR: Cannot get Device 0's time")
        sys.exit(1)
    
    print(f"Device 0 time: {target_time}")
    print("Synchronizing all devices to Device 0 time...")
    print("-" * 60)
    
    # Define devices to sync (exclude Device 0)
    devices = [
        ("Device 1", "192.168.99.101"),
        ("Device 2", "192.168.99.102"), 
        ("Device 3", "192.168.99.103"),
        ("Device 4", "192.168.99.104"),
        ("Device 5", "192.168.99.105")
    ]
    
    # Sync each device
    success_count = 0
    for device_name, device_ip in devices:
        if sync_device_time(device_ip, device_name, target_time):
            success_count += 1
    
    print("-" * 60)
    print(f"Synchronization complete: {success_count}/{len(devices)} devices synced")
    
    if success_count == len(devices):
        print("All devices synchronized successfully!")
        
        # Restart field-client services
        restart_field_clients()
        
        print("\nWaiting 10 seconds for services to restart...")
        time.sleep(10)
        
        print("\nRunning clock check to verify synchronization...")
        try:
            subprocess.run(['python3', 'check_clocks.py'], cwd='/opt/field-trainer/app')
        except Exception as e:
            print(f"Clock check failed: {e}")
            print("Run 'python3 check_clocks.py' manually to verify sync")
    else:
        print("Some devices failed to synchronize. Check connectivity and try again.")
        print("You may need to manually sync failed devices.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()