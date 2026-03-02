"""
Flask API server for Meridian.
Exposes the same data as in-process services via REST for client/server mode.

WHERE FUNCTIONALITY CAME FROM (required on server; do not remove):
  - container/container.py         → create_service_container(db_path) used here
  - container/calendar_service.py → GET /api/family_circles/<id>/calendar/*
  - container/medication_service.py → GET /api/family_circles/<id>/medications
  - container/emergency_service.py → GET /api/family_circles/<id>/contacts, medical-summary
  - container/contact_service.py  (used by emergency_service; no direct endpoint)
  - container/ice_profile_service.py → GET/PUT /api/family_circles/<id>/ice-profile

WHERE IT MOVED TO (client uses these instead of container on client):
  - client/remote.py (RemoteTimeService, RemoteCalendarService, etc.) calls this API.

SERVER DEPLOYMENT: This module requires config, container/, and database_management/.
client/, display/, app_factory.py, icons/, and the Kivy app are not needed on the server;
they can be omitted or relocated to a client-only repo.
"""

import json
import os
import datetime
from dataclasses import asdict
from flask import Flask, abort, jsonify, request, g, send_from_directory, Response, redirect, session

# config from shared; server internals relative
try:
    from ...shared.config import (
        DatabaseConfig,
        get_database_path,
        get_server_host,
        get_server_port,
    )
except ImportError:
    from shared.config import (
        DatabaseConfig,
        get_database_path,
        get_server_host,
        get_server_port,
    )
from .database import DatabaseManager
from .services.container import create_service_container

try:
    from ...shared.config import get_uploads_dir
except ImportError:
    from shared.config import get_uploads_dir

_alert_activated = False


def create_server_app(db_path=None):
    """Create Flask app and register API routes.
    Functionality is provided by container (via create_service_container).
    Clients use client/remote.create_remote() to call this API."""
    db_path = db_path or get_database_path()
    container = create_service_container(db_path)

    app = Flask(__name__)
    _secret = os.environ.get("SECRET_KEY")
    if not _secret:
        import logging
        logging.getLogger(__name__).warning("SECRET_KEY not set; using dev default. Set SECRET_KEY in production.")
        _secret = "dev-secret-change-in-production"
    app.secret_key = _secret

    @app.after_request
    def add_cors(resp):
        origin = os.environ.get("CORS_ORIGIN", "").strip()
        if origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Id, X-Family-Circle-Id"
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
        if request.path == "/login":
            g.user_id = None
            g.family_circle_id = None
            return
        # Session-based (check-in page and its script)
        if request.path in ("/checkin", "/checkin.js", "/api/session"):
            uid = session.get("user_id")
            fid = session.get("family_circle_id")
            if not uid or not fid:
                if request.path == "/checkin":
                    return redirect("/login")
                if request.path == "/api/session":
                    abort(401, "Not logged in")
                abort(401, "Log in at /login first")
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

    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    contact_svc = container.get_contact_service()
    location_svc = container.get_location_service()
    ice_profile_svc = container.get_ice_profile_service()
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
        """All contacts for the family."""
        _require_family_access(family_circle_id)
        r = contact_svc.get_all_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        contacts = [asdict(c) for c in (r.data or [])]
        return jsonify({"data": contacts})

    @app.route("/api/family_circles/<family_circle_id>/emergency-contacts")
    def api_emergency_contacts(family_circle_id):
        """Only emergency-priority contacts."""
        _require_family_access(family_circle_id)
        r = contact_svc.get_emergency_contacts(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        contacts = [asdict(c) for c in (r.data or [])]
        return jsonify({"data": contacts})

    @app.route("/api/family_circles/<family_circle_id>/medical-summary")
    def api_medical_summary(family_circle_id):
        _require_family_access(family_circle_id)
        r = ice_profile_svc.get_medical_summary(family_circle_id)
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

    @app.route("/api/family_circles/<family_circle_id>/ice-profile", methods=["GET", "PUT"])
    def api_ice_profile(family_circle_id):
        _require_family_access(family_circle_id)
        if request.method == "GET":
            r = ice_profile_svc.get_ice_profile(family_circle_id)
            if not r.success:
                return jsonify({"error": r.error}), 500
            return jsonify({"data": r.data})
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        # TODO: why does ice profile need to ever PUT or update care recipient? 
        care_recipient_svc = container.get_care_recipient_service()
        r = care_recipient_svc.update_care_recipient(family_circle_id, data)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    _web_client_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "webapp", "web_client")
    )

    def _serve_with_api_url(filename, api_url=""):
        """Serve static file with __API_URL__ replaced. Use '' when API and webapp share origin."""
        path = os.path.join(_web_client_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().replace("__API_URL__", api_url)
        return Response(content, mimetype="text/html" if filename.endswith(".html") else "application/javascript")

    @app.route("/login")
    def serve_login():
        return _serve_with_api_url("login.html")

    @app.route("/api/session")
    def api_session():
        """Return current session user_id and family_circle_id."""
        return jsonify({
            "user_id": g.user_id,
            "family_circle_id": g.family_circle_id,
        })

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

    @app.route("/checkin")
    def serve_checkin():
        return _serve_with_api_url("checkin.html")

    @app.route("/checkin.js")
    def serve_checkin_js():
        return _serve_with_api_url("checkin.js")

    @app.route("/api/family_circles/<family_circle_id>/family-members")
    def api_get_family_members(family_circle_id):
        _require_family_access(family_circle_id)
        r = family_svc.get_family_members(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/family_circles/<family_circle_id>/checkin", methods=["POST"])
    def api_create_checkin(family_circle_id):
        """Create a new location check-in."""
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
                jsonify(
                    {"error": "user_id, latitude, and longitude are required"}
                ),
                400,
            )
        if user_id != g.user_id:
            return jsonify({"error": "cannot check in for another user"}), 403

        _require_family_access(family_circle_id)
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
        """Get latest check-in per family member. Adds photo_url when user has a photo.
        Why: family map needs checkins and photos in one call."""
        _require_family_access(family_circle_id)
        r = location_svc.get_checkins(family_circle_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        data = r.data or []
        base = request.url_root.rstrip("/")
        for row in data:
            if row.get("photo_filename") and row.get("user_id"):
                row["photo_url"] = "%s/api/users/%s/photo" % (base, row["user_id"])
        return jsonify({"data": data})

    @app.route("/api/users/<user_id>/photo")
    def api_serve_photo(user_id):
        """Serve user photo. User must be in same family. Returns 404 if no photo."""
        db = container.get_database_manager()
        r = db.execute_query(
            "SELECT u.photo_filename FROM users u "
            "INNER JOIN user_family_circle ufc ON u.id = ufc.user_id "
            "WHERE u.id = ? AND ufc.family_circle_id = ?",
            (user_id, g.family_circle_id),
        )
        if not r.success or not r.data or not r.data[0].get("photo_filename"):
            abort(404)
        fn = r.data[0]["photo_filename"]
        if ".." in fn or fn.startswith("/"):
            abort(404)
        uploads_dir = get_uploads_dir()
        path = os.path.join(uploads_dir, fn)
        if not os.path.exists(path):
            abort(404)
        return send_from_directory(uploads_dir, fn, mimetype=None)

    return app


def run_server(host=None, port=None):
    """Create and run the server. Host/port from config (get_server_host, get_server_port) when not passed."""
    app = create_server_app()
    host = host if host is not None else get_server_host()
    port = port if port is not None else get_server_port()
    app.run(host=host, port=port, debug=False)
