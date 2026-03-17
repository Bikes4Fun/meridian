"""Entry point for pywebview kiosk. Run: python -m apps.kiosk"""

import os
import sys

# Ensure src is on path
_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_src_dir, "..", ".env"))
except ImportError:
    pass

if "--fullscreen" in sys.argv:
    os.environ["KIOSK_TV_MODE"] = "1"

import logging
import threading
import time

from shared.config import (
    get_log_level,
    get_database_path,
    get_railway_api_url,
    get_server_host,
    get_server_port,
    find_available_port,
    is_railway_reachable,
)
from apps.kiosk.app import create_app

KIOSK_USER_ID = os.environ.get("KIOSK_USER_ID") or "fm_care_001"
FAMILY_CIRCLE_ID = os.environ.get("FAMILY_CIRCLE_ID") or os.environ.get("PATIENT_FAMILY_CIRCLE_ID") or "F00000"


def _start_local_api_server(logger):
    """Start API server in background. Returns api_url."""
    from apps.server.api import run_server

    host = get_server_host()
    start_port = get_server_port()
    port = find_available_port(host, start_port)
    if port != start_port:
        logger.warning(f"Port {start_port} in use, using {port}")
    os.environ["PORT"] = str(port)
    logger.info("Starting API server...")
    threading.Thread(target=run_server, kwargs={"port": port}, daemon=True).start()
    time.sleep(0.5)
    api_url = f"http://127.0.0.1:{port}"
    logger.info(f"API: {api_url}")
    return api_url


def main():
    use_local = "--local" in sys.argv
    railway_reachable = is_railway_reachable()
    using_local_db = use_local or not railway_reachable

    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    if using_local_db:
        db_path = get_database_path()
        logger.info(f"Database: local - {db_path}")
        if not railway_reachable:
            logger.warning("Railway unreachable, using local DB")
        from dev.demo.seed import ensure_local_database, refresh_demo_checkins

        ensure_local_database(db_path)
        refresh_demo_checkins(db_path)
        api_url = _start_local_api_server(logger)
    else:
        api_url = get_railway_api_url()
        logger.info(f"API: {api_url}")
        logger.info("Database: Railway (remote)")
        try:
            import urllib.request
            with urllib.request.urlopen(f"{api_url.rstrip('/')}/api/health", timeout=3) as resp:
                if resp.status == 200:
                    logger.info("Server health: ok")
                else:
                    logger.warning(f"Server health: {resp.status}")
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")

    logger.info("Starting Meridian Kiosk (pywebview)...")
    app = create_app(
        api_url=api_url,
        kiosk_user_id=KIOSK_USER_ID,
        family_circle_id=FAMILY_CIRCLE_ID,
    )
    app.run()


if __name__ == "__main__":
    main()
    sys.exit(0)
