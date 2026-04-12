"""
Security tests for the client/server API (Flask server).
Uses the Flask test client; no running server required.

API auth (from apps.server.api set_user_id / verify_family_membership / _require_family_access):
- No auth: GET /api/health, POST /api/login, GET /login.html
- Session only (no headers): GET /api/session (401) — requires session user_id + family_circle_id
- Both X-User-Id and X-Family-Circle-Id (or session): all other API routes must match a row in user_family_circle; family-scoped routes also require URL family_circle_id == header family.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from dev.tests.conftest import (
    CARE_RECIPIENT_USER_ID,
    FAMILY_CIRCLE_ID,
    TEST_USER_ID,
    OTHER_FAMILY_ID,
    OTHER_FAMILY_USER_ID,
    PATH_TRAVERSAL_USER_ID,
)

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
    (
        "/api/family_circles/%s/care-recipients/"
        + CARE_RECIPIENT_USER_ID
        + "/dnr-document",
        True,
    ),
    ("/api/family_circles/%s/family-members", True),
    ("/api/family_circles/%s/named-places", True),
    ("/api/family_circles/%s/get_checkins", True),
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
    (
        "/api/family_circles/%s/care-recipient-photo",
        "POST",
        True,
        {"data": {}},
    ),
    (
        "/api/family_circles/%s/care-recipient-dnr-document",
        "POST",
        True,
        {"data": {}},
    ),
]
# (path_template, method, is_family_scoped, kwargs for request)


# --- Security: no secrets in client-facing responses ---
@pytest.mark.integration
def test_error_responses_do_not_expose_secret_key(api_client):
    """Auth failures must not leak SECRET_KEY in response body."""
    r = api_client.get("/api/family_circles/x/medications")
    assert r.status_code == 401
    body = r.get_data(as_text=True)
    assert "dev-secret-change-in-production" not in body
    assert "SECRET_KEY" not in body


# --- Security: user types URL without being logged in → 401 (no access to protected pages) ---
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


# --- Security: fake credentials rejected ---
@pytest.mark.integration
def test_fake_credentials_rejected(api_client):
    """Headers with no user_family_circle row are rejected (verify_family_membership)."""
    r = api_client.get(
        "/api/family_circles/FAKEFAMILY/emergency-profile",
        headers={"X-User-Id": "FAKEUSER", "X-Family-Circle-Id": "FAKEFAMILY"},
    )
    assert r.status_code == 403
    assert r.get_json().get("error") == "forbidden"


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


@pytest.mark.integration
def test_real_user_from_other_family_cannot_access_your_family(api_client):
    """A legitimate user authenticated against their own real family
    cannot access a different family's data."""
    other_family_headers = {
        "X-User-Id": OTHER_FAMILY_USER_ID,
        "X-Family-Circle-Id": OTHER_FAMILY_ID,
    }
    protected_paths = [
        "/api/family_circles/%s/emergency-profile" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID,
        "/api/family_circles/%s/contacts" % FAMILY_CIRCLE_ID,
    ]
    for path in protected_paths:
        r = api_client.get(path, headers=other_family_headers)
        assert r.status_code == 403, (
            "real user from other family must not access %s" % path
        )


# --- Security: user must belong to family (not only URL/header family match) ---
@pytest.mark.integration
def test_api_forbidden_when_user_not_member_of_header_family(api_client):
    """403 when X-User-Id is not linked to X-Family-Circle-Id even if URL matches header."""
    headers = {
        "X-User-Id": OTHER_FAMILY_USER_ID,
        "X-Family-Circle-Id": FAMILY_CIRCLE_ID,
    }
    r = api_client.get(
        "/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID,
        headers=headers,
    )
    assert r.status_code == 403
    assert r.get_json().get("error") == "forbidden"


# --- Security: check-in identity ---
@pytest.mark.integration
def test_checkin_succeeds_when_user_matches(api_client):
    r = api_client.post(
        "/api/family_circles/%s/create_checkin" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json={"user_id": TEST_USER_ID, "latitude": 37.0, "longitude": -113.0},
    )
    assert r.status_code == 201
    assert r.get_json()["data"]["user_id"] == TEST_USER_ID


@pytest.mark.integration
def test_checkin_forbidden_when_user_differs(api_client):
    r = api_client.post(
        "/api/family_circles/%s/create_checkin" % FAMILY_CIRCLE_ID,
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


# --- Security: emergency alert requires auth ---
@pytest.mark.integration
def test_alert_status_unauthorized_without_headers(api_client):
    """GET status with no headers → 401."""
    r = api_client.get("/api/emergency/alert/status")
    assert r.status_code == 401


@pytest.mark.integration
def test_alert_activate_unauthorized_without_headers(api_client):
    """POST activate with no headers → 401."""
    r = api_client.post("/api/emergency/alert", json={"activated": True})
    assert r.status_code == 401
