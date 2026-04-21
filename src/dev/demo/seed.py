"""
Demo seed: API-only client. Reads JSON files and POSTs to server API.
Uses the same endpoints as kiosk/webapp (calendar events, checkins, medications, etc.).
"""

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEMO_FAMILY_CIRCLE_ID = "F00000"
DEMO_USER_ID = "fm_001"

try:
    from ...shared.config import get_database_path, get_uploads_dir
except ImportError:
    from shared.config import get_database_path, get_uploads_dir


def ensure_local_seed_prerequisites(db_path: str) -> None:
    """INSERT OR IGNORE minimal rows so verify_family_membership passes before HTTP seed (local SQLite)."""
    fam = (
        (os.environ.get("FAMILY_CIRCLE_ID") or os.environ.get("PATIENT_FAMILY_CIRCLE_ID") or DEMO_FAMILY_CIRCLE_ID)
        .strip()
        or DEMO_FAMILY_CIRCLE_ID
    )
    kiosk = (os.environ.get("KIOSK_USER_ID") or "fm_care_001").strip() or "fm_care_001"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO family_circles (id) VALUES (?)", (fam,))
        for uid, name in (("fm_001", "Dean"), (kiosk, "Kiosk")):
            conn.execute(
                "INSERT OR IGNORE INTO users (id, display_name, photo_filename, family_circle_id) VALUES (?,?,?,?)",
                (uid, name, None, fam),
            )
            conn.execute(
                "INSERT OR IGNORE INTO family_memberships (user_id, family_circle_id) VALUES (?,?)",
                (uid, fam),
            )
        conn.commit()
    finally:
        conn.close()


def get_data_dir() -> str:
    """Get the path to the demo data directory."""
    return os.path.join(os.path.dirname(__file__), "data")


def load_json_file(filename: str) -> Dict[str, Any]:
    """Load a JSON file from the demo data directory."""
    file_path = os.path.join(get_data_dir(), filename)
    with open(file_path, "r") as f:
        return json.load(f)


def _demo_phone_env_key(user_id: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in str(user_id)).upper()
    return f"MERIDIAN_DEMO_PHONE_{normalized}"


def _apply_demo_user_phone_overrides(users: list[dict]) -> None:
    """Override demo user phone numbers from environment variables."""
    for user in users:
        user_id = user.get("id")
        if not user_id:
            continue
        phone = (os.environ.get(_demo_phone_env_key(user_id)) or "").strip()
        if phone:
            user["phone"] = phone


def _resolve_event_time(value: str, today: date) -> str:
    """Resolve TODAY_, TOMORROW_, PLUS_N_DAYS_ placeholders to ISO datetime strings."""
    if not value:
        return value
    if value.startswith("TODAY_"):
        return f"{today}T{value.replace('TODAY_', '')}"
    if value.startswith("TOMORROW_"):
        return f"{today + timedelta(days=1)}T{value.replace('TOMORROW_', '')}"
    for n, prefix in enumerate(
        ["PLUS_2_DAYS_", "PLUS_3_DAYS_", "PLUS_4_DAYS_", "PLUS_5_DAYS_"], 2
    ):
        if value.startswith(prefix):
            return f"{today + timedelta(days=n)}T{value.replace(prefix, '')}"
    return value


def _headers(user_id: str, family_circle_id: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-User-Id": user_id,
        "X-Family-Circle-Id": family_circle_id,
    }


def _make_photo_filename_resolver():
    uploads = get_uploads_dir()
    try:
        names = [
            n for n in os.listdir(uploads) if os.path.isfile(os.path.join(uploads, n))
        ]
    except OSError:
        names = []
    if not names:
        return lambda fn: fn

    by_exact = {n: n for n in names}
    by_lower = {n.lower(): n for n in names}
    by_stem_lower = {}
    for n in names:
        stem = os.path.splitext(n)[0].lower()
        if stem and stem not in by_stem_lower:
            by_stem_lower[stem] = n

    def _resolve(fn):
        if not fn:
            return fn
        if fn in by_exact:
            return by_exact[fn]
        low = str(fn).lower()
        if low in by_lower:
            return by_lower[low]
        stem = os.path.splitext(str(fn))[0].lower()
        if stem in by_stem_lower:
            return by_stem_lower[stem]
        return fn

    return _resolve


