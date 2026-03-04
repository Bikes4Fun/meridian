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

## API security (auth requirements)

All auth is enforced in `apps.server.api` (`set_user_id`, `_require_family_access`).

**No auth (public):** GET `/api/health`, POST `/api/login`, GET `/login`

**Session only** (no headers; session must have `user_id` + `family_circle_id`): GET `/checkin` (redirect to `/login` if no session), GET `/checkin.js` (401), GET `/api/session` (401)

**Both X-User-Id and X-Family-Circle-Id** (or same from session) required for all other API routes. Family-scoped routes also require the URL `family_circle_id` to match the header (wrong family → 403):

- GET `/api/family_circles/<id>/calendar/headers`, `calendar/month`, `calendar/date`, `calendar/events`
- GET `/api/family_circles/<id>/medications`, `contacts`, `emergency-contacts`, `medical-summary`
- GET `/api/family_circles/<id>/emergency-profile`, `emergency-profile/pdf`
- GET `/api/family_circles/<id>/family-members`, `named-places`, `checkins`
- GET `/api/emergency/alert/status` (no family in URL; still requires both headers)
- POST `/api/emergency/alert`
- GET/PUT `/api/family_circles/<id>/emergency-profile`
- POST `/api/family_circles/<id>/checkin` (body `user_id` must equal `X-User-Id`)
- GET `/api/users/<user_id>/photo` (user must be in same family as `X-Family-Circle-Id`)

Tests in `test_api.py` use `PROTECTED_GET_ROUTES` and `PROTECTED_POST_PUT_ROUTES` to assert every protected route returns 401 without auth and every family-scoped route returns 403 when requesting another family.

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
