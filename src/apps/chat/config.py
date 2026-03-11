"""
Sendbird configuration from environment.
Used only by apps/chat; not shared with the rest of the app.
Users must already exist in Sendbird; we do not create them. We only issue session tokens.
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


def get_sendbird_user_id(app_user_id: str) -> str:
    """
    Map our app user_id to Sendbird user id (must already exist in Sendbird).
    Demo: set SENDBIRD_DEMO_APP_USER_ID to our user (e.g. fm_001) and SENDBIRD_DEMO_SENDBIRD_USER_ID
    to the corresponding Sendbird user id. Later replace with DB lookup.
    """
    demo_app = (os.getenv("SENDBIRD_DEMO_APP_USER_ID") or "").strip()
    if demo_app and app_user_id == demo_app:
        return (os.getenv("SENDBIRD_DEMO_SENDBIRD_USER_ID") or "").strip()
    return ""


def get_sendbird_chat_with_user_id(app_user_id: str, family_circle_id: str) -> str:
    """
    Who this user chats with (Sendbird user id of the other party, e.g. daughter).
    Demo: set SENDBIRD_DEMO_CHAT_WITH_ID to that Sendbird user id. Later replace with DB/contact lookup.
    """
    demo_app = (os.getenv("SENDBIRD_DEMO_APP_USER_ID") or "").strip()
    if demo_app and app_user_id == demo_app:
        return (os.getenv("SENDBIRD_DEMO_CHAT_WITH_ID") or "").strip()
    return ""
