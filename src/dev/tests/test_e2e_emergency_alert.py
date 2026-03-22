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
from dev.tests.conftest import FAMILY_CIRCLE_ID, TEST_USER_ID

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}


@pytest.fixture(autouse=True)
def reset_alert_state(api_client):
    """Reset global alert state after each test."""
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
