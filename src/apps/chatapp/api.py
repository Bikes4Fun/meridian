"""
Chatapp API server. Owns Sendbird: config, token, recipient.
Main server only directs clients here (chat-session-url, chat-session-bootstrap).
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse

import logging
import requests
from flask import (
    Flask,
    abort,
    jsonify,
    request,
    g,
    session,
    redirect,
    send_from_directory,
)

try:
    from ...shared.config import get_database_path, DatabaseConfig
except ImportError:
    from shared.config import get_database_path, DatabaseConfig

from ..server.database import DatabaseManager
from ..server.services.sendbird import SendbirdService


def _verify_chat_entry_token(secret: str, token: str) -> dict | None:
    """Verify token from main server; return payload or None."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts[0], parts[1]
        payload_b64_padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded).decode())
        if payload.get("exp", 0) < time.time():
            return None
        expected = hmac.new(
            secret.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        return payload
    except Exception:
        return None


def create_chatapp_app(static_dir: str, secret_key: str = None):
    """Create Flask app for chatapp API and static serving."""
    app = Flask(__name__, static_folder=None)
    app.secret_key = (
        secret_key or os.environ.get("SECRET_KEY") or "dev-secret-change-in-production"
    )

    db_path = get_database_path()
    db_config = DatabaseConfig(path=db_path, create_if_missing=True)
    db_manager = DatabaseManager(db_config)
    sendbird_svc = SendbirdService(db_manager)

    @app.route("/auth")
    def auth():
        """Verify token from main server, set session, redirect to chat."""
        token = (request.args.get("token") or "").strip()
        if not token:
            return jsonify({"error": "token required"}), 400
        payload = _verify_chat_entry_token(app.secret_key, token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 403
        session["user_id"] = payload["user_id"]
        session["family_circle_id"] = payload["family_circle_id"]
        path = "/"
        sb = (payload.get("sendbird_user_id") or "").strip()
        dn = (payload.get("display_name") or "").strip()
        if sb:
            path += "?sendbird_user_id=" + urllib.parse.quote(sb)
            if dn:
                path += "&display_name=" + urllib.parse.quote(dn)
        return redirect(path)

    @app.route("/api/login", methods=["POST"])
    def api_login():
        """Login for dev/testing. Sets session from user_id, family_circle_id."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        user_id = data.get("user_id")
        family_circle_id = data.get("family_circle_id")
        if not user_id or not family_circle_id:
            return jsonify({"error": "user_id and family_circle_id required"}), 400
        session["user_id"] = user_id
        session["family_circle_id"] = family_circle_id
        return jsonify({"ok": True})

    def _require_session():
        if request.path in ("/api/login", "/auth"):
            return
        if not request.path.startswith("/api/"):
            return
        uid = session.get("user_id")
        fid = session.get("family_circle_id")
        if not uid or not fid:
            abort(401, "Log in at /auth or /api/login first")
        g.user_id = uid
        g.family_circle_id = fid

    @app.errorhandler(401)
    def _json_401(err):
        """Return JSON for 401 so fetch().json() works; Flask default is HTML."""
        return jsonify({"error": "Not logged in", "detail": str(err.description or "Log in at /auth or /api/login first")}), 401

    @app.before_request
    def before():
        _require_session()

    @app.after_request
    def _log_request_response(resp):
        """Print chat API requests in a compact format."""
        if request.method == "OPTIONS":
            return resp
        if not (
            request.path.startswith("/api/chat/")
            or request.path == "/auth"
            or request.path == "/api/login"
        ):
            return resp
        try:
            body = (
                request.get_json(silent=True)
                if request.method in ("POST", "PUT", "PATCH")
                else None
            )
            req = "%s %s" % (request.method, request.path)
            if body:
                req += " " + json.dumps(body)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                print("[chatapp] %s → %s redirect" % (req, resp.status_code))
            else:
                resp_body = resp.get_data(as_text=True)
                if (
                    resp.headers.get("Content-Type", "").startswith("application/json")
                    and resp_body
                ):
                    try:
                        formatted = json.dumps(
                            json.loads(resp_body), separators=(",", ":")
                        )
                        formatted = (
                            formatted[:300] + "…" if len(formatted) > 300 else formatted
                        )
                    except (ValueError, TypeError):
                        formatted = resp_body[:200]
                    print("[chatapp] %s → %s  %s" % (req, resp.status_code, formatted))
                else:
                    print("[chatapp] %s → %s" % (req, resp.status_code))
        except Exception:
            pass
        return resp

    @app.route("/api/chat/config", methods=["GET"])
    def api_chat_config():
        """Return Sendbird app_id for client SDK."""
        if not sendbird_svc.is_configured():
            return (
                jsonify(
                    {
                        "error": "Sendbird not configured (SENDBIRD_APP_ID, SENDBIRD_API_TOKEN)"
                    }
                ),
                503,
            )
        return jsonify({"app_id": sendbird_svc.get_sendbird_app_id()})

    @app.route("/api/chat/token", methods=["POST"])
    def api_chat_token():
        """Issue session token for Sendbird user mapped to app user."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(
            app_user_id
        ) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return (
                jsonify(
                    {
                        "error": "No Sendbird user linked",
                        "detail": "Add sendbird_user_id to user or set SENDBIRD_USER_ID_MAP.",
                    }
                ),
                400,
            )
        try:
            ok, token_val, err = sendbird_svc.issue_session_token(sendbird_user_id)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({
                    "error": "Cannot reach Sendbird",
                    "detail": "Check network and SENDBIRD_APP_ID.",
                }), 502
            logging.exception("Unexpected error while issuing Sendbird session token")
            return jsonify({
                "error": "Sendbird issue token failed",
                "detail": "An internal error occurred while issuing the token.",
            }), 502
        if not ok:
            return jsonify({"error": "Sendbird issue token failed", "detail": err}), 502
        r = db_manager.execute_query(
            "SELECT display_name FROM users WHERE id = ?", (app_user_id,)
        )
        display_name = (
            (r.data[0].get("display_name") or app_user_id).strip()
            if r.success and r.data
            else app_user_id
        )
        return jsonify(
            {
                "sendbird_user_id": sendbird_user_id,
                "session_token": token_val,
                "display_name": display_name,
            }
        )

    @app.route("/api/chat/recipient", methods=["GET"])
    def api_chat_recipient():
        """Default 1:1 recipient for current user."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        family_circle_id = getattr(g, "family_circle_id", None) or ""
        sendbird_recipient_id, recipient_name = sendbird_svc.get_default_recipient(
            family_circle_id
        )
        if not sendbird_recipient_id:
            sendbird_recipient_id = (
                sendbird_svc.get_sendbird_default_recipient_id_from_env()
            )
            recipient_name = "Family"
        if not sendbird_recipient_id:
            return (
                jsonify(
                    {
                        "error": "No default recipient",
                        "detail": "Add sendbird_user_id to contact or set SENDBIRD_DEFAULT_RECIPIENT_ID.",
                    }
                ),
                503,
            )
        return jsonify(
            {"sendbird_user_id": sendbird_recipient_id, "name": recipient_name}
        )

    @app.route("/api/chat/channel", methods=["POST"])
    def api_chat_channel():
        """Create 1:1 group channel via Platform API. Returns channel_url for client getChannel."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(
            app_user_id
        ) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return jsonify({"error": "No Sendbird user linked"}), 400
        data = request.get_json(silent=True) or {}
        recipient_id = (data.get("recipient_sendbird_user_id") or "").strip()
        if not recipient_id:
            family_circle_id = getattr(g, "family_circle_id", None) or ""
            recipient_id, _ = sendbird_svc.get_default_recipient(family_circle_id)
        if not recipient_id:
            recipient_id = sendbird_svc.get_sendbird_default_recipient_id_from_env()
        if not recipient_id:
            return jsonify({"error": "No default recipient"}), 503
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        payload = {
            "user_ids": [sendbird_user_id, recipient_id],
            "is_distinct": True,
            "name": "Family",
        }
        try:
            r = requests.post(
                base + "/group_channels",
                headers=sendbird_svc._headers(),
                json=payload,
                timeout=10,
            )
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({
                    "error": "Cannot reach Sendbird",
                    "detail": "Check network and SENDBIRD_APP_ID.",
                }), 502
            logging.exception("Create channel failed due to unexpected error")
            return jsonify({
                "error": "Create channel failed",
                "detail": "An internal error occurred while creating the channel.",
            }), 502
        if r.status_code != 200:
            body = (
                r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            msg = body.get("message", r.text)
            return jsonify({"error": "Create channel failed", "detail": msg}), 502
        data = r.json()
        channel_url = (data.get("channel_url") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return (
                jsonify(
                    {
                        "error": "Create channel failed",
                        "detail": "Invalid channel_url from Sendbird" if channel_url else "No channel_url in response",
                    }
                ),
                502,
            )
        # Automatic "wants to chat" message to Deanna — commented out
        # r = db_manager.execute_query(
        #     "SELECT display_name FROM users WHERE id = ?", (app_user_id,)
        # )
        # display_name = (
        #     (r.data[0].get("display_name") or app_user_id).strip()
        #     if r.success and r.data
        #     else app_user_id
        # )
        # msg_body = {
        #     "message_type": "MESG",
        #     "user_id": sendbird_user_id,
        #     "message": (display_name or "Someone") + " wants to chat.",
        # }
        #
        # msg_url = base + "/group_channels/" + channel_url + "/messages"
        # try:
        #     r2 = requests.post(
        #         msg_url, headers=sendbird_svc._headers(), json=msg_body, timeout=10
        #     )
        #     if r2.status_code == 200:
        #         resp_data = (
        #             r2.json()
        #             if r2.headers.get("content-type", "").startswith("application/json")
        #             else {}
        #         )
        #         msg_id = resp_data.get("message_id") or resp_data.get("id")
        #         if msg_id is not None:
        #             print(
        #                 "[chatapp] wants-to-chat → sent (Sendbird confirmed msg_id: %s)"
        #                 % msg_id
        #             )
        #         else:
        #             print(
        #                 "[chatapp] wants-to-chat → sent (Sendbird 200, no msg_id in response)"
        #             )
        #     else:
        #         print(
        #             "[chatapp] wants-to-chat → %s %s"
        #             % (r2.status_code, r2.text[:100] if r2.text else "")
        #         )
        # except Exception as e:
        #     print("[chatapp] wants-to-chat → error: %s" % e)
        return jsonify({"channel_url": channel_url})

    @app.route("/api/chat/send", methods=["POST"])
    def api_chat_send():
        """Proxy: send message via Sendbird Platform API."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(
            app_user_id
        ) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return jsonify({"error": "No Sendbird user linked"}), 400
        data = request.get_json(silent=True) or {}
        channel_url = (data.get("channel_url") or "").strip()
        message = (data.get("message") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return jsonify({"error": "channel_url required"}), 400
        if not message:
            return jsonify({"error": "message required"}), 400
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        payload = {
            "message_type": "MESG",
            "user_id": sendbird_user_id,
            "message": message,
        }
        msg_url = base + "/group_channels/" + urllib.parse.quote(channel_url, safe="") + "/messages"
        try:
            r = requests.post(msg_url, headers=sendbird_svc._headers(), json=payload, timeout=10)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network."}), 502
            logging.exception("Send message failed")
            return jsonify({"error": "Send failed", "detail": str(e)}), 502
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", r.text)
            return jsonify({"error": "Send failed", "detail": msg}), 502
        return jsonify(r.json())

    @app.route("/api/chat/messages", methods=["GET"])
    def api_chat_messages():
        """Proxy: list messages via Sendbird Platform API."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        channel_url = (request.args.get("channel_url") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return jsonify({"error": "channel_url required"}), 400
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        message_ts = int(time.time() * 1000) + 86400000
        msg_url = base + "/group_channels/" + urllib.parse.quote(channel_url, safe="") + "/messages"
        params = {"message_ts": message_ts, "prev_limit": 50, "next_limit": 0}
        try:
            r = requests.get(msg_url, headers=sendbird_svc._headers(), params=params, timeout=10)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network."}), 502
            logging.exception("List messages failed")
            return jsonify({"error": "List messages failed", "detail": str(e)}), 502
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", r.text)
            return jsonify({"error": "List messages failed", "detail": msg}), 502
        return jsonify(r.json())

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_static(path):
        """Serve static files from dist."""
        if not path:
            if not session.get("user_id") or not session.get("family_circle_id"):
                return redirect("/poc_chat.html")
            path = "index.html"
        return send_from_directory(static_dir, path)

    return app


def register_chatapp_routes(app, sendbird_svc, db_manager, chat_static_prefix: str = ""):
    """Register chatapp API routes on an existing Flask app (for Railway all-in-one deploy).
    chat_static_prefix: e.g. '/chat' when chatapp static is at /chat/*; auth redirects there."""
    auth_redirect_base = (chat_static_prefix or "").rstrip("/")

    @app.route("/auth")
    def auth():
        token = (request.args.get("token") or "").strip()
        if not token:
            return jsonify({"error": "token required"}), 400
        payload = _verify_chat_entry_token(app.secret_key, token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 403
        session["user_id"] = payload["user_id"]
        session["family_circle_id"] = payload["family_circle_id"]
        path = (auth_redirect_base + "/poc_chat.html") if auth_redirect_base else "/"
        sb = (payload.get("sendbird_user_id") or "").strip()
        dn = (payload.get("display_name") or "").strip()
        if sb:
            path += "?sendbird_user_id=" + urllib.parse.quote(sb)
            if dn:
                path += "&display_name=" + urllib.parse.quote(dn)
        return redirect(path)

    @app.route("/api/chat/config", methods=["GET"])
    def api_chat_config():
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured (SENDBIRD_APP_ID, SENDBIRD_API_TOKEN)"}), 503
        return jsonify({"app_id": sendbird_svc.get_sendbird_app_id()})

    @app.route("/api/chat/token", methods=["POST"])
    def api_chat_token():
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(app_user_id) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return jsonify({"error": "No Sendbird user linked", "detail": "Add sendbird_user_id to user or set SENDBIRD_USER_ID_MAP."}), 400
        try:
            ok, token_val, err = sendbird_svc.issue_session_token(sendbird_user_id)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network and SENDBIRD_APP_ID."}), 502
            logging.exception("Unexpected error while issuing Sendbird session token")
            return jsonify({"error": "Sendbird issue token failed", "detail": "An internal error occurred while issuing the token."}), 502
        if not ok:
            return jsonify({"error": "Sendbird issue token failed", "detail": err}), 502
        r = db_manager.execute_query("SELECT display_name FROM users WHERE id = ?", (app_user_id,))
        display_name = (r.data[0].get("display_name") or app_user_id).strip() if r.success and r.data else app_user_id
        return jsonify({"sendbird_user_id": sendbird_user_id, "session_token": token_val, "display_name": display_name})

    @app.route("/api/chat/recipient", methods=["GET"])
    def api_chat_recipient():
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        family_circle_id = getattr(g, "family_circle_id", None) or ""
        sendbird_recipient_id, recipient_name = sendbird_svc.get_default_recipient(family_circle_id)
        if not sendbird_recipient_id:
            sendbird_recipient_id = sendbird_svc.get_sendbird_default_recipient_id_from_env()
            recipient_name = "Family"
        if not sendbird_recipient_id:
            return jsonify({"error": "No default recipient", "detail": "Add sendbird_user_id to contact or set SENDBIRD_DEFAULT_RECIPIENT_ID."}), 503
        return jsonify({"sendbird_user_id": sendbird_recipient_id, "name": recipient_name})

    @app.route("/api/chat/channel", methods=["POST"])
    def api_chat_channel():
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(app_user_id) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return jsonify({"error": "No Sendbird user linked"}), 400
        data = request.get_json(silent=True) or {}
        recipient_id = (data.get("recipient_sendbird_user_id") or "").strip()
        if not recipient_id:
            family_circle_id = getattr(g, "family_circle_id", None) or ""
            recipient_id, _ = sendbird_svc.get_default_recipient(family_circle_id)
        if not recipient_id:
            recipient_id = sendbird_svc.get_sendbird_default_recipient_id_from_env()
        if not recipient_id:
            return jsonify({"error": "No default recipient"}), 503
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        payload = {"user_ids": [sendbird_user_id, recipient_id], "is_distinct": True, "name": "Family"}
        try:
            r = requests.post(base + "/group_channels", headers=sendbird_svc._headers(), json=payload, timeout=10)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network and SENDBIRD_APP_ID."}), 502
            logging.exception("Create channel failed due to unexpected error")
            return jsonify({"error": "Create channel failed", "detail": "An internal error occurred while creating the channel."}), 502
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", r.text)
            return jsonify({"error": "Create channel failed", "detail": msg}), 502
        data = r.json()
        channel_url = (data.get("channel_url") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return jsonify({"error": "Create channel failed", "detail": "Invalid channel_url from Sendbird" if channel_url else "No channel_url in response"}), 502
        return jsonify({"channel_url": channel_url})

    @app.route("/api/chat/send", methods=["POST"])
    def api_chat_send():
        """Proxy: send message via Sendbird Platform API."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(app_user_id) or sendbird_svc.get_sendbird_user_id_from_env(app_user_id)
        if not sendbird_user_id:
            return jsonify({"error": "No Sendbird user linked"}), 400
        data = request.get_json(silent=True) or {}
        channel_url = (data.get("channel_url") or "").strip()
        message = (data.get("message") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return jsonify({"error": "channel_url required"}), 400
        if not message:
            return jsonify({"error": "message required"}), 400
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        payload = {"message_type": "MESG", "user_id": sendbird_user_id, "message": message}
        msg_url = base + "/group_channels/" + urllib.parse.quote(channel_url, safe="") + "/messages"
        try:
            r = requests.post(msg_url, headers=sendbird_svc._headers(), json=payload, timeout=10)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network."}), 502
            logging.exception("Send message failed")
            return jsonify({"error": "Send failed", "detail": str(e)}), 502
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", r.text)
            return jsonify({"error": "Send failed", "detail": msg}), 502
        return jsonify(r.json())

    @app.route("/api/chat/messages", methods=["GET"])
    def api_chat_messages():
        """Proxy: list messages via Sendbird Platform API."""
        if not sendbird_svc.is_configured():
            return jsonify({"error": "Sendbird not configured"}), 503
        app_user_id = getattr(g, "user_id", None)
        if not app_user_id:
            return jsonify({"error": "Not logged in"}), 401
        channel_url = (request.args.get("channel_url") or "").strip()
        if not channel_url or not channel_url.startswith("sendbird_group_channel_"):
            return jsonify({"error": "channel_url required"}), 400
        base = sendbird_svc._api_url()
        if not base:
            return jsonify({"error": "Sendbird not configured"}), 503
        message_ts = int(time.time() * 1000) + 86400000
        msg_url = base + "/group_channels/" + urllib.parse.quote(channel_url, safe="") + "/messages"
        params = {"message_ts": message_ts, "prev_limit": 50, "next_limit": 0}
        try:
            r = requests.get(msg_url, headers=sendbird_svc._headers(), params=params, timeout=10)
        except Exception as e:
            err_msg = str(e)
            if "resolve" in err_msg.lower() or "nodename" in err_msg.lower() or "ConnectionError" in type(e).__name__:
                return jsonify({"error": "Cannot reach Sendbird", "detail": "Check network."}), 502
            logging.exception("List messages failed")
            return jsonify({"error": "List messages failed", "detail": str(e)}), 502
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("message", r.text)
            return jsonify({"error": "List messages failed", "detail": msg}), 502
        return jsonify(r.json())


def run_chatapp_server(port: int, static_dir: str, secret_key: str = None):
    """Run chatapp Flask server."""
    app = create_chatapp_app(static_dir, secret_key)
    app.run(host="127.0.0.1", port=port, debug=False)
