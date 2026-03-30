"""Integration tests for POST .../care-recipient-photo."""

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

_MIN_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


@pytest.mark.integration
def test_care_recipient_photo_upload_persists_and_serves(
    populated_test_db, monkeypatch, tmp_path
):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    app = create_server_app(db_path=populated_test_db.config.path)
    client = app.test_client()
    url = f"/api/family_circles/{FAMILY_CIRCLE_ID}/care-recipient-photo"
    r = client.post(
        url,
        headers=API_HEADERS,
        data={
            "care_recipient_user_id": CARE_RECIPIENT_USER_ID,
            "photo": (io.BytesIO(_MIN_JPEG), "care.jpg"),
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    j = r.get_json()
    assert j.get("data", {}).get("photo_filename")
    fn = j["data"]["photo_filename"]
    assert (tmp_path / fn).is_file()

    r2 = client.get(
        f"/api/users/{CARE_RECIPIENT_USER_ID}/photo",
        headers=API_HEADERS,
    )
    assert r2.status_code == 200
    assert r2.data[:2] == b"\xff\xd8"


@pytest.mark.integration
def test_care_recipient_photo_upload_rejects_wrong_recipient(api_client):
    url = f"/api/family_circles/{FAMILY_CIRCLE_ID}/care-recipient-photo"
    r = api_client.post(
        url,
        headers=API_HEADERS,
        data={
            "care_recipient_user_id": "not_a_care_recipient",
            "photo": (io.BytesIO(_MIN_JPEG), "x.jpg"),
        },
    )
    assert r.status_code == 404
