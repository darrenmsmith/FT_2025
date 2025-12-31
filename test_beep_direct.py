#!/usr/bin/env python3
"""
Direct beep test using Device 0 speaker
"""
import time
import sys
sys.path.insert(0, '/opt')

from field_trainer.ft_registry import REGISTRY

print("=" * 60)
print("DIRECT BEEP TEST - Device 0")
print("=" * 60)
print("\nPattern: 1 beep -> 8s wait -> 2 beeps")
print("\nStarting in 2 seconds...")
time.sleep(2)

# Check if audio is available
if not REGISTRY._audio:
    print("\n❌ ERROR: Audio system not available")
    print("This script must run while field-trainer-server is running")
    sys.exit(1)

# Test cycle
print("\n1. ▶ Playing single beep (GO!)")
REGISTRY._audio.play('default_beep')
print("   ✓ Beep 1 sent")

print("\n2. ⏱ Waiting 8 seconds (athlete runs)...")
time.sleep(8.0)

print("\n3. ▶ Playing double beep (You made it!)")
REGISTRY._audio.play('default_beep')
print("   ✓ Beep 1 sent")
time.sleep(0.3)
REGISTRY._audio.play('default_beep')
print("   ✓ Beep 2 sent")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
