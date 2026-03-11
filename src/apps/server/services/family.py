"""
Family service for family circle and member data.
"""

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

from ..database import DatabaseManager, DatabaseServiceMixin


class FamilyService(DatabaseServiceMixin):
    """Service for family circle and member operations."""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)

    def get_family_members(self, family_circle_id: str) -> ServiceResult:
        """Return users in the family."""
        query = """
            SELECT u.id, u.display_name, u.photo_filename
            FROM users u
            INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
            WHERE ufc.family_circle_id = ?
            ORDER BY u.display_name
        """
        return self.safe_query(query, (family_circle_id,))

    def get_photo_filename(self, entity_type: str, entity_id: str, family_circle_id: str) -> ServiceResult:
        """Photo filename for user or contact if in family; data is str or None. entity_type: 'user' or 'contact'."""
        if entity_type == "user":
            r = self.safe_query(
                "SELECT u.photo_filename FROM users u "
                "INNER JOIN user_family_circle ufc ON u.id = ufc.user_id "
                "WHERE u.id = ? AND ufc.family_circle_id = ?",
                (entity_id, family_circle_id),
            )
        elif entity_type == "contact":
            r = self.safe_query(
                "SELECT photo_filename FROM contacts WHERE id = ? AND family_circle_id = ?",
                (entity_id, family_circle_id),
            )
        else:
            return ServiceResult.error_result("entity_type must be 'user' or 'contact'")
        if not r.success or not r.data:
            return ServiceResult.error_result("Entity not found or not in family")
        fn = (r.data[0].get("photo_filename") or "").strip()
        return ServiceResult.success_result(fn if fn else None)
