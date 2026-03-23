"""
User service for Meridian.
Read/write users. SQLite enforces sendbird_user_id uniqueness per family.
"""

import sqlite3
from typing import Optional

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def add_user(
        self,
        user_id: str,
        display_name: str,
        photo_filename: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        sendbird_user_id: Optional[str] = None,
    ) -> ServiceResult:
        """Insert or replace user. Returns error if sendbird_user_id duplicates another user."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users
                    (id, display_name, photo_filename, family_circle_id, sendbird_user_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        display_name,
                        photo_filename,
                        family_circle_id,
                        sendbird_user_id,
                    ),
                )
                conn.commit()
            return ServiceResult.success_result({"id": user_id})
        except sqlite3.IntegrityError as e:
            err = str(e).lower()
            if "unique" in err or "sendbird" in err:
                return ServiceResult.error_result(
                    "Duplicate sendbird_user_id. Each user must have a unique Sendbird ID."
                )
            return ServiceResult.error_result("Database constraint failed: %s" % e)
