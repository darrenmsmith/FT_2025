#!/usr/bin/env python3
"""
JSN-SR04T Sonar Distance Sensor for Field Trainer
- Direct lgpio edge-callback timing (accurate on Pi 5 and Pi 3 A+)
- Delta-based proximity detection with configurable threshold
- GPIO allocated only when monitoring is active (battery conservation)
- Parallel module to mpu65xx_touch_sensor.py

Wiring (as installed on Device 0):
    Trig → GPIO 23, Physical Pin 16 (direct 3.3V)
    Echo → GPIO 24, Physical Pin 18 (via 1kΩ+2kΩ voltage divider, 5V→3.3V)
"""

import time
import threading
import collections
from typing import Optional, Callable

# GPIO pin assignments — as physically wired
TRIGGER_PIN = 23  # GPIO 23, Physical Pin 16
ECHO_PIN    = 24  # GPIO 24, Physical Pin 18

# lgpio chip — Pi 5 uses gpiochip4 (symlink to gpiochip0); Pi 3 uses gpiochip0
GPIO_CHIP = 4

# Sensor hardware limits
SENSOR_MIN_CM = 25.0
SENSOR_MAX_CM = 600.0

# Timing
TRIGGER_PULSE_S  = 0.000015   # 15 µs trigger pulse (> 10 µs minimum)
ECHO_TIMEOUT_S   = 0.040      # 40 ms = max round-trip for 600 cm
READ_INTERVAL_S  = 0.5        # Default: readings every 500 ms (configurable 100ms–2000ms)

# Detection defaults
DEFAULT_THRESHOLD_CM = 30.0   # Trigger if object closer than background by this amount
BASELINE_SAMPLES     = 10     # Rolling window for background average
DETECTION_DEBOUNCE        = 1.0  # Min seconds between detections
BASELINE_FREEZE_TIME      = 2.0  # Seconds to hold baseline after detection
MIN_BASELINE_SAMPLES      = 3    # Readings needed before detection enabled
DEFAULT_CONFIRM_READINGS  = 2    # Consecutive below-threshold readings required to fire

# lgpio nanosecond conversion (callback ticks are ns since epoch on Pi 5)
NS_PER_CM = 58000.0           # 58 µs = 58000 ns per centimetre (one-way ×2 / speed)


