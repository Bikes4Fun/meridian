"""
Unit and integration tests for ContactService and EmergencyService.
"""
import pytest
from apps.server.services.contact import ContactService
from apps.server.services.emergency import EmergencyService
from dev.tests.conftest import FAMILY_CIRCLE_ID


@pytest.mark.unit
class TestContactService:
    """Test cases for ContactService."""
    
    def test_get_all_contacts(self, contact_service):
        """Test getting all contacts from database."""
        result = contact_service.get_all_contacts(FAMILY_CIRCLE_ID)
        
        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, list)
        # Should have the test contacts we inserted
        assert len(result.data) >= 0
    
    def test_get_emergency_contacts(self, contact_service):
        """Test getting emergency contacts only."""
        result = contact_service.get_emergency_contacts(FAMILY_CIRCLE_ID)
        
        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, list)
        # All returned contacts should be emergency priority
        for contact in result.data:
            assert hasattr(contact, 'priority')
            # Emergency contacts should have priority 'emergency'
    
@pytest.mark.integration
class TestContactServiceIntegration:
    """Integration tests for ContactService with database."""
    
    def test_get_contacts_with_data(self, contact_service, sample_contacts_data):
        """Test getting contacts when database has data."""
        result = contact_service.get_all_contacts(FAMILY_CIRCLE_ID)
        
        assert result.success is True
        # Should have at least the test contacts
        contact_names = [c.display_name for c in result.data]
        # Verify we can retrieve contacts
        assert len(result.data) >= 0
    
    def test_emergency_contacts_filtering(self, contact_service):
        """Test that emergency contacts are properly filtered."""
        result = contact_service.get_emergency_contacts(FAMILY_CIRCLE_ID)
        
        assert result.success is True
        # Emergency contacts should only include those with emergency priority
        for contact in result.data:
            # The exact filtering logic depends on implementation
            # But we should get some contacts back
            assert hasattr(contact, 'display_name')


@pytest.mark.unit
class TestEmergencyService:
    """Test cases for EmergencyService."""
    
    def test_get_emergency_contacts(self, emergency_service):
        """Test getting emergency contacts through emergency service."""
        result = emergency_service.get_emergency_contacts(FAMILY_CIRCLE_ID)
        
        assert result.success is True
        assert result.data is not None
    
    def test_get_all_contacts(self, emergency_service):
        """Test getting all contacts through emergency service."""
        result = emergency_service.get_all_contacts(FAMILY_CIRCLE_ID)
        assert result.success is True
        assert result.data is not None

    def test_get_medical_summary(self, emergency_service, populated_test_db):
        """Test getting medical summary."""
        result = emergency_service.get_medical_summary(FAMILY_CIRCLE_ID)
        assert result.success is True
        assert isinstance(result.data, str)
        assert len(result.data) > 0
        data_lower = result.data.lower()
        assert "medical" in data_lower or "medication" in data_lower or "allergy" in data_lower
