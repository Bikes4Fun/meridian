"""
Sendbird Chat PoC: server-side routes only.
Uses Platform API to issue session tokens only. Users must already exist in Sendbird; we do not create them.
"""
import time
import urllib.parse

import requests
from flask import Blueprint, jsonify, g, request, redirect, session

# Config from this app only
from apps.chat.config import (
    get_sendbird_app_id,
    get_sendbird_api_token,
    is_configured,
    get_sendbird_user_id,
    get_sendbird_chat_with_user_id,
)

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _api_url() -> str:
    """Base URL for Sendbird Platform API: https://api-{app_id}.sendbird.com/v3"""
    app_id = get_sendbird_app_id()
    if not app_id:
        return ""
    return "https://api-{}.sendbird.com/v3".format(app_id)


def _headers() -> dict:
    """Headers for Platform API: Api-Token and Content-Type."""
    return {
        "Api-Token": get_sendbird_api_token(),
        "Content-Type": "application/json; charset=utf8",
    }


def _issue_session_token(user_id: str) -> tuple[bool, str, str]:
    """
    Issue a session token for user_id. Returns (success, token_or_error, error_detail).
    Token valid 7 days (Sendbird default if expires_at not sent).
    """
    base = _api_url()
    if not base:
        return False, "", "Sendbird not configured"
    # expires_at: Unix timestamp in milliseconds. 7 days from now.
    expires_at = int((time.time() + 7 * 24 * 3600) * 1000)
    payload = {"expires_at": expires_at}
    # user_id may contain @ etc.; must be URL-encoded in path
    encoded_user_id = urllib.parse.quote(user_id, safe="")
    r = requests.post(
        base + "/users/" + encoded_user_id + "/token",
        headers=_headers(),
        json=payload,
        timeout=10,
    )
    if r.status_code != 200:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        msg = body.get("message", r.text)
        return False, "", msg
    data = r.json()
    token = (data.get("token") or data.get("session_token") or "").strip()
    if not token:
        return False, "", "No token in response"
    return True, token, ""


@bp.route("/entry", methods=["GET"])
def entry():
    """
    Set session from query params and redirect to /chat. For kiosk in-app webview only.
    Security: allowed only from localhost so remote users cannot hijack a session.
    Same session flow as POST /api/login; this is just a GET that sets session and redirects.
    """
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"error": "Forbidden: entry only from localhost"}), 403
    user_id = (request.args.get("user_id") or "").strip()
    family_circle_id = (request.args.get("family_circle_id") or "").strip()
    if not user_id or not family_circle_id:
        return jsonify({"error": "user_id and family_circle_id required"}), 400
    session["user_id"] = user_id
    session["family_circle_id"] = family_circle_id
    return redirect("/chat")


@bp.route("/config", methods=["GET"])
def config():
    """Return app_id for the client SDK. No auth required if you want to show login first; we require session."""
    if not is_configured():
        return jsonify({"error": "Sendbird not configured (SENDBIRD_APP_ID, SENDBIRD_API_TOKEN)"}), 503
    return jsonify({"app_id": get_sendbird_app_id()})


@bp.route("/token", methods=["POST"])
def token():
    """
    Issue session token for the current user's Sendbird identity. Users must already exist in Sendbird.
    Requires existing session. Returns Sendbird user_id, session_token, and chat_with_user_id (the other party).
    """
    if not is_configured():
        return jsonify({"error": "Sendbird not configured"}), 503
    app_user_id = getattr(g, "user_id", None)
    family_circle_id = getattr(g, "family_circle_id", None) or ""
    if not app_user_id:
        return jsonify({"error": "Not logged in"}), 401
    sendbird_user_id = get_sendbird_user_id(app_user_id)
    chat_with_user_id = get_sendbird_chat_with_user_id(app_user_id, family_circle_id)
    if not sendbird_user_id:
        return jsonify({"error": "Sendbird user mapping not configured for this user", "detail": "Set SENDBIRD_DEMO_APP_USER_ID and SENDBIRD_DEMO_SENDBIRD_USER_ID (or add DB mapping)"}), 400
    if not chat_with_user_id:
        return jsonify({"error": "Chat recipient not configured", "detail": "Set SENDBIRD_DEMO_CHAT_WITH_ID (Sendbird user id of the person they message, e.g. daughter)"}), 400
    ok, token_val, err = _issue_session_token(sendbird_user_id)
    if not ok:
        return jsonify({"error": "Sendbird issue token failed", "detail": err}), 502
    return jsonify({
        "user_id": sendbird_user_id,
        "session_token": token_val,
        "chat_with_user_id": chat_with_user_id,
    })
