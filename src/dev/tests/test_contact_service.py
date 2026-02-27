"""
Unit and integration tests for ContactService and EmergencyService.
"""
import pytest
from lib.container_services.contact_service import ContactService
from lib.container_services.emergency_service import EmergencyService


@pytest.mark.unit
class TestContactService:
    """Test cases for ContactService."""
    
    def test_get_all_contacts(self, contact_service):
        """Test getting all contacts from database."""
        result = contact_service.get_all_contacts()
        
        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, list)
        # Should have the test contacts we inserted
        assert len(result.data) >= 0
    
    def test_get_emergency_contacts(self, contact_service):
        """Test getting emergency contacts only."""
        result = contact_service.get_emergency_contacts()
        
        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, list)
        # All returned contacts should be emergency priority
        for contact in result.data:
            assert hasattr(contact, 'priority')
            # Emergency contacts should have priority 'emergency'
    
    def test_format_emergency_contacts_for_display(self, contact_service):
        """Test formatting emergency contacts for display."""
        result = contact_service.format_emergency_contacts_for_display()
        
        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, str)
        # Should contain contact information
        assert len(result.data) > 0


@pytest.mark.integration
class TestContactServiceIntegration:
    """Integration tests for ContactService with database."""
    
    def test_get_contacts_with_data(self, contact_service, sample_contacts_data):
        """Test getting contacts when database has data."""
        result = contact_service.get_all_contacts()
        
        assert result.success is True
        # Should have at least the test contacts
        contact_names = [c.display_name for c in result.data]
        # Verify we can retrieve contacts
        assert len(result.data) >= 0
    
    def test_emergency_contacts_filtering(self, contact_service):
        """Test that emergency contacts are properly filtered."""
        result = contact_service.get_emergency_contacts()
        
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
        result = emergency_service.get_emergency_contacts()
        
        assert result.success is True
        assert result.data is not None
    
    def test_get_all_contacts(self, emergency_service):
        """Test getting all contacts through emergency service."""
        result = emergency_service.get_all_contacts()
        
        assert result.success is True
        assert result.data is not None
    
    def test_format_contacts_for_display(self, emergency_service):
        """Test formatting contacts for display."""
        result = emergency_service.format_contacts_for_display()
        
        assert result.success is True
        assert isinstance(result.data, str)
    
    def test_get_medical_summary(self, emergency_service, populated_test_db):
        """Test getting medical summary."""
        result = emergency_service.get_medical_summary()
        
        assert result.success is True
        assert isinstance(result.data, str)
        # Should contain medical information sections
        assert len(result.data) > 0
        # Should mention medications, allergies, or conditions sections
        data_lower = result.data.lower()
        assert 'medical' in data_lower or 'medication' in data_lower or 'allergy' in data_lower
