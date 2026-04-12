"""Profile photo uploads, upload-dir helpers, and safe basename checks for stored filenames."""

import os
import uuid
from pathlib import Path
from typing import Any, Optional, Tuple

from werkzeug.utils import secure_filename

from .safe_query_manager import QueryManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

MAX_PROFILE_PHOTO_BYTES = 8 * 1024 * 1024

_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def is_safe_saved_upload_basename(name: str) -> bool:
    """True if non-empty and no path traversal (basename only; file lives under uploads dir)."""
    n = (name or "").strip()
    return bool(n) and ".." not in n and "/" not in n and "\\" not in n


def care_recipients_stored_photo_state(
    db_manager: QueryManager, family_circle_id: str, care_recipient_user_id: str
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
    db_manager: QueryManager,
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


def save_image_upload_to_uploads(
    photo: Any,
    uploads_dir: str,
    *,
    max_bytes: int,
    default_ext: str = ".jpg",
) -> Tuple[Optional[str], Optional[str], int]:
    """Write multipart image to uploads_dir with a random basename. Returns (basename, error, http_status)."""
    orig = secure_filename(photo.filename) or "photo.jpg"
    ext = Path(orig).suffix.lower()
    if ext not in _IMAGE_EXTS:
        ext = default_ext
    new_fn = f"{uuid.uuid4().hex}{ext}"

    os.makedirs(uploads_dir, exist_ok=True)
    dest = os.path.join(uploads_dir, new_fn)
    photo.save(dest)

    if os.path.getsize(dest) > max_bytes:
        try:
            os.remove(dest)
        except OSError:
            pass
        return (None, "photo too large", 413)

    return (new_fn, None, 200)


def remove_replaced_file_in_uploads_dir(
    uploads_dir: str,
    old_basename: Optional[str],
    new_basename: str,
) -> None:
    """Best-effort delete of a previous basename under uploads_dir when it is replaced."""
    if (
        not old_basename
        or old_basename == new_basename
        or not is_safe_saved_upload_basename(old_basename)
    ):
        return
    old_path = os.path.join(uploads_dir, old_basename)
    uploads_abs = os.path.abspath(uploads_dir)
    if os.path.abspath(old_path).startswith(uploads_abs + os.sep):
        try:
            os.remove(old_path)
        except OSError:
            pass


def apply_care_recipient_profile_photo(
    user_svc: Any,
    family_circle_id: str,
    care_recipient_user_id: str,
    photo: Any,
    uploads_dir: str,
    max_bytes: int = MAX_PROFILE_PHOTO_BYTES,
) -> Tuple[Optional[dict], Optional[str], int]:
    """Persist image file and sync users.photo_filename and care_recipients.photo_path."""
    dbm = user_svc.db_manager
    old_user_fn = user_svc.get_user_photo_filename(
        care_recipient_user_id, family_circle_id
    )
    exists, old_cr_basename = care_recipients_stored_photo_state(
        dbm, family_circle_id, care_recipient_user_id
    )
    if not exists:
        return (None, "care recipient not found", 404)

    new_fn, err, status = save_image_upload_to_uploads(
        photo, uploads_dir, max_bytes=max_bytes
    )
    if err:
        return (None, err, status)

    assert new_fn is not None
    dest = os.path.join(uploads_dir, new_fn)

    ur = user_svc.set_user_photo_filename(
        care_recipient_user_id, family_circle_id, new_fn
    )
    if not ur.success:
        try:
            os.remove(dest)
        except OSError:
            pass
        return (None, ur.error or "update failed", 500)

    pr = set_care_recipients_stored_photo_path(
        dbm, family_circle_id, care_recipient_user_id, new_fn
    )
    if not pr.success:
        user_svc.set_user_photo_filename(
            care_recipient_user_id, family_circle_id, old_user_fn
        )
        try:
            os.remove(dest)
        except OSError:
            pass
        return (None, pr.error or "update failed", 500)

    remove_replaced_file_in_uploads_dir(uploads_dir, old_cr_basename, new_fn)

    return (
        {
            "photo_filename": new_fn,
            "photo_path": new_fn,
            "care_recipient_user_id": care_recipient_user_id,
        },
        None,
        200,
    )


class PhotoUploadService:
    """Multipart uploads and care-recipient profile photo sync; wire via DatabaseServices.get_photo_upload_service()."""

    def __init__(self, user_service: Any):
        self.user_service = user_service

    def apply_care_recipient_profile_photo(
        self,
        family_circle_id: str,
        care_recipient_user_id: str,
        photo: Any,
        uploads_dir: str,
        max_bytes: int = MAX_PROFILE_PHOTO_BYTES,
    ) -> Tuple[Optional[dict], Optional[str], int]:
        return apply_care_recipient_profile_photo(
            self.user_service,
            family_circle_id,
            care_recipient_user_id,
            photo,
            uploads_dir,
            max_bytes=max_bytes,
        )

    def remove_replaced_file_in_uploads_dir(
        self,
        uploads_dir: str,
        old_basename: Optional[str],
        new_basename: str,
    ) -> None:
        remove_replaced_file_in_uploads_dir(uploads_dir, old_basename, new_basename)
