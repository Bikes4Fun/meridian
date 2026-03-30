"""
Smoke tests for GET .../emergency-profile/pdf (auth + PDF bytes).
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from dev.tests.conftest import CARE_RECIPIENT_USER_ID, FAMILY_CIRCLE_ID, TEST_USER_ID

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}

PDF_PATH = f"/api/family_circles/{FAMILY_CIRCLE_ID}/emergency-profile/pdf"


@pytest.mark.integration
def test_emergency_profile_pdf_requires_auth(api_client):
    r = api_client.get(PDF_PATH)
    assert r.status_code == 401


@pytest.mark.integration
def test_emergency_profile_pdf_returns_pdf_bytes(api_client):
    r = api_client.put(
        f"/api/family_circles/{FAMILY_CIRCLE_ID}/emergency-profile",
        headers=API_HEADERS,
        json={
            "user_id": CARE_RECIPIENT_USER_ID,
            "profile": {"name": "PDF Smoke Test", "dob": "1950-06-01"},
            "medical": {"dnr": True, "allergies": [], "conditions": ""},
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = api_client.get(PDF_PATH, headers=API_HEADERS)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert "application/pdf" in (r.headers.get("Content-Type") or "").lower()
    data = r.get_data()
    assert data[:4] == b"%PDF"
    assert b"PDF Smoke Test" in data
    assert b"DNR on file: Yes" in data
    # Seeded medications in populated_test_db (composed into emergency profile)
    assert b"Lisinopril" in data
