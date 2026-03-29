import logging
import os
import socket
from dataclasses import dataclass

_logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    path: str
    create_if_missing: bool = True
    backup_enabled: bool = False
    connection_timeout: int = 30


def get_database_path() -> str:
    """Get database path from environment or default. Default is absolute so it works regardless of cwd."""
    default_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "apps",
        "server",
        "meridian_kiosk.db",
    )
    return os.getenv("DATABASE_PATH", default_path)


def get_uploads_dir() -> str:
    """Directory for user photos. Server serves from here; kiosks fetch and cache."""
    path = os.getenv("UPLOADS_DIR", "").strip()
    if path:
        return os.path.abspath(path)
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "dev",
        "demo",
        "data",
        "family_img",
    )


def get_log_level() -> str:
    """Get log level from environment or default."""
    return os.getenv("LOG_LEVEL", "INFO")


def get_update_interval() -> float:
    """Get update interval in seconds."""
    return float(os.getenv("UPDATE_INTERVAL", "1.0"))


# Kiosk display: TV reference (9:16 portrait), dev scale for local testing
# TV mode (KIOSK_TV_MODE=1): full 1080×1920 on second monitor, fullscreen, no scaling.
#   KIOSK_TV_LEFT, KIOSK_TV_TOP = second monitor origin (System Prefs > Displays > Arrange).
#   KIOSK_TV_FULLSCREEN=0 to skip fullscreen (borderless window only).
KIOSK_REFERENCE_WIDTH = 1080
KIOSK_REFERENCE_HEIGHT = 1920


def get_kiosk_dev_scale() -> bool:
    """Dev scale ON = proportional layout for local. OFF = full TV size. TV mode forces OFF."""
    if get_kiosk_tv_mode():
        return False
    val = os.getenv("KIOSK_DEV_SCALE", "1").lower()
    return val in ("1", "true", "yes")


def get_kiosk_dev_height() -> int:
    """Dev window height in px. Override with KIOSK_DEV_HEIGHT."""
    return int(os.getenv("KIOSK_DEV_HEIGHT", "1100"))


def get_kiosk_window_size() -> tuple[int, int]:
    """(width, height) for kiosk Window.size. Preserves 9:16 when dev scale ON."""
    if not get_kiosk_dev_scale():
        return (KIOSK_REFERENCE_WIDTH, KIOSK_REFERENCE_HEIGHT)
    h = get_kiosk_dev_height()
    w = int(KIOSK_REFERENCE_WIDTH * (h / KIOSK_REFERENCE_HEIGHT))
    return (w, h)


def get_kiosk_tv_mode() -> bool:
    """TV mode: full 1080×1920 on target monitor, no dev scaling."""
    val = os.getenv("KIOSK_TV_MODE", "0").lower()
    return val in ("1", "true", "yes")


def get_kiosk_tv_position() -> tuple[int, int]:
    """(left, top) for window when in TV mode. Use for second monitor. 0,0 = primary."""
    left = int(os.getenv("KIOSK_TV_LEFT", "0"))
    top = int(os.getenv("KIOSK_TV_TOP", "0"))
    return (left, top)


def get_kiosk_tv_fullscreen() -> bool:
    """Fullscreen when in TV mode. Set KIOSK_TV_FULLSCREEN=1 to enable."""
    val = os.getenv("KIOSK_TV_FULLSCREEN", "1").lower()
    return val in ("1", "true", "yes")


# Server bind address: single source of truth for host/port (env SERVER_HOST, PORT).
def get_server_host() -> str:
    """Host the API server binds to. Default 0.0.0.0."""
    return os.getenv("SERVER_HOST", "0.0.0.0")


def get_server_port() -> int:
    """Port the API server binds to. Default 8000. Override with PORT."""
    return int(os.getenv("PORT", "8000"))


def get_webapp_port() -> int:
    """Port the webapp static server binds to. Default 3000. Override with WEBAPP_PORT."""
    return int(os.getenv("WEBAPP_PORT", "3000"))


def get_chatapp_port() -> int:
    """Port the chatapp static server binds to. Default 3001. Override with CHATAPP_PORT."""
    return int(os.getenv("CHATAPP_PORT", "3001"))


def find_available_port(host: str, start_port: int, max_tries: int = 20) -> int:
    """Try binding to start_port, start_port+1, ...; return first available port."""
    for offset in range(max_tries):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        "No available port in range %s..%s" % (start_port, start_port + max_tries - 1)
    )


def _load_api_config():
    """Load api_config.json. Used by get_api_base_url."""
    import json

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get_api_base_url() -> str:
    """Single source for the public API base URL (baked into webapp/chatapp/kiosk and used at runtime).

    Precedence:
      1. RAILWAY_API_URL — explicit override
      2. CHATAPP_API_URL — legacy alias for the same override (prefer RAILWAY_API_URL)
      3. RAILWAY_PUBLIC_DOMAIN — set by Railway per deployment
      4. railway_api_url in src/shared/api_config.json
      5. http://127.0.0.1:<PORT> — local all-in-one when nothing else is configured
    """
    for env_var in ("RAILWAY_API_URL", "CHATAPP_API_URL"):
        url = (os.getenv(env_var) or "").strip()
        if url:
            # Normalize env overrides similarly to RAILWAY_PUBLIC_DOMAIN:
            # if no scheme is provided, default to https://.
            if "://" not in url:
                url = f"https://{url}"
            return url.rstrip("/")
    domain = (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if domain:
        if "://" in domain:
            return domain.rstrip("/")
        return f"https://{domain}".rstrip("/")
    cfg = _load_api_config()
    url = (cfg.get("railway_api_url") or "").strip()
    if url:
        if "://" not in url:
            url = f"https://{url}"
        return url.rstrip("/")
    host = get_server_host()
    if host == "0.0.0.0":
        host = "127.0.0.1"
    fallback = f"http://{host}:{get_server_port()}"
    _logger.warning(
        f"No API URL in env or api_config; using local fallback {fallback}"
    )
    return fallback.rstrip("/")


def get_railway_api_url() -> str:
    """Compatibility wrapper for legacy call sites."""
    return get_api_base_url()


# APNs (Apple Push Notifications) for "Where is everyone?"
# Set APNS_AUTH_KEY_PATH, APNS_KEY_ID, APNS_TEAM_ID to enable. APNS_BUNDLE_ID defaults to com.deanna.Meridian.
# APNS_USE_SANDBOX=1 for dev/sandbox, 0 for production.
def get_apns_auth_key_path() -> str:
    """Path to .p8 APNs auth key. Empty = push disabled (stub mode)."""
    return (os.getenv("APNS_AUTH_KEY_PATH") or "").strip()


def get_apns_key_id() -> str:
    return (os.getenv("APNS_KEY_ID") or "").strip()


def get_apns_team_id() -> str:
    return (os.getenv("APNS_TEAM_ID") or "").strip()


def get_apns_bundle_id() -> str:
    return (os.getenv("APNS_BUNDLE_ID") or "com.deanna.Meridian").strip()


def get_apns_use_sandbox() -> bool:
    val = os.getenv("APNS_USE_SANDBOX", "1").lower()
    return val in ("1", "true", "yes")


def is_railway_reachable(timeout: float = 3.0) -> bool:
    """Return True if Railway API /api/health responds successfully."""
    try:
        import urllib.request

        url = get_api_base_url().rstrip("/") + "/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
