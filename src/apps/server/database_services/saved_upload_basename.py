"""Helpers for upload basenames stored in SQLite (e.g. users.photo_filename, care_recipients.photo_path)."""

from typing import Optional, Tuple

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


def is_safe_saved_upload_basename(name: str) -> bool:
    """True if non-empty and no path traversal (basename only; file lives under uploads dir)."""
    n = (name or "").strip()
    return bool(n) and ".." not in n and "/" not in n and "\\" not in n


def care_recipients_stored_photo_state(
    db_manager: DatabaseManager, family_circle_id: str, care_recipient_user_id: str
) -> Tuple[bool, Optional[str]]:
    """Whether a care_recipients row exists; stored photo_path basename or None."""
    r = db_manager.execute_query(
        "SELECT photo_path FROM care_recipients WHERE family_circle_id = ? AND care_recipient_user_id = ?",
        (family_circle_id, care_recipient_user_id),
    )
    if not r.success or not r.data:
        return (False, None)
    p = (r.data[0].get("photo_path") or "").strip()
    if p and not is_safe_saved_upload_basename(p):
        return (True, None)
    return (True, p if p else None)


def set_care_recipients_stored_photo_path(
    db_manager: DatabaseManager,
    family_circle_id: str,
    care_recipient_user_id: str,
    basename: str,
) -> ServiceResult:
    """Set care_recipients.photo_path to a basename only."""
    if not is_safe_saved_upload_basename(basename):
        return ServiceResult.error_result("invalid photo_path")
    r = db_manager.execute_update(
        "UPDATE care_recipients SET photo_path = ? WHERE family_circle_id = ? AND care_recipient_user_id = ?",
        (basename, family_circle_id, care_recipient_user_id),
    )
    if not r.success:
        return r
    if r.data == 0:
        return ServiceResult.error_result("care recipient not found")
    return ServiceResult.success_result(
        {"photo_path": basename, "care_recipient_user_id": care_recipient_user_id}
    )
