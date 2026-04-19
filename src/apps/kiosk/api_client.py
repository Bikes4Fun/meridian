"""
Kiosk-side HTTP clients: GET/POST helpers, Remote* services, LocalTimeService, KioskRemoteServiceContainer (typed getters over those clients).

Scope: talk to the Meridian API from the kiosk process; no UI.

Not here: Flask routes, pywebview, or server DB ServiceContainer (see server container.py).
"""

import logging
import math
import os
import urllib.parse
import hashlib
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

    @staticmethod
    def osm_tile_cache_dir() -> Optional[str]:
        """Disk folder for OSM map tiles; same tree Flask serves at /kiosk/osm-tiles/..."""
        base = RemotePhotoService.kiosk_cache_root()
        if not base:
            return None
        return os.path.join(base, "osm_tiles")

    @staticmethod
    def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
        lat_rad = math.radians(lat_deg)
        n = 2.0**zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int(
            (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
            / 2.0
            * n
        )
        return xtile, ytile

    def warm_osm_tiles_around(
        self,
        lat: float,
        lon: float,
        zooms: Tuple[int, ...] = (13, 14),
        radius: int = 1,
    ) -> None:
        """Prefetch OSM raster tiles into osm_tile_cache_dir."""
        root = self.osm_tile_cache_dir()
        if not root:
            return
        headers = {
            "User-Agent": "MeridianKiosk/1.0 (https://github.com/Bikes4Fun/meridian)"
        }
        for z in zooms:
            x0, y0 = self._deg2num(lat, lon, z)
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x, y = x0 + dx, y0 + dy
                    m = 2**z
                    if x < 0 or y < 0 or x >= m or y >= m:
                        continue
                    dest = os.path.join(root, str(z), str(x), f"{y}.png")
                    if os.path.isfile(dest) and os.path.getsize(dest) > 200:
                        continue
                    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                    try:
                        r = requests.get(url, headers=headers, timeout=12)
                        if r.ok and len(r.content) > 200:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with open(dest, "wb") as wf:
                                wf.write(r.content)
                    except Exception as e:
                        logger.debug("OSM tile warm %s: %s", url, e)

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

    @staticmethod
    def _safe_cache_key(s: str) -> str:
        return "".join(
            ch if ch.isalnum() or ch in "._-" else "_" for ch in (s or "").strip()
        ) or "x"

    @staticmethod
    def _sniff_image_mime(data: bytes) -> str:
        if len(data) >= 2 and data[0:2] == b"\xff\xd8":
            return "image/jpeg"
        if len(data) >= 8 and data[0:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if len(data) >= 6 and data[0:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    @staticmethod
    def kiosk_cache_root() -> Optional[str]:
        """Disk cache root for kiosk asset caches (photos and OSM tiles)."""
        flag = (os.environ.get("MERIDIAN_KIOSK_PHOTO_CACHE") or "1").strip().lower()
        if flag in ("0", "false", "no"):
            return None
        custom = (os.environ.get("MERIDIAN_KIOSK_CACHE_DIR") or "").strip()
        if custom:
            return os.path.abspath(custom)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[dict] = None,
        session: Optional["requests.Session"] = None,
        photo_cache_root: Optional[str] = None,
    ):
        self._base = (base_url or "").rstrip("/")
        self._headers = headers or {}
        self._session = session
        self._cache_root = (
            photo_cache_root
            if photo_cache_root is not None
            else self.kiosk_cache_root()
        )
        self._photo_cache_dir = (
            os.path.join(self._cache_root, "photos") if self._cache_root else None
        )
        if self._photo_cache_dir:
            try:
                os.makedirs(self._photo_cache_dir, exist_ok=True)
            except Exception:
                self._photo_cache_dir = None

    def _cache_path_for_url(self, url: str) -> Optional[str]:
        if not self._photo_cache_dir:
            return None
        digest = hashlib.sha256((url or "").encode("utf-8")).hexdigest()
        safe = self._safe_cache_key(digest)
        return os.path.join(self._photo_cache_dir, safe)

    def _data_uri_from_bytes(self, raw: bytes, mime_hint: str = "") -> Optional[str]:
        if not raw:
            return None
        try:
            import base64
        except ImportError:
            return None
        mime = (mime_hint or "").strip() or self._sniff_image_mime(raw)
        b64 = base64.b64encode(raw).decode()
        return f"data:{mime};base64,{b64}"

    def _read_cached_photo_b64(self, url: str) -> Optional[str]:
        cache_path = self._cache_path_for_url(url)
        if not cache_path or not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "rb") as f:
                raw = f.read()
            return self._data_uri_from_bytes(raw, "")
        except Exception as e:
            logger.debug(f"Photo cache read failed for {url}: {e}")
            return None

    def _write_cached_photo(self, url: str, raw: bytes) -> bool:
        cache_path = self._cache_path_for_url(url)
        if not cache_path or not raw:
            return False
        try:
            with open(cache_path, "wb") as f:
                f.write(raw)
            return True
        except Exception as e:
            logger.debug(f"Photo cache write failed for {url}: {e}")
            return False

    def fetch_photo_b64(self, url: str) -> Optional[str]:
        """Fetch any photo URL via authenticated session, return data URI or None."""
        if not url:
            return None
        cached = self._read_cached_photo_b64(url)
        if cached:
            return cached
        try:
            client = self._session if self._session else requests
            r = client.get(url, headers=self._headers, timeout=5)
            if r.ok and r.content:
                mime = r.headers.get("Content-Type", "image/jpeg")
                self._write_cached_photo(url, r.content)
                return self._data_uri_from_bytes(r.content, mime)
            logger.debug(f"Photo fetch {url} -> {r.status_code}")
        except Exception as e:
            logger.debug(f"Photo fetch {url} failed: {e}")
        return None


    def get_user_photo_b64(self, user_id: str) -> Optional[str]:
        user_id = (user_id or "").strip()
        if not user_id:
            return None
        quoted = urllib.parse.quote(user_id, safe="")
        return self.fetch_photo_b64(f"{self._base}/api/users/{quoted}/photo")


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
