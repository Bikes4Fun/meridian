"""
Main entry point for Meridian.

Local dev (default): start the Flask API + local DB on this machine, bake webapp/chatapp
(via python -m apps.webapp / apps.chatapp with MERIDIAN_BAKE_API_URL), then open pywebview
against that local server (or loopback URL when --win-kiosk / TV mode needs SendBird Call).

Remote API (--remote-api or MERIDIAN_REMOTE_API=1): local pywebview only; no local Flask.
Kiosk loads API + static assets from the remote base URL (RAILWAY_API_URL / get_api_base_url() /
api_config.json). No local webapp/chatapp bake.

API_URL empty string in bakes = same-origin (served from same host as the API).
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


import sys
import subprocess
import logging
from urllib.parse import urlparse

# Ensure src is on path for new package layout
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# --fullscreen = TV mode on second monitor (full 1080×1920, no dev scaling)
if "--fullscreen" in sys.argv:
    os.environ["KIOSK_TV_MODE"] = "1"
# --win-kiosk = 2736×1824 window (see shared.config get_kiosk_win_kiosk)
if "--win-kiosk" in sys.argv:
    os.environ["KIOSK_WIN_KIOSK"] = "1"

from shared.config import (
    get_log_level,
    get_database_path,
)
from apps.kiosk.app import create_app
from apps.kiosk.__main__ import (
    FAMILY_CIRCLE_ID,
    KIOSK_USER_ID,
    _start_local_api_server,
    prepare_remote_api_kiosk_session,
    use_meridian_remote_api_mode,
)


def _run_bake_subprocesses(logger, bake_api_url: str, src_dir: str) -> None:
    """Bake webapp + chatapp static files; MERIDIAN_BAKE_API_URL is read by each -m __main__."""
    repo_root = os.path.dirname(src_dir)
    env = {**os.environ, "PYTHONPATH": src_dir, "MERIDIAN_BAKE_API_URL": bake_api_url}
    for mod in ("apps.webapp", "apps.chatapp"):
        logger.debug("Baking %s", mod)
        subprocess.run(
            [sys.executable, "-m", mod],
            check=True,
            cwd=repo_root,
            env=env,
        )


def run_local_server_and_db(logger):
    logger.debug("Database: local - %s", get_database_path())
    local_api_url = _start_local_api_server(logger)

    seed_status = "skipped"
    try:
        from dev.demo.seed import run_seed

        if run_seed(local_api_url):
            seed_status = "seeded"
        else:
            seed_status = "skipped"
    except Exception as e:
        seed_status = "failed"
        logger.warning(f"Demo seed failed: {e}")

    pu = urlparse(local_api_url)
    loopback_kiosk = (
        (
            "--win-kiosk" in sys.argv
            or "--fullscreen" in sys.argv
            or os.environ.get("KIOSK_WIN_KIOSK") == "1"
            or os.environ.get("KIOSK_TV_MODE") == "1"
        )
        and pu.scheme == "http"
        and (pu.hostname or "") not in ("127.0.0.1", "localhost")
        and bool(pu.port)
    )
    bake_api_url = "" if loopback_kiosk else local_api_url
    kiosk_app_url = (
        f"http://127.0.0.1:{pu.port}" if loopback_kiosk else local_api_url
    )

    src_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        _run_bake_subprocesses(logger, bake_api_url, src_dir)
    except Exception as e:
        logger.error("Build failed (%s).", e)
        sys.exit(1)

    logger.debug("Database loaded")

    if loopback_kiosk:
        os.environ["WEBAPP_URL"] = kiosk_app_url
        os.environ["CHATAPP_URL"] = kiosk_app_url.rstrip("/")
        os.environ["CORS_ORIGIN"] = ",".join(
            dict.fromkeys([kiosk_app_url, local_api_url])
        )
    else:
        os.environ["WEBAPP_URL"] = local_api_url
        os.environ["CHATAPP_URL"] = local_api_url.rstrip("/")
        os.environ["CORS_ORIGIN"] = local_api_url

    logger.info(f"Ready: {local_api_url}")
    if loopback_kiosk:
        logger.info(
            f"Kiosk pywebview uses {kiosk_app_url} (SendBird Call); API also at {local_api_url}"
        )
        logger.info(
            f"Sendbird Call in a desktop browser on this Mac: open http://127.0.0.1:{pu.port}/chatapp/chat.html "
            f"(HTTP on a LAN hostname is blocked by the Calls SDK)."
        )
    logger.debug(f"Seed status: {seed_status}")

    return local_api_url, kiosk_app_url


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
    logging.getLogger("apps.server.database_services.safe_query_manager").setLevel(
        logging.WARNING
    )
    logging.getLogger("dev.demo.seed").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    return logger


def main():
    """Start pywebview kiosk: full local stack, or local pywebview + remote API only."""
    logger = set_logging()
    api_url = ""

    if "SENDBIRD_SSL_VERIFY" not in os.environ:
        os.environ["SENDBIRD_SSL_VERIFY"] = "0"

    if use_meridian_remote_api_mode():
        kiosk_target = prepare_remote_api_kiosk_session(logger)
        api_url = kiosk_target
    else:
        logger.debug(
            "Starting local server, getting DB, and baking webapp/chatapp via subprocess"
        )
        try:
            api_url, kiosk_target = run_local_server_and_db(logger)
        except Exception as e:
            logger.error(f"Local server / DB setup failed: {e}")
            raise

    if not api_url:
        logger.error("No API URL; aborting.")
        sys.exit(1)

    logger.debug("Starting Meridian Kiosk (pywebview)...")
    try:
        app = create_app(
            api_url=kiosk_target,
            kiosk_user_id=KIOSK_USER_ID,
            family_circle_id=FAMILY_CIRCLE_ID,
        )
        app.run()
    except Exception as e:
        logger.error(f"Meridian startup failed: {e}")
        raise


if __name__ == "__main__":
    main()
