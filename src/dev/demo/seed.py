"""
Demo functions for loading JSON data into SQLite database.

WHERE THIS IS USED: main.main() calls demo_main(user_id) when demo_mode is True to seed the
local SQLite database (contacts, medications, calendar, display settings, etc.).

RELOCATION/REMOVAL: In a strict client/server deployment, data lives on the server. Run demo
once against the server's DB (or use a separate migration/seed step on the server). The client
does not need this package if it never seeds data; it can be omitted from the client deployment
or relocated to a server-only / admin script.
"""

import json
import logging
import os
import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import sys

try:
    from apps.server.database import DatabaseManager
    from shared.config import DatabaseConfig, get_database_path
except ImportError:
    from apps.server.database import DatabaseManager
    from shared.config import DatabaseConfig, get_database_path


def get_data_dir():
    """Get the path to the demo data directory."""
    return os.path.join(os.path.dirname(__file__), "data")


_db_manager_cache = {}


def get_database_manager(db_path: str) -> DatabaseManager:
    """Get a DatabaseManager instance for the SQLite database (cached per path)."""
    if db_path not in _db_manager_cache:
        db_config = DatabaseConfig(path=db_path, create_if_missing=True)
        _db_manager_cache[db_path] = DatabaseManager(db_config)
    return _db_manager_cache[db_path]


def load_json_file(filename: str) -> Dict[str, Any]:
    """Load a JSON file from the demo_data directory."""
    file_path = os.path.join(get_data_dir(), filename)
    with open(file_path, "r") as f:
        return json.load(f)


