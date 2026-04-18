"""
Kiosk-side HTTP clients: GET/POST helpers, Remote* services, LocalTimeService, KioskRemoteServiceContainer (typed getters over those clients).

Scope: talk to the Meridian API from the kiosk process; no UI.

Not here: Flask routes, pywebview, or server DB ServiceContainer (see server container.py).
"""

import logging
import os
import urllib.parse
from datetime import datetime
from typing import Any, Optional, Tuple
import requests

try:
    from ...shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


class RemoteServiceError(Exception):
    """Raised when a remote API request fails in an unrecoverable way."""

def _headers(
    kiosk_user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
) -> dict:
    out = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "Meridian-Kiosk/1.0",
    }
    if kiosk_user_id:
        out["X-User-Id"] = kiosk_user_id
    if family_circle_id:
        out["X-Family-Circle-Id"] = family_circle_id
    return out


def _get(
    url: str,
    timeout: int = 5,
    headers: Optional[dict] = None,
    session: Optional["requests.Session"] = None,
) -> Tuple[bool, Any, Optional[str]]:
    try:
        logger.info(f"API GET {url}")
        client = session if session else requests
        r = client.get(url, timeout=timeout, headers=headers or {})
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            logger.info(f"API {url} -> error: {j['error']}")
            return False, None, j["error"]
        if "data" in j:
            logger.info(f"API {url} -> ok")
            return True, j["data"], None
        logger.info(f"API {url} -> ok")
        return True, j, None
    except Exception as e:
        logger.info(f"API {url} -> failed: {e}")
        return False, None, str(e)


def _request(
    method: str,
    url: str,
    timeout: int = 5,
    headers: Optional[dict] = None,
    session: Optional["requests.Session"] = None,
    json_body: Optional[dict] = None,
) -> Tuple[bool, Any, Optional[str]]:
    """Shared HTTP request. Returns (ok, data, err). Used by _api_write_request and location/checkin."""
    try:
        logger.info(f"API {method} {url}")
        client = session if session else requests
        req_headers = {**(headers or {}), "Content-Type": "application/json"}
        if method == "POST":
            r = client.post(
                url, json=json_body or {}, headers=req_headers, timeout=timeout
            )
        elif method == "PUT":
            r = client.put(
                url, json=json_body or {}, headers=req_headers, timeout=timeout
            )
        elif method == "DELETE":
            r = client.delete(url, headers=headers or {}, timeout=timeout)
        else:
            return False, None, f"unsupported method {method}"
        j = None
        if r.content:
            try:
                j = r.json()
            except Exception:
                j = None
        if not r.ok:
            if isinstance(j, dict) and "error" in j and j["error"]:
                return False, None, str(j["error"])
            body_text = (r.text or "").strip()
            if body_text:
                return False, None, body_text
            return False, None, f"HTTP {r.status_code}"
        if isinstance(j, dict) and "error" in j:
            return False, None, j["error"]
        if j is None:
            j = {}
        return True, j, None
    except Exception as e:
        logger.info(f"API {method} {url} -> failed: {e}")
        return False, None, str(e)


def _get_raw(
    url: str,
    timeout: int = 10,
    headers: Optional[dict] = None,
    session: Optional["requests.Session"] = None,
) -> Tuple[bool, Optional[bytes], Optional[str]]:
    """GET URL and return response body as bytes (e.g. for PDF)."""
    try:
        logger.info(f"API GET {url} (bytes)")
        client = session if session else requests
        r = client.get(url, timeout=timeout, headers=headers or {})
        r.raise_for_status()
        logger.info(f"API {url} -> ok ({len(r.content)} bytes)")
        return True, r.content, None
    except Exception as e:
        logger.info(f"API {url} -> failed: {e}")
        return False, None, str(e)

