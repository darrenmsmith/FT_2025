"""
Server-side LED control (Device 0 hardware).
- Optional (no-op if rpi_ws281x isn't present on this host)
- Single worker thread polls the current LEDState and renders frames
"""

import threading
import time
from enum import Enum
from typing import Optional

try:
    from rpi_ws281x import PixelStrip, Color  # type: ignore
    _HAVE_WS281X = True
except Exception:
    _HAVE_WS281X = False


class LEDState(str, Enum):
    OFF = "off"
    SOLID_GREEN = "solid_green"
    SOLID_RED = "solid_red"
    BLINK_AMBER = "blink_amber"
    BLINK_ORANGE = "blink_orange"
    BLINK_BLUE = "blink_blue"
    BLINK_GREEN = "blink_green"
    RAINBOW = "rainbow"


class LEDManager:
    def __init__(self, pin: int = 18, led_count: int = 8, brightness: int = 32):
        self._state: LEDState = LEDState.OFF
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._have_hw = _HAVE_WS281X
        if self._have_hw:
            self._strip = PixelStrip(led_count, pin, brightness=brightness, channel=0)
            self._strip.begin()
        else:
            self._strip = None  # type: ignore

        self._start_thread()

    # ---------- public ----------
    def set_state(self, state: LEDState) -> None:
        with self._lock:
            self._state = state

    def get_state(self) -> LEDState:
        with self._lock:
            return self._state

    def shutdown(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self._have_hw and self._strip:
            self._fill(0, 0, 0)  # off

    # ---------- worker ----------
    def _start_thread(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            state = self.get_state()
            if state == LEDState.OFF:
                self._fill(0, 0, 0)
                time.sleep(0.2)
            elif state == LEDState.SOLID_GREEN:
                self._fill(0, 128, 0)
                time.sleep(0.2)
            elif state == LEDState.SOLID_RED:
                self._fill(128, 0, 0)
                time.sleep(0.2)
            elif state == LEDState.BLINK_AMBER:
                self._fill(180, 120, 0); time.sleep(0.3)
                self._fill(0, 0, 0);     time.sleep(0.3)
            elif state == LEDState.BLINK_ORANGE:
                self._fill(255, 165, 0); time.sleep(0.3)
                self._fill(0, 0, 0);     time.sleep(0.3)
            elif state == LEDState.BLINK_BLUE:
                self._fill(0, 0, 255);   time.sleep(0.3)
                self._fill(0, 0, 0);     time.sleep(0.3)
            elif state == LEDState.BLINK_GREEN:
                self._fill(0, 255, 0);   time.sleep(0.3)
                self._fill(0, 0, 0);     time.sleep(0.3)
            elif state == LEDState.RAINBOW:
                self._rainbow_cycle(5)
            else:
                time.sleep(0.2)

    # ---------- helpers ----------
    def _fill(self, r: int, g: int, b: int) -> None:
        if not (self._have_hw and self._strip):
            return
        color = Color(r, g, b)
        for i in range(self._strip.numPixels()):
            self._strip.setPixelColor(i, color)
        self._strip.show()

    def _rainbow_cycle(self, steps: int = 5) -> None:
        if not (self._have_hw and self._strip):
            time.sleep(0.2)
            return
        n = self._strip.numPixels()
        for j in range(256):
            if self._stop.is_set() or self.get_state() != LEDState.RAINBOW:
                break
            for i in range(n):
                self._strip.setPixelColor(i, self._wheel((int(i * 256 / n) + j) & 255))
            self._strip.show()
            time.sleep(0.005 * steps)

    @staticmethod
    def _wheel(pos: int):
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        if pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)
