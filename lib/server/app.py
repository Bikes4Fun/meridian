"""
Flask API server for Dementia TV.
Exposes the same data as in-process services via REST for client/server mode.

WHERE FUNCTIONALITY CAME FROM (required on server; do not remove):
  - container_services/container.py         → create_service_container(db_path) used here
  - container_services/calendar_service.py → GET /api/calendar/*
  - container_services/medication_service.py → GET /api/medications
  - container_services/emergency_service.py → GET /api/emergency/*
  - container_services/contact_service.py  (used by emergency_service; no direct endpoint)

WHERE IT MOVED TO (client uses these instead of container on client):
  - client/remote_services.py (RemoteTimeService, RemoteCalendarService, etc.) calls this API.

SERVER DEPLOYMENT: This module requires config, container_services/, and database_management/.
client/, display/, app_factory.py, icons/, and the Kivy app are not needed on the server;
they can be omitted or relocated to a client-only repo.
"""

import json
import os
import datetime
from flask import Flask, jsonify, request, g, send_from_directory, Response

# config at top level (lib); server internals relative
try:
    from ..config import DatabaseConfig, get_database_path, get_server_host, get_server_port
except ImportError:
    from config import DatabaseConfig, get_database_path, get_server_host, get_server_port
from .database_management.database_manager import DatabaseManager
from .container_services.container import create_service_container

DEFAULT_USER_ID = "0000000000"


def _row_to_display_settings_response(row) -> dict:
    """Convert DB row from user_display_settings to JSON-serializable display dict for API."""
    return {
        "user_id": row["user_id"],
        "display": {
            "font_sizes": json.loads(row["font_sizes"]) if isinstance(row["font_sizes"], str) else row["font_sizes"],
            "colors": json.loads(row["colors"]) if isinstance(row["colors"], str) else row["colors"],
            "spacing": json.loads(row["spacing"]) if isinstance(row["spacing"], str) else row["spacing"],
            "touch_targets": json.loads(row["touch_targets"]) if isinstance(row["touch_targets"], str) else row["touch_targets"],
            "window_width": row["window_width"],
            "window_height": row["window_height"],
            "window_left": row["window_left"],
            "window_top": row["window_top"],
            "clock_icon_size": row["clock_icon_size"],
            "clock_icon_height": row["clock_icon_height"],
            "clock_text_height": row["clock_text_height"],
            "clock_day_height": row["clock_day_height"],
            "clock_time_height": row["clock_time_height"],
            "clock_date_height": row["clock_date_height"],
            "clock_spacing": row["clock_spacing"],
            "clock_padding": json.loads(row["clock_padding"]) if isinstance(row["clock_padding"], str) else row["clock_padding"],
            "main_padding": json.loads(row["main_padding"]) if isinstance(row["main_padding"], str) else row["main_padding"],
            "home_layout": row["home_layout"],
            "clock_proportion": row["clock_proportion"],
            "todo_proportion": row["todo_proportion"],
            "med_events_split": row["med_events_split"],
            "navigation_height": row["navigation_height"],
            "button_flat_style": bool(row["button_flat_style"]),
            "clock_background_color": json.loads(row["clock_background_color"]) if isinstance(row["clock_background_color"], str) else row["clock_background_color"],
            "med_background_color": json.loads(row["med_background_color"]) if isinstance(row["med_background_color"], str) else row["med_background_color"],
            "events_background_color": json.loads(row["events_background_color"]) if isinstance(row["events_background_color"], str) else row["events_background_color"],
            "contacts_background_color": json.loads(row["contacts_background_color"]) if isinstance(row["contacts_background_color"], str) else row["contacts_background_color"],
            "medical_background_color": json.loads(row["medical_background_color"]) if isinstance(row["medical_background_color"], str) else row["medical_background_color"],
            "calendar_background_color": json.loads(row["calendar_background_color"]) if isinstance(row["calendar_background_color"], str) else row["calendar_background_color"],
            "nav_background_color": json.loads(row["nav_background_color"]) if isinstance(row["nav_background_color"], str) else row["nav_background_color"],
            "clock_orientation": row["clock_orientation"],
            "med_orientation": row["med_orientation"],
            "events_orientation": row["events_orientation"],
            "bottom_section_orientation": row["bottom_section_orientation"],
            "high_contrast": bool(row["high_contrast"]),
            "large_text": bool(row["large_text"]),
            "reduced_motion": bool(row["reduced_motion"]),
            "navigation_buttons": json.loads(row["navigation_buttons"]) if isinstance(row["navigation_buttons"], str) else row["navigation_buttons"],
            "borders": json.loads(row["borders"]) if row["borders"] and isinstance(row["borders"], str) else (row["borders"] or {}),
        },
    }


