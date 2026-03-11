"""
Sendbird configuration from environment.
Used only by apps/chat; not shared with the rest of the app.
"""
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
