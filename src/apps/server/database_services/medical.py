"""
Medication service for managing user-defined medication schedules.
WHERE FUNCTIONALITY MOVED TO (client): client/remote.RemoteMedicationService calls GET /api/medications.
REMOVAL: Required on server. Can be omitted from client deployment when SERVER_URL is set.
"""

import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .safe_query_manager import QueryManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


def _is_prn_slot_token(s: str) -> bool:
    sl = s.strip().lower()
    if sl in ("prn", "as needed"):
        return True
    if sl.startswith("prn+") or sl.startswith("prn:"):
        return True
    return False


def _count_prn_doses(slots: List[str]) -> int:
    return sum(1 for x in slots if _is_prn_slot_token(x))


def _remove_last_prn_dose(slots: List[str]) -> List[str]:
    last_i = None
    for i, s in enumerate(slots):
        if _is_prn_slot_token(s):
            last_i = i
    if last_i is None:
        return slots
    return [s for j, s in enumerate(slots) if j != last_i]


@dataclass
class TimedMedication:
    name: str
    time: str
    status: str = "not_done"
    notes: Optional[str] = None
    group_time: Optional[str] = None
    id: Optional[int] = None
    fda_rxcui: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None


@dataclass
class PRNMedication:
    name: str
    last_taken: Optional[str] = None
    status: str = "available"
    doses_today: int = 0
    max_daily: Optional[int] = None
    notes: Optional[str] = None
    id: Optional[int] = None
    fda_rxcui: Optional[str] = None
    frequency: Optional[str] = None


