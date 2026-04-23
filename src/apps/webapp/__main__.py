"""Build webapp static assets: python -m apps.webapp."""

import logging
import os
import shutil

try:
    from ...shared.config import get_log_level
except ImportError:
    from shared.config import get_log_level

def _set_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, get_log_level().upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


def _inject_webapp_api_url(content: str, api_url: str) -> str:
    needle = "var _u = '__API_URL__';"
    if needle in content:
        esc = api_url.replace("\\", "\\\\").replace("'", "\\'")
        return content.replace(needle, f"var _u = '{esc}';")
    return content.replace("__API_URL__", api_url)


def build_webapp(logger, api_url: str, src_dir: str) -> None:
    client = os.path.join(src_dir, "apps", "webapp", "web_client")
    client_public = os.path.join(client, "public")
    client_src = os.path.join(client, "src")
    client_features = os.path.join(client_src, "features")
    dist = os.path.join(src_dir, "apps", "webapp", "web_server", "dist")
    os.makedirs(dist, exist_ok=True)
    for filename in ("login.html", "privacy.html", "terms.html", "index.html", "info.html", "user-test-form.html"):
        src_path = os.path.join(client_public, filename)
        dst_path = os.path.join(dist, filename)
        if not os.path.isfile(src_path):
            continue
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(_inject_webapp_api_url(content, api_url))
    for filename in ("app.js", "events.js", "medications.js", "ice_editor.js"):
        src_path = os.path.join(client_features, filename)
        dst_path = os.path.join(dist, filename)
        if not os.path.isfile(src_path):
            continue
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(_inject_webapp_api_url(content, api_url))
    api_client_path = os.path.join(client_src, "api_client.js")
    if os.path.isfile(api_client_path):
        with open(api_client_path, encoding="utf-8") as f:
            content = f.read()
        with open(os.path.join(dist, "api_client.js"), "w", encoding="utf-8") as f:
            f.write(_inject_webapp_api_url(content, api_url))
    style_path = os.path.join(client_public, "style.css")
    if os.path.isfile(style_path):
        shutil.copy2(style_path, os.path.join(dist, "style.css"))

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

    repo_root = os.path.abspath(os.path.join(src_dir, ".."))
    brand_dst = os.path.join(dist, "brand")
    os.makedirs(brand_dst, exist_ok=True)
    # Prefer dedicated web brand assets; fall back to iOS app icon so web startup logo always renders.
    logo_candidates = {
        "logo-banner.png": [
            os.path.join(repo_root, "assets", "icons", "original_banner_logo.png"),
            os.path.join(repo_root, "src", "shared", "assets", "icons", "original_banner_logo.png"),
            os.path.join(repo_root, "meridian-ios", "Assets.xcassets", "AppIcon.appiconset", "AppIcon.png"),
        ],
        "logo-mark.png": [
            os.path.join(repo_root, "assets", "icons", "app-icon.png"),
            os.path.join(repo_root, "src", "shared", "assets", "icons", "app-icon.png"),
            os.path.join(repo_root, "meridian-ios", "Assets.xcassets", "AppIcon.appiconset", "AppIcon.png"),
        ],
    }
    for dst_name, candidates in logo_candidates.items():
        src_path = next((candidate for candidate in candidates if os.path.isfile(candidate)), None)
        if src_path:
            shutil.copy2(src_path, os.path.join(brand_dst, dst_name))

    logger.info("Webapp build complete")

def main() -> None:
    logger = _set_logging()
    api_url = (os.getenv("MERIDIAN_API_URL") or "").rstrip("/")
    if not api_url:
        # Railway/Railpack build has no deploy URL at image build time; app.js treats a
        # non-http _u as same-origin (relative /api/*). Set MERIDIAN_API_URL when the
        # static bundle must target a different host (e.g. local API + separate static).
        logger.info(
            "MERIDIAN_API_URL unset; webapp build uses same-origin API base (relative URLs)"
        )
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    build_webapp(logger, api_url, src_dir)


if __name__ == "__main__":
    main()

