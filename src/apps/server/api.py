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
client/, display/, app_factory.py, icons/, and the Kivy app are not needed on the server;
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
from .services.container import create_service_container

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
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
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
    db_path = db_path or get_database_path()
    container = create_service_container(db_path)

    app = Flask(__name__)
    _secret = os.environ.get("SECRET_KEY")
    if not _secret:
        import logging

        logging.getLogger(__name__).warning(
            "SECRET_KEY not set; using dev default. Set SECRET_KEY in production."
        )
        _secret = "dev-secret-change-in-production"
    app.secret_key = _secret

    @app.after_request
    def add_cors(resp):
        origins = [o.strip() for o in (os.environ.get("CORS_ORIGIN") or "").split(",") if o.strip()]
        req_origin = request.headers.get("Origin", "").strip()
        if origins and req_origin and req_origin in origins:
            resp.headers["Access-Control-Allow-Origin"] = req_origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        elif origins:
            resp.headers["Access-Control-Allow-Origin"] = origins[0]
        origins = [o.strip() for o in (os.environ.get("CORS_ORIGIN") or "").split(",") if o.strip()]
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
        """Print full query and response for chat, login, auth API requests only."""
        if not (request.path.startswith("/api/chat/") or request.path == "/api/login"):
            return resp
        try:
            query = "%s %s" % (request.method, request.url)
            body = request.get_json(silent=True) if request.method in ("POST", "PUT", "PATCH") else None
            if body is not None:
                query += "\n  body: %s" % json.dumps(body)
            resp_body = resp.get_data(as_text=True)
            if resp.headers.get("Content-Type", "").startswith("application/json") and resp_body:
                try:
                    resp_body = json.dumps(json.loads(resp_body), indent=2)
                except (ValueError, TypeError):
                    pass
            print("[main server] query:\n  %s\n[main server] response: %s\n%s" % (query, resp.status_code, resp_body))
        except Exception:
            pass
        return resp

    @app.before_request
    def handle_options():
        if request.method == "OPTIONS":
            return Response(status=204)

    @app.before_request
    def set_user_id():
        """Resolve user_id and family_circle_id from headers or session. Fail if missing."""
        if request.path in ("/api/health", "/api/login"):
            g.user_id = None
            g.family_circle_id = None
            return
        # chat-session-bootstrap: new webview (kiosk, mobile) opens URL from chat-session-url; no prior cookie. Token verified in handler.
        if request.path == "/api/chat/chat-session-bootstrap":
            g.user_id = None
            g.family_circle_id = None
            return
        # /api/session: session only.
        if request.path == "/api/session":
        # /api/session: session only.
        if request.path == "/api/session":
            uid = session.get("user_id")
            fid = session.get("family_circle_id")
            if not uid or not fid:
                abort(401, "Not logged in")
            g.user_id = uid
            g.family_circle_id = fid
            return
        # chat-session-url: session OR X-User-Id + X-Family-Circle-Id (kiosk uses headers).
        if request.path == "/api/chat/chat-session-url":
            uid = session.get("user_id") or request.headers.get("X-User-Id")
            fid = session.get("family_circle_id") or request.headers.get("X-Family-Circle-Id")
            if not uid or not fid:
                abort(401, "Log in at /login first or provide X-User-Id and X-Family-Circle-Id")
                abort(401, "Not logged in")
            g.user_id = uid
            g.family_circle_id = fid
            return
        # chat-session-url: session OR X-User-Id + X-Family-Circle-Id (kiosk uses headers).
        if request.path == "/api/chat/chat-session-url":
            uid = session.get("user_id") or request.headers.get("X-User-Id")
            fid = session.get("family_circle_id") or request.headers.get("X-Family-Circle-Id")
            if not uid or not fid:
                abort(401, "Log in at /login first or provide X-User-Id and X-Family-Circle-Id")
            g.user_id = uid
            g.family_circle_id = fid
            return
        # API: headers or session
        user_id = request.headers.get("X-User-Id")
        family_circle_id = request.headers.get("X-Family-Circle-Id")
        if not user_id or not family_circle_id:
            uid = session.get("user_id")
            fid = session.get("family_circle_id")
            if uid and fid:
                user_id = uid
                family_circle_id = fid
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
        recipient_sendbird_user_id, recipient_display_name = who the kiosk user will chat WITH (from headers)."""
        recipient_sb = (request.args.get("recipient_sendbird_user_id") or request.args.get("sendbird_user_id") or "").strip()
        recipient_name = (request.args.get("recipient_display_name") or request.args.get("display_name") or "").strip()
        """Returns a URL; when opened in a webview, establishes session for chat. Auth: session or X-User-Id + X-Family-Circle-Id.
        recipient_sendbird_user_id, recipient_display_name = who the kiosk user will chat WITH (from headers)."""
        recipient_sb = (request.args.get("recipient_sendbird_user_id") or request.args.get("sendbird_user_id") or "").strip()
        recipient_name = (request.args.get("recipient_display_name") or request.args.get("display_name") or "").strip()
        token = _create_chat_entry_token(
            app.secret_key,
            g.user_id,
            g.family_circle_id,
            recipient_sb,
            recipient_name,
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
        chatapp_url = (os.environ.get("CHATAPP_URL") or "").rstrip("/")
        if not chatapp_url:
            return jsonify({"error": "CHATAPP_URL not configured; cannot redirect to chat"}), 503
        return redirect(chatapp_url + "/auth?token=" + urllib.parse.quote(token))
        return redirect(chatapp_url + "/auth?token=" + urllib.parse.quote(token))

    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    contact_svc = container.get_contact_service()
    location_svc = container.get_location_service()
    emergency_svc = container.get_emergency_service()
    family_svc = container.get_family_service()

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
        r = calendar_svc.get_events_for_date(date)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/medications")
    def api_medications(family_circle_id):
        _require_family_access(family_circle_id)
        r = medication_svc.get_medication_data(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/contacts")
    def api_contacts(family_circle_id):
        """All contacts for the family. Kiosk can load once at boot and cache; includes photo_url, photo_filename, sendbird_user_id."""
        _require_family_access(family_circle_id)
        r = contact_svc.get_all_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        base = request.url_root.rstrip("/")
        contacts = [asdict(c) for c in (r.data or [])]
        for c in contacts:
            c["photo_url"] = "%s/api/photo/contact/%s" % (base, c["id"])
        return jsonify({"data": contacts})

    @app.route("/api/family_circles/<family_circle_id>/emergency-contacts")
    def api_emergency_contacts(family_circle_id):
        """Only emergency-priority contacts."""
        _require_family_access(family_circle_id)
        r = contact_svc.c_service_get_emergency_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        base = request.url_root.rstrip("/")
        contacts = [asdict(c) for c in (r.data or [])]
        for c in contacts:
            c["photo_url"] = "%s/api/photo/contact/%s" % (base, c["id"])
        return jsonify({"data": contacts})

    @app.route("/api/family_circles/<family_circle_id>/medical-summary")
    def api_medical_summary(family_circle_id):
        _require_family_access(family_circle_id)
        r = emergency_svc.e_service_get_medical_summary(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/emergency/alert/status")
    def api_alert_status():
        return jsonify({"data": {"activated": _alert_activated}})

    @app.route("/api/emergency/alert", methods=["POST"])
    def api_alert():
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
        return jsonify({"ok": True})

    @app.route("/api/family_circles/<family_circle_id>/family-members")
    def api_get_family_members(family_circle_id):
        _require_family_access(family_circle_id)
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

    @app.route("/api/family_circles/<family_circle_id>/checkin", methods=["POST"])
    def api_create_checkin(family_circle_id):
        """Create a new location check-in."""
        # TODO: use userid for this, not family circle. allowing the user to checkin to multiple families if needed?
        # TODO: rename something like 'create_checkin'
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

    @app.route("/api/family_circles/<family_circle_id>/named-places")
    def api_get_named_places(family_circle_id):
        _require_family_access(family_circle_id)
        r = location_svc.get_named_places(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/checkins")
    def api_get_checkins(family_circle_id):
        """Get latest check-in per family member. Includes photo_url and photo_filename."""
        # TODO: rename something like 'get_checkins'
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

    return app


def run_server(host=None, port=None):
    """Create and run the server. Host/port from config (get_server_host, get_server_port) when not passed."""
    app = create_server_app()
    if app is None:
        raise RuntimeError("create_server_app() returned None")
    host = host if host is not None else get_server_host()
    port = port if port is not None else get_server_port()
    app.run(host=host, port=port, debug=False)
