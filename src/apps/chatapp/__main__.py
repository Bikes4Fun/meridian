"""Build chatapp static assets: python -m src.apps.chatapp (or python src/apps/chatapp from repo root)."""

import logging
import os
import shutil
import sys

_src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from shared.config import get_log_level, get_server_host, get_server_port


def _set_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


def build_chatapp(logger, api_url: str, src_dir: str) -> None:
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

    logger.info("Chatapp build complete")


def _chatapp_bake_api_url() -> str:
    """URL embedded in chat.js. CHATAPP_API_URL overrides; on Railway use RAILWAY_PUBLIC_DOMAIN; else local API."""
    override = (os.getenv("CHATAPP_API_URL") or "").strip()
    if override:
        return override.rstrip("/")
    domain = (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if domain:
        if "://" in domain:
            return domain.rstrip("/")
        return f"https://{domain}".rstrip("/")
    host = get_server_host()
    if host == "0.0.0.0":
        host = "127.0.0.1"
    return f"http://{host}:{get_server_port()}"


def main() -> None:
    logger = _set_logging()
    api_url = _chatapp_bake_api_url()
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    build_chatapp(logger, api_url, src_dir)


if __name__ == "__main__":
    main()

