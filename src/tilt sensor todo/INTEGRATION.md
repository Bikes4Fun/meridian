# Meridian Tilt Sensor Integration Plan
## DFR0028 Gravity Digital Tilt Sensor — Bottle / Item Monitor

---

## What This Does

Four tilt sensors (DFR0028, single-direction) are attached to bottles or containers — medications, alcohol, cleaning supplies, or anything the family wants to monitor. When an item is picked up, moved, or tipped, the sensor transitions from UPRIGHT → TILTED and the Arduino immediately sends a serial event. The Meridian kiosk reads this in real time and the server logs it so the webapp can show a timeline.

This is **passive monitoring without a camera** — the patient never knows it's there, and it doesn't require any interaction.

---

## Hardware Setup

### Wiring (per sensor)
```
DFR0028 sensor
  VCC  ──►  Arduino 5V pin  (or 4.5V battery holder positive)
  GND  ──►  Arduino GND
  SIG  ──►  Arduino digital pin (pins 2, 3, 4, 5 in the sketch)
```

The DFR0028 single-direction model outputs:
- **HIGH** when upright (ball rolls to contact pins)
- **LOW** when tilted past threshold (ball rolls away)

### Battery holders (FIT0337, 4.5V)
These are for standalone deployment — sensors that live on a shelf far from a wall outlet. For the prototype, just use the Arduino 5V rail. When deploying in the field, each sensor module (sensor + tiny enclosure) can be powered by its own 4.5V cell holder.

### Arduino placement
The Arduino itself stays near the kiosk (USB to the kiosk computer for serial). Run thin 2-wire or 3-wire cables from the Arduino to each sensor placement. Cat5/ethernet wire works well for long runs — you have 4 pairs, one per sensor.

### Sensor placement ideas
- **Medication bottles** — tape or velcro sensor to the side or bottom; fires when bottle is lifted
- **Cleaning supply cabinet** — inside cabinet door frame, fires when door opens past threshold
- **Alcohol bottles** — same as medication; can track if cabinet is opened overnight
- **Water/hydration bottle** — fires when picked up, gives an indirect hydration signal
- **Bed edge / chair** — angled placement detects when patient sits or stands (more advanced)

---

## Wire Protocol

The Arduino sends lines over Serial at 9600 baud. Format:

```
MERIDIAN,TILT,<sensor_id>,<state>,<event>
```

| Field | Values | Meaning |
|---|---|---|
| `sensor_id` | 1–4 | Which sensor fired |
| `state` | `UPRIGHT` / `TILTED` | Current stable state |
| `event` | `CHANGED` / `STEADY` | CHANGED = transition just happened; STEADY = heartbeat |

**Examples:**
```
MERIDIAN,TILT,INIT,READY           ← Arduino just powered on
MERIDIAN,TILT,2,TILTED,CHANGED     ← Sensor 2 just tipped (bottle picked up)
MERIDIAN,TILT,2,UPRIGHT,CHANGED    ← Sensor 2 back upright (bottle set down)
MERIDIAN,TILT,1,UPRIGHT,STEADY     ← Heartbeat; sensor 1 still upright, no change
```

This intentionally matches the `MERIDIAN,*` prefix used by the existing stove temperature sensor so the serial parsing infrastructure is reusable.

---

## Kiosk Integration — `sensor_widgets.py`

Add a `TiltSensorHandler` class to `sensor_widgets.py`, mirroring the existing `SensorHandler` / `TemperatureSensor` pattern.

### New env vars
```
TILT_SERIAL_PORT   (default: /dev/ttyUSB1 or next available USB serial)
TILT_SERIAL_BAUD   (default: 9600)
```

### Class structure

```python
# In sensor_widgets.py — add alongside TemperatureSensor

TILT_SENSOR_NAMES = {
    "1": os.environ.get("TILT_SENSOR_1_NAME", "Sensor 1"),
    "2": os.environ.get("TILT_SENSOR_2_NAME", "Sensor 2"),
    "3": os.environ.get("TILT_SENSOR_3_NAME", "Sensor 3"),
    "4": os.environ.get("TILT_SENSOR_4_NAME", "Sensor 4"),
}
# e.g. TILT_SENSOR_1_NAME="Morning medications"
#      TILT_SENSOR_2_NAME="Evening medications"

class TiltSensor:
    """Daemon thread reads DFR0028 tilt events from serial."""
    # Tracks: per-sensor state (UPRIGHT/TILTED), last_changed timestamp,
    # event log (last N events with timestamp + state)
    # Methods: start(), get_states() -> dict, get_recent_events() -> list

class TiltSensorHandler:
    """Attached to SensorHandler; pushes tilt state to kiosk UI and posts events to server API."""
    # start_tilt_sensor()
    # _start_tilt_push() — reads events, posts to /api/sensors/tilt/event
    # get_tilt_display() -> dict  (for kiosk settings UI)
```

### Kiosk settings screen display
In `settings_screen.py`, add a tilt sensor section to the Monitors card below the stove temperature row. For each sensor (1–4):

