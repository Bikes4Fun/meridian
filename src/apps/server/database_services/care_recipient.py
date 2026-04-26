"""
Care recipient and contact role updates. Legal/medical designations (proxy, POA) are just contact roles.
"""

from .safe_query_manager import QueryManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class CareRecipientService:
    def __init__(self, db_manager: QueryManager):
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
        # medical_dnr: accept integer 0/1/2 or boolean; kiosk reads bool(value) so any nonzero = truthy
        raw_dnr = medical.get("dnr")
        if isinstance(raw_dnr, bool):
            medical_dnr = 1 if raw_dnr else 0
        elif raw_dnr is not None:
            try:
                medical_dnr = int(raw_dnr)
            except (TypeError, ValueError):
                medical_dnr = 0
        else:
            medical_dnr = 0
        photo_path = data.get("photo_path")
        dnr_document_path = data.get("dnr_document_path")
        medical_proxy_phone = data.get("medical_proxy_phone")
        poa_name = data.get("poa_name")
        poa_phone = data.get("poa_phone")
        notes = data.get("notes")
        medical_dni_status = medical.get("dni_status")
        medical_nutrition_status = medical.get("nutrition_status")
        polst_dnr_signed = int(bool(medical.get("polst_dnr_signed")))
        polst_dni_signed = int(bool(medical.get("polst_dni_signed")))
        polst_nutrition_signed = int(bool(medical.get("polst_nutrition_signed")))
        devices_notes = data.get("devices_notes")
        brief_history = data.get("brief_history")
        other_notes = data.get("other_notes")

        if not care_recipient_user_id:
            return ServiceResult.error_result("care_recipient_user_id required")

        result = self.db_manager.execute_update(
            """
            INSERT OR REPLACE INTO care_recipients
              (family_circle_id, care_recipient_user_id, name, dob, photo_path,
               medical_dnr, dnr_document_path, notes,
               medical_dni_status, medical_nutrition_status,
               polst_dnr_signed, polst_dni_signed, polst_nutrition_signed,
               devices_notes, brief_history, other_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                medical_dni_status,
                medical_nutrition_status,
                polst_dnr_signed,
                polst_dni_signed,
                polst_nutrition_signed,
                devices_notes,
                brief_history,
                other_notes,
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
        else:
            self.db_manager.execute_update(
                "DELETE FROM ice_contact_roles WHERE family_circle_id=? AND role='medical_proxy'",
                (family_circle_id,),
            )
        if poa_name or poa_phone:
            cid = f"poa_{family_circle_id}"
            if _ensure_contact(cid, poa_name or "", poa_phone):
                _set_role("poa", cid)
        else:
            self.db_manager.execute_update(
                "DELETE FROM ice_contact_roles WHERE family_circle_id=? AND role='poa'",
                (family_circle_id,),
            )
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

    def care_recipient_exists(
        self, family_circle_id: str, care_recipient_user_id: str
    ) -> bool:
        """Return True when a care recipient row exists for this family/user id."""
        r = self.db_manager.execute_query(
            "SELECT 1 FROM care_recipients WHERE family_circle_id = ? AND care_recipient_user_id = ? LIMIT 1",
            (family_circle_id, care_recipient_user_id),
        )
        return bool(r.success and r.data)

    def get_dnr_document_basename(
        self, family_circle_id: str, care_recipient_user_id: str
    ):
        """Return stored DNR/POLST basename for a care recipient, or None."""
        r = self.db_manager.execute_query(
            "SELECT dnr_document_path FROM care_recipients WHERE family_circle_id = ? AND care_recipient_user_id = ? LIMIT 1",
            (family_circle_id, care_recipient_user_id),
        )
        if not r.success or not r.data:
            return None
        return r.data[0].get("dnr_document_path")

    def set_dnr_document_path(
        self, family_circle_id: str, care_recipient_user_id: str, dnr_document_path: str
    ) -> ServiceResult:
        """Update stored DNR/POLST basename for an existing care recipient row."""
        r = self.db_manager.execute_update(
            "UPDATE care_recipients SET dnr_document_path = ? WHERE family_circle_id = ? AND care_recipient_user_id = ?",
            (dnr_document_path, family_circle_id, care_recipient_user_id),
        )
        if not r.success:
            return r
        return ServiceResult.success_result(
            {
                "family_circle_id": family_circle_id,
                "care_recipient_user_id": care_recipient_user_id,
                "dnr_document_path": dnr_document_path,
            }
        )

    def replace_all_conditions(self, care_recipient_user_id: str, condition_names: list) -> ServiceResult:
        """Delete all conditions for care recipient and reinsert the given list."""
        del_r = self.db_manager.execute_update(
            "DELETE FROM conditions WHERE care_recipient_user_id = ?",
            (care_recipient_user_id,),
        )
        if not del_r.success:
            return del_r
        for name in condition_names:
            name = (name or "").strip()
            if not name:
                continue
            self.db_manager.execute_update(
                "INSERT OR REPLACE INTO conditions (care_recipient_user_id, condition_name) VALUES (?, ?)",
                (care_recipient_user_id, name),
            )
        return ServiceResult.success_result(True)

    def replace_all_allergies(self, care_recipient_user_id: str, allergens: list) -> ServiceResult:
        """Delete all allergies for care recipient and reinsert the given list.

        Each item may be a string (allergen only) or a dict with 'allergen' and optional 'reaction'.
        """
        del_r = self.db_manager.execute_update(
            "DELETE FROM allergies WHERE care_recipient_user_id = ?",
            (care_recipient_user_id,),
        )
        if not del_r.success:
            return del_r
        for item in allergens:
            if isinstance(item, dict):
                allergen = (item.get("allergen") or "").strip()
                reaction = (item.get("reaction") or "").strip() or None
            else:
                allergen = (item or "").strip()
                reaction = None
            if not allergen:
                continue
            self.db_manager.execute_update(
                "INSERT INTO allergies (care_recipient_user_id, allergen, reaction) VALUES (?, ?, ?)",
                (care_recipient_user_id, allergen, reaction),
            )
        return ServiceResult.success_result(True)

    def get_documents(self, family_circle_id: str) -> ServiceResult:
        """Return all documents for the care recipient of this family circle."""
        r = self.db_manager.execute_query(
            "SELECT id, doc_type, doc_label, doc_date, file_path, sort_order"
            " FROM care_recipient_documents"
            " WHERE family_circle_id = ?"
            " ORDER BY sort_order, id",
            (family_circle_id,),
        )
        return r

    def add_document(self, family_circle_id: str, care_recipient_user_id: str,
                     doc_type: str, doc_label: str, doc_date: str, file_path: str,
                     sort_order: int = 0) -> ServiceResult:
        return self.db_manager.execute_insert(
            "INSERT INTO care_recipient_documents"
            " (family_circle_id, care_recipient_user_id, doc_type, doc_label, doc_date, file_path, sort_order)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (family_circle_id, care_recipient_user_id, doc_type, doc_label, doc_date, file_path, sort_order),
        )

    def update_document(self, doc_id: int, family_circle_id: str,
                        doc_type: str, doc_label: str, doc_date: str) -> ServiceResult:
        return self.db_manager.execute_update(
            "UPDATE care_recipient_documents"
            " SET doc_type=?, doc_label=?, doc_date=?"
            " WHERE id=? AND family_circle_id=?",
            (doc_type, doc_label, doc_date, doc_id, family_circle_id),
        )

    def set_document_file(self, doc_id: int, family_circle_id: str, file_path: str) -> ServiceResult:
        return self.db_manager.execute_update(
            "UPDATE care_recipient_documents SET file_path=? WHERE id=? AND family_circle_id=?",
            (file_path, doc_id, family_circle_id),
        )

    def get_document_file_path(self, doc_id: int, family_circle_id: str):
        r = self.db_manager.execute_query(
            "SELECT file_path FROM care_recipient_documents WHERE id=? AND family_circle_id=?",
            (doc_id, family_circle_id),
        )
        if r.success and r.data:
            return r.data[0].get("file_path")
        return None

    def delete_document(self, doc_id: int, family_circle_id: str) -> ServiceResult:
        return self.db_manager.execute_update(
            "DELETE FROM care_recipient_documents WHERE id=? AND family_circle_id=?",
            (doc_id, family_circle_id),
        )

    def get_care_recipient_user_id(self, family_circle_id: str):
        r = self.db_manager.execute_query(
            "SELECT care_recipient_user_id FROM care_recipients WHERE family_circle_id=? LIMIT 1",
            (family_circle_id,),
        )
        if r.success and r.data:
            return r.data[0].get("care_recipient_user_id")
        return None

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
