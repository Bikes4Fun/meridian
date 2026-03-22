"""
E2E critical path: full pipeline in one test.
Replaces manual verification (med → alert → profile → checkin).
Run: PYTHONPATH=src pytest src/dev/tests/test_e2e_critical_path.py -v
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
)


@pytest.fixture(autouse=True)
def reset_alert_state(api_client):
    """Ensure clean alert state before and after test."""
    api_client.post(
        "/api/emergency/alert",
        headers={"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID},
        json={"activated": False},
    )
    yield
    r = api_client.post(
        "/api/emergency/alert",
        headers={"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID},
        json={"activated": False},
    )
    assert r.status_code == 200, f"Alert teardown failed: {r.status_code}"


API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}

NEW_MED_NAME = "E2E Critical Path Med"
PROFILE_NAME = "E2E Critical Path Profile"


@pytest.mark.integration
def test_full_pipeline_login_med_alert_profile_checkin(api_client):
    """Full pipeline: add med → fetch meds → alert → profile PUT/GET → checkin → get checkins."""
    # 1. Add medication
    r = api_client.post(
        "/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json={
            "name": NEW_MED_NAME,
            "medication_times": ["Evening"],
            "dosage": "5 mg",
            "frequency": "daily",
        },
    )
    assert r.status_code == 201

    # 2. Fetch medications (assert new med present)
    r = api_client.get(
        "/api/family_circles/%s/medications" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 200
    data = r.get_json().get("data") or {}
    timed = data.get("timed_medications") or []
    prn = data.get("prn_medications") or []
    all_names = [m.get("name", "") for m in timed + prn if isinstance(m, dict)]
    assert any(
        NEW_MED_NAME in n for n in all_names
    ), f"Expected med '{NEW_MED_NAME}' in: {all_names}"

    # 3. Trigger alert
    r = api_client.post(
        "/api/emergency/alert",
        headers=API_HEADERS,
        json={"activated": True},
    )
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True

    # 4. Fetch alert status (assert activated)
    r = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.get_json()["data"]["activated"] is True

    # 5. PUT emergency profile
    profile_payload = {
        "user_id": CARE_RECIPIENT_USER_ID,
        "profile": {"name": PROFILE_NAME, "dob": "1950-01-01"},
        "medical": {"dnr": False, "allergies": [], "conditions": "E2E test"},
    }
    r = api_client.put(
        "/api/family_circles/%s/emergency-profile" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json=profile_payload,
    )
    assert r.status_code == 200

    # 6. GET emergency profile (assert data persisted)
    r = api_client.get(
        "/api/family_circles/%s/emergency-profile" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 200
    data = r.get_json().get("data") or {}
    assert (data.get("profile") or {}).get("name") == PROFILE_NAME

    # 7. Create checkin
    r = api_client.post(
        "/api/family_circles/%s/create_checkin" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
        json={"user_id": TEST_USER_ID, "latitude": 37.5, "longitude": -122.4},
    )
    assert r.status_code == 201
    assert r.get_json()["data"]["user_id"] == TEST_USER_ID

    # 8. Get checkins (assert checkin present)
    r = api_client.get(
        "/api/family_circles/%s/get_checkins" % FAMILY_CIRCLE_ID,
        headers=API_HEADERS,
    )
    assert r.status_code == 200
    checkins = r.get_json().get("data") or []
    user_ids = [c.get("user_id") for c in checkins]
    assert TEST_USER_ID in user_ids