class LocalTimeService:
    """Time from the device (no server call)."""

    def __init__(self, base_url: str):
        pass

    def get_time(self) -> str:
        return datetime.now().strftime("%-I:%M %p").replace(" 0", " ").lstrip()

    def get_dayof_week(self) -> str:
        return datetime.now().strftime("%A")

    def get_day_period(self) -> tuple[str, str]:
        """Human label + sprite key (morning|noon|evening|night); same buckets as clock art."""
        h = datetime.now().hour
        if 5 <= h < 11:
            return ("Morning", "morning")
        if 11 <= h < 14:
            return ("Midday", "noon")
        if 14 <= h < 18:
            return ("Evening", "evening")
        return ("Night", "night")

    def get_am_pm(self) -> str:
        return self.get_day_period()[0]

    def get_clock_date_line(self) -> str:
        return f"{self.get_month_day()}, {self.get_year()}"

    def get_date(self) -> str:
        return datetime.now().strftime("%B %-d, %Y").replace(" 0", " ").lstrip()

    def get_month_day(self) -> str:
        return datetime.now().strftime("%B %-d").replace(" 0", " ").lstrip()

    def get_year(self) -> str:
        return str(datetime.now().year)


class RemoteCalendarService:
    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def _today_param(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def get_day_headers(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/headers",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "calendar/headers request failed")
        return ServiceResult.success_result(data)

    def get_current_month_data(self, reference_date=None) -> Any:
        today = self._today_param()
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/month?date={today}",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "calendar/month request failed")
        return ServiceResult.success_result(data)

    def get_current_date(self) -> int:
        today = self._today_param()
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/date?date={today}",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            raise RemoteServiceError(err or "API calendar/date failed")
        if data is None:
            raise RemoteServiceError("API calendar/date returned no data")
        return int(data)

    def get_events_for_date(self, date: str) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events?date={date}",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "calendar/events request failed")
        return ServiceResult.success_result(data)

    def add_event(self, payload: dict) -> Any:
        """POST new event. Shared by kiosk, future mobile client, etc."""
        return _api_write_request(
            "POST",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events",
            self._headers,
            self._session,
            json_body=payload,
        )

    def update_event(self, event_id: str, payload: dict) -> Any:
        """PUT event. Shared by kiosk, webapp, mobile, etc."""
        quoted = urllib.parse.quote(event_id, safe="")
        return _api_write_request(
            "PUT",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events/{quoted}",
            self._headers,
            self._session,
            json_body=payload,
        )

    def delete_event(self, event_id: str) -> Any:
        """DELETE event. Shared by kiosk, webapp, mobile, etc."""
        quoted = urllib.parse.quote(event_id, safe="")
        return _api_write_request(
            "DELETE",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events/{quoted}",
            self._headers,
            self._session,
        )


def _api_write_request(
    method: str,
    url: str,
    headers: dict,
    session: Any,
    json_body: Optional[dict] = None,
) -> Any:
    """Shared helper for calendar API write operations."""
    ok, resp, err = _request(
        method, url, headers=headers, session=session, json_body=json_body
    )
    if ok:
        data = resp.get("data", True) if (resp and isinstance(resp, dict)) else True
        return ServiceResult.success_result(data)
    return ServiceResult.error_result(err or "request failed")


class RemoteMedicationService:
    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def get_medication_data(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/medications",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "medications request failed")
        return ServiceResult.success_result(data)

    def add_medication(self, payload: dict) -> Any:
        """POST new medication. Payload: name, medication_times, dosage?"""
        return _api_write_request(
            "POST",
            f"{self._base}/api/family_circles/{self._fc_id}/medications",
            self._headers,
            self._session,
            json_body=payload,
        )

    def get_medication_for_edit(self, medication_id: int) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "request failed")
        return ServiceResult.success_result(data)

    def update_medication(self, medication_id: int, payload: dict) -> Any:
        return _api_write_request(
            "PUT",
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}",
            self._headers,
            self._session,
            json_body=payload,
        )

    def delete_medication(self, medication_id: int) -> Any:
        return _api_write_request(
            "DELETE",
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}",
            self._headers,
            self._session,
        )

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> Any:
        return _api_write_request(
            "POST",
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}/mark-taken",
            self._headers,
            self._session,
            json_body={"time": time_slot, "taken": taken},
        )


