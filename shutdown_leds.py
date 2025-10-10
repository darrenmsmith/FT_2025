#!/usr/bin/env python3
"""Turn off LEDs on shutdown"""
try:
    from rpi_ws281x import PixelStrip, Color
    strip = PixelStrip(15, 12, 800000, 10, False, 128, 0)
    strip.begin()
    for i in range(15):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
    print("LEDs turned off")
except Exception as e:
    print(f"LED shutdown error: {e}")
