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
