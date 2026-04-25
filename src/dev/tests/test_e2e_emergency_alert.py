"""
E2E tests for emergency alert API (activate, deactivate, 401).
Uses Flask test client; no running server required.
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
    OTHER_FAMILY_ID,
    OTHER_FAMILY_USER_ID,
    TEST_USER_ID,
)

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}
OTHER_API_HEADERS = {
    "X-User-Id": OTHER_FAMILY_USER_ID,
    "X-Family-Circle-Id": OTHER_FAMILY_ID,
}

KIOSK_JS_PATH = src_dir / "apps" / "kiosk" / "web" / "kiosk.js"


@pytest.fixture(autouse=True)
def reset_alert_state(api_client):
    """Teardown: clear alert for the default test family (API state is per `family_circle_id`)."""
    yield
    r = api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": False}
    )
    assert r.status_code == 200, f"Alert teardown failed: {r.status_code}"


@pytest.mark.integration
def test_alert_activate_sets_status(api_client):
    """POST activated=True → GET returns true."""
    r = api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": True}
    )
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True

    r = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True


@pytest.mark.integration
def test_alert_deactivate_clears_status(api_client):
    """Activate then deactivate → GET returns false."""
    api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": True}
    )
    r = api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": False}
    )
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is False

    r = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is False


@pytest.mark.integration
def test_alert_status_readable_by_care_recipient_without_manage_perm(api_client):
    """Kiosk uses care-recipient headers; they are not granted emergency_alert.manage in test DB."""
    care_headers = {
        "X-User-Id": CARE_RECIPIENT_USER_ID,
        "X-Family-Circle-Id": FAMILY_CIRCLE_ID,
    }
    api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": True}
    )
    r = api_client.get("/api/emergency/alert/status", headers=care_headers)
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True
    r_post = api_client.post(
        "/api/emergency/alert", headers=care_headers, json={"activated": False}
    )
    assert r_post.status_code == 403


@pytest.mark.integration
def test_alert_status_is_scoped_per_family(api_client):
    """Alert activation in one family does not affect another family."""
    r = api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": True}
    )
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True

    r = api_client.get("/api/emergency/alert/status", headers=OTHER_API_HEADERS)
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is False


@pytest.mark.e2e
def test_kiosk_alert_shortcut_wires_to_activate_alert(api_client):
    """Webapp contract: dashboard shortcut and initKioskAlertShortcut post alert activation (API)."""
    login = api_client.post(
        "/api/login",
        json={"user_id": TEST_USER_ID, "family_circle_id": FAMILY_CIRCLE_ID},
    )
    assert login.status_code == 200

    dashboard = api_client.get("/")
    assert dashboard.status_code == 200
    html = dashboard.get_data(as_text=True)
    assert 'id="kioskAlertShortcutBtn"' in html

    app_js = api_client.get("/src/features/app.js")
    assert app_js.status_code == 200
    js = app_js.get_data(as_text=True)
    assert "function initKioskAlertShortcut()" in js
    assert "meridianApiClient.setEmergencyAlert(true)" in js

    # API-side assertion for the click action target.
    status_before = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
    assert status_before.status_code == 200
    assert status_before.get_json()["data"]["activated"] is False

    activate = api_client.post(
        "/api/emergency/alert", headers=API_HEADERS, json={"activated": True}
    )
    assert activate.status_code == 200
    assert activate.get_json()["data"]["activated"] is True


@pytest.mark.integration
def test_kiosk_js_uses_bridge_for_voice_token():
    """Kiosk web JS should not fetch voice token directly; use pywebview bridge API."""
    js = KIOSK_JS_PATH.read_text(encoding="utf-8")
    assert "fetch('/api/voice/token'" not in js
    assert "pywebview.api.get_voice_token" in js
