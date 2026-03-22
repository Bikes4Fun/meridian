"""
Infrastructure tests: API health, public endpoints, authenticated stack check.
Uses Flask test client.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from dev.tests.conftest import FAMILY_CIRCLE_ID, REF_DATE, TEST_USER_ID

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}


@pytest.mark.integration
def test_api_health_no_headers(api_client):
    """Health is public; no headers required."""
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


@pytest.mark.integration
def test_api_login_accessible_without_auth(api_client):
    """POST /api/login is public entry point."""
    r = api_client.post("/api/login", json={"user_id": "u", "family_circle_id": "fc"})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


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
