#!/usr/bin/env python3
"""
Local touch sensor calibration - runs on the device itself
Measures baseline and detects taps to calculate optimal threshold
"""

import sys
import time
sys.path.insert(0, '/opt')

from field_trainer.ft_touch import TouchSensor

def run_calibration(node_id: str, tap_count: int = 5):
    """Run calibration locally on this device"""

    print(f"🎯 Starting calibration for {node_id}")
    print()

    # Initialize sensor
    sensor = TouchSensor(node_id)

    if not sensor.hardware_available:
        print("❌ FAILED: Hardware not available")
        return False

    # Step 1: Measure baseline
    print("📊 Step 1: Measuring baseline (keep device still for 3 seconds)...")
    baseline_samples = []

    for i in range(30):  # 3 seconds at 10Hz
        reading = sensor._get_sensor_reading()
        if reading:
            magnitude = sensor._calculate_magnitude(reading)
            baseline_samples.append(magnitude)
        time.sleep(0.1)

    if not baseline_samples:
        print("❌ FAILED: Could not measure baseline")
        return False

    baseline = sum(baseline_samples) / len(baseline_samples)
    print(f"✓ Baseline: {baseline:.3f}g")
    print()

    # Step 2: Collect tap samples
    # Use 0.05g above baseline for detection (very sensitive to catch soft taps)
    tap_threshold = baseline + 0.05
    print(f"📊 Step 2: Tap the device {tap_count} times")
    print()

    tap_magnitudes = []

    for tap_num in range(1, tap_count + 1):
        print(f"👆 Waiting for tap {tap_num}/{tap_count}... ", end='', flush=True)

        tap_detected = False
        retry_count = 0
        max_retries = 2
        current_tap_threshold = tap_threshold

        while not tap_detected and retry_count <= max_retries:
            max_magnitude = 0.0
            start_time = time.time()
            timeout = 6  # 6 seconds per tap (30 seconds total for 5 taps)
            last_shown_magnitude = 0.0

            while not tap_detected and (time.time() - start_time) < timeout:
                reading = sensor._get_sensor_reading()
                if reading:
                    magnitude = sensor._calculate_magnitude(reading)

                    if magnitude > max_magnitude:
                        max_magnitude = magnitude

                    # Show every touch detected (even if below threshold)
                    touch_detection_level = baseline + 0.02  # Very low threshold just for feedback
                    if magnitude > touch_detection_level and magnitude > last_shown_magnitude + 0.05:
                        # Show touch feedback
                        if magnitude < current_tap_threshold:
                            print(f"⚪ {magnitude:.3f}g ", end='', flush=True)
                        last_shown_magnitude = magnitude

                    # Accept tap if above current threshold
                    if magnitude > current_tap_threshold:
                        tap_magnitudes.append(magnitude)
                        tap_detected = True
                        print(f"✓ Detected! Magnitude: {magnitude:.3f}g")
                        break

                time.sleep(0.05)  # 20Hz

            # Auto-adjust threshold if needed (silently)
            if not tap_detected:
                if max_magnitude > baseline + 0.02:  # User was tapping, but threshold too high
                    retry_count += 1
                    if retry_count <= max_retries:
                        # Lower threshold by 0.02g each retry
                        current_tap_threshold = max(baseline + 0.02, current_tap_threshold - 0.02)
                        # Continue retry loop silently
                    else:
                        print(f"❌ Timeout")
                        print()
                        print("❌ FAILED: Not all taps detected")
                        return False
                else:
                    print(f"❌ Timeout")
                    print()
                    print("❌ FAILED: Not all taps detected")
                    return False

        # Brief pause between taps
        time.sleep(0.5)

    print()

    # Step 3: Calculate recommended threshold
    if not tap_magnitudes:
        print("❌ FAILED: No taps detected")
        return False

    avg_tap = sum(tap_magnitudes) / len(tap_magnitudes)
    min_tap = min(tap_magnitudes)
    max_tap = max(tap_magnitudes)

    # Threshold: halfway between baseline and minimum tap, with 20% safety margin
    recommended_threshold = baseline + ((min_tap - baseline) * 0.6)

    print()
    print(f"📊 Baseline: {baseline:.3f}g  |  Tap range: {min_tap:.3f}g - {max_tap:.3f}g  |  Threshold: {recommended_threshold:.3f}g")
    print()

    # Step 4: Save threshold
    sensor.update_threshold(recommended_threshold)

    print("✅ PASSED - Calibration complete!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: calibrate_touch.py <node_id> [tap_count]")
        print("Example: calibrate_touch.py 192.168.99.103 5")
        sys.exit(1)

    node_id = sys.argv[1]
    tap_count = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    success = run_calibration(node_id, tap_count)
    sys.exit(0 if success else 1)
