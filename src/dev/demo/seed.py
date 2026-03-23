"""
Demo seed: API-only client. Reads JSON files and POSTs to server API.
Uses the same endpoints as kiosk/webapp (calendar events, checkins, medications, etc.).
"""

import json
import logging
import os
import datetime
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEMO_FAMILY_CIRCLE_ID = "F00000"
DEMO_USER_ID = "fm_001"


def get_data_dir() -> str:
    """Get the path to the demo data directory."""
    return os.path.join(os.path.dirname(__file__), "data")


def load_json_file(filename: str) -> Dict[str, Any]:
    """Load a JSON file from the demo data directory."""
    file_path = os.path.join(get_data_dir(), filename)
    with open(file_path, "r") as f:
        return json.load(f)


def _resolve_event_time(value: str, today: datetime.date) -> str:
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


def run_seed(api_url: str, user_id: str = DEMO_USER_ID) -> bool:
    """Seed data via API. Server must be running. Uses standard endpoints (users, contacts, medications, calendar, checkins)."""
    try:
        import requests
    except ImportError:
        logger.error("requests required for demo seed")
        return False

    base = api_url.rstrip("/")
    fam_id = DEMO_FAMILY_CIRCLE_ID
    user_id = user_id or DEMO_USER_ID

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
        r = requests.post(
            f"{base}/api/users",
            json=user,
            timeout=5,
        )
        if not r.ok:
            logger.error("Create user %s failed: %s", user.get("id"), r.status_code)
            return False
    for user in users:
        uid = user.get("id")
        fc_id = user.get("family_circle_id")
        if fc_id and uid:
            r = requests.post(
                f"{base}/api/family_circles/{fc_id}/users",
                json={"user_id": uid},
                headers=_headers(user_id, fam_id),
                timeout=5,
            )
            if not r.ok:
                logger.error("Add user %s to family failed: %s", uid, r.status_code)
                return False

    contacts = load_json_file("contacts.json").get("contacts", [])
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
        for role, cid in [("medical_proxy", cr.get("proxy_contact_id")), ("poa", cr.get("poa_contact_id"))]:
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
            logger.debug("Medication time %s failed: %s", name, r.status_code)

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
            logger.warning("Medication %s failed: %s", med.get("name"), r.status_code)

    care_recipient_user_id = cr.get("user_id") if cr else None
    for a in medical.get("allergies", []):
        allergen = a.get("allergen") if isinstance(a, dict) else a
        if allergen and care_recipient_user_id:
            requests.post(
                f"{base}/api/family_circles/{fam_id}/allergies",
                json={"care_recipient_user_id": care_recipient_user_id, "allergen": allergen},
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
                    "diagnosis_date": c.get("diagnosis_date") if isinstance(c, dict) else None,
                    "notes": c.get("notes") if isinstance(c, dict) else None,
                },
                headers=_headers(user_id, fam_id),
                timeout=5,
            )

    family_data = load_json_file("family.json")
    for loc in family_data.get("named_places", []):
        r = requests.post(
            f"{base}/api/family_circles/{fam_id}/named-places",
            json=loc,
            headers=_headers(user_id, fam_id),
            timeout=5,
        )
        if not r.ok:
            logger.debug("Named place %s failed: %s", loc.get("location_id"), r.status_code)

    for checkin in family_data.get("location_checkins", []):
        uid = checkin.get("user_id")
        if not uid or checkin.get("latitude") is None or checkin.get("longitude") is None:
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
        if not r.ok:
            logger.debug("Checkin for %s failed: %s", uid, r.status_code)

    today = datetime.datetime.now().date()
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

    logger.info("Demo data loaded successfully!")
    return True


if __name__ == "__main__":
    import sys
    try:
        from shared.config import get_server_host, get_server_port
        host = "127.0.0.1" if get_server_host() == "0.0.0.0" else get_server_host()
        default_url = f"http://{host}:{get_server_port()}"
    except ImportError:
        default_url = "http://127.0.0.1:8000"
    api_url = os.environ.get("API_URL", default_url)
    logging.basicConfig(level=logging.INFO)
    ok = run_seed(api_url)
    sys.exit(0 if ok else 1)
