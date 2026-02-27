"""
Configuration management for Dementia TV application.
Simple functions to get configuration values from environment variables.

CLIENT/SERVER: Used by both client and server. get_server_url() controls client use of
remote vs container; get_users_database_path() used by server and by client
Do not remove from either deployment.
"""

import os
import socket
from dataclasses import dataclass


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
        "dementia_tv.db",
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


def get_server_url() -> str:
    """Get API server base URL for client. Uses SERVER_URL if set, else http://127.0.0.1:<get_server_port()>."""
    url = (os.getenv("SERVER_URL") or "").strip()
    return url or ("http://127.0.0.1:%s" % get_server_port())


# Backward compatibility - simple ConfigManager wrapper
class ConfigManager:
    """Simple configuration manager for backward compatibility."""

    def get_database_path(self) -> str:
        """Get database path."""
        return get_database_path()

    def get_log_level(self) -> str:
        """Get log level."""
        return get_log_level()
