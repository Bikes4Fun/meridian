"""
Sendbird Chat: config, DB lookups, and Platform API helpers.
Routes live in api.py; this module has no routes.
Uses Platform API (issue session token). No Sendbird SDK dependency; requests only.
"""
import json
import os
import time
import urllib.parse

import requests
from flask import current_app


# --- Config (env) ---

def get_sendbird_app_id() -> str:
    """Application ID from Sendbird Dashboard (Settings → Application → General). Case-sensitive."""
    return (os.getenv("SENDBIRD_APP_ID") or "").strip()


def get_sendbird_api_token() -> str:
    """Master or secondary API token for Platform API (Dashboard → API tokens)."""
    return (os.getenv("SENDBIRD_API_TOKEN") or "").strip()


def is_configured() -> bool:
    """True if both app id and api token are set."""
    return bool(get_sendbird_app_id() and get_sendbird_api_token())


def get_sendbird_user_id_from_env(app_user_id: str) -> str:
    """
    Map app user_id to Sendbird user_id via SENDBIRD_USER_ID_MAP JSON env.
    Returns empty string if no mapping.
    """
    raw = (os.getenv("SENDBIRD_USER_ID_MAP") or "").strip()
    if not raw:
        return ""
    try:
        m = json.loads(raw)
        return (m.get(app_user_id) or "").strip() if isinstance(m, dict) else ""
    except (TypeError, ValueError):
        return ""


def get_sendbird_default_recipient_id_from_env() -> str:
    """Sendbird user_id of the default 1:1 recipient from SENDBIRD_DEFAULT_RECIPIENT_ID."""
    return (os.getenv("SENDBIRD_DEFAULT_RECIPIENT_ID") or "").strip()


# --- DB lookups ---

def get_sendbird_user_id_for_app_user(app_user_id: str) -> str:
    """Look up Sendbird user_id from users.sendbird_user_id. Returns empty if not in DB or no container."""
    container = current_app.config.get("container")
    if not container:
        return ""
    db = container.get_database_manager()
    r = db.execute_query("SELECT sendbird_user_id FROM users WHERE id = ?", (app_user_id,))
    if not r.success or not r.data:
        return ""
    return (r.data[0].get("sendbird_user_id") or "").strip()


def get_default_recipient(family_circle_id: str) -> tuple:
    """First contact in this family with sendbird_user_id. Returns (sendbird_user_id, display_name) or ('', '')."""
    container = current_app.config.get("container")
    if not container:
        return "", ""
    db = container.get_database_manager()
    r = db.execute_query(
        "SELECT sendbird_user_id, display_name FROM contacts WHERE family_circle_id = ? AND sendbird_user_id IS NOT NULL AND sendbird_user_id != '' LIMIT 1",
        (family_circle_id,),
    )
    if not r.success or not r.data:
        return "", ""
    row = r.data[0]
    return (row.get("sendbird_user_id") or "").strip(), (row.get("display_name") or "Family").strip()


# --- Platform API helpers ---

def _api_url() -> str:
    """Base URL for Sendbird Platform API: https://api-{app_id}.sendbird.com/v3"""
    app_id = get_sendbird_app_id()
    if not app_id:
        return ""
    return "https://api-{}.sendbird.com/v3".format(app_id)


def _headers() -> dict:
    """Headers for Platform API: Api-Token and Content-Type."""
    return {
        "Api-Token": get_sendbird_api_token(),
        "Content-Type": "application/json; charset=utf8",
    }


def _issue_session_token(user_id: str) -> tuple[bool, str, str]:
    """
    Issue a session token for user_id. Returns (success, token_or_error, error_detail).
    Token valid 7 days (Sendbird default if expires_at not sent).
    """
    base = _api_url()
    if not base:
        return False, "", "Sendbird not configured"
    expires_at = int((time.time() + 7 * 24 * 3600) * 1000)
    payload = {"expires_at": expires_at}
    encoded_user_id = urllib.parse.quote(user_id, safe="")
    r = requests.post(
        base + "/users/" + encoded_user_id + "/token",
        headers=_headers(),
        json=payload,
        timeout=10,
    )
    if r.status_code != 200:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        msg = body.get("message", r.text)
        return False, "", msg
    data = r.json()
    token = (data.get("token") or data.get("session_token") or "").strip()
    if not token:
        return False, "", "No token in response"
    return True, token, ""
