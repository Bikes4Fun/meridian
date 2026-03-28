"""
Care recipient and contact role updates. Legal/medical designations (proxy, POA) are just contact roles.
"""

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class CareRecipientService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def update_care_recipient(self, family_circle_id: str, data: dict) -> ServiceResult:
        """Update care_recipients and contact roles (proxy, POA). Data is care recipient, not session user."""
        care_recipient_user_id = data.get("user_id") or data.get(
            "care_recipient_user_id"
        )
        profile = data.get("profile") or {}
        medical = data.get("medical") or {}
        emergency = data.get("emergency") or {}
        proxy = emergency.get("proxy") or {}
        profile_name = profile.get("name")
        profile_dob = profile.get("dob")
        medical_dnr = 1 if medical.get("dnr") else 0
        photo_path = data.get("photo_path")
        dnr_document_path = data.get("dnr_document_path")
        medical_proxy_phone = data.get("medical_proxy_phone")
        poa_name = data.get("poa_name")
        poa_phone = data.get("poa_phone")
        notes = data.get("notes")

        if not care_recipient_user_id:
            return ServiceResult.error_result("care_recipient_user_id required")

        result = self.db_manager.execute_update(
            """
            INSERT OR REPLACE INTO care_recipients (family_circle_id, care_recipient_user_id, name, dob, photo_path, medical_dnr, dnr_document_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_circle_id,
                care_recipient_user_id,
                profile_name,
                profile_dob,
                photo_path,
                medical_dnr,
                dnr_document_path,
                notes,
            ),
        )
        if not result.success:
            return result

        def _ensure_contact(cid: str, name: str, phone: str) -> bool:
            r = self.db_manager.execute_query(
                "SELECT id FROM contacts WHERE id = ? AND family_circle_id = ?",
                (cid, family_circle_id),
            )
            if r.success and r.data:
                return self.db_manager.execute_update(
                    "UPDATE contacts SET display_name=?, phone=? WHERE id=? AND family_circle_id=?",
                    (name, phone or "", cid, family_circle_id),
                ).success
            return self.db_manager.execute_update(
                "INSERT INTO contacts (id, family_circle_id, display_name, phone) VALUES (?, ?, ?, ?)",
                (cid, family_circle_id, name, phone or ""),
            ).success

        def _set_role(role: str, contact_id: str) -> bool:
            return self.db_manager.execute_update(
                "INSERT OR REPLACE INTO ice_contact_roles (family_circle_id, role, contact_id) VALUES (?, ?, ?)",
                (family_circle_id, role, contact_id),
            ).success

        proxy_name = proxy.get("name")
        if proxy_name or medical_proxy_phone:
            cid = f"proxy_{family_circle_id}"
            if _ensure_contact(cid, proxy_name or "", medical_proxy_phone):
                _set_role("medical_proxy", cid)
        if poa_name or poa_phone:
            cid = f"poa_{family_circle_id}"
            if _ensure_contact(cid, poa_name or "", poa_phone):
                _set_role("poa", cid)
        return ServiceResult.success_result(
            {
                "family_circle_id": family_circle_id,
                "care_recipient_user_id": care_recipient_user_id,
            }
        )

    def set_contact_role(
        self, family_circle_id: str, role: str, contact_id: str
    ) -> ServiceResult:
        """Assign contact role (e.g. medical_proxy, poa) for family."""
        return self.db_manager.execute_update(
            "INSERT OR REPLACE INTO ice_contact_roles (family_circle_id, role, contact_id) VALUES (?, ?, ?)",
            (family_circle_id, role, contact_id),
        )

    def add_allergy(self, care_recipient_user_id: str, allergen: str) -> ServiceResult:
        """Add allergy for care recipient."""
        return self.db_manager.execute_update(
            "INSERT OR REPLACE INTO allergies (care_recipient_user_id, allergen) VALUES (?, ?)",
            (care_recipient_user_id, allergen),
        )

    def add_condition(
        self,
        care_recipient_user_id: str,
        condition_name: str,
        diagnosis_date=None,
        notes=None,
    ) -> ServiceResult:
        """Add condition for care recipient."""
        return self.db_manager.execute_update(
            """INSERT OR REPLACE INTO conditions (care_recipient_user_id, condition_name, diagnosis_date, notes) VALUES (?, ?, ?, ?)""",
            (care_recipient_user_id, condition_name, diagnosis_date, notes),
        )
