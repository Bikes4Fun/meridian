"""Entry point for pywebview kiosk. Run: PYTHONPATH=src python -m apps.kiosk

Kiosk uses a provided API base URL; it does not start the API server.
"""

import logging
import os
import sys

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

from shared.config import get_log_level
from apps.kiosk.app import create_app

KIOSK_USER_ID = os.environ.get("KIOSK_USER_ID") or "fm_care_001"
FAMILY_CIRCLE_ID = (
    os.environ.get("FAMILY_CIRCLE_ID")
    or os.environ.get("PATIENT_FAMILY_CIRCLE_ID")
    or "F00000"
)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.app").setLevel(logging.INFO)
    logging.getLogger("pywebview").setLevel(logging.WARNING)
    logging.getLogger("apps.kiosk.api_client").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.location").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.safe_query_manager").setLevel(
        logging.WARNING
    )
    logging.getLogger("dev.demo.seed").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    api_url = (os.getenv("MERIDIAN_API_URL") or "").rstrip("/")
    if not api_url:
        raise RuntimeError("MERIDIAN_API_URL is required for kiosk startup")

    logger.debug("Kiosk API URL: %s", api_url)
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
