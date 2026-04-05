"""
Server-only: lazy DB-backed service getters (one DatabaseManager, shared service cache).

Scope: construct domain services for the Flask/API process.

Not here: kiosk remote clients, kiosk package imports, or Flask route definitions.
"""

try:
    from ...shared.config import DatabaseConfig
except ImportError:
    from shared.config import DatabaseConfig
from .database_manager import DatabaseManager
from .database_services.contact import ContactService
from .database_services.user import UserService
from .database_services.calendar import CalendarService
from .database_services.medical import MedicationService
from .database_services.location import LocationService
from .database_services.emergency import EmergencyService
from .database_services.care_recipient import CareRecipientService
from .database_services.family import FamilyService
from .database_services.push_notification import PushNotificationService
from .database_services.sendbird import SendbirdService
from .database_services.photo_upload_service import PhotoUploadService
from .database_services.call_signal import CallSignalService


class ServiceContainer:
    def __init__(self, db_path: str = "meridian_kiosk.db"):
        self.db_path = db_path
        self._db_manager = None
        self._services = {}

    def _get_database_manager(self):
        if self._db_manager is None:
            self._db_manager = DatabaseManager(
                DatabaseConfig(path=self.db_path, create_if_missing=True)
            )
        return self._db_manager

    def ensure_schema(self) -> bool:
        """Create database schema if missing. Call on server startup."""
        r = self._get_database_manager().create_database_schema()
        return r.success

    def _get_or_create(self, key: str, factory):
        # Lazy singleton per key; factory may call other getters (order-safe via _services checks).
        if key not in self._services:
            self._services[key] = factory()
        return self._services[key]

    def get_contact_service(self):
        return self._get_or_create(
            "contact_service",
            lambda: ContactService(self._get_database_manager()),
        )

    def get_user_service(self):
        return self._get_or_create(
            "user_service",
            lambda: UserService(
                self._get_database_manager(),
                self.get_family_service(),
            ),
        )

    def get_calendar_service(self):
        return self._get_or_create(
            "calendar_service",
            lambda: CalendarService(self._get_database_manager()),
        )

    def get_medication_service(self):
        return self._get_or_create(
            "medication_service",
            lambda: MedicationService(self._get_database_manager()),
        )

    def get_location_service(self):
        return self._get_or_create(
            "location_service",
            lambda: LocationService(self._get_database_manager()),
        )

    def get_emergency_service(self):
        return self._get_or_create(
            "emergency_service",
            lambda: EmergencyService(
                self._get_database_manager(),
                self.get_contact_service(),
            ),
        )

    def get_care_recipient_service(self):
        return self._get_or_create(
            "care_recipient_service",
            lambda: CareRecipientService(self._get_database_manager()),
        )

    def get_family_service(self):
        return self._get_or_create(
            "family_service",
            lambda: FamilyService(self._get_database_manager()),
        )

    def get_push_notification_service(self):
        return self._get_or_create(
            "push_notification_service",
            lambda: PushNotificationService(self._get_database_manager()),
        )

    def get_sendbird_service(self):
        return self._get_or_create(
            "sendbird_service",
            lambda: SendbirdService(self._get_database_manager()),
        )

    def get_photo_upload_service(self):
        return self._get_or_create(
            "photo_upload_service",
            lambda: PhotoUploadService(self.get_user_service()),
        )

    def get_call_signal_service(self):
        return self._get_or_create(
            "call_signal_service",
            lambda: CallSignalService(self._get_database_manager()),
        )


def create_service_container(db_path: str = "meridian_kiosk.db") -> ServiceContainer:
    return ServiceContainer(db_path)
