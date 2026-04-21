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

import hashlib
import json
import mimetypes
import os
import tempfile
import time
import uuid
import datetime
import urllib.parse
import urllib.request
import urllib.request
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
    send_file,
    Response,
    redirect,
    session,
)

# config from shared; server internals relative
try:
    from ...shared.config import (
        get_database_path,
        get_meridian_ssl_files,
        get_server_host,
        get_server_port,
        get_uploads_dir,
    )
except ImportError:
    from shared.config import (
        get_database_path,
        get_meridian_ssl_files,
        get_server_host,
        get_server_port,
        get_uploads_dir,
    )
try:
    from ...shared.emergency_profile_pdf import build_pdf
except ImportError:
    try:
        from shared.emergency_profile_pdf import build_pdf
    except ImportError:
        build_pdf = None
from .database_services.db_service_registry import create_service_container
from .twilio_voice import register_twilio_voice_routes


_alert_activation_by_family = {}
_alert_activation_lock = threading.Lock()
_logger = logging.getLogger(__name__)

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


def create_server_app(db_path=None):
    """Create Flask app and register API routes.
    Functionality is provided by container (via create_service_container).
    Kiosk uses api_client.create_kiosk_remote() to call this API."""

    # TODO: if we are using container, should we ever be using database manager functions alone?
    db_path = db_path or get_database_path()
    container = create_service_container(db_path)
    # TODO: whats the point here if it isn't being checked?
    if not container.ensure_schema():
        raise RuntimeError("Failed to ensure database schema")

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
        """Paths that need no session (static assets, login page, kiosk shell)."""
        if path in (
            "/login.html",
            "/privacy.html",
            "/terms.html",
            "/app.js",
            "/style.css",
        ):
            return True
        if path == "/kiosk":
            return True
        if path.startswith(("/kiosk/", "/fonts/", "/shared/", "/brand/")):
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
        if request.path.startswith("/twilio/"):
            g.user_id = None
            g.family_circle_id = None
            return
        if _webapp_public_path(request.path):
            g.user_id = None
            g.family_circle_id = None
            return

        # All /api/*: JSON clients — 401 if unauthenticated (no redirect)
        if request.path.startswith("/api"):
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

    user_svc = container.get_user_service()
    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    contact_svc = container.get_contact_service()
    location_svc = container.get_location_service()
    emergency_svc = container.get_emergency_service()
    family_svc = container.get_family_service()
    register_twilio_voice_routes(app, user_svc)

    @app.before_request
    def verify_family_membership():
        """Reject API calls where user_id + family_circle_id are not linked in family_memberships.

        Headers alone used to satisfy _require_family_access when URL family matched X-Family-Circle-Id
        even if X-User-Id was not a member of that family.
        """
        if not request.path.startswith("/api"):
            return
        if request.path in (
            "/api/health",
            "/api/login",
            "/api/logout",
            "/auth",
            "/kiosk-auth",
        ):
            return
        if request.path == "/api/users" and request.method == "POST":
            return
        uid = getattr(g, "user_id", None)
        fid = getattr(g, "family_circle_id", None)
        if not uid or not fid:
            return
        mem = family_svc.user_belongs_to_family(uid, fid)
        if not mem.success:
            return jsonify({"error": mem.error or "Database query failed"}), 500
        if not mem.data:
            return jsonify({"error": "forbidden"}), 403

    care_recipient_svc = container.get_care_recipient_service()
    photo_upload_svc = container.get_photo_upload_service()
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

    def _require_family_permission(permission: str):
        r = family_svc.user_has_permission(g.user_id, g.family_circle_id, permission)
        if not r.success:
            return jsonify({"error": r.error or "Database query failed"}), 500
        if not r.data:
            return jsonify({"error": "forbidden"}), 403
        return None

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
            # They should have an auth code from the admin family member
            # The auth code should reference the family circle id in some way or they should need to input the family circle id
            # The auth code should be a one-time use code that is sent to the user's email or phone
            # The auth code should be valid for a limited time
            # The auth code should be used to verify the user's identity
            # The auth code should be used to create a new user in the database
            # The auth code should be used to link the user to the family circle
            # The auth code should be used to create a new user in the database
            # The admin should receive / maintain a list of auth codes and their status (used, expired, etc.)
            # The admin should be able to revoke auth codes
            # The admin should be able to view the list of users and their family circle memberships
            # The admin should be able to view the list of auth codes and their status
            # The admin should be able to revoke auth codes
            # The admin should be able to view the list of users and their family circle memberships
            # The admin should be able to view the list of auth codes and their status
            # The admin should be able to revoke auth codes
            family_circle_id=None,
            phone=data.get("phone"),
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
        perms_r = family_svc.get_permissions(family_circle_id)
        if not perms_r.success:
            return jsonify({"error": perms_r.error}), 500
        permissions_by_user = perms_r.data or {}
        base = request.url_root.rstrip("/")
        members = [dict(m) for m in (r.data or [])]
        for m in members:
            m["photo_url"] = (
                "%s/api/users/%s/photo" % (base, m["id"]) if m.get("id") else None
            )
            uid = (m.get("id") or "").strip()
            m["permissions"] = permissions_by_user.get(uid, [])
        return jsonify({"data": members})

    @app.route("/api/family_circles/<family_circle_id>/permissions", methods=["GET", "POST"])
    def api_family_permissions(family_circle_id):
        """
        GET: all or a specific user's family/user permissions; ? TODO: clarify what this is for
        POST: grant/revoke a family-scoped permission.
        """
        _require_family_access(family_circle_id)
        if request.method == "GET":
            target_user_id = (request.args.get("user_id") or "").strip()
            if target_user_id and target_user_id != g.user_id:
                can_manage_r = family_svc.can_manage_family_permissions(
                    g.user_id, g.family_circle_id
                )
                if not can_manage_r.success:
                    return jsonify({"error": can_manage_r.error or "Database query failed"}), 500
                if not can_manage_r.data:
                    return jsonify({"error": "forbidden"}), 403
                perms_r = family_svc.get_permissions(family_circle_id, target_user_id)
                if not perms_r.success:
                    return jsonify({"error": perms_r.error or "Database query failed"}), 500
                return jsonify(
                    {
                        "data": {
                            "user_id": target_user_id,
                            "permissions": perms_r.data or [],
                        }
                    }
                )
            if target_user_id:
                perms_r = family_svc.get_permissions(family_circle_id, target_user_id)
                if not perms_r.success:
                    return jsonify({"error": perms_r.error or "Database query failed"}), 500
                return jsonify(
                    {"data": {"user_id": target_user_id, "permissions": perms_r.data or []}}
                )
            can_manage_r = family_svc.can_manage_family_permissions(
                g.user_id, g.family_circle_id
            )
            if not can_manage_r.success:
                return jsonify({"error": can_manage_r.error or "Database query failed"}), 500
            if not can_manage_r.data:
                return jsonify({"error": "forbidden"}), 403
            perms_r = family_svc.get_permissions(family_circle_id)
            if not perms_r.success:
                return jsonify({"error": perms_r.error or "Database query failed"}), 500
            return jsonify({"data": perms_r.data or {}})

        data = request.get_json() or {}
        user_id = (data.get("user_id") or "").strip()
        permission = (data.get("permission") or "").strip()
        if not user_id or not permission:
            return jsonify({"error": "user_id and permission required"}), 400
        granted = bool(data.get("granted", True))
        can_manage_r = family_svc.can_manage_family_permissions(g.user_id, g.family_circle_id)
        if not can_manage_r.success:
            return jsonify({"error": can_manage_r.error or "Database query failed"}), 500
        if not can_manage_r.data:
            return jsonify({"error": "forbidden"}), 403
        update_r = family_svc.set_permission(user_id, family_circle_id, permission, granted)
        if not update_r.success:
            if update_r.error == "target user not in family":
                return jsonify({"error": "forbidden"}), 403
            return jsonify({"error": update_r.error or "Database query failed"}), 500
        return jsonify({"data": update_r.data})

    @app.route(
        "/api/family_circles/<family_circle_id>/contacts", methods=["GET", "POST"]
    )
    def api_contacts(family_circle_id):
        """GET: all contacts. POST: add contact."""
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
                linked_user_id=data.get("linked_user_id"),
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
        # TODO: remove api.py queries and maybe even safe_query_manager? (user container?)
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
        try:
            in_uploads = (
                os.path.commonpath([uploads_abs, os.path.abspath(path)]) == uploads_abs
            )
        except ValueError:
            in_uploads = False
        if not in_uploads:
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
        denied = _require_family_permission("emergency_alert.manage")
        if denied is not None:
            return denied
        return jsonify({"data": {"activated": _get_alert_activated(g.family_circle_id)}})

    @app.route("/api/emergency/alert", methods=["POST"])
    def api_alert():
        """TODO: Requires user + family (via before_request). Eventually: authorization/role check."""
        denied = _require_family_permission("emergency_alert.manage")
        if denied is not None:
            return denied
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
        from_display_name = user_svc.get_display_name(g.user_id)
        r = call_signal_svc.request_call(
            family_circle_id=g.family_circle_id,
            from_user_id=g.user_id,
            to_user_id=to_user_id,
            from_display_name=from_display_name,
        )
        if not r.success:
            if "not in family circle" in (r.error or "").lower():
                return jsonify({"error": r.error}), 403
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
        err_detail = ((data.get("error") or data.get("reason") or "").strip() or "")[:500]
        phase = (data.get("phase") or "").strip()[:120]
        en = (data.get("err_name") or "").strip()[:80]
        parts = []
        if phase:
            parts.append(f"phase={phase!r}")
        if en:
            parts.append(f"err_name={en!r}")
        if err_detail:
            parts.append(f"detail={err_detail!r}")
        extra = (" " + " ".join(parts)) if parts else ""
        _logger.info(
            f"Call socket event={event} source={client_source} device={client_device_id}{extra}"
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

        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        # TODO: why does emergency profile need to ever PUT or update care recipient?
        r = care_recipient_svc.update_care_recipient(family_circle_id, data)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/emergency-profile/pdf")
    def api_emergency_profile_pdf(family_circle_id):
        _require_family_access(family_circle_id)
        if build_pdf is None:
            return jsonify({"error": "PDF generation unavailable: reportlab not installed"}), 503
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

    @app.route("/api/me/permissions")
    def api_me_permissions():
        r = family_svc.get_permissions(g.family_circle_id, g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data or []})

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

        user_id = data.get("user_id") or g.user_id
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        notes = data.get("notes")
        # location_name is always resolved from GPS in create_checkin; never from client

        if latitude is None or longitude is None:
            return (
                jsonify({"error": "latitude and longitude are required"}),
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
        push_svc = container.get_notification_service()
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
        push_svc = container.get_notification_service()
        r = push_svc.request_location_update(family_circle_id, g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        data = r.data or {}
        return jsonify({"ok": True, "requested_count": data.get("requested_count", 0)})

    # Static routes (webapp + kiosk) for Railway all-in-one deploy
    _src = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _webapp_dist = os.path.join(_src, "apps", "webapp", "web_server", "dist")
    _kiosk_web = os.path.join(_src, "apps", "kiosk", "web")
    _webapp_client = os.path.join(_src, "apps", "webapp", "web_client")
    _kiosk_icons = os.path.join(_src, "shared", "assets", "icons")
    if os.path.isdir(_webapp_dist):
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

        @app.route("/privacy.html")
        def serve_privacy():
            return send_from_directory(_webapp_dist, "privacy.html")

        @app.route("/terms.html")
        def serve_terms():
            return send_from_directory(_webapp_dist, "terms.html")

        @app.route("/ice-editor")
        @app.route("/ice_editor.html")
        def serve_ice_editor():
            return send_from_directory(_webapp_dist, "ice_editor.html")

        @app.route("/info.html")
        def serve_info_guide():
            return send_from_directory(_webapp_dist, "info.html")

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

    if os.path.isdir(_kiosk_web):
        def _server_osm_tile_cache_root() -> str:
            custom = (os.environ.get("MERIDIAN_SERVER_OSM_TILE_CACHE_DIR") or "").strip()
            if custom:
                return custom
            return os.path.join(tempfile.gettempdir(), "meridian-osm-tiles")

        def _path_in_cache_root(root_real: str, candidate: str) -> bool:
            candidate_real = os.path.realpath(candidate)
            try:
                return os.path.commonpath([root_real, candidate_real]) == root_real
            except ValueError:
                return False

        def _prune_osm_tile_cache(root_real: str) -> None:
            now = int(time.time())
            last_run = getattr(_prune_osm_tile_cache, "_last_run", 0)
            if now - last_run < 300:
                return
            _prune_osm_tile_cache._last_run = now
            try:
                ttl_sec = int(
                    (os.environ.get("MERIDIAN_SERVER_OSM_TILE_CACHE_TTL_SEC") or "1209600").strip()
                )
            except ValueError:
                ttl_sec = 1209600
            try:
                max_files = int(
                    (os.environ.get("MERIDIAN_SERVER_OSM_TILE_CACHE_MAX_FILES") or "12000").strip()
                )
            except ValueError:
                max_files = 12000
            keep = []
            for dirpath, _dirnames, filenames in os.walk(root_real):
                for name in filenames:
                    if not name.endswith(".png"):
                        continue
                    path = os.path.realpath(os.path.join(dirpath, name))
                    if not _path_in_cache_root(root_real, path):
                        continue
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    if ttl_sec > 0 and now - int(st.st_mtime) > ttl_sec:
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                        continue
                    keep.append((st.st_mtime, path))
            overflow = len(keep) - max_files
            if overflow > 0:
                keep.sort(key=lambda item: item[0])
                for _mtime, path in keep[:overflow]:
                    if not _path_in_cache_root(root_real, path):
                        continue
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        def _resolve_osm_tile_cache_path(root: str, z: int, x: int, y: int) -> tuple[str, str]:
            # Accept only valid OSM tile coordinates so we never build out-of-range paths.
            if z < 0 or z > 19:
                abort(404)
            tile_limit = 2**z
            if x < 0 or y < 0 or x >= tile_limit or y >= tile_limit:
                abort(404)
            # Resolve to absolute canonical paths and enforce dest remains under root.
            root_real = os.path.realpath(root)
            dest_real = os.path.realpath(
                os.path.join(root_real, str(z), str(x), f"{y}.png")
            )
            try:
                in_root = os.path.commonpath([root_real, dest_real]) == root_real
            except ValueError:
                in_root = False
            if not in_root:
                abort(404)
            return root_real, dest_real

        @app.route("/kiosk/osm-tiles/<int:z>/<int:x>/<int:y>.png")
        def serve_kiosk_osm_tile(z, x, y):
            root = _server_osm_tile_cache_root()
            # Centralize all coordinate and path traversal checks in one place.
            root_real, dest_real = _resolve_osm_tile_cache_path(root, z, x, y)
            if os.path.isfile(dest_real):
                return send_file(dest_real, mimetype="image/png")
            url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "MeridianServer/1.0 (tile cache; +https://github.com/Bikes4Fun/meridian)"
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = resp.read()
                if len(data) < 100:
                    abort(502)
                if not _path_in_cache_root(root_real, dest_real):
                    abort(404)
                parent_real = os.path.realpath(os.path.dirname(dest_real))
                if not _path_in_cache_root(root_real, parent_real):
                    abort(404)
                os.makedirs(parent_real, exist_ok=True)
                with open(dest_real, "wb") as wf:
                    wf.write(data)
                _prune_osm_tile_cache(root_real)
                return Response(data, mimetype="image/png")
            except Exception:
                abort(502)

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
    ssl_files = get_meridian_ssl_files()
    ssl_kw: dict = {}
    if ssl_files:
        cert_path, key_path = ssl_files
        ssl_kw["ssl_context"] = (cert_path, key_path)
        _logger.info(
            f"HTTPS enabled (MERIDIAN_SSL_CERT / MERIDIAN_SSL_KEY): {cert_path}"
        )
    app.run(host=host, port=port, debug=False, **ssl_kw)
