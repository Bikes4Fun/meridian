"""Multipart image storage under uploads/ and care-recipient profile photo DB sync."""

import os
import uuid
from pathlib import Path
from typing import Any, Optional, Tuple

from werkzeug.utils import secure_filename

from .saved_upload_basename import (
    care_recipients_stored_photo_state,
    is_safe_saved_upload_basename,
    set_care_recipients_stored_photo_path,
)
from .user import UserService

MAX_PROFILE_PHOTO_BYTES = 8 * 1024 * 1024

_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


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
    user_svc: UserService,
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
    def __init__(self, user_service: UserService):
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
