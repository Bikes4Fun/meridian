## Summary
TV-based digital assistant for dementia patients and families. Provides daily orientation (large date/time, appointments), medication reminders with safety features, emergency medical info, and photo-based family directory. Target: mild-moderate dementia, living at home.


## Technical Stack
- **Language**: Python
- **UI**: Kivy (TV-sized touch interface)
- **Database**: SQLite
- **Libraries**: Pillow (images), Requests (APIs), QR code libs
- **Deployment**: Raspberry Pi, local network, optional cloud backup


## Run
```bash
pip install -r requirements.txt
python src/dev/main.py
```

## Tests
```bash
PYTHONPATH=src pytest src/dev/tests     # All tests
PYTHONPATH=src pytest src/dev/tests -v  # Verbose
PYTHONPATH=src pytest src/dev/tests/test_contact.py   # Specific file
PYTHONPATH=src pytest src/dev/tests --cov=apps --cov=shared --cov-report=html
```
See `src/dev/tests/README.md` for fixtures, markers, and test structure.

## Architecture
- **shared/config.py** – ConfigManager, DatabaseConfig; environment-based config
- **shared/interfaces.py** – ServiceResult, service contracts
- **apps/server/** – Flask API (api.py), database (database.py), services (container, calendar, contact, etc.)
- **apps/kiosk/** – Kivy TV UI (app.py, screens.py, widgets.py, api_client.py, settings.py)
- **dev/main.py** – Entry point; starts API server and Kivy client

## Project Structure
```
meridian/
├── src/
│   ├── apps/
│   │   ├── kiosk/              # Kivy TV UI (screens, widgets, api_client)
│   │   │   ├── app.py
│   │   │   ├── screens.py
│   │   │   ├── widgets.py
│   │   │   ├── modular_display.py
│   │   │   ├── api_client.py
│   │   │   ├── settings.py
│   │   │   └── cache/          # Map tile cache
│   │   ├── server/             # Flask API, DB, services
│   │   │   ├── api.py
│   │   │   ├── database.py
│   │   │   ├── schema.sql
│   │   │   ├── ice_profile.json
│   │   │   └── services/
│   │   │       ├── container.py
│   │   │       ├── calendar.py
│   │   │       ├── contact.py
│   │   │       ├── emergency.py
│   │   │       ├── ice_profile.py
│   │   │       ├── location.py
│   │   │       └── medication.py
│   │   └── webapp/             # Web client (checkin, map)
│   │       ├── web_client/
│   │       │   ├── checkin.html
│   │       │   └── checkin.js
│   │       └── web_server/
│   │           ├── build.js
│   │           ├── package.json
│   │           └── vercel.json
│   ├── dev/
│   │   ├── main.py             # Entry point
│   │   ├── demo/
│   │   │   ├── seed.py
│   │   │   └── data/
│   │   │       ├── calendar.json
│   │   │       ├── contacts.json
│   │   │       ├── family.json
│   │   │       ├── medical.json
│   │   │       ├── kiosk_settings.json
│   │   │       └── family_img/
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── pytest.ini
│   │       ├── test_api.py
│   │       ├── test_calendar.py
│   │       ├── test_contact.py
│   │       ├── test_database.py
│   │       ├── test_medication.py
│   │       └── test_time_service.py
│   └── shared/
│       ├── config.py
│       └── interfaces.py
├── info/
│   ├── assignments/
│   ├── git_issue_generation.sh
│   └── third party documentation and research/
├── requirements.txt
├── README.md
└── todo.md
```

