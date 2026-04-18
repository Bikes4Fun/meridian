"""Run server: python -m apps.server [serve] [port]."""

import os
import sys
import threading
import time
import urllib.request

# Ensure src is on path for Railway/deploy (shared is at src/shared)
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
if _src not in sys.path:
    sys.path.insert(0, _src)


def _should_run_demo_seed() -> bool:
    """Avoid auto-seeding deployed APIs unless explicitly requested.

    Railway (and similar) set RAILWAY_* env vars → skip seed by default so restarts
    do not clobber data. To load demo data there, set MERIDIAN_DEMO_SEED=1 on the service.
    """
    flag = (os.environ.get("MERIDIAN_DEMO_SEED") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return not bool(
        (os.environ.get("RAILWAY_ENVIRONMENT") or "").strip()
        or (os.environ.get("RAILWAY_SERVICE_NAME") or "").strip()
    )


def _seed_demo_data_after_startup(api_base_url: str, logger=None) -> None:
    """Wait for server health, then seed demo data once."""
    try:
        from ...dev.demo.seed import run_seed
    except ImportError:
        from dev.demo.seed import run_seed

    if not _should_run_demo_seed():
        msg = (
            "Auto-seed skipped (deploy env detected). "
            "Set MERIDIAN_DEMO_SEED=1 on the service to load demo data on Railway."
        )
        if logger is not None:
            logger.info(msg)
        else:
            print(msg)
        return

    health_url = f"{api_base_url}/api/health"
    for _ in range(60):
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(1)
    else:
        msg = f"Auto-seed skipped: server health not ready at {health_url}"
        if logger is not None:
            logger.warning(msg)
        else:
            print(msg)
        return

    ok = run_seed(api_base_url)
    if ok:
        msg = "Auto-seed complete: demo data loaded."
        if logger is not None:
            logger.info(msg)
        else:
            print(msg)
    else:
        msg = "Auto-seed failed: demo data not loaded."
        if logger is not None:
            logger.warning(msg)
        else:
            print(msg)


def _prepare_server_runtime(logger=None, requested_port=None) -> tuple[int, str, str]:
    """Prepare db/schema and return (port, api_base_url, db_path)."""
    try:
        from ...shared.config import (
            find_available_port,
            get_database_path,
            get_local_api_base_url,
            get_meridian_ssl_files,
            get_server_host,
            get_server_port,
        )
    except ImportError:
        from shared.config import (
            find_available_port,
            get_database_path,
            get_local_api_base_url,
            get_meridian_ssl_files,
            get_server_host,
            get_server_port,
        )
    try:
        from ...dev.demo.seed import ensure_local_seed_prerequisites
    except ImportError:
        from dev.demo.seed import ensure_local_seed_prerequisites

    from .database_services.db_service_registry import create_service_container

    host = get_server_host()
    start_port = requested_port if requested_port is not None else get_server_port()
    port = find_available_port(host, start_port)
    if port != start_port:
        msg = f"Port {start_port} in use, using port {port} instead."
        if logger is not None:
            logger.warning(msg)
        else:
            print(msg)
    os.environ["PORT"] = str(port)

    db_path = get_database_path()
    create_service_container(db_path).ensure_schema()
    ensure_local_seed_prerequisites(db_path)
    if logger is not None:
        logger.info(f"Database: local - {db_path}")

    api_base_url = get_local_api_base_url(
        host=host,
        port=port,
        https_enabled=bool(get_meridian_ssl_files()),
    )
    return port, api_base_url, db_path


def start_local_api_server(logger=None) -> str:
    """Start local API server in a background thread and return base URL."""
    from .api import run_server

    port, api_base_url, _db_path = _prepare_server_runtime(logger=logger)
    threading.Thread(target=run_server, kwargs={"port": port}, daemon=True).start()
    _seed_demo_data_after_startup(api_base_url, logger)
    if logger is not None:
        logger.info(f"Local API URL: {api_base_url}")
    return api_base_url


def main():
    from .api import run_server

    args = sys.argv[1:]
    requested_port = None
    if args and args[0] == "serve":
        args = args[1:]
    elif args and not args[0].isdigit():
        print(
            f"Unknown command '{args[0]}'. Supported: serve [port], or [port] for backward compatibility."
        )
        sys.exit(2)
    if args:
        try:
            requested_port = int(args[0])
        except ValueError:
            requested_port = None

    _port, api_base_url, _db_path = _prepare_server_runtime(
        logger=None, requested_port=requested_port
    )
    threading.Thread(
        target=_seed_demo_data_after_startup,
        args=(api_base_url, None),
        daemon=True,
    ).start()
    run_server()


if __name__ == "__main__":
    main()
