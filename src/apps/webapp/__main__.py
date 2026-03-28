"""Build webapp static assets: python -m src.apps.webapp."""

import logging
import os
import shutil

try:
    from ...shared.config import get_api_base_url, get_log_level
except ImportError:
    from shared.config import get_api_base_url, get_log_level


def _set_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


def build_webapp(logger, api_url: str, src_dir: str) -> None:
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
        for filename in (
            "AtkinsonHyperlegible-Regular.ttf",
            "AtkinsonHyperlegible-Bold.ttf",
            "AtkinsonHyperlegible-Italic.ttf",
            "AtkinsonHyperlegible-BoldItalic.ttf",
        ):
            src_path = os.path.join(font_src, filename)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, os.path.join(font_dst, filename))

    logger.info("Webapp build complete")


def main() -> None:
    logger = _set_logging()
    api_url = get_api_base_url()
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    build_webapp(logger, api_url, src_dir)


if __name__ == "__main__":
    main()

