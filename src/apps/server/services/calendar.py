"""
Calendar service: month grid, day headers, events for date.
Use reference_date (TV's local date) for "current" month/date so the server does not use its own
datetime.now() for the TV's context. Client should send ?date=YYYY-MM-DD for calendar endpoints.
"""

import calendar
import datetime
from dataclasses import dataclass
from typing import List, Optional

from ..database import DatabaseManager, DatabaseServiceMixin

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


@dataclass
class Event:
    title: str
    start_time: Optional[datetime.datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None

    def __str__(self):
        if self.start_time:
            return f"{self.title} ({self.start_time.strftime('%I:%M %p')})"
        return self.title

    def to_display_text(self):
        if self.start_time:
            return f"• {self.title} ({self.start_time.strftime('%I:%M %p')})"
        return f"• {self.title}"


class CalendarService(DatabaseServiceMixin):
    def __init__(self, db_manager: DatabaseManager):
        DatabaseServiceMixin.__init__(self, db_manager)

    def _ref(self, reference_date: Optional[datetime.date] = None) -> datetime.date:
        """Use TV's date when provided; otherwise fall back to server date (client should send ?date=)."""
        return (
            reference_date
            if reference_date is not None
            else datetime.datetime.now().date()
        )

    def get_current_month_data(
        self, reference_date: Optional[datetime.date] = None
    ) -> ServiceResult:
        d = self._ref(reference_date)
        return ServiceResult.success_result(calendar.monthcalendar(d.year, d.month))

    def get_current_date(self, reference_date: Optional[datetime.date] = None) -> int:
        return self._ref(reference_date).day

    def get_current_month(self, reference_date: Optional[datetime.date] = None) -> int:
        return self._ref(reference_date).month

    def get_current_year(self, reference_date: Optional[datetime.date] = None) -> int:
        return self._ref(reference_date).year

    def get_day_headers(self) -> ServiceResult:
        return ServiceResult.success_result(
            ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        )

    def add_event(self, date: str, event: Event) -> None:
        pass

    def get_events_for_date(self, date: str) -> ServiceResult:
        try:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.datetime.now().replace(day=int(date)).date()
        target_date_str = target_date.strftime("%Y-%m-%d")
        query = """
            SELECT title, start_time, description, location
            FROM calendar_events
            WHERE DATE(start_time) = ?
            ORDER BY start_time
        """
        result = self.safe_query(query, (target_date_str,))
        if not result.success:
            return result
        events = []
        for row in result.data:
            start_time = None
            if row["start_time"]:
                try:
                    start_time = datetime.datetime.fromisoformat(
                        row["start_time"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass
            event = Event(
                title=row["title"],
                start_time=start_time,
                description=row.get("description"),
                location=row.get("location"),
            )
            events.append(str(event))
        return ServiceResult.success_result(events)

    def get_today_events(
        self, reference_date: Optional[datetime.date] = None
    ) -> ServiceResult:
        return self.get_events_for_date(self._ref(reference_date).strftime("%Y-%m-%d"))

    def format_events_for_display(self, events: List[str]) -> str:
        if not events:
            return "No events\ntoday"
        return "Today's\nEvents:\n\n" + "\n".join(
            f"{i}. {e}" for i, e in enumerate(events, 1)
        )

    def get_month_name(self, reference_date: Optional[datetime.date] = None) -> str:
        return datetime.date(2000, self._ref(reference_date).month, 1).strftime("%B")
