"""
Modular Display Components for Meridian Kiosk

Simple, reusable UI components that leverage Kivy's built-in capabilities.
Focus on dementia-friendly design with minimal complexity.
Design tokens live here; widget-specific values live in widgets.py.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle



class KioskWidget(BoxLayout):
    """Base widget with dementia-friendly defaults."""

    def __init__(self, background_color=None, **kwargs):
        defaults = {
            "size_hint": (1, 1),
            "padding": 16,
            "spacing": 16,
            "orientation": "vertical",
        }
        defaults.update(kwargs)
        background_color = defaults.pop("background_color", background_color)
        BoxLayout.__init__(self, **defaults)

        self._setup_background(background_color)
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _setup_background(self, custom_color=None):
        """Setup background with dementia-friendly colors."""
        with self.canvas.before:
            if custom_color:
                Color(*custom_color)
            else:
                Color(0.95, 0.95, 0.93, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)

    def _update_bg(self, instance, value):
        """Update background when widget size/position changes."""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class KioskLabel(Label):
    """Text display widget with dementia-friendly defaults. type='header'|'subheader'|'body'|'hero'|'caption'|'button' for presets."""

    def __init__(self, type=None, **kwargs):

        # Only add overrides that differ from Kivy Label defaults (halign=left, valign=bottom)
        LABEL_TYPES = {
            "header": {"font_size": 56, "color": (0.1, 0.1, 0.1, 1), "valign": "middle"},
            "subheader": {"font_size": 48, "color": (0.1, 0.1, 0.1, 1), "valign": "middle"},
            "body": {"font_size": 32, "color": (0.1, 0.1, 0.1, 1), "valign": "top"},
            "hero": {"font_size": 96, "color": (0.1, 0.1, 0.1, 1), "halign": "center", "valign": "middle"},
            "caption": {"font_size": 32, "color": (0.55, 0.55, 0.55, 1), "halign": "center", "valign": "middle"},
            "button": {"font_size": 56, "color": (0.1, 0.1, 0.1, 1), "halign": "center", "valign": "middle"},
        }
        defaults = dict(LABEL_TYPES.get(type, LABEL_TYPES["body"]))
        defaults.update(kwargs)
        Label.__init__(self, **defaults)

        def _update_text_size(widget, *args):
            widget.text_size = widget.size

        self.bind(size=_update_text_size)
        _update_text_size(self)


class KioskButton(Button):
    """Button with hardcoded standard style. Override via kwargs."""

    def __init__(self, **kwargs):
        defaults = {
            "font_size": 56,
            "color": (0.1, 0.1, 0.1, 1),
            "background_color": (0.4, 0.6, 0.85, 1),
            "background_normal": "",
            "background_down": "",
            "size_hint": (1, 1),
        }
        defaults.update(kwargs)
        Button.__init__(self, **defaults)
