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
    from src.apps.server.database import DatabaseManager
    from src.shared.config import DatabaseConfig, get_database_path
except ImportError:
    from apps.server.database import DatabaseManager
    from shared.config import DatabaseConfig, get_database_path


DEMO_FAMILY_CIRCLE_ID = "F00000"
DEMO_USER_ID = "fm_001"  # Primary demo user; matches main.DEMO_USER_ID


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


def load_demo_contacts_from_json_into_db(db_manager, family_circle_id: str):
    """Load contacts from JSON. Can have photo_filename and notes for contact card."""
    contacts_data = load_json_file("contacts.json")
    contacts = contacts_data.get("contacts", [])

    for contact in contacts:
        query = """
            INSERT OR REPLACE INTO contacts 
            (id, family_circle_id, display_name, phone, email, birthday, relationship, priority, photo_filename, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            contact.get("id"),
            family_circle_id,
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


def load_demo_family_circles_from_json_into_db(db_manager):
    """Load family circles from family.json."""
    data = load_json_file("family.json")
    circles = data.get("family_circles", [])
    if not circles and data.get("family_circle_id"):
        circles = [{"id": data.get("family_circle_id")}]
    if not circles:
        raise ValueError("family.json missing family_circles or family_circle_id")
    for circle in circles:
        fc_id = circle.get("id") if isinstance(circle, dict) else circle
        if fc_id:
            db_manager.execute_update(
                "INSERT OR IGNORE INTO family_circles (id) VALUES (?)",
                (fc_id,),
            )
    logger.debug("  Loaded %d family circles" % len(circles))


def _link_users_to_family_circles(db_manager, users):
    """Link users to family circles via user_family_circle."""
    for user in users:
        uid = user.get("id")
        fc_id = user.get("family_circle_id")
        if fc_id:
            db_manager.execute_update(
                "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
                (uid, fc_id),
            )


def load_demo_users_from_json_into_db(db_manager):
    """Load all users from users.json."""
    users = load_json_file("users.json")

    for user in users:
        uid = user.get("id")
        photo_filename = user.get("photo_filename")
        db_manager.execute_update(
            """
            INSERT OR REPLACE INTO users (id, display_name, photo_filename, family_circle_id)
            VALUES (?, ?, ?, ?)
            """,
            (uid, user.get("display_name"), photo_filename, user.get("family_circle_id")),
        )

    _link_users_to_family_circles(db_manager, users)
    logger.debug("  Loaded %d users" % len(users))

def load_demo_medication_times_from_json_into_db(db_manager, family_circle_id: str):
    """Load medication times from medical.json."""
    data = load_json_file("medical.json").get("medication_times", {})
    for name, td in data.items():
        t = td.get("time") if isinstance(td, dict) else None
        if t == "null":
            t = None
        db_manager.execute_update(
            "INSERT OR REPLACE INTO medication_times (family_circle_id, name, time) VALUES (?, ?, ?)",
            (family_circle_id, name, t),
        )
    logger.debug("  Loaded medication times for family %s", family_circle_id)


def load_demo_medications_data_from_json_to_db(db_manager, family_circle_id: str, care_recipient_user_id: str):
    """Load medications from JSON into SQLite database. care_recipient_user_id = person meds belong to."""
    medical_data = load_json_file("medical.json")
    medications = medical_data.get("medications", [])

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        for med in medications:
            cursor.execute(
                """
                INSERT OR REPLACE INTO medications
                (care_recipient_user_id, name, dosage, frequency, notes, max_daily, last_taken, taken_today)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    care_recipient_user_id,
                    med.get("name"),
                    med.get("dosage"),
                    med.get("frequency"),
                    med.get("notes"),
                    med.get("max_daily"),
                    med.get("last_taken"),
                    med.get("taken"),
                ),
            )
            medication_id = cursor.lastrowid

            for time_name in med.get("medication_times", []):
                cursor.execute(
                    "SELECT id FROM medication_times WHERE family_circle_id = ? AND name = ?",
                    (family_circle_id, time_name),
                )
                row = cursor.fetchone()
                if row:
                    cursor.execute(
                        "INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (?, ?)",
                        (medication_id, row[0]),
                    )

        conn.commit()
    logger.debug("  Loaded %d medications" % len(medications))


