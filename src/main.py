"""
Main entry point for Meridian.
In local mode, starts the API server (DB + REST) in a background thread and runs the pywebview kiosk client.
In Railway/remote mode (with --railway-run), uses a remote Railway API (no local API server thread).

Build webapp + chatapp static files (see build_webapp / build_chatapp).
Replaces node build.js / build_all.js - no Node.js dependency.
API_URL empty string = same-origin (served from same server as API).
"""

import os

# Load .env from repo root if python-dotenv is available (SENDBIRD_APP_ID, etc.)
# TODO: if this is not used by everything then it should only exist in the section it is used by
try:
    from dotenv import load_dotenv

    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


# --- FUTURE contents of apps/webapp/build_webapp.py --- #
def build_webapp(logger, api_url: str, src_dir: str):
    import os
    import shutil

    client = os.path.join(src_dir, "apps", "webapp", "web_client")
    dist = os.path.join(src_dir, "apps", "webapp", "web_server", "dist")
    os.makedirs(dist, exist_ok=True)
    for filename in (
        "login.html",
        "index.html",
        "app.js",
        "events.js",
        "medications.js",
    ):
        src_path = os.path.join(client, filename)
        dst_path = os.path.join(dist, filename)
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content.replace("__API_URL__", api_url))
    if os.path.isfile(os.path.join(client, "style.css")):
        shutil.copy2(os.path.join(client, "style.css"), os.path.join(dist, "style.css"))
    font_src = os.path.join(src_dir, "shared", "fonts", "Atkinson_Hyperlegible")
    font_dst = os.path.join(dist, "fonts")
    if os.path.isdir(font_src):
        os.makedirs(font_dst, exist_ok=True)
        for f in (
            "AtkinsonHyperlegible-Regular.ttf",
            "AtkinsonHyperlegible-Bold.ttf",
            "AtkinsonHyperlegible-Italic.ttf",
            "AtkinsonHyperlegible-BoldItalic.ttf",
        ):
            if os.path.isfile(os.path.join(font_src, f)):
                shutil.copy2(os.path.join(font_src, f), os.path.join(font_dst, f))
    logger.debug("Webapp built: login.html, index.html, app.js, events.js, style.css")


# --- FUTURE contents of apps/chatapp/build_chatapp.py --- #
def build_chatapp(logger, api_url: str, src_dir: str):
    import os
    import shutil

    client = os.path.join(src_dir, "apps", "chatapp", "chat_client")
    dist = os.path.join(src_dir, "apps", "chatapp", "chat_server", "dist")
    os.makedirs(dist, exist_ok=True)
    chat_html_src = os.path.join(client, "chat.html")
    chat_html_dst = os.path.join(dist, "chat.html")
    with open(chat_html_src, encoding="utf-8") as f:
        chat_html = f.read().replace("__API_URL__", api_url)
    with open(chat_html_dst, "w", encoding="utf-8") as f:
        f.write(chat_html)
    chat_js_src = os.path.join(client, "chat.js")
    chat_js_dst = os.path.join(dist, "chat.js")
    with open(chat_js_src, encoding="utf-8") as f:
        chat_js = f.read().replace("__API_URL__", api_url)
    with open(chat_js_dst, "w", encoding="utf-8") as f:
        f.write(chat_js)
    if os.path.isfile(os.path.join(client, "chat.css")):
        shutil.copy2(os.path.join(client, "chat.css"), os.path.join(dist, "chat.css"))
    logger.debug("Chatapp built: chat.html, chat.js, chat.css")


# --- FUTURE contents of apps/kiosk/run_kiosk.py OR use  kiosk/app and keep this one thing here --- #
def run_kiosk(logger, api_url):
    # Kiosk runs as the kiosk user (often care recipient). Webapp user logs in as Dylan (fm_005) to chat with kiosk user.
    KIOSK_USER_ID = "fm_care_001"
    PATIENT_FAMILY_CIRCLE_ID = "F00000"

    app = create_app(
        api_url=api_url,
        kiosk_user_id=KIOSK_USER_ID,
        family_circle_id=PATIENT_FAMILY_CIRCLE_ID,
    )
    logger.info("Kiosk, server and webapp created successfully")
    app.run()


