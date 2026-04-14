"""Main entry point for Meridian local development."""

import os

# Load .env from repo root if python-dotenv is available.
# TODO: if this is not used by everything then it should only exist in the section it is used by
try:
    from dotenv import load_dotenv

    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


import subprocess
import logging
import sys

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

from shared.config import get_log_level, get_remote_api_base_url


def set_logging() -> logging.Logger:
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
    logging.getLogger("apps.server.database_services.location").setLevel(logging.WARNING)
    logging.getLogger("apps.server.database_services.safe_query_manager").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    return logger


def _run_module(logger: logging.Logger, module_name: str, args: list[str]) -> None:
    src_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(src_dir)
    env = {**os.environ, "PYTHONPATH": src_dir}
    cmd = [sys.executable, "-m", module_name, *args]
    logger.debug(f"Running {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=repo_root, env=env)


def main() -> None:
    """Run local stack or remote kiosk mode; pass through kiosk flags."""
    logger = set_logging()
    kiosk_args = [arg for arg in sys.argv[1:]]
    remote_run = "--remote-api" in kiosk_args

    try:
        if remote_run:
            remote_api_url = get_remote_api_base_url()
            if not remote_api_url:
                raise RuntimeError("RAILWAY_API_URL is required when using --remote-api")
            os.environ["MERIDIAN_API_URL"] = remote_api_url
            _run_module(logger, "apps.kiosk", kiosk_args)
            return

        else:
            from apps.server.__main__ import start_local_api_server

            api_url = start_local_api_server(logger).rstrip("/")
            os.environ["MERIDIAN_API_URL"] = api_url
            _run_module(logger, "apps.webapp", [])
            _run_module(logger, "apps.kiosk", kiosk_args)
            
    except Exception as e:
        logger.error(f"Meridian startup failed: {e}")
        raise


if __name__ == "__main__":
    main()
