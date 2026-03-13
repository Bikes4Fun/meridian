"""
Tests for the client/server API (Flask server).
Uses the Flask test client; no running server required.

API auth (from apps.server.api set_user_id / _require_family_access):
- No auth: GET /api/health, POST /api/login, GET /login
- Session only (no headers): /checkin (redirect), /checkin.js (401), GET /api/session (401) — require session user_id + family_circle_id
- Both X-User-Id and X-Family-Circle-Id (or session): all other API routes. Family-scoped routes also require URL family_circle_id == header family.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from apps.server.api import create_server_app
from dev.tests.conftest import (
    CARE_RECIPIENT_USER_ID,
    FAMILY_CIRCLE_ID,
    TEST_USER_ID,
    OTHER_FAMILY_ID,
    OTHER_FAMILY_USER_ID,
    PATH_TRAVERSAL_USER_ID,
)


@pytest.fixture
def api_client(populated_test_db):
    """Flask test client for the API server using populated test DB."""
    db_path = populated_test_db.config.path
    app = create_server_app(db_path=db_path)
    return app.test_client()


API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}

# Every protected API route that requires both X-User-Id and X-Family-Circle-Id (no auth → 401).
# Family-scoped: URL family must match header family (wrong family → 403).
PROTECTED_GET_ROUTES = [
    ("/api/family_circles/%s/calendar/headers", True),
    ("/api/family_circles/%s/calendar/month", True),
    ("/api/family_circles/%s/calendar/date", True),
    ("/api/family_circles/%s/calendar/events", True),
    ("/api/family_circles/%s/medications", True),
    ("/api/family_circles/%s/contacts", True),
    ("/api/family_circles/%s/emergency-contacts", True),
    ("/api/family_circles/%s/medical-summary", True),
    ("/api/family_circles/%s/emergency-profile", True),
    ("/api/family_circles/%s/emergency-profile/pdf", True),
    ("/api/family_circles/%s/family-members", True),
    ("/api/family_circles/%s/named-places", True),
    ("/api/family_circles/%s/checkins", True),
    ("/api/emergency/alert/status", False),
]
# (path_template, is_family_scoped): is_family_scoped means URL has family_circle_id and _require_family_access applies

PROTECTED_POST_PUT_ROUTES = [
    ("/api/emergency/alert", "POST", False, {"json": {"activated": False}}),
    (
        "/api/family_circles/%s/emergency-profile",
        "PUT",
        True,
        {"json": {"user_id": CARE_RECIPIENT_USER_ID, "name": "x"}},
    ),
]
# (path_template, method, is_family_scoped, kwargs for request)


# --- Security: no secrets in client-facing responses ---
@pytest.mark.integration
def test_api_health_no_headers(api_client):
    """Health is public; no headers required."""
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


@pytest.mark.integration
def test_public_responses_do_not_expose_secrets(api_client):
    """Assert server code (api_health, api_login) never puts secrets in response bodies.
    We hit the real routes via api_client and check the actual response body."""
    r = api_client.get("/api/health")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "SECRET" not in body.upper()
    assert "dev-secret" not in body.lower()

    r = api_client.post("/api/login", json={"user_id": "u", "family_circle_id": "fc"})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "SECRET" not in body.upper()
    assert "dev-secret" not in body.lower()
    assert "password" not in body.lower() and "api_key" not in body.lower()


@pytest.mark.integration
def test_api_login_accessible_without_auth(api_client):
    """POST /api/login is public entry point."""
    r = api_client.post("/api/login", json={"user_id": "u", "family_circle_id": "fc"})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


# --- Security: user types URL without being logged in → 401 (no access to protected pages) ---
@pytest.mark.integration
def test_api_requires_both_headers(api_client):
    """No headers (e.g. user typed URL, not logged in) → 401; both headers → 200."""
    path = "/api/family_circles/%s/calendar/headers" % FAMILY_CIRCLE_ID
    r = api_client.get(path)
    assert r.status_code == 401
    r = api_client.get(path, headers={"X-User-Id": "u1"})
    assert r.status_code == 401
    r = api_client.get(path, headers=API_HEADERS)
    assert r.status_code == 200


@pytest.mark.integration
def test_typed_url_without_login_protected_routes_401(api_client):
    """User physically typing a protected URL with no session/headers cannot access data."""
    protected_paths = [
        "/api/family_circles/%s/calendar/headers" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/emergency-profile" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/family-members" % FAMILY_CIRCLE_ID,
    ]
    for path in protected_paths:
        r = api_client.get(path)
        assert r.status_code == 401, "path %s should require auth" % path


@pytest.mark.integration
def test_unauthenticated_user_cannot_access_any_protected_endpoint(api_client):
    """Someone who is NOT logged in (no session, no X-User-Id/X-Family-Circle-Id), regardless of family, gets 401."""
    paths_any_family = [
        "/api/family_circles/%s/contacts" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/contacts" % OTHER_FAMILY_ID,
        "/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/emergency-profile" % FAMILY_CIRCLE_ID,
    ]
    for path in paths_any_family:
        r = api_client.get(path)
        assert r.status_code == 401, "unauthenticated must not access %s" % path


@pytest.mark.integration
def test_every_protected_get_route_requires_both_headers_401(api_client):
    """Every protected GET route returns 401 with no X-User-Id / X-Family-Circle-Id."""
    for template, is_family_scoped in PROTECTED_GET_ROUTES:
        if "%s" in template:
            path = template % FAMILY_CIRCLE_ID
        else:
            path = template
        if "calendar/events" in path:
            path += "?date=2024-01-15"
        r = api_client.get(path)
        assert r.status_code == 401, "no auth must get 401: %s" % path


@pytest.mark.integration
def test_every_family_scoped_route_rejects_wrong_family_403(api_client):
    """Every family-scoped route returns 403 when authenticated as fam_a but URL is fam_b."""
    for template, is_family_scoped in PROTECTED_GET_ROUTES:
        if not is_family_scoped:
            continue
        path = template % OTHER_FAMILY_ID
        if "calendar/events" in path:
            path += "?date=2024-01-15"
        r = api_client.get(path, headers=API_HEADERS)
        assert r.status_code == 403, "fam_a must not access fam_b: %s" % path


@pytest.mark.integration
def test_every_protected_post_put_route_requires_both_headers_401(api_client):
    """Protected POST/PUT routes return 401 with no X-User-Id / X-Family-Circle-Id."""
    for template, method, is_family_scoped, kwargs in PROTECTED_POST_PUT_ROUTES:
        path = (
            (template % FAMILY_CIRCLE_ID)
            if is_family_scoped and "%s" in template
            else template
        )
        r = api_client.open(path, method=method, **kwargs)
        assert r.status_code == 401, "no auth must get 401: %s %s" % (method, path)


@pytest.mark.integration
def test_api_medications_requires_auth(api_client):
    r = api_client.get("/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID)
    assert r.status_code == 401


@pytest.mark.integration
def test_api_contacts_requires_auth(api_client):
    r = api_client.get("/api/family_circles/%s/contacts" % FAMILY_CIRCLE_ID)
    assert r.status_code == 401


# --- Security: session routes ---
@pytest.mark.integration
def test_checkin_page_redirects_to_login_without_session(api_client):
    r = api_client.get("/checkin")
    assert r.status_code == 302
    assert "login" in r.headers.get("Location", "").lower()


@pytest.mark.integration
def test_checkin_js_401_without_session(api_client):
    r = api_client.get("/checkin.js")
    assert r.status_code == 401


# --- Security: user A (fam_a) cannot access family B (fam_b) data → 403 ---
@pytest.mark.integration
def test_api_cross_family_403(api_client):
    """User authenticated as fam_a cannot access fam_b URLs (typed or otherwise) → 403."""
    r = api_client.get(
        "/api/family_circles/%s/calendar/headers" % OTHER_FAMILY_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 403
    body = r.get_data(as_text=True)
    assert "family" in body.lower() or "mismatch" in body.lower()


@pytest.mark.integration
def test_fam_a_cannot_access_fam_b_data(api_client):
    """Test user is logged in as fam_a (API_HEADERS = FAMILY_CIRCLE_ID). Request fam_b (OTHER_FAMILY_ID) data → 403."""
    fam_b_paths = [
        "/api/family_circles/%s/contacts" % OTHER_FAMILY_ID,
        "/api/family_circles/%s/medications" % OTHER_FAMILY_ID,
        "/api/family_circles/%s/emergency-profile" % OTHER_FAMILY_ID,
    ]
    for path in fam_b_paths:
        r = api_client.get(path, headers=API_HEADERS)
        assert r.status_code == 403, "fam_a must not access fam_b path %s" % path


# --- Security: check-in identity ---
@pytest.mark.integration
def test_checkin_succeeds_when_user_matches(api_client):
    r = api_client.post(
        "/api/family_circles/%s/checkin" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json={"user_id": TEST_USER_ID, "latitude": 37.0, "longitude": -113.0},
    )
    assert r.status_code == 201
    assert r.get_json()["data"]["user_id"] == TEST_USER_ID


@pytest.mark.integration
def test_checkin_forbidden_when_user_differs(api_client):
    r = api_client.post(
        "/api/family_circles/%s/checkin" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json={"user_id": "other_user", "latitude": 37.0, "longitude": -113.0},
    )
    assert r.status_code == 403
    j = r.get_json()
    assert j.get("error") == "cannot check in for another user"


# --- Security: photo user must be in family ---
@pytest.mark.integration
def test_api_photo_404_when_user_not_in_family(api_client):
    r = api_client.get(
        "/api/users/%s/photo" % OTHER_FAMILY_USER_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 404


# --- Security: photo path traversal (api_serve_photo rejects .. and / in filename) ---
@pytest.mark.integration
def test_api_photo_404_path_traversal(api_client):
    """User in family has photo_filename '../evil' in DB; api_serve_photo must reject and return 404."""
    r = api_client.get(
        "/api/users/%s/photo" % PATH_TRAVERSAL_USER_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 404


# --- Infrastructure: one authenticated stack check (CalendarService.get_day_headers contract) ---
@pytest.mark.integration
def test_api_calendar_headers(api_client):
    """Proves Flask + container + DB + auth path; response matches CalendarService.get_day_headers()."""
    r = api_client.get(
        "/api/family_circles/%s/calendar/headers" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert j["data"] == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
