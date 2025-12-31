#!/usr/bin/env python3
"""
Simple beep pattern test
Tests: 1 beep -> 8s wait -> 2 beeps
"""
import time
import sys
sys.path.insert(0, '/opt')

from field_trainer.ft_registry import REGISTRY

def play_beep(count=1):
    """Play beep on Device 0"""
    for i in range(count):
        if i > 0:
            time.sleep(0.3)  # Gap between beeps

        if REGISTRY._audio:
            REGISTRY._audio.play('default_beep')
            print(f"   Beep {i+1}/{count}")
        time.sleep(0.1)  # Small delay to ensure beep plays

print("=" * 60)
print("BEEP PATTERN TEST")
print("=" * 60)
print("\nPattern: 1 beep -> 8s wait -> 2 beeps")
print("\nStarting in 2 seconds...")
time.sleep(2)

# Test cycle
print("\n1. Single beep (GO!)")
play_beep(1)

print("\n2. Waiting 8 seconds (athlete runs)...")
time.sleep(8.0)

print("\n3. Double beep (You made it!)")
play_beep(2)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nDid you hear:")
print("  - 1 beep")
print("  - 8 second pause")
print("  - 2 beeps")
print()
