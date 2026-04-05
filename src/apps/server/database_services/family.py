"""
Family service for family circle and member data.
"""

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class FamilyService:
    """Service for family circle and member operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def add_family_circle(self, family_circle_id: str) -> ServiceResult:
        """Create family circle if not exists."""
        return self.db_manager.execute_update(
            "INSERT OR IGNORE INTO family_circles (id) VALUES (?)",
            (family_circle_id,),
        )

    def add_user_to_family(self, user_id: str, family_circle_id: str) -> ServiceResult:
        """Link user to family circle."""
        return self.db_manager.execute_update(
            "INSERT OR IGNORE INTO user_family_circle (user_id, family_circle_id) VALUES (?, ?)",
            (user_id, family_circle_id),
        )

    def get_family_members(self, family_circle_id: str) -> ServiceResult:
        """Return users in the family."""
        query = """
            SELECT u.id, u.display_name, u.photo_filename
            FROM users u
            INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
            WHERE ufc.family_circle_id = ?
            ORDER BY u.display_name
        """
        return self.db_manager.execute_query(query, (family_circle_id,))

    def user_belongs_to_family(self, user_id: str, family_circle_id: str) -> ServiceResult:
        """True if user_id is linked to family_circle_id in user_family_circle."""
        r = self.db_manager.execute_query(
            "SELECT 1 FROM user_family_circle WHERE user_id = ? AND family_circle_id = ?",
            (user_id, family_circle_id),
        )
        if not r.success:
            return r
        return ServiceResult.success_result(bool(r.data))
