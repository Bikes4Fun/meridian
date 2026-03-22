"""
Chat entry token security: expired, tampered, missing fields.
Tests _create_chat_entry_token and _verify_chat_entry_token from server api.
"""

import base64
import json
import sys
import time
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from apps.server.api import _create_chat_entry_token, _verify_chat_entry_token

SECRET = "test-secret-key"


@pytest.mark.unit
def test_valid_token_verifies():
    """Create token → verify returns payload with user_id, family_circle_id."""
    token = _create_chat_entry_token(
        SECRET, "u1", "fc1", sendbird_user_id="sb1", display_name="Alice"
    )
    payload = _verify_chat_entry_token(SECRET, token)
    assert payload is not None
    assert payload["user_id"] == "u1"
    assert payload["family_circle_id"] == "fc1"
    assert payload.get("sendbird_user_id") == "sb1"
    assert payload.get("display_name") == "Alice"
    assert "exp" in payload


@pytest.mark.unit
def test_expired_token_rejected():
    """Token with exp in the past returns None."""
    payload = {
        "user_id": "u1",
        "family_circle_id": "fc1",
        "exp": int(time.time()) - 60,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        .rstrip(b"=")
        .decode()
    )
    import hmac
    import hashlib

    sig = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    token = payload_b64 + "." + sig
    result = _verify_chat_entry_token(SECRET, token)
    assert result is None


@pytest.mark.unit
def test_tampered_signature_rejected():
    """Token with modified signature returns None."""
    token = _create_chat_entry_token(SECRET, "u1", "fc1")
    parts = token.split(".")
    tampered = parts[0] + ".deadbeef0123456789abcdef0123456789abcdef"
    result = _verify_chat_entry_token(SECRET, tampered)
    assert result is None


@pytest.mark.unit
def test_tampered_payload_rejected():
    """Token with modified payload but reused signature returns None."""
    token = _create_chat_entry_token(SECRET, "u1", "fc1")
    orig_payload_b64, sig = token.split(".")
    payload = {
        "user_id": "attacker",
        "family_circle_id": "fc1",
        "exp": int(time.time()) + 300,
    }
    new_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        .rstrip(b"=")
        .decode()
    )
    tampered_token = new_payload_b64 + "." + sig
    result = _verify_chat_entry_token(SECRET, tampered_token)
    assert result is None


@pytest.mark.unit
def test_missing_exp_rejected():
    """Payload without exp (or exp=0) is treated as expired."""
    payload = {"user_id": "u1", "family_circle_id": "fc1"}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        .rstrip(b"=")
        .decode()
    )
    import hmac
    import hashlib

    sig = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    token = payload_b64 + "." + sig
    result = _verify_chat_entry_token(SECRET, token)
    assert result is None


@pytest.mark.unit
def test_wrong_part_count_rejected():
    """Token with not exactly 2 parts returns None."""
    token = _create_chat_entry_token(SECRET, "u1", "fc1")
    result = _verify_chat_entry_token(SECRET, token + ".extra")
    assert result is None
    result = _verify_chat_entry_token(SECRET, "onlyonepart")
    assert result is None


@pytest.mark.unit
def test_wrong_secret_rejected():
    """Token created with secret A cannot be verified with secret B."""
    token = _create_chat_entry_token("secret-a", "u1", "fc1")
    result = _verify_chat_entry_token("secret-b", token)
    assert result is None
