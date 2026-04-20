"""
Server-only: lazy DB-backed service getters (one QueryManager, shared service cache).

Scope: construct domain services for the Flask/API process (api.py uses this as the single
factory). Service modules may import each other for constructor injection (e.g. UserService
and FamilyService); helpers such as photos.is_safe_saved_upload_basename are plain functions.

Not here: kiosk remote clients, kiosk package imports, or Flask route definitions.
"""

try:
    from ...shared.config import DatabaseConfig
except ImportError:
    from shared.config import DatabaseConfig
from .safe_query_manager import QueryManager
from .user import ContactService, FamilyService, UserService
from .calendar import CalendarService
from .medical import MedicationService
from .location import LocationService
from .emergency import EmergencyService
from .care_recipient import CareRecipientService
from .notification import PushNotificationService
from .photos import PhotoUploadService
from .call_signal import CallSignalService


class DatabaseServices:
    def __init__(self, db_path: str = "meridian_kiosk.db"):
        self.db_path = db_path
        self._db_manager = None
        self._services = {}

    def _get_query_manager(self):
        if self._db_manager is None:
            self._db_manager = QueryManager(
                DatabaseConfig(path=self.db_path, create_if_missing=True)
            )
        return self._db_manager

    def ensure_schema(self) -> bool:
        """Create database schema if missing. Call on server startup."""
        r = self._get_query_manager().create_database_schema()
        return r.success

    def _get_or_create(self, key: str, factory):
        # Lazy singleton per key; factory may call other getters (order-safe via _services checks).
        if key not in self._services:
            self._services[key] = factory()
        return self._services[key]

    def get_contact_service(self):
        return self._get_or_create(
            "contact_service",
            lambda: ContactService(self._get_query_manager()),
        )

    def get_user_service(self):
        return self._get_or_create(
            "user_service",
            lambda: UserService(
                self._get_query_manager(),
                self.get_family_service(),
            ),
        )

    def get_calendar_service(self):
        return self._get_or_create(
            "calendar_service",
            lambda: CalendarService(self._get_query_manager()),
        )

    def get_medication_service(self):
        return self._get_or_create(
            "medication_service",
            lambda: MedicationService(self._get_query_manager()),
        )

    def get_location_service(self):
        return self._get_or_create(
            "location_service",
            lambda: LocationService(self._get_query_manager()),
        )

    def get_emergency_service(self):
        return self._get_or_create(
            "emergency_service",
            lambda: EmergencyService(
                self._get_query_manager(),
                self.get_contact_service(),
            ),
        )

    def get_care_recipient_service(self):
        return self._get_or_create(
            "care_recipient_service",
            lambda: CareRecipientService(self._get_query_manager()),
        )

    def get_family_service(self):
        return self._get_or_create(
            "family_service",
            lambda: FamilyService(self._get_query_manager()),
        )

    def get_notification_service(self):
        return self._get_or_create(
            "notification_service",
            lambda: PushNotificationService(self._get_query_manager()),
        )

    def get_photo_upload_service(self):
        return self._get_or_create(
            "photo_upload_service",
            lambda: PhotoUploadService(self.get_user_service()),
        )

    def get_call_signal_service(self):
        return self._get_or_create(
            "call_signal_service",
            lambda: CallSignalService(self._get_query_manager()),
        )


def create_service_container(db_path: str = "meridian_kiosk.db") -> DatabaseServices:
    return DatabaseServices(db_path)
