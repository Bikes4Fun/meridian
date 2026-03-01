"""
Simplified service container for Meridian.
Used only by server/app.py. Client uses client/remote.create_remote() instead.
"""

try:
    from ....shared.config import DatabaseConfig
except ImportError:
    from shared.config import DatabaseConfig
from ..database import DatabaseManager
from .contact import ContactService
from .calendar import CalendarService
from .medication import MedicationService
from .emergency import EmergencyService
from .location import LocationService
from .ice_profile import ICEProfileService
from .care_recipient import CareRecipientService
from .family import FamilyService


class ServiceContainer:
    def __init__(self, db_path: str = "meridian_kiosk.db"):
        self.db_path = db_path
        self._db_manager = None
        self._services = {}

    def get_database_manager(self):
        if self._db_manager is None:
            self._db_manager = DatabaseManager(
                DatabaseConfig(path=self.db_path, create_if_missing=True)
            )
        return self._db_manager

    def get_contact_service(self):
        if "contact_service" not in self._services:
            self._services["contact_service"] = ContactService(
                self.get_database_manager()
            )
        return self._services["contact_service"]

    def get_calendar_service(self):
        if "calendar_service" not in self._services:
            self._services["calendar_service"] = CalendarService(
                self.get_database_manager()
            )
        return self._services["calendar_service"]

    def get_medication_service(self):
        if "medication_service" not in self._services:
            self._services["medication_service"] = MedicationService(
                self.get_database_manager()
            )
        return self._services["medication_service"]

    def get_emergency_service(self):
        if "emergency_service" not in self._services:
            self._services["emergency_service"] = EmergencyService(
                self.get_contact_service()
            )
        return self._services["emergency_service"]

    def get_location_service(self):
        if "location_service" not in self._services:
            self._services["location_service"] = LocationService(
                self.get_database_manager()
            )
        return self._services["location_service"]

    def get_ice_profile_service(self):
        if "ice_profile_service" not in self._services:
            self._services["ice_profile_service"] = ICEProfileService(
                self.get_database_manager()
            )
        return self._services["ice_profile_service"]

    def get_care_recipient_service(self):
        if "care_recipient_service" not in self._services:
            self._services["care_recipient_service"] = CareRecipientService(
                self.get_database_manager()
            )
        return self._services["care_recipient_service"]

    def get_family_service(self):
        if "family_service" not in self._services:
            self._services["family_service"] = FamilyService(
                self.get_database_manager()
            )
        return self._services["family_service"]


def create_service_container(db_path: str = "meridian_kiosk.db") -> ServiceContainer:
    return ServiceContainer(db_path)
