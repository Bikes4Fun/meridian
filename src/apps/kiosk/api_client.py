"""
Remote API client for the Meridian server.
Used when SERVER_URL is set. Time comes from the device (LocalTimeService);
calendar, medications, emergency, and settings come from the server API.
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional, Tuple

try:
    from shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


class RemoteServiceError(Exception):
    """Raised when a remote API request fails in an unrecoverable way."""


def _headers(
    user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
) -> dict:
    out = {}
    if user_id:
        out["X-User-Id"] = user_id
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
        client = session if session else requests
        r = client.get(url, timeout=timeout, headers=headers or {})
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            return False, None, j["error"]
        if "data" in j:
            return True, j["data"], None
        return True, j, None
    except Exception as e:
        logger.debug("Request failed %s: %s", url, e)
        return False, None, str(e)


class LocalTimeService:
    """Time from the device (no server call)."""

    def __init__(self, base_url: str, user_id: Optional[str] = None):
        self._base = base_url.rstrip("/")
        self._user_id = user_id

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
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(user_id, family_circle_id)
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


class RemoteMedicationService:
    def __init__(
        self,
        base_url: str,
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(user_id, family_circle_id)
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


class RemoteEmergencyService:
    def __init__(
        self,
        base_url: str,
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(user_id, family_circle_id)
        self._session = session

    def get_emergency_contacts(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/contacts",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(
                err or "emergency/contacts request failed"
            )
        contacts = data if isinstance(data, list) else (data or [])
        return ServiceResult.success_result(contacts)

    def get_medical_summary(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/medical-summary",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(
                err or "emergency/medical-summary request failed"
            )
        return ServiceResult.success_result(data)


class RemoteAlertService:
    def __init__(
        self,
        base_url: str,
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._headers = _headers(user_id, family_circle_id)
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


class RemoteICEProfileService:
    def __init__(
        self,
        base_url: str,
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(user_id, family_circle_id)
        self._session = session

    def get_ice_profile(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/ice-profile",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "ice request failed")
        return ServiceResult.success_result(data)


class RemoteLocationService:
    def __init__(
        self,
        base_url: str,
        user_id: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        session: Optional["requests.Session"] = None,
    ):
        self._base = base_url.rstrip("/")
        self._fc_id = family_circle_id or ""
        self._headers = _headers(user_id, family_circle_id)
        self._session = session

    def get_checkins(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/checkins",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "location/latest request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def get_named_places(self) -> Any:
        ok, data, err = _get(
            f"{self._base}/api/family_circles/{self._fc_id}/named-places",
            headers=self._headers,
            session=self._session,
        )
        if not ok:
            return ServiceResult.error_result(err or "location/places request failed")
        return ServiceResult.success_result(data if data is not None else [])

    def create_checkin(
        self,
        contact_id: str,
        latitude: float,
        longitude: float,
        notes: Optional[str] = None,
    ) -> Any:
        """Create check-in. location_name resolved from GPS. notes = user message."""
        try:
            import requests
        except ImportError:
            return ServiceResult.error_result("requests not installed")
        try:
            payload = {
                "contact_id": contact_id,
                "latitude": latitude,
                "longitude": longitude,
            }
            if notes:
                payload["notes"] = notes

            client = self._session if self._session else requests
            r = client.post(
                f"{self._base}/api/family_circles/{self._fc_id}/checkin",
                json=payload,
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                return ServiceResult.error_result(j["error"])
            return ServiceResult.success_result(j.get("data"))
        except Exception as e:
            logger.debug("Check-in request failed: %s", e)
            return ServiceResult.error_result(str(e))

    def fetch_photo_to_cache(self, user_id: str, cache_dir: str) -> Optional[str]:
        """Fetch photo from server and save to cache. Returns local path or None. Reuses cache if present."""
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
            logger.debug("Photo fetch failed for %s: %s", user_id, e)
            return None


def get_display_settings(
    server_url: str,
    user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
    session: Optional["requests.Session"] = None,
):
    """Load display settings from kiosk_settings.json. API override disabled for now."""
    from .settings import DisplaySettings

    return DisplaySettings.default()


def create_remote(
    server_url: str,
    user_id: Optional[str] = None,
    family_circle_id: Optional[str] = None,
    session: Optional["requests.Session"] = None,
) -> dict:
    """Return services dict: time from device, rest from server API."""
    try:
        import requests

        if session is None:
            session = requests.Session()
    except ImportError:
        session = None
    services = {
        "time_service": LocalTimeService(server_url, user_id),
        "calendar_service": RemoteCalendarService(
            server_url, user_id, family_circle_id, session
        ),
        "medication_service": RemoteMedicationService(
            server_url, user_id, family_circle_id, session
        ),
        "emergency_service": RemoteEmergencyService(
            server_url, user_id, family_circle_id, session
        ),
        "ice_profile_service": RemoteICEProfileService(
            server_url, user_id, family_circle_id, session
        ),
        "location_service": RemoteLocationService(
            server_url, user_id, family_circle_id, session
        ),
        "alert_service": RemoteAlertService(
            server_url, user_id, family_circle_id, session
        ),
    }
    services["_alert_activated"] = [False]
    return services
