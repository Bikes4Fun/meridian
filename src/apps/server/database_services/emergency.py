"""
Emergency service for Meridian.
Emergency profile (first responder view), medical summary, and contacts.
Composes from canonical sources: care_recipients, medications, allergies, conditions, contacts.
"""

from dataclasses import asdict

from .safe_query_manager import QueryManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult
from .user import ContactService


class EmergencyService:
    def __init__(self, db_manager: QueryManager, contact_service: ContactService):
        self.db_manager = db_manager
        self.contact_service = contact_service

    def get_emergency_profile(self, family_circle_id: str) -> ServiceResult:
        """Compose emergency profile from canonical sources. No data stored in this service."""
        care = self.db_manager.execute_query(
            "SELECT care_recipient_user_id, name, dob, photo_path, medical_dnr, dnr_document_path, notes,"
            " medical_dni_status, medical_nutrition_status, devices_notes, brief_history, other_notes"
            " FROM care_recipients WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        care_row = care.data[0] if care.success and care.data else None

        care_recipient_user_id = (
            care_row["care_recipient_user_id"] if care_row else None
        )
        conditions_result = (
            self.db_manager.execute_query(
                "SELECT condition_name FROM conditions WHERE care_recipient_user_id = ? ORDER BY condition_name",
                (care_recipient_user_id,),
            )
            if care_recipient_user_id
            else self.db_manager.execute_query("SELECT 1 WHERE 0", ())
        )
        conditions_list = (
            [
                r["condition_name"]
                for r in conditions_result.data
                if r.get("condition_name")
            ]
            if conditions_result.success and conditions_result.data
            else []
        )
        medical_conditions = ", ".join(conditions_list) if conditions_list else None

        allergies_result = (
            self.db_manager.execute_query(
                "SELECT allergen, reaction FROM allergies WHERE care_recipient_user_id = ?",
                (care_recipient_user_id,),
            )
            if care_recipient_user_id
            else self.db_manager.execute_query("SELECT 1 WHERE 0", ())
        )
        allergies = (
            [{"allergen": a["allergen"], "reaction": a["reaction"]} for a in allergies_result.data]
            if allergies_result.success and allergies_result.data
            else []
        )

        meds_result = (
            self.db_manager.execute_query(
                """
            SELECT m.id, m.name, m.dosage, m.frequency, m.fda_rxcui
            FROM medications m
            WHERE m.care_recipient_user_id = ?
            ORDER BY m.name
            """,
                (care_recipient_user_id,),
            )
            if care_recipient_user_id
            else self.db_manager.execute_query("SELECT 1 WHERE 0", ())
        )
        med_rows = meds_result.data if meds_result.success and meds_result.data else []
        times_by_med: dict = {}
        if med_rows:
            med_ids = [m["id"] for m in med_rows]
            placeholders = ",".join("?" * len(med_ids))
            times_r = self.db_manager.execute_query(
                f"""
            SELECT mtt.medication_id, mt.name AS time_name
            FROM medication_to_time mtt
            JOIN medication_times mt ON mtt.group_id = mt.id
            WHERE mtt.medication_id IN ({placeholders})
            """,
                tuple(med_ids),
            )
            if times_r.success and times_r.data:
                for row in times_r.data:
                    mid = row["medication_id"]
                    nm = row.get("time_name")
                    if nm:
                        times_by_med.setdefault(mid, []).append(nm)
        medications = [
            {
                "id": m["id"],
                "name": m["name"],
                "dosage": m["dosage"],
                "frequency": m["frequency"],
                "fda_rxcui": m.get("fda_rxcui"),
                "medication_times": times_by_med.get(m["id"], []),
            }
            for m in med_rows
        ]

        proxy_name, proxy_phone, poa_name, poa_phone = None, None, None, None
        roles_result = self.db_manager.execute_query(
            "SELECT role, contact_id FROM ice_contact_roles WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        if roles_result.success and roles_result.data:
            contact_ids = [r["contact_id"] for r in roles_result.data]
            if contact_ids:
                placeholders = ",".join("?" * len(contact_ids))
                contacts_result = self.db_manager.execute_query(
                    f"SELECT id, display_name, phone FROM contacts WHERE id IN ({placeholders})",
                    tuple(contact_ids),
                )
                contacts_by_id = (
                    {c["id"]: c for c in (contacts_result.data or [])}
                    if contacts_result.success
                    else {}
                )
                for r in roles_result.data:
                    c = contacts_by_id.get(r["contact_id"])
                    if c:
                        if r["role"] == "medical_proxy":
                            proxy_name, proxy_phone = c.get("display_name"), c.get(
                                "phone"
                            )
                        elif r["role"] == "poa":
                            poa_name, poa_phone = c.get("display_name"), c.get("phone")

        if (
            not care_row
            and not conditions_list
            and not allergies
            and not medications
            and not proxy_name
            and not poa_name
        ):
            return ServiceResult.success_result(None)

        ec_r = self.contact_service.get_emergency_contacts(family_circle_id)
        emergency_contacts = (
            [asdict(c) for c in (ec_r.data or [])] if ec_r.success else []
        )

        data = {
            "family_circle_id": family_circle_id,
            "care_recipient_user_id": care_recipient_user_id,
            "profile": {
                "name": care_row["name"] if care_row else None,
                "dob": care_row["dob"] if care_row else None,
            },
            "medical": {
                "conditions": medical_conditions,
                "dnr": int(care_row["medical_dnr"]) if care_row and care_row["medical_dnr"] is not None else 0,
                "dni_status": care_row["medical_dni_status"] if care_row else None,
                "nutrition_status": care_row["medical_nutrition_status"] if care_row else None,
                "allergies": allergies,
                "medications": medications,
            },
            "emergency": {"proxy": {"name": proxy_name}},
            "photo_path": care_row["photo_path"] if care_row else None,
            "dnr_document_path": care_row["dnr_document_path"] if care_row else None,
            "medical_proxy_phone": proxy_phone,
            "poa_name": poa_name,
            "poa_phone": poa_phone,
            "notes": care_row["notes"] if care_row else None,
            "devices_notes": care_row["devices_notes"] if care_row else None,
            "brief_history": care_row["brief_history"] if care_row else None,
            "other_notes": care_row["other_notes"] if care_row else None,
            "last_updated": None,
            "last_updated_by": None,
            "emergency_contacts": emergency_contacts,
        }
        return ServiceResult.success_result(data)

    def e_service_get_medical_summary(self, family_circle_id: str) -> ServiceResult:
        """Formatted medical summary string for emergency display."""
        r = self.get_emergency_profile(family_circle_id)
        if not r.success or not r.data:
            return ServiceResult.success_result("Medical Information:")
        medical = r.data.get("medical") or {}
        lines = ["Medical Information:"]
        meds = medical.get("medications") or []
        if meds:
            lines.append("\nMedications:")
            for m in meds:
                name = m.get("name") or ""
                dosage = m.get("dosage") or ""
                frequency = m.get("frequency") or ""
                parts = [name]
                if dosage or frequency:
                    parts.append(f"{dosage} {frequency}".strip())
                lines.append("• " + " - ".join(parts))
        allergies = medical.get("allergies") or []
        if allergies:
            lines.append("\nAllergies:")
            for a in allergies:
                lines.append(f"• {a}")
        conditions_str = medical.get("conditions")
        if conditions_str:
            lines.append("\nMedical Conditions:")
            for c in conditions_str.split(","):
                c = c.strip()
                if c:
                    lines.append(f"• {c}")
        return ServiceResult.success_result("\n".join(lines))

    def e_service_get_emergency_contacts(self, family_circle_id: str) -> ServiceResult:
        return self.contact_service.get_emergency_contacts(family_circle_id)

    def get_all_contacts(self, family_circle_id: str) -> ServiceResult:
        return self.contact_service.get_all_contacts(family_circle_id)
