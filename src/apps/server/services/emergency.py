"""
Emergency service for Meridian.
WHERE FUNCTIONALITY MOVED TO (client): client/remote.RemoteEmergencyService calls GET /api/emergency/*.
REMOVAL: Required on server. Can be omitted from client deployment when SERVER_URL is set.
"""

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult
from .contact import ContactService


class EmergencyService:
    def __init__(self, contact_service: ContactService, ice_profile_service):
        self.contact_service = contact_service
        self.ice_profile_service = ice_profile_service

    def get_emergency_contacts(self, family_circle_id: str) -> ServiceResult:
        return self.contact_service.get_emergency_contacts(family_circle_id)

    def get_all_contacts(self, family_circle_id: str) -> ServiceResult:
        return self.contact_service.get_all_contacts(family_circle_id)

    def get_medical_summary(self, family_circle_id: str) -> ServiceResult:
        r = self.ice_profile_service.get_ice_profile(family_circle_id)
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
            lines.append(f"• {name} - {dosage} {frequency}")
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
