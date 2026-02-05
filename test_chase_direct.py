#!/usr/bin/env python3
"""
Direct LED test - calls REGISTRY.set_led() via HTTP API endpoint.
This mimics exactly what the Settings page does.
"""

import requests
import time

BASE_URL = "http://localhost:5000"

def test_led_command(device_id, color):
    """Send LED test command using the settings API."""
    print(f"   {device_id} → {color}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/settings/test-led",
            json={
                'device': device_id,
                'color': color
            },
            timeout=5
        )

        if response.status_code == 200:
            print(f"      ✓ Command sent (status 200)")
            return True
        else:
            print(f"      ✗ Failed: HTTP {response.status_code}")
            print(f"         Response: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"      ✗ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("DIRECT LED TEST (via Settings API)")
    print("="*60 + "\n")

    devices = [
        '192.168.99.101',  # C1
        '192.168.99.102',  # C2
        '192.168.99.103',  # C3
        '192.168.99.104',  # C4
        '192.168.99.105',  # C5
    ]

    # PHASE 1: Test solid colors
    print("\n" + "="*60)
    print("PHASE 1: TESTING SOLID COLORS")
    print("="*60 + "\n")

    solid_colors = ['red', 'green', 'blue', 'yellow', 'orange']

    for color in solid_colors:
        print(f"\n🎨 Testing {color.upper()} on all cones...")

        for device_id in devices:
            test_led_command(device_id, color)

        print(f"   ⏱️  Waiting 3 seconds to observe...")
        time.sleep(3)

    print("\n✅ Solid color tests complete!")

    # PHASE 2: Test chase patterns
    print("\n" + "="*60)
    print("PHASE 2: TESTING CHASE ANIMATIONS")
    print("="*60 + "\n")

    chase_colors = ['chase_red', 'chase_green', 'chase_blue', 'chase_yellow', 'chase_amber']

    for color in chase_colors:
        print(f"\n🎨 Testing {color.upper()} on all cones...")

        for device_id in devices:
            test_led_command(device_id, color)

        print(f"   ⏱️  Waiting 4 seconds for chase animation...")
        time.sleep(4)

    print("\n✅ Chase animation tests complete!")

    # Return to standby
    print("\n🧹 Returning all devices to orange (solid_amber)...")
    for device_id in devices:
        test_led_command(device_id, 'orange')

    print("\n" + "="*60)
    print("TEST COMPLETE!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
