"""
Unit tests for TimeService.
These tests don't require a database connection.
"""
import pytest
from datetime import datetime
from container_services.time_service import TimeService


@pytest.mark.unit
class TestTimeService:
    """Test cases for TimeService."""
    
    def test_get_dayof_week(self, time_service):
        """Test getting day of week."""
        day = time_service.get_dayof_week()
        assert day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    def test_get_am_pm_returns_valid_value(self, time_service):
        """Test that get_am_pm returns a valid time of day."""
        result = time_service.get_am_pm()
        assert result in ["Morning", "Afternoon", "Evening", "Night"]
    
    def test_get_am_pm_is_string(self, time_service):
        """Test that get_am_pm returns a string."""
        result = time_service.get_am_pm()
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_get_time_format(self, time_service):
        """Test that get_time returns properly formatted time."""
        time_str = time_service.get_time()
        # Should be in format like "08:30 AM" or "02:30 PM"
        assert ':' in time_str
        assert 'AM' in time_str or 'PM' in time_str
    
    def test_get_date_format(self, time_service):
        """Test that get_date returns properly formatted date."""
        date_str = time_service.get_date()
        # Should be in format like "January 15, 2024"
        assert ',' in date_str
        # Check for current year or recent years (2024-2026)
        current_year = datetime.now().year
        assert str(current_year) in date_str or str(current_year - 1) in date_str or str(current_year + 1) in date_str
    
    def test_get_month_day_format(self, time_service):
        """Test that get_month_day returns properly formatted month and day."""
        month_day = time_service.get_month_day()
        # Should be in format like "JANUARY 15" (uppercase)
        assert month_day.isupper()
        assert ' ' in month_day
    
    def test_get_year(self, time_service):
        """Test that get_year returns current year as string."""
        year = time_service.get_year()
        assert year.isdigit()
        assert len(year) == 4
        assert int(year) >= 2024
