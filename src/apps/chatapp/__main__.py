"""Build chatapp static assets: python -m src.apps.chatapp (or python src/apps/chatapp from repo root)."""

import logging
import os
import shutil
import sys

_src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from shared.config import get_api_base_url, get_log_level


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


def main() -> None:
    logger = _set_logging()
    api_url = get_api_base_url()
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    build_chatapp(logger, api_url, src_dir)


if __name__ == "__main__":
    main()

