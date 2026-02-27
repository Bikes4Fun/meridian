"""
Simplified service container for Dementia TV application.
Used only by server/app.py. Client uses client/remote.create_remote() instead.
"""

try:
    from ...config import DatabaseConfig
except ImportError:
    from config import DatabaseConfig
from ..database_management.database_manager import DatabaseManager
from .contact_service import ContactService
from .calendar_service import CalendarService
from .medication_service import MedicationService
from .emergency_service import EmergencyService
from .location_service import LocationService
from .ice_profile_service import ICEProfileService


class ServiceContainer:
    def __init__(self, db_path: str = "dementia_tv.db"):
        self.db_path = db_path
        self._db_manager = None
        self. = {}

    def get_database_manager(self):
        if self._db_manager is None:
            self._db_manager = DatabaseManager(
                DatabaseConfig(path=self.db_path, create_if_missing=True)
            )
        return self._db_manager

    def get_contact_service(self):
        if "contact_service" not in self.:
            self.["contact_service"] = ContactService(
                self.get_database_manager()
            )
        return self.["contact_service"]

    def get_calendar_service(self):
        if "calendar_service" not in self.:
            self.["calendar_service"] = CalendarService(
                self.get_database_manager()
            )
        return self.["calendar_service"]

    def get_medication_service(self):
        if "medication_service" not in self.:
            self.["medication_service"] = MedicationService(
                self.get_database_manager()
            )
        return self.["medication_service"]

    def get_emergency_service(self):
        if "emergency_service" not in self.:
            self.["emergency_service"] = EmergencyService(
                self.get_contact_service()
            )
        return self.["emergency_service"]

    def get_location_service(self):
        if "location_service" not in self.:
            self.["location_service"] = LocationService(
                self.get_database_manager()
            )
        return self.["location_service"]

    def get_ice_profile_service(self):
        if "ice_profile_service" not in self.:
            self.["ice_profile_service"] = ICEProfileService(
                self.get_database_manager()
            )
        return self.["ice_profile_service"]


def create_service_container(db_path: str = "dementia_tv.db") -> ServiceContainer:
    return ServiceContainer(db_path)
