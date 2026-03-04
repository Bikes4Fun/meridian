"""
Shared test fixtures and utilities for Meridian tests.
"""
import os
import tempfile
import pytest
from pathlib import Path

# Add src directory to path for new package layout
import sys
src_dir = Path(__file__).parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from shared.config import ConfigManager, DatabaseConfig
from apps.server.database import DatabaseManager
from apps.kiosk.api_client import LocalTimeService
from apps.server.services.contact import ContactService
from apps.server.services.calendar import CalendarService
from apps.server.services.medical import MedicationService
from apps.server.services.emergency import EmergencyService


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_db_config(temp_db_path):
    """Create a database config for testing."""
    return DatabaseConfig(
        path=temp_db_path,
        create_if_missing=True,
        backup_enabled=False,
        connection_timeout=5
    )


@pytest.fixture
def test_db_manager(test_db_config):
    """Create a database manager with test database."""
    manager = DatabaseManager(test_db_config)
    result = manager.create_database_schema()
    if not result.success:
        raise RuntimeError("Schema creation failed: %s" % result.error)
    return manager


# Single source of truth for API and integration tests. Align with apps.server.schema.
FAMILY_CIRCLE_ID = 'test_family'
TEST_USER_ID = 'test_user'
CARE_RECIPIENT_USER_ID = 'care_recipient_user'
OTHER_FAMILY_ID = 'other_family'
OTHER_FAMILY_USER_ID = 'other_family_user'
PATH_TRAVERSAL_USER_ID = 'path_traversal_user'
REF_DATE = '2024-01-15'


@pytest.fixture
def family_circle_id():
    return FAMILY_CIRCLE_ID


@pytest.fixture
def sample_contacts_data():
    """Sample contact data for testing. Use primary_emergency/secondary_emergency for emergency-contacts filter."""
    return [
        {
            'id': 'contact1',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'John Doe',
            'phone': '555-0100',
            'email': 'john@example.com',
            'relationship': 'Son',
            'emergency_priority': 'primary_emergency'
        },
        {
            'id': 'contact2',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'Jane Doe',
            'phone': '555-0101',
            'email': 'jane@example.com',
            'relationship': 'Daughter',
            'emergency_priority': 'secondary_emergency'
        },
        {
            'id': 'contact3',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'Dr. Smith',
            'phone': '555-0200',
            'relationship': 'Doctor',
            'emergency_priority': 'normal'
        }
    ]


