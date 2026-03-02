"""
Care recipient and contact role updates. Legal/medical designations (proxy, POA) are just contact roles.
"""

from ..database import DatabaseManager, DatabaseServiceMixin

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class CareRecipientService(DatabaseServiceMixin):
    def __init__(self, db_manager: DatabaseManager):
        DatabaseServiceMixin.__init__(self, db_manager)

    def update_care_recipient(
        self, family_circle_id: str, data: dict
    ) -> ServiceResult:
        """Update care_recipients and contact roles (proxy, POA). Data is care recipient, not session user."""
        care_recipient_user_id = data.get("user_id") or data.get("care_recipient_user_id")
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
            return ServiceResult.error_result(
                "care_recipient_user_id required"
            )

        result = self.safe_update(
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
            r = self.safe_query(
                "SELECT id FROM contacts WHERE id = ? AND family_circle_id = ?",
                (cid, family_circle_id),
            )
            if r.success and r.data:
                return (
                    self.safe_update(
                        "UPDATE contacts SET display_name=?, phone=? WHERE id=? AND family_circle_id=?",
                        (name, phone or "", cid, family_circle_id),
                    ).success
                )
            return self.safe_update(
                "INSERT INTO contacts (id, family_circle_id, display_name, phone) VALUES (?, ?, ?, ?)",
                (cid, family_circle_id, name, phone or ""),
            ).success

        def _set_role(role: str, contact_id: str) -> bool:
            return self.safe_update(
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

