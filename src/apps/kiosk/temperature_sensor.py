"""Background serial reader for stove / oven temperature (Arduino Nano, socat simulator, etc.).

Alert thresholds and snooze live here (kiosk-side), not in shared.config.
When readings stay above threshold for STOVE_ALERT_DURATION_SEC, the kiosk posts the same
/api/emergency/alert activated=true flow the webapp uses so family sees the emergency screen.
"""

import logging
import os
import re
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Serial device (set STOVE_SERIAL_PORT e.g. to /tmp/ttyFAKE0 for a simulator).
STOVE_SERIAL_PORT = os.environ.get("STOVE_SERIAL_PORT", "/dev/ttyUSB0")
STOVE_SERIAL_BAUD = int(os.environ.get("STOVE_SERIAL_BAUD", "9600"))

# Tuning for testing with °C sim lines like "Temp: 31.6 °C"
STOVE_ALERT_THRESHOLD_C = 30.0
STOVE_ALERT_DURATION_SEC = 20.0
STOVE_SNOOZE_MINUTES = 30
STOVE_DISPLAY_CELSIUS = True
STOVE_INPUT_DEFAULT_CELSIUS = True

_NUM = re.compile(r"(-?\d+(?:\.\d+)?)\s*°?\s*([FC])?\b", re.IGNORECASE)


def _both_from_value(val: float, unit_c: bool) -> Tuple[float, float]:
    """Return (temp_c, temp_f)."""
    if unit_c:
        return val, val * 9.0 / 5.0 + 32.0
    return (val - 32.0) * 5.0 / 9.0, val


class TemperatureSensor:
    """Daemon thread reads serial lines; latest temperature and stove-emergency gating."""

    def __init__(self, port: Optional[str] = None, baudrate: int = STOVE_SERIAL_BAUD):
        self._port = port if port is not None else STOVE_SERIAL_PORT
        self._baud = baudrate
        self._lock = threading.Lock()
        self._latest_c: Optional[float] = None
        self._latest_f: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self._above_since: Optional[float] = None
        self._ignore_until: float = 0.0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _parse_line(self, line: str) -> Optional[Tuple[float, float]]:
        line = line.strip()
        if not line:
            return None
        m = _NUM.search(line)
        if m:
            val = float(m.group(1))
            suf = (m.group(2) or "").upper()
            if suf == "C":
                return _both_from_value(val, True)
            if suf == "F":
                return _both_from_value(val, False)
            return _both_from_value(val, STOVE_INPUT_DEFAULT_CELSIUS)
        try:
            val = float(line.split(",")[0].strip())
        except (ValueError, IndexError):
            return None
        return _both_from_value(val, STOVE_INPUT_DEFAULT_CELSIUS)

    def _note_reading(self, temp_c: float, temp_f: float) -> None:
        now = time.time()
        with self._lock:
            self._latest_c = temp_c
            self._latest_f = temp_f
            if now < self._ignore_until:
                return
            if temp_c < STOVE_ALERT_THRESHOLD_C:
                self._above_since = None
                return
            if self._above_since is None:
                self._above_since = now

    def snooze(self) -> None:
        """Snooze alerts and clear sustained-over-threshold timer."""
        with self._lock:
            self._ignore_until = time.time() + float(STOVE_SNOOZE_MINUTES * 60)
            self._above_since = None

    def should_activate_stove_emergency(self) -> bool:
        """True when reading has stayed ≥ threshold long enough (and not snoozed)."""
        now = time.time()
        with self._lock:
            if now < self._ignore_until:
                return False
            if self._above_since is None:
                return False
            if self._latest_c is None:
                return False
            if self._latest_c < STOVE_ALERT_THRESHOLD_C:
                return False
            return (now - self._above_since) >= STOVE_ALERT_DURATION_SEC

    def reading_below_threshold_c(self) -> bool:
        with self._lock:
            if self._latest_c is None:
                return False
            return self._latest_c < STOVE_ALERT_THRESHOLD_C

    def get_display(self) -> str:
        with self._lock:
            tc, tf = self._latest_c, self._latest_f
        if tc is None or tf is None:
            return "—"
        if STOVE_DISPLAY_CELSIUS:
            return f"{tc:.1f}°C"
        return f"{tf:.0f}°F"

    def _run_loop(self) -> None:
        try:
            import serial
        except ImportError:
            logger.error(
                "pyserial is not installed; stove temperature sensor disabled. "
                "Install the pyserial package to enable temperature monitoring."
            )
            with self._lock:
                self._latest_c = None
                self._latest_f = None
                self._above_since = None
            return

        while True:
            try:
                ser = serial.Serial(self._port, self._baud, timeout=1)
            except Exception as e:
                logger.debug(f"stove serial open {self._port}: {e}")
                with self._lock:
                    self._latest_c = None
                    self._latest_f = None
                    self._above_since = None
                time.sleep(2)
                continue
            try:
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", errors="replace").strip()
                    parsed = self._parse_line(text)
                    if parsed is not None:
                        tc, tf = parsed
                        self._note_reading(tc, tf)
            except Exception as e:
                logger.debug(f"stove serial read: {e}")
                with self._lock:
                    self._latest_c = None
                    self._latest_f = None
                    self._above_since = None
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
            time.sleep(2)
