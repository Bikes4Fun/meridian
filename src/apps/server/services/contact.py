"""
Contact service for Dementia TV application.
Loads contacts from SQLite database.

WHERE FUNCTIONALITY MOVED TO (client): No direct API; client uses RemoteEmergencyService.
WHERE IT'S USED (server): emergency_service uses this; server/app.py exposes via GET /api/emergency/*.

REMOVAL: Required on server (used by emergency_service). Can be omitted from client deployment when SERVER_URL is set.
"""

from typing import List, Optional
from dataclasses import dataclass

from ..database_management.database_manager import DatabaseManager, DatabaseServiceMixin

try:
    from ...interfaces import ServiceResult
except ImportError:
    from interfaces import ServiceResult


@dataclass
class Contact:
    id: str
    display_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None
    relationship: Optional[str] = None
    priority: Optional[str] = None

    def __str__(self):
        return f"{self.display_name} ({self.relationship}) - {self.phone}"

    def to_display_text(self):
        return f"• {self.display_name} - {self.phone}\n  {self.relationship}"


class ContactService(DatabaseServiceMixin):
    def __init__(self, db_manager: DatabaseManager):
        DatabaseServiceMixin.__init__(self, db_manager)

    def get_all_contacts(self) -> ServiceResult:
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, priority
            FROM contacts
        """
        result = self.safe_query(query)
        if not result.success:
            return result
        contacts = [
            Contact(
                id=row["id"],
                display_name=row["display_name"],
                phone=row["phone"],
                email=row["email"],
                birthday=row["birthday"],
                relationship=row["relationship"],
                priority=row["priority"],
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def get_emergency_contacts(self) -> ServiceResult:
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, priority
            FROM contacts
            WHERE priority IN ('primary_emergency', 'secondary_emergency')
        """
        result = self.safe_query(query)
        if not result.success:
            return result
        contacts = [
            Contact(
                id=row["id"],
                display_name=row["display_name"],
                phone=row["phone"],
                email=row["email"],
                birthday=row["birthday"],
                relationship=row["relationship"],
                priority=row["priority"],
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def get_contact_by_id(self, contact_id: str) -> ServiceResult:
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, priority
            FROM contacts WHERE id = ?
        """
        result = self.safe_query(query, (contact_id,))
        if not result.success:
            return result
        if result.data:
            row = result.data[0]
            return ServiceResult.success_result(
                Contact(
                    id=row["id"],
                    display_name=row["display_name"],
                    phone=row["phone"],
                    email=row["email"],
                    birthday=row["birthday"],
                    relationship=row["relationship"],
                    priority=row["priority"],
                )
            )
        return ServiceResult.error_result(f"Contact with ID '{contact_id}' not found")

    def format_emergency_contacts_for_display(self) -> ServiceResult:
        result = self.get_emergency_contacts()
        if not result.success:
            return result
        emergency_contacts = result.data
        if not emergency_contacts:
            return ServiceResult.success_result("No emergency contacts found")
        lines = ["Emergency Contacts:"]
        for contact in emergency_contacts:
            lines.append(contact.to_display_text())
        return ServiceResult.success_result("\n".join(lines))
