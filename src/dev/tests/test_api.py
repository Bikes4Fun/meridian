"""
Tests for the client/server API (Flask server).
Uses the Flask test client; no running server required.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from apps.server.api import create_server_app


@pytest.fixture
def api_client(populated_test_db):
    """Flask test client for the API server using populated test DB."""
    db_path = populated_test_db.config.path
    app = create_server_app(db_path=db_path)
    return app.test_client()


# user_id = who is requesting; family_circle_id = which family's data (matches conftest FAMILY_CIRCLE_ID).
API_HEADERS = {"X-User-Id": "test_user", "X-Family-Circle-Id": "test_family"}


def test_api_health(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_api_calendar_headers(api_client):
    r = api_client.get("/api/family_circles/test_family/calendar/headers", headers=API_HEADERS)
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)
    assert len(j["data"]) == 7


def test_api_calendar_month(api_client):
    r = api_client.get("/api/family_circles/test_family/calendar/month", headers=API_HEADERS)
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)


def test_api_calendar_events(api_client):
    r = api_client.get("/api/family_circles/test_family/calendar/events?date=15", headers=API_HEADERS)
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)


def test_api_requires_both_headers(api_client):
    r = api_client.get("/api/family_circles/test_family/calendar/headers")
    assert r.status_code == 401
    r = api_client.get("/api/family_circles/test_family/calendar/headers", headers={"X-User-Id": "u1"})
    assert r.status_code == 401
    r = api_client.get("/api/family_circles/test_family/calendar/headers", headers=API_HEADERS)
    assert r.status_code == 200


def test_checkin_succeeds_when_user_matches(api_client):
    """Check-in succeeds when user_id in body matches logged-in user."""
    r = api_client.post(
        "/api/family_circles/test_family/checkin",
        headers=API_HEADERS,
        json={"user_id": "test_user", "latitude": 37.0, "longitude": -113.0},
    )
    assert r.status_code == 201
    assert r.get_json()["data"]["user_id"] == "test_user"


def test_checkin_forbidden_when_user_differs(api_client):
    """Check-in forbidden when user_id in body differs from logged-in user."""
    r = api_client.post(
        "/api/family_circles/test_family/checkin",
        headers=API_HEADERS,
        json={"user_id": "other_user", "latitude": 37.0, "longitude": -113.0},
    )
    assert r.status_code == 403
    assert "cannot check in for another user" in r.get_json()["error"]
