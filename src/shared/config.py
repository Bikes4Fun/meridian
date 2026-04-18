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
KIOSK_WIN_WIDTH = 1824//2
KIOSK_WIN_HEIGHT = 2736//2


def get_kiosk_win_kiosk() -> bool:
    """Windows kiosk layout (e.g. python -m apps.kiosk --win-kiosk)."""
    val = os.getenv("KIOSK_WIN_KIOSK", "0").lower()
    return val in ("1", "true", "yes")


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
    if get_kiosk_win_kiosk():
        return (KIOSK_WIN_WIDTH, KIOSK_WIN_HEIGHT)
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


def get_local_api_host(host: str | None = None) -> str:
    """Resolve the host clients should use for local API access."""
    api_host = host if host is not None else get_server_host()
    if api_host == "0.0.0.0":
        public_host = (os.getenv("SERVER_PUBLIC_HOST") or "").strip()
        if public_host:
            return public_host
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
    return api_host


def get_local_api_base_url(
    host: str | None = None,
    port: int | None = None,
    https_enabled: bool = False,
) -> str:
    """Build local API URL from host/port and optional HTTPS."""
    api_host = get_local_api_host(host)
    api_port = port if port is not None else get_server_port()
    scheme = "https" if https_enabled else "http"
    return f"{scheme}://{api_host}:{api_port}".rstrip("/")


def _meridian_repo_root() -> str:
    """Parent of src/ (directory that contains src/shared/config.py)."""
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def _resolve_ssl_file_path(raw: str) -> str | None:
    """Absolute path if raw exists; relative paths try cwd then repo root."""
    p = (raw or "").strip()
    if not p:
        return None
    p = os.path.expanduser(p)
    candidates: list[str] = []
    if os.path.isabs(p):
        candidates.append(os.path.normpath(p))
    else:
        rel = os.path.normpath(p)
        candidates.append(os.path.normpath(os.path.join(os.getcwd(), rel)))
        candidates.append(os.path.normpath(os.path.join(_meridian_repo_root(), rel)))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def get_meridian_ssl_files() -> tuple[str, str] | None:
    """Local dev HTTPS: (cert, key) paths when MERIDIAN_SSL_CERT and MERIDIAN_SSL_KEY exist as files. Else None."""
    cert_raw = (os.getenv("MERIDIAN_SSL_CERT") or "").strip()
    key_raw = (os.getenv("MERIDIAN_SSL_KEY") or "").strip()
    if not cert_raw or not key_raw:
        return None
    cert = _resolve_ssl_file_path(cert_raw)
    key = _resolve_ssl_file_path(key_raw)
    if not cert or not key:
        _logger.warning(
            f"MERIDIAN_SSL_CERT / MERIDIAN_SSL_KEY set but file not found "
            f"(tried cwd then repo root). cert={cert_raw!r} key={key_raw!r}"
        )
        return None
    return (cert, key)

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

def get_remote_api_base_url() -> str | None:
    """Remote Railway API URL from RAILWAY_API_URL, or None if unset."""
    url = (os.getenv("RAILWAY_API_URL") or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = f"https://{url}"
    return url.rstrip("/")


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

        base_url = get_remote_api_base_url()
        if not base_url:
            return False
        url = f"{base_url}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
