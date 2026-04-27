# Meridian

<p align="center">
  <img src="src/shared/assets/icons/original_banner_logo.png" alt="Meridian banner" width="420">
</p>


A large-format family command center for patients living at home with mild-to-moderate cognitive decline and their families.

Meridian is intended to run as a wall-mounted fixture (such as a touch-screen TV or monitor):

- **Stays put** — no losing it like phones and chargers  
- **Visible from across the room** — always in place  
- **Accessible** — large formatting for low-vision users and those prone to disorientation

It aims to provide benefits and services such as anxiety relief for common dementia/Alzheimer's symptoms, time and location orientation, healthcare management, and connection features that reduce caregiver burden and help patients maintain independence longer.

---

## ⚠️ Development Data Security Risk / Not for production use

**Meridian is in active development. If you explore the webapp or kiosk, enter test/demo data ONLY.**

- **Do not enter private data** — anything you would not want accessible to anyone who can see this repository or navigate to the webapp, server URL, DB URL, etc. (real names, medical info, phone numbers, etc.).
- **Nothing is encrypted and there is no true authentication yet.**

---

## Why Meridian?

Patients with cognitive decline face daily challenges such as stress and confusion, time orientation, medication management, cognitive overload and feeling connected to family. Caregivers face anxiety about safety, missed medications, and emergency
preparedness. Meridian addresses both sides:

- **For patients** — large, simple UI with familiar faces, clear time/date, and medication reminders
- **For caregivers** — real-time family location, emergency profile always up to date, one-button alert
- **For first responders** — printable POLST/ICE document with DNR status, medications, and contacts

## Who It's For

🙋‍♀️🙋‍♂️🧓 Primary user: patients with mild-to-moderate progressive cognitive decline living at home.
While typically these care-recipients are elderly and aging, this is not always the case.
As such, anyone with progressive cognitive decline who is still living at home is a potential user.
🙋‍♀️🙋‍♂️🚑 Secondary users: adult children, family caregivers, and in an emergency, first responders.

## Screenshots

Development status as of March 22, 2026

### Kiosk home screen

<p align="center">
  <img src="assets/examples/kiosk%20home%20march%2022.png" alt="Kiosk home screen" width="400">
</p>

### Emergency / ICE screen and webapp alert

<p align="center">
  <img src="assets/examples/kiosk%20running%20emergency%20alert%20with%20webapp%20button%20displayed.png" alt="Emergency ICE screen with webapp alert controls" width="680">
</p>

### Family chat

<p align="center">
  <img src="assets/examples/kiosk%20family%20chat%20screen.png" alt="Family chat screen" width="400">
</p>

> *Printed POLST PDF* (coming soon)

> *iOS app* (coming soon)

---

## Discussions & Polls

GitHub Discussions for design decisions. Please engage in our current open polls:

- 💬 [What's Next?](https://github.com/Bikes4Fun/meridian/discussions/113)

- 💬 [Emergency Profile / POLST — Feature Priorities](https://github.com/Bikes4Fun/meridian/discussions/109#discussion-9723470)
- 💬 [Kiosk Chat Window](https://github.com/Bikes4Fun/meridian/discussions/108#discussion-9723391)

---

## Technical Stack
- **UI and mobile**: pywebview + HTML/CSS/JS, Swift (iOS)
- **Server**: Python (Flask), SQLite
- **Libraries and APIs**: Pillow, Requests, Leaflet, ReportLab, Twilio

**Push notifications (Where is everyone?)**  
Without APNs config, the server logs requests but does not send pushes. To enable real push on a physical device, set: `APNS_AUTH_KEY_PATH` (path to .p8 key), `APNS_KEY_ID`, `APNS_TEAM_ID`. Optional: `APNS_BUNDLE_ID` (default com.meridian.Meridian), `APNS_USE_SANDBOX=1` for dev.

**iOS kiosk call (`GET /api/family/kiosk-number`, force-answer)**  
`FamilyService.get_twilio_number` uses **`MERIDIAN_DEMO_KIOSK_TWILIO_NUMBER`** or **`TWILIO_PHONE_NUMBER`** when set (same as Twilio Voice), else `family_circles.twilio_phone_number`, and the `api_kiosk_number` route can fall back to optional [`family_circles.json`](src/dev/demo/data/family_circles.json). **`POST /api/calls/force-answer` returning 404** means the route is missing on that host; a current server returns **201**.

---

## Run and Tests

On **Windows**, run the kiosk with **64-bit Python 3.11 or 3.12** from [python.org](https://www.python.org/downloads/). The kiosk uses `pywebview`, which depends on `pythonnet`; current `pythonnet` wheels do not cover Python 3.14, so `pip install -r requirements.txt` fails while building from source. After installing a supported Python, use `py -3.12 -m pip install -r requirements.txt` (or activate a 3.12 venv). From `src`, run **`py -3.12 main.py`** — not plain `python main.py` if another Python (e.g. 3.14) is first on `PATH`, or you will get `ModuleNotFoundError` for packages installed into 3.12. If pywebview logs **WebView2** / **Invalid window handle** (`0x80070578`), start the app from a **normal desktop session** (open `cmd` or PowerShell while logged in at the PC, or inside Remote Desktop), not from an **SSH-only** shell; the kiosk needs an interactive Windows desktop. Install or repair the [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) if the error persists.

```bash
pip install -r requirements.txt
PYTHONPATH=src python src/main.py           # local DB/server (default); add `--remote` for kiosk-only against remote API (`RAILWAY_API_URL` / `.env`; legacy `--remote-api` works)
PYTHONPATH=src python -m apps.server
PYTHONPATH=src python -m apps.webapp
PYTHONPATH=src python -m apps.kiosk
PYTHONPATH=src pytest src/dev/tests         # -v for verbose;
```

### Twilio Voice Quickstart (Server-Side)

```bash
pip install flask twilio
export TWILIO_ACCOUNT_SID=YOUR_ACCOUNT_SID
export TWILIO_AUTH_TOKEN=YOUR_AUTH_TOKEN
export TWILIO_PHONE_NUMBER=+1YOUR_TWILIO_NUMBER
```

```python
import os
from twilio.rest import Client

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
call = client.calls.create(
    url="http://demo.twilio.com/docs/voice.xml",
    to="+18005550100",
    from_="+18005550199",
)
print(call.sid)
```

---


## Project Structure
```
meridian/
├── src/
│   ├── apps/
│   │   ├── kiosk/              # pywebview TV UI (HTML/CSS/JS)
│   │   │   ├── app.py
│   │   │   ├── web/            # kiosk.html, kiosk.css, kiosk.js
│   │   │   ├── html_primitives.py
│   │   │   ├── api_client.py
│   │   │   ├── *_screen.py     # home, emergency, checkin, chat
│   │   │   └── cache/          # Map tile cache
│   │   ├── server/             # Flask API, DB, services
│   │   │   ├── api.py
│   │   │   └── database_services/   # schema.sql (SQLite DDL), QueryManager, domain services
│   │   └── webapp/             # Caregiver web client
│   ├── dev/
│   │   ├── demo/               # Seed demo data
│   │   └── tests/              # README.md
│   ├── main.py                 # Entry point (API + kiosk)
│   └── shared/
│       ├── config.py
│       └── interfaces.py
├── requirements.txt
└── README.md
```

---

Almost all written content in issues, milestones, and documentation has been generated entirely
by, or with assistance from, Cursor Agent and Claude (Anthropic).
