"""
Calendar service: month grid, day headers, events for date.
Use reference_date (TV's local date) for "current" month/date so the server does not use its own
datetime.now() for the TV's context. Client should send ?date=YYYY-MM-DD for calendar endpoints.
"""

import calendar
import datetime
from dataclasses import dataclass
from typing import List, Optional

from ..database_manager import DatabaseManager

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


class CalendarService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

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

    def add_event(
        self,
        family_circle_id: str,
        event_id: str,
        title: str,
        start_time: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        end_time: Optional[str] = None,
        **kwargs,
    ) -> ServiceResult:
        """Insert a new calendar event. event_id required (client-generated UUID or slug)."""
        query = """
            INSERT INTO calendar_events
            (id, family_circle_id, title, description, start_time, end_time, location, driver_name, driver_contact_id, pickup_time, leave_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event_id,
            family_circle_id,
            title,
            description or None,
            start_time,
            end_time or None,
            location or None,
            kwargs.get("driver_name"),
            kwargs.get("driver_contact_id"),
            kwargs.get("pickup_time"),
            kwargs.get("leave_time"),
        )
        result = self.db_manager.execute_update(query, params)
        if not result.success:
            return ServiceResult.error_result(result.error or "Insert failed")
        return ServiceResult.success_result({"id": event_id})

    def update_event(
        self,
        family_circle_id: str,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
        **kwargs,
    ) -> ServiceResult:
        """Update an existing calendar event."""
        # Build dynamic UPDATE
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if start_time is not None:
            updates.append("start_time = ?")
            params.append(start_time)
        if end_time is not None:
            updates.append("end_time = ?")
            params.append(end_time)
        if location is not None:
            updates.append("location = ?")
            params.append(location)
        for k in ("driver_name", "driver_contact_id", "pickup_time", "leave_time"):
            if k in kwargs:
                updates.append(f"{k} = ?")
                params.append(kwargs[k])
        if not updates:
            return ServiceResult.success_result({"id": event_id})
        params.extend([event_id, family_circle_id])
        query = f"UPDATE calendar_events SET {', '.join(updates)} WHERE id = ? AND family_circle_id = ?"
        result = self.db_manager.execute_update(query, params)
        if not result.success:
            return ServiceResult.error_result(result.error or "Update failed")
        return ServiceResult.success_result({"id": event_id})

    def delete_event(self, family_circle_id: str, event_id: str) -> ServiceResult:
        """Delete a calendar event."""
        result = self.db_manager.execute_update(
            "DELETE FROM calendar_events WHERE id = ? AND family_circle_id = ?",
            (event_id, family_circle_id),
        )
        if not result.success:
            return ServiceResult.error_result(result.error or "Delete failed")
        return ServiceResult.success_result(True)

    def _event_rows_to_payloads(self, rows: list) -> List[dict]:
        events: List[dict] = []
        for row in rows:
            start_time = None
            if row.get("start_time"):
                try:
                    start_time = datetime.datetime.fromisoformat(
                        str(row["start_time"]).replace("Z", "+00:00")
                    )
                except Exception:
                    pass
            display = row["title"]
            if start_time:
                display = f"{row['title']} ({start_time.strftime('%I:%M %p')})"
            events.append(
                {
                    "id": row.get("id"),
                    "title": row["title"],
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                    "description": row.get("description"),
                    "location": row.get("location"),
                    "driver_name": row.get("driver_name"),
                    "driver_contact_id": row.get("driver_contact_id"),
                    "pickup_time": row.get("pickup_time"),
                    "leave_time": row.get("leave_time"),
                    "display": display,
                }
            )
        return events

    def get_events_for_date(
        self, date: str, family_circle_id: Optional[str] = None
    ) -> ServiceResult:
        try:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.datetime.now().replace(day=int(date)).date()
        target_date_str = target_date.strftime("%Y-%m-%d")
        if family_circle_id:
            query = """
                SELECT id, title, start_time, end_time, description, location,
                    driver_name, driver_contact_id, pickup_time, leave_time
                FROM calendar_events
                WHERE family_circle_id = ? AND DATE(start_time) = ?
                ORDER BY start_time
            """
            result = self.db_manager.execute_query(
                query, (family_circle_id, target_date_str)
            )
        else:
            query = """
                SELECT id, title, start_time, end_time, description, location,
                    driver_name, driver_contact_id, pickup_time, leave_time
                FROM calendar_events
                WHERE DATE(start_time) = ?
                ORDER BY start_time
            """
            result = self.db_manager.execute_query(query, (target_date_str,))
        if not result.success:
            return result
        return ServiceResult.success_result(self._event_rows_to_payloads(result.data))

    def get_events_in_range(
        self,
        start_date: str,
        end_date: str,
        family_circle_id: Optional[str] = None,
    ) -> ServiceResult:
        try:
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return ServiceResult.error_result("invalid date")
        if family_circle_id:
            query = """
                SELECT id, title, start_time, end_time, description, location,
                    driver_name, driver_contact_id, pickup_time, leave_time
                FROM calendar_events
                WHERE family_circle_id = ? AND DATE(start_time) >= ? AND DATE(start_time) <= ?
                ORDER BY start_time
            """
            result = self.db_manager.execute_query(
                query, (family_circle_id, start_date, end_date)
            )
        else:
            query = """
                SELECT id, title, start_time, end_time, description, location,
                    driver_name, driver_contact_id, pickup_time, leave_time
                FROM calendar_events
                WHERE DATE(start_time) >= ? AND DATE(start_time) <= ?
                ORDER BY start_time
            """
            result = self.db_manager.execute_query(query, (start_date, end_date))
        if not result.success:
            return result
        return ServiceResult.success_result(self._event_rows_to_payloads(result.data))

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