def run_seed(api_url: str, user_id: str = DEMO_USER_ID) -> bool:
    """Seed data via API. Server must be running. Uses standard endpoints (users, contacts, medications, calendar, checkins)."""
    try:
        ensure_local_seed_prerequisites(get_database_path())
    except Exception as e:
        logger.error("Local seed prerequisites failed: %s", e)
        return False

    try:
        import requests
    except ImportError:
        logger.error("requests required for demo seed")
        return False

    base = api_url.rstrip("/")
    fam_id = DEMO_FAMILY_CIRCLE_ID
    user_id = user_id or DEMO_USER_ID
    resolve_photo_filename = _make_photo_filename_resolver()
    family_data = load_json_file("family.json")

    r = requests.get(
        f"{base}/api/family_circles/{fam_id}/medications",
        headers=_headers(user_id, fam_id),
        timeout=5,
    )
    if r.ok:
        body = r.json() if r.content else {}
        med_data = body.get("data") if isinstance(body, dict) else {}
        if not isinstance(med_data, dict):
            med_data = {}
        if med_data.get("timed_medications") or med_data.get("prn_medications"):
            logger.debug("Demo data already present, skipping seed")
            return True

    r = requests.post(
        f"{base}/api/family_circles/{fam_id}",
        json={},
        headers=_headers(user_id, fam_id),
        timeout=5,
    )
    if not r.ok and r.status_code != 409:
        logger.error("Create family failed: %s %s", r.status_code, r.text)
        return False

    users = load_json_file("users.json")
    for user in users:
        user["photo_filename"] = resolve_photo_filename(user.get("photo_filename"))
    _apply_demo_user_phone_overrides(users)
    for user in users:
        r = requests.post(
            f"{base}/api/users",
            json=user,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if not r.ok:
            logger.error("Create user %s failed: %s", user.get("id"), r.status_code)
            return False
    for user in users:
        if user.get("family_circle_id"):
            r = requests.post(
                f"{base}/api/family_circles/{fam_id}/family-members",
                json={"id": user.get("id")},
                headers=_headers(user_id, fam_id),
                timeout=5,
            )
            if not r.ok:
                logger.error(
                    "Add user %s to family failed: %s", user.get("id"), r.status_code
                )
                return False

    seed_family_permissions = family_data.get("seed_family_permissions", [])
    for permission_set in seed_family_permissions:
        admin_user_id = (permission_set.get("user_id") or "").strip()
        if not admin_user_id:
            continue
        for permission in permission_set.get("permissions", []):
            permission = (permission or "").strip()
            if not permission:
                continue
            r = requests.post(
                f"{base}/api/family_circles/{fam_id}/permissions",
                json={
                    "user_id": admin_user_id,
                    "permission": permission,
                    "granted": True,
                },
                headers=_headers(user_id, fam_id),
                timeout=5,
            )
            if not r.ok:
                logger.error(
                    f"Grant demo admin permission {permission} to {admin_user_id} failed: {r.status_code}"
                )
                return False

    contacts = load_json_file("contacts.json").get("contacts", [])
    for contact in contacts:
        contact["photo_filename"] = resolve_photo_filename(
            contact.get("photo_filename")
        )
    for contact in contacts:
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/contacts",
            json=contact,
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.error("Add contact %s failed: %s", contact.get("id"), r.status_code)
            return False

    medical = load_json_file("medical.json")
    cr = medical.get("care_recipient", {})
    if cr:
        r = requests.put(
            f"{base}/api/family_circles/{fam_id}/care-recipient",
            json=cr,
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.error("Care recipient failed: %s", r.status_code)
            return False
        for role, cid in [
            ("medical_proxy", cr.get("proxy_contact_id")),
            ("poa", cr.get("poa_contact_id")),
        ]:
            if cid:
                requests.post(
                    f"{base}/api/family_circles/{fam_id}/contact-roles",
                    json={"role": role, "contact_id": cid},
                    headers=_headers(user_id, fam_id),
                    timeout=5,
                )

    for name, mt in (medical.get("medication_times") or {}).items():
        t = mt.get("time") if isinstance(mt, dict) else None
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/medication-times",
            json={"name": name, "time": t},
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.debug(
                f"Medication time seed request for {name!r} (time={t!r}) failed with status {r.status_code}"
            )

    for med in medical.get("medications", []):
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/medications",
            json={
                "name": med.get("name"),
                "medication_times": med.get("medication_times", []),
                "dosage": med.get("dosage"),
                "frequency": med.get("frequency"),
                "notes": med.get("notes"),
                "max_daily": med.get("max_daily"),
            },
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            name = med.get("name")
            if r.status_code in (400, 409):
                logger.debug(
                    f"Medication seed request for {name!r} was already present (status {r.status_code})"
                )
            else:
                logger.warning(
                    f"Medication seed request for {name!r} failed with status {r.status_code}"
                )

    care_recipient_user_id = cr.get("user_id") if cr else None
    for a in medical.get("allergies", []):
        allergen = a.get("allergen") if isinstance(a, dict) else a
        if allergen and care_recipient_user_id:
            requests.post(
                f"{base}/api/family_circles/{fam_id}/allergies",
                json={
                    "care_recipient_user_id": care_recipient_user_id,
                    "allergen": allergen,
                },
                headers=_headers(user_id, fam_id),
                timeout=5,
            )
    for c in medical.get("conditions", []):
        cond = c.get("condition") if isinstance(c, dict) else c
        if cond and care_recipient_user_id:
            requests.post(
                f"{base}/api/family_circles/{fam_id}/conditions",
                json={
                    "care_recipient_user_id": care_recipient_user_id,
                    "condition": cond,
                    "diagnosis_date": (
                        c.get("diagnosis_date") if isinstance(c, dict) else None
                    ),
                    "notes": c.get("notes") if isinstance(c, dict) else None,
                },
                headers=_headers(user_id, fam_id),
                timeout=5,
            )

    for loc in family_data.get("named_places", []):
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/named-places",
            json=loc,
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.debug(
                "Named place %s failed: %s", loc.get("location_id"), r.status_code
            )

    checkin_ok, checkin_fail = 0, 0
    for checkin in family_data.get("location_checkins", []):
        uid = checkin.get("user_id")
        if (
            not uid
            or checkin.get("latitude") is None
            or checkin.get("longitude") is None
        ):
            continue
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/create_checkin",
            json={
                "user_id": uid,
                "latitude": checkin["latitude"],
                "longitude": checkin["longitude"],
                "notes": checkin.get("notes"),
            },
            headers=_headers(uid, fam_id),
            timeout=5,
        )
        if r.ok:
            checkin_ok += 1
        else:
            checkin_fail += 1
            logger.debug("Checkin for %s failed: %s", uid, r.status_code)
    if checkin_ok or checkin_fail:
        logger.info(
            "Check-ins: %d created%s",
            checkin_ok,
            f", {checkin_fail} failed" if checkin_fail else "",
        )

    today = datetime.now().date()
    events = load_json_file("calendar.json").get("calendar_events", [])
    for event_data in events:
        evt_id = event_data.get("id")
        evt_url = f"{base}/api/family_circles/{fam_id}/calendar/events/{evt_id}"
        requests.delete(evt_url, headers=_headers(user_id, fam_id), timeout=5)
    for event_data in events:
        start_time = _resolve_event_time(event_data.get("start_time"), today)
        end_time = _resolve_event_time(event_data.get("end_time"), today)
        payload = {
            "id": event_data.get("id"),
            "title": event_data.get("title"),
            "start_time": start_time,
            "end_time": end_time,
            "description": event_data.get("description"),
            "location": event_data.get("location"),
            "driver_name": event_data.get("driver_name"),
            "driver_contact_id": event_data.get("driver_contact_id"),
            "pickup_time": event_data.get("pickup_time"),
            "leave_time": event_data.get("leave_time"),
        }
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/calendar/events",
            json=payload,
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.warning("Calendar event failed: %s", r.status_code)

    logger.debug("Demo data loaded successfully!")
    return True


if __name__ == "__main__":
    import sys

    try:
        from shared.config import get_server_host, get_server_port

        host = get_server_host()
        default_url = f"http://{host}:{get_server_port()}"
    except ImportError:
        default_url = "http://127.0.0.1:8000"
    api_url = os.environ.get("API_URL", default_url)
    logging.basicConfig(level=logging.INFO)
    ok = run_seed(api_url)
    sys.exit(0 if ok else 1)
