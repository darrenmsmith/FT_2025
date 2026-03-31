#!/usr/bin/env python3
"""
MH Flying Fish IR Proximity Sensor for Field Trainer
- Detects beam break (OUT goes LOW) on GPIO 17
- Used for sprint finish line auto-stop
- Supports test mode for Settings page calibration UI
- Graceful fallback if GPIO is unavailable (log warning, disable sensor)

Wiring (all devices identical):
    VCC → 5V       Pin 2
    GND → Ground   Pin 6
    OUT → GPIO 17  Pin 11
"""

import time
import logging

logger = logging.getLogger(__name__)

GPIO_PIN     = 17
DEBOUNCE_S   = 0.2   # Minimum seconds between triggers


class IrSensor:
    def __init__(self, gpio_pin=GPIO_PIN):
        self.gpio_pin       = gpio_pin
        self._sensor        = None
        self._callback      = None          # Called on beam break when armed
        self._armed         = False         # True only during an active sprint run
        self._last_trigger  = 0.0
        self._test_mode     = False
        self._test_callback = None          # Called on every beam break in test mode
        self._init_sensor()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_sensor(self):
        try:
            from gpiozero import DigitalInputDevice
            self._sensor = DigitalInputDevice(self.gpio_pin, pull_up=True)
            self._sensor.when_activated = self._on_beam_break  # fires when pin goes LOW = beam broken (NO output)
            logger.info(f"IR sensor initialised on GPIO {self.gpio_pin}")
        except Exception as e:
            logger.warning(f"IR sensor not available on GPIO {self.gpio_pin}: {e}")
            self._sensor = None

    # ------------------------------------------------------------------
    # Internal beam-break handler (runs in gpiozero callback thread)
    # ------------------------------------------------------------------

    def _on_beam_break(self):
        now = time.time()
        if now - self._last_trigger < DEBOUNCE_S:
            return
        self._last_trigger = now

        if self._test_mode:
            if self._test_callback:
                self._test_callback({'event': 'beam_break', 'timestamp': now})
            return

        if self._armed and self._callback:
            self._callback(now)

    # ------------------------------------------------------------------
    # Public API — course lifecycle
    # ------------------------------------------------------------------

    def arm(self):
        """Enable detection — call when a sprint run goes live (beep fires)."""
        self._armed = True
        logger.info(f"IR sensor armed (GPIO {self.gpio_pin})")

    def disarm(self):
        """Disable detection — call when run ends or course deactivates."""
        self._armed = False
        logger.info(f"IR sensor disarmed (GPIO {self.gpio_pin})")

    def set_detection_callback(self, fn):
        """Register function called when beam breaks during an armed run."""
        self._callback = fn

    # ------------------------------------------------------------------
    # Public API — test mode (Settings page calibration)
    # ------------------------------------------------------------------

    def start_test_mode(self, emit_fn):
        """Emit beam-break events for real-time feedback in Settings UI."""
        self._test_mode     = True
        self._test_callback = emit_fn
        logger.info("IR sensor test mode started")

    def stop_test_mode(self):
        self._test_mode     = False
        self._test_callback = None
        logger.info("IR sensor test mode stopped")

    # ------------------------------------------------------------------
    # Public API — status
    # ------------------------------------------------------------------

    def get_current_value(self):
        """Return 1 = beam broken (pin LOW/active), 0 = beam clear (pin HIGH)."""
        if self._sensor:
            return self._sensor.value
        return None

    @property
    def available(self):
        return self._sensor is not None

    @property
    def armed(self):
        return self._armed

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        if self._sensor:
            self._sensor.close()
            self._sensor = None
