"""
Medication service for managing user-defined medication schedules.
WHERE FUNCTIONALITY MOVED TO (client): client/remote.RemoteMedicationService calls GET /api/medications.
REMOVAL: Required on server. Can be omitted from client deployment when SERVER_URL is set.
"""

from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


@dataclass
class TimedMedication:
    name: str
    time: str
    status: str = "not_done"
    notes: Optional[str] = None
    group_time: Optional[str] = None
    id: Optional[int] = None


@dataclass
class PRNMedication:
    name: str
    last_taken: Optional[str] = None
    status: str = "available"
    max_daily: Optional[int] = None
    notes: Optional[str] = None
    id: Optional[int] = None


class MedicationService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.timed_medications: List[TimedMedication] = []
        self.prn_medications: List[PRNMedication] = []

    def _get_care_recipient_user_id(self, family_circle_id: str) -> Optional[str]:
        r = self.db_manager.execute_query(
            "SELECT care_recipient_user_id FROM care_recipients WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        return r.data[0]["care_recipient_user_id"] if r.success and r.data else None

    def _load_medication_data(self, family_circle_id: str) -> None:
        self.timed_medications = []
        self.prn_medications = []
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return
        query = """
            SELECT m.id, m.name, m.dosage, m.taken_today, m.last_taken, mt.name as time_name, mt.time as group_time
            FROM medications m
            LEFT JOIN medication_to_time mtt ON m.id = mtt.medication_id
            LEFT JOIN medication_times mt ON mtt.group_id = mt.id
            WHERE m.care_recipient_user_id = ?
            ORDER BY m.name, mt.time
        """
        result = self.db_manager.execute_query(query, (care_recipient_user_id,))
        if not result.success:
            self.logger.error("Failed to load medication data: %s", result.error)
            return
        medication_groups = {}
        for row in result.data:
            med_name = row["name"]
            dosage = row["dosage"] or ""
            time_name = row["time_name"]
            group_time = row["group_time"]
            taken_today = row["taken_today"]
            last_taken = row.get("last_taken")
            med_id = row["id"]
            if med_name not in medication_groups:
                medication_groups[med_name] = {
                    "id": med_id,
                    "dosage": dosage,
                    "taken_today": taken_today,
                    "last_taken": last_taken,
                    "groups": [],
                }
            if time_name:
                medication_groups[med_name]["groups"].append(
                    {"name": time_name, "time": group_time}
                )
        for med_name, med_data in medication_groups.items():
            if med_data["groups"]:
                is_prn = any(
                    g["name"].lower() in ["prn", "as needed"]
                    for g in med_data["groups"]
                )
                med_id = med_data.get("id")
                if is_prn:
                    taken_slots = [
                        s.strip()
                        for s in (med_data.get("taken_today") or "").split(",")
                        if s.strip()
                    ]
                    prn_taken = "prn" in taken_slots or "as needed" in taken_slots
                    self.prn_medications.append(
                        PRNMedication(
                            name=f"{med_name} {med_data['dosage']}".strip(),
                            status="taken" if prn_taken else "available",
                            last_taken=med_data.get("last_taken"),
                            id=med_id,
                        )
                    )
                else:
                    taken_slots = [
                        s.strip()
                        for s in (med_data["taken_today"] or "").split(",")
                        if s.strip()
                    ]
                    for group in med_data["groups"]:
                        slot_done = group["name"] in taken_slots
                        self.timed_medications.append(
                            TimedMedication(
                                name=f"{med_name} {med_data['dosage']}".strip(),
                                time=group["name"],
                                status="done" if slot_done else "not_done",
                                group_time=group["time"],
                                id=med_id,
                            )
                        )
            else:
                self.logger.warning("Medication '%s' has no times assigned", med_name)

    def add_medication(
        self,
        family_circle_id: str,
        name: str,
        medication_times: List[str],
        dosage: Optional[str] = None,
        frequency: Optional[str] = None,
        notes: Optional[str] = None,
        max_daily: Optional[int] = None,
    ) -> ServiceResult:
        """Insert medication into DB and link to medication_times. Returns med id or error."""
        care_recipient_user_id = self._get_care_recipient_user_id(family_circle_id)
        if not care_recipient_user_id:
            return ServiceResult.error_result("No care recipient for family circle")
        if not name or not medication_times:
            return ServiceResult.error_result("name and medication_times required")
        result = self.db_manager.execute_insert(
            """INSERT INTO medications
               (care_recipient_user_id, name, dosage, frequency, notes, max_daily, last_taken, taken_today)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (care_recipient_user_id, name, dosage, frequency, notes, max_daily),
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
            "SELECT name, dosage FROM medications WHERE id = ? AND care_recipient_user_id = ?",
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
    ) -> ServiceResult:
        """Update medication name, dosage, and times."""
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
        self.db_manager.execute_update(
            "UPDATE medications SET name = ?, dosage = ? WHERE id = ?",
            (name, dosage, medication_id),
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
            max_daily=kwargs.get("max_daily"),
            notes=kwargs.get("notes"),
        )
        for key, value in kwargs.items():
            if key not in ("max_daily", "notes", "last_taken", "status"):
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
            "SELECT taken_today, last_taken FROM medications WHERE id = ? AND care_recipient_user_id IN (SELECT care_recipient_user_id FROM care_recipients WHERE family_circle_id = ?)",
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
        if taken:
            if slot_key not in slots:
                slots.append(slot_key)
        else:
            slots = [
                s for s in slots if s.lower() != slot_key and s.lower() != "as needed"
            ]
        new_taken_today = ",".join(slots) if slots else None
        now_str = datetime.now().strftime("%I:%M %p")
        if slot_key == "prn" and taken:
            up = self.db_manager.execute_update(
                "UPDATE medications SET taken_today = ?, last_taken = ? WHERE id = ?",
                (new_taken_today, now_str, medication_id),
            )
        else:
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
                }
                for m in self.timed_medications
            ],
            "prn_medications": [
                {
                    "id": m.id,
                    "name": m.name,
                    "last_taken": m.last_taken,
                    "status": m.status,
                }
                for m in self.prn_medications
            ],
        }
        return ServiceResult.success_result(data)

    def get_overdue_medications(self) -> ServiceResult:
        return ServiceResult.success_result([])

    def get_upcoming_medications(self) -> List[TimedMedication]:
        return [m for m in self.timed_medications if m.status == "not_done"]
