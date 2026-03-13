"""
Kiosk UI primitives: base styled components.
KioskWidget, KioskLabel, KioskButton, apply_debug_border.
Design tokens live here; composites in widgets.py.
"""

from kivy.graphics import Color, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button


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


def apply_debug_border(widget, **kwargs):
    """Apply default border to widget."""
    b = {"color": [0, 0, 0, 1], "width": 1}
    b.update(kwargs)

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


class KioskLabel(Label):
    """Text display widget with dementia-friendly defaults. type='header'|'subheader'|'body'|'hero'|'caption'|'button' for presets."""

    _TYPES = {
        "header": {
            "font_size": 56,
            "color": (0.1, 0.1, 0.1, 1),
            "valign": "middle",
        },
        "subheader": {
            "font_size": 48,
            "color": (0.1, 0.1, 0.1, 1),
            "valign": "middle",
        },
        "body": {"font_size": 32, "color": (0.1, 0.1, 0.1, 1), "valign": "top"},
        "hero": {
            "font_size": 96,
            "color": (0.1, 0.1, 0.1, 1),
            "halign": "center",
            "valign": "middle",
        },
        "caption": {
            "font_size": 32,
            "color": (0.55, 0.55, 0.55, 1),
            "halign": "center",
            "valign": "middle",
        },
        "button": {
            "font_size": 56,
            "color": (0.1, 0.1, 0.1, 1),
            "halign": "center",
            "valign": "middle",
        },
    }

    def __init__(self, type=None, **kwargs):
        # Only add overrides that differ from Kivy Label defaults (halign=left, valign=bottom)
        defaults = dict(self._TYPES.get(type, self._TYPES["body"]))
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

class KioskNavBar(KioskWidget):
    """Generic navigation bar with configurable buttons."""

    def __init__(self, screen_manager=None, buttons=None, **kwargs):
        defaults = {
            "orientation": "horizontal",
            "size_hint": (1, None),
            "height": 90,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.screen_manager = screen_manager
        self.buttons = buttons or []

        # Create navigation buttons
        self._create_nav_buttons()

    def _create_nav_buttons(self):
        """Create navigation buttons from configuration."""
        if not self.buttons:
            print("WARNING: No nav buttons configured!")
            return

        nav_button_width = 1.0 / len(self.buttons)

        for button_config in self.buttons:
            if isinstance(button_config, dict):
                text = button_config["text"]
                screen_name = button_config["screen"]
            else:
                continue

            btn = KioskButton(
                text=text,
                size_hint=(nav_button_width, None),
                height=self.height,
            )

            # Create proper closures for all callbacks to avoid reference issues
            def make_press_handler(btn_text, btn_screen):
                def press_handler(instance):
                    # print(f"on_press FIRED for button '{btn_text}' -> screen '{btn_screen}'")
                    self._navigate_to_screen(btn_screen)

                return press_handler

            btn.bind(on_press=make_press_handler(text, screen_name))
            self.add_widget(btn)

    def _navigate_to_screen(self, screen_name):
        """Navigate to specified screen."""
        if self.screen_manager:
            self.screen_manager.current = screen_name
        else:
            print(
                f"ERROR: Cannot navigate to '{screen_name}' - screen_manager is None!"
            )
