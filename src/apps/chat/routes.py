"""
Sendbird Chat PoC: server-side routes only.
Uses Platform API (create user, issue session token). No Sendbird SDK dependency; requests only.
"""
import time
import urllib.parse

import requests
from flask import Blueprint, jsonify, g, request, redirect, session

# Config from this app only
from apps.chat.config import (
    get_sendbird_app_id,
    get_sendbird_api_token,
    get_sendbird_user_id,
    get_sendbird_default_recipient_id,
    is_configured,
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
    Issue session token for the existing Sendbird user mapped to this app user.
    Requires existing session. Does not create users; app user must be mapped via SENDBIRD_USER_ID_MAP.
    """
    if not is_configured():
        return jsonify({"error": "Sendbird not configured"}), 503
    app_user_id = getattr(g, "user_id", None)
    if not app_user_id:
        return jsonify({"error": "Not logged in"}), 401
    sendbird_user_id = get_sendbird_user_id(app_user_id)
    if not sendbird_user_id:
        return jsonify({
            "error": "No Sendbird user linked for this account",
            "detail": "Set SENDBIRD_USER_ID_MAP so this app user maps to an existing Sendbird user_id.",
        }), 400
    ok, token_val, err = _issue_session_token(sendbird_user_id)
    if not ok:
        return jsonify({"error": "Sendbird issue token failed", "detail": err}), 502
    return jsonify({"sendbird_user_id": sendbird_user_id, "session_token": token_val})


@bp.route("/recipient", methods=["GET"])
def recipient():
    """
    Return the default 1:1 chat recipient (e.g. daughter) for the current user.
    Client uses this to open the distinct group channel between sender and recipient.
    """
    if not is_configured():
        return jsonify({"error": "Sendbird not configured"}), 503
    if not getattr(g, "user_id", None):
        return jsonify({"error": "Not logged in"}), 401
    sendbird_recipient_id = get_sendbird_default_recipient_id()
    if not sendbird_recipient_id:
        return jsonify({"error": "No default recipient configured", "detail": "Set SENDBIRD_DEFAULT_RECIPIENT_ID."}), 503
    return jsonify({"sendbird_user_id": sendbird_recipient_id, "name": "Family"})