class SonarSensor:
    """
    JSN-SR04T ultrasonic distance sensor with proximity detection.

    Usage:
        sensor = SonarSensor()
        sensor.set_detection_callback(my_callback)
        sensor.start_monitoring()   # allocates GPIO
        ...
        sensor.stop_monitoring()    # releases GPIO
    """

    def __init__(self, device_id: str = 'local'):
        self.device_id = device_id
        self.threshold_cm       = DEFAULT_THRESHOLD_CM
        self.read_interval_s    = READ_INTERVAL_S
        self.confirm_readings   = DEFAULT_CONFIRM_READINGS
        self.detection_callback: Optional[Callable] = None

        # Consecutive below-threshold counter (resets when reading goes back above)
        self._below_count: int = 0

        # Runtime state
        self.running        = False
        self._thread: Optional[threading.Thread] = None
        self._lgpio_handle  = None
        self._lgpio_cb      = None
        self.hardware_available = False

        # Edge timing for echo measurement
        self._edge_lock  = threading.Lock()
        self._edge_times: list = []   # [(level, tick_ns), ...]

        # Live readings
        self.current_distance_cm: Optional[float] = None
        self._baseline_window: collections.deque = collections.deque(maxlen=BASELINE_SAMPLES)
        self.baseline_cm: Optional[float]  = None
        self._baseline_freeze_until: float = 0.0

        # Event tracking
        self.last_detection_time: float = 0.0
        self.detection_count: int  = 0
        self.reading_count:   int  = 0
        self.out_of_range_count: int = 0
        # Snapshot of distance/baseline at the exact moment of last detection
        self.last_detection_distance_cm: Optional[float] = None
        self.last_detection_baseline_cm: Optional[float] = None

        # Detect whether lgpio is available
        self._lgpio_available = self._check_lgpio()

    # ------------------------------------------------------------------
    # Hardware init / release
    # ------------------------------------------------------------------

    def _check_lgpio(self) -> bool:
        try:
            import lgpio  # noqa: F401
            return True
        except ImportError:
            print(f"SonarSensor [{self.device_id}]: lgpio not available")
            return False

    def _allocate_gpio(self) -> bool:
        """Open lgpio chip and claim pins. Called only when starting monitoring."""
        if not self._lgpio_available:
            return False
        try:
            import lgpio
            self._lgpio_handle = lgpio.gpiochip_open(GPIO_CHIP)
            lgpio.gpio_claim_output(self._lgpio_handle, TRIGGER_PIN, 0)
            lgpio.gpio_claim_alert(self._lgpio_handle, ECHO_PIN,
                                   lgpio.BOTH_EDGES, lgpio.SET_PULL_NONE)
            self._lgpio_cb = lgpio.callback(
                self._lgpio_handle, ECHO_PIN,
                lgpio.BOTH_EDGES, self._edge_callback
            )
            self.hardware_available = True
            print(f"SonarSensor [{self.device_id}]: GPIO allocated "
                  f"(Trig=GPIO{TRIGGER_PIN}, Echo=GPIO{ECHO_PIN}, chip={GPIO_CHIP})")
            return True
        except Exception as e:
            print(f"SonarSensor [{self.device_id}]: GPIO allocation failed: {e}")
            self.hardware_available = False
            return False

    def _release_gpio(self):
        """Cancel callback and close lgpio handle."""
        if self._lgpio_cb is not None:
            try:
                self._lgpio_cb.cancel()
            except Exception:
                pass
            self._lgpio_cb = None
        if self._lgpio_handle is not None:
            try:
                import lgpio
                lgpio.gpiochip_close(self._lgpio_handle)
            except Exception:
                pass
            self._lgpio_handle = None
        self.hardware_available = False

    # ------------------------------------------------------------------
    # Edge callback and distance measurement
    # ------------------------------------------------------------------

    def _edge_callback(self, chip, gpio, level, tick_ns):
        """Called by lgpio on every echo edge. tick_ns = nanoseconds since epoch."""
        with self._edge_lock:
            self._edge_times.append((level, tick_ns))

    def _read_distance_cm(self) -> Optional[float]:
        """
        Send one trigger pulse and measure the echo pulse width.
        Returns distance in cm, or None on timeout / out-of-range.
        """
        if self._lgpio_handle is None:
            return None
        try:
            import lgpio

            # Clear any stale edges
            with self._edge_lock:
                self._edge_times.clear()

            # Send trigger pulse
            lgpio.gpio_write(self._lgpio_handle, TRIGGER_PIN, 0)
            time.sleep(0.000002)
            lgpio.gpio_write(self._lgpio_handle, TRIGGER_PIN, 1)
            time.sleep(TRIGGER_PULSE_S)
            lgpio.gpio_write(self._lgpio_handle, TRIGGER_PIN, 0)

            # Wait for echo to complete
            time.sleep(ECHO_TIMEOUT_S)

            with self._edge_lock:
                edges = list(self._edge_times)

            rises = [t for lvl, t in edges if lvl == 1]
            falls = [t for lvl, t in edges if lvl == 0]

            if not rises or not falls:
                return None

            # Use the first rising edge and the first falling edge after it
            t_rise = rises[0]
            valid_falls = [t for t in falls if t > t_rise]
            if not valid_falls:
                return None

            pulse_ns = valid_falls[0] - t_rise
            dist_cm  = pulse_ns / NS_PER_CM
            return dist_cm if SENSOR_MIN_CM <= dist_cm <= SENSOR_MAX_CM else None

        except Exception:
            return None

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    def _monitoring_loop(self):
        """Background thread: read sensor, maintain baseline, check for detection."""
        while self.running:
            dist_cm = self._read_distance_cm()
            now = time.time()

            if dist_cm is not None:
                self.current_distance_cm = dist_cm
                self.reading_count += 1

                # Update rolling baseline — only accept readings that are
                # close to the current baseline (reject outliers that would
                # drag the baseline down and cause false detections).
                # On the first MIN_BASELINE_SAMPLES readings, accept everything
                # to establish a starting baseline.
                if now >= self._baseline_freeze_until:
                    baseline_established = len(self._baseline_window) >= MIN_BASELINE_SAMPLES
                    if not baseline_established:
                        # Bootstrap phase: accept all readings
                        self._baseline_window.append(dist_cm)
                    elif abs(dist_cm - self.baseline_cm) <= self.threshold_cm * 1.5:
                        # Only update baseline if reading is within 1.5× threshold
                        # of current background — outliers are ignored
                        self._baseline_window.append(dist_cm)

                    if len(self._baseline_window) > 0:
                        self.baseline_cm = (
                            sum(self._baseline_window) / len(self._baseline_window)
                        )

                # Detection: require N consecutive readings below threshold
                # to filter out single-shot reflections (sensor noise at range)
                baseline_ready = (
                    self.baseline_cm is not None and
                    len(self._baseline_window) >= MIN_BASELINE_SAMPLES
                )
                if baseline_ready and dist_cm < self.baseline_cm - self.threshold_cm:
                    self._below_count += 1
                else:
                    self._below_count = 0

                if (self._below_count >= self.confirm_readings and
                        now - self.last_detection_time >= DETECTION_DEBOUNCE):
                    self.last_detection_time = now
                    self._baseline_freeze_until = now + BASELINE_FREEZE_TIME
                    self._below_count = 0
                    self.detection_count += 1
                    self.last_detection_distance_cm = dist_cm
                    self.last_detection_baseline_cm = self.baseline_cm
                    if self.detection_callback:
                        try:
                            self.detection_callback()
                        except Exception as e:
                            print(f"SonarSensor [{self.device_id}]: callback error: {e}")
            else:
                # No valid reading — don't update baseline or distance display
                self.out_of_range_count += 1

            # ECHO_TIMEOUT_S (~40 ms) already consumed; sleep the remainder
            elapsed = ECHO_TIMEOUT_S + TRIGGER_PULSE_S
            remaining = self.read_interval_s - elapsed
            if remaining > 0:
                time.sleep(remaining)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_monitoring(self):
        """Start background monitoring. Allocates GPIO pins."""
        if self.running:
            return
        if not self._allocate_gpio():
            return

        # Reset state
        self.current_distance_cm   = None
        self._baseline_window.clear()
        self.baseline_cm           = None
        self._baseline_freeze_until = 0.0
        self.last_detection_time   = 0.0
        self.detection_count       = 0
        self.reading_count         = 0
        self.out_of_range_count    = 0
        self._below_count          = 0
        self.last_detection_distance_cm = None
        self.last_detection_baseline_cm = None

        self.running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        print(f"SonarSensor [{self.device_id}]: monitoring started")

    def stop_monitoring(self):
        """Stop monitoring and release GPIO pins."""
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._release_gpio()
        self.current_distance_cm = None
        self.baseline_cm = None
        self._baseline_window.clear()
        print(f"SonarSensor [{self.device_id}]: monitoring stopped, GPIO released")

    def set_detection_callback(self, callback: Callable):
        """Set function to call when proximity detection fires."""
        self.detection_callback = callback

    def set_threshold(self, threshold_cm: float):
        """Update detection threshold in centimetres."""
        self.threshold_cm = max(5.0, float(threshold_cm))

    def set_read_interval(self, interval_s: float):
        """Update how often the sensor fires. Min 0.05s (50ms), no practical max."""
        self.read_interval_s = max(0.05, float(interval_s))

    def set_confirm_readings(self, count: int):
        """Set how many consecutive below-threshold readings trigger detection (1–5)."""
        self.confirm_readings = max(1, min(5, int(count)))

    def get_status(self) -> dict:
        """Return current sensor state for API responses."""
        now = time.time()
        recent_detection = (
            self.last_detection_time > 0 and
            (now - self.last_detection_time) < 2.0
        )

        def cm_to_in(cm):
            return round(cm / 2.54, 1) if cm is not None else None

        return {
            'running':             self.running,
            'hardware_available':  self.hardware_available,
            'lgpio_available':     self._lgpio_available,
            'distance_cm':         round(self.current_distance_cm, 1) if self.current_distance_cm is not None else None,
            'distance_in':         cm_to_in(self.current_distance_cm),
            'baseline_cm':         round(self.baseline_cm, 1) if self.baseline_cm is not None else None,
            'baseline_in':         cm_to_in(self.baseline_cm),
            'baseline_samples':    len(self._baseline_window),
            'threshold_cm':        self.threshold_cm,
            'recent_detection':    recent_detection,
            'detection_count':     self.detection_count,
            'last_detection_distance_cm': round(self.last_detection_distance_cm, 1) if self.last_detection_distance_cm is not None else None,
            'last_detection_baseline_cm': round(self.last_detection_baseline_cm, 1) if self.last_detection_baseline_cm is not None else None,
            'reading_count':       self.reading_count,
            'read_interval_ms':    int(self.read_interval_s * 1000),
            'confirm_readings':    self.confirm_readings,
            'below_count':         self._below_count,
            'trigger_pin':         TRIGGER_PIN,
            'echo_pin':            ECHO_PIN,
        }
