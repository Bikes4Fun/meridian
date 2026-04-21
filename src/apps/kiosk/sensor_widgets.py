"""Background serial reader for stove / oven temperature (Arduino Nano, socat simulator, etc.).

Alert thresholds and snooze live here (kiosk-side), not in shared.config.
When readings stay above threshold for STOVE_ALERT_DURATION_SEC, the kiosk posts the same
/api/emergency/alert activated=true flow the webapp uses so family sees the emergency screen.
"""

import glob
import logging
import os
import re
import sys
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Wire format: Arduino (or any sender) may print one line per reading:
#   MERIDIAN,C,34.56
#   MERIDIAN,F,94.1
# Other lines still work via the numeric regex below (e.g. "Temp: 31.6 °C").


def _default_stove_serial_port() -> str:
    """STOVE_SERIAL_PORT from env, else first USB serial on macOS, else Linux default."""
    raw = os.environ.get("STOVE_SERIAL_PORT")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    if sys.platform.startswith("win"):
        return "COM3"
    if sys.platform == "darwin":
        matches = sorted(
            glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.wchusbserial*")
        )
        if matches:
            return matches[0]
    return "/dev/ttyUSB0"


# Serial device (set in .env or STOVE_SERIAL_PORT; /tmp/ttyFAKE0 for a simulator).
STOVE_SERIAL_PORT = _default_stove_serial_port()
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

class SensorHandler:
    def __init__(self, app):
        self._app = app
        self._temp_sensor: Optional["TemperatureSensor"] = None
        self._stove_alert_armed = False
        self._push_thread: Optional[threading.Thread] = None

    def start_stove_sensor(self) -> None:
        if self._temp_sensor is None:
            self._temp_sensor = TemperatureSensor()
            self._temp_sensor.start()
        if self._push_thread is not None:
            return
        self._push_thread = threading.Thread(target=self._start_temp_push, daemon=True)
        self._push_thread.start()

    def push_stove_temp_display(self) -> None:
        """Refresh Settings → Monitors stove value immediately."""
        sensor = self._temp_sensor
        if not sensor:
            return
        self._app._eval_el("stove-temp", sensor.get_display())

    def _start_temp_push(self):
        """Push stove temperature to UI and post/clear emergency alert via server (same as webapp)."""
        while True:
            time.sleep(2)
            if self._temp_sensor:
                reading = self._temp_sensor.get_display()
                self._app._eval_el("stove-temp", reading)
                self._maybe_stove_emergency_alert()

    def snooze_stove_alerts(self) -> None:
        if self._temp_sensor:
            self._temp_sensor._snooze_local_timer()
        alert_svc = self._app.services.get_alert_service()
        if alert_svc and getattr(alert_svc, "set_alert_activated", None):
            r = alert_svc.set_alert_activated(False)
            if r.success:
                self._stove_alert_armed = False
        else:
            self._stove_alert_armed = False

    def _maybe_stove_emergency_alert(self) -> None:
        sensor = self._temp_sensor
        alert_svc = self._app.services.get_alert_service()
        if not sensor or not alert_svc or not getattr(
            alert_svc, "set_alert_activated", None
        ):
            return
        if sensor.should_activate_stove_emergency():
            if not self._stove_alert_armed:
                r = alert_svc.set_alert_activated(True)
                if r.success:
                    self._stove_alert_armed = True
                    logger.info("Stove temperature sustained over threshold; alert activated")
            return
        if self._stove_alert_armed and sensor.reading_below_threshold_c():
            r = alert_svc.set_alert_activated(False)
            if r.success:
                logger.info("Stove temperature normalized; alert cleared")
                self._stove_alert_armed = False

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
        upper = line.upper()
        if upper.startswith("MERIDIAN,"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    unit = parts[1].upper()
                    val = float(parts[2])
                    if unit == "C":
                        return _both_from_value(val, True)
                    if unit == "F":
                        return _both_from_value(val, False)
                except ValueError:
                    pass
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

    def _snooze_local_timer(self) -> None:
        """Sensor-local snooze window; does not touch server alert state."""
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
                logger.info(f"stove serial connected {self._port} @ {self._baud} baud")
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


