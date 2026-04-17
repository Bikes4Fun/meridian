"""Minimal Twilio Programmable Voice hooks (inbound TwiML + authenticated outbound)."""

import logging
import os

from flask import Response, jsonify, request

logger = logging.getLogger(__name__)


def register_twilio_voice_routes(app):
    def _normalize_to_e164(raw: str) -> str:
        value = (raw or "").strip()
        if not value:
            return ""
        if value.startswith("+") and value[1:].isdigit():
            return value
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return value

    @app.route("/twilio/voice", methods=["GET", "POST"])
    def twilio_voice_webhook():
        from twilio.twiml.voice_response import VoiceResponse

        resp = VoiceResponse()
        resp.say("Hello from Meridian.")
        return Response(str(resp), mimetype="text/xml")

    @app.route("/api/voice/call", methods=["POST"])
    def api_voice_outbound_call():
        body = request.get_json() or {}
        to = _normalize_to_e164(body.get("to") or "")
        logger.info(f"/api/voice/call requested: to={to or '(empty)'}")
        account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        from_num = (
            os.environ.get("TWILIO_PHONE_NUMBER")
            or os.environ.get("TWILIO_FROM_NUMBER")
            or ""
        ).strip()
        missing = []
        if not account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not from_num:
            missing.append("TWILIO_PHONE_NUMBER or TWILIO_FROM_NUMBER")
        if missing:
            logger.warning(f"Twilio config missing: {', '.join(missing)}")
            return (
                jsonify({"error": f"Twilio not configured: missing {', '.join(missing)}"}),
                503,
            )
        if not to:
            return jsonify({"error": "to phone required"}), 400
        try:
            from twilio.rest import Client

            client = Client(account_sid, auth_token)
            base = request.url_root.rstrip("/")
            call = client.calls.create(
                url=f"{base}/twilio/voice",
                to=to,
                from_=from_num,
            )
        except Exception:
            logger.exception(f"Twilio call create failed {e}")
            return jsonify({"error": "Unable to place call right now."}), 502
        logger.info(f"Twilio call queued sid={call.sid} to={to}")
        return jsonify({"sid": call.sid})
