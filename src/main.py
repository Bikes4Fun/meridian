"""Main entry point for Meridian local development.

Public HTTPS for Twilio (optional):
- Pass `--ngrok` to spawn `ngrok http <PORT>` after the API starts and set MERIDIAN_API_URL
  to the tunnel URL (same Flask process; ngrok only proxies).

`--ngrok` uses ngrok’s local API (default http://127.0.0.1:4040). Stop any other ngrok agent
using that port, or automatic startup will fail.
"""

import json
import os

# Load .env from repo root if python-dotenv is available.
try:
    from dotenv import load_dotenv

    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


import shutil
import subprocess
import logging
import sys
import time
import urllib.error
import urllib.request
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

from shared.config import get_log_level, get_remote_api_base_url

_NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def _parse_port_from_api_base(api_url: str) -> int:
    p = urlparse(api_url)
    if p.port is not None:
        return p.port
    return 80 if (p.scheme or "http") == "http" else 443


def _terminate_ngrok(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def _start_ngrok_tunnel(port: int, logger: logging.Logger) -> tuple[str, subprocess.Popen]:
    """Run `ngrok http <port>`, poll local API for https public URL, return (base url, process)."""
    ngrok_bin = shutil.which("ngrok")
    if not ngrok_bin:
        raise RuntimeError(
            "ngrok not found in PATH. Install from https://ngrok.com/download."
        )
    proc = subprocess.Popen(
        [ngrok_bin, "http", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.6)
    if proc.poll() is not None:
        err = ""
        if proc.stderr:
            err = proc.stderr.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ngrok exited immediately.{(' ' + err) if err else ''}")

    deadline = time.monotonic() + 35.0
    public_base = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(_NGROK_API, timeout=2.0) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            for t in data.get("tunnels") or []:
                if (t.get("proto") or "") != "https":
                    continue
                u = (t.get("public_url") or "").strip().rstrip("/")
                if u:
                    public_base = u
                    break
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            pass
        if public_base:
            break
        time.sleep(0.35)

    if not public_base:
        _terminate_ngrok(proc)
        raise RuntimeError(
            "ngrok started but no HTTPS tunnel URL was read from http://127.0.0.1:4040/api/tunnels. "
            "Is another process using the ngrok local API port?"
        )
    logger.info(f"ngrok tunnel: {public_base} → localhost:{port}")
    return public_base, proc


def set_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Intentional: silence connection-pool, Werkzeug, PIL, verbose display/app_factory debug
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("twilio.http_client").setLevel(logging.WARNING)
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
    kiosk_args = [arg for arg in sys.argv[1:] if arg != "--ngrok"]
    use_ngrok = "--ngrok" in sys.argv[1:]
    remote_run = "--remote-api" in kiosk_args
    ngrok_proc: subprocess.Popen | None = None

    try:
        if remote_run:
            if use_ngrok:
                logger.warning("--ngrok is ignored with --remote-api (API is not local).")
            remote_api_url = get_remote_api_base_url()
            if not remote_api_url:
                raise RuntimeError("RAILWAY_API_URL is required when using --remote-api")
            logger.info("Runtime mode: railway (--remote-api)")
            os.environ["MERIDIAN_API_URL"] = remote_api_url
            _run_module(logger, "apps.kiosk", kiosk_args)
            return

        else:
            from apps.server.__main__ import start_local_api_server

            api_url = start_local_api_server(logger).rstrip("/")
            if use_ngrok:
                ngrok_url, ngrok_proc = _start_ngrok_tunnel(_parse_port_from_api_base(api_url), logger)
                os.environ["MERIDIAN_PUBLIC_API_URL"] = ngrok_url
                api_url = ngrok_url
                os.environ["MERIDIAN_KIOSK_NGROK_BYPASS"] = "1"
                os.environ["MERIDIAN_KIOSK_USER_AGENT"] = "Meridian-Kiosk/1.0"
                logger.info("Runtime mode: ngrok (--ngrok)")
            else:
                logger.info("Runtime mode: local")
                os.environ.pop("MERIDIAN_KIOSK_NGROK_BYPASS", None)
                if (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip():
                    logger.warning(
                        "Twilio is configured but this run is local-only. "
                        "Voice/TwiML webhooks need a public HTTPS base: run `python main.py --ngrok` "
                        "or `python main.py --remote-api`."
                    )
            os.environ["MERIDIAN_API_URL"] = api_url
            _run_module(logger, "apps.webapp", [])
            _run_module(logger, "apps.kiosk", kiosk_args)

    except Exception as e:
        logger.error(f"Meridian startup failed: {e}")
        raise
    finally:
        _terminate_ngrok(ngrok_proc)


if __name__ == "__main__":
    main()
