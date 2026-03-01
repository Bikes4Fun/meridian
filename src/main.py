"""
Main entry point for the Meridian.
Starts the API server (DB + REST) in a background thread, then runs the Kivy TV client.
"""

import os
import sys

# Ensure src is on path for new package layout
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Before any Kivy import: silence Kivy startup logs (Logger, Factory, Image, Window, GL, etc.)
os.environ["KIVY_LOG_LEVEL"] = "warning"
os.environ["KCFG_KIVY_LOG_LEVEL"] = "warning"
# os.environ["KIVY_NO_CONSOLELOG"] = "2"
if "--local" in sys.argv:
    os.environ["KIVY_NO_ARGS"] = "1"

import logging
import subprocess
import threading
import time
from shared.config import (
    ConfigManager,
    get_database_path,
    get_railway_api_url,
    get_server_host,
    get_server_port,
    get_webapp_port,
    find_available_port,
    is_railway_reachable,
)
from apps.kiosk.app import create_app

# TODO: from auth when not demo
DEMO_MODE = True
DEMO_USER_ID = "fm_001"
DEMO_FAMILY_CIRCLE_ID = "F00000"


def _start_local_api_server(logger):
    """Start API server in background. Returns api_url."""
    from apps.server.api import run_server

    host = get_server_host()
    start_port = get_server_port()
    port = find_available_port(host, start_port)
    if port != start_port:
        logger.warning(
            "Port %s in use, using port %s instead. Stop any separate "
            "'python -m apps.server' so web app and TV use the same server.",
            start_port, port,
        )
    os.environ["PORT"] = str(port)

    logger.info("Starting API server...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    api_url = "http://127.0.0.1:%s" % port
    logger.info("API/DB: %s", api_url)
    return api_url


def _start_local_webapp_server(api_url, logger):
    """Build and serve webapp on webapp port. Sets CORS_ORIGIN."""
    host = get_server_host()
    webapp_port = find_available_port(host, get_webapp_port())
    os.environ["CORS_ORIGIN"] = "http://127.0.0.1:%s" % webapp_port

    src_dir = os.path.dirname(os.path.abspath(__file__))
    webapp_dist = os.path.join(src_dir, "apps", "webapp", "web_server", "dist")
    webapp_server_dir = os.path.join(src_dir, "apps", "webapp", "web_server")

    try:
        subprocess.run(
            ["node", "build.js"],
            cwd=webapp_server_dir,
            env={**os.environ, "API_URL": api_url},
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Webapp build skipped (%s). Use API /checkin for web UI.", e)

    if os.path.exists(webapp_dist):
        from http.server import HTTPServer, SimpleHTTPRequestHandler

        class WebappHandler(SimpleHTTPRequestHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, directory=webapp_dist)

        webapp_server = HTTPServer(("127.0.0.1", webapp_port), WebappHandler)
        webapp_thread = threading.Thread(target=webapp_server.serve_forever, daemon=True)
        webapp_thread.start()
        webapp_url = "http://127.0.0.1:%s" % webapp_port
        logger.info("Webapp: %s", webapp_url)
    else:
        webapp_url = "%s/checkin" % api_url
        logger.info("Webapp: %s (served by API)", webapp_url)
    return webapp_url


def main():
    """Start Kivy TV client. Use Railway API if reachable, else start local server + DB."""
    use_local = "--local" in sys.argv

    config_manager = ConfigManager()
    logging.basicConfig(
        level=getattr(logging, config_manager.get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Intentional: silence connection-pool, Werkzeug, PIL, verbose display/app_factory debug
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("display.widgets").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.app").setLevel(logging.WARNING)
    logging.getLogger("dev.demo.seed").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    if not use_local and is_railway_reachable():
        api_url = get_railway_api_url()
        logger.info("API/DB: %s", api_url)
        logger.info("Webapp: %s/checkin (served by API)", api_url)
    
    elif not is_railway_reachable():
            logger.warning(
                "Railway API not reachable (%s), using local database.",
                get_railway_api_url(),
            )
    elif use_local:
        
        # Build local DB if needed
        db_path = get_database_path()

        from dev.demo.seed import ensure_local_database
        ensure_local_database(db_path)
        logger.info("Local DB validated.")

        from dev.demo.seed import refresh_demo_checkins
        refresh_demo_checkins(db_path)
        logger.info("Database loaded")

        api_url = _start_local_api_server(logger)
        webapp_url = _start_local_webapp_server(api_url, logger)

    logger.info("Starting Meridian ...")
    try:
        auth = (
            {"user_id": DEMO_USER_ID, "family_circle_id": DEMO_FAMILY_CIRCLE_ID}
            if use_local
            else {}
        )
        app = create_app(config_manager, api_url=api_url, **auth)
        logger.info("Meridian Kiosk, server, and webapp created successfully, starting...")
        app.run()
    except Exception as e:
        logger.error("Meridian startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
