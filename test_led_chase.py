#!/usr/bin/env python3
"""Test LED solid colors and chase animations on C1-C5"""

import requests
import time

BASE_URL = "http://localhost:5001"  # Correct port!

def test_led(device_id, color, description):
    """Send LED command and return success status."""
    print(f"   {description}")
    try:
        response = requests.post(
            f"{BASE_URL}/api/settings/test-led",
            json={'device': device_id, 'color': color},
            timeout=5
        )
        if response.status_code == 200:
            print(f"      ✓ Success")
            return True
        else:
            print(f"      ✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"      ✗ Error: {e}")
        return False

def main():
    devices = {
        '192.168.99.101': 'C1',
        '192.168.99.102': 'C2',
        '192.168.99.103': 'C3',
        '192.168.99.104': 'C4',
        '192.168.99.105': 'C5',
    }

    print("\n" + "="*70)
    print("LED TEST: SOLID COLORS AND CHASE ANIMATIONS")
    print("="*70 + "\n")

    # PHASE 1: Solid colors
    print("PHASE 1: SOLID COLORS (verify LED commands work)")
    print("-"*70)

    for color in ['red', 'green', 'blue', 'yellow', 'orange']:
        print(f"\n🎨 Setting all cones to {color.upper()}...")
        for device_id, name in devices.items():
            test_led(device_id, color, f"{name} → {color}")

        print(f"   ⏱️  Observe for 3 seconds...")
        time.sleep(3)

    # PHASE 2: Chase animations
    print("\n" + "="*70)
    print("PHASE 2: CHASE ANIMATIONS")
    print("-"*70)

    for color in ['chase_red', 'chase_green', 'chase_blue', 'chase_yellow', 'chase_amber']:
        print(f"\n🌀 Setting all cones to {color.upper()}...")
        for device_id, name in devices.items():
            test_led(device_id, color, f"{name} → {color}")

        print(f"   ⏱️  Observe for 4 seconds...")
        time.sleep(4)

    # Return to standby
    print("\n" + "="*70)
    print("🧹 Returning all cones to ORANGE (standby)...")
    for device_id, name in devices.items():
        test_led(device_id, 'orange', f"{name} → orange")

    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