class MedicationService:
    def __init__(self, db_manager: QueryManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.timed_medications: List[TimedMedication] = []
        self.prn_medications: List[PRNMedication] = []

    def add_medication_time(
        self, family_circle_id: str, name: str, time_value: Optional[str] = None
    ) -> ServiceResult:
        """Create medication time slot for family."""
        return self.db_manager.execute_update(
            "INSERT OR IGNORE INTO medication_times (family_circle_id, name, time) VALUES (?, ?, ?)",
            (family_circle_id, name, time_value),
        )

    def _get_care_recipient_user_id(self, family_circle_id: str) -> Optional[str]:
        r = self.db_manager.execute_query(
            "SELECT care_recipient_user_id FROM care_recipients WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        return r.data[0]["care_recipient_user_id"] if r.success and r.data else None

    def _medication_name_conflicts(
        self,
        care_recipient_user_id: str,
        name: str,
        exclude_medication_id: Optional[int] = None,
    ) -> bool:
        """True if another medication for this care recipient already uses the same name (trimmed, case-insensitive)."""
        nm = (name or "").strip()
        if not nm:
            return False
        q = (
            "SELECT 1 FROM medications WHERE care_recipient_user_id = ? "
            "AND TRIM(LOWER(name)) = TRIM(LOWER(?))"
        )
        params: Tuple[Any, ...] = (care_recipient_user_id, nm)
        if exclude_medication_id is not None:
            q += " AND id != ?"
            params = (care_recipient_user_id, nm, exclude_medication_id)
        r = self.db_manager.execute_query(q, params)
        return bool(r.success and r.data)

    def _load_medication_data(self, family_circle_id: str) -> None:
        self.timed_medications = []
        self.prn_medications = []
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return
        query = """
            SELECT m.id, m.name, m.dosage, m.frequency, m.fda_rxcui, m.taken_today, m.last_taken,
                   m.max_daily,
                   mt.name AS time_name, mt.time AS group_time, mtt.group_id AS slot_group_id
            FROM medications m
            LEFT JOIN medication_to_time mtt ON m.id = mtt.medication_id
            LEFT JOIN medication_times mt ON mtt.group_id = mt.id
            WHERE m.care_recipient_user_id = ?
            ORDER BY m.id, mt.time
        """
        result = self.db_manager.execute_query(query, (care_recipient_user_id,))
        if not result.success:
            self.logger.error("Failed to load medication data: %s", result.error)
            return
        medication_groups = {}
        slot_links_seen = set()
        for row in result.data:
            med_id = row["id"]
            med_name = row["name"]
            dosage = row["dosage"] or ""
            frequency = (row.get("frequency") or "").strip()
            time_name = row["time_name"]
            group_time = row["group_time"]
            taken_today = row["taken_today"]
            last_taken = row.get("last_taken")
            if med_id not in medication_groups:
                medication_groups[med_id] = {
                    "name": med_name,
                    "dosage": dosage,
                    "frequency": frequency,
                    "fda_rxcui": (row.get("fda_rxcui") or "").strip() or None,
                    "taken_today": taken_today,
                    "last_taken": last_taken,
                    "max_daily": row.get("max_daily"),
                    "groups": [],
                }
            if time_name:
                sgid = row.get("slot_group_id")
                if sgid is not None:
                    link_key = (med_id, int(sgid))
                    if link_key in slot_links_seen:
                        continue
                    slot_links_seen.add(link_key)
                medication_groups[med_id]["groups"].append(
                    {"name": time_name, "time": group_time}
                )
        for med_id, med_data in medication_groups.items():
            med_name = med_data["name"]
            if med_data["groups"]:
                is_prn = any(
                    g["name"].lower() in ["prn", "as needed"]
                    for g in med_data["groups"]
                )
                if is_prn:
                    taken_slots = [
                        s.strip()
                        for s in (med_data.get("taken_today") or "").split(",")
                        if s.strip()
                    ]
                    doses = _count_prn_doses(taken_slots)
                    prn_taken = doses > 0
                    freq = (med_data.get("frequency") or "").strip() or None
                    md_raw = med_data.get("max_daily")
                    max_d: Optional[int]
                    if md_raw is not None and str(md_raw).strip() != "":
                        try:
                            max_d = int(md_raw)
                            if max_d <= 0:
                                max_d = None
                        except (TypeError, ValueError):
                            max_d = None
                    else:
                        max_d = None
                    self.prn_medications.append(
                        PRNMedication(
                            name=f"{med_name} {med_data['dosage']}".strip(),
                            status="taken" if prn_taken else "available",
                            last_taken=med_data.get("last_taken"),
                            id=med_id,
                            fda_rxcui=med_data.get("fda_rxcui"),
                            frequency=freq,
                            doses_today=doses,
                            max_daily=max_d,
                        )
                    )
                else:
                    taken_slots = [
                        s.strip()
                        for s in (med_data["taken_today"] or "").split(",")
                        if s.strip()
                    ]
                    taken_lower = {s.lower() for s in taken_slots}
                    dose_disp = (med_data.get("dosage") or "").strip() or None
                    freq_disp = (med_data.get("frequency") or "").strip() or None
                    for group in med_data["groups"]:
                        tnm = (group["name"] or "").strip().lower()
                        slot_done = tnm in taken_lower
                        self.timed_medications.append(
                            TimedMedication(
                                name=f"{med_name} {med_data['dosage']}".strip(),
                                time=group["name"],
                                status="done" if slot_done else "not_done",
                                group_time=group["time"],
                                id=med_id,
                                fda_rxcui=med_data.get("fda_rxcui"),
                                dosage=dose_disp,
                                frequency=freq_disp,
                            )
                        )
            else:
                self.logger.warning(
                    "Medication id=%s (%s) has no times assigned", med_id, med_name
                )

    def add_medication(
        self,
        family_circle_id: str,
        name: str,
        medication_times: List[str],
        dosage: Optional[str] = None,
        frequency: Optional[str] = None,
        notes: Optional[str] = None,
        max_daily: Optional[int] = None,
        fda_rxcui: Optional[str] = None,
    ) -> ServiceResult:
        """Insert medication into DB and link to medication_times. Returns med id or error."""
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return ServiceResult.error_result("No care recipient for family circle")
        if not name or not medication_times:
            return ServiceResult.error_result("name and medication_times required")
        if self._medication_name_conflicts(care_recipient_user_id, name):
            return ServiceResult.error_result("A medication with this name already exists")
        rx = (fda_rxcui or "").strip() or None
        result = self.db_manager.execute_insert(
            """INSERT INTO medications
               (care_recipient_user_id, name, dosage, frequency, fda_rxcui, notes, max_daily, last_taken, taken_today)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (care_recipient_user_id, name, dosage, frequency, rx, notes, max_daily),
        )
        if not result.success:
            return ServiceResult.error_result(result.error or "Insert failed")
        medication_id = result.data
        for time_name in medication_times:
            r = self.db_manager.execute_query(
                "SELECT id FROM medication_times WHERE family_circle_id = ? AND name = ?",
                (family_circle_id, time_name),
            )
            if not r.success or not r.data:
                return ServiceResult.error_result(
                    f"Medication time '{time_name}' not found for family"
                )
            group_id = r.data[0]["id"]
            link_result = self.db_manager.execute_update(
                "INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (?, ?)",
                (medication_id, group_id),
            )
            if not link_result.success:
                return ServiceResult.error_result(link_result.error or "Link failed")
        return ServiceResult.success_result({"id": medication_id})

    def get_medication_for_edit(
        self, family_circle_id: str, medication_id: int
    ) -> ServiceResult:
        """Return one medication's name, dosage, medication_times for edit form."""
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return ServiceResult.error_result("No care recipient for family circle")
        r = self.db_manager.execute_query(
            "SELECT name, dosage, frequency, fda_rxcui FROM medications WHERE id = ? AND care_recipient_user_id = ?",
            (medication_id, care_recipient_user_id),
        )
        if not r.success or not r.data:
            return ServiceResult.error_result("Medication not found")
        row = r.data[0]
        times_r = self.db_manager.execute_query(
            """SELECT mt.name FROM medication_to_time mtt
               JOIN medication_times mt ON mtt.group_id = mt.id
               WHERE mtt.medication_id = ? AND mt.family_circle_id = ?""",
            (medication_id, family_circle_id),
        )
        time_names = (
            [t["name"] for t in (times_r.data or [])] if times_r.success else []
        )
        return ServiceResult.success_result(
            {
                "id": medication_id,
                "name": row["name"],
                "dosage": row["dosage"] or "",
                "frequency": row["frequency"] or "",
                "fda_rxcui": row["fda_rxcui"] or "",
                "medication_times": time_names,
            }
        )

    def update_medication(
        self,
        family_circle_id: str,
        medication_id: int,
        name: str,
        medication_times: List[str],
        dosage: Optional[str] = None,
        frequency: Optional[str] = None,
        fda_rxcui: Optional[str] = None,
    ) -> ServiceResult:
        """Update medication name, dosage, frequency, fda_rxcui, and times."""
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return ServiceResult.error_result("No care recipient for family circle")
        if not name or not medication_times:
            return ServiceResult.error_result("name and medication_times required")
        r = self.db_manager.execute_query(
            "SELECT id FROM medications WHERE id = ? AND care_recipient_user_id = ?",
            (medication_id, care_recipient_user_id),
        )
        if not r.success or not r.data:
            return ServiceResult.error_result("Medication not found")
        if self._medication_name_conflicts(
            care_recipient_user_id, name, exclude_medication_id=medication_id
        ):
            return ServiceResult.error_result("A medication with this name already exists")
        rx = (fda_rxcui or "").strip() or None
        self.db_manager.execute_update(
            "UPDATE medications SET name = ?, dosage = ?, frequency = ?, fda_rxcui = ? WHERE id = ?",
            (name, dosage or "", frequency or "", rx, medication_id),
        )
        self.db_manager.execute_update(
            "DELETE FROM medication_to_time WHERE medication_id = ?", (medication_id,)
        )
        for time_name in medication_times:
            tr = self.db_manager.execute_query(
                "SELECT id FROM medication_times WHERE family_circle_id = ? AND name = ?",
                (family_circle_id, time_name),
            )
            if not tr.success or not tr.data:
                return ServiceResult.error_result(
                    f"Medication time '{time_name}' not found"
                )
            self.db_manager.execute_update(
                "INSERT OR IGNORE INTO medication_to_time (medication_id, group_id) VALUES (?, ?)",
                (medication_id, tr.data[0]["id"]),
            )
        return ServiceResult.success_result({"id": medication_id})

    def delete_medication(
        self, family_circle_id: str, medication_id: int
    ) -> ServiceResult:
        """Delete medication and its time links."""
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return ServiceResult.error_result("No care recipient for family circle")
        r = self.db_manager.execute_query(
            "SELECT id FROM medications WHERE id = ? AND care_recipient_user_id = ?",
            (medication_id, care_recipient_user_id),
        )
        if not r.success or not r.data:
            return ServiceResult.error_result("Medication not found")
        self.db_manager.execute_update(
            "DELETE FROM medication_to_time WHERE medication_id = ?", (medication_id,)
        )
        self.db_manager.execute_update(
            "DELETE FROM medications WHERE id = ?", (medication_id,)
        )
        return ServiceResult.success_result(True)

    def add_timed_medication(self, name: str, time: str, **kwargs) -> TimedMedication:
        medication = TimedMedication(
            name=name,
            time=time,
            status=kwargs.get("status", "not_done"),
            notes=kwargs.get("notes"),
        )
        for key, value in kwargs.items():
            if key not in ("notes", "status"):
                setattr(medication, key, value)
        self.timed_medications.append(medication)
        return medication

    def add_prn_medication(self, name: str, **kwargs) -> PRNMedication:
        medication = PRNMedication(
            name=name,
            last_taken=kwargs.get("last_taken"),
            status=kwargs.get("status", "available"),
            doses_today=kwargs.get("doses_today", 0),
            max_daily=kwargs.get("max_daily"),
            notes=kwargs.get("notes"),
        )
        for key, value in kwargs.items():
            if key not in (
                "max_daily",
                "notes",
                "last_taken",
                "status",
                "doses_today",
            ):
                setattr(medication, key, value)
        self.prn_medications.append(medication)
        return medication

    def mark_medication_done(
        self, medication_name: str, medication_type: str = "timed"
    ) -> ServiceResult:
        if medication_type == "timed":
            for med in self.timed_medications:
                if med.name == medication_name:
                    med.status = "done"
                    return ServiceResult.success_result(True)
        elif medication_type == "prn":
            for med in self.prn_medications:
                if med.name == medication_name:
                    med.last_taken = datetime.now().strftime("%I:%M %p")
                    med.status = "taken"
                    return ServiceResult.success_result(True)
        return ServiceResult.error_result(f"Medication '{medication_name}' not found")

    def mark_medication_taken(
        self, family_circle_id: str, medication_id: int, time_slot: str, taken: bool
    ) -> ServiceResult:
        """Mark a medication time slot as taken or not. time_slot e.g. Morning, Evening, prn. taken_today stores comma-separated list. For prn, also updates last_taken."""
        self._load_medication_data(family_circle_id)
        r = self.db_manager.execute_query(
            "SELECT taken_today, last_taken, max_daily FROM medications WHERE id = ? AND care_recipient_user_id IN (SELECT care_recipient_user_id FROM care_recipients WHERE family_circle_id = ?)",
            (medication_id, family_circle_id),
        )
        if not r.success or not r.data:
            return ServiceResult.error_result("Medication not found")
        current = (r.data[0].get("taken_today") or "").strip()
        slots = [s.strip() for s in current.split(",") if s.strip()]
        slot_normalized = time_slot.strip().lower()
        if slot_normalized in ("prn", "as needed"):
            slot_key = "prn"
        else:
            slot_key = time_slot.strip()
        max_raw = r.data[0].get("max_daily")
        max_daily: Optional[int]
        if max_raw is not None and str(max_raw).strip() != "":
            try:
                max_daily = int(max_raw)
                if max_daily <= 0:
                    max_daily = None
            except (TypeError, ValueError):
                max_daily = None
        else:
            max_daily = None
        now_str = datetime.now().strftime("%I:%M %p")
        if slot_key == "prn":
            if taken:
                doses = _count_prn_doses(slots)
                if max_daily is not None and doses >= max_daily:
                    return ServiceResult.error_result(
                        "Daily limit reached for this medication"
                    )
                slots = list(slots)
                slots.append(f"prn+{int(datetime.now().timestamp() * 1000)}")
            else:
                slots = _remove_last_prn_dose(list(slots))
            new_taken_today = ",".join(slots) if slots else None
            if taken:
                new_last = now_str
            else:
                new_last = (
                    None
                    if _count_prn_doses(slots) == 0
                    else r.data[0].get("last_taken")
                )
            up = self.db_manager.execute_update(
                "UPDATE medications SET taken_today = ?, last_taken = ? WHERE id = ?",
                (new_taken_today, new_last, medication_id),
            )
            if not up.success:
                return ServiceResult.error_result(up.error or "Update failed")
            return ServiceResult.success_result(True)
        if taken:
            if not any(s.lower() == slot_key.lower() for s in slots):
                slots.append(slot_key)
        else:
            slots = [s for s in slots if s.lower() != slot_key.lower()]
        new_taken_today = ",".join(slots) if slots else None
        up = self.db_manager.execute_update(
            "UPDATE medications SET taken_today = ? WHERE id = ?",
            (new_taken_today, medication_id),
        )
        if not up.success:
            return ServiceResult.error_result(up.error or "Update failed")
        return ServiceResult.success_result(True)

    def get_medication_data(self, family_circle_id: str) -> ServiceResult:
        self._load_medication_data(family_circle_id)
        group_names = {}
        result = self.db_manager.execute_query(
            "SELECT name, time FROM medication_times WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        if result.success:
            for row in result.data:
                group_names[row["name"]] = row["time"]
        data = {
            "medication_time_groups": group_names,
            "timed_medications": [
                {
                    "id": m.id,
                    "name": m.name,
                    "time": m.time,
                    "status": m.status,
                    "group_time": group_names.get(m.time),
                    "fda_rxcui": m.fda_rxcui,
                    "dosage": m.dosage,
                    "frequency": m.frequency,
                }
                for m in self.timed_medications
            ],
            "prn_medications": [
                {
                    "id": m.id,
                    "name": m.name,
                    "last_taken": m.last_taken,
                    "status": m.status,
                    "fda_rxcui": m.fda_rxcui,
                    "frequency": m.frequency,
                    "doses_today": m.doses_today,
                    "max_daily": m.max_daily,
                }
                for m in self.prn_medications
            ],
        }
        return ServiceResult.success_result(data)

    def get_overdue_medications(self) -> ServiceResult:
        return ServiceResult.success_result([])

    def get_upcoming_medications(self) -> List[TimedMedication]:
        return [m for m in self.timed_medications if m.status == "not_done"]
