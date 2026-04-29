#!/usr/bin/env python3
"""
IR Proximity / Break-Beam Sensor for Field Trainer
Supports two sensor types — behaviour is identical (active-LOW, pull_up=True):

  MH Flying Fish (reflective proximity, single cone)
      VCC → 5V  Pin 2 | GND → Pin 6 | OUT → GPIO 17  Pin 11

  Adafruit 5 mm Break-Beam (two-cone pair)
    Emitter cone  — power only (no GPIO)
    Receiver cone — White signal wire → GPIO 17  Pin 11

Config is loaded from /opt/field_trainer/config/ir_config_device{N}.json
(N = last octet of the device IP, e.g. 105 for 192.168.99.105).
If the file is missing, defaults to mh_flying_fish / receiver / enabled.
"""

import json
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GPIO_PIN    = 17
DEBOUNCE_S  = 0.2   # Minimum seconds between triggers

CONFIG_DIR  = '/opt/field_trainer/config'

# Sensor type constants
TYPE_MH_FLYING_FISH    = 'mh_flying_fish'
TYPE_ADAFRUIT_BREAKBEAM = 'adafruit_breakbeam'

ROLE_RECEIVER = 'receiver'
ROLE_EMITTER  = 'emitter'


def _load_ir_config(ip_suffix: str) -> dict:
    """Load per-device IR config from JSON. Returns defaults if file missing."""
    path = os.path.join(CONFIG_DIR, f'ir_config_device{ip_suffix}.json')
    defaults = {
        'sensor_type': TYPE_MH_FLYING_FISH,
        'role': ROLE_RECEIVER,
        'gpio_pin': GPIO_PIN,
        'enabled': True,
        'debounce_ms': int(DEBOUNCE_S * 1000),
    }
    try:
        with open(path) as f:
            return {**defaults, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return defaults


class IrSensor:
    def __init__(self, gpio_pin=GPIO_PIN, sensor_type=TYPE_MH_FLYING_FISH,
                 role=ROLE_RECEIVER, debounce_s=DEBOUNCE_S):
        self.gpio_pin       = gpio_pin
        self.sensor_type    = sensor_type   # 'mh_flying_fish' | 'adafruit_breakbeam'
        self.role           = role          # 'receiver' | 'emitter'
        self._debounce_s    = debounce_s
        self._sensor        = None
        self._callback      = None
        self._armed         = False
        self._last_trigger  = 0.0
        self._test_mode     = False
        self._test_callback = None
        self._beam_broken   = False  # event-driven beam state for health monitoring
        self._init_sensor()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_sensor(self):
        if self._sensor:
            try:
                self._sensor.close()
            except Exception:
                pass
            self._sensor = None

        if self.role == ROLE_EMITTER:
            logger.info(f"IR sensor role=emitter on this cone — no GPIO sensing needed")
            return

        try:
            from gpiozero import DigitalInputDevice
            self._sensor = DigitalInputDevice(self.gpio_pin, pull_up=True)
            if self.sensor_type == TYPE_ADAFRUIT_BREAKBEAM:
                # Adafruit break-beam: beam intact = pin LOW, beam broken = pin HIGH
                # pin HIGH = gpiozero "deactivated" (inactive with pull_up=True)
                self._sensor.when_deactivated = self._on_beam_break
                # Initialise beam state from current pin reading
                self._beam_broken = not self._sensor.is_active
            else:
                # MH Flying Fish: object detected = pin LOW = gpiozero "activated"
                self._sensor.when_activated = self._on_beam_break
            logger.info(f"IR sensor ({self.sensor_type}) initialised on GPIO {self.gpio_pin}")
        except Exception as e:
            logger.warning(f"IR sensor not available on GPIO {self.gpio_pin}: {e}")
            self._sensor = None

    # ------------------------------------------------------------------
    # Internal beam-break handler (runs in gpiozero callback thread)
    # ------------------------------------------------------------------

    def _on_beam_break(self):
        self._beam_broken = True  # set immediately; cleared by polling in is_beam_intact()
        now = time.time()
        if now - self._last_trigger < self._debounce_s:
            return
        self._last_trigger = now

        if self._test_mode:
            if self._test_callback:
                self._test_callback({
                    'event': 'beam_break',
                    'sensor_type': self.sensor_type,
                    'timestamp': now,
                })
            return

        if self._armed and self._callback:
            self._callback(now)

    # ------------------------------------------------------------------
    # Public API — course lifecycle
    # ------------------------------------------------------------------

    def reset_beam_state(self):
        """Reset beam health tracking — call before a new run or after test mode."""
        self._beam_broken = False

    def arm(self):
        """Enable detection — call when a sprint run goes live (beep fires)."""
        if self.role == ROLE_EMITTER:
            return
        self._armed = True
        logger.info(f"IR sensor armed (GPIO {self.gpio_pin}, type={self.sensor_type})")

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
        if self.role == ROLE_EMITTER:
            logger.info("IR test mode requested on emitter cone — ignored")
            return
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

    def is_beam_intact(self) -> Optional[bool]:
        """True if beam is intact, False if broken, None if unavailable.
        Simple direct GPIO poll — caller uses consecutive-miss counting to
        filter transient noise. Only meaningful for adafruit_breakbeam receiver.
        """
        if self._sensor is None or self.role == ROLE_EMITTER:
            return None
        if self.sensor_type == TYPE_ADAFRUIT_BREAKBEAM:
            return bool(self._sensor.is_active)  # pull_up=True: active=LOW=beam intact
        return None

    def get_current_value(self):
        """Return 1 = triggered (beam broken / object detected), 0 = clear. None if unavailable.

        gpiozero with pull_up=True: value=1 when pin LOW (active), value=0 when pin HIGH.

        MH Flying Fish:      pin LOW = object detected  → value=1 → return 1  (no inversion)
        Adafruit break-beam: pin LOW = beam INTACT       → value=1 → return 0  (invert)
                             pin HIGH = beam BROKEN      → value=0 → return 1  (invert)
        """
        if self._sensor is None:
            return None
        raw = self._sensor.value
        if self.sensor_type == TYPE_ADAFRUIT_BREAKBEAM:
            return 0 if raw else 1
        return raw

    def get_config(self) -> dict:
        """Return sensor configuration for heartbeat / API responses."""
        return {
            'sensor_type': self.sensor_type,
            'role': self.role,
            'gpio_pin': self.gpio_pin,
        }

    @property
    def available(self):
        """True if GPIO is initialised (always False for emitter role)."""
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
