"""
Display settings for the TV app. Client gets settings from GET /api/settings and uses DisplaySettings.from_dict().
Defaults load from demo/demo_data/default_display_settings.json (single source).
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Any


def _default_display_settings_path() -> str:
    """Path to the single default display settings JSON (dev/demo/data/kiosk_settings.json)."""
    return os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "dev",
        "demo",
        "data",
        "kiosk_settings.json",
    )


@dataclass
class DisplaySettings:
    """User display preferences (fonts, colors, layout, etc.)."""

    font_sizes: Dict[str, int]
    colors: Dict[str, tuple]
    spacing: Dict[str, int]

    # Touch targets
    touch_targets: Dict[str, int]

    # Window settings
    window_width: int
    window_height: int

    # Clock settings
    clock_icon_size: int
    clock_icon_height: int
    clock_text_height: int
    clock_day_height: int
    clock_time_height: int
    clock_date_height: int
    clock_spacing: int
    clock_padding: list
    main_padding: list

    # Layout preferences
    home_layout: str  # 'horizontal' or 'vertical'
    clock_proportion: float
    todo_proportion: float

    # Accessibility settings
    high_contrast: bool
    large_text: bool
    reduced_motion: bool

    # Window position
    window_left: int
    window_top: int

    # Layout configuration
    med_events_split: float
    navigation_height: int
    button_flat_style: bool
    clock_background_color: tuple
    med_background_color: tuple
    events_background_color: tuple
    contacts_background_color: tuple
    medical_background_color: tuple
    calendar_background_color: tuple
    nav_background_color: tuple
    clock_orientation: str
    med_orientation: str
    events_orientation: str
    bottom_section_orientation: str

    # Navigation configuration
    navigation_buttons: list

    # Borders configuration (optional - dict of component_name -> {color, width})
    borders: Dict[str, Dict[str, Any]]

    @classmethod
    def default(cls) -> "DisplaySettings":
        """Load display defaults from default_display_settings.json; used when server has no settings for the user."""
        path = _default_display_settings_path()
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DisplaySettings":
        """Build from API/JSON dict (e.g. GET /api/settings or demo default_display_settings.json)."""
        colors = d.get("colors", {})
        return cls(
            font_sizes=d["font_sizes"],
            colors={k: tuple(v) for k, v in colors.items()},
            spacing=d["spacing"],
            touch_targets=d["touch_targets"],
            window_width=d["window_width"],
            window_height=d["window_height"],
            clock_icon_size=d["clock_icon_size"],
            clock_icon_height=d["clock_icon_height"],
            clock_text_height=d["clock_text_height"],
            clock_day_height=d["clock_day_height"],
            clock_time_height=d["clock_time_height"],
            clock_date_height=d["clock_date_height"],
            clock_spacing=d["clock_spacing"],
            clock_padding=d["clock_padding"],
            main_padding=d["main_padding"],
            home_layout=d["home_layout"],
            clock_proportion=d["clock_proportion"],
            todo_proportion=d["todo_proportion"],
            high_contrast=d["high_contrast"],
            large_text=d["large_text"],
            reduced_motion=d["reduced_motion"],
            window_left=d["window_left"],
            window_top=d["window_top"],
            med_events_split=d["med_events_split"],
            navigation_height=d["navigation_height"],
            button_flat_style=d["button_flat_style"],
            clock_background_color=tuple(d["clock_background_color"]),
            med_background_color=tuple(d["med_background_color"]),
            events_background_color=tuple(d["events_background_color"]),
            contacts_background_color=tuple(d["contacts_background_color"]),
            medical_background_color=tuple(d["medical_background_color"]),
            calendar_background_color=tuple(d["calendar_background_color"]),
            nav_background_color=tuple(d["nav_background_color"]),
            clock_orientation=d["clock_orientation"],
            med_orientation=d["med_orientation"],
            events_orientation=d["events_orientation"],
            bottom_section_orientation=d["bottom_section_orientation"],
            navigation_buttons=d["navigation_buttons"],
            borders=d.get("borders", {}),
        )
