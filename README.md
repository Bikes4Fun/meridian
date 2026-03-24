# Meridian

![Meridian banner](assets/banner_logo.png)


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

**Kiosk home screen**

![image of Kiosk home](assets/kiosk%20home%20march%2022.png)

**Emergency / ICE screen and webapp alert**

![image of Emergency alert](assets/kiosk%20running%20emergency%20alert%20with%20webapp%20button%20displayed.png)

**Family chat**

![image of Family chat](assets/kiosk%20family%20chat%20screen.png)

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
- **Libraries and APIs**: Pillow, Requests, Leaflet, ReportLab, Sendbird

**Push notifications (Where is everyone?)**  
Without APNs config, the server logs requests but does not send pushes. To enable real push on a physical device, set: `APNS_AUTH_KEY_PATH` (path to .p8 key), `APNS_KEY_ID`, `APNS_TEAM_ID`. Optional: `APNS_BUNDLE_ID` (default com.meridian.Meridian), `APNS_USE_SANDBOX=1` for dev.

---

## Run and Tests
```bash
pip install -r requirements.txt
PYTHONPATH=src python src/main.py           # --local for local DB/server; omit for Railway.
PYTHONPATH=src pytest src/dev/tests         # -v for verbose;
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
│   │   │   ├── database.py
│   │   │   ├── schema.sql
│   │   │   └── services/
│   │   ├── chatapp/            # Sendbird chat integration
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
