"""
ICE Profile service for In-Case-of-Emergency data.
WHERE FUNCTIONALITY MOVED TO (client): client/remote calls GET /api/ice, PUT /api/ice.
REMOVAL: Required on server. Can be omitted from client deployment when SERVER_URL is set.
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
        """Get ICE profile for family. Joins allergies and medications from existing tables."""
        profile_result = self.safe_query(
            """
            SELECT family_circle_id, profile_name, profile_dob, photo_path, medical_conditions,
                   medical_dnr, dnr_document_path, emergency_proxy_name, medical_proxy_phone,
                   poa_name, poa_phone, notes, last_updated, last_updated_by
            FROM ice_profile
            WHERE family_circle_id = ?
            """,
            (family_circle_id,),
        )
        if not profile_result.success:
            return profile_result
        if not profile_result.data:
            return ServiceResult.success_result(None)

        row = profile_result.data[0]
        allergies_result = self.safe_query(
            "SELECT allergen FROM allergies WHERE family_circle_id = ?", (family_circle_id,)
        )
        allergies = (
            [a["allergen"] for a in allergies_result.data]
            if allergies_result.success and allergies_result.data
            else []
        )

        meds_result = self.safe_query(
            """
            SELECT m.name, m.dosage, m.frequency
            FROM medications m
            WHERE m.family_circle_id = ?
            ORDER BY m.name
            """,
            (family_circle_id,),
        )
        medications = (
            [
                {"name": m["name"], "dosage": m["dosage"], "frequency": m["frequency"]}
                for m in meds_result.data
            ]
            if meds_result.success and meds_result.data
            else []
        )

        data = {
            "family_circle_id": row["family_circle_id"],
            "profile": {"name": row["profile_name"], "dob": row["profile_dob"]},
            "medical": {
                "conditions": row["medical_conditions"],
                "dnr": bool(row["medical_dnr"]),
                "allergies": allergies,
                "medications": medications,
            },
            "emergency": {
                "proxy": {"name": row["emergency_proxy_name"]},
            },
            "photo_path": row["photo_path"],
            "dnr_document_path": row["dnr_document_path"],
            "medical_proxy_phone": row["medical_proxy_phone"],
            "poa_name": row["poa_name"],
            "poa_phone": row["poa_phone"],
            "notes": row["notes"],
            "last_updated": row["last_updated"],
            "last_updated_by": row["last_updated_by"],
        }
        return ServiceResult.success_result(data)

    def update_ice_profile(self, family_circle_id: str, data: dict) -> ServiceResult:
        """Insert or replace ICE profile row. Accepts Smart911-shaped JSON (profile.name, medical.conditions, etc.)."""
        profile = data.get("profile") or {}
        medical = data.get("medical") or {}
        emergency = data.get("emergency") or {}
        proxy = emergency.get("proxy") or {}
        profile_name = profile.get("name")
        profile_dob = profile.get("dob")
        medical_conditions = medical.get("conditions")
        medical_dnr = 1 if medical.get("dnr") else 0
        emergency_proxy_name = proxy.get("name")
        photo_path = data.get("photo_path")
        dnr_document_path = data.get("dnr_document_path")
        medical_proxy_phone = data.get("medical_proxy_phone")
        poa_name = data.get("poa_name")
        poa_phone = data.get("poa_phone")
        notes = data.get("notes")
        last_updated_by = data.get("last_updated_by")

        existing = self.safe_query(
            "SELECT id FROM ice_profile WHERE family_circle_id = ?", (family_circle_id,)
        )
        if existing.success and existing.data:
            result = self.safe_update(
                """
                UPDATE ice_profile SET
                    profile_name = ?, profile_dob = ?, photo_path = ?,
                    medical_conditions = ?, medical_dnr = ?, dnr_document_path = ?,
                    emergency_proxy_name = ?, medical_proxy_phone = ?,
                    poa_name = ?, poa_phone = ?, notes = ?,
                    last_updated = CURRENT_TIMESTAMP, last_updated_by = ?
                WHERE family_circle_id = ?
                """,
                (
                    profile_name,
                    profile_dob,
                    photo_path,
                    medical_conditions,
                    medical_dnr,
                    dnr_document_path,
                    emergency_proxy_name,
                    medical_proxy_phone,
                    poa_name,
                    poa_phone,
                    notes,
                    last_updated_by,
                    family_circle_id,
                ),
            )
        else:
            result = self.safe_update(
                """
                INSERT INTO ice_profile
                (family_circle_id, profile_name, profile_dob, photo_path, medical_conditions,
                 medical_dnr, dnr_document_path, emergency_proxy_name, medical_proxy_phone,
                 poa_name, poa_phone, notes, last_updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    family_circle_id,
                    profile_name,
                    profile_dob,
                    photo_path,
                    medical_conditions,
                    medical_dnr,
                    dnr_document_path,
                    emergency_proxy_name,
                    medical_proxy_phone,
                    poa_name,
                    poa_phone,
                    notes,
                    last_updated_by,
                ),
            )
        if not result.success:
            return result
        return self.get_ice_profile(family_circle_id)
