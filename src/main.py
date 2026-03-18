"""
Main entry point for the Meridian.
Starts the API server (DB + REST) in a background thread, then runs the pywebview kiosk client.
"""

import os
import sys

# Load .env from repo root if python-dotenv is available (SENDBIRD_APP_ID, etc.)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

# Ensure src is on path for new package layout
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# --fullscreen = TV mode on second monitor (full 1080×1920, no dev scaling)
if "--fullscreen" in sys.argv:
    os.environ["KIOSK_TV_MODE"] = "1"

import json
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

# Kiosk runs as the kiosk user (often care recipient). Webapp user logs in as Dylan (fm_005) to chat with kiosk user.
KIOSK_USER_ID = "fm_care_001"
PATIENT_FAMILY_CIRCLE_ID = "F00000"


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
            start_port,
            port,
        )
    os.environ["PORT"] = str(port)

    logger.info("Starting API server...")
    server_thread = threading.Thread(
        target=run_server, kwargs={"port": port}, daemon=True
    )
    server_thread.start()
    time.sleep(0.5)

    api_url = "http://127.0.0.1:%s" % port
    logger.info("API/DB: %s", api_url)
    return api_url


def main():
    """Start pywebview kiosk. Use Railway API if reachable, else start local server + DB."""
    use_local = "--local" in sys.argv
    railway_reachable = is_railway_reachable()
    using_local_db = use_local or not railway_reachable

    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Intentional: silence connection-pool, Werkzeug, PIL, verbose display/app_factory debug
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("display.widgets").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.app").setLevel(logging.WARNING)
    logging.getLogger("dev.demo.seed").setLevel(logging.INFO)
    logger = logging.getLogger(__name__)

    # using_local_db = where DB comes from (local file or Railway). Drives DB setup + API server.
    # use_local = --local flag; also runs local webapp/chatapp. Railway-unreachable fallback uses local DB but not webapp/chatapp.
    if using_local_db:
        db_path = get_database_path()
        logger.info("Database: local - %s", db_path)
        if not railway_reachable:
            logger.warning(
                "Railway API not reachable (%s), using local database.",
                get_railway_api_url(),
            )
        from dev.demo.seed import (
            ensure_local_database,
            demo_seed_after_server,
            refresh_demo_checkins,
        )

        ensure_local_database(db_path)
        logger.info("Local DB bootstrap complete.")
        if use_local:
            src_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                from build_all import build_webapp, build_chatapp
                build_webapp("", src_dir)
                build_chatapp("", src_dir)
            except Exception as e:
                logger.error("Build failed (%s).", e)
                sys.exit(1)
        api_url = _start_local_api_server(logger)
        if not demo_seed_after_server(api_url, db_path):
            logger.warning("Demo seed after server failed")
        refresh_demo_checkins(db_path)
        logger.info("Database loaded")
    else:
        api_url = get_railway_api_url()
        logger.info("Database: Railway (remote) - %s", api_url)
        webapp_url = os.environ.get("WEBAPP_URL", "").strip()
        chatapp_url = os.environ.get("CHATAPP_URL", "").strip()
        logger.info("Webapp: %s", webapp_url or "(set WEBAPP_URL)")
        logger.info("Chatapp: %s", chatapp_url or "(set CHATAPP_URL for chat redirect)")

    if use_local:
        os.environ["WEBAPP_URL"] = api_url
        os.environ["CHATAPP_URL"] = api_url.rstrip("/")
        os.environ["CORS_ORIGIN"] = api_url
        webapp_url = api_url
        chatapp_url = api_url.rstrip("/") + "/chatapp"
        logger.info("Webapp: %s", webapp_url)
        logger.info("Chatapp: %s", chatapp_url)
    elif not using_local_db:
        pass  # webapp/chatapp from env already logged above
    else:
        _src = os.path.dirname(os.path.abspath(__file__))
        _webapp_dist = os.path.join(_src, "apps", "webapp", "web_server", "dist")
        _chatapp_dist = os.path.join(_src, "apps", "chatapp", "chat_server", "dist")
        if os.path.isdir(_webapp_dist) and os.path.isdir(_chatapp_dist):
            logger.info("[Webapp      ] %s", api_url)
            logger.info("[Chatapp     ] %s/chatapp/", api_url)

    logger.info("Starting Meridian ...")
    try:
        app = create_app(
            api_url=api_url,
            kiosk_user_id=KIOSK_USER_ID,
            family_circle_id=PATIENT_FAMILY_CIRCLE_ID,
        )
        logger.info(
            "Meridian Kiosk, server, and webapp created successfully, starting..."
        )
        if use_local:
            print(f"")
            print(f"POC Chat — Window 1 (Marian):")
            print("  Chatapp URL:", chatapp_url + "/")
            print(f"  F00000")
            print(f"  fm_care_001")
            print(f"  dtzecha")
            print(f"\nWindow 2 (Dylan):")
            print(f"  F00000")
            print(f"  fm_005")
            print(f"  testpatient")
            print(f"")
        app.run()
    except Exception as e:
        logger.error("Meridian startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
