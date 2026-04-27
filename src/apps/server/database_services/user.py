"""
User, family, and contact services for Meridian.
"""

import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import List, Optional

from .safe_query_manager import QueryManager
from .photos import is_safe_saved_upload_basename

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


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
    user_id: Optional[str] = None

    def __str__(self):
        return f"{self.display_name} ({self.relationship}) - {self.phone}"

    def to_display_text(self):
        return f"• {self.display_name} - {self.phone}\n  {self.relationship}"


class ContactService:
    def __init__(self, db_manager: QueryManager):
        self.db_manager = db_manager

    def get_all_contacts(self, family_circle_id: str) -> ServiceResult:
        query = """
            SELECT c.id, c.display_name, c.phone, c.email, c.birthday, c.relationship,
                   c.emergency_priority, c.photo_filename,
                   COALESCE(NULLIF(TRIM(c.linked_user_id), ''),
                     (SELECT u.id FROM users u
                      INNER JOIN family_memberships ufc ON u.id = ufc.user_id
                      WHERE ufc.family_circle_id = c.family_circle_id
                        AND u.display_name = c.display_name
                      LIMIT 1)) AS user_id
            FROM contacts c
            WHERE c.family_circle_id = ?
        """
        result = self.db_manager.execute_query(query, (family_circle_id,))
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
                user_id=row.get("user_id"),
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def get_emergency_contacts(self, family_circle_id: str) -> ServiceResult:
        query = """
            SELECT c.id, c.display_name, c.phone, c.email, c.birthday, c.relationship,
                   c.emergency_priority, c.photo_filename,
                   COALESCE(NULLIF(TRIM(c.linked_user_id), ''),
                     (SELECT u.id FROM users u
                      INNER JOIN family_memberships ufc ON u.id = ufc.user_id
                      WHERE ufc.family_circle_id = c.family_circle_id
                        AND u.display_name = c.display_name
                      LIMIT 1)) AS user_id
            FROM contacts c
            WHERE c.family_circle_id = ? AND c.emergency_priority IN ('primary_emergency', 'secondary_emergency')
        """
        result = self.db_manager.execute_query(query, (family_circle_id,))
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
                user_id=row.get("user_id"),
            )
            for row in result.data
        ]
        return ServiceResult.success_result(contacts)

    def add_contact(
        self,
        contact_id: str,
        family_circle_id: str,
        display_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        birthday: Optional[str] = None,
        relationship: Optional[str] = None,
        emergency_priority: Optional[str] = None,
        photo_filename: Optional[str] = None,
        notes: Optional[str] = None,
        linked_user_id: Optional[str] = None,
    ) -> ServiceResult:
        """Insert or replace contact."""
        return self.db_manager.execute_update(
            """INSERT OR REPLACE INTO contacts
            (id, family_circle_id, display_name, phone, email, birthday, relationship, emergency_priority, photo_filename, notes, linked_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contact_id,
                family_circle_id,
                display_name or "",
                phone,
                email,
                birthday,
                relationship,
                emergency_priority,
                photo_filename,
                notes,
                linked_user_id,
            ),
        )

    def get_contact_in_family(
        self, contact_id: str, family_circle_id: str
    ) -> ServiceResult:
        """Get contact by id, ensuring it belongs to the family."""
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, emergency_priority, photo_filename
            FROM contacts WHERE id = ? AND family_circle_id = ?
        """
        result = self.db_manager.execute_query(query, (contact_id, family_circle_id))
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
                )
            )
        return ServiceResult.error_result(f"Contact with ID '{contact_id}' not found")

    def get_contact_by_id(self, contact_id: str) -> ServiceResult:
        query = """
            SELECT id, display_name, phone, email, birthday, relationship, emergency_priority, photo_filename
            FROM contacts WHERE id = ?
        """
        result = self.db_manager.execute_query(query, (contact_id,))
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
                )
            )
        return ServiceResult.error_result(f"Contact with ID '{contact_id}' not found")


