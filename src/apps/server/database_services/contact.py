"""
Contact service for Meridian.
Loads contacts from SQLite database.

WHERE FUNCTIONALITY MOVED TO (client): No direct API; client uses RemoteEmergencyService.
WHERE IT'S USED (server): emergency_service uses this; server/app.py exposes via GET /api/emergency/*.

REMOVAL: Required on server (used by emergency_service). Can be omitted from client deployment when SERVER_URL is set.
"""

from typing import List, Optional
from dataclasses import dataclass

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


@dataclass
class Contact:
    id: str
    display_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None
    relationship: Optional[str] = None
    emergency_priority: Optional[str] = None
    photo_filename: Optional[str] = None
    sendbird_user_id: Optional[str] = None
    user_id: Optional[str] = None

    def __str__(self):
        return f"{self.display_name} ({self.relationship}) - {self.phone}"

    def to_display_text(self):
        return f"• {self.display_name} - {self.phone}\n  {self.relationship}"


class ContactService:

    def get_all_contacts(self, family_circle_id: str) -> ServiceResult:
        query = """
            SELECT c.id, c.display_name, c.phone, c.email, c.birthday, c.relationship,
                   c.emergency_priority, c.photo_filename, c.sendbird_user_id,
                   (SELECT u.id FROM users u
                    INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
                    WHERE ufc.family_circle_id = c.family_circle_id
                      AND u.sendbird_user_id = c.sendbird_user_id
                      AND c.sendbird_user_id IS NOT NULL AND c.sendbird_user_id != ''
                    LIMIT 1) AS user_id
            FROM contacts c
            WHERE c.family_circle_id = ?
        """
        result = self.safe_query(query, (family_circle_id,))
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
                emergency_priority=row["emergency_priority"],
                photo_filename=row.get("photo_filename"),
                sendbird_user_id=row.get("sendbird_user_id"),
                user_id=row.get("user_id"),
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def c_service_get_emergency_contacts(self, family_circle_id: str) -> ServiceResult:
        query = """
            SELECT c.id, c.display_name, c.phone, c.email, c.birthday, c.relationship,
                   c.emergency_priority, c.photo_filename, c.sendbird_user_id,
                   (SELECT u.id FROM users u
                    INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
                    WHERE ufc.family_circle_id = c.family_circle_id
                      AND u.sendbird_user_id = c.sendbird_user_id
                      AND c.sendbird_user_id IS NOT NULL AND c.sendbird_user_id != ''
                    LIMIT 1) AS user_id
            FROM contacts c
            WHERE c.family_circle_id = ? AND c.emergency_priority IN ('primary_emergency', 'secondary_emergency')
        """
        result = self.safe_query(query, (family_circle_id,))
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
                emergency_priority=row["emergency_priority"],
                photo_filename=row.get("photo_filename"),
                sendbird_user_id=row.get("sendbird_user_id"),
                user_id=row.get("user_id"),
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def get_contact_in_family(
        self, contact_id: str, family_circle_id: str
    ) -> ServiceResult:
        """Get contact by id, ensuring it belongs to the family."""
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, emergency_priority, photo_filename, sendbird_user_id
            FROM contacts WHERE id = ? AND family_circle_id = ?
        """
        result = self.safe_query(query, (contact_id, family_circle_id))
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
                    emergency_priority=row["emergency_priority"],
                    photo_filename=row.get("photo_filename"),
                    sendbird_user_id=row.get("sendbird_user_id"),
                )
            )
        return ServiceResult.error_result(f"Contact with ID '{contact_id}' not found")

    def get_contact_by_id(self, contact_id: str) -> ServiceResult:
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, emergency_priority, photo_filename, sendbird_user_id
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
                    emergency_priority=row["emergency_priority"],
                    photo_filename=row.get("photo_filename"),
                    sendbird_user_id=row.get("sendbird_user_id"),
                )
            )
        return ServiceResult.error_result(f"Contact with ID '{contact_id}' not found")
