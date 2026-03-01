"""
Shared test fixtures and utilities for Meridian tests.
"""
import os
import tempfile
import pytest
import sqlite3
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
from apps.server.services.medication import MedicationService
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


FAMILY_CIRCLE_ID = 'test_family'

@pytest.fixture
def sample_contacts_data():
    """Sample contact data for testing."""
    return [
        {
            'id': 'contact1',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'John Doe',
            'phone': '555-0100',
            'email': 'john@example.com',
            'relationship': 'Son',
            'priority': 'emergency'
        },
        {
            'id': 'contact2',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'Jane Doe',
            'phone': '555-0101',
            'email': 'jane@example.com',
            'relationship': 'Daughter',
            'priority': 'emergency'
        },
        {
            'id': 'contact3',
            'user_id': FAMILY_CIRCLE_ID,
            'display_name': 'Dr. Smith',
            'phone': '555-0200',
            'relationship': 'Doctor',
            'priority': 'normal'
        }
    ]


@pytest.fixture
def populated_test_db(test_db_manager, sample_contacts_data):
    """Create a test database with sample data."""
    test_db_manager.execute_update(
        "INSERT OR IGNORE INTO family_circles (id) VALUES (?)",
        (FAMILY_CIRCLE_ID,),
    )
    # Insert sample contacts
    for contact in sample_contacts_data:
        query = """
            INSERT INTO contacts (id, family_circle_id, display_name, phone, email, relationship, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        test_db_manager.execute_update(query, (
            contact['id'],
            contact['user_id'],
            contact['display_name'],
            contact.get('phone'),
            contact.get('email'),  # Use .get() to handle missing email
            contact.get('relationship'),
            contact.get('priority')
        ))
    
    # Insert medication times (family-scoped)
    times = [
        ('Morning', '06:00:00'),
        ('Afternoon', '12:00:00'),
        ('Evening', '18:00:00'),
        ('prn', None),
    ]
    for name, time_val in times:
        query = "INSERT INTO medication_times (family_circle_id, name, time) VALUES (?, ?, ?)"
        test_db_manager.execute_update(query, (FAMILY_CIRCLE_ID, name, time_val))
    # Insert sample medications
    meds = [
        ('Lisinopril', '10 mg', 'daily', FAMILY_CIRCLE_ID),
        ('Metformin', '500 mg', 'twice daily', FAMILY_CIRCLE_ID),
    ]
    for name, dosage, frequency, fc_id in meds:
        query = """
            INSERT INTO medications (name, dosage, frequency, family_circle_id, taken_today)
            VALUES (?, ?, ?, ?, 0)
        """
        test_db_manager.execute_update(query, (name, dosage, frequency, fc_id))
    # Link medications to times (Lisinopril->Morning, Metformin->Afternoon)
    test_db_manager.execute_update(
        "INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (1, 1)", ()
    )
    test_db_manager.execute_update(
        "INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (2, 2)", ()
    )
    
    # Insert sample calendar events
    events = [
        ('event1', FAMILY_CIRCLE_ID, 'Doctor Appointment', '2024-01-15 10:00:00', '2024-01-15 11:00:00', 'Clinic'),
        ('event2', FAMILY_CIRCLE_ID, 'Family Visit', '2024-01-15 14:00:00', '2024-01-15 16:00:00', 'Home')
    ]
    for event_id, fc_id, title, start, end, location in events:
        query = """
            INSERT INTO calendar_events (id, family_circle_id, title, start_time, end_time, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        test_db_manager.execute_update(query, (event_id, fc_id, title, start, end, location))
    
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
def emergency_service(contact_service):
    """Create an EmergencyService with contact service."""
    return EmergencyService(contact_service)


@pytest.fixture
def config_manager():
    """Create a ConfigManager instance."""
    return ConfigManager()
