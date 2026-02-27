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
python lib/main.py
```

## Tests
```bash
pytest                  # All tests
pytest -v               # Verbose
pytest tests/test_contact_service.py   # Specific file
pytest --cov=lib        # With coverage
```
See `tests/README.md` for fixtures, markers, and test structure.

## Architecture
- **config.py** – ConfigManager, AppConfig; environment-based config
- **interfaces.py** – Service contracts (Contact, Calendar, Medication, etc.)
- **container.py** – DI container; service lifecycle and resolution
- **database_manager.py** – Centralized DB ops
- **app_factory.py** – Creates and configures the application

## Project Structure
```
meridian/
├── lib/                      # Core application
│   ├── app_factory.py
│   ├── config.py
│   ├── interfaces.py
│   ├── main.py
│   ├── demo/                 # Demo data and seeding
│   │   ├── demo.py
│   │   └── demo_data/
│   │       ├── calendar_events.json
│   │       ├── contacts.json
│   │       ├── default_display_settings.json
│   │       ├── family.json
│   │       ├── medical_info.json
│   │       └── family_img/
│   ├── display/              # Kivy UI (screens, widgets)
│   │   ├── modular_display.py
│   │   ├── screens.py
│   │   ├── widgets.py
│   │   ├── user_settings.py
│   │   └── remote_services.py
│   ├── server/               # Flask API, services, DB
│   │   ├── app.py
│   │   ├── __main__.py
│   │   ├── database_management/
│   │   │   ├── database_manager.py
│   │   │   └── ice_profile.json
│   │   └── container_services/
│   │       ├── container.py
│   │       ├── calendar_service.py
│   │       ├── contact_service.py
│   │       ├── emergency_service.py
│   │       ├── ice_profile_service.py
│   │       ├── location_service.py
│   │       └── medication_service.py
│   └── webapp/               # Web client (checkin, map)
│       ├── web_client/
│       │   ├── checkin.html
│       │   └── checkin.js
│       └── web_server/
│           ├── build.js
│           ├── package.json
│           └── vercel.json
├── tests/
│   ├── conftest.py
│   ├── pytest.ini
│   ├── test_api_server.py
│   ├── test_calendar_service.py
│   ├── test_contact_service.py
│   ├── test_database_manager.py
│   ├── test_medication_service.py
│   └── test_time_service.py
├── info/
│   ├── ARCHITECTURE.md
│   ├── todo.md
│   ├── DEPRECATED.md
│   ├── git_issue_generation.sh
│   ├── assignments/
│   │   ├── check 1/
│   │   ├── proposal/
│   │   └── powerpoints/
│   └── third party documentation and research/
├── .gitignore
├── README.md
├── requirements.txt
└── todo.md
```

