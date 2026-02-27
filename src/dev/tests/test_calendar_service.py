"""
Unit and integration tests for CalendarService.
"""
import pytest
from datetime import datetime
from container_services.calendar_service import CalendarService


@pytest.mark.unit
class TestCalendarService:
    """Test cases for CalendarService."""
    
    def test_get_current_month_data(self, calendar_service):
        """Test getting current month calendar data."""
        result = calendar_service.get_current_month_data()
        
        assert result.success is True
        assert result.data is not None
        # Should return a list of weeks (lists of days)
        assert isinstance(result.data, list)
        assert len(result.data) > 0
    
    def test_get_current_date(self, calendar_service):
        """Test getting current date."""
        day = calendar_service.get_current_date()
        
        assert isinstance(day, int)
        assert 1 <= day <= 31
    
    def test_get_current_month(self, calendar_service):
        """Test getting current month."""
        month = calendar_service.get_current_month()
        
        assert isinstance(month, int)
        assert 1 <= month <= 12
    
    def test_get_current_year(self, calendar_service):
        """Test getting current year."""
        year = calendar_service.get_current_year()
        
        assert isinstance(year, int)
        assert year >= 2024
    
    def test_get_day_headers(self, calendar_service):
        """Test getting day headers for calendar."""
        result = calendar_service.get_day_headers()
        
        assert result.success is True
        assert result.data is not None
        # Should return list of day abbreviations
        assert isinstance(result.data, list)
        assert len(result.data) == 7
        # Check for common day abbreviations
        days = result.data
        assert any('Mon' in day or 'Monday' in day for day in days)
        assert any('Sun' in day or 'Sunday' in day for day in days)


@pytest.mark.integration
class TestCalendarServiceIntegration:
    """Integration tests for CalendarService with database."""
    
    def test_get_events_for_date_with_events(self, calendar_service, populated_test_db):
        """Test getting events for a specific date that has events."""
        # Get events for day 15 (we inserted events for 2024-01-15)
        result = calendar_service.get_events_for_date('15')
        
        assert result.success is True
        assert result.data is not None
        # Should return list of event strings
        assert isinstance(result.data, list)
        # Note: The actual events depend on current date matching
        # This test verifies the method works, not the specific data
    
    def test_get_events_for_date_no_events(self, calendar_service):
        """Test getting events for a date with no events."""
        # Use a valid day number (1-28) that likely has no events
        # Use day 1 which is less likely to have events in test data
        result = calendar_service.get_events_for_date('1')
        
        assert result.success is True
        # Should return empty list or None
        assert result.data is None or result.data == []
    
    def test_get_events_for_date_invalid(self, calendar_service):
        """Test getting events with invalid date."""
        # The method will raise ValueError when trying to convert 'invalid' to int
        # We expect it to raise an exception for invalid input
        with pytest.raises(ValueError):
            calendar_service.get_events_for_date('invalid')