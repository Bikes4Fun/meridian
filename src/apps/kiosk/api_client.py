"""
Remote API client for the Meridian server.
Used when SERVER_URL is set. Time comes from the device (LocalTimeService);
calendar, medications, emergency, and settings come from the server API.
"""

import logging
import os
import urllib.parse
from datetime import datetime
from typing import Any, Optional, Tuple
import requests

try:
    from shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


class RemoteServiceError(Exception):
    """Raised when a remote API request fails in an unrecoverable way."""


def fetch_photo_b64(url: str, session: Any, headers: dict) -> Optional[str]:
    """Fetch any photo URL via authenticated session, return data URI or None. Avoids file:// auth for <img>."""
    if not url:
        return None
    try:
        import requests
        import base64
    except ImportError:
        return None
    try:
        client = session if session else requests
        r = client.get(url, headers=headers, timeout=5)
        if r.ok and r.content:
            mime = r.headers.get("Content-Type", "image/jpeg")
            b64 = base64.b64encode(r.content).decode()
            return f"data:{mime};base64,{b64}"
        logger.debug(f"Photo fetch {url} -> {r.status_code}")
    except Exception as e:
        logger.debug(f"Photo fetch {url} failed: {e}")
    return None


def _headers(
    kiosk_user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
) -> dict:
    out = {}
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
        import requests
    except ImportError:
        return False, None, "requests not installed"
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
    """Shared HTTP request. Returns (ok, data, err). Used by _calendar_request and location/checkin."""
    try:
        import requests
    except ImportError:
        return False, None, "requests not installed"
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
        r.raise_for_status()
        j = r.json() if r.content else {}
        if isinstance(j, dict) and "error" in j:
            return False, None, j["error"]
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
        import requests
    except ImportError:
        return False, None, "requests not installed"
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
        self._base = base_url.rstrip("/")

    def get_time(self) -> str:
        return datetime.now().strftime("%-I:%M %p").replace(" 0", " ").lstrip()

    def get_dayof_week(self) -> str:
        return datetime.now().strftime("%A")

    def get_am_pm(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Morning"
        if hour < 17:
            return "Afternoon"
        return "Evening"

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
        return _calendar_request(
            "POST",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events",
            self._headers,
            self._session,
            json_body=payload,
        )

    def update_event(self, event_id: str, payload: dict) -> Any:
        """PUT event. Shared by kiosk, webapp, mobile, etc."""
        quoted = urllib.parse.quote(event_id, safe="")
        return _calendar_request(
            "PUT",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events/{quoted}",
            self._headers,
            self._session,
            json_body=payload,
        )

    def delete_event(self, event_id: str) -> Any:
        """DELETE event. Shared by kiosk, webapp, mobile, etc."""
        quoted = urllib.parse.quote(event_id, safe="")
        return _calendar_request(
            "DELETE",
            f"{self._base}/api/family_circles/{self._fc_id}/calendar/events/{quoted}",
            self._headers,
            self._session,
        )


def _calendar_request(
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
        return _calendar_request(
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
        return _calendar_request(
            "PUT",
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}",
            self._headers,
            self._session,
            json_body=payload,
        )

    def delete_medication(self, medication_id: int) -> Any:
        return _calendar_request(
            "DELETE",
            f"{self._base}/api/family_circles/{self._fc_id}/medications/{medication_id}",
            self._headers,
            self._session,
        )

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> Any:
        return _calendar_request(
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

    def get_emergency_profile(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/emergency-profile",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "emergency-profile request failed")
        return ServiceResult.success_result(data)

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


class RemoteChatEntryService:
    """Get signed chat entry URL for kiosk webview. Uses same API auth as other kiosk calls."""

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

    def get_entry_url(
        self, recipient_sendbird_user_id: str = "", recipient_display_name: str = ""
    ) -> Any:
        """Fetch signed entry URL. recipient = who the kiosk user will chat WITH. Returns ServiceResult with url in data."""
        params = []
        if recipient_sendbird_user_id:
            params.append(
                f"recipient_sendbird_user_id={urllib.parse.quote(recipient_sendbird_user_id)}"
            )
        if recipient_display_name:
            params.append(
                f"recipient_display_name={urllib.parse.quote(recipient_display_name)}"
            )
        qs = "&".join(params)
        url = f"{self._base}/api/chat/chat-session-url" + ("?" + qs if qs else "")
        ok, data, err = _get(url, headers=self._headers, session=self._session)
        if not ok:
            return ServiceResult.error_result(err or "entry-url request failed")
        url_val = data.get("url") if isinstance(data, dict) else None
        if not url_val:
            return ServiceResult.error_result("entry-url returned no url")
        return ServiceResult.success_result(url_val)


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

    def get_contacts(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/contacts",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "contacts request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def fetch_photo(self, url: str) -> Optional[str]:
        """Fetch any photo URL; returns data URI or None."""
        return fetch_photo_b64(url, self._session, self._headers)


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

    def fetch_photo(self, url: str) -> Optional[str]:
        """Fetch any photo URL; returns data URI or None."""
        return fetch_photo_b64(url, self._session, self._headers)

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


def create_kiosk_remote(
    server_url: str,
    kiosk_user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
    session: Optional["requests.Session"] = None,
) -> dict:
    """Return services dict for kiosk client: time from device, rest from server API."""
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
        "chat_entry_service": RemoteChatEntryService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "alert_service": RemoteAlertService(
            server_url, kiosk_user_id, family_circle_id, session
        ),
        "_alert_activated": [False],
    }
    return services
