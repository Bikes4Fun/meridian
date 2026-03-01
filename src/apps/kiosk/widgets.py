"""
Widget creation logic for Meridian Kiosk.
Handles the creation of individual UI widgets.
"""

from .modular_display import (
    DementiaWidget,
    DementiaLabel,
    DementiaButton,
    DementiaImage,
)

# Top section: Day + Time of day (left) | Icon (right)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.clock import Clock
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


def apply_border(widget, key, display_settings):
    """Apply border to widget if configured in display_settings.borders. Uses default when key missing."""
    if display_settings.borders and key in display_settings.borders:
        b = display_settings.borders[key]
    else:
        b = {"color": [0, 0, 0, 1], "width": 1}

    def make_updater(color, width):
        def update(instance, value):
            instance.canvas.after.clear()
            with instance.canvas.after:
                Color(*color)
                Line(
                    rectangle=(instance.x, instance.y, instance.width, instance.height),
                    width=width,
                )

        return update

    widget.bind(
        pos=make_updater(b["color"], b["width"]),
        size=make_updater(b["color"], b["width"]),
    )


class WidgetFactory:
    """Factory for creating UI widgets based on user preferences."""

    def __init__(self, services, display_settings=None):
        self.services = services
        self.display_settings = display_settings
        self.time_service = services.get("time_service")
        self.calendar_service = services.get("calendar_service")
        self.emergency_service = services.get("emergency_service")
        self.medication_service = services.get("medication_service")
        self.ice_profile_service = services.get("ice_profile_service")
        self.location_service = services.get("location_service")

    def create_widget(self, widget_type, **kwargs):
        """Create a widget of the specified type."""
        widget_creators = {
            "clock": self.create_clock_widget,
            "medication": self.create_medication_widget,
            "events": self.create_events_widget,
            "calendar": self.create_calendar_widget,
            "today_events": self.create_today_events_widget,
            "emergency_contacts": self.create_emergency_contacts_widget,
            "medical_info": self.create_medical_info_widget,
            "emergency_profile": self.create_emergency_profile_widget,
            "family_locations": self.create_family_locations_widget,
        }

        if widget_type not in widget_creators:
            raise ValueError(f"Unknown widget type: {widget_type}")

        return widget_creators[widget_type](**kwargs)

    def get_available_widgets(self):
        """Get list of available widget types."""
        return [
            "clock",
            "medication",
            "events",
            "calendar",
            "today_events",
            "emergency_contacts",
            "medical_info",
            "emergency_profile",
        ]

    def is_widget_enabled(self, widget_type):
        """Check if a widget type is enabled for the user."""
        # all widgets are enabled by default
        # TODO: check user preferences from user_setting
        return True

    def get_user_widget_preferences(self):
        """Get user's widget preferences."""
        # For now, return default preferences
        # TODO: load from user_settings
        return {
            "clock": True,
            "medication": True,
            "events": True,
            "calendar": True,
            "today_events": True,
            "emergency_contacts": True,
            "medical_info": True,
        }

    def create_widgets_for_screen(self, screen_type):
        """Create all widgets needed for a specific screen type."""
        screen_widgets = {
            "home": ["clock", "medication", "events"],
            "calendar": ["calendar", "today_events"],
            "emergency": ["emergency_profile"],
            "more": [],
        }

        if screen_type not in screen_widgets:
            return []

        widgets = []
        for widget_type in screen_widgets[screen_type]:
            if self.is_widget_enabled(widget_type):
                widget = self.create_widget(widget_type)
                widgets.append((widget_type, widget))

        return widgets

    def create_clock_widget(self):
        """Create clock widget using modular components - dementia clock style."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        # Use colors from settings
        clock_bg = display_settings.clock_background_color
        text_color = display_settings.colors["text"]

        clock = DementiaWidget(
            orientation="vertical",
            background_color=clock_bg,
            display_settings=display_settings,
        )
        clock.spacing = display_settings.clock_spacing
        clock.padding = display_settings.clock_padding
        apply_border(clock, "clock", display_settings)

        top_section = BoxLayout(orientation="horizontal")
        top_section.size_hint = (1, None)
        top_section.height = (
            display_settings.clock_day_height + display_settings.clock_text_height
        )
        apply_border(top_section, "clock_top_section", display_settings)

        # Left side: Day and Time of day stacked
        left_stack = BoxLayout(orientation="vertical")
        left_stack.size_hint = (0.7, 1)

        day_label = DementiaLabel(
            font_size="title", text="", display_settings=display_settings
        )
        day_label.color = text_color
        day_label.halign = "left"
        day_label.valign = "middle"
        day_label.size_hint = (1, 0.5)
        apply_border(day_label, "clock_day_label", display_settings)
        left_stack.add_widget(day_label)

        time_of_day_label = DementiaLabel(
            font_size="large", text="", display_settings=display_settings
        )
        time_of_day_label.color = text_color
        time_of_day_label.halign = "left"
        time_of_day_label.valign = "top"
        time_of_day_label.size_hint = (1, 0.5)
        apply_border(time_of_day_label, "clock_time_of_day_label", display_settings)
        left_stack.add_widget(time_of_day_label)

        top_section.add_widget(left_stack)

        # Right side: Icon (centered in container)
        icon_container = AnchorLayout(anchor_x="center", anchor_y="center")
        icon_container.size_hint = (0.3, 1)
        apply_border(icon_container, "clock_icon_container", display_settings)

        time_of_day_icon = Image()
        time_of_day_icon.size_hint = (None, None)
        time_of_day_icon.width = display_settings.clock_icon_size
        time_of_day_icon.height = display_settings.clock_icon_size
        # Set initial icon based on current time
        initial_time_of_day = (
            self.time_service.get_am_pm() if self.time_service else "Morning"
        )
        time_of_day_icon.source = self._get_time_of_day_icon(initial_time_of_day)
        icon_container.add_widget(time_of_day_icon)

        top_section.add_widget(icon_container)
        clock.add_widget(top_section)

        # Main time display - very large, centered
        time_label = DementiaLabel(
            font_size="huge", text="", display_settings=display_settings
        )
        time_label.color = text_color
        time_label.halign = "center"
        time_label.valign = "middle"
        time_label.size_hint = (1, None)
        time_label.height = display_settings.clock_time_height
        apply_border(time_label, "clock_time_label", display_settings)
        clock.add_widget(time_label)

        # Bottom section: Month Day (left) | Year (right)
        bottom_section = BoxLayout(orientation="horizontal")
        bottom_section.size_hint = (1, None)
        bottom_section.height = display_settings.clock_date_height
        apply_border(bottom_section, "clock_bottom_section", display_settings)

        date_label = DementiaLabel(
            font_size="large", text="", display_settings=display_settings
        )
        date_label.color = text_color
        date_label.halign = "left"
        date_label.valign = "middle"
        date_label.size_hint = (0.6, 1)
        apply_border(date_label, "clock_date_label", display_settings)
        bottom_section.add_widget(date_label)

        year_label = DementiaLabel(
            font_size="large", text="", display_settings=display_settings
        )
        year_label.color = text_color
        year_label.halign = "right"
        year_label.valign = "middle"
        year_label.size_hint = (0.4, 1)
        apply_border(year_label, "clock_year_label", display_settings)
        bottom_section.add_widget(year_label)

        clock.add_widget(bottom_section)

        # Store references for updates
        clock.day_label = day_label
        clock.time_of_day_icon = time_of_day_icon
        clock.time_of_day_label = time_of_day_label
        clock.time_label = time_label
        clock.date_label = date_label
        clock.year_label = year_label

        return clock

    def _get_time_of_day_icon(self, time_of_day):
        """Get the appropriate icon for the time of day."""
        _kiosk_dir = os.path.dirname(os.path.abspath(__file__))
        icon_map = {
            "Morning": os.path.join(_kiosk_dir, "icons", "sunrise.png"),
            "Noon": os.path.join(_kiosk_dir, "icons", "noon.png"),
            "Afternoon": os.path.join(_kiosk_dir, "icons", "noon.png"),  # Use noon for afternoon
            "Evening": os.path.join(_kiosk_dir, "icons", "evening.png"),
            "Night": os.path.join(_kiosk_dir, "icons", "night.png"),
        }
        return icon_map.get(
            time_of_day
        )  # TODO: had a default but shouldn't be using defaults

    def create_medication_widget(self):
        """Create medication widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        # Use actual user settings - no hardcoded defaults
        med = DementiaWidget(
            display_settings=display_settings,
            orientation=display_settings.med_orientation,
            background_color=display_settings.med_background_color,
        )

        # Title - much larger
        title = DementiaLabel(
            display_settings=display_settings, font_size="title", text="Medications"
        )
        med.add_widget(title)

        # Medication content
        med_content = DementiaLabel(
            display_settings=display_settings,
            font_size="body",
            text="Loading medications...",
        )
        med.add_widget(med_content)
        med.medication_content = med_content

        return med

    def create_events_widget(self):
        """Create events widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        # Use actual user settings - no hardcoded defaults
        events = DementiaWidget(
            display_settings=display_settings,
            orientation=display_settings.events_orientation,
            background_color=display_settings.events_background_color,
        )

        # Title
        title = DementiaLabel(
            display_settings=display_settings, font_size="title", text="Today's Events"
        )
        events.add_widget(title)

        # Events content
        events_content = DementiaLabel(
            display_settings=display_settings,
            font_size="body",
            text="Loading events...",
        )
        events.add_widget(events_content)
        events.events_content = events_content

        return events

    def create_calendar_widget(self):
        """Create interactive calendar widget using modular components."""
        logger.debug(
            f"[CALENDAR] create_calendar_widget called, calendar_service={self.calendar_service is not None}"
        )
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        calendar = DementiaWidget(
            display_settings=display_settings,
            orientation="vertical",
            background_color=display_settings.calendar_background_color,
        )
        apply_border(calendar, "calendar", display_settings)

        # Calendar title
        title = DementiaLabel(
            display_settings=display_settings, font_size="title", text="Calendar"
        )
        calendar.add_widget(title)

        # Calendar grid container (no padding so buttons can receive touches)
        calendar_grid = DementiaWidget(
            display_settings=display_settings, orientation="vertical"
        )
        calendar_grid.size_hint = (1, 1)
        calendar_grid.padding = 0
        calendar_grid.spacing = 2

        if self.calendar_service:
            # Get calendar data
            days_result = self.calendar_service.get_day_headers()
            cal_data_result = self.calendar_service.get_current_month_data()

            if days_result.success and cal_data_result.success:
                # Day headers
                days = days_result.data
                cal_data = cal_data_result.data
                current_date = self.calendar_service.get_current_date()

                # Create day headers row (no padding so buttons fill the row)
                header_row = DementiaWidget(
                    display_settings=display_settings, orientation="horizontal"
                )
                header_row.size_hint = (1, None)
                header_row.height = 50
                header_row.padding = 0
                header_row.spacing = 2

                for day in days:
                    header_btn = DementiaButton(
                        display_settings=display_settings,
                        text=day,
                        font_size="body",
                        color="text",
                        background_color="surface",
                        size_hint=(1, 1),
                    )
                    header_row.add_widget(header_btn)

                calendar_grid.add_widget(header_row)

                # Store day buttons for selection highlighting
                day_buttons = {}

                # Create calendar days
                for week in cal_data:
                    week_row = DementiaWidget(
                        display_settings=display_settings, orientation="horizontal"
                    )
                    week_row.size_hint = (1, None)
                    week_row.height = 50
                    week_row.padding = 0
                    week_row.spacing = 2

                    for day in week:
                        if day == 0:
                            # Empty day
                            empty_btn = DementiaButton(
                                display_settings=display_settings,
                                text="",
                                font_size="body",
                                color="text",
                                background_color="surface",
                                size_hint=(1, 1),
                            )
                            week_row.add_widget(empty_btn)
                        else:
                            # Day button
                            day_btn = DementiaButton(
                                display_settings=display_settings,
                                text=str(day),
                                font_size="body",
                                color="text",
                                background_color="surface",
                                size_hint=(1, 1),
                            )

                            # Store reference for selection highlighting
                            day_buttons[day] = day_btn

                            if day == current_date:
                                day_btn.background_color = display_settings.colors[
                                    "error"
                                ]  # Highlight today

                            # Bind click event
                            def make_click_handler(day_num, btn):
                                def handler(instance):
                                    logger.debug(f"Button CLICKED for day {day_num}")
                                    self._on_date_select(
                                        day_num,
                                        btn,
                                        day_buttons,
                                        current_date,
                                        display_settings,
                                    )

                                return handler

                            day_btn.bind(on_press=make_click_handler(day, day_btn))
                            day_btn.bind(on_release=make_click_handler(day, day_btn))
                            week_row.add_widget(day_btn)

                    calendar_grid.add_widget(week_row)

                # Store current selection (start with today)
                calendar.selected_day = current_date
                calendar.day_buttons = day_buttons

                calendar.add_widget(calendar_grid)

            else:
                error_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="Error loading calendar",
                )
                calendar.add_widget(error_content)
        else:
            error_content = DementiaLabel(
                display_settings=display_settings,
                font_size="body",
                text="Calendar service not available",
            )
            calendar.add_widget(error_content)

        return calendar

    def create_today_events_widget(self):
        """Create today's events widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        events = DementiaWidget(
            display_settings=display_settings, orientation="vertical"
        )
        apply_border(events, "today_events", display_settings)

        # Events title
        title = DementiaLabel(
            display_settings=display_settings, font_size="title", text="Today's Events"
        )
        events.add_widget(title)

        # Events content
        if self.calendar_service:
            today = datetime.now()
            result = self.calendar_service.get_events_for_date(
                today.strftime("%Y-%m-%d")
            )

            if result.success and result.data:
                events_text = [f"• {event}" for event in result.data]
                events_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="\n".join(events_text),
                )
            else:
                events_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="No events today",
                )
        else:
            events_content = DementiaLabel(
                display_settings=display_settings,
                font_size="body",
                text="Calendar service not available",
            )

        events.add_widget(events_content)

        # Store reference for updates from calendar clicks
        events.events_content = events_content
        return events

    def create_emergency_contacts_widget(self):
        """Create emergency contacts widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        contacts = DementiaWidget(
            display_settings=display_settings,
            orientation="vertical",
            background_color=display_settings.contacts_background_color,
        )
        apply_border(contacts, "emergency_contacts", display_settings)

        # Contacts title
        title = DementiaLabel(
            display_settings=display_settings,
            font_size="title",
            text="Emergency Contacts",
        )
        contacts.add_widget(title)

        # Contacts content
        if self.emergency_service:
            result = self.emergency_service.format_contacts_for_display()
            if result.success:
                contacts_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text=result.data,
                )
            else:
                contacts_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="Error loading contacts",
                )
        else:
            contacts_content = DementiaLabel(
                display_settings=display_settings,
                font_size="body",
                text="Emergency service not available",
            )

        contacts.add_widget(contacts_content)
        return contacts

    def create_medical_info_widget(self):
        """Create medical info widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        medical = DementiaWidget(
            display_settings=display_settings,
            orientation="vertical",
            background_color=display_settings.medical_background_color,
        )
        apply_border(medical, "medical_info", display_settings)

        # Medical title
        title = DementiaLabel(
            display_settings=display_settings,
            font_size="title",
            text="Medical Information",
        )
        medical.add_widget(title)

        # Medical content
        if self.emergency_service:
            result = self.emergency_service.get_medical_summary()
            if result.success:
                medical_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text=result.data,
                )
            else:
                medical_content = DementiaLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="Error loading medical info",
                )
        else:
            medical_content = DementiaLabel(
                display_settings=display_settings,
                font_size="body",
                text="Emergency service not available",
            )

        medical.add_widget(medical_content)
        return medical

    def create_emergency_profile_widget(self):
        """Create emergency profile: patient name, DNR, contacts, meds, allergies, proxy, POA.
        Light background, dark text for vision-impaired; flashing border for visibility."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        dark_text = (0.1, 0.1, 0.1, 1)
        profile = DementiaWidget(
            display_settings=display_settings,
            orientation="vertical",
            background_color=(0.98, 0.98, 0.96, 1),
        )
        profile.spacing = display_settings.spacing["md"]
        profile.padding = display_settings.spacing["lg"]

        alert_ref = self.services.get("_alert_activated", [False])
        flash_state = [0]

        def _draw_border(w, color):
            w.canvas.after.clear()
            with w.canvas.after:
                Color(*color)
                Line(rectangle=(w.x, w.y, w.width, w.height), width=8)

        def _border_tick(dt):
            if alert_ref[0]:
                flash_state[0] = 1 - flash_state[0]
                c = (1, 0.3, 0.1, 1) if flash_state[0] else (1, 0.5, 0, 1)
            else:
                c = (0.9, 0.4, 0.1, 1)
            _draw_border(profile, c)

        def _update_border(o, v):
            if alert_ref[0]:
                c = (1, 0.3, 0.1, 1) if flash_state[0] else (1, 0.5, 0, 1)
            else:
                c = (0.9, 0.4, 0.1, 1)
            _draw_border(profile, c)

        profile.bind(pos=_update_border, size=_update_border)
        Clock.schedule_interval(_border_tick, 0.5)

        if self.ice_profile_service:
            result = self.ice_profile_service.get_ice_profile()
            if result.success and result.data:
                d = result.data
                profile_data = d.get("profile") or {}
                medical = d.get("medical") or {}
                emergency = d.get("emergency") or {}
                proxy = emergency.get("proxy") or {}

                name_label = DementiaLabel(
                    display_settings=display_settings,
                    font_size="huge",
                    text=profile_data.get("name") or "Patient",
                    color="text",
                )
                name_label.color = dark_text
                profile.add_widget(name_label)

                dnr = medical.get("dnr", False)
                dnr_label = DementiaLabel(
                    display_settings=display_settings,
                    font_size="huge",
                    text="DNR" if dnr else "FULL CODE",
                    color="text",
                )
                dnr_label.color = (0.8, 0.2, 0.2, 1) if dnr else (0.2, 0.6, 0.2, 1)
                profile.add_widget(dnr_label)

                if medical.get("conditions"):
                    cond_label = DementiaLabel(
                        display_settings=display_settings,
                        font_size="title",
                        text=f"Diagnosis: {medical['conditions']}",
                        color="text",
                    )
                    cond_label.color = dark_text
                    profile.add_widget(cond_label)

                if proxy.get("name") or d.get("medical_proxy_phone"):
                    proxy_text = f"Medical Proxy: {proxy.get('name', '')} {d.get('medical_proxy_phone', '')}".strip()
                    if proxy_text:
                        p_label = DementiaLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=proxy_text,
                            color="text",
                        )
                        p_label.color = dark_text
                        profile.add_widget(p_label)

                if d.get("poa_name") or d.get("poa_phone"):
                    poa_text = (
                        f"POA: {d.get('poa_name', '')} {d.get('poa_phone', '')}".strip()
                    )
                    if poa_text:
                        poa_label = DementiaLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=poa_text,
                            color="text",
                        )
                        poa_label.color = dark_text
                        profile.add_widget(poa_label)

                allergies = medical.get("allergies") or []
                if allergies:
                    a_label = DementiaLabel(
                        display_settings=display_settings,
                        font_size="large",
                        text="Allergies: " + ", ".join(allergies),
                        color="text",
                    )
                    a_label.color = dark_text
                    profile.add_widget(a_label)

                meds = medical.get("medications") or []
                if meds:
                    med_lines = [
                        f"{m.get('name', '')} {m.get('dosage', '')}".strip()
                        for m in meds
                    ]
                    med_label = DementiaLabel(
                        display_settings=display_settings,
                        font_size="large",
                        text="Medications: " + "; ".join(med_lines[:5]),
                        color="text",
                    )
                    med_label.color = dark_text
                    profile.add_widget(med_label)

                if self.emergency_service:
                    ec_result = self.emergency_service.format_contacts_for_display()
                    if (
                        ec_result.success
                        and ec_result.data
                        and "No emergency contacts" not in str(ec_result.data)
                    ):
                        ec_label = DementiaLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text="Emergency Contacts:\n" + str(ec_result.data),
                            color="text",
                        )
                        ec_label.color = dark_text
                        profile.add_widget(ec_label)
            else:
                err_label = DementiaLabel(
                    display_settings=display_settings,
                    font_size="title",
                    text="Emergency profile not found",
                    color="text",
                )
                err_label.color = dark_text
                profile.add_widget(err_label)
        else:
            err_label = DementiaLabel(
                display_settings=display_settings,
                font_size="title",
                text="Emergency profile service not available",
                color="text",
            )
            err_label.color = dark_text
            profile.add_widget(err_label)

        return profile

    def _on_date_select(
        self, day_num, clicked_btn, day_buttons, current_date, display_settings
    ):
        """Handle date selection in calendar."""
        logger.debug(f"Calendar day clicked: day_num={day_num}")
        logger.debug(
            f"calendar_service={self.calendar_service is not None}, has today_events_widget={hasattr(self, 'today_events_widget')}"
        )

        # Highlight selected day - reset all buttons first
        for day, btn in day_buttons.items():
            if day == current_date:
                # Today stays highlighted with error color
                btn.background_color = display_settings.colors["error"]
            else:
                # Reset to surface color
                btn.background_color = display_settings.colors["surface"]

        # Highlight the clicked day with nav color (unless it's today, which keeps error color)
        if day_num != current_date:
            clicked_btn.background_color = display_settings.colors["nav"]

        logger.debug(f"Highlighted day {day_num}")

        if self.calendar_service and hasattr(self, "today_events_widget"):
            try:
                date_str = datetime.now().replace(day=day_num).strftime("%Y-%m-%d")
            except ValueError:
                date_str = datetime.now().strftime("%Y-%m-%d")
            result = self.calendar_service.get_events_for_date(date_str)
            logger.debug(
                f"Events for day {day_num}: success={result.success}, count={len(result.data) if result.data else 0}"
            )

            # Update the events_content label directly (not searching children)
            if hasattr(self.today_events_widget, "events_content"):
                if result.success and result.data:
                    events_text = [f"• {event}" for event in result.data]
                    self.today_events_widget.events_content.text = (
                        f"Day {day_num} Events:\n" + "\n".join(events_text)
                    )
                    logger.debug(f"Updated events_content with: {events_text}")
                else:
                    self.today_events_widget.events_content.text = (
                        f"Day {day_num}: No events"
                    )
                    logger.debug(f"Updated events_content to 'No events'")
            else:
                logger.debug(f"today_events_widget has no events_content attribute!")
        else:
            logger.debug(
                f"Cannot update - missing calendar_service or today_events_widget"
            )

    def _create_family_locations_title(self):
        """Create Family Locations screen title block."""
        title = DementiaLabel(
            display_settings=self.display_settings,
            font_size="title",
            text="Family Locations",
        )
        title.size_hint_y = None
        title.height = 70
        apply_border(title, "family_locations_title", self.display_settings)
        return title

    def _create_family_possible_places_block(self):
        """Create possible family locations block (debug)."""
        prefix = "possible family locations:\n"
        if self.location_service:
            places_result = self.location_service.get_named_places()
            if places_result.success and places_result.data:
                lines = []
                for p in places_result.data:
                    lat, lon = p.get("gps_latitude"), p.get("gps_longitude")
                    coords = (
                        f"{lat:.6f},{lon:.6f}"
                        if lat is not None and lon is not None
                        else "—"
                    )
                    lines.append(f"• {p.get('location_name', 'Unknown')}:\n   {coords}")
                suffix = "\n".join(lines)
            else:
                suffix = "(none)"
        else:
            suffix = "(unavailable)"
        widget = DementiaLabel(
            display_settings=self.display_settings,
            font_size="body",
            text=prefix + suffix,
            shorten=False,
        )
        widget.size_hint_x = 0.5  # for_columns

        apply_border(widget, "family_locations_places", self.display_settings)
        return widget

    def _create_family_checkins_block(self):
        """Create family check-ins block."""
        line_h = self.display_settings.font_sizes["body"] + 4
        if self.location_service:
            result = self.location_service.get_checkins()
            if result.success and result.data:

                checkins_text = []
                for checkin in result.data:
                    contact_name = checkin.get("contact_name", "Unknown")
                    location = checkin.get("location_name", None)

                    if not location:
                        lat = checkin.get("latitude")
                        lon = checkin.get("longitude")
                        location = (
                            f"{lat:.6f}, {lon:.6f}"
                            if lat is not None and lon is not None
                            else "Unknown location"
                        )

                    time_str = datetime.now().strftime("%H:%M")

                    lines = [f"• {contact_name}", f"  {location} at {time_str}"]
                    checkins_text.append("\n".join(lines))

                n_lines = (
                    sum(c.count("\n") + 1 for c in checkins_text)
                    + (len(checkins_text) - 1) * 2
                )
                text = "\n\n".join(checkins_text)
            else:
                n_lines = 2
                text = "No family check-ins yet"

        else:
            n_lines = 2
            text = "Location service not available"

        widget = DementiaLabel(
            display_settings=self.display_settings,
            font_size="body",
            text=text,
            shorten=False,
        )
        widget.size_hint_x = 0.5  # for columns
        widget.height = max(120, int(n_lines * line_h))
        apply_border(widget, "family_locations_checkins", self.display_settings)
        return widget

    def _create_family_future_map_block(self):
        """Create map container; MapView is added lazily on screen enter to avoid black screen in ScreenManager."""
        map_lat = (37.0056 + 37.139) / 2
        map_lon = (-113.503 + -113.599) / 2
        container = BoxLayout(size_hint_y=0.72)
        apply_border(container, "family_future_map", self.display_settings)
        container._map_params = {"lat": map_lat, "lon": map_lon, "zoom": 11}
        return container

    def create_family_locations_widget(self):
        """Create family location check-in widget; arranges title, possible places, and check-ins."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        family = DementiaWidget(
            display_settings=self.display_settings, orientation="vertical"
        )
        apply_border(family, "family_locations", self.display_settings)
        family.add_widget(self._create_family_locations_title())

        columns_row = BoxLayout(orientation="horizontal", size_hint_y=0.28)
        columns_row.add_widget(self._create_family_possible_places_block())
        columns_row.add_widget(self._create_family_checkins_block())

        family.add_widget(columns_row)
        map_container = self._create_family_future_map_block()
        family.map_container = map_container
        family.add_widget(map_container)
        return family