```
Morning medications    ● UPRIGHT     Last moved: 8:32 AM
Evening medications    ● TILTED      Just moved
Sensor 3               ○ offline
Sensor 4               ● UPRIGHT     Last moved: yesterday 6:14 PM
```

The kiosk display is read-only — informational for the caregiver who might be at the kiosk, and more prominently surfaced in the webapp.

---

## Server API — New Endpoints

Add to `api.py`:

### POST `/api/family_circles/<id>/sensors/tilt/event`
Called by the kiosk when a CHANGED event fires. Body:
```json
{
  "sensor_id": "2",
  "sensor_name": "Evening medications",
  "state": "TILTED",
  "timestamp": "2026-04-19T20:14:00"
}
```

### GET `/api/family_circles/<id>/sensors/tilt/status`
Returns current state of all 4 sensors plus recent event log.
```json
{
  "sensors": {
    "1": { "name": "Morning medications", "state": "UPRIGHT", "last_changed": "2026-04-19T08:32:00" },
    "2": { "name": "Evening medications", "state": "TILTED",  "last_changed": "2026-04-19T20:14:00" },
    "3": { "name": "Sensor 3",            "state": null,       "last_changed": null },
    "4": { "name": "Sensor 4",            "state": "UPRIGHT", "last_changed": "2026-04-18T18:14:00" }
  },
  "recent_events": [
    { "sensor_id": "2", "sensor_name": "Evening medications", "state": "TILTED", "timestamp": "..." },
    ...
  ]
}
```

### Database
Add a `tilt_sensor_events` table:
```sql
CREATE TABLE tilt_sensor_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    sensor_name TEXT,
    state TEXT NOT NULL,          -- 'UPRIGHT' or 'TILTED'
    recorded_at TEXT NOT NULL     -- ISO timestamp
);
```
Keep the last 500 rows per family circle (prune on insert). No need for a large history table — this is a rolling log.

---

## Webapp Integration

### Health tab — Medication adherence signal
The tilt sensor data surfaces naturally in the Health tab alongside medications. Add a small "Last accessed" timestamp next to each medication in the list, derived from tilt sensor events. This is a soft signal, not a strict medication tracking claim — "Morning medications bottle last moved at 8:32 AM" is useful context, not medical record.

The mapping between sensor IDs and medications is set in the webapp Kiosk Settings → Sensors section (admin assigns which sensor monitors which medication or item).

### Kiosk Settings tab — Sensors section
In the webapp Kiosk Settings tab, add a Sensors card. For each sensor slot (1–4):
- Editable name field: what is this sensor monitoring? (e.g. "Morning medications")
- Current state badge: UPRIGHT / TILTED / Offline
- Last event timestamp
- Enable/disable notifications for this sensor

### Notifications
Tilt events can optionally generate notifications to family members. Configurable per sensor:
- **No notification** — log only (default)
- **Notify after hours** — only alert if the sensor fires between midnight and 6 AM (cabinet opened at night)
- **Always notify** — push to configured family members on any TILTED event
- **Notify if not moved** — alert if a sensor has been UPRIGHT (bottle not touched) past a configured time window (e.g. "Evening medications not moved by 9 PM")

The "notify if not moved" case is especially valuable — it's a passive medication adherence signal without requiring any patient interaction.

### Family Circle tab — Sensor activity feed
In the Family Circle overview, a small sensor activity strip shows the last 5 tilt events across all sensors, with relative timestamps: "Evening medications — moved 2 hours ago." This gives family members at a glance whether routine activities happened as expected today.

---

## Alert Logic on the Kiosk

CHANGED events are the only ones that trigger any action. STEADY/heartbeat lines just update the display.

For the kiosk, tilt events are informational — they do **not** trigger the emergency alert system (unlike the stove sensor). The emergency alert system is for stove/fire/fall. Tilt events go into the log and optionally trigger push notifications via the server.

The one exception: if you want to add a "bottle opened overnight" alert, the kiosk can check whether a TILTED event arrived during a configured quiet window and post a lower-priority notification (not the red emergency mode, but a yellow advisory).

---

## Deployment Notes

- The Arduino appears as a second USB serial device alongside the stove temperature Arduino (or they can be the same Arduino if enough pins are available — the stove sensor uses pin 2 via OneWire; just shift tilt sensor pins to 4, 5, 6, 7 and share one Arduino).
- `TILT_SERIAL_PORT` and `STOVE_SERIAL_PORT` should point to different `/dev/ttyUSB*` devices if using two Arduinos.
- If using one Arduino for both stove (DS18B20 OneWire on pin 2) and tilt (DFR0028 on pins 4–7), the combined sketch sends both `MERIDIAN,C,34.56` and `MERIDIAN,TILT,1,UPRIGHT,STEADY` lines on the same serial port. The kiosk parser routes them by prefix.
- Label sensor positions with tape on first deployment so the admin knows which slot ID maps to which physical bottle.
