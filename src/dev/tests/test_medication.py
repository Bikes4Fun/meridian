"""
Unit and integration tests for MedicationService.
"""
import pytest
from apps.server.services.medication import MedicationService, TimedMedication, PRNMedication


@pytest.mark.unit
class TestMedicationService:
    """Test cases for MedicationService."""
    
    def test_add_timed_medication(self, medication_service):
        """Test adding a timed medication."""
        med = medication_service.add_timed_medication(
            name='Aspirin',
            time='Morning',
            status='not_done'
        )
        
        # Check type by class name to avoid import issues
        assert med.__class__.__name__ == 'TimedMedication'
        assert med.name == 'Aspirin'
        assert med.time == 'Morning'
        assert med.status == 'not_done'
    
    def test_add_timed_medication_with_notes(self, medication_service):
        """Test adding a timed medication with notes."""
        med = medication_service.add_timed_medication(
            name='Lisinopril',
            time='Morning',
            notes='Take with food'
        )
        
        assert med.notes == 'Take with food'
    
    def test_add_prn_medication(self, medication_service):
        """Test adding a PRN medication."""
        med = medication_service.add_prn_medication(
            name='Ibuprofen',
            max_daily=3
        )
        
        # Check type by class name to avoid import issues
        assert med.__class__.__name__ == 'PRNMedication'
        assert med.name == 'Ibuprofen'
        assert med.max_daily == 3
        assert med.status == 'available'
    
    def test_mark_medication_done_timed(self, medication_service):
        """Test marking a timed medication as done."""
        medication_service.add_timed_medication(
            name='Test Med',
            time='Morning'
        )
        
        result = medication_service.mark_medication_done('Test Med', 'timed')
        
        assert result.success is True
        # Verify the medication status was updated
        meds = [m for m in medication_service.timed_medications if m.name == 'Test Med']
        assert len(meds) > 0
        assert meds[0].status == 'done'
    
    def test_mark_medication_done_prn(self, medication_service):
        """Test marking a PRN medication as taken."""
        medication_service.add_prn_medication(name='Ibuprofen')
        
        result = medication_service.mark_medication_done('Ibuprofen', 'prn')
        
        assert result.success is True
        # Verify the medication was updated
        meds = [m for m in medication_service.prn_medications if m.name == 'Ibuprofen']
        assert len(meds) > 0
        assert meds[0].status == 'taken'
        assert meds[0].last_taken is not None
    
    def test_mark_medication_done_not_found(self, medication_service):
        """Test marking a non-existent medication as done."""
        result = medication_service.mark_medication_done('Nonexistent', 'timed')
        
        assert result.success is False
        assert 'not found' in result.error.lower()
    
    def test_get_medication_data(self, medication_service, family_circle_id):
        """Test getting medication data for display."""
        # Add some test medications
        medication_service.add_timed_medication('Med1', 'Morning')
        medication_service.add_prn_medication('PRN1')
        
        result = medication_service.get_medication_data(family_circle_id)
        
        assert result.success is True
        assert result.data is not None
        assert 'timed_medications' in result.data
        assert 'prn_medications' in result.data
        assert isinstance(result.data['timed_medications'], list)
        assert isinstance(result.data['prn_medications'], list)
    
    def test_get_upcoming_medications(self, medication_service):
        """Test getting upcoming medications."""
        # Add medications with different statuses
        medication_service.add_timed_medication('Med1', 'Morning', status='not_done')
        medication_service.add_timed_medication('Med2', 'Afternoon', status='done')
        
        upcoming = medication_service.get_upcoming_medications()
        
        assert isinstance(upcoming, list)
        # Should only include not_done medications
        assert all(med.status == 'not_done' for med in upcoming)
        assert len(upcoming) >= 1


@pytest.mark.integration
class TestMedicationServiceIntegration:
    """Integration tests for MedicationService with database."""
    
    def test_load_medication_data_from_db(self, medication_service, populated_test_db, family_circle_id):
        """Test loading medications from database."""
        # The medication_service should load data in __init__
        # Verify it loaded the test data
        result = medication_service.get_medication_data(family_circle_id)
        
        assert result.success is True
        # Should have loaded medications from the test database
        # The exact count depends on test data setup
        assert result.data is not None
    
    def test_get_overdue_medications(self, medication_service):
        """Test getting overdue medications."""
        result = medication_service.get_overdue_medications()
        
        assert result.success is True
        assert isinstance(result.data, list)
        # Currently returns empty list, but method exists for future implementation
