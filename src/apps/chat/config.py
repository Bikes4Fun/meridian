"""
Sendbird configuration from environment.
Used only by apps/chat; not shared with the rest of the app.
Users must already exist in Sendbird; we map app user_id to Sendbird user_id and issue a session token only.
"""
import json
import os


def get_sendbird_app_id() -> str:
    """Application ID from Sendbird Dashboard (Settings → Application → General). Case-sensitive."""
    return (os.getenv("SENDBIRD_APP_ID") or "").strip()


def get_sendbird_api_token() -> str:
    """Master or secondary API token for Platform API (Dashboard → API tokens)."""
    return (os.getenv("SENDBIRD_API_TOKEN") or "").strip()


def is_configured() -> bool:
    """True if both app id and api token are set."""
    return bool(get_sendbird_app_id() and get_sendbird_api_token())


def get_sendbird_user_id(app_user_id: str) -> str:
    """
    Map our app user_id (e.g. kiosk fm_001) to the existing Sendbird user_id (phone, email, or username in Sendbird).
    Uses SENDBIRD_USER_ID_MAP JSON env: {"fm_001": "sendbird_id_for_patient", ...}.
    Returns empty string if no mapping (do not create users; user must exist in Sendbird).
    """
    raw = (os.getenv("SENDBIRD_USER_ID_MAP") or "").strip()
    if not raw:
        return ""
    try:
        m = json.loads(raw)
        return (m.get(app_user_id) or "").strip() if isinstance(m, dict) else ""
    except (TypeError, ValueError):
        return ""


def get_sendbird_default_recipient_id() -> str:
    """
    Sendbird user_id of the default recipient for 1:1 chat (e.g. daughter).
    Set SENDBIRD_DEFAULT_RECIPIENT_ID to the Sendbird user_id they already have.
    """
    return (os.getenv("SENDBIRD_DEFAULT_RECIPIENT_ID") or "").strip()