@pytest.fixture
def populated_test_db(test_db_manager, sample_contacts_data):
    """Create a test database with sample data. Matches schema: users, user_family_circle, care_recipients, medications by care_recipient_user_id."""
    db = test_db_manager
    db.execute_update("INSERT OR IGNORE INTO family_circles (id) VALUES (?)", (FAMILY_CIRCLE_ID,))
    db.execute_update("INSERT OR IGNORE INTO family_circles (id) VALUES (?)", (OTHER_FAMILY_ID,))

    db.execute_update(
        "INSERT OR REPLACE INTO users (id, display_name) VALUES (?, ?)",
        (TEST_USER_ID, 'Test User'),
    )
    db.execute_update(
        "INSERT OR REPLACE INTO users (id, display_name) VALUES (?, ?)",
        (CARE_RECIPIENT_USER_ID, 'Care Recipient'),
    )
    db.execute_update(
        "INSERT OR REPLACE INTO users (id, display_name) VALUES (?, ?)",
        (OTHER_FAMILY_USER_ID, 'Other User'),
    )
    db.execute_update(
        "INSERT OR REPLACE INTO users (id, display_name, photo_filename) VALUES (?, ?, ?)",
        (PATH_TRAVERSAL_USER_ID, 'Path Traversal Test', '../evil'),
    )
    db.execute_update(
        "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
        (TEST_USER_ID, FAMILY_CIRCLE_ID),
    )
    db.execute_update(
        "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
        (PATH_TRAVERSAL_USER_ID, FAMILY_CIRCLE_ID),
    )
    db.execute_update(
        "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
        (CARE_RECIPIENT_USER_ID, FAMILY_CIRCLE_ID),
    )
    db.execute_update(
        "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
        (OTHER_FAMILY_USER_ID, OTHER_FAMILY_ID),
    )

    db.execute_update(
        "INSERT OR REPLACE INTO care_recipients (family_circle_id, care_recipient_user_id, name) VALUES (?, ?, ?)",
        (FAMILY_CIRCLE_ID, CARE_RECIPIENT_USER_ID, 'Care Recipient'),
    )

    for contact in sample_contacts_data:
        db.execute_update(
            """INSERT INTO contacts (id, family_circle_id, display_name, phone, email, relationship, emergency_priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                contact['id'],
                contact['user_id'],
                contact['display_name'],
                contact.get('phone'),
                contact.get('email'),
                contact.get('relationship'),
                contact.get('emergency_priority'),
            ),
        )

    times = [
        ('Morning', '06:00:00'),
        ('Afternoon', '12:00:00'),
        ('Evening', '18:00:00'),
        ('prn', None),
    ]
    for name, time_val in times:
        db.execute_update(
            "INSERT INTO medication_times (family_circle_id, name, time) VALUES (?, ?, ?)",
            (FAMILY_CIRCLE_ID, name, time_val),
        )
    r = db.execute_query("SELECT id FROM medication_times WHERE family_circle_id = ? ORDER BY name", (FAMILY_CIRCLE_ID,))
    time_ids = [row['id'] for row in r.data] if r.success and r.data else []
    morning_id = time_ids[0] if len(time_ids) > 0 else 1
    afternoon_id = time_ids[1] if len(time_ids) > 1 else 2

    db.execute_update(
        """INSERT INTO medications (care_recipient_user_id, name, dosage, frequency, taken_today)
           VALUES (?, ?, ?, ?, 0)""",
        (CARE_RECIPIENT_USER_ID, 'Lisinopril', '10 mg', 'daily'),
    )
    db.execute_update(
        """INSERT INTO medications (care_recipient_user_id, name, dosage, frequency, taken_today)
           VALUES (?, ?, ?, ?, 0)""",
        (CARE_RECIPIENT_USER_ID, 'Metformin', '500 mg', 'twice daily'),
    )
    med_r = db.execute_query("SELECT id FROM medications WHERE care_recipient_user_id = ? ORDER BY name", (CARE_RECIPIENT_USER_ID,))
    med_ids = [row['id'] for row in med_r.data] if med_r.success and med_r.data else [1, 2]
    db.execute_update("INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (?, ?)", (med_ids[0], morning_id))
    db.execute_update("INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (?, ?)", (med_ids[1], afternoon_id))

    for event_id, fc_id, title, start, end, location in [
        ('event1', FAMILY_CIRCLE_ID, 'Doctor Appointment', REF_DATE + ' 10:00:00', REF_DATE + ' 11:00:00', 'Clinic'),
        ('event2', FAMILY_CIRCLE_ID, 'Family Visit', REF_DATE + ' 14:00:00', REF_DATE + ' 16:00:00', 'Home'),
    ]:
        db.execute_update(
            """INSERT INTO calendar_events (id, family_circle_id, title, start_time, end_time, location)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, fc_id, title, start, end, location),
        )

    return test_db_manager


@pytest.fixture
def time_service():
    """Create a TimeService instance (LocalTimeService from api_client)."""
    return LocalTimeService(base_url="http://test", user_id="test")


@pytest.fixture
def contact_service(populated_test_db):
    """Create a ContactService with test database."""
    return ContactService(populated_test_db)


@pytest.fixture
def calendar_service(populated_test_db):
    """Create a CalendarService with test database."""
    return CalendarService(populated_test_db)


@pytest.fixture
def medication_service(populated_test_db):
    """Create a MedicationService with test database."""
    return MedicationService(populated_test_db)


@pytest.fixture
def emergency_service(populated_test_db, contact_service):
    """Create an EmergencyService with test database and contact service."""
    return EmergencyService(populated_test_db, contact_service)


@pytest.fixture
def config_manager():
    """Create a ConfigManager instance."""
    return ConfigManager()
