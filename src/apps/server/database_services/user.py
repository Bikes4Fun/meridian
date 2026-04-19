"""
User service for Meridian.
Read/write users.
"""

import sqlite3
import logging
from typing import Optional

from .safe_query_manager import QueryManager
from .family import FamilyService
from .photos import is_safe_saved_upload_basename

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db_manager: QueryManager, family_service: FamilyService):
        self.db_manager = db_manager
        self._family_service = family_service

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
        mem = self._family_service.user_belongs_to_family(user_id, family_circle_id)
        if not mem.success:
            return mem
        if not mem.data:
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

    def get_user_phone_for_family(
        self, user_id: str, family_circle_id: str
    ) -> ServiceResult:
        """Phone on file for user if they belong to family (caller ID for voice)."""
        mem = self._family_service.user_belongs_to_family(user_id, family_circle_id)
        if not mem.success:
            return mem
        if not mem.data:
            return ServiceResult.error_result("user not in family")
        r = self.db_manager.execute_query(
            "SELECT u.phone FROM users u "
            "INNER JOIN user_family_circle ufc ON u.id = ufc.user_id "
            "WHERE u.id = ? AND ufc.family_circle_id = ?",
            (user_id, family_circle_id),
        )
        if not r.success:
            return r
        if not r.data:
            return ServiceResult.success_result("")
        p = (r.data[0].get("phone") or "").strip()
        return ServiceResult.success_result(p)

    def add_user(
        self,
        user_id: str,
        display_name: str,
        photo_filename: Optional[str] = None,
        family_circle_id: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> ServiceResult:
        """Insert or replace user."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users
                    (id, display_name, photo_filename, family_circle_id, phone)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        display_name,
                        photo_filename,
                        family_circle_id,
                        (phone or "").strip() or None,
                    ),
                )
                conn.commit()
            return ServiceResult.success_result({"id": user_id})
        except sqlite3.IntegrityError as e:
            logger.warning(f"User insert integrity error: {e}")
            return ServiceResult.error_result("Unable to save user due to a data conflict")
