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


def test_api_health(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_api_time(api_client):
    r = api_client.get("/api/time")
    assert r.status_code == 200
    j = r.get_json()
    assert "day_of_week" in j
    assert "am_pm" in j
    assert "time" in j
    assert "month_day" in j
    assert "year" in j


def test_api_calendar_headers(api_client):
    r = api_client.get("/api/calendar/headers")
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)
    assert len(j["data"]) == 7


def test_api_calendar_month(api_client):
    r = api_client.get("/api/calendar/month")
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)


def test_api_calendar_events(api_client):
    r = api_client.get("/api/calendar/events?date=15")
    assert r.status_code == 200
    j = r.get_json()
    assert "data" in j
    assert isinstance(j["data"], list)


def test_api_user_id_header(api_client):
    r = api_client.get("/api/health", headers={"X-User-Id": "test_family_1"})
    assert r.status_code == 200