def load_demo_contacts_from_json_into_db(db_path: str, user_id: str):
    """Load contacts from JSON. Can have photo_filename and notes for contact card."""
    contacts_data = load_json_file("contacts.json")
    contacts = contacts_data.get("contacts", [])

    db_manager = get_database_manager(db_path)

    for contact in contacts:
        query = """
            INSERT OR REPLACE INTO contacts 
            (id, user_id, display_name, phone, email, birthday, relationship, priority, photo_filename, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            contact.get("id"),
            user_id,
            contact.get("display_name"),
            contact.get("phone"),
            contact.get("email"),
            contact.get("birthday"),
            contact.get("relationship"),
            contact.get("priority"),
            contact.get("photo_filename"),
            contact.get("notes"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d contacts" % len(contacts))


def load_demo_family_members_from_json_into_db(db_path: str, user_id: str):
    """Load family members (tracked users). Cross-referenced to contacts via contact_id for contact card."""
    family_data = load_json_file("family.json")
    members = family_data.get("family_members", [])
    photo_base = family_data.get("photo_base", "")

    db_manager = get_database_manager(db_path)

    for member in members:
        fn = member.get("photo_filename")
        photo_path = ("%s/%s" % (photo_base, fn)) if photo_base and fn else fn
        query = """
            INSERT OR REPLACE INTO family_members 
            (id, user_id, display_name, photo_filename, contact_id)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            member.get("id"),
            user_id,
            member.get("display_name"),
            photo_path,
            member.get("contact_id"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d family members" % len(members))


def load_demo_medication_groups_from_json_into_db(db_path: str, user_id: str):
    """Load medication groups from JSON into SQLite database."""
    medical_data = load_json_file("medical.json")
    groups = medical_data.get("medication_groups", {})

    db_manager = get_database_manager(db_path)

    for group_name, group_data in groups.items():
        time_value = group_data.get("time")
        if time_value == "null" or time_value is None:
            time_value = None

        query = """
            INSERT OR REPLACE INTO medication_groups 
            (name, time, display_name)
            VALUES (?, ?, ?)
        """
        params = (group_name, time_value, group_data.get("display_name"))
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d medication groups" % len(groups))


def load_demo_medications_data_from_json_to_db(db_path: str, user_id: str):
    """Load medications from JSON into SQLite database."""
    medical_data = load_json_file("medical.json")
    medications = medical_data.get("medications", [])

    db_manager = get_database_manager(db_path)

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        for med in medications:
            cursor.execute(
                """
                INSERT OR REPLACE INTO medications 
                (user_id, name, dosage, frequency, notes, max_daily, current_quantity, last_taken, taken_today)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    med.get("name"),
                    med.get("dosage"),
                    med.get("frequency"),
                    med.get("notes"),
                    med.get("max_daily"),
                    med.get("current_quantity"),
                    med.get("last_taken"),
                    med.get("taken"),
                ),
            )

            # Get the medication ID for junction table
            medication_id = cursor.lastrowid

            # Add to medication groups
            groups = med.get("groups", [])
            for group_name in groups:
                # Get group ID
                cursor.execute(
                    "SELECT id FROM medication_groups WHERE name = ?", (group_name,)
                )
                group_result = cursor.fetchone()
                if group_result:
                    group_id = group_result[0]
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO medication_to_group (medication_id, group_id)
                        VALUES (?, ?)
                    """,
                        (medication_id, group_id),
                    )

        conn.commit()
    logger.debug("  Loaded %d medications" % len(medications))


def load_allergies_data(db_path: str, user_id: str):
    """Load allergies from JSON into SQLite database."""
    medical_data = load_json_file("medical.json")
    allergies = medical_data.get("allergies", [])

    db_manager = get_database_manager(db_path)

    for allergy in allergies:
        query = """
            INSERT OR REPLACE INTO allergies (user_id, allergen)
            VALUES (?, ?)
        """
        db_manager.execute_update(query, (user_id, allergy.get("allergen")))
    logger.debug("  Loaded %d allergies" % len(allergies))


def load_demo_ice_profile_data(db_path: str, user_id: str):
    """Load ICE profile from JSON (users row created in demo_main)."""
    medical_data = load_json_file("medical.json")
    ice_data = medical_data.get("ice_profile", {})
    if not ice_data:
        return

    db_manager = get_database_manager(db_path)
    profile = ice_data.get("profile") or {}
    medical = ice_data.get("medical") or {}
    emergency = ice_data.get("emergency") or {}
    proxy = emergency.get("proxy") or {}
    existing = db_manager.execute_query(
        "SELECT id FROM ice_profile WHERE user_id = ?", (user_id,)
    )
    params = (
        profile.get("name"),
        profile.get("dob"),
        medical.get("conditions"),
        1 if medical.get("dnr") else 0,
        proxy.get("name"),
        ice_data.get("medical_proxy_phone"),
        ice_data.get("poa_name"),
        ice_data.get("poa_phone"),
        ice_data.get("notes"),
    )
    if existing.success and existing.data:
        db_manager.execute_update(
            """
            UPDATE ice_profile SET
                profile_name = ?, profile_dob = ?, medical_conditions = ?,
                medical_dnr = ?, emergency_proxy_name = ?, medical_proxy_phone = ?,
                poa_name = ?, poa_phone = ?, notes = ?
            WHERE user_id = ?
            """,
            params + (user_id,),
        )
    else:
        db_manager.execute_update(
            """
            INSERT INTO ice_profile
            (user_id, profile_name, profile_dob, medical_conditions, medical_dnr,
             emergency_proxy_name, medical_proxy_phone, poa_name, poa_phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id,) + params,
        )
    logger.debug("  Loaded 1 ICE profile")


def load_conditions_data(db_path: str, user_id: str):
    """Load medical conditions from JSON into SQLite database."""
    medical_data = load_json_file("medical.json")
    conditions = medical_data.get("conditions", [])

    db_manager = get_database_manager(db_path)

    for condition in conditions:
        query = """
            INSERT OR REPLACE INTO conditions 
            (user_id, condition_name, diagnosis_date, notes)
            VALUES (?, ?, ?, ?)
        """
        params = (
            user_id,
            condition.get("condition"),
            condition.get("diagnosis_date"),
            condition.get("notes"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d conditions" % len(conditions))


def load_calendar_events_data(db_path: str, user_id: str):
    """Load calendar events from JSON into SQLite database."""
    calendar_data = load_json_file("calendar.json")
    events = calendar_data.get("calendar_events", [])

    db_manager = get_database_manager(db_path)

    for event_data in events:
        # Handle dynamic date placeholders
        start_time = event_data.get("start_time")
        end_time = event_data.get("end_time")

        # Replace date placeholders with actual dates
        today = datetime.now().date()

        if start_time and start_time.startswith("TODAY_"):
            time_part = start_time.replace("TODAY_", "")
            start_time = f"{today}T{time_part}"
        elif start_time and start_time.startswith("TOMORROW_"):
            time_part = start_time.replace("TOMORROW_", "")
            tomorrow = today + timedelta(days=1)
            start_time = f"{tomorrow}T{time_part}"
        elif start_time and start_time.startswith("PLUS_2_DAYS_"):
            time_part = start_time.replace("PLUS_2_DAYS_", "")
            plus_2 = today + timedelta(days=2)
            start_time = f"{plus_2}T{time_part}"
        elif start_time and start_time.startswith("PLUS_3_DAYS_"):
            time_part = start_time.replace("PLUS_3_DAYS_", "")
            plus_3 = today + timedelta(days=3)
            start_time = f"{plus_3}T{time_part}"
        elif start_time and start_time.startswith("PLUS_4_DAYS_"):
            time_part = start_time.replace("PLUS_4_DAYS_", "")
            plus_4 = today + timedelta(days=4)
            start_time = f"{plus_4}T{time_part}"
        elif start_time and start_time.startswith("PLUS_5_DAYS_"):
            time_part = start_time.replace("PLUS_5_DAYS_", "")
            plus_5 = today + timedelta(days=5)
            start_time = f"{plus_5}T{time_part}"

        if end_time and end_time.startswith("TODAY_"):
            time_part = end_time.replace("TODAY_", "")
            end_time = f"{today}T{time_part}"
        elif end_time and end_time.startswith("TOMORROW_"):
            time_part = end_time.replace("TOMORROW_", "")
            tomorrow = today + timedelta(days=1)
            end_time = f"{tomorrow}T{time_part}"
        elif end_time and end_time.startswith("PLUS_2_DAYS_"):
            time_part = end_time.replace("PLUS_2_DAYS_", "")
            plus_2 = today + timedelta(days=2)
            end_time = f"{plus_2}T{time_part}"
        elif end_time and end_time.startswith("PLUS_3_DAYS_"):
            time_part = end_time.replace("PLUS_3_DAYS_", "")
            plus_3 = today + timedelta(days=3)
            end_time = f"{plus_3}T{time_part}"
        elif end_time and end_time.startswith("PLUS_4_DAYS_"):
            time_part = end_time.replace("PLUS_4_DAYS_", "")
            plus_4 = today + timedelta(days=4)
            end_time = f"{plus_4}T{time_part}"
        elif end_time and end_time.startswith("PLUS_5_DAYS_"):
            time_part = end_time.replace("PLUS_5_DAYS_", "")
            plus_5 = today + timedelta(days=5)
            end_time = f"{plus_5}T{time_part}"

        query = """
            INSERT OR REPLACE INTO calendar_events 
            (id, user_id, title, description, start_time, end_time, location, driver_name, driver_contact_id, pickup_time, leave_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event_data.get("id"),
            user_id,
            event_data.get("title"),
            event_data.get("description"),
            start_time,
            end_time,
            event_data.get("location"),
            event_data.get("driver_name"),
            event_data.get("driver_contact_id"),
            event_data.get("pickup_time"),
            event_data.get("leave_time"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d calendar events" % len(events))


def load_user_locations_data(db_path: str, user_id: str):
    """Load user designated locations from JSON into SQLite database."""
    family_data = load_json_file("family.json")
    locations = family_data.get("named_places")

    db_manager = get_database_manager(db_path)

    for location in locations:
        # Parse GPS coordinates
        gps_lat = None
        gps_lng = None
        if location.get("gps"):
            gps_parts = location["gps"].split(",")
            if len(gps_parts) == 2:
                gps_lat = float(gps_parts[0])
                gps_lng = float(gps_parts[1])

        query = """
            INSERT OR REPLACE INTO named_places
            (location_id, location_name, gps_latitude, gps_longitude, radius_metres)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            location.get("location_id"),
            location.get("location_name"),
            gps_lat,
            gps_lng,
            location.get("radius_metres", 150),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d named places" % len(locations))


def load_location_checkins_data(db_path: str, user_id: str):
    """Load location check-ins from JSON. Uses family_member_id."""
    family_data = load_json_file("family.json")
    checkins = family_data.get("location_checkins", [])

    db_manager = get_database_manager(db_path)

    now = datetime.now().isoformat()
    for checkin in checkins:
        query = """
            INSERT INTO location_checkins 
            (user_id, family_member_id, timestamp, latitude, longitude, location_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            user_id,
            checkin.get("family_member_id"),
            now,
            checkin.get("latitude"),
            checkin.get("longitude"),
            checkin.get("location_name"),
            checkin.get("notes"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d location check-ins" % len(checkins))


def load_demo_settings_from_json_into_db(db_path, user_id):
    """Load user display settings from default_display_settings.json into SQLite database."""
    try:
        from apps.kiosk.settings import DisplaySettings
    except ImportError:
        from apps.kiosk.settings import DisplaySettings
    default_settings = (
        DisplaySettings.default()
    )  # single source: demo/demo_data/default_display_settings.json

    db_manager = get_database_manager(db_path)

    # Serialize default settings to JSON strings
    font_sizes_json = json.dumps(default_settings.font_sizes)
    colors_json = json.dumps({k: list(v) for k, v in default_settings.colors.items()})
    spacing_json = json.dumps(default_settings.spacing)
    touch_targets_json = json.dumps(default_settings.touch_targets)
    clock_padding_json = json.dumps(default_settings.clock_padding)
    main_padding_json = json.dumps(default_settings.main_padding)
    clock_bg_json = json.dumps(list(default_settings.clock_background_color))
    med_bg_json = json.dumps(list(default_settings.med_background_color))
    events_bg_json = json.dumps(list(default_settings.events_background_color))
    contacts_bg_json = json.dumps(list(default_settings.contacts_background_color))
    medical_bg_json = json.dumps(list(default_settings.medical_background_color))
    calendar_bg_json = json.dumps(list(default_settings.calendar_background_color))
    nav_bg_json = json.dumps(list(default_settings.nav_background_color))
    navigation_buttons_json = json.dumps(default_settings.navigation_buttons)
    borders_json = json.dumps(default_settings.borders)

    query = """
        INSERT OR REPLACE INTO user_display_settings 
        (user_id, font_sizes, colors, spacing, touch_targets, window_width, window_height,
         window_left, window_top, clock_icon_size, clock_icon_height, clock_text_height,
         clock_day_height, clock_time_height, clock_date_height, clock_spacing, clock_padding, main_padding,
         home_layout, clock_proportion, todo_proportion, med_events_split, navigation_height, button_flat_style,
         clock_background_color, med_background_color, events_background_color,
         contacts_background_color, medical_background_color, calendar_background_color, nav_background_color,
         clock_orientation, med_orientation, events_orientation, bottom_section_orientation,
         high_contrast, large_text, reduced_motion, navigation_buttons, borders)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        user_id,
        font_sizes_json,
        colors_json,
        spacing_json,
        touch_targets_json,
        default_settings.window_width,
        default_settings.window_height,
        default_settings.window_left,
        default_settings.window_top,
        default_settings.clock_icon_size,
        default_settings.clock_icon_height,
        default_settings.clock_text_height,
        default_settings.clock_day_height,
        default_settings.clock_time_height,
        default_settings.clock_date_height,
        default_settings.clock_spacing,
        clock_padding_json,
        main_padding_json,
        default_settings.home_layout,
        default_settings.clock_proportion,
        default_settings.todo_proportion,
        default_settings.med_events_split,
        default_settings.navigation_height,
        int(bool(default_settings.button_flat_style)),
        clock_bg_json,
        med_bg_json,
        events_bg_json,
        contacts_bg_json,
        medical_bg_json,
        calendar_bg_json,
        nav_bg_json,
        default_settings.clock_orientation,
        default_settings.med_orientation,
        default_settings.events_orientation,
        default_settings.bottom_section_orientation,
        int(bool(default_settings.high_contrast)),
        int(bool(default_settings.large_text)),
        int(bool(default_settings.reduced_motion)),
        navigation_buttons_json,
        borders_json,
    )

    result = db_manager.execute_update(query, params)
    if not result.success:
        raise RuntimeError(f"Failed to load display settings: {result.error}")
    logger.debug("  Loaded 1 display settings")


def demo_main(user_id, db_path=None):
    """Load all JSON demo data into the database. Run via: python -m apps.server seed (or pass db_path)."""
    logger.debug("Loading demo data into database...")
    if db_path is None:
        db_path = get_database_path()

    # get_database_manager (used by all load_* below) creates DB and schema when missing
    # Schema must already exist (main.py creates it when demo mode and DB missing)

    try:
        # Ensure demo user exists (ice_profile FK)
        get_database_manager(db_path).execute_update(
            "INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,)
        )
        # Load all JSON data into database
        load_demo_contacts_from_json_into_db(db_path, user_id=user_id)
        load_demo_family_members_from_json_into_db(db_path, user_id=user_id)
        load_demo_medication_groups_from_json_into_db(db_path, user_id=user_id)
        load_demo_medications_data_from_json_to_db(db_path, user_id=user_id)
        load_allergies_data(db_path, user_id=user_id)
        load_conditions_data(db_path, user_id=user_id)
        load_demo_ice_profile_data(db_path, user_id=user_id)
        load_calendar_events_data(db_path, user_id=user_id)
        load_user_locations_data(db_path, user_id=user_id)
        load_location_checkins_data(
            db_path, user_id=user_id
        )  # there should potentially be data from the webapp checkin
        load_demo_settings_from_json_into_db(db_path, user_id=user_id)

        logger.info("Demo data loaded successfully!")
        return True

    except Exception as e:
        logger.error("Error loading demo data: %s", e)
        import traceback

        traceback.print_exc()
        return False
