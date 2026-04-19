"""
Infrastructure tests: API health, public endpoints, authenticated stack check.
Uses Flask test client.
"""

import sys
import types
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


def _install_fake_twilio_modules(
    monkeypatch,
    *,
    validate_result=True,
    jwt_value=b"fake-jwt",
    jwt_raises=False,
    include_rest=False,
    fail_second_leg=False,
):
    twilio_mod = types.ModuleType("twilio")
    request_validator_mod = types.ModuleType("twilio.request_validator")
    twiml_mod = types.ModuleType("twilio.twiml")
    voice_response_mod = types.ModuleType("twilio.twiml.voice_response")
    jwt_mod = types.ModuleType("twilio.jwt")
    access_token_mod = types.ModuleType("twilio.jwt.access_token")
    grants_mod = types.ModuleType("twilio.jwt.access_token.grants")

    class FakeRequestValidator:
        def __init__(self, _token):
            pass

        def validate(self, _url, _params, _sig):
            return validate_result

    class FakeDial:
        def __init__(self):
            self.numbers = []

        def number(self, value):
            self.numbers.append(value)

        def conference(self, room, beep="false"):
            self.numbers.append((room, beep))

    class FakeVoiceResponse:
        def __init__(self):
            self.actions = []

        def say(self, text):
            self.actions.append(("say", text))

        def dial(self, caller_id=None):
            d = FakeDial()
            self.actions.append(("dial", caller_id, d))
            return d

        def __str__(self):
            return "<Response/>"

    class FakeVoiceGrant:
        def __init__(self, outgoing_application_sid):
            self.outgoing_application_sid = outgoing_application_sid

    class FakeAccessToken:
        def __init__(self, _account_sid, _api_key_sid, _api_key_secret, identity, ttl):
            self.identity = identity
            self.ttl = ttl
            self.grants = []

        def add_grant(self, grant):
            self.grants.append(grant)

        def to_jwt(self):
            if jwt_raises:
                raise RuntimeError("jwt failed")
            return jwt_value

    request_validator_mod.RequestValidator = FakeRequestValidator
    voice_response_mod.VoiceResponse = FakeVoiceResponse
    access_token_mod.AccessToken = FakeAccessToken
    grants_mod.VoiceGrant = FakeVoiceGrant

    monkeypatch.setitem(sys.modules, "twilio", twilio_mod)
    monkeypatch.setitem(sys.modules, "twilio.request_validator", request_validator_mod)
    monkeypatch.setitem(sys.modules, "twilio.twiml", twiml_mod)
    monkeypatch.setitem(sys.modules, "twilio.twiml.voice_response", voice_response_mod)
    monkeypatch.setitem(sys.modules, "twilio.jwt", jwt_mod)
    monkeypatch.setitem(sys.modules, "twilio.jwt.access_token", access_token_mod)
    monkeypatch.setitem(sys.modules, "twilio.jwt.access_token.grants", grants_mod)
    if include_rest:
        rest_mod = types.ModuleType("twilio.rest")

        class FakeCalls:
            def __init__(self):
                self._count = 0

            def create(self, **_kwargs):
                self._count += 1
                if fail_second_leg and self._count == 2:
                    raise RuntimeError("second leg failed")
                sid = "CA_TO" if self._count == 1 else "CA_FROM"
                return types.SimpleNamespace(sid=sid)

        class FakeClient:
            def __init__(self, _account_sid, _auth_token):
                self.calls = FakeCalls()

        rest_mod.Client = FakeClient
        monkeypatch.setitem(sys.modules, "twilio.rest", rest_mod)


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


@pytest.mark.integration
def test_twilio_voice_token_missing_env_returns_503(api_client, monkeypatch):
    for key in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_API_KEY_SID",
        "TWILIO_API_KEY_SECRET",
        "TWILIO_TWIML_APP_SID",
    ):
        monkeypatch.delenv(key, raising=False)
    r = api_client.get("/api/voice/token", headers=API_HEADERS)
    assert r.status_code == 503
    assert "Kiosk voice not configured" in (r.get_json() or {}).get("error", "")


@pytest.mark.integration
def test_twilio_voice_client_rejects_bad_signature(api_client, monkeypatch):
    _install_fake_twilio_modules(monkeypatch, validate_result=False)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    r = api_client.post(
        "/twilio/voice/client",
        data={"To": "+14155550100", "callerId": "+14155550101"},
        headers={"X-Twilio-Signature": "bad-signature"},
    )
    assert r.status_code == 403


@pytest.mark.integration
def test_twilio_voice_token_success_returns_token_and_caller_id(api_client, monkeypatch):
    _install_fake_twilio_modules(monkeypatch, jwt_value=b"jwt-123")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_API_KEY_SID", "SK123")
    monkeypatch.setenv("TWILIO_API_KEY_SECRET", "secret123")
    monkeypatch.setenv("TWILIO_TWIML_APP_SID", "AP123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+14155550199")
    r = api_client.get("/api/voice/token", headers=API_HEADERS)
    body = r.get_json() or {}
    assert r.status_code == 200
    assert body.get("token") == "jwt-123"
    assert body.get("caller_id") == "+14155550199"


@pytest.mark.integration
def test_twilio_voice_token_handles_jwt_failure(api_client, monkeypatch):
    _install_fake_twilio_modules(monkeypatch, jwt_raises=True)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_API_KEY_SID", "SK123")
    monkeypatch.setenv("TWILIO_API_KEY_SECRET", "secret123")
    monkeypatch.setenv("TWILIO_TWIML_APP_SID", "AP123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+14155550199")
    r = api_client.get("/api/voice/token", headers=API_HEADERS)
    assert r.status_code == 500
    assert (r.get_json() or {}).get("error") == "Could not create voice token"


@pytest.mark.integration
def test_twilio_voice_call_requires_to_phone(api_client, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+14155550199")
    r = api_client.post("/api/voice/call", json={}, headers=API_HEADERS)
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "to phone required"


@pytest.mark.integration
def test_twilio_voice_call_conference_success(api_client, monkeypatch):
    _install_fake_twilio_modules(monkeypatch, include_rest=True)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth123")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+14155550199")
    r = api_client.post(
        "/api/voice/call",
        json={"to": "+14155550100"},
        headers=API_HEADERS,
    )
    body = r.get_json() or {}
    assert r.status_code == 200
    assert body.get("sid") == "CA_TO"
    assert body.get("sid_caller") == "CA_FROM"
    assert body.get("conference")


# @pytest.mark.integration
# def test_0_pollute_alert_state(api_client):
#     """Pollutes state for the default family: activates emergency alert without reset. No teardown.
#     With per-family alert storage, only same-family tests see the leak; name order forces victim after polluter."""
#     api_client.post("/api/emergency/alert", headers=API_HEADERS, json={"activated": True})


# @pytest.mark.integration
# def test_1_alert_isolation_victim(api_client):
#     """Assumes alert is False for the default test family. Fails when run after test_0_pollute_alert_state
#     (demonstrates missing teardown for that family's alert flag)."""
#     r = api_client.get("/api/emergency/alert/status", headers=API_HEADERS)
#     assert r.status_code == 200
#     assert r.get_json()["data"]["activated"] is False, "alert was polluted by prior test"
