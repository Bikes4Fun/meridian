"""
Widget creation logic for Meridian Kiosk.
Handles the creation of individual UI widgets.
"""

from .modular_display import (
    KioskWidget,
    KioskLabel,
    KioskButton,
)

# Top section: Day + Time of day (left) | Icon (right)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


def _format_contacts_for_display(contacts, include_header=True):
    """Format contact dicts into display text. Used by widgets."""
    if not contacts:
        return "No emergency contacts found"
    lines = ["Emergency Contacts:"] if include_header else []
    for c in contacts:
        phone = c.get("phone") or ""
        rel = c.get("relationship") or ""
        lines.append(f"• {c.get('display_name', '')} - {phone}\n  {rel}")
    return "\n".join(lines)


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
            "emergency_profile",
            "family_locations",
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
            "emergency_profile": True,
            "family_locations": True,
        }

    def create_widgets_for_screen(self, screen_type):
        """Create all widgets needed for a specific screen type."""
        screen_widgets = {
            "home": ["clock", "medication", "events"],
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

        clock = KioskWidget(
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

        day_label = KioskLabel(
            font_size="title", text="", display_settings=display_settings
        )
        day_label.color = text_color
        day_label.halign = "left"
        day_label.valign = "middle"
        day_label.size_hint = (1, 0.5)
        apply_border(day_label, "clock_day_label", display_settings)
        left_stack.add_widget(day_label)

        time_of_day_label = KioskLabel(
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
        time_label = KioskLabel(
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

        date_label = KioskLabel(
            font_size="large", text="", display_settings=display_settings
        )
        date_label.color = text_color
        date_label.halign = "left"
        date_label.valign = "middle"
        date_label.size_hint = (0.6, 1)
        apply_border(date_label, "clock_date_label", display_settings)
        bottom_section.add_widget(date_label)

        year_label = KioskLabel(
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
        """Get the appropriate icon for the time of day. Returns None if file not found."""
        _kiosk_dir = os.path.dirname(os.path.abspath(__file__))
        icon_map = {
            "Morning": os.path.join(_kiosk_dir, "icons", "sunrise.png"),
            "Noon": os.path.join(_kiosk_dir, "icons", "noon.png"),
            "Afternoon": os.path.join(_kiosk_dir, "icons", "noon.png"),  # Use noon for afternoon
            "Evening": os.path.join(_kiosk_dir, "icons", "evening.png"),
            "Night": os.path.join(_kiosk_dir, "icons", "night.png"),
        }
        path = icon_map.get(time_of_day)
        if path and os.path.exists(path):
            return path
        return ""

    def create_medication_widget(self):
        """Create medication widget using modular components."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        # Use actual user settings - no hardcoded defaults
        med = KioskWidget(
            display_settings=display_settings,
            orientation=display_settings.med_orientation,
            background_color=display_settings.med_background_color,
        )

        # Title - much larger
        title = KioskLabel(
            display_settings=display_settings, font_size="title", text="Medications"
        )
        med.add_widget(title)

        # Medication content
        med_content = KioskLabel(
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
        events = KioskWidget(
            display_settings=display_settings,
            orientation=display_settings.events_orientation,
            background_color=display_settings.events_background_color,
        )

        # Title
        title = KioskLabel(
            display_settings=display_settings, font_size="title", text="Today's Events"
        )
        events.add_widget(title)

        # Events content
        events_content = KioskLabel(
            display_settings=display_settings,
            font_size="body",
            text="Loading events...",
        )
        events.add_widget(events_content)
        events.events_content = events_content

        return events

    def create_emergency_profile_widget(self):
        """Create emergency profile: patient name, DNR, contacts, meds, allergies, proxy, POA.
        Light background, dark text for vision-impaired; flashing border for visibility."""
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        dark_text = (0.1, 0.1, 0.1, 1)
        profile = KioskWidget(
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
                care_recipient_user_id = d.get("care_recipient_user_id")

                name_section = BoxLayout(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(60),
                    spacing=display_settings.spacing["md"],
                )
                photo_cell = BoxLayout(size_hint_x=None, width=dp(60))
                with photo_cell.canvas.before:
                    Color(0.8, 0.8, 0.8, 1)
                    photo_cell._bg = Rectangle(pos=photo_cell.pos, size=photo_cell.size)
                photo_cell.bind(pos=lambda w, v: setattr(w._bg, "pos", w.pos), size=lambda w, v: setattr(w._bg, "size", w.size))
                photo_img = Image(size_hint=(1, 1), fit_mode="contain")
                if care_recipient_user_id and self.location_service and hasattr(self.location_service, "fetch_photo_to_cache"):
                    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
                    def _set_photo(dt):
                        path = self.location_service.fetch_photo_to_cache(care_recipient_user_id, cache_dir)
                        if path and os.path.exists(path):
                            photo_img.source = path
                    Clock.schedule_once(_set_photo, 0.1)
                photo_cell.add_widget(photo_img)
                name_section.add_widget(photo_cell)
                name_label = KioskLabel(
                    display_settings=display_settings,
                    font_size="huge",
                    text=profile_data.get("name") or "Patient",
                    color="text",
                )
                name_label.color = dark_text
                name_section.add_widget(name_label)
                apply_border(name_section, "emergency_profile_name", display_settings)
                profile.add_widget(name_section)

                dnr = medical.get("dnr", False)
                dnr_label = KioskLabel(
                    display_settings=display_settings,
                    font_size="huge",
                    text="DNR" if dnr else "FULL CODE",
                    color="text",
                )
                dnr_label.color = (0.8, 0.2, 0.2, 1) if dnr else (0.2, 0.6, 0.2, 1)
                apply_border(dnr_label, "emergency_profile_dnr", display_settings)
                profile.add_widget(dnr_label)

                if self.emergency_service:
                    ms_result = self.emergency_service.get_medical_summary()
                    if ms_result.success and ms_result.data:
                        ms_label = KioskLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=ms_result.data,
                            color="text",
                        )
                        ms_label.color = dark_text
                        apply_border(ms_label, "emergency_profile_medical", display_settings)
                        profile.add_widget(ms_label)

                if medical.get("conditions"):
                    cond_label = KioskLabel(
                        display_settings=display_settings,
                        font_size="title",
                        text=f"Diagnosis: {medical['conditions']}",
                        color="text",
                    )
                    cond_label.color = dark_text
                    apply_border(cond_label, "emergency_profile_conditions", display_settings)
                    profile.add_widget(cond_label)

                if self.emergency_service:
                    ec_result = self.emergency_service.get_emergency_contacts()
                    if ec_result.success and ec_result.data:
                        ec_block = BoxLayout(orientation="vertical")
                        ec_label = KioskLabel(
                            display_settings=display_settings,
                            font_size="title",
                            text="Emergency contacts",
                            color="text",
                        )
                        ec_label.color = dark_text
                        ec_block.add_widget(ec_label)
                        ec_list = KioskLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=_format_contacts_for_display(ec_result.data, include_header=False),
                            color="text",
                        )
                        ec_list.color = dark_text
                        ec_block.add_widget(ec_list)
                        apply_border(ec_block, "emergency_contacts", display_settings)
                        profile.add_widget(ec_block)

                if proxy.get("name") or d.get("medical_proxy_phone"):
                    proxy_text = f"Medical Proxy: {proxy.get('name', '')} {d.get('medical_proxy_phone', '')}".strip()
                    if proxy_text:
                        p_label = KioskLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=proxy_text,
                            color="text",
                        )
                        p_label.color = dark_text
                        apply_border(p_label, "emergency_profile_proxy", display_settings)
                        profile.add_widget(p_label)

                if d.get("poa_name") or d.get("poa_phone"):
                    poa_text = (
                        f"POA: {d.get('poa_name', '')} {d.get('poa_phone', '')}".strip()
                    )
                    if poa_text:
                        poa_label = KioskLabel(
                            display_settings=display_settings,
                            font_size="large",
                            text=poa_text,
                            color="text",
                        )
                        poa_label.color = dark_text
                        apply_border(poa_label, "emergency_profile_poa", display_settings)
                        profile.add_widget(poa_label)
            else:
                err_label = KioskLabel(
                    display_settings=display_settings,
                    font_size="title",
                    text="Emergency profile not found",
                    color="text",
                )
                err_label.color = dark_text
                profile.add_widget(err_label)
        else:
            err_label = KioskLabel(
                display_settings=display_settings,
                font_size="title",
                text="Emergency profile service not available",
                color="text",
            )
            err_label.color = dark_text
            profile.add_widget(err_label)

        return profile

    def _create_family_locations_title(self):
        """Create Family Locations screen title block."""
        title = KioskLabel(
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
        widget = KioskLabel(
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

        widget = KioskLabel(
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
        family = KioskWidget(
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
