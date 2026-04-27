"""Twilio Programmable Voice: browser Voice (WebRTC) for kiosk, TwiML hooks, token/status."""

import logging
import os

from flask import Response, abort, g, jsonify, request

logger = logging.getLogger(__name__)


def normalize_phone_e164(raw: str) -> str:
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


def _redact_phone(raw: str) -> str:
    """Mask phone values in logs to avoid clear-text PII."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return "(none)"
    return f"***{digits[-4:]}"


def _sid_suffix(sid: str) -> str:
    """Last segment of Twilio SIDs for logs (avoid full resource ids in clear text)."""
    s = (sid or "").strip()
    if len(s) <= 8:
        return "***" if s else "(none)"
    return f"...{s[-8:]}"


def _twilio_public_request_url() -> str:
    """URL Twilio used for signature validation (honor reverse-proxy HTTPS)."""
    url = request.url
    if request.headers.get("X-Forwarded-Proto", "").lower() == "https" and url.startswith(
        "http://"
    ):
        url = "https://" + url[7:]
    return url


def register_twilio_voice_routes(app, user_svc, family_svc):
    """Register voice routes: TwiML, token (kiosk WebRTC), client TwiML App URL, status."""

    @app.route("/twilio/voice", methods=["GET", "POST"])
    def twilio_voice_webhook():
        from twilio.twiml.voice_response import VoiceResponse  # pyright: ignore[reportMissingImports]

        resp = VoiceResponse()
        resp.say("Hello from Meridian.")
        return Response(str(resp), mimetype="text/xml")

    @app.route("/twilio/voice/client", methods=["POST"])
    def twilio_voice_client_twiml():
        """TwiML App Voice URL: inbound PSTN routing + kiosk outbound to PSTN. Called by Twilio only."""
        from twilio.request_validator import RequestValidator  # pyright: ignore[reportMissingImports]
        from twilio.twiml.voice_response import VoiceResponse  # pyright: ignore[reportMissingImports]

        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        if not auth_token:
            abort(503)
        validator = RequestValidator(auth_token)
        sig = request.headers.get("X-Twilio-Signature") or ""
        params = request.form.to_dict()
        if not validator.validate(_twilio_public_request_url(), params, sig):
            host = (request.host or "").lower()
            if "ngrok" in host:
                logger.warning(
                    f"Twilio signature validation failed on ngrok host {host}; allowing request in local dev mode"
                )
            else:
                logger.warning("Twilio signature validation failed for /twilio/voice/client")
                abort(403)

        called = normalize_phone_e164(params.get("Called") or params.get("To") or "")
        direction = params.get("Direction") or ""

        # Inbound: route calls to Marian's kiosk number directly to kiosk WebRTC client identity.
        if called == "+14359008919":
            vr = VoiceResponse()
            dial = vr.dial()
            dial.client("14359008919")
            return Response(str(vr), mimetype="text/xml")

        # Outbound: kiosk dialling a PSTN number via the TwiML app
        to = normalize_phone_e164(params.get("To") or "")
        caller_id = normalize_phone_e164(params.get("callerId") or params.get("CallerId") or "")
        if not to or not caller_id:
            logger.warning(
                "TwiML /twilio/voice/client missing To or callerId (to=%s caller_id=%s)",
                _redact_phone(params.get("To") or ""),
                _redact_phone(params.get("callerId") or params.get("CallerId") or ""),
            )
            err = VoiceResponse()
            err.say("Meridian could not place this call.")
            return Response(str(err), mimetype="text/xml")
        vr = VoiceResponse()
        dial = vr.dial(caller_id=caller_id)
        dial.number(to)
        return Response(str(vr), mimetype="text/xml")

    @app.route("/api/voice/token", methods=["GET"])
    def api_voice_token():
        """Short-lived JWT for Twilio Voice JS in the kiosk (WebRTC to PSTN)."""
        account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        api_key_sid = (os.environ.get("TWILIO_API_KEY_SID") or "").strip()
        api_key_secret = (os.environ.get("TWILIO_API_KEY_SECRET") or "").strip()
        twiml_app_sid = (os.environ.get("TWILIO_TWIML_APP_SID") or "").strip()
        missing = [
            n
            for n, v in (
                ("TWILIO_ACCOUNT_SID", account_sid),
                ("TWILIO_AUTH_TOKEN", auth_token),
                ("TWILIO_API_KEY_SID", api_key_sid),
                ("TWILIO_API_KEY_SECRET", api_key_secret),
                ("TWILIO_TWIML_APP_SID", twiml_app_sid),
            )
            if not v
        ]
        if missing:
            return (
                jsonify(
                    {
                        "error": f"Kiosk voice not configured: set {', '.join(missing)}. "
                        f"Create API Keys + TwiML App in Twilio Console; Voice URL = …/twilio/voice/client"
                    }
                ),
                503,
            )
        caller_id = "+14359008919"
        try:
            from twilio.jwt.access_token import AccessToken  # pyright: ignore[reportMissingImports]
            from twilio.jwt.access_token.grants import VoiceGrant  # pyright: ignore[reportMissingImports]

            identity = "14359008919"
            token = AccessToken(account_sid, api_key_sid, api_key_secret, identity=identity, ttl=3600)
            token.add_grant(VoiceGrant(outgoing_application_sid=twiml_app_sid, incoming_allow=True))
            jwt_bytes = token.to_jwt()
            jwt_str = jwt_bytes.decode("utf-8") if isinstance(jwt_bytes, bytes) else jwt_bytes
            return jsonify({"token": jwt_str, "caller_id": caller_id})
        except Exception as e:
            logger.exception(f"Voice token failed: {e}")
            return jsonify({"error": "Could not create voice token"}), 500

    @app.route("/api/voice/twilio-status", methods=["GET"])
    def api_voice_twilio_status():
        """Lightweight check that Twilio accepts these credentials (kiosk startup)."""
        account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        if not account_sid or not auth_token:
            return jsonify({"ok": False, "detail": "credentials not configured"})
        try:
            from twilio.rest import Client  # pyright: ignore[reportMissingImports]

            Client(account_sid, auth_token).api.accounts(account_sid).fetch()
            return jsonify({"ok": True})
        except Exception as e:
            logger.warning(
                "Twilio account check failed (account %s): %s",
                _sid_suffix(account_sid),
                e,
            )
            return jsonify({"ok": False, "detail": "twilio rejected credentials or unreachable"})
