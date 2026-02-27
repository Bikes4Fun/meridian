"""
Shared test fixtures and utilities for Dementia TV tests.
"""
import os
import tempfile
import pytest
import sqlite3
from pathlib import Path

# Add lib directory to path so relative imports work
import sys
lib_dir = Path(__file__).parent.parent / 'lib'
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

# Now we can import using the same relative imports the codebase uses
from config import ConfigManager
from config import DatabaseConfig
from database_management.database_manager import DatabaseManager
from container_services.time_service import TimeService
from container_services.contact_service import ContactService
from container_services.calendar_service import CalendarService
from container_services.medication_service import MedicationService
from container_services.emergency_service import EmergencyService


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
    # Create schema in test database
    schema_path = Path(__file__).parent.parent / 'lib' / 'database_management' / 'schema.sql'
    
    manager = DatabaseManager(test_db_config)
    
    # Create schema
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        with manager.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
    
    return manager


@pytest.fixture
def sample_contacts_data():
    """Sample contact data for testing."""
    return [
        {
            'id': 'contact1',
            'user_id': 'test_user',
            'display_name': 'John Doe',
            'phone': '555-0100',
            'email': 'john@example.com',
            'relationship': 'Son',
            'priority': 'emergency'
        },
        {
            'id': 'contact2',
            'user_id': 'test_user',
            'display_name': 'Jane Doe',
            'phone': '555-0101',
            'email': 'jane@example.com',
            'relationship': 'Daughter',
            'priority': 'emergency'
        },
        {
            'id': 'contact3',
            'user_id': 'test_user',
            'display_name': 'Dr. Smith',
            'phone': '555-0200',
            'relationship': 'Doctor',
            'priority': 'normal'
        }
    ]


@pytest.fixture
def populated_test_db(test_db_manager, sample_contacts_data):
    """Create a test database with sample data."""
    # Insert sample contacts
    for contact in sample_contacts_data:
        query = """
            INSERT INTO contacts (id, user_id, display_name, phone, email, relationship, priority)
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
    
    # Insert medication groups
    groups = [
        ('Morning', '06:00:00', 'Morning'),
        ('Afternoon', '12:00:00', 'Afternoon'),
        ('Evening', '18:00:00', 'Evening'),
        ('PRN', None, 'PRN (As Needed)')
    ]
    for name, time, display in groups:
        query = "INSERT INTO medication_groups (name, time, display_name) VALUES (?, ?, ?)"
        test_db_manager.execute_update(query, (name, time, display))
    
    # Insert sample medications
    meds = [
        ('Lisinopril', '10 mg', 'daily', 'test_user'),
        ('Metformin', '500 mg', 'twice daily', 'test_user')
    ]
    for name, dosage, frequency, user_id in meds:
        query = """
            INSERT INTO medications (name, dosage, frequency, user_id, taken_today)
            VALUES (?, ?, ?, ?, 0)
        """
        result = test_db_manager.execute_update(query, (name, dosage, frequency, user_id))
        # Link to morning group (assuming first medication gets ID 1, second gets ID 2)
    
    # Link medications to groups
    test_db_manager.execute_update(
        "INSERT INTO medication_to_group (medication_id, group_id) VALUES (1, 1)",
        ()
    )
    test_db_manager.execute_update(
        "INSERT INTO medication_to_group (medication_id, group_id) VALUES (2, 2)",
        ()
    )
    
    # Insert sample calendar events
    events = [
        ('event1', 'test_user', 'Doctor Appointment', '2024-01-15 10:00:00', '2024-01-15 11:00:00', 'Clinic'),
        ('event2', 'test_user', 'Family Visit', '2024-01-15 14:00:00', '2024-01-15 16:00:00', 'Home')
    ]
    for event_id, user_id, title, start, end, location in events:
        query = """
            INSERT INTO calendar_events (id, user_id, title, start_time, end_time, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        test_db_manager.execute_update(query, (event_id, user_id, title, start, end, location))
    
    return test_db_manager


@pytest.fixture
def time_service():
    """Create a TimeService instance."""
    return TimeService()


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