def create_server_app(db_path=None):
    """Create Flask app and register API routes.
    Functionality is provided by container_services (via create_service_container).
    Clients use client/remote_services.create_remote_services() to call this API."""
    db_path = db_path or get_database_path()
    container = create_service_container(db_path)

    app = Flask(__name__)

    @app.after_request
    def add_cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Id"
        return resp

    @app.before_request
    def handle_options():
        if request.method == "OPTIONS":
            return Response(status=204)

    @app.before_request
    def set_user_id():
        """Read user_id from X-User-Id header or ?user_id= query; default for demo."""
        g.user_id = request.headers.get("X-User-Id") or request.args.get("user_id") or DEFAULT_USER_ID

    calendar_svc = container.get_calendar_service()
    medication_svc = container.get_medication_service()
    emergency_svc = container.get_emergency_service()
    location_svc = container.get_location_service()

    def _parse_date_param():
        """Parse optional ?date=YYYY-MM-DD from request (TV's local date). Use for calendar 'current' endpoints."""
        s = request.args.get("date")
        if not s:
            return None
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    @app.route("/api/calendar/headers")
    def api_calendar_headers():
        r = calendar_svc.get_day_headers()
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/calendar/month")
    def api_calendar_month():
        ref = _parse_date_param()
        r = calendar_svc.get_current_month_data(reference_date=ref)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/calendar/date")
    def api_calendar_date():
        ref = _parse_date_param()
        return jsonify({"data": calendar_svc.get_current_date(reference_date=ref)})

    @app.route("/api/calendar/events")
    def api_calendar_events():
        date = request.args.get("date")
        if not date:
            return jsonify({"error": "missing date"}), 400
        r = calendar_svc.get_events_for_date(date)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/medications")
    def api_medications():
        r = medication_svc.get_medication_data()
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/emergency/contacts")
    def api_emergency_contacts():
        r = emergency_svc.format_contacts_for_display()
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/emergency/medical-summary")
    def api_emergency_medical_summary():
        r = emergency_svc.get_medical_summary()
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    _web_client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webapp", "web_client"))

    @app.route("/checkin")
    def serve_checkin():
        return send_from_directory(_web_client_dir, "checkin.html")

    @app.route("/checkin.js")
    def serve_checkin_js():
        return send_from_directory(_web_client_dir, "checkin.js")

    @app.route("/api/settings")
    def api_settings():
        """Return display settings for the current user (X-User-Id). 404 when none in DB; client uses display defaults."""
        db_config = DatabaseConfig(path=db_path, create_if_missing=True)
        db = DatabaseManager(db_config)
        result = db.get_user_display_settings_from_db_query(g.user_id)
        if not result.success or not result.data:
            return jsonify({"error": "settings not found"}), 404
        return jsonify({"data": _row_to_display_settings_response(result.data[0])})

    @app.route("/api/location/family-members")
    def api_get_family_members():
        """Return family members for check-in dropdown."""
        r = location_svc.get_family_members(g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/location/checkin", methods=["POST"])
    def api_create_checkin():
        """Create a new location check-in."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data provided"}), 400
        
        family_member_id = data.get("family_member_id")
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        notes = data.get("notes")
        # location_name is always resolved from GPS in create_checkin; never from client

        if not family_member_id or latitude is None or longitude is None:
            return jsonify({"error": "family_member_id, latitude, and longitude are required"}), 400

        r = location_svc.create_checkin(
            g.user_id, family_member_id, latitude, longitude, notes=notes
        )
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data}), 201

    @app.route("/api/location/places")
    def api_get_named_places():
        """Return all named places for the family."""
        r = location_svc.get_named_places(g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    @app.route("/api/location/latest")
    def api_get_checkins():
        """Get latest check-in per family member."""
        r = location_svc.get_checkins(g.user_id)
        if not r.success:
            return jsonify({"error": r.error}), 500
        return jsonify({"data": r.data})

    return app


def run_server(host=None, port=None):
    """Create and run the server. Host/port from config (get_server_host, get_server_port) when not passed."""
    app = create_server_app()
    host = host if host is not None else get_server_host()
    port = port if port is not None else get_server_port()
    app.run(host=host, port=port, debug=False)
