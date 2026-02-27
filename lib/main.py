"""
Main entry point for the Dementia TV application.
Starts the API server (DB + REST) in a background thread, then runs the Kivy TV client.
"""

import os

# Before any Kivy import: silence Kivy startup logs (Logger, Factory, Image, Window, GL, etc.)
os.environ["KIVY_LOG_LEVEL"] = "warning"
os.environ["KCFG_KIVY_LOG_LEVEL"] = "warning"
# os.environ["KIVY_NO_CONSOLELOG"] = "2"

import logging
import threading
import time
from config import (
    ConfigManager,
    DatabaseConfig,
    get_database_path,
    get_server_host,
    get_server_port,
    find_available_port,
)
from app_factory import create_app

DEMO_MODE = True
DEMO_USER = "0000000000"


def main():
    """Start API server in background, then run Kivy TV client."""

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
    logging.getLogger("app_factory").setLevel(logging.WARNING)
    logging.getLogger("demo.demo").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    # In demo mode: if DB doesn't exist, create schema and seed before server starts
    db_path = get_database_path()
    if DEMO_MODE and not os.path.exists(db_path):
        from server.database_management.database_manager import DatabaseManager
        from demo.demo import demo_main

        db_config = DatabaseConfig(path=db_path, create_if_missing=True)
        db = DatabaseManager(db_config)
        result = db.create_database_schema()
        if not result.success:
            logger.error("Schema creation failed: %s", result.error)
            raise RuntimeError("Schema creation failed: %s" % result.error)
        if not demo_main(DEMO_USER, db_path=db_path):
            raise RuntimeError("Demo seeding failed")
    if DEMO_MODE:
        try:
            from demo.demo import (
                load_demo_family_members_from_json_into_db,
                load_location_checkins_data,
            )

            load_demo_family_members_from_json_into_db(db_path, DEMO_USER)
            load_location_checkins_data(db_path, DEMO_USER)
        except Exception as e:
            logger.debug("Demo family/checkins refresh skipped (old schema?): %s", e)

    logger.info("Database loaded")

    # Start API server in background so DB is created/loaded and client has data
    from server.app import run_server

    host = get_server_host()
    start_port = get_server_port()
    port = find_available_port(host, start_port)
    if port != start_port:
        logger.warning("Port %s in use, using port %s instead.", start_port, port)
    os.environ["PORT"] = str(port)  # so get_server_url() uses this port for the client

    logger.info("Starting API server...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # give server a moment to bind and load DB

    logger.info("Server activated")
    logger.info("Starting Dementia TV Application...")
    try:
        user_id = "0000000000"  # TODO: from auth when not demo
        app = create_app(config_manager, user_id)
        logger.info("Application created successfully, starting...")
        app.run()
    except Exception as e:
        logger.error("Application startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
