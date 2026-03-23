"""
Build webapp + chatapp static files.
Replaces node build.js / build_all.js - no Node.js dependency.
API_URL empty string = same-origin (served from same server as API).
"""

import os
import shutil


def build_webapp(api_url: str, src_dir: str):
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
        content = open(os.path.join(client, filename), encoding="utf-8").read()
        open(os.path.join(dist, filename), "w", encoding="utf-8").write(
            content.replace("__API_URL__", api_url)
        )
    if os.path.isfile(os.path.join(client, "style.css")):
        shutil.copy2(os.path.join(client, "style.css"), os.path.join(dist, "style.css"))
    font_src = os.path.join(src_dir, "shared", "fonts", "Atkinson_Hyperlegible")
    font_dst = os.path.join(dist, "fonts")
    if os.path.isdir(font_src):
        os.makedirs(font_dst, exist_ok=True)
        for f in (
            "AtkinsonHyperlegible-Regular.ttf",
            "AtkinsonHyperlegible-Bold.ttf",
            "AtkinsonHyperlegible-Italic.ttf",
            "AtkinsonHyperlegible-BoldItalic.ttf",
        ):
            if os.path.isfile(os.path.join(font_src, f)):
                shutil.copy2(os.path.join(font_src, f), os.path.join(font_dst, f))
    print("Webapp built: login.html, index.html, app.js, events.js, style.css")


def build_chatapp(api_url: str, src_dir: str):
    client = os.path.join(src_dir, "apps", "chatapp", "chat_client")
    dist = os.path.join(src_dir, "apps", "chatapp", "chat_server", "dist")
    os.makedirs(dist, exist_ok=True)
    chat_html = (
        open(os.path.join(client, "chat.html"), encoding="utf-8")
        .read()
        .replace("__API_URL__", api_url)
    )
    open(os.path.join(dist, "index.html"), "w", encoding="utf-8").write(chat_html)
    open(os.path.join(dist, "chat.html"), "w", encoding="utf-8").write(chat_html)
    chat_js = (
        open(os.path.join(client, "chat.js"), encoding="utf-8")
        .read()
        .replace("__API_URL__", api_url)
    )
    open(os.path.join(dist, "chat.js"), "w", encoding="utf-8").write(chat_js)
    if os.path.isfile(os.path.join(client, "chat.css")):
        shutil.copy2(os.path.join(client, "chat.css"), os.path.join(dist, "chat.css"))
    print("Chatapp built: index.html, chat.html, chat.js, chat.css")


if __name__ == "__main__":
    src_dir = os.path.dirname(os.path.abspath(__file__))
    api_url = os.environ.get("API_URL", "")
    build_webapp(api_url, src_dir)
    build_chatapp(api_url, src_dir)
    print("Build complete.")
