

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


def get_log_level() -> str:
    """Get log level from environment or default."""
    return os.getenv("LOG_LEVEL", "INFO")


def get_update_interval() -> float:
    """Get update interval in seconds."""
    return float(os.getenv("UPDATE_INTERVAL", "1.0"))


# Server bind address: single source of truth for host/port (env SERVER_HOST, PORT).
def get_server_host() -> str:
    """Host the API server binds to. Default 0.0.0.0."""
    return os.getenv("SERVER_HOST", "0.0.0.0")


def get_server_port() -> int:
    """Port the API server binds to. Default 8080. Override with PORT."""
    return int(os.getenv("PORT", "8080"))


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
    """Load api_config.json. Used by get_railway_api_url."""
    import json

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get_railway_api_url() -> str:
    """Get Railway API base URL for remote DB. RAILWAY_API_URL env overrides api_config.json."""
    url = (os.getenv("RAILWAY_API_URL") or "").strip()
    if url:
        return url
    cfg = _load_api_config()
    url = (cfg.get("railway_api_url") or "").strip()
    if not url:
        _logger.warning(
            "Railway API URL not configured. Set RAILWAY_API_URL or add railway_api_url to src/shared/api_config.json"
        )
        raise RuntimeError(
            "Railway API URL not configured. Set RAILWAY_API_URL or add railway_api_url to src/shared/api_config.json"
        )
    return url


def is_railway_reachable(timeout: float = 3.0) -> bool:
    """Return True if Railway API /api/health responds successfully."""
    try:
        import urllib.request

        url = get_railway_api_url().rstrip("/") + "/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


# Backward compatibility - simple ConfigManager wrapper
class ConfigManager:
    """Simple configuration manager for backward compatibility."""

    def get_database_path(self) -> str:
        """Get database path."""
        return get_database_path()

    def get_log_level(self) -> str:
        """Get log level."""
        return get_log_level()
