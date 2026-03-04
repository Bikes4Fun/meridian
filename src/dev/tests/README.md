# Testing Guide for Meridian

This directory contains the test suite for Meridian.

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

**Canonical command (from repo root):**
```bash
PYTHONPATH=src pytest src/dev/tests
```

### Run with verbose output
```bash
PYTHONPATH=src pytest src/dev/tests -v
```

### Run specific test file
```bash
PYTHONPATH=src pytest src/dev/tests/test_api.py
```

### Run only integration tests (uses database or API)
```bash
PYTHONPATH=src pytest src/dev/tests -m integration
```

### Run with coverage report
```bash
PYTHONPATH=src pytest src/dev/tests --cov=apps --cov=shared --cov-report=html
```

## Test Structure

Security and infrastructure only (no feature-specific tests):

- `conftest.py` - Shared fixtures; fixture data is source of truth (see schema alignment there)
- `test_api.py` - Flask API: no secrets in responses, unauthenticated URL → 401, fam_a cannot access fam_b → 403, check-in identity, photo family check, one stack check (integration)
- `test_database.py` - DatabaseManager: schema, persistence, invalid path (integration)

Out of scope for this suite: `test_time_service.py` is empty (time formatting is not security/infrastructure).

## Test Markers

- `@pytest.mark.integration` - Uses database or API client (all current tests)
- `@pytest.mark.unit` - Reserved; not used
- `@pytest.mark.slow` - Not currently used

## Test Fixtures

Fixtures used (in `conftest.py`): `temp_db_path`, `test_db_config`, `test_db_manager`, `populated_test_db`, `api_client` (in test_api.py)

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
