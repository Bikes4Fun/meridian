# ── sensor_widgets.py additions ────────────────────────────────────────────────
#
# Add to SensorHandler (alongside existing stove push methods).
# These push live data to the new sensor card UI via meridianSensors JS object.

import json
import time

# ── Stove push (replaces existing _start_temp_push / push_stove_temp_display) ──

def _push_stove_card(self) -> None:
    """Push full stove sensor state to the new sensor card UI."""
    sensor = self._temp_sensor
    if not sensor:
        # Sensor never started — offline
        payload = {
            "temp": "—",
            "lastRead": "",
            "status": "offline",
            "alertTime": None,
            "barPct": 0,
            "snoozed": False,
            "snoozeLeft": None,
            "offline": True,
        }
    else:
        temp_str = sensor.get_display()          # e.g. "82.4°F"
        status = "unknown"
        bar_pct = 0
        alert_time_str = None
        offline = False

        with sensor._lock:
            tc = sensor._latest_c
            armed = self._stove_alert_armed
            ignore_until = sensor._ignore_until
            above_since = sensor._above_since

        if tc is None:
            status = "offline"
            offline = True
        elif armed:
            status = "alert"
            # bar at 100% during active alert
            bar_pct = 100
            # Format alert time from above_since
            if above_since:
                import datetime
                alert_time_str = "Triggered " + datetime.datetime.fromtimestamp(
                    above_since
                ).strftime("%-I:%M %p")
        else:
            status = "online"
            from .sensor_widgets import STOVE_ALERT_THRESHOLD_C
            if tc is not None:
                # bar = fraction of threshold; cap at 95% when not alerting
                bar_pct = min(95, int((tc / STOVE_ALERT_THRESHOLD_C) * 100))

        snoozed = ignore_until > time.time()
        snooze_left = None
        if snoozed:
            remaining_sec = int(ignore_until - time.time())
            snooze_left = f"{remaining_sec // 60} min left"

        payload = {
            "temp": temp_str,
            "lastRead": "Last read just now",  # or track timestamp and format
            "status": status,
            "alertTime": alert_time_str,
            "barPct": bar_pct,
            "snoozed": snoozed,
            "snoozeLeft": snooze_left,
            "offline": offline,
        }

    js = f"if(window.meridianSensors)meridianSensors.updateStove({json.dumps(payload)});"
    self._app._eval(js)


# ── Tilt sensor push (call from TiltSensorHandler push loop) ───────────────────

def _push_tilt_card(self, slot: int, state: str, last_changed_ts, missed_warn: str | None = None) -> None:
    """
    Push tilt sensor state for one slot to the UI.
    slot: 1–4
    state: 'upright' | 'tilted' | 'offline'
    last_changed_ts: float (time.time()) or None
    missed_warn: str shown in amber banner, or None to hide it
    """
    import datetime

    time_str = "—"
    if last_changed_ts:
        now = time.time()
        elapsed = now - last_changed_ts
        if elapsed < 90:
            time_str = "just now"
        elif elapsed < 3600:
            time_str = f"{int(elapsed // 60)} min ago"
        elif elapsed < 86400:
            time_str = datetime.datetime.fromtimestamp(last_changed_ts).strftime("%-I:%M %p")
        else:
            time_str = "yesterday"

    opts = {"state": state, "time": time_str}
    js = f"if(window.meridianSensors)meridianSensors.updateTilt({slot},{json.dumps(opts)});"
    self._app._eval(js)

    if missed_warn is not None:
        warn_js = f"if(window.meridianSensors)meridianSensors.updateTiltMissedWarn({json.dumps(missed_warn)});"
        self._app._eval(warn_js)


# ── app.py: update _navigate_to to also push sensor card on settings load ──────
#
# In MeridianKioskApp._navigate_to, after the existing:
#   if screen_name == "settings":
#       self._sensor.push_stove_temp_display()
#
# Replace with:
#   if screen_name == "settings":
#       self._sensor.push_stove_card_full()   # new method wrapping _push_stove_card
#       self._sensor.push_all_tilt_cards()    # new method iterating slots 1-4