class RemoteAlertService:
    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def get_alert_status(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/emergency/alert/status",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "alert status request failed")
        return ServiceResult.success_result(data or {"activated": False})

    def set_alert_activated(self, activated: bool) -> Any:
        ok, j, err = _request(
            "POST",
            f"{self._base}/api/emergency/alert",
            headers=self._headers,
            session=self._session,
            json_body={"activated": bool(activated)},
        )
        if not ok:
            return ServiceResult.error_result(err or "alert POST failed")
        if isinstance(j, dict) and "data" in j:
            return ServiceResult.success_result(j["data"])
        return ServiceResult.success_result(j or {})


class RemoteIncomingCallService:
    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def get_incoming_call(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/calls/incoming",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "incoming call request failed")
        return ServiceResult.success_result(data or {})

    def acknowledge_incoming_call(self, call_id: int) -> Any:
        ok, j, err = _request(
            "POST",
            f"{self._base}/api/calls/{call_id}/ack",
            headers=self._headers,
            session=self._session,
            json_body={},
        )
        if not ok:
            return ServiceResult.error_result(err or "incoming call ack failed")
        if isinstance(j, dict) and "data" in j:
            return ServiceResult.success_result(j["data"])
        return ServiceResult.success_result(j or {})


class RemoteVoiceService:
    """Trigger outbound voice calls through server Twilio routes."""

    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def place_call(self, phone: str) -> Any:
        phone = (phone or "").strip()
        if not phone:
            return ServiceResult.error_result("phone required")
        ok, j, err = _request(
            "POST",
            f"{self._base}/api/voice/call",
            headers=self._headers,
            session=self._session,
            json_body={"to": phone},
        )
        if not ok:
            logger.warning(f"Voice call request failed for {phone}: {err or 'voice call failed'}")
            return ServiceResult.error_result(err or "voice call failed")
        logger.info(f"Voice call request succeeded for {phone}")
        if isinstance(j, dict) and "sid" in j:
            return ServiceResult.success_result({"sid": j.get("sid")})
        if isinstance(j, dict) and "data" in j:
            return ServiceResult.success_result(j.get("data"))
        return ServiceResult.success_result(j or {})

    def log_twilio_startup_check(self) -> None:
        """GET /api/voice/twilio-status — log whether Twilio credentials work."""
        ok, j, err = _get(
            f"{self._base}/api/voice/twilio-status",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            logger.warning(f"Twilio startup check failed: {err}")
            return
        if isinstance(j, dict) and j.get("ok"):
            logger.info("Twilio API credentials OK")
        else:
            logger.warning(f"Twilio not ready: {j}")


class RemoteEmergencyProfileService:
    """Emergency profile (first responder view), medical summary, and emergency contacts from the server."""

    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session
        self._photo_service = RemotePhotoService(self._base, self._headers, self._session)

    def get_emergency_profile(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/emergency-profile",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "emergency-profile request failed")
        return ServiceResult.success_result(data)

    def get_user_photo_b64(self, user_id: str) -> Optional[str]:
        # could use photo service directly but this maintains current call structure.
        return self._photo_service.get_user_photo_b64(user_id)

    def get_medical_summary_from_server(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/medical-summary",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "medical-summary request failed")
        return ServiceResult.success_result(data)

    def get_pdf_url(self) -> str:
        """URL for the printable PDF."""
        return f"{self._base}/api/family_circles/{self._fc_id}/emergency-profile/pdf"

    def get_emergency_profile_pdf(self) -> Any:
        """Fetch PDF bytes for the emergency profile (for printing)."""
        ok, data, err = _get_raw(
            self.get_pdf_url(),
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(
                err or "emergency-profile PDF request failed"
            )
        return ServiceResult.success_result(data)


    def get_dnr_document_url(self, family_circle_id: str, care_recipient_user_id: str) -> str:
        fc_id = (family_circle_id or "").strip()
        user_id = (care_recipient_user_id or "").strip()
        if not fc_id or not user_id:
            return ""
        return (
            f"{self._base}/api/family_circles/{urllib.parse.quote(fc_id, safe='')}"
            f"/care-recipients/{urllib.parse.quote(user_id, safe='')}/dnr-document"
        )


class RemoteContactService:
    """All contacts for the family (e.g. chat grid)."""

    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session
        self._photo_service = RemotePhotoService(self._base, self._headers, self._session)

    def get_contacts(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/contacts",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "contacts request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def get_user_photo_b64(self, user_id: str) -> Optional[str]:
        # could use photo service directly but this maintains current call structure.
        return self._photo_service.get_user_photo_b64(user_id)

    def get_best_contact_photo_b64(self, user_id: str, contact_id: str) -> Optional[str]:
        # could use photo service directly but this maintains current call structure.
        return self._photo_service.get_best_contact_photo_b64(
            user_id, contact_id, self._fc_id
        )

class RemoteLocationService:
    def __init__(
        self,
        base_url: str,
        kiosk_user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session
        self._photo_service = RemotePhotoService(self._base, self._headers, self._session)

    def get_checkins(self, family_circle_id: Optional[str] = None) -> Any:
        fc_id = family_circle_id if family_circle_id is not None else self._fc_id
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{fc_id}/get_checkins",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "location/latest request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def get_named_places(self, family_circle_id: Optional[str] = None) -> Any:
        fc_id = family_circle_id if family_circle_id is not None else self._fc_id
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{fc_id}/named-places",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "location/places request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def where_is_everyone(self, family_circle_id: Optional[str] = None) -> str:
        """Request family to refresh location. Returns user-facing message."""
        fc_id = family_circle_id if family_circle_id is not None else self._fc_id
        ok, data, err = _request(
            "POST",
            f"{self._base}/api/family_circles/{fc_id}/where-is-everyone",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return f"Could not send: {err}"
        count = (data or {}).get("requested_count", 0)
        if count > 0:
            return "Request sent! Your family will update their locations."
        return "No family members to notify."

    def create_checkin(
        self,
        contact_id: str,
        latitude: float,
        longitude: float,
        notes: Optional[str] = None,
    ) -> Any:
        """Create check-in. location_name resolved from GPS. notes = user message."""
        payload = {
            "contact_id": contact_id,
            "latitude": latitude,
            "longitude": longitude,
        }
        if notes:
            payload["notes"] = notes
        ok, data, err = _request(
            "POST",
            f"{self._base}/api/family_circles/{self._fc_id}/create_checkin",
            headers=self._headers,
            session=self._session,
            json_body=payload,
        )
        if not ok:
            return ServiceResult.error_result(err or "create_checkin failed")
        return ServiceResult.success_result(
            data.get("data") if isinstance(data, dict) else data
        )

    def get_user_photo_b64(self, user_id: str) -> Optional[str]:
        # could use photo service directly but this maintains current call structure.
        return self._photo_service.get_user_photo_b64(user_id)

class RemotePhotoService:

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[dict] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = (base_url or "").rstrip("/")
        self._headers = headers or {}
        self._session = session

    def fetch_photo_b64(self, url: str) -> Optional[str]:
        """Fetch any photo URL via authenticated session, return data URI or None."""
        if not url:
            return None
        try:
            import base64
        except ImportError:
            return None
        try:
            client = self._session if self._session else requests
            r = client.get(url, headers=self._headers, timeout=5)
            if r.ok and r.content:
                mime = r.headers.get("Content-Type", "image/jpeg")
                b64 = base64.b64encode(r.content).decode()
                return f"data:{mime};base64,{b64}"
            logger.debug(f"Photo fetch {url} -> {r.status_code}")
        except Exception as e:
            logger.debug(f"Photo fetch {url} failed: {e}")
        return None

    def get_user_photo_b64(self, user_id: str) -> Optional[str]:
        user_id = (user_id or "").strip()
        if not self._base or not user_id:
            return None
        quoted = urllib.parse.quote(user_id, safe="")
        return self.fetch_photo_b64(f"{self._base}/api/users/{quoted}/photo")

    def get_contact_photo_b64(self, family_circle_id: str, contact_id: str) -> Optional[str]:
        family_circle_id = (family_circle_id or "").strip()
        contact_id = (contact_id or "").strip()
        if not self._base or not family_circle_id or not contact_id:
            return None
        family_circle_id = urllib.parse.quote(family_circle_id, safe="")
        contact_id = urllib.parse.quote(contact_id, safe="")
        return self.fetch_photo_b64(
            f"{self._base}/api/family_circles/{family_circle_id}/contacts/{contact_id}/photo"
        )

    def get_best_contact_photo_b64(
        self, user_id: str, contact_id: str, family_circle_id: str
    ) -> Optional[str]:
        avatar_src = self.get_user_photo_b64(user_id)
        if avatar_src:
            return avatar_src
        return self.get_contact_photo_b64(family_circle_id, contact_id)


    def fetch_photo_to_cache(self, user_id: str, cache_dir: str) -> Optional[str]:
        """Fetch photo from server and save to cache. Returns local path or None. Reuses cache if present. user_id = whose photo (any family member)."""
        try:
            import requests
        except ImportError:
            return None
        photo_dir = os.path.join(cache_dir, "photos")
        os.makedirs(photo_dir, exist_ok=True)
        cached = os.path.join(photo_dir, user_id)
        if os.path.exists(cached):
            return cached
        try:
            url = f"{self._base}/api/users/{user_id}/photo"
            client = self._session if self._session else requests
            r = client.get(url, headers=self._headers, timeout=10)
            r.raise_for_status()
            with open(cached, "wb") as f:
                f.write(r.content)
            return cached
        except Exception as e:
            logger.debug(f"Photo fetch failed for {user_id}: {e}")
            return None


class KioskRemoteServiceContainer:
    """Typed access to kiosk HTTP-backed services.

    Exposes the same ``get_*_service()`` method *names* as the server-side
    ``ServiceContainer`` (database-backed; server ``container.py``) so call
    sites share one convention; here each getter returns a remote client, not a DB service.
    """

    __slots__ = ("_s",)

    def __init__(self, services_dict: dict):
        self._s = services_dict

    def get_time_service(self):
        return self._s.get("time_service")

    def get_calendar_service(self):
        return self._s.get("calendar_service")

    def get_medication_service(self):
        return self._s.get("medication_service")

    def get_emergency_service(self):
        return self._s.get("emergency_service")

    def get_location_service(self):
        return self._s.get("location_service")

    def get_contact_service(self):
        return self._s.get("contact_service")

    def get_alert_service(self):
        return self._s.get("alert_service")

    def get_incoming_call_service(self):
        return self._s.get("incoming_call_service")

    def get_voice_service(self):
        return self._s.get("voice_service")

    @property
    def alert_activated_holder(self) -> list:
        """Single-element list updated by alert poll (same object as legacy dict entry)."""
        return self._s["_alert_activated"]

    def get_emergency_print_status_label(self):
        return self._s.get("_emergency_print_status_label")


def create_kiosk_remote(
    server_url: str,
    kiosk_user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
    session: Optional["requests.Session"] = None,
) -> KioskRemoteServiceContainer:
    """Return typed kiosk services: time from device, rest from server API."""
    try:
        import requests

        if session is None:
            session = requests.Session()
    except ImportError:
        session = None
    services = {
        "time_service": LocalTimeService(server_url),
        "calendar_service": RemoteCalendarService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "medication_service": RemoteMedicationService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "emergency_service": RemoteEmergencyProfileService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "location_service": RemoteLocationService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "contact_service": RemoteContactService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "alert_service": RemoteAlertService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "incoming_call_service": RemoteIncomingCallService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "voice_service": RemoteVoiceService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "_alert_activated": [False],
    }
    return KioskRemoteServiceContainer(services)
