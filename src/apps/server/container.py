"""
Simplified service container for Meridian.
Used only by server/app.py. Kiosk uses api_client.create_kiosk_remote() instead.
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

    def get_contact_service(self):
        if "contact_service" not in self._services:
            self._services["contact_service"] = ContactService(
                self._get_database_manager()
            )
        return self._services["contact_service"]

    def get_user_service(self):
        if "user_service" not in self._services:
            self._services["user_service"] = UserService(self._get_database_manager())
        return self._services["user_service"]

    def get_calendar_service(self):
        if "calendar_service" not in self._services:
            self._services["calendar_service"] = CalendarService(
                self._get_database_manager()
            )
        return self._services["calendar_service"]

    def get_medication_service(self):
        if "medication_service" not in self._services:
            self._services["medication_service"] = MedicationService(
                self._get_database_manager()
            )
        return self._services["medication_service"]

    def get_location_service(self):
        if "location_service" not in self._services:
            self._services["location_service"] = LocationService(
                self._get_database_manager()
            )
        return self._services["location_service"]

    def get_emergency_service(self):
        if "emergency_service" not in self._services:
            self._services["emergency_service"] = EmergencyService(
                self._get_database_manager(),
                self.get_contact_service(),
            )
        return self._services["emergency_service"]

    def get_care_recipient_service(self):
        if "care_recipient_service" not in self._services:
            self._services["care_recipient_service"] = CareRecipientService(
                self._get_database_manager()
            )
        return self._services["care_recipient_service"]

    def get_family_service(self):
        if "family_service" not in self._services:
            self._services["family_service"] = FamilyService(
                self._get_database_manager()
            )
        return self._services["family_service"]

    def get_push_notification_service(self):
        if "push_notification_service" not in self._services:
            self._services["push_notification_service"] = PushNotificationService(
                self._get_database_manager()
            )
        return self._services["push_notification_service"]

    def get_sendbird_service(self):
        if "sendbird_service" not in self._services:
            self._services["sendbird_service"] = SendbirdService(
                self._get_database_manager()
            )
        return self._services["sendbird_service"]

    def get_photo_upload_service(self):
        if "photo_upload_service" not in self._services:
            self._services["photo_upload_service"] = PhotoUploadService(
                self.get_user_service()
            )
        return self._services["photo_upload_service"]

    def get_call_signal_service(self):
        if "call_signal_service" not in self._services:
            self._services["call_signal_service"] = CallSignalService(
                self._get_database_manager()
            )
        return self._services["call_signal_service"]


def create_service_container(db_path: str = "meridian_kiosk.db") -> ServiceContainer:
    return ServiceContainer(db_path)
