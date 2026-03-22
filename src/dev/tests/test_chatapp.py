"""
Chatapp API tests: /auth token verification, /api/chat/config, /api/chat/token.
Requires chatapp routes registered (webapp + chatapp dist dirs exist).
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from apps.server.api import _create_chat_entry_token, create_server_app
from dev.tests.conftest import CARE_RECIPIENT_USER_ID, FAMILY_CIRCLE_ID, TEST_USER_ID

API_HEADERS = {"X-User-Id": TEST_USER_ID, "X-Family-Circle-Id": FAMILY_CIRCLE_ID}


def _has_chatapp_routes(app):
    """Check if chatapp routes are registered (e.g. /auth exists)."""
    rules = [r.rule for r in app.url_map.iter_rules()]
    return "/auth" in rules


@pytest.fixture
def api_client_with_chatapp(populated_test_db):
    """API client with chatapp routes when dist dirs exist."""
    db_path = populated_test_db.config.path
    app = create_server_app(db_path=db_path)
    return app.test_client()


@pytest.mark.integration
def test_auth_requires_token(api_client_with_chatapp):
    """GET /auth with no token → 400."""
    if not _has_chatapp_routes(api_client_with_chatapp.application):
        pytest.skip("chatapp routes not registered (dist dirs missing)")
    r = api_client_with_chatapp.get("/auth")
    assert r.status_code == 400
    assert "token" in r.get_json().get("error", "").lower()


@pytest.mark.integration
def test_auth_rejects_invalid_token(api_client_with_chatapp):
    """GET /auth?token=invalid → 403."""
    if not _has_chatapp_routes(api_client_with_chatapp.application):
        pytest.skip("chatapp routes not registered (dist dirs missing)")
    r = api_client_with_chatapp.get("/auth?token=not.a.valid.token")
    assert r.status_code == 403
    assert (
        "invalid" in r.get_json().get("error", "").lower()
        or "expired" in r.get_json().get("error", "").lower()
    )


@pytest.mark.integration
def test_auth_accepts_valid_token_redirects(api_client_with_chatapp):
    """GET /auth?token=<valid> → 302 redirect to chat."""
    if not _has_chatapp_routes(api_client_with_chatapp.application):
        pytest.skip("chatapp routes not registered (dist dirs missing)")
    app = api_client_with_chatapp.application
    token = _create_chat_entry_token(
        app.secret_key,
        TEST_USER_ID,
        FAMILY_CIRCLE_ID,
        sendbird_user_id="",
        display_name="",
    )
    r = api_client_with_chatapp.get("/auth?token=" + token)
    assert r.status_code == 302
    assert "chatapp" in r.location or "chat" in r.location or r.location.endswith("/")
