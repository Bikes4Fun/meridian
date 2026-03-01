"""
Modular Display Components for Meridian Kiosk

Simple, reusable UI components that leverage Kivy's built-in capabilities.
Focus on dementia-friendly design with minimal complexity.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle


class KioskWidget(BoxLayout):
    """Base widget with dementia-friendly defaults."""

    def __init__(self, display_settings, background_color=None, **kwargs):
        if "background_color" in kwargs:
            kwargs.pop("background_color")
        self.display_settings = display_settings
        BoxLayout.__init__(self, **kwargs)

        # Dementia-friendly defaults using user settings
        self.size_hint = (1, 1)
        self.padding = self.display_settings.spacing["lg"]
        self.spacing = self.display_settings.spacing["md"]

        # Setup background with custom color if provided
        self._setup_background(background_color)
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _setup_background(self, custom_color=None):
        """Setup background with dementia-friendly colors."""
        with self.canvas.before:
            # Use custom color if provided, otherwise use default from settings
            if custom_color:
                Color(*custom_color)
            else:
                Color(*self.display_settings.colors["surface"])
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)

    def _update_bg(self, instance, value):
        """Update background when widget size/position changes."""
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class KioskLabel(Label):
    """Text display widget with dementia-friendly defaults. Named after Kivy's Label (static text);
    font_size/color/align come from display_settings for consistency."""

    def __init__(
        self,
        display_settings,
        font_size="large",
        color="text",
        halign="center",
        valign="middle",
        **kwargs,
    ):
        Label.__init__(self, **kwargs)

        self.display_settings = display_settings

        # Configurable properties with sensible defaults
        self.font_size = self.display_settings.font_sizes[font_size]
        self.color = self.display_settings.colors[color]
        self.halign = halign
        self.valign = valign
        self.text_size = self.size
        self.bind(size=self._update_text_size)

    def _update_text_size(self, instance, value):
        """Update text size when widget size changes."""
        self.text_size = self.size


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

    def __init__(self, display_settings, screen_manager=None, buttons=None, **kwargs):
        super().__init__(
            display_settings=display_settings, orientation="horizontal", **kwargs
        )
        self.screen_manager = screen_manager
        self.size_hint = (1, None)
        self.height = 90

        # Use provided buttons or default empty list
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