class FamilyService:
    """Service for family circle and member operations."""

    def __init__(self, db_manager: QueryManager):
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
            "INSERT OR IGNORE INTO family_memberships (user_id, family_circle_id) VALUES (?, ?)",
            (user_id, family_circle_id),
        )

    def get_family_members(self, family_circle_id: str) -> ServiceResult:
        """Return users in the family."""
        query = """
            SELECT u.id, u.display_name, u.photo_filename
            FROM users u
            INNER JOIN family_memberships ufc ON u.id = ufc.user_id
            WHERE ufc.family_circle_id = ?
            ORDER BY u.display_name
        """
        return self.db_manager.execute_query(query, (family_circle_id,))

    def user_belongs_to_family(self, user_id: str, family_circle_id: str) -> ServiceResult:
        """True if user_id is linked to family_circle_id in family_memberships."""
        r = self.db_manager.execute_query(
            "SELECT 1 FROM family_memberships WHERE user_id = ? AND family_circle_id = ?",
            (user_id, family_circle_id),
        )
        if not r.success:
            return r
        return ServiceResult.success_result(bool(r.data))

    def get_kiosk_emergency_alert_activated(
        self, family_circle_id: str
    ) -> ServiceResult:
        """Whether the kiosk emergency screen is activated for this family (DB-backed)."""
        r = self.db_manager.execute_query(
            "SELECT activated FROM kiosk_emergency_alerts WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        if not r.success:
            return r
        rows = r.data or []
        if not rows:
            return ServiceResult.success_result(False)
        return ServiceResult.success_result(bool(rows[0].get("activated")))

    def set_kiosk_emergency_alert_activated(
        self, family_circle_id: str, activated: bool
    ) -> ServiceResult:
        """Persist kiosk emergency alert; survives multi-worker API processes."""
        val = 1 if activated else 0
        r = self.db_manager.execute_update(
            """
            INSERT INTO kiosk_emergency_alerts (family_circle_id, activated)
            VALUES (?, ?)
            ON CONFLICT(family_circle_id) DO UPDATE SET activated = excluded.activated
            """,
            (family_circle_id, val),
        )
        if not r.success:
            return r
        return ServiceResult.success_result(bool(activated))

    def user_has_permission(
        self, user_id: str, family_circle_id: str, permission: str
    ) -> ServiceResult:
        """True when user has family-scoped permission."""
        if not user_id or not family_circle_id or not permission:
            return ServiceResult.error_result(
                "user_id, family_circle_id, and permission required"
            )
        r = self.db_manager.execute_query(
            """
            SELECT 1
            FROM family_permissions
            WHERE user_id = ? AND family_circle_id = ? AND permission = ?
            LIMIT 1
            """,
            (user_id, family_circle_id, permission),
        )
        if not r.success:
            return r
        return ServiceResult.success_result(bool(r.data))

    def get_permissions(
        self, family_circle_id: str, user_id: str = ""
    ) -> ServiceResult:
        r = self.db_manager.execute_query(
            """
            SELECT user_id, permission
            FROM family_permissions
            WHERE family_circle_id = ?
            ORDER BY user_id, permission
            """,
            (family_circle_id,),
        )
        if not r.success:
            return r
        data_by_user = {}
        for row in r.data or []:
            uid = (row.get("user_id") or "").strip()
            perm = (row.get("permission") or "").strip()
            if not uid or not perm:
                continue
            data_by_user.setdefault(uid, []).append(perm)
        target_user_id = (user_id or "").strip()
        if target_user_id:
            return ServiceResult.success_result(data_by_user.get(target_user_id, []))
        return ServiceResult.success_result(data_by_user)

    def get_twilio_number(self, family_circle_id: str) -> Optional[str]:
        """Return E.164 Twilio number: MERIDIAN_DEMO_KIOSK_TWILIO_NUMBER or TWILIO_PHONE_NUMBER if set, else DB."""
        from_env = (
            (os.environ.get("MERIDIAN_DEMO_KIOSK_TWILIO_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER") or "")
            .strip()
        )
        if from_env:
            return from_env
        r = self.db_manager.execute_query(
            "SELECT twilio_phone_number FROM family_circles WHERE id = ? LIMIT 1",
            (family_circle_id,),
        )
        if not r.success or not r.data:
            return None
        return (r.data[0].get("twilio_phone_number") or "").strip() or None

    def get_family_by_twilio_number(self, phone: str) -> Optional[str]:
        """Return family_circle_id for the given Twilio phone number, or None."""
        r = self.db_manager.execute_query(
            "SELECT id FROM family_circles WHERE twilio_phone_number = ? LIMIT 1",
            ((phone or "").strip(),),
        )
        if not r.success or not r.data:
            return None
        return r.data[0].get("id")

    def can_manage_family_permissions(
        self, actor_user_id: str, family_circle_id: str
    ) -> ServiceResult:
        """True when actor may grant/revoke family permissions (with bootstrap allowance)."""
        manage_r = self.user_has_permission(
            actor_user_id, family_circle_id, "family_permissions.manage"
        )
        if not manage_r.success:
            return manage_r
        if manage_r.data:
            return ServiceResult.success_result(True)
        alert_r = self.user_has_permission(
            actor_user_id, family_circle_id, "emergency_alert.manage"
        )
        if not alert_r.success:
            return alert_r
        if alert_r.data:
            return ServiceResult.success_result(True)
        family_perms_r = self.get_permissions(family_circle_id)
        if not family_perms_r.success:
            return family_perms_r
        # Bootstrap: allow first permission assignment in a family with no permissions yet.
        return ServiceResult.success_result(not bool(family_perms_r.data))

    def set_permission(
        self,
        user_id: str,
        family_circle_id: str,
        permission: str,
        granted: bool,
    ) -> ServiceResult:
        member_r = self.user_belongs_to_family(user_id, family_circle_id)
        if not member_r.success:
            return member_r
        if not member_r.data:
            return ServiceResult.error_result("target user not in family")
        if granted:
            r = self.db_manager.execute_update(
                """
                INSERT OR IGNORE INTO family_permissions (user_id, family_circle_id, permission)
                VALUES (?, ?, ?)
                """,
                (user_id, family_circle_id, permission),
            )
        else:
            r = self.db_manager.execute_update(
                """
                DELETE FROM family_permissions
                WHERE user_id = ? AND family_circle_id = ? AND permission = ?
                """,
                (user_id, family_circle_id, permission),
            )
        if not r.success:
            return r
        return ServiceResult.success_result(
            {
                "user_id": user_id,
                "permission": permission,
                "granted": bool(granted),
            }
        )


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
            "INNER JOIN family_memberships ufc ON u.id = ufc.user_id "
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
            "INNER JOIN family_memberships ufc ON u.id = ufc.user_id "
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
