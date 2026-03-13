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
    for filename in ("login.html", "index.html", "app.js"):
        content = open(os.path.join(client, filename), encoding="utf-8").read()
        open(os.path.join(dist, filename), "w", encoding="utf-8").write(
            content.replace("__API_URL__", api_url)
        )
    print("Webapp built: login.html, index.html, app.js")


def build_chatapp(api_url: str, src_dir: str):
    client = os.path.join(src_dir, "apps", "chatapp", "chat_client")
    dist = os.path.join(src_dir, "apps", "chatapp", "chat_server", "dist")
    os.makedirs(dist, exist_ok=True)
    chat_html = open(os.path.join(client, "chat.html"), encoding="utf-8").read().replace(
        "__API_URL__", api_url
    )
    open(os.path.join(dist, "index.html"), "w", encoding="utf-8").write(chat_html)
    open(os.path.join(dist, "chat.html"), "w", encoding="utf-8").write(chat_html)
    shutil.copy(os.path.join(client, "poc_chat.html"), os.path.join(dist, "poc_chat.html"))
    chat_js = open(os.path.join(client, "chat.js"), encoding="utf-8").read().replace(
        "__API_URL__", api_url
    )
    open(os.path.join(dist, "chat.js"), "w", encoding="utf-8").write(chat_js)
    print("Chatapp built: index.html, chat.html, poc_chat.html, chat.js")


if __name__ == "__main__":
    src_dir = os.path.dirname(os.path.abspath(__file__))
    api_url = os.environ.get("API_URL", "")
    build_webapp(api_url, src_dir)
    build_chatapp(api_url, src_dir)
    print("Build complete.")
