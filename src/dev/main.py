"""
Main entry point for the Dementia TV application.
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

import logging
import threading
import time
from shared.config import (
    ConfigManager,
    DatabaseConfig,
    get_database_path,
    get_railway_api_url,
    get_server_host,
    get_server_port,
    find_available_port,
    is_railway_reachable,
)
from apps.kiosk.app import create_app

# TODO: from auth when not demo
DEMO_MODE = True
user_id = "0000000000" if DEMO_MODE else None


def main():
    """Start Kivy TV client. Use Railway API if reachable, else start local server + DB."""

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

    if is_railway_reachable():
        api_url = get_railway_api_url()
        logger.info("Using Railway API: %s", api_url)
    
    else:
        logger.warning(
            "Railway API not reachable (%s), using local database.",
            get_railway_api_url(),
        )
        
        # Build local DB if needed
        db_path = get_database_path()
        if not os.path.exists(db_path):
            from apps.server.database import DatabaseManager
            from dev.demo.seed import demo_main

            db_config = DatabaseConfig(path=db_path, create_if_missing=True)
            db = DatabaseManager(db_config)
            result = db.create_database_schema()
            if not result.success:
                logger.error("Schema creation failed: %s", result.error)
                raise RuntimeError("Schema creation failed: %s" % result.error)
            if not demo_main(user_id, db_path=db_path):
                raise RuntimeError("Demo seeding failed")
        
        if DEMO_MODE:
            # update demo family location
            try:
                from dev.demo.seed import (
                    load_location_checkins_data,
                )
                load_location_checkins_data(db_path, user_id)
            except Exception as e:
                logger.debug("Demo family/checkins refresh skipped (old schema?): %s", e)

        logger.info("Database loaded")

        # Start local API server in background
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

        logger.info("Server activated")
        api_url = "http://127.0.0.1:%s" % port

    logger.info("Starting Dementia TV Application...")
    try:
        app = create_app(config_manager, user_id, api_url=api_url)
        logger.info("Application created successfully, starting...")
        app.run()
    except Exception as e:
        logger.error("Application startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
