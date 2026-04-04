"""
User service for Meridian.
Read/write users. SQLite enforces sendbird_user_id uniqueness per family.
"""

import sqlite3
from typing import Optional

from ..database_manager import DatabaseManager
from .saved_upload_basename import is_safe_saved_upload_basename

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_user_photo_filename(
        self, user_id: str, family_circle_id: str
    ) -> Optional[str]:
        """Get photo_filename for user if they belong to family. None if not found or invalid."""
        r = self.db_manager.execute_query(
            "SELECT u.photo_filename FROM users u "
            "INNER JOIN user_family_circle ufc ON u.id = ufc.user_id "
            "WHERE u.id = ? AND ufc.family_circle_id = ?",
            (user_id, family_circle_id),
        )
        if not r.success or not r.data:
            return None
        fn = (r.data[0].get("photo_filename") or "").strip()
        if not fn or not is_safe_saved_upload_basename(fn):
            return None
        return fn

    def set_user_photo_filename(
        self, user_id: str, family_circle_id: str, photo_filename: Optional[str]
    ) -> ServiceResult:
        """Set users.photo_filename; user must be in family. Filename must be a safe basename."""
        mem = self.db_manager.execute_query(
            "SELECT 1 FROM user_family_circle WHERE user_id = ? AND family_circle_id = ?",
            (user_id, family_circle_id),
        )
        if not mem.success or not mem.data:
            return ServiceResult.error_result("user not in family")
        fn = (photo_filename or "").strip()
        if fn and not is_safe_saved_upload_basename(fn):
            return ServiceResult.error_result("invalid photo filename")
        u = self.db_manager.execute_update(
            "UPDATE users SET photo_filename = ? WHERE id = ?",
            (fn if fn else None, user_id),
        )
        if not u.success:
            return u
        return ServiceResult.success_result({"user_id": user_id, "photo_filename": fn or None})

    def get_display_name(self, user_id: str) -> str:
        """Get user display_name; returns user_id if not found."""
        r = self.db_manager.execute_query(
            "SELECT display_name FROM users WHERE id = ?", (user_id,)
        )
        if r.success and r.data:
            dn = (r.data[0].get("display_name") or "").strip()
            return dn if dn else user_id
        return user_id

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
            return ServiceResult.error_result("An internal error occurred")
