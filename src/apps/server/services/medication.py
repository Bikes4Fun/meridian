"""
Medication service for managing user-defined medication schedules.
WHERE FUNCTIONALITY MOVED TO (client): client/remote.RemoteMedicationService calls GET /api/medications.
REMOVAL: Required on server. Can be omitted from client deployment when SERVER_URL is set.
"""

from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from ..database import DatabaseManager, DatabaseServiceMixin

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


@dataclass
class PRNMedication:
    name: str
    last_taken: Optional[str] = None
    status: str = "available"
    max_daily: Optional[int] = None
    notes: Optional[str] = None


class MedicationService(DatabaseServiceMixin):
    def __init__(self, db_manager: DatabaseManager):
        DatabaseServiceMixin.__init__(self, db_manager)
        self.timed_medications: List[TimedMedication] = []
        self.prn_medications: List[PRNMedication] = []

    def _get_care_recipient_user_id(self, family_circle_id: str) -> Optional[str]:
        r = self.safe_query(
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
            SELECT m.name, m.dosage, m.taken_today, mt.name as time_name, mt.time as group_time
            FROM medications m
            LEFT JOIN medication_to_time mtt ON m.id = mtt.medication_id
            LEFT JOIN medication_times mt ON mtt.group_id = mt.id
            WHERE m.care_recipient_user_id = ?
            ORDER BY m.name, mt.time
        """
        result = self.safe_query(query, (care_recipient_user_id,))
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
            if med_name not in medication_groups:
                medication_groups[med_name] = {
                    "dosage": dosage,
                    "taken_today": taken_today,
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
                if is_prn:
                    self.prn_medications.append(
                        PRNMedication(
                            name=f"{med_name} {med_data['dosage']}".strip(),
                            status="available",
                            last_taken=None,
                        )
                    )
                else:
                    for group in med_data["groups"]:
                        self.timed_medications.append(
                            TimedMedication(
                                name=f"{med_name} {med_data['dosage']}".strip(),
                                time=group["name"],
                                status=(
                                    "done" if med_data["taken_today"] else "not_done"
                                ),
                                group_time=group["time"],
                            )
                        )
            else:
                self.logger.warning("Medication '%s' has no times assigned", med_name)

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
                    "name": m.name,
                    "time": m.time,
                    "status": m.status,
                    "notes": m.notes,
                    "group_time": group_names.get(m.time),
                }
                for m in self.timed_medications
            ],
            "prn_medications": [
                {
                    "name": m.name,
                    "last_taken": m.last_taken,
                    "status": m.status,
                    "max_daily": m.max_daily,
                    "notes": m.notes,
                }
                for m in self.prn_medications
            ],
        }
        return ServiceResult.success_result(data)

    def get_overdue_medications(self) -> ServiceResult:
        return ServiceResult.success_result([])

    def get_upcoming_medications(self) -> List[TimedMedication]:
        return [m for m in self.timed_medications if m.status == "not_done"]
