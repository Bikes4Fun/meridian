"""
Flask API server for Meridian.
Exposes the same data as in-process services via REST for client/server mode.

WHERE FUNCTIONALITY CAME FROM (required on server; do not remove):
  - container/container.py         → create_service_container(db_path) used here
  - container/calendar_service.py → GET /api/family_circles/<id>/calendar/*
  - container/medication_service.py → GET /api/family_circles/<id>/medications
- container/emergency_service.py → GET /api/family_circles/<id>/contacts, medical-summary, emergency-profile
  - container/contact_service.py  (used by emergency_service; no direct endpoint)

WHERE IT MOVED TO (client uses these instead of container on client):
  - client/remote.py (RemoteTimeService, RemoteCalendarService, etc.) calls this API.

SERVER DEPLOYMENT: This module requires config, container/, and database_management/.
client/, display/, app_factory.py, icons/, and the kiosk client are not needed on the server;
they can be omitted or relocated to a client-only repo.
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import time
import uuid
import datetime
import urllib.parse
import logging
import threading
from dataclasses import asdict
from pathlib import Path

from werkzeug.utils import secure_filename
from flask import (
    Flask,
    abort,
    jsonify,
    request,
    g,
    send_from_directory,
    Response,
    redirect,
    session,
)

# config from shared; server internals relative
try:
    from ...shared.config import (
        get_database_path,
        get_server_host,
        get_server_port,
    )
except ImportError:
    from shared.config import (
        get_database_path,
        get_server_host,
        get_server_port,
    )
from .emergency_profile_pdf import build_pdf
from .container import create_service_container

try:
    from ...apps.chatapp.api import register_chatapp_routes
except ImportError:
    from apps.chatapp.api import register_chatapp_routes

try:
    from ...shared.config import get_uploads_dir
except ImportError:
    from shared.config import get_uploads_dir

_alert_activation_by_family = {}
_alert_activation_lock = threading.Lock()
_logger = logging.getLogger(__name__)

_ENTRY_TOKEN_TTL_SEC = 300  # 5 minutes
_CHAT_ENTRY_TOKEN_PURPOSE = "chat_session_bootstrap"
_USED_CHAT_ENTRY_TOKEN_SIGS = {}
_USED_CHAT_ENTRY_TOKEN_LOCK = threading.Lock()

_MAX_CARE_RECIPIENT_DNR_BYTES = 20 * 1024 * 1024
_DNR_UPLOAD_EXTS = frozenset(
    {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
)


def _get_alert_activated(family_circle_id: str) -> bool:
    with _alert_activation_lock:
        return bool(_alert_activation_by_family.get(family_circle_id, False))


def _set_alert_activated(family_circle_id: str, activated: bool) -> bool:
    with _alert_activation_lock:
        _alert_activation_by_family[family_circle_id] = bool(activated)
        return _alert_activation_by_family[family_circle_id]


def _create_chat_entry_token(
    secret: str,
    user_id: str,
    family_circle_id: str,
    sendbird_user_id: str = "",
    display_name: str = "",
    auto_start_call: bool = False,
) -> str:
    """Create a signed token for chat entry. Valid for _ENTRY_TOKEN_TTL_SEC."""
    payload = {
        "purpose": _CHAT_ENTRY_TOKEN_PURPOSE,
        "user_id": user_id,
        "family_circle_id": family_circle_id,
        "sendbird_user_id": sendbird_user_id,
        "display_name": display_name,
        "auto_start_call": bool(auto_start_call),
        "exp": int(time.time()) + _ENTRY_TOKEN_TTL_SEC,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        .rstrip(b"=")
        .decode()
    )
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return payload_b64 + "." + sig


def _verify_chat_entry_token(secret: str, token: str) -> dict | None:
    """Verify token, return payload dict or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts[0], parts[1]
        payload_b64_padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded).decode())
        exp = int(payload.get("exp", 0) or 0)
        if exp < time.time():
            return None
        if (payload.get("purpose") or "") != _CHAT_ENTRY_TOKEN_PURPOSE:
            return None
        expected = hmac.new(
            secret.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        now = int(time.time())
        with _USED_CHAT_ENTRY_TOKEN_LOCK:
            expired_sigs = [
                token_sig
                for token_sig, token_exp in _USED_CHAT_ENTRY_TOKEN_SIGS.items()
                if int(token_exp or 0) <= now
            ]
            for token_sig in expired_sigs:
                _USED_CHAT_ENTRY_TOKEN_SIGS.pop(token_sig, None)
            if sig in _USED_CHAT_ENTRY_TOKEN_SIGS:
                return None
            _USED_CHAT_ENTRY_TOKEN_SIGS[sig] = exp
        return payload
    except Exception:
        return None


def create_server_app(db_path=None):
    """Create Flask app and register API routes.
    Functionality is provided by container (via create_service_container).
    Kiosk uses api_client.create_kiosk_remote() to call this API."""

    # TODO: if we are using container, should we ever be using database manager functions alone?
    db_path = db_path or get_database_path()
    container = create_service_container(db_path)
    # TODO: whats the point here if it isn't being checked?
    container.ensure_schema()

    app = Flask(__name__)
    _secret = os.environ.get("SECRET_KEY")
    if not _secret:
        _secret = "dev-secret-change-in-production"
    app.secret_key = _secret
    # Must be identical on every worker (Railway/gunicorn); per-process time.time() breaks sessions across workers.
    app.config["SESSION_SERVER_ID"] = hashlib.sha256(
        (app.secret_key + ":meridian_web_session").encode()
    ).hexdigest()[:32]
    _sess_max = int(os.environ.get("MERIDIAN_SESSION_MAX_AGE_SEC", "86400"))
    _sess_idle = int(os.environ.get("MERIDIAN_SESSION_IDLE_SEC", "1800"))
    app.config["MERIDIAN_SESSION_MAX_AGE_SEC"] = _sess_max
    app.config["MERIDIAN_SESSION_IDLE_SEC"] = _sess_idle
    app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(seconds=_sess_max)

    def _session_clocks_ok() -> bool:
        """Absolute max age + idle timeout. Missing stamps (older cookies): set now and allow once."""
        now = int(time.time())
        login_at = session.get("_login_at")
        last = session.get("_last_activity")
        if login_at is None or last is None:
            session["_login_at"] = now
            session["_last_activity"] = now
            return True
        max_age = int(app.config.get("MERIDIAN_SESSION_MAX_AGE_SEC", 86400))
        idle = int(app.config.get("MERIDIAN_SESSION_IDLE_SEC", 1800))
        try:
            login_i = int(login_at)
            last_i = int(last)
        except (TypeError, ValueError):
            return False
        if now - login_i > max_age:
            return False
        if now - last_i > idle:
            return False
        return True

    def _session_valid():
        """Session matches server id and is within max age + idle limits."""
        sid = session.get("_sid")
        if not sid or sid != app.config.get("SESSION_SERVER_ID"):
            return False
        return _session_clocks_ok()

    def _touch_session_activity_if_cookie_auth() -> None:
        """Refresh idle deadline when the browser session cookie is the auth path (not header-based kiosk API)."""
        if request.headers.get("X-User-Id") and request.headers.get("X-Family-Circle-Id"):
            return
        if not session.get("user_id"):
            return
        if not _session_valid():
            return
        session["_last_activity"] = int(time.time())

    @app.after_request
    def add_cors(resp):
        # Security: with Allow-Credentials, only reflect Origin when allowlisted (CORS_ORIGIN).
        # Do not add a blind elif req_origin: echo Origin—that enables credentialed cross-origin
        # abuse from untrusted sites when cookies are sent (e.g. SameSite=None).
        origins = [
            o.strip()
            for o in (os.environ.get("CORS_ORIGIN") or "").split(",")
            if o.strip()
        ]
        req_origin = request.headers.get("Origin", "").strip()
        if origins and req_origin and req_origin in origins:
            resp.headers["Access-Control-Allow-Origin"] = req_origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        elif origins:
            resp.headers["Access-Control-Allow-Origin"] = origins[0]
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        elif req_origin:
            # Browsers reject Access-Control-Allow-Origin: * when fetch uses credentials: 'include'
            # (e.g. webapp login). Reflecting Origin matches that case; prefer explicit CORS_ORIGIN in production.
            resp.headers["Access-Control-Allow-Origin"] = req_origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-User-Id, X-Family-Circle-Id"
        )
        return resp

    @app.after_request
    def _log_request_response(resp):
        """Placeholder for request/response logging (disabled)."""
        return resp

    @app.before_request
    def handle_options():
        if request.method == "OPTIONS":
            return Response(status=204)

    def _webapp_public_path(path: str) -> bool:
        """Paths that need no session (static assets, login page, chatapp/kiosk shells)."""
        if path in (
            "/login.html",
            "/app.js",
            "/meridian_api_base.js",
            "/style.css",
        ):
            return True
        if path in ("/chatapp", "/kiosk"):
            return True
        if path.startswith(
            ("/chatapp/", "/kiosk/", "/fonts/", "/shared/", "/brand/")
        ):
            return True
        return False

    @app.before_request
    def set_user_id():
        """Resolve user_id and family_circle_id from headers or session. Fail if missing."""
        if request.path in (
            "/api/health",
            "/api/login",
            "/api/logout",
            "/auth",
            "/kiosk-auth",
        ):
            g.user_id = None
            g.family_circle_id = None
            return
        if request.path == "/api/users" and request.method == "POST":
            g.user_id = None
            g.family_circle_id = None
            return
        if _webapp_public_path(request.path):
            g.user_id = None
            g.family_circle_id = None
            return

        # All /api/*: JSON clients — 401 if unauthenticated (no redirect)
        if request.path.startswith("/api"):
            # chat-session-bootstrap: new webview; token verified in handler.
            if request.path == "/api/chat/chat-session-bootstrap":
                g.user_id = None
                g.family_circle_id = None
                return

            # /api/session: session only.
            if request.path == "/api/session":
                if not _session_valid():
                    session.clear()
                    abort(401, "Not logged in")
                uid = session.get("user_id")
                fid = session.get("family_circle_id")
                if not uid or not fid:
                    abort(401, "Not logged in")
                g.user_id = uid
                g.family_circle_id = fid
                _touch_session_activity_if_cookie_auth()
                return

            # chat-session-url: session OR X-User-Id + X-Family-Circle-Id (kiosk uses headers).
            if request.path == "/api/chat/chat-session-url":
                uid = request.headers.get("X-User-Id")
                fid = request.headers.get("X-Family-Circle-Id")
                if (not uid or not fid) and _session_valid():
                    uid = uid or session.get("user_id")
                    fid = fid or session.get("family_circle_id")
                elif not uid or not fid:
                    session.clear()
                if not uid or not fid:
                    abort(
                        401,
                        "Log in at /login first or provide X-User-Id and X-Family-Circle-Id",
                    )
                g.user_id = uid
                g.family_circle_id = fid
                _touch_session_activity_if_cookie_auth()
                return
            # API: headers or session
            user_id = request.headers.get("X-User-Id")
            family_circle_id = request.headers.get("X-Family-Circle-Id")
            if not user_id or not family_circle_id:
                if _session_valid():
                    uid = session.get("user_id")
                    fid = session.get("family_circle_id")
                    if uid and fid:
                        user_id = uid
                        family_circle_id = fid
                else:
                    session.clear()
            if not user_id:
                abort(401, "X-User-Id header required")
            if not family_circle_id:
                abort(401, "X-Family-Circle-Id header required")
            g.user_id = user_id
            g.family_circle_id = family_circle_id
            _touch_session_activity_if_cookie_auth()
            return

        # Remaining routes: webapp HTML and other non-API paths — session required (browser redirect)
        if not _session_valid():
            session.clear()
            dest = request.full_path or "/"
            return redirect(
                "/login.html?next=" + urllib.parse.quote(dest, safe="")
            )
        uid = session.get("user_id")
        fid = session.get("family_circle_id")
        if not uid or not fid:
            dest = request.full_path or "/"
            return redirect(
                "/login.html?next=" + urllib.parse.quote(dest, safe="")
            )
        g.user_id = uid
        g.family_circle_id = fid
        _touch_session_activity_if_cookie_auth()

    app.config["container"] = container

    def _set_authenticated_session(user_id: str, family_circle_id: str) -> None:
        """Canonical session auth write path: set identity + server id marker."""
        session.permanent = True
        now = int(time.time())
        session["user_id"] = user_id
        session["family_circle_id"] = family_circle_id
        session["_sid"] = app.config.get("SESSION_SERVER_ID", "")
        session["_login_at"] = now
        session["_last_activity"] = now

    def _session_identity_from_payload(payload: dict) -> tuple[str, str]:
        """Extract normalized identity from signed payload."""
        user_id = (payload.get("user_id") or "").strip()
        family_circle_id = (payload.get("family_circle_id") or "").strip()
        return user_id, family_circle_id

    def _chat_redirect_path_from_payload(payload: dict) -> str:
        """Build chat destination path from signed payload context."""
        path = "/chatapp/chat.html"
        recipient_sb = (payload.get("sendbird_user_id") or "").strip()
        recipient_name = (payload.get("display_name") or "").strip()
        auto_start_call = bool(payload.get("auto_start_call"))
        if recipient_sb:
            path += "?sendbird_user_id=" + urllib.parse.quote(recipient_sb)
            if recipient_name:
                path += "&display_name=" + urllib.parse.quote(recipient_name)
            if auto_start_call:
                path += "&auto_start_call=1"
        return path

    @app.route("/api/chat/chat-session-url", methods=["GET"])
    def api_chat_session_url():
        """Returns a URL; when opened in a webview, establishes session for chat. Auth: session or X-User-Id + X-Family-Circle-Id.
        recipient_sendbird_user_id, recipient_display_name = who the kiosk user will chat WITH (from headers).
        """
        recipient_sb = (
            request.args.get("recipient_sendbird_user_id")
            or request.args.get("sendbird_user_id")
            or ""
        ).strip()
        recipient_name = (
            request.args.get("recipient_display_name")
            or request.args.get("display_name")
            or ""
        ).strip()
        auto_start_call = (
            (request.args.get("auto_start_call") or "").strip().lower()
            in ("1", "true", "yes", "on")
        )
        token = _create_chat_entry_token(
            app.secret_key,
            g.user_id,
            g.family_circle_id,
            recipient_sb,
            recipient_name,
            auto_start_call=auto_start_call,
        )
        base_url = request.url_root.rstrip("/")
        bootstrap_url = f"{base_url}/api/chat/chat-session-bootstrap?token={urllib.parse.quote(token)}"
        return jsonify({"url": bootstrap_url})

    @app.route("/api/chat/chat-session-bootstrap", methods=["GET"])
    def api_chat_session_bootstrap():
        """URL target. Verifies token, sets session cookie, redirects to chatapp. For webapp/kiosk/mobile opening chat in a fresh webview."""
        token = (request.args.get("token") or "").strip()
        if not token:
            return jsonify({"error": "token required"}), 400
        payload = _verify_chat_entry_token(app.secret_key, token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 403
        user_id, family_circle_id = _session_identity_from_payload(payload)
        if not user_id or not family_circle_id:
            return jsonify({"error": "Invalid token payload"}), 403
        _set_authenticated_session(user_id, family_circle_id)
        return redirect(_chat_redirect_path_from_payload(payload))

    user_svc = container.get_user_service()
    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    contact_svc = container.get_contact_service()
    location_svc = container.get_location_service()
    emergency_svc = container.get_emergency_service()
    family_svc = container.get_family_service()
    care_recipient_svc = container.get_care_recipient_service()
    photo_upload_svc = container.get_photo_upload_service()
    sendbird_svc = container.get_sendbird_service()
    call_signal_svc = container.get_call_signal_service()

    def _parse_date_param():
        """Parse optional ?date=YYYY-MM-DD from request (TV's local date). Use for calendar 'current' endpoints."""
        s = request.args.get("date")
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _require_family_access(family_circle_id):
        """Verify requester has access to family_circle_id. Abort 403 if not."""
        if family_circle_id != g.family_circle_id:
            abort(403, "family circle mismatch")

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.route("/api/family_circles/<family_circle_id>", methods=["POST"])
    def api_create_family_circle(family_circle_id):
        """Create family circle if not exists."""
        _require_family_access(family_circle_id)
        r = family_svc.add_family_circle(family_circle_id)
        return jsonify({"data": True}), 201

    @app.route("/api/users", methods=["POST"])
    def api_create_user():
        """Create or replace user. No auth (new users have no credentials)."""
        data = request.get_json() or {}
        user_id = data.get("id")
        if not user_id:
            return jsonify({"error": "id required"}), 400
        r = user_svc.add_user(
            user_id=user_id,
            display_name=data.get("display_name") or "",
            photo_filename=data.get("photo_filename"),
            # TODO far future security: new users may be invited to a family and have an auth code etc but shouldn't be able to simply join a family
            family_circle_id=data.get("family_circle_id"),
            sendbird_user_id=data.get("sendbird_user_id"),
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data}), 201

    @app.route(
        "/api/family_circles/<family_circle_id>/family-members", methods=["GET", "POST"]
    )
    def api_family_members(family_circle_id):
        """GET: list family members. POST: add existing user to family."""
        _require_family_access(family_circle_id)
        if request.method == "POST":
            data = request.get_json() or {}
            user_id = data.get("id") or data.get("user_id")
            if not user_id:
                return jsonify({"error": "id or user_id required"}), 400
            r = family_svc.add_user_to_family(user_id, family_circle_id)
            return jsonify({"data": True}), 201
        r = family_svc.get_family_members(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        base = request.url_root.rstrip("/")
        members = [dict(m) for m in (r.data or [])]
        for m in members:
            m["photo_url"] = (
                "%s/api/users/%s/photo" % (base, m["id"]) if m.get("id") else None
            )
        return jsonify({"data": members})

    @app.route(
        "/api/family_circles/<family_circle_id>/contacts", methods=["GET", "POST"]
    )
    def api_contacts(family_circle_id):
        """GET: all contacts. POST: add contact. Kiosk loads once at boot; includes photo_filename, sendbird_user_id."""
        _require_family_access(family_circle_id)
        if request.method == "POST":
            data = request.get_json() or {}
            if not data.get("id"):
                return jsonify({"error": "id required"}), 400
            r = contact_svc.add_contact(
                contact_id=data.get("id"),
                family_circle_id=family_circle_id,
                display_name=data.get("display_name"),
                phone=data.get("phone"),
                email=data.get("email"),
                birthday=data.get("birthday"),
                relationship=data.get("relationship"),
                emergency_priority=data.get("emergency_priority"),
                photo_filename=data.get("photo_filename"),
                notes=data.get("notes"),
                sendbird_user_id=data.get("sendbird_user_id"),
            )
            if not r.success:
                return jsonify({"error": "add contact failed"}), 500
            return jsonify({"data": True}), 201
        r = contact_svc.get_all_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": [asdict(c) for c in (r.data or [])]})

    @app.route("/api/family_circles/<family_circle_id>/care-recipient", methods=["PUT"])
    def api_update_care_recipient(family_circle_id):
        """Update care recipient profile. Use set_contact_role for proxy/poa."""
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        r = care_recipient_svc.update_care_recipient(family_circle_id, data)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/contact-roles", methods=["POST"])
    def api_set_contact_role(family_circle_id):
        """Assign contact role (medical_proxy, poa)."""
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        role = data.get("role")
        contact_id = data.get("contact_id")
        if not role or not contact_id:
            return jsonify({"error": "role and contact_id required"}), 400
        r = care_recipient_svc.set_contact_role(family_circle_id, role, contact_id)
        return jsonify({"data": True})

    @app.route(
        "/api/family_circles/<family_circle_id>/medication-times", methods=["POST"]
    )
    def api_add_medication_time(family_circle_id):
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name required"}), 400
        t = data.get("time")
        if t == "null":
            t = None
        r = medication_svc.add_medication_time(family_circle_id, name, t)
        return jsonify({"data": True}), 201

    @app.route("/api/family_circles/<family_circle_id>/allergies", methods=["POST"])
    def api_add_allergy(family_circle_id):
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        care_recipient_user_id = data.get("care_recipient_user_id")
        allergen = data.get("allergen")
        if not care_recipient_user_id or not allergen:
            return (
                jsonify({"error": "care_recipient_user_id and allergen required"}),
                400,
            )
        r = care_recipient_svc.add_allergy(care_recipient_user_id, allergen)
        return jsonify({"data": True}), 201

    @app.route("/api/family_circles/<family_circle_id>/conditions", methods=["POST"])
    def api_add_condition(family_circle_id):
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        care_recipient_user_id = data.get("care_recipient_user_id")
        condition = data.get("condition")
        if not care_recipient_user_id or not condition:
            return (
                jsonify({"error": "care_recipient_user_id and condition required"}),
                400,
            )
        r = care_recipient_svc.add_condition(
            care_recipient_user_id,
            condition,
            data.get("diagnosis_date"),
            data.get("notes"),
        )
        return jsonify({"data": True}), 201

    @app.route(
        "/api/family_circles/<family_circle_id>/named-places", methods=["GET", "POST"]
    )
    def api_named_places(family_circle_id):
        _require_family_access(family_circle_id)
        if request.method == "POST":
            data = request.get_json() or {}
            loc_id = data.get("location_id")
            loc_name = data.get("location_name")
            if not loc_id or not loc_name:
                return jsonify({"error": "location_id and location_name required"}), 400
            gps = data.get("gps", "")
            gps_lat, gps_lng = None, None
            if gps:
                parts = str(gps).split(",")
                if len(parts) == 2:
                    try:
                        gps_lat, gps_lng = float(parts[0]), float(parts[1])
                    except ValueError:
                        pass
            r = location_svc.add_named_place(
                family_circle_id,
                loc_id,
                loc_name,
                gps_latitude=gps_lat,
                gps_longitude=gps_lng,
                radius_metres=data.get("radius_metres", 150),
            )
            if not r.success:
                return jsonify({"error": "add named place failed"}), 500
            return jsonify({"data": True}), 201
        r = location_svc.get_named_places(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/users/<user_id>/photo")
    def api_serve_photo(user_id):
        # TODO: remove api.py queries and maybe even database_manager? (user container?)
        """Serve user photo. User must be in requester's family. Rejects path traversal in filename."""
        fn = user_svc.get_user_photo_filename(user_id, g.family_circle_id)
        if not fn:
            abort(404)
        uploads = get_uploads_dir()
        return send_from_directory(uploads, fn, as_attachment=False)

    @app.route(
        "/api/family_circles/<family_circle_id>/care-recipient-photo",
        methods=["POST"],
    )
    def api_care_recipient_photo(family_circle_id):
        """Multipart: care_recipient_user_id + photo. Writes uploads basename; updates users + care_recipients."""
        _require_family_access(family_circle_id)
        cr_id = (request.form.get("care_recipient_user_id") or "").strip()
        up = request.files.get("photo")
        if not cr_id or not up or not (up.filename or "").strip():
            return jsonify({"error": "care_recipient_user_id and photo required"}), 400

        data, err, status = photo_upload_svc.apply_care_recipient_profile_photo(
            family_circle_id, cr_id, up, get_uploads_dir()
        )
        if err:
            return jsonify({"error": err}), status
        return jsonify({"data": data})

    @app.route(
        "/api/family_circles/<family_circle_id>/care-recipient-dnr-document",
        methods=["POST"],
    )
    def api_care_recipient_dnr_document(family_circle_id):
        """Multipart: care_recipient_user_id + document (PDF or image). Stores basename on care_recipients."""
        _require_family_access(family_circle_id)
        cr_id = (request.form.get("care_recipient_user_id") or "").strip()
        up = request.files.get("document")
        if not cr_id or not up or not (up.filename or "").strip():
            return jsonify({"error": "care_recipient_user_id and document required"}), 400
        if not care_recipient_svc.care_recipient_exists(family_circle_id, cr_id):
            return jsonify({"error": "care recipient not found"}), 404

        orig = secure_filename(up.filename) or "document.pdf"
        ext = Path(orig).suffix.lower()
        if ext not in _DNR_UPLOAD_EXTS:
            return (
                jsonify({"error": "allowed types: pdf, doc, docx, jpg, png, gif, webp"}),
                400,
            )
        new_fn = f"{uuid.uuid4().hex}{ext}"

        uploads = get_uploads_dir()
        os.makedirs(uploads, exist_ok=True)
        dest = os.path.join(uploads, new_fn)
        up.save(dest)
        if os.path.getsize(dest) > _MAX_CARE_RECIPIENT_DNR_BYTES:
            try:
                os.remove(dest)
            except OSError:
                pass
            return jsonify({"error": "document too large"}), 413

        old_basename = care_recipient_svc.get_dnr_document_basename(
            family_circle_id, cr_id
        )
        dr = care_recipient_svc.set_dnr_document_path(
            family_circle_id, cr_id, new_fn
        )
        if not dr.success:
            try:
                os.remove(dest)
            except OSError:
                pass
            return jsonify({"error": dr.error}), 500

        photo_upload_svc.remove_replaced_file_in_uploads_dir(
            uploads, old_basename, new_fn
        )

        return jsonify({"data": dr.data})

    @app.route(
        "/api/family_circles/<family_circle_id>/care-recipients/<care_recipient_user_id>/dnr-document"
    )
    def api_serve_care_recipient_dnr_document(
        family_circle_id, care_recipient_user_id
    ):
        """POLST / DNR scan for kiosk and webapp; same auth as emergency profile."""
        _require_family_access(family_circle_id)
        fn = care_recipient_svc.get_dnr_document_basename(
            family_circle_id, care_recipient_user_id
        )
        if not fn:
            abort(404)
        uploads = get_uploads_dir()
        path = os.path.join(uploads, fn)
        if not os.path.isfile(path):
            abort(404)
        uploads_abs = os.path.abspath(uploads)
        if not os.path.abspath(path).startswith(uploads_abs + os.sep):
            abort(404)
        mt, _ = mimetypes.guess_type(fn)
        if not mt:
            mt = "application/octet-stream"
        return send_from_directory(uploads, fn, mimetype=mt, as_attachment=False)

    @app.route("/api/family_circles/<family_circle_id>/calendar/headers")
    def api_calendar_headers(family_circle_id):
        _require_family_access(family_circle_id)
        r = calendar_svc.get_day_headers()
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/calendar/month")
    def api_calendar_month(family_circle_id):
        _require_family_access(family_circle_id)
        ref = _parse_date_param()
        r = calendar_svc.get_current_month_data(reference_date=ref)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/calendar/date")
    def api_calendar_date(family_circle_id):
        _require_family_access(family_circle_id)
        ref = _parse_date_param()
        return jsonify({"data": calendar_svc.get_current_date(reference_date=ref)})

    @app.route("/api/family_circles/<family_circle_id>/calendar/events")
    def api_calendar_events(family_circle_id):
        _require_family_access(family_circle_id)
        date = request.args.get("date")
        date_from = request.args.get("from")
        date_to = request.args.get("to")
        if date_from and date_to:
            r = calendar_svc.get_events_in_range(
                date_from, date_to, family_circle_id=family_circle_id
            )
        elif date:
            r = calendar_svc.get_events_for_date(date, family_circle_id=family_circle_id)
        else:
            return jsonify({"error": "missing date or from+to"}), 400
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route(
        "/api/family_circles/<family_circle_id>/calendar/events", methods=["POST"]
    )
    def api_calendar_events_post(family_circle_id):
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        event_id = data.get("id") or (f"evt_{int(time.time() * 1000)}")
        title = data.get("title")
        start_time = data.get("start_time")
        if not title or not start_time:
            return jsonify({"error": "title and start_time required"}), 400
        r = calendar_svc.add_event(
            family_circle_id,
            event_id=event_id,
            title=title,
            start_time=start_time,
            description=data.get("description"),
            location=data.get("location"),
            end_time=data.get("end_time"),
            driver_name=data.get("driver_name"),
            driver_contact_id=data.get("driver_contact_id"),
            pickup_time=data.get("pickup_time"),
            leave_time=data.get("leave_time"),
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route(
        "/api/family_circles/<family_circle_id>/calendar/events/<event_id>",
        methods=["PUT"],
    )
    def api_calendar_event_put(family_circle_id, event_id):
        _require_family_access(family_circle_id)
        data = request.get_json() or {}
        r = calendar_svc.update_event(
            family_circle_id,
            event_id=event_id,
            title=data.get("title"),
            description=data.get("description"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            location=data.get("location"),
            driver_name=data.get("driver_name"),
            driver_contact_id=data.get("driver_contact_id"),
            pickup_time=data.get("pickup_time"),
            leave_time=data.get("leave_time"),
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route(
        "/api/family_circles/<family_circle_id>/calendar/events/<event_id>",
        methods=["DELETE"],
    )
    def api_calendar_event_delete(family_circle_id, event_id):
        _require_family_access(family_circle_id)
        r = calendar_svc.delete_event(family_circle_id, event_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": True})

    @app.route(
        "/api/family_circles/<family_circle_id>/medications", methods=["GET", "POST"]
    )
    def api_medications(family_circle_id):
        _require_family_access(family_circle_id)
        if request.method == "GET":
            r = medication_svc.get_medication_data(family_circle_id)
            if not r.success:
                return jsonify({"error": r.error}), 500
            return jsonify({"data": r.data})
        body = request.get_json() or {}
        name = body.get("name")
        medication_times = body.get("medication_times") or []
        if not name:
            return jsonify({"error": "name required"}), 400
        if not medication_times:
            return jsonify({"error": "medication_times required"}), 400
        r = medication_svc.add_medication(
            family_circle_id,
            name,
            medication_times,
            dosage=body.get("dosage"),
            frequency=body.get("frequency"),
            notes=body.get("notes"),
            max_daily=body.get("max_daily"),
            fda_rxcui=body.get("fda_rxcui"),
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data}), 201

    @app.route(
        "/api/family_circles/<family_circle_id>/medications/<int:medication_id>",
        methods=["GET", "PUT", "DELETE"],
    )
    def api_medication(family_circle_id, medication_id):
        _require_family_access(family_circle_id)
        if request.method == "GET":
            r = medication_svc.get_medication_for_edit(family_circle_id, medication_id)
            if not r.success:
                return jsonify({"error": r.error}), 404
            return jsonify({"data": r.data})
        if request.method == "PUT":
            body = request.get_json() or {}
            name = body.get("name")
            medication_times = body.get("medication_times") or []
            if not name:
                return jsonify({"error": "name required"}), 400
            if not medication_times:
                return jsonify({"error": "medication_times required"}), 400
            r = medication_svc.update_medication(
                family_circle_id,
                medication_id,
                name,
                medication_times,
                dosage=body.get("dosage"),
                frequency=body.get("frequency"),
                fda_rxcui=body.get("fda_rxcui"),
            )
            if not r.success:
                return jsonify({"error": r.error}), 400
            return jsonify({"data": r.data})
        r = medication_svc.delete_medication(family_circle_id, medication_id)
        if not r.success:
            return jsonify({"error": r.error}), 404
        return jsonify({"data": True})

    @app.route(
        "/api/family_circles/<family_circle_id>/medications/<int:medication_id>/mark-taken",
        methods=["POST"],
    )
    def api_medication_mark_taken(family_circle_id, medication_id):
        _require_family_access(family_circle_id)
        body = request.get_json() or {}
        time_slot = body.get("time")
        taken = body.get("taken", True)
        if not time_slot:
            return jsonify({"error": "time required (e.g. Morning, Evening)"}), 400
        r = medication_svc.mark_medication_taken(
            family_circle_id, medication_id, time_slot, taken
        )
        if not r.success:
            return jsonify({"error": r.error}), 400
        return jsonify({"data": True})

    @app.route("/api/family_circles/<family_circle_id>/emergency-contacts")
    def api_emergency_contacts(family_circle_id):
        """Only emergency-priority contacts."""
        _require_family_access(family_circle_id)
        r = contact_svc.get_emergency_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": [asdict(c) for c in (r.data or [])]})

    @app.route("/api/family_circles/<family_circle_id>/medical-summary")
    def api_medical_summary(family_circle_id):
        _require_family_access(family_circle_id)
        r = emergency_svc.e_service_get_medical_summary(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/emergency/alert/status")
    def api_alert_status():
        """TODO: Requires user + family (via before_request). Eventually: authorization/role check."""
        return jsonify({"data": {"activated": _get_alert_activated(g.family_circle_id)}})

    @app.route("/api/emergency/alert", methods=["POST"])
    def api_alert():
        """TODO: Requires user + family (via before_request). Eventually: authorization/role check."""
        data = request.get_json() or {}
        activated = _set_alert_activated(
            g.family_circle_id, bool(data.get("activated", False))
        )
        return jsonify({"data": {"activated": activated}})

    @app.route("/api/calls/request", methods=["POST"])
    def api_call_request():
        """Create an incoming-call signal for target user (kiosk poll consumes this)."""
        data = request.get_json() or {}
        to_user_id = (data.get("to_user_id") or "").strip()
        if not to_user_id:
            return jsonify({"error": "to_user_id required"}), 400
        from_sendbird_user_id = sendbird_svc.get_sendbird_user_id_for_app_user(g.user_id)
        from_display_name = user_svc.get_display_name(g.user_id)
        r = call_signal_svc.request_call(
            family_circle_id=g.family_circle_id,
            from_user_id=g.user_id,
            to_user_id=to_user_id,
            from_sendbird_user_id=from_sendbird_user_id,
            from_display_name=from_display_name,
        )
        if not r.success:
            return jsonify({"error": r.error}), 400
        return jsonify({"data": r.data}), 201

    @app.route("/api/calls/incoming", methods=["GET"])
    def api_call_incoming():
        """Return latest pending incoming-call signal for current user."""
        r = call_signal_svc.get_incoming_call(
            family_circle_id=g.family_circle_id, to_user_id=g.user_id
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data or {}})

    @app.route("/api/calls/<int:call_id>/ack", methods=["POST"])
    def api_call_ack(call_id):
        """Acknowledge incoming call so kiosk does not repeatedly open chat."""
        r = call_signal_svc.acknowledge_call(call_id, g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 400
        return jsonify({"data": r.data or {"updated": 0}})

    @app.route("/api/calls/socket-event", methods=["POST"])
    def api_call_socket_event():
        """Client-reported socket lifecycle events (debug visibility in server logs)."""
        data = request.get_json() or {}
        event = (data.get("event") or "").strip()

        if not event:
            return jsonify({"error": "event required"}), 400

        client_source = (data.get("client_source") or "").strip() or "unknown"
        client_device_id = (data.get("client_device_id") or "").strip() or "unknown"
        started_events = {
            "kiosk_sendbird_websocket_connected",
            "sendbird_websocket_connected",
        }
        issue_events = {
            "kiosk_calls_sdk_missing",
            "calls_sdk_missing",
            "kiosk_sendbird_call_setup_failed",
            "sendbird_call_setup_failed",
        }
        if event in started_events:
            _logger.info(
                f"Call socket started event={event} source={client_source} device={client_device_id}"
            )
        elif event in issue_events:
            _logger.info(
                f"Call socket issue event={event} source={client_source} device={client_device_id}"
            )

        return jsonify({"data": {"ok": True}})

    @app.route(
        "/api/family_circles/<family_circle_id>/emergency-profile",
        methods=["GET", "PUT"],
    )
    def api_emergency_profile(family_circle_id):
        _require_family_access(family_circle_id)
        if request.method == "GET":
            r = emergency_svc.get_emergency_profile(family_circle_id)
            if not r.success:
                return jsonify({"error": r.error}), 500
            return jsonify({"data": r.data})

        if (
            request.method != "PUT"
        ):  # TODO: why are we allowing a PUT method in the route, and then 'defensive'ly failing it?
            return  # defensive
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        # TODO: why does emergency profile need to ever PUT or update care recipient?
        care_recipient_svc = container.get_care_recipient_service()
        r = care_recipient_svc.update_care_recipient(family_circle_id, data)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/emergency-profile/pdf")
    def api_emergency_profile_pdf(family_circle_id):
        _require_family_access(family_circle_id)
        r = emergency_svc.get_emergency_profile(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        if not r.data:
            return jsonify({"error": "No emergency profile"}), 404
        pdf_bytes = build_pdf(r.data)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "inline; filename=emergency-profile.pdf"},
        )

    @app.route("/api/session")
    def api_session():
        """Return current session user_id and family_circle_id."""
        return jsonify(
            {
                "user_id": g.user_id,
                "family_circle_id": g.family_circle_id,
            }
        )

    @app.route("/kiosk-auth", methods=["GET"])
    def kiosk_auth():
        """Set session from query params and redirect to /kiosk/. For kiosk auto-login."""
        user_id = (request.args.get("user_id") or "").strip()
        family_circle_id = (request.args.get("family_circle_id") or "").strip()
        if not user_id or not family_circle_id:
            return jsonify({"error": "user_id and family_circle_id required"}), 400
        mem = family_svc.user_belongs_to_family(user_id, family_circle_id)
        if not mem.success:
            return jsonify({"error": mem.error or "Database query failed"}), 500
        if not mem.data:
            return jsonify({"error": "forbidden"}), 403
        _set_authenticated_session(user_id, family_circle_id)
        return redirect("/kiosk/")

    @app.route("/api/login", methods=["POST"])
    def api_login():
        """Fake login: set session from user_id and family_circle_id. For demo/simulated auth."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        user_id = (data.get("user_id") or "").strip()
        family_circle_id = (data.get("family_circle_id") or "").strip()
        if not user_id or not family_circle_id:
            return jsonify({"error": "user_id and family_circle_id required"}), 400
        mem = family_svc.user_belongs_to_family(user_id, family_circle_id)
        if not mem.success:
            return jsonify({"error": mem.error or "Database query failed"}), 500
        if not mem.data:
            return jsonify({"error": "forbidden"}), 403
        _set_authenticated_session(user_id, family_circle_id)
        return jsonify({"ok": True})

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        """Clear session. For switching users."""
        session.clear()
        return jsonify({"ok": True})

    @app.route(
        "/api/family_circles/<family_circle_id>/create_checkin", methods=["POST"]
    )
    def api_create_checkin(family_circle_id):
        """Create a new location check-in."""
        # TODO: use userid for this, not family circle. allowing the user to checkin to multiple families if needed?
        _require_family_access(family_circle_id)
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400

        user_id = data.get("user_id")
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        notes = data.get("notes")
        # location_name is always resolved from GPS in create_checkin; never from client

        if not user_id or latitude is None or longitude is None:
            return (
                jsonify({"error": "user_id, latitude, and longitude are required"}),
                400,
            )
        if user_id != g.user_id:
            return jsonify({"error": "cannot check in for another user"}), 403

        r = location_svc.create_checkin(
            family_circle_id, user_id, latitude, longitude, notes=notes
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data}), 201

    @app.route("/api/family_circles/<family_circle_id>/get_checkins")
    def api_get_checkins(family_circle_id):
        """Get latest check-in per family member. Includes photo_url and photo_filename."""
        _require_family_access(family_circle_id)
        r = location_svc.get_checkins(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        base = request.url_root.rstrip("/")
        data = [dict(row) for row in (r.data or [])]
        for row in data:
            uid = row.get("user_id")
            row["photo_url"] = "%s/api/users/%s/photo" % (base, uid) if uid else None
        return jsonify({"data": data})

    @app.route("/api/device-token", methods=["POST"])
    def api_register_device_token():
        """Register APNs/FCM device token for push. Requires session."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        token = (data.get("token") or "").strip()
        platform = (data.get("platform") or "ios").strip().lower()
        if not token:
            return jsonify({"error": "token required"}), 400
        push_svc = container.get_push_notification_service()
        r = push_svc.register_device_token(g.user_id, token, platform)
        if not r.success:
            return jsonify({"error": r.error}), 400
        return jsonify({"ok": True})

    @app.route(
        "/api/family_circles/<family_circle_id>/where-is-everyone",
        methods=["POST"],
    )
    def api_where_is_everyone(family_circle_id):
        """Request family members to refresh location. Sends push (stub for now)."""
        _require_family_access(family_circle_id)
        push_svc = container.get_push_notification_service()
        r = push_svc.request_location_update(family_circle_id, g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        data = r.data or {}
        return jsonify({"ok": True, "requested_count": data.get("requested_count", 0)})

    # Chatapp routes + static (webapp, chatapp, kiosk) for Railway all-in-one deploy
    _src = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _webapp_dist = os.path.join(_src, "apps", "webapp", "web_server", "dist")
    _chatapp_dist = os.path.join(_src, "apps", "chatapp", "chat_server", "dist")
    _kiosk_web = os.path.join(_src, "apps", "kiosk", "web")
    _webapp_client = os.path.join(_src, "apps", "webapp", "web_client")
    _repo_root = os.path.dirname(_src)
    _kiosk_icons = os.path.join(_repo_root, "assets", "icons")
    if os.path.isfile(os.path.join(_webapp_client, "meridian_api_base.js")):

        @app.route("/meridian_api_base.js")
        def serve_meridian_api_base_js():
            """Source copy in web_client — not tied to webapp dist (kiosk loads this before meds inline)."""
            return send_from_directory(_webapp_client, "meridian_api_base.js")

    if os.path.isdir(_webapp_dist) and os.path.isdir(_chatapp_dist):
        user_svc = container.get_user_service()
        register_chatapp_routes(
            app, sendbird_svc, user_svc, chat_static_prefix="/chatapp"
        )

        @app.route("/")
        @app.route("/index.html")
        def serve_index():
            """Serve dashboard HTML; inject session so the client need not rely on a second /api/session round-trip."""
            index_path = os.path.join(_webapp_dist, "index.html")
            with open(index_path, encoding="utf-8") as f:
                html = f.read()
            uid = session.get("user_id") or ""
            fid = session.get("family_circle_id") or ""
            boot = json.dumps({"user_id": uid, "family_circle_id": fid})
            idle_sec = int(app.config.get("MERIDIAN_SESSION_IDLE_SEC", 1800))
            inject = (
                f"<script>window.__MERIDIAN_SESSION__={boot};"
                f"window.__MERIDIAN_IDLE_LOGOUT_SEC__={idle_sec};</script>"
            )
            if "</head>" in html:
                html = html.replace("</head>", inject + "</head>", 1)
            else:
                html = inject + html
            resp = Response(html, mimetype="text/html; charset=utf-8")
            resp.headers["Cache-Control"] = "no-store"
            return resp

        @app.route("/login.html")
        def serve_login():
            return send_from_directory(_webapp_dist, "login.html")

        @app.route("/ice-editor")
        @app.route("/ice_editor.html")
        def serve_ice_editor():
            return send_from_directory(_webapp_dist, "ice_editor.html")

        @app.route("/info.html")
        def serve_info_guide():
            return send_from_directory(_webapp_dist, "info.html")

        @app.route("/meridian_medications_inline.js")
        def serve_meridian_medications_inline_js():
            return send_from_directory(_webapp_dist, "meridian_medications_inline.js")

        @app.route("/app.js")
        def serve_app_js():
            return send_from_directory(_webapp_dist, "app.js")

        @app.route("/events.js")
        def serve_events_js():
            return send_from_directory(_webapp_dist, "events.js")

        @app.route("/medications.js")
        def serve_medications_js():
            return send_from_directory(_webapp_dist, "medications.js")

        @app.route("/ice_editor.js")
        def serve_ice_editor_js():
            return send_from_directory(_webapp_dist, "ice_editor.js")

        @app.route("/style.css")
        def serve_style_css():
            return send_from_directory(_webapp_dist, "style.css")

        _webapp_brand = os.path.join(_webapp_dist, "brand")

        @app.route("/brand/<path:path>")
        def serve_webapp_brand(path):
            if not os.path.isdir(_webapp_brand):
                abort(404)
            if path.startswith("/") or ".." in path:
                abort(404)
            _, ext = os.path.splitext(path)
            if ext.lower() not in {".png", ".svg", ".webp", ".ico"}:
                abort(404)
            return send_from_directory(_webapp_brand, path)

        @app.route("/fonts/<path:path>")
        def serve_fonts(path):
            return send_from_directory(os.path.join(_webapp_dist, "fonts"), path)

        @app.route("/shared/<path:path>")
        def serve_shared(path):
            allowed_extensions = {".css", ".woff", ".woff2", ".ttf", ".otf", ".eot"}
            _, ext = os.path.splitext(path)
            if ext.lower() not in allowed_extensions:
                abort(404)
            return send_from_directory(os.path.join(_src, "shared"), path)

        @app.route("/chatapp/")
        @app.route("/chatapp/<path:path>")
        def serve_chat(path=""):
            if not path:
                path = "chat.html"
            return send_from_directory(_chatapp_dist, path)

        if os.path.isdir(_kiosk_web):

            @app.route("/kiosk/")
            @app.route("/kiosk/<path:path>")
            def serve_kiosk(path=""):
                if not path:
                    path = "kiosk.html"
                if path.startswith("icons/") and os.path.isdir(_kiosk_icons):
                    return send_from_directory(_kiosk_icons, path[6:])
                return send_from_directory(_kiosk_web, path)

    return app


def run_server(host=None, port=None):
    """Create and run the server. Host/port from config (get_server_host, get_server_port) when not passed."""
    app = create_server_app()
    if app is None:
        raise RuntimeError("create_server_app() returned None")
    try:
        import flask.cli

        flask.cli.show_server_banner = lambda *_args: None
    except Exception:
        pass
    host = host if host is not None else get_server_host()
    port = port if port is not None else get_server_port()
    app.run(host=host, port=port, debug=False)