def load_allergies_data(db_manager, care_recipient_user_id: str):
    """Load allergies from JSON into SQLite database. care_recipient_user_id = person allergies belong to."""
    medical_data = load_json_file("medical.json")
    allergies = medical_data.get("allergies", [])

    for allergy in allergies:
        query = """
            INSERT OR REPLACE INTO allergies (care_recipient_user_id, allergen)
            VALUES (?, ?)
        """
        db_manager.execute_update(query, (care_recipient_user_id, allergy.get("allergen")))
    logger.debug("  Loaded %d allergies" % len(allergies))


def load_demo_care_recipient_data(db_manager, family_circle_id: str):
    """Load care recipient and contact roles (proxy, POA) from care_recipient section. Legal/medical data, not ICE-specific."""
    medical_data = load_json_file("medical.json")
    cr_data = medical_data.get("care_recipient", {})
    if not cr_data:
        return

    care_recipient_user_id = cr_data.get("user_id")
    if not care_recipient_user_id:
        raise ValueError("care_recipient requires user_id")

    profile = cr_data.get("profile") or {}
    medical = cr_data.get("medical") or {}
    emergency = cr_data.get("emergency") or {}
    proxy = emergency.get("proxy") or {}
    name = profile.get("name")
    dob = profile.get("dob")
    medical_dnr = 1 if medical.get("dnr") else 0
    proxy_name = proxy.get("name")
    medical_proxy_phone = cr_data.get("medical_proxy_phone")
    poa_name = cr_data.get("poa_name")
    poa_phone = cr_data.get("poa_phone")
    notes = cr_data.get("notes")

    db_manager.execute_update(
        """
        INSERT OR REPLACE INTO care_recipients (family_circle_id, care_recipient_user_id, name, dob, photo_path, medical_dnr, dnr_document_path, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (family_circle_id, care_recipient_user_id, name, dob, None, medical_dnr, None, notes),
    )

    if proxy_name or medical_proxy_phone:
        cid = f"proxy_{family_circle_id}"
        db_manager.execute_update(
            "INSERT OR REPLACE INTO contacts (id, family_circle_id, display_name, phone) VALUES (?, ?, ?, ?)",
            (cid, family_circle_id, proxy_name or "", medical_proxy_phone or ""),
        )
        db_manager.execute_update(
            "INSERT OR REPLACE INTO ice_contact_roles (family_circle_id, role, contact_id) VALUES (?, ?, ?)",
            (family_circle_id, "medical_proxy", cid),
        )
    if poa_name or poa_phone:
        cid = f"poa_{family_circle_id}"
        db_manager.execute_update(
            "INSERT OR REPLACE INTO contacts (id, family_circle_id, display_name, phone) VALUES (?, ?, ?, ?)",
            (cid, family_circle_id, poa_name or "", poa_phone or ""),
        )
        db_manager.execute_update(
            "INSERT OR REPLACE INTO ice_contact_roles (family_circle_id, role, contact_id) VALUES (?, ?, ?)",
            (family_circle_id, "poa", cid),
        )
    logger.debug("  Loaded care recipient and contact roles")


def load_conditions_data(db_manager, care_recipient_user_id: str):
    """Load medical conditions from JSON into SQLite database. care_recipient_user_id = person conditions belong to."""
    medical_data = load_json_file("medical.json")
    conditions = medical_data.get("conditions", [])

    for condition in conditions:
        query = """
            INSERT OR REPLACE INTO conditions 
            (care_recipient_user_id, condition_name, diagnosis_date, notes)
            VALUES (?, ?, ?, ?)
        """
        params = (
            care_recipient_user_id,
            condition.get("condition"),
            condition.get("diagnosis_date"),
            condition.get("notes"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d conditions" % len(conditions))


def load_calendar_events_data(db_manager, family_circle_id: str):
    """Load calendar events from JSON into SQLite database."""
    calendar_data = load_json_file("calendar.json")
    events = calendar_data.get("calendar_events", [])

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
            (id, family_circle_id, title, description, start_time, end_time, location, driver_name, driver_contact_id, pickup_time, leave_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event_data.get("id"),
            family_circle_id,
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


def load_user_locations_data(db_manager, family_circle_id: str):
    """Load named places from JSON into SQLite database."""
    family_data = load_json_file("family.json")
    locations = family_data.get("named_places") or []

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
            (location_id, family_circle_id, location_name, gps_latitude, gps_longitude, radius_metres)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            location.get("location_id"),
            family_circle_id,
            location.get("location_name"),
            gps_lat,
            gps_lng,
            location.get("radius_metres", 150),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d named places" % len(locations))


def load_location_checkins_data(db_manager, family_circle_id: str):
    """Load location check-ins from JSON into location_checkins table."""
    family_data = load_json_file("family.json")
    checkins = family_data.get("location_checkins", [])

    now = datetime.now().isoformat()
    for checkin in checkins:
        uid = checkin.get("user_id")
        if not uid:
            raise ValueError("location_checkins entry missing user_id")
        query = """
            INSERT INTO location_checkins
            (family_circle_id, user_id, timestamp, latitude, longitude, location_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            family_circle_id,
            uid,
            now,
            checkin.get("latitude"),
            checkin.get("longitude"),
            checkin.get("location_name"),
            checkin.get("notes"),
        )
        db_manager.execute_update(query, params)
    logger.debug("  Loaded %d location check-ins" % len(checkins))


def refresh_demo_checkins(db_path: str) -> None:
    """Refresh demo location check-ins. Logs and continues on failure (e.g. old schema)."""
    try:
        load_location_checkins_data(
            get_database_manager(db_path), family_circle_id=DEMO_FAMILY_CIRCLE_ID
        )
    except Exception as e:
        logger.debug("Demo checkins refresh skipped (old schema?): %s", e)


def ensure_local_database(db_path: str) -> bool:
    """Create schema (adds missing tables). Always seed demo data so DB stays updated."""
    db_config = DatabaseConfig(path=db_path, create_if_missing=True)
    db = DatabaseManager(db_config)
    result = db.create_database_schema()
    if not result.success:
        logger.error("Local database setup failed")
        raise RuntimeError("Local database setup failed")
    data_loaded = demo_main(user_id=DEMO_USER_ID, db_path=db_path)
    if not data_loaded:
        logger.error("Local demo data loading error")
        raise RuntimeError("Local demo data loading error")
    return True


def demo_main(user_id, db_path=None) -> bool:
    """Load all JSON demo data into the database. Run via: python -m apps.server seed (or pass db_path)."""
    logger.debug("Loading demo data into database...")
    if db_path is None:
        db_path = get_database_path()

    # get_database_manager (used by all load_* below) creates DB and schema when missing
    # Schema must already exist (main.py creates it when demo mode and DB missing)

    try:
        db = get_database_manager(db_path)
        # Load all JSON data into database
        load_demo_users_from_json_into_db(db)
        load_demo_family_circles_from_json_into_db(db)
        load_demo_contacts_from_json_into_db(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)
        care_recipient_user_id = load_json_file("medical.json").get("care_recipient", {}).get("user_id")
        if not care_recipient_user_id:
            raise ValueError("medical.json care_recipient must have user_id")
        load_demo_medication_times_from_json_into_db(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)
        load_demo_medications_data_from_json_to_db(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID, care_recipient_user_id=care_recipient_user_id)
        load_allergies_data(db, care_recipient_user_id=care_recipient_user_id)
        load_conditions_data(db, care_recipient_user_id=care_recipient_user_id)
        load_demo_care_recipient_data(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)
        load_calendar_events_data(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)
        load_user_locations_data(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)
        load_location_checkins_data(db, family_circle_id=DEMO_FAMILY_CIRCLE_ID)

        logger.info("Demo data loaded successfully!")
        return True

    except Exception as e:
        logger.error("Error loading demo data: %s", e)
        import traceback

        traceback.print_exc()
        return False
