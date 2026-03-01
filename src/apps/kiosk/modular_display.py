"""
Modular Display Components for Meridian Kiosk

Simple, reusable UI components that leverage Kivy's built-in capabilities.
Focus on dementia-friendly design with minimal complexity.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle


class DementiaWidget(BoxLayout):
    """Base widget with dementia-friendly defaults."""

    def __init__(self, display_settings, background_color=None, **kwargs):
        if "background_color" in kwargs:
            kwargs.pop("background_color")
        BoxLayout.__init__(self, **kwargs)

        self.display_settings = display_settings

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


class DementiaLabel(Label):
    """Configurable label with dementia-friendly defaults."""

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


class DementiaButton(Button):
    """Configurable button - all style parameters required from display_settings."""

    def __init__(
        self,
        display_settings,
        font_size,
        color,
        background_color,
        size_hint=(1, 1),
        **kwargs,
    ):
        Button.__init__(self, **kwargs)

        self.display_settings = display_settings

        # Use flat style if configured in display_settings
        if display_settings.button_flat_style:
            self.background_normal = ""
            self.background_down = ""

        # All properties from display_settings - no hardcoded values
        self.font_size = self.display_settings.font_sizes[font_size]
        self.color = self.display_settings.colors[color]
        self.background_color = self.display_settings.colors[background_color]
        self.size_hint = size_hint


class DementiaImage(Image):
    """Configurable image widget with dementia-friendly defaults."""

    def __init__(self, display_settings, size_hint=(1, 1), **kwargs):
        Image.__init__(self, **kwargs)

        self.display_settings = display_settings

        # Configurable properties with sensible defaults
        self.size_hint = size_hint


class DementiaScrollView(ScrollView):
    """Configurable ScrollView with dementia-friendly defaults."""

    def __init__(self, size_hint=(1, 1), bar_width=20, scroll_distance=100, **kwargs):
        ScrollView.__init__(self, **kwargs)

        # Configurable properties with sensible defaults
        self.size_hint = size_hint
        self.bar_width = bar_width
        self.scroll_distance = scroll_distance


class DementiaGridLayout(GridLayout):
    """Configurable GridLayout with dementia-friendly defaults."""

    def __init__(
        self, display_settings, spacing=None, padding=None, size_hint=(1, 1), **kwargs
    ):
        GridLayout.__init__(self, **kwargs)

        self.display_settings = display_settings

        # Configurable properties - use actual user settings
        self.spacing = spacing or display_settings.spacing["md"]
        self.padding = padding or display_settings.spacing["sm"]
        self.size_hint = size_hint


class ContentWidget(DementiaWidget):
    """Generic content widget that can hold any content."""

    def __init__(self, content=None, **kwargs):
        super().__init__(**kwargs)

        if content:
            self.add_widget(content)

    def set_content(self, widget):
        """Set the content widget."""
        self.clear_widgets()
        self.add_widget(widget)

    def add_content(self, widget):
        """Add content to the widget."""
        self.add_widget(widget)


class ListWidget(DementiaWidget):
    """Simple list widget using Kivy's built-in capabilities."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"

        # Create scrollable content - pass display_settings through
        self.scroll_view = DementiaScrollView()
        self.content_layout = DementiaWidget(
            display_settings=self.display_settings, orientation="vertical"
        )
        self.scroll_view.add_widget(self.content_layout)
        self.add_widget(self.scroll_view)

    def add_item(self, widget):
        """Add an item to the list."""
        self.content_layout.add_widget(widget)

    def clear_items(self):
        """Clear all items from the list."""
        self.content_layout.clear_widgets()


class GridWidget(DementiaWidget):
    """Simple grid widget using Kivy's GridLayout."""

    def __init__(self, cols=2, **kwargs):
        super().__init__(**kwargs)

        self.grid_layout = DementiaGridLayout(
            display_settings=self.display_settings, cols=cols
        )
        self.add_widget(self.grid_layout)

    def add_item(self, widget):
        """Add an item to the grid."""
        self.grid_layout.add_widget(widget)

    def clear_items(self):
        """Clear all items from the grid."""
        self.grid_layout.clear_widgets()


class SectionWidget(DementiaWidget):
    """Simple section widget with title and content."""

    def __init__(self, title="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"

        if title:
            # Use display_settings from parent (DementiaWidget)
            self.title_label = DementiaLabel(
                display_settings=self.display_settings, text=title
            )
            self.title_label.font_size = self.display_settings.font_sizes["title"]
            self.add_widget(self.title_label)

    def add_content(self, widget):
        """Add content to the section."""
        self.add_widget(widget)


class ActionWidget(DementiaWidget):
    """Simple action widget with buttons."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"

    def add_button(self, text, action=None):
        """Add a button to the action widget."""
        button = DementiaButton(text=text)
        if action:
            button.bind(on_press=action)
        self.add_widget(button)


class DementiaNavBar(DementiaWidget):
    """Generic navigation bar with configurable buttons."""

    def __init__(self, display_settings, screen_manager=None, buttons=None, **kwargs):
        super().__init__(
            display_settings=display_settings, orientation="horizontal", **kwargs
        )
        self.screen_manager = screen_manager
        self.size_hint = (1, None)
        self.height = display_settings.navigation_height if display_settings else 80

        # Use provided buttons or default empty list
        self.buttons = buttons or []

        # Create navigation buttons
        self._create_nav_buttons()

    def _create_nav_buttons(self):
        """Create navigation buttons from configuration."""
        if not self.buttons:
            print("WARNING: No nav buttons configured!")
            return

        # Calculate button width based on number of buttons
        button_width = 1.0 / len(self.buttons)

        for button_config in self.buttons:
            # Extract button configuration - all values required, no defaults
            if isinstance(button_config, dict):
                text = button_config["text"]
                screen_name = button_config["screen"]
                text_color = button_config["color"]
                background_color = button_config["background_color"]
                font_size = button_config["font_size"]
            else:
                continue  # Skip invalid button configurations

            btn = DementiaButton(
                display_settings=self.display_settings,
                text=text,
                font_size=font_size,
                color=text_color,
                background_color=background_color,
                size_hint=(button_width, None),
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
