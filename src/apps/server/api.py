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
import os
import time
import datetime
import urllib.parse
from dataclasses import asdict
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
from .emergency_pdf import build_pdf
from .container import create_service_container

try:
    from ...apps.chatapp.api import register_chatapp_routes
except ImportError:
    from apps.chatapp.api import register_chatapp_routes

try:
    from ...shared.config import get_uploads_dir
except ImportError:
    from shared.config import get_uploads_dir

_alert_activated = False

_ENTRY_TOKEN_TTL_SEC = 300  # 5 minutes


def _create_chat_entry_token(
    secret: str,
    user_id: str,
    family_circle_id: str,
    sendbird_user_id: str = "",
    display_name: str = "",
) -> str:
    """Create a signed token for chat entry. Valid for _ENTRY_TOKEN_TTL_SEC."""
    payload = {
        "user_id": user_id,
        "family_circle_id": family_circle_id,
        "sendbird_user_id": sendbird_user_id,
        "display_name": display_name,
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
        import logging

        logging.getLogger(__name__).warning(
            "SECRET_KEY not set; using dev default. Set SECRET_KEY in production."
        )
        _secret = "dev-secret-change-in-production"
    app.secret_key = _secret
    app.config["SESSION_SERVER_ID"] = str(time.time())

    def _session_valid():
        """Session is valid only if it matches current server instance (invalidates on restart)."""
        sid = session.get("_sid")
        return sid and sid == app.config.get("SESSION_SERVER_ID")

    @app.after_request
    def add_cors(resp):
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
        # Public routes: no auth required (login page, chatapp POC, kiosk static, fonts)
        if (
            request.path
            in ("/login.html", "/app.js", "/events.js", "/medications.js", "/style.css")
            or request.path in ("/chatapp", "/kiosk")
            or request.path.startswith("/chatapp/")
            or request.path.startswith("/kiosk/")
            or request.path.startswith("/fonts/")
            or request.path.startswith("/shared/")
        ):
            g.user_id = None
            g.family_circle_id = None
            return
        # / and /index.html: require session, redirect to login if missing
        if request.path in ("/", "/index.html"):
            if not _session_valid():
                session.clear()
                return redirect("/login.html")
            uid = session.get("user_id")
            fid = session.get("family_circle_id")
            if not uid or not fid:
                return redirect("/login.html")
            g.user_id = uid
            g.family_circle_id = fid
            return

        # chat-session-bootstrap: new webview (kiosk, mobile) opens URL from chat-session-url; no prior cookie. Token verified in handler.
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

    app.config["container"] = container

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
        token = _create_chat_entry_token(
            app.secret_key,
            g.user_id,
            g.family_circle_id,
            recipient_sb,
            recipient_name,
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
        chatapp_url = (
            os.environ.get("CHATAPP_URL") or request.url_root.rstrip("/")
        ).rstrip("/")
        if not chatapp_url:
            return (
                jsonify(
                    {"error": "CHATAPP_URL not configured; cannot redirect to chat"}
                ),
                503,
            )
        return redirect(chatapp_url + "/auth?token=" + urllib.parse.quote(token))

    user_svc = container.get_user_service()
    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    contact_svc = container.get_contact_service()
    location_svc = container.get_location_service()
    emergency_svc = container.get_emergency_service()
    family_svc = container.get_family_service()
    care_recipient_svc = container.get_care_recipient_service()

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
        if not date:
            return jsonify({"error": "missing date"}), 400
        r = calendar_svc.get_events_for_date(date, family_circle_id=family_circle_id)
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
        r = contact_svc.c_service_get_emergency_contacts(family_circle_id)
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
        return jsonify({"data": {"activated": _alert_activated}})

    @app.route("/api/emergency/alert", methods=["POST"])
    def api_alert():
        """TODO: Requires user + family (via before_request). Eventually: authorization/role check."""
        global _alert_activated
        data = request.get_json() or {}
        _alert_activated = bool(data.get("activated", False))
        return jsonify({"data": {"activated": _alert_activated}})

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
        session["user_id"] = user_id
        session["family_circle_id"] = family_circle_id
        session["_sid"] = app.config.get("SESSION_SERVER_ID", "")
        return redirect("/kiosk/")

    @app.route("/api/login", methods=["POST"])
    def api_login():
        """Fake login: set session from user_id and family_circle_id. For demo/simulated auth."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        user_id = data.get("user_id")
        family_circle_id = data.get("family_circle_id")
        if not user_id or not family_circle_id:
            return jsonify({"error": "user_id and family_circle_id required"}), 400
        session["user_id"] = user_id
        session["family_circle_id"] = family_circle_id
        session["_sid"] = app.config.get("SESSION_SERVER_ID", "")
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
    _repo_root = os.path.dirname(_src)
    _kiosk_icons = os.path.join(_repo_root, "assets", "icons")
    if os.path.isdir(_webapp_dist) and os.path.isdir(_chatapp_dist):
        sendbird_svc = container.get_sendbird_service()
        user_svc = container.get_user_service()
        register_chatapp_routes(
            app, sendbird_svc, user_svc, chat_static_prefix="/chatapp"
        )

        @app.route("/")
        @app.route("/index.html")
        def serve_index():
            return send_from_directory(_webapp_dist, "index.html")

        @app.route("/login.html")
        def serve_login():
            return send_from_directory(_webapp_dist, "login.html")

        @app.route("/app.js")
        def serve_app_js():
            return send_from_directory(_webapp_dist, "app.js")

        @app.route("/events.js")
        def serve_events_js():
            return send_from_directory(_webapp_dist, "events.js")

        @app.route("/medications.js")
        def serve_medications_js():
            return send_from_directory(_webapp_dist, "medications.js")

        @app.route("/style.css")
        def serve_style_css():
            return send_from_directory(_webapp_dist, "style.css")

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
