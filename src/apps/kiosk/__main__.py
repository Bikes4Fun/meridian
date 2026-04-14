"""Entry point for pywebview kiosk. Run: PYTHONPATH=src python -m apps.kiosk

Local dev (default): start Flask API + local DB on this machine, then open pywebview against it.
Remote API: local pywebview only; API + static webapp/chatapp come from deployed Meridian
(--remote-api or MERIDIAN_REMOTE_API=1, with RAILWAY_API_URL / get_api_base_url() / api_config.json).
"""

import logging
import os
import socket
import sys
import threading
import time

# Ensure src is on path
_src_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_src_dir, "..", ".env"))
except ImportError:
    pass

if "--fullscreen" in sys.argv:
    os.environ["KIOSK_TV_MODE"] = "1"
if "--win-kiosk" in sys.argv:
    os.environ["KIOSK_WIN_KIOSK"] = "1"

from shared.config import (
    find_available_port,
    get_api_base_url,
    get_database_path,
    get_log_level,
    get_meridian_ssl_files,
    get_server_host,
    get_server_port,
)
from apps.kiosk.app import create_app

KIOSK_USER_ID = os.environ.get("KIOSK_USER_ID") or "fm_care_001"
FAMILY_CIRCLE_ID = (
    os.environ.get("FAMILY_CIRCLE_ID")
    or os.environ.get("PATIENT_FAMILY_CIRCLE_ID")
    or "F00000"
)


def use_meridian_remote_api_mode() -> bool:
    """True when kiosk should use deployed Meridian (no local Flask on this machine)."""
    if "--remote-api" in sys.argv:
        return True
    v = (os.environ.get("MERIDIAN_REMOTE_API") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def prepare_remote_api_kiosk_session(logger) -> str:
    """Health-check deployed API; return base URL for pywebview. Does not bake local static assets."""
    base = get_api_base_url().rstrip("/")
    try:
        import urllib.request

        url = f"{base}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                logger.debug("Remote API health returned status %s", resp.status)
    except Exception as e:
        logger.debug("Remote API health check failed: %s", e)
    return base


def _start_local_api_server(logger) -> str:
    """Start API server in background. Returns api_url."""
    from apps.server.api import run_server

    host = get_server_host()
    start_port = get_server_port()
    port = find_available_port(host, start_port)
    if port != start_port:
        logger.warning(
            f"Port {start_port} in use, using port {port} instead. Stop any separate "
            "'python -m apps.server' so web app and TV use the same server."
        )
    os.environ["PORT"] = str(port)

    logger.debug("Starting local API server...")
    threading.Thread(target=run_server, kwargs={"port": port}, daemon=True).start()
    time.sleep(0.5)

    api_host = host
    if host == "0.0.0.0":
        public_host = (os.getenv("SERVER_PUBLIC_HOST") or "").strip()
        if public_host:
            api_host = public_host
        else:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    api_host = s.getsockname()[0]
            except OSError:
                api_host = "127.0.0.1"

    scheme = "https" if get_meridian_ssl_files() else "http"
    return f"{scheme}://{api_host}:{port}"


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.app").setLevel(logging.WARNING)
    logging.getLogger("pywebview").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.api_client").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.location").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.safe_query_manager").setLevel(
        logging.WARNING
    )
    logging.getLogger("dev.demo.seed").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    if "SENDBIRD_SSL_VERIFY" not in os.environ:
        os.environ["SENDBIRD_SSL_VERIFY"] = "0"

    if use_meridian_remote_api_mode():
        api_url = prepare_remote_api_kiosk_session(logger)
    else:
        logger.info("Database: local - %s", get_database_path())
        api_url = _start_local_api_server(logger)

    logger.debug("Starting Meridian Kiosk (pywebview)...")
    app = create_app(
        api_url=api_url,
        kiosk_user_id=KIOSK_USER_ID,
        family_circle_id=FAMILY_CIRCLE_ID,
    )
    app.run()


if __name__ == "__main__":
    main()
    sys.exit(0)
