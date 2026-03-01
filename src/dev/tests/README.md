# Testing Guide for Meridian

This directory contains the test suite for the Meridian Python application.

## Setup

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

Or install just the test dependencies:
```bash
pip install pytest pytest-cov pytest-mock
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run tests with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_time_service.py
```

### Run specific test class
```bash
pytest tests/test_time_service.py::TestTimeService
```

### Run specific test function
```bash
pytest tests/test_time_service.py::TestTimeService::test_get_dayof_week
```

### Run only unit tests (fast, no database)
```bash
pytest -m unit
```

### Run only integration tests (requires database)
```bash
pytest -m integration
```

### Run with coverage report
```bash
pytest --cov=apps --cov=shared --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

## Test Structure

- `conftest.py` - Shared fixtures and test utilities
- `test_time_service.py` - Tests for TimeService (unit tests)
- `test_database_manager.py` - Tests for DatabaseManager (unit + integration)
- `test_calendar_service.py` - Tests for CalendarService (unit + integration)
- `test_medication_service.py` - Tests for MedicationService (unit + integration)
- `test_contact_service.py` - Tests for ContactService and EmergencyService (unit + integration)

## Test Markers

Tests are marked with pytest markers:
- `@pytest.mark.unit` - Fast unit tests that don't require database
- `@pytest.mark.integration` - Tests that require database connection
- `@pytest.mark.slow` - Tests that take a long time (not currently used)

## Test Fixtures

Common fixtures available in `conftest.py`:
- `temp_db_path` - Temporary database file path
- `test_db_config` - Database configuration for testing
- `test_db_manager` - DatabaseManager instance with test database
- `populated_test_db` - Database with sample data
- `time_service` - TimeService instance
- `contact_service` - ContactService with test database
- `calendar_service` - CalendarService with test database
- `medication_service` - MedicationService with test database
- `emergency_service` - EmergencyService instance

## Writing New Tests

1. Create a new test file: `test_<service_name>.py`
2. Import pytest and your service
3. Use fixtures from `conftest.py` for database setup
4. Mark tests appropriately (`@pytest.mark.unit` or `@pytest.mark.integration`)
5. Follow the naming convention: `test_<functionality>`

Example:
```python
import pytest
from apps.server.services.my_service import MyService

@pytest.mark.unit
class TestMyService:
    def test_my_function(self, my_service):
        result = my_service.my_function()
        assert result.success is True
```

## Notes

- All tests use temporary databases that are cleaned up automatically
- Integration tests use the `populated_test_db` fixture which includes sample data
- Unit tests should mock external dependencies when possible
- Tests are designed to run independently and in any order
