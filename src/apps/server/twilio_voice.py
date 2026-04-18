"""Twilio Programmable Voice: REST outbound, browser Voice (WebRTC) for kiosk, TwiML hooks."""

import logging
import os
import uuid

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


def _twilio_public_request_url() -> str:
    """URL Twilio used for signature validation (honor reverse-proxy HTTPS)."""
    url = request.url
    if request.headers.get("X-Forwarded-Proto", "").lower() == "https" and url.startswith(
        "http://"
    ):
        url = "https://" + url[7:]
    return url


def register_twilio_voice_routes(app, user_svc):
    """Register voice routes: TwiML, REST call, token (kiosk WebRTC), client TwiML App URL."""

    @app.route("/twilio/voice", methods=["GET", "POST"])
    def twilio_voice_webhook():
        from twilio.twiml.voice_response import VoiceResponse

        resp = VoiceResponse()
        resp.say("Hello from Meridian.")
        return Response(str(resp), mimetype="text/xml")

    @app.route("/twilio/voice/client", methods=["POST"])
    def twilio_voice_client_twiml():
        """TwiML App Voice URL: browser client outbound to PSTN. Called by Twilio only."""
        from twilio.request_validator import RequestValidator
        from twilio.twiml.voice_response import VoiceResponse

        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        if not auth_token:
            abort(503)
        validator = RequestValidator(auth_token)
        sig = request.headers.get("X-Twilio-Signature") or ""
        params = request.form.to_dict()
        if not validator.validate(_twilio_public_request_url(), params, sig):
            logger.warning("Twilio signature validation failed for /twilio/voice/client")
            abort(403)
        to = normalize_phone_e164(params.get("To") or "")
        caller_id = normalize_phone_e164(params.get("callerId") or params.get("CallerId") or "")
        if not to or not caller_id:
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
        pr = user_svc.get_user_phone_for_family(g.user_id, g.family_circle_id)
        if not pr.success:
            return jsonify({"error": pr.error or "failed"}), 500
        caller_raw = (pr.data or "").strip()
        caller_id = normalize_phone_e164(caller_raw) if caller_raw else ""
        if not caller_id:
            caller_id = (
                os.environ.get("TWILIO_PHONE_NUMBER") or os.environ.get("TWILIO_FROM_NUMBER") or ""
            ).strip()
        if not caller_id:
            return (
                jsonify(
                    {
                        "error": "No caller ID: add phone to your user profile or set TWILIO_PHONE_NUMBER"
                    }
                ),
                503,
            )
        try:
            from twilio.jwt.access_token import AccessToken
            from twilio.jwt.access_token.grants import VoiceGrant

            identity = f"kiosk_{g.user_id}"[:120]
            token = AccessToken(account_sid, api_key_sid, api_key_secret, identity=identity, ttl=3600)
            token.add_grant(VoiceGrant(outgoing_application_sid=twiml_app_sid))
            jwt_bytes = token.to_jwt()
            jwt_str = jwt_bytes.decode("utf-8") if isinstance(jwt_bytes, bytes) else jwt_bytes
            return jsonify({"token": jwt_str, "caller_id": caller_id})
        except Exception as e:
            logger.exception(f"Voice token failed: {e}")
            return jsonify({"error": "Could not create voice token"}), 500

    @app.route("/api/voice/call", methods=["POST"])
    def api_voice_outbound_call():
        body = request.get_json() or {}
        to = normalize_phone_e164(body.get("to") or "")
        pr = user_svc.get_user_phone_for_family(g.user_id, g.family_circle_id)
        if not pr.success:
            return jsonify({"error": pr.error or "failed"}), 500
        caller_raw = (pr.data or "").strip()
        from_num = normalize_phone_e164(caller_raw) if caller_raw else ""
        if not from_num:
            from_num = (
                os.environ.get("TWILIO_PHONE_NUMBER")
                or os.environ.get("TWILIO_FROM_NUMBER")
                or ""
            ).strip()
            if from_num:
                logger.warning(
                    f"Twilio outbound: user {g.user_id} has no phone on file; using TWILIO_PHONE_NUMBER as From"
                )
        logger.info(
            f"/api/voice/call requested: from={from_num or '(none)'} to={to or '(empty)'}"
        )
        account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        missing = []
        if not account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not from_num:
            missing.append("user phone (POST /api/users with phone) or TWILIO_PHONE_NUMBER")
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
            from twilio.twiml.voice_response import VoiceResponse

            client = Client(account_sid, auth_token)
            # One call to `to` with TwiML Dial→Number(`from_num`) chained a second PSTN leg after
            # Eleanor answered; if that leg failed (no answer, trial, etc.), Twilio played
            # "an application error has occurred." Bridge both parties with the same Conference instead.
            room = f"meridian_{uuid.uuid4().hex[:16]}"
            join_conf = VoiceResponse()
            join_conf.dial().conference(room, beep="false")
            twiml_str = str(join_conf)
            call_to = client.calls.create(to=to, from_=from_num, twiml=twiml_str)
            if from_num == to:
                logger.info(f"Twilio call queued sid={call_to.sid} from={from_num} to={to} (single party)")
                return jsonify({"sid": call_to.sid})
            call_from = None
            try:
                call_from = client.calls.create(to=from_num, from_=from_num, twiml=twiml_str)
            except Exception as e2:
                logger.warning(
                    f"Twilio conference second leg failed (callee may be alone in room until hangup): {e2}"
                )
        except Exception as e:
            logger.exception(f"Twilio call create failed: {e}")
            return jsonify({"error": "Unable to place call right now."}), 502
        if call_from is not None:
            logger.info(
                f"Twilio conference {room}: leg_to sid={call_to.sid} to={to}, "
                f"leg_from sid={call_from.sid} to={from_num}"
            )
            return jsonify({"sid": call_to.sid, "sid_caller": call_from.sid, "conference": room})
        logger.info(f"Twilio conference {room}: leg_to sid={call_to.sid} to={to} (second leg failed)")
        return jsonify({"sid": call_to.sid, "conference": room, "second_leg_failed": True})

    @app.route("/api/voice/twilio-status", methods=["GET"])
    def api_voice_twilio_status():
        """Lightweight check that Twilio accepts these credentials (kiosk startup)."""
        account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        if not account_sid or not auth_token:
            return jsonify({"ok": False, "detail": "credentials not configured"})
        try:
            from twilio.rest import Client

            Client(account_sid, auth_token).api.accounts(account_sid).fetch()
            return jsonify({"ok": True})
        except Exception as e:
            logger.warning(f"Twilio account check failed: {e}")
            return jsonify({"ok": False, "detail": "twilio rejected credentials or unreachable"})