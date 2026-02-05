#!/usr/bin/env python3
"""
Simplified LED test script for chase and rainbow patterns.
Tests one solid color, two chase patterns, and rainbow.
"""

import requests
import time

BASE_URL = "http://localhost:5001"
LOG_FILE = "/tmp/led_test.log"

def log(message):
    """Log to both console and file."""
    print(message)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

def test_led_pattern(device_id, pattern_name):
    """Send LED pattern to a specific device."""
    log(f"   {device_id} -> {pattern_name}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/settings/test-led",
            json={
                "device": device_id,
                "color": pattern_name
            },
            timeout=5
        )

        if response.status_code == 200:
            log("      Success")
            return True
        else:
            log(f"      Failed: {response.status_code}")
            log(f"      Response: {response.text}")
            return False
    except Exception as e:
        log(f"      Error: {e}")
        return False

def main():
    # Clear log file
    with open(LOG_FILE, "w") as f:
        f.write("")

    log("")
    log("="*60)
    log("SIMPLIFIED LED TEST")
    log("="*60)
    log(f"Log file: {LOG_FILE}")
    log("")

    # Test only C1 for easier observation
    test_device = {"node_id": "192.168.99.101", "name": "C1"}

    # Test patterns - 10 second observation times
    # Rainbow disabled - it hangs the test, needs more investigation
    tests = [
        {"pattern": "solid_red", "wait": 5, "description": "Test solid color (baseline)"},
        {"pattern": "chase_red", "wait": 10, "description": "Test red chase - watch for moving LEDs"},
        {"pattern": "chase_blue", "wait": 10, "description": "Test blue chase - watch for moving LEDs"},
        {"pattern": "chase_green", "wait": 10, "description": "Test green chase - watch for moving LEDs"},
        {"pattern": "chase_yellow", "wait": 10, "description": "Test yellow chase - watch for moving LEDs"},
    ]

    for test in tests:
        log("")
        log("="*60)
        log("TEST: " + test["description"])
        log("Pattern: " + test["pattern"])
        log("Device: C1 only (easier to observe)")
        log("="*60)

        test_led_pattern(test_device["node_id"], test["pattern"])

        log("")
        log("WATCH C1 CAREFULLY for " + str(test["wait"]) + " seconds...")
        if "chase" in test["pattern"]:
            log("  >>> Look for: 3 LEDs lighting up and moving around the ring")
        elif "rainbow" in test["pattern"]:
            log("  >>> Look for: Colors changing through the rainbow spectrum")
        log("")

        time.sleep(test["wait"])

    # Return to standby
    log("")
    log("="*60)
    log("CLEANUP: Returning C1 to standby (solid_amber)")
    log("="*60)

    test_led_pattern(test_device["node_id"], "solid_amber")

    log("")
    log("="*60)
    log("LED TEST COMPLETE!")
    log("="*60)
    log("")

    log("")
    log("What you should have seen on C1:")
    log("- Solid red: Steady red light (baseline - proves LED commands work)")
    log("- Chase red: 3 red LEDs moving in a circle around the ring")
    log("- Chase blue: 3 blue LEDs moving in a circle around the ring")
    log("- Rainbow: LEDs cycling through rainbow colors")
    log("")
    log("If chase/rainbow did NOT show:")
    log("  - Client firmware may not support these patterns")
    log("  - Or duration/delay parameters may be incorrect")
    log("")
    log("Log saved to: " + LOG_FILE)
    log("")

if __name__ == "__main__":
    main()