# --- FUTURE contents of src/main.py --- #

import sys
import threading
import time
import logging

# Ensure src is on path for new package layout
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# --fullscreen = TV mode on second monitor (full 1080×1920, no dev scaling)
if "--fullscreen" in sys.argv:
    os.environ["KIOSK_TV_MODE"] = "1"

from shared.config import (
    get_log_level,
    get_database_path,
    get_railway_api_url,
    get_server_host,
    get_server_port,
    find_available_port,
)

# from apps.chatapp.build_chatapp import build_chatapp
# from apps.webapp.build_webapp import build_webapp
# perhaps kiosk/app is 'run_kiosk' ...
from apps.kiosk.app import create_app


def _start_local_api_server(logger):
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
    server_thread = threading.Thread(
        target=run_server, kwargs={"port": port}, daemon=True
    )
    server_thread.start()
    time.sleep(0.5)

    api_url = f"http://127.0.0.1:{port}"
    return api_url


def run_local_server_and_db(logger):
    logger.debug("Database: local - %s", get_database_path())
    local_api_url = _start_local_api_server(logger)
    src_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        build_webapp(logger, local_api_url, src_dir)
        build_chatapp(logger, local_api_url, src_dir)
    except Exception as e:
        logger.error("Build failed (%s).", e)
        sys.exit(1)

    try:
        from dev.demo.seed import run_seed

        if run_seed(local_api_url):
            logger.info("Demo data seeded")
        else:
            logger.warning("Demo seed failed or skipped")
    except Exception as e:
        logger.warning(f"Demo seed failed: {e}")

    logger.debug("Database loaded")

    os.environ["WEBAPP_URL"] = local_api_url
    os.environ["CHATAPP_URL"] = local_api_url.rstrip("/")
    os.environ["CORS_ORIGIN"] = local_api_url

    logger.info(f"API/DB: {local_api_url}")
    logger.info(f"Webapp: {local_api_url}")
    logger.debug(f"Chatapp: {local_api_url}/chatapp")

    return local_api_url


def use_railway_api_and_db(logger):
    api_url = get_railway_api_url()
    logger.info(f"Database: Railway (remote) - {api_url}")
    webapp_url = os.environ.get("WEBAPP_URL", "").strip()
    chatapp_url = os.environ.get("CHATAPP_URL", "").strip()
    logger.info(f"Webapp: {webapp_url or '(set WEBAPP_URL)'}")
    logger.debug(f"Chatapp: {chatapp_url or '(set CHATAPP_URL for chat redirect)'}")
    return api_url


def set_logging():
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Intentional: silence connection-pool, Werkzeug, PIL, verbose display/app_factory debug
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.app").setLevel(logging.WARNING)
    logging.getLogger("pywebview").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.api_client").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.location").setLevel(
        logging.WARNING
    )
    logging.getLogger("apps.server.database_manager").setLevel(logging.WARNING)
    logging.getLogger("dev.demo.seed").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    return logger


def main():
    """Start pywebview kiosk. Use Railway API if reachable, else start local server + DB."""
    logger = set_logging()
    api_url = ""

    if "--railway-run" not in sys.argv:
        logger.debug(
            "Starting local server, getting DB, and serving local webapp/chatapp"
        )
        try:
            api_url = run_local_server_and_db(logger)
        except Exception as e:
            logger.error(f"Local server / DB setup failed: {e}")
            raise

        logger.debug("Starting Meridian Kiosk...")
        try:
            run_kiosk(logger, api_url)
        except Exception as e:
            logger.error(f"Meridian startup failed: {e}")
            raise

    else:
        logger.info("Obtaining remote railway API, webapp, and chatapp")
        try:
            api_url = use_railway_api_and_db(logger)
        except Exception as e:
            logger.error(f"Railway API setup failed: {e}")
            raise

        logger.debug("Starting Meridian Kiosk...")
        try:
            run_kiosk(logger, api_url)
        except Exception as e:
            logger.error(f"Meridian startup failed: {e}")
            raise

    if not api_url:
        logger.error("No API URL; aborting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
