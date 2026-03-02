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

    def add_button(self, text, screen_name, color="primary", font_size="large"):
        """Add a button to the navigation bar dynamically."""
        button_config = {
            "text": text,
            "screen": screen_name,
            "color": color,
            "font_size": font_size,
        }
        self.buttons.append(button_config)

        # Recreate buttons
        self.clear_widgets()
        self._create_nav_buttons()

    def remove_button(self, screen_name):
        """Remove a button from the navigation bar."""
        self.buttons = [
            btn
            for btn in self.buttons
            if (isinstance(btn, dict) and btn.get("screen") != screen_name)
            or (isinstance(btn, tuple) and len(btn) > 1 and btn[1] != screen_name)
        ]

        # Recreate buttons
        self.clear_widgets()
        self._create_nav_buttons()
