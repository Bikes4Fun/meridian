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

import json
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
    get_chatapp_port,
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
            start_port, port,
        )
    os.environ["PORT"] = str(port)

    logger.info("Starting API server...")
    server_thread = threading.Thread(target=run_server, kwargs={"port": port}, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    api_url = "http://127.0.0.1:%s" % port
    logger.info("API/DB: %s", api_url)
    return api_url


def _start_local_webapp_server(api_url, logger):
    """Build and serve webapp. Abort if build fails."""
    host = get_server_host()
    webapp_port = find_available_port(host, get_webapp_port())
    webapp_url = "http://127.0.0.1:%s" % webapp_port
    os.environ["WEBAPP_URL"] = webapp_url

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
        logger.error("Webapp build failed (%s). Run 'node build.js' in apps/webapp/web_server.", e)
        sys.exit(1)

    if not os.path.exists(webapp_dist):
        logger.error("Webapp dist/ missing after build. Aborting.")
        sys.exit(1)

    from http.server import HTTPServer, SimpleHTTPRequestHandler

    class WebappHandler(SimpleHTTPRequestHandler):
        def __init__(self, request, client_address, server):
            super().__init__(request, client_address, server, directory=webapp_dist)

    webapp_server = HTTPServer(("127.0.0.1", webapp_port), WebappHandler)
    threading.Thread(target=webapp_server.serve_forever, daemon=True).start()
    logger.info("Webapp: %s", webapp_url)
    return webapp_url


def _start_local_chatapp_server(api_url, logger):
    """Build and run chatapp API server (Flask). Serves UI + chat API (config, token, recipient)."""
    host = get_server_host()
    chatapp_port = find_available_port(host, get_chatapp_port())
    chatapp_url = "http://127.0.0.1:%s" % chatapp_port
    os.environ["CHATAPP_URL"] = chatapp_url

    src_dir = os.path.dirname(os.path.abspath(__file__))
    chatapp_server_dir = os.path.join(src_dir, "apps", "chatapp", "chat_server")
    chatapp_dist = os.path.join(chatapp_server_dir, "dist")

    try:
        subprocess.run(
            ["node", "build.js"],
            cwd=chatapp_server_dir,
            env={**os.environ, "API_URL": ""},
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error("Chatapp build failed (%s). Run 'node build.js' in apps/chatapp/chat_server.", e)
        sys.exit(1)

    if not os.path.exists(chatapp_dist):
        logger.error("Chatapp dist/ missing after build. Aborting.")
        sys.exit(1)

    from apps.chatapp.api import run_chatapp_server

    threading.Thread(
        target=run_chatapp_server,
        kwargs={"port": chatapp_port, "static_dir": chatapp_dist},
        daemon=True,
    ).start()
    logger.info("Chatapp: %s", chatapp_url)
    time.sleep(0.3)
    from apps.chatapp.verify_api import verify_api
    # verify_api(chatapp_url, logger)
    return chatapp_url


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

    if use_local:
        db_path = get_database_path()
        from dev.demo.seed import ensure_local_database
        ensure_local_database(db_path)
        logger.info("Local DB validated.")
        from dev.demo.seed import refresh_demo_checkins
        refresh_demo_checkins(db_path)
        logger.info("Database loaded")
        api_url = _start_local_api_server(logger)
        webapp_url = _start_local_webapp_server(api_url, logger)
        chatapp_url = _start_local_chatapp_server(api_url, logger)
        os.environ["CORS_ORIGIN"] = ",".join([webapp_url, chatapp_url])
    elif is_railway_reachable():
        api_url = get_railway_api_url()
        logger.info("API/DB: %s", api_url)
        webapp_url = os.environ.get("WEBAPP_URL", "").strip()
        chatapp_url = os.environ.get("CHATAPP_URL", "").strip()
        logger.info("Webapp: %s", webapp_url or "(set WEBAPP_URL)")
        logger.info("Chatapp: %s", chatapp_url or "(set CHATAPP_URL for chat redirect)")
    else:
        logger.warning(
            "Railway API not reachable (%s), using local database.",
            get_railway_api_url(),
        )
        api_url = _start_local_api_server(logger)

    logger.info("Starting Meridian ...")
    try:
        app = create_app(
            api_url=api_url,
            kiosk_user_id=KIOSK_USER_ID,
            family_circle_id=PATIENT_FAMILY_CIRCLE_ID,
        )
        logger.info("Meridian Kiosk, server, and webapp created successfully, starting...")
        app.run()
    except Exception as e:
        logger.error("Meridian startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
