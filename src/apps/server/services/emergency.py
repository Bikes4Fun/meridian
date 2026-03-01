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
    def __init__(self, contact_service: ContactService):
        self.contact_service = contact_service

    def get_emergency_contacts(self) -> ServiceResult:
        return self.contact_service.get_emergency_contacts()

    def get_all_contacts(self) -> ServiceResult:
        return self.contact_service.get_all_contacts()

    def format_contacts_for_display(self) -> ServiceResult:
        return self.contact_service.format_emergency_contacts_for_display()

    def get_medical_summary(self) -> ServiceResult:
        medications_result = self.contact_service.db_manager.execute_query(
            "SELECT name, dosage, frequency FROM medications"
        )
        medications = medications_result.data if medications_result.success else []
        allergies_result = self.contact_service.db_manager.execute_query(
            "SELECT allergen FROM allergies"
        )
        allergies = allergies_result.data if allergies_result.success else []
        conditions_result = self.contact_service.db_manager.execute_query(
            "SELECT condition_name FROM conditions"
        )
        conditions = conditions_result.data if conditions_result.success else []
        lines = ["Medical Information:"]
        if medications:
            lines.append("\nMedications:")
            for med in medications:
                lines.append(f"• {med['name']} - {med['dosage']} {med['frequency']}")
        if allergies:
            lines.append("\nAllergies:")
            for allergy in allergies:
                lines.append(f"• {allergy['allergen']}")
        if conditions:
            lines.append("\nMedical Conditions:")
            for condition in conditions:
                lines.append(f"• {condition['condition_name']}")
        return ServiceResult.success_result("\n".join(lines))
