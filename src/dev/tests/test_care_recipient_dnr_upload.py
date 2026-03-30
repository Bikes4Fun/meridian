"""Integration tests for POLST/DNR document upload and GET."""

import io
import sys
from pathlib import Path

import pytest

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from dev.tests.conftest import (  # noqa: E402
    CARE_RECIPIENT_USER_ID,
    FAMILY_CIRCLE_ID,
    TEST_USER_ID,
)
from apps.server.api import create_server_app  # noqa: E402

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}

_MIN_PDF = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.mark.integration
def test_care_recipient_dnr_upload_persists_and_serves(
    populated_test_db, monkeypatch, tmp_path
):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    app = create_server_app(db_path=populated_test_db.config.path)
    client = app.test_client()
    post_url = f"/api/family_circles/{FAMILY_CIRCLE_ID}/care-recipient-dnr-document"
    r = client.post(
        post_url,
        headers=API_HEADERS,
        data={
            "care_recipient_user_id": CARE_RECIPIENT_USER_ID,
            "document": (io.BytesIO(_MIN_PDF), "orders.pdf"),
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.get_json()
    assert j.get("data", {}).get("dnr_document_path")

    get_url = (
        f"/api/family_circles/{FAMILY_CIRCLE_ID}/care-recipients/"
        f"{CARE_RECIPIENT_USER_ID}/dnr-document"
    )
    r2 = client.get(get_url, headers=API_HEADERS)
    assert r2.status_code == 200
    assert r2.data[:4] == b"%PDF"
    assert "pdf" in (r2.headers.get("Content-Type") or "").lower()


@pytest.mark.integration
def test_care_recipient_dnr_upload_rejects_wrong_recipient(api_client):
    url = f"/api/family_circles/{FAMILY_CIRCLE_ID}/care-recipient-dnr-document"
    r = api_client.post(
        url,
        headers=API_HEADERS,
        data={
            "care_recipient_user_id": "not_a_care_recipient",
            "document": (io.BytesIO(_MIN_PDF), "x.pdf"),
        },
    )
    assert r.status_code == 404
