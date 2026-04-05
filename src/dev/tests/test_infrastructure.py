"""
Infrastructure tests: API health, public endpoints, authenticated stack check.
Uses Flask test client.
"""

import sys
import unittest.mock as mock
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from apps.server.api import create_server_app
from dev.tests.conftest import (
    FAMILY_CIRCLE_ID,
    OTHER_FAMILY_USER_ID,
    REF_DATE,
    TEST_USER_ID,
)

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}


@pytest.mark.integration
def test_api_health_no_headers(api_client):
    """Health is public; no headers required."""
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


@pytest.mark.integration
def test_api_login_accessible_without_auth(api_client):
    """POST /api/login is public entry point; body must match user_family_circle."""
    r = api_client.post(
        "/api/login",
        json={"user_id": TEST_USER_ID, "family_circle_id": FAMILY_CIRCLE_ID},
    )
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


@pytest.mark.integration
def test_api_login_forbidden_when_not_in_family(api_client):
    """POST /api/login rejects user_id not linked to family_circle_id."""
    r = api_client.post(
        "/api/login",
        json={"user_id": OTHER_FAMILY_USER_ID, "family_circle_id": FAMILY_CIRCLE_ID},
    )
    assert r.status_code == 403
    assert r.get_json().get("error") == "forbidden"


@pytest.mark.integration
def test_login_rejects_no_body(api_client):
    """POST /api/login with no body → 400 or 415."""
    r = api_client.post("/api/login")
    assert r.status_code in (400, 415)


@pytest.mark.integration
def test_login_rejects_empty_user_id(api_client):
    """POST /api/login with empty user_id → 400."""
    r = api_client.post("/api/login", json={"user_id": "", "family_circle_id": "fc"})
    assert r.status_code == 400


@pytest.mark.integration
def test_login_rejects_empty_family_circle_id(api_client):
    """POST /api/login with empty family_circle_id → 400."""
    r = api_client.post("/api/login", json={"user_id": "u", "family_circle_id": ""})
    assert r.status_code == 400


@pytest.mark.integration
def test_login_rejects_missing_user_id(api_client):
    """POST /api/login without user_id → 400."""
    r = api_client.post("/api/login", json={"family_circle_id": "fc"})
    assert r.status_code == 400


@pytest.mark.integration
def test_login_rejects_missing_family_circle_id(api_client):
    """POST /api/login without family_circle_id → 400."""
    r = api_client.post("/api/login", json={"user_id": "u"})
    assert r.status_code == 400


@pytest.mark.integration
def test_session_cookie_invalid_after_idle(monkeypatch, populated_test_db):
    """Cookie session rejected after MERIDIAN_SESSION_IDLE_SEC without activity."""
    monkeypatch.setenv("MERIDIAN_SESSION_IDLE_SEC", "120")
    db_path = populated_test_db.config.path
    app = create_server_app(db_path=db_path)
    client = app.test_client()
    t0 = 1_700_000_000
    with mock.patch("apps.server.api.time.time", return_value=t0):
        r0 = client.post(
            "/api/login",
            json={"user_id": TEST_USER_ID, "family_circle_id": FAMILY_CIRCLE_ID},
        )
    assert r0.status_code == 200
    with mock.patch("apps.server.api.time.time", return_value=t0 + 5):
        r = client.get("/api/session")
    assert r.status_code == 200
    with mock.patch("apps.server.api.time.time", return_value=t0 + 200):
        r2 = client.get("/api/session")
    assert r2.status_code == 401


@pytest.mark.integration
def test_session_cookie_invalid_after_max_age(monkeypatch, populated_test_db):
    """Cookie session rejected after MERIDIAN_SESSION_MAX_AGE_SEC from login."""
    monkeypatch.setenv("MERIDIAN_SESSION_MAX_AGE_SEC", "300")
    monkeypatch.setenv("MERIDIAN_SESSION_IDLE_SEC", "86400")
    db_path = populated_test_db.config.path
    app = create_server_app(db_path=db_path)
    client = app.test_client()
    t0 = 1_800_000_000
    with mock.patch("apps.server.api.time.time", return_value=t0):
        r0 = client.post(
            "/api/login",
            json={"user_id": TEST_USER_ID, "family_circle_id": FAMILY_CIRCLE_ID},
        )
    assert r0.status_code == 200
    with mock.patch("apps.server.api.time.time", return_value=t0 + 60):
        r = client.get("/api/session")
    assert r.status_code == 200
    with mock.patch("apps.server.api.time.time", return_value=t0 + 400):
        r2 = client.get("/api/session")
    assert r2.status_code == 401


@pytest.mark.integration
def test_happy_path(api_client):
    """Flask + container + DB + auth path works end-to-end."""
    r = api_client.get(
        "/api/family_circles/%s/calendar/events?date=%s" % (FAMILY_CIRCLE_ID, REF_DATE),
        headers=API_HEADERS,
    )
    assert r.status_code == 200
    events = r.get_json()["data"]
    assert len(events) == 2  # conftest seeds exactly 2 events on REF_DATE
    titles = [e["title"] for e in events]
    assert "Doctor Appointment" in titles


# @pytest.mark.integration
# def test_0_pollute_alert_state(api_client):
#     """Pollutes shared state: activates emergency alert without reset. No teardown.
#     Causes test_1_alert_isolation_victim to fail when run after this (name forces order)."""
#     api_client.post("/api/emergency/alert", headers=API_HEADERS, json={"activated": True})


# @pytest.mark.integration
# def test_1_alert_isolation_victim(api_client):
#     """Assumes alert is False. Fails when run after test_0_pollute_alert_state
#     (demonstrates shared state pollution when tests lack proper isolation)."""
#     r = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
#     assert r.status_code == 200
#     assert r.get_json()["data"]["activated"] is False, "alert was polluted by prior test"
