"""
ICE Profile service for In-Case-of-Emergency data.
Composes from canonical sources: care_recipients, medications, allergies, conditions, contacts.
ICE does not store data; it gathers it for the emergency display.
"""

from ..database import DatabaseManager, DatabaseServiceMixin

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class ICEProfileService(DatabaseServiceMixin):
    def __init__(self, db_manager: DatabaseManager):
        DatabaseServiceMixin.__init__(self, db_manager)

    def get_ice_profile(self, family_circle_id: str) -> ServiceResult:
        """Compose ICE profile from canonical sources. No data stored in ICE."""
        care = self.safe_query(
            "SELECT care_recipient_user_id, name, dob, photo_path, medical_dnr, dnr_document_path, notes FROM care_recipients WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        care_row = care.data[0] if care.success and care.data else None

        care_recipient_user_id = care_row["care_recipient_user_id"] if care_row else None
        conditions_result = self.safe_query(
            "SELECT condition_name FROM conditions WHERE care_recipient_user_id = ? ORDER BY condition_name",
            (care_recipient_user_id,),
        ) if care_recipient_user_id else self.safe_query("SELECT 1 WHERE 0", ())
        conditions_list = (
            [r["condition_name"] for r in conditions_result.data if r.get("condition_name")]
            if conditions_result.success and conditions_result.data
            else []
        )
        medical_conditions = ", ".join(conditions_list) if conditions_list else None

        allergies_result = self.safe_query(
            "SELECT allergen FROM allergies WHERE care_recipient_user_id = ?",
            (care_recipient_user_id,),
        ) if care_recipient_user_id else self.safe_query("SELECT 1 WHERE 0", ())
        allergies = (
            [a["allergen"] for a in allergies_result.data]
            if allergies_result.success and allergies_result.data
            else []
        )

        meds_result = self.safe_query(
            """
            SELECT m.name, m.dosage, m.frequency
            FROM medications m
            WHERE m.care_recipient_user_id = ?
            ORDER BY m.name
            """,
            (care_recipient_user_id,),
        ) if care_recipient_user_id else self.safe_query("SELECT 1 WHERE 0", ())
        medications = (
            [
                {"name": m["name"], "dosage": m["dosage"], "frequency": m["frequency"]}
                for m in meds_result.data
            ]
            if meds_result.success and meds_result.data
            else []
        )

        proxy_name, proxy_phone, poa_name, poa_phone = None, None, None, None
        roles_result = self.safe_query(
            "SELECT role, contact_id FROM ice_contact_roles WHERE family_circle_id = ?",
            (family_circle_id,),
        )
        if roles_result.success and roles_result.data:
            contact_ids = [r["contact_id"] for r in roles_result.data]
            if contact_ids:
                placeholders = ",".join("?" * len(contact_ids))
                contacts_result = self.safe_query(
                    f"SELECT id, display_name, phone FROM contacts WHERE id IN ({placeholders})",
                    tuple(contact_ids),
                )
                contacts_by_id = {c["id"]: c for c in (contacts_result.data or [])} if contacts_result.success else {}
                for r in roles_result.data:
                    c = contacts_by_id.get(r["contact_id"])
                    if c:
                        if r["role"] == "medical_proxy":
                            proxy_name, proxy_phone = c.get("display_name"), c.get("phone")
                        elif r["role"] == "poa":
                            poa_name, poa_phone = c.get("display_name"), c.get("phone")

        if not care_row and not conditions_list and not allergies and not medications and not proxy_name and not poa_name:
            return ServiceResult.success_result(None)

        data = {
            "family_circle_id": family_circle_id,
            "care_recipient_user_id": care_recipient_user_id,
            "profile": {"name": care_row["name"] if care_row else None, "dob": care_row["dob"] if care_row else None},
            "medical": {
                "conditions": medical_conditions,
                "dnr": bool(care_row["medical_dnr"]) if care_row else False,
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
            "last_updated": None,
            "last_updated_by": None,
        }
        return ServiceResult.success_result(data)

