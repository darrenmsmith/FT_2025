#!/usr/bin/env python3
"""
Test script to verify chase animations work on client cones.
Cycles through chase patterns on each connected device.
"""

import requests
import time

BASE_URL = "http://localhost:5000"

def get_connected_devices():
    """Get list of connected devices - hardcoded for C1-C5."""
    # Known device IPs for C1-C5
    return [
        {'node_id': '192.168.99.101', 'status': 'Active'},  # C1
        {'node_id': '192.168.99.102', 'status': 'Active'},  # C2
        {'node_id': '192.168.99.103', 'status': 'Active'},  # C3
        {'node_id': '192.168.99.104', 'status': 'Active'},  # C4
        {'node_id': '192.168.99.105', 'status': 'Active'},  # C5
    ]

def test_chase_pattern(device_id, pattern_name):
    """Send a chase pattern to a specific device using test-led API."""
    print(f"   {device_id} → {pattern_name}")

    try:
        # Use the test-led API endpoint
        # The API accepts chase_* pattern names directly as the color parameter
        response = requests.post(
            f"{BASE_URL}/api/settings/test-led",
            json={
                'device': device_id,
                'color': pattern_name  # Pass pattern name directly (e.g., 'chase_red')
            },
            timeout=5
        )

        if response.status_code == 200:
            print(f"      ✓ Command sent")
            return True
        else:
            print(f"      ✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"      ✗ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("CHASE ANIMATION TEST")
    print("="*60 + "\n")

    # Get connected devices
    print("🔍 Getting connected devices...")
    devices = get_connected_devices()

    if not devices:
        print("❌ No devices connected!")
        return

    print(f"✓ Found {len(devices)} connected device(s):\n")
    for dev in devices:
        print(f"   • {dev['node_id']} - Status: {dev['status']}")

    print("\n" + "-"*60)

    # PHASE 1: Test solid colors to verify commands work at all
    print("\n" + "="*60)
    print("PHASE 1: TESTING SOLID COLORS (verify LED commands work)")
    print("="*60 + "\n")

    solid_patterns = [
        'solid_red',
        'solid_green',
        'solid_blue',
        'solid_yellow',
        'solid_amber',
    ]

    for pattern in solid_patterns:
        print(f"\n🎨 Testing {pattern} on all cones...")

        for dev in devices:
            test_chase_pattern(dev['node_id'], pattern)

        print(f"   ⏱️  Waiting 3 seconds to observe...")
        time.sleep(3)

    print("\n✅ Solid color tests complete!")
    print("   Did all cones show the correct solid colors?")

    # PHASE 2: Test chase patterns
    print("\n" + "="*60)
    print("PHASE 2: TESTING CHASE ANIMATIONS")
    print("="*60 + "\n")

    chase_patterns = [
        'chase_red',
        'chase_green',
        'chase_blue',
        'chase_yellow',
        'chase_amber',
        'chase'  # Default chase (white)
    ]

    for pattern in chase_patterns:
        print(f"\n🎨 Testing {pattern} on all cones...")

        for dev in devices:
            test_chase_pattern(dev['node_id'], pattern)

        print(f"   ⏱️  Waiting 4 seconds for chase animation...")
        time.sleep(4)  # Chase animations are 3s, give a buffer

    # Return to solid colors
    print("\n🧹 Returning all devices to solid_amber (standby)...")
    for dev in devices:
        test_chase_pattern(dev['node_id'], 'solid_amber')

    print("\n" + "="*60)
    print("✅ LED PATTERN TEST COMPLETE!")
    print("="*60 + "\n")

    print("Expected behavior:")
    print("PHASE 1 (Solid Colors):")
    print("- All cones should have shown solid red, green, blue, yellow, amber")
    print()
    print("PHASE 2 (Chase Animations):")
    print("- All cones should have shown 6 different chase animations")
    print("- Chases should auto-terminate after 3 seconds")
    print()
    print("Final state:")
    print("- All cones should now be back to solid amber (standby)")
    print()

if __name__ == "__main__":
    main()
