# Calendar screen - for later reference

Removed from kiosk to simplify. Restore when adding calendar back.

## app.py (MeridianKioskApp.build)
```python
        calendar_screen = self.screen_factory.create_calendar_screen()
        self.screen_manager.add_widget(calendar_screen)
```

## screens.py (ScreenFactory.create_calendar_screen)
```python
    def create_calendar_screen(self):
        """Create calendar screen using modular components."""
        screen = Screen(name="calendar")

        main_layout = BoxLayout(orientation="vertical")
        main_layout.size_hint = (1, 1)
        main_layout.padding = self.display_settings.main_padding

        nav_widget = self._create_navigation()
        main_layout.add_widget(nav_widget)

        content_layout = BoxLayout(orientation="horizontal")
        content_layout.size_hint = (1, 1)

        calendar_widget = self.widget_factory.create_widget("calendar")
        calendar_widget.size_hint = (0.67, 1)
        content_layout.add_widget(calendar_widget)

        today_widget = self.widget_factory.create_widget("today_events")
        today_widget.size_hint = (0.33, 1)
        content_layout.add_widget(today_widget)

        self.widget_factory.today_events_widget = today_widget

        main_layout.add_widget(content_layout)
        screen.add_widget(main_layout)

        return screen
```

## widgets.py

### create_calendar_widget + create_today_events_widget + _on_date_select
(Full methods - see git history. Summary: calendar grid with day buttons, today_events panel, click handler that updates events for selected day.)

### Also remove from widgets.py:
- widget_creators: "calendar" and "today_events"
- get_available_widgets: "calendar" and "today_events"
- get_user_widget_preferences: "calendar" and "today_events"
- screen_widgets "calendar": ["calendar", "today_events"]

## kiosk_settings.json
- navigation_buttons: remove Calendar entry (or filter in _create_navigation as done)
- calendar_background_color: kept for seed/settings compatibility; unused until calendar restored


def create_calendar_widget(self):
        """Create interactive calendar widget using modular components."""
        logger.debug(
            f"[CALENDAR] create_calendar_widget called, calendar_service={self.calendar_service 
            is not None}"
        )
        if not self.display_settings:
            raise ValueError("display_settings must be provided to WidgetFactory")
        display_settings = self.display_settings

        calendar = KioskWidget(
            display_settings=display_settings,
            orientation="vertical",
            background_color=display_settings.calendar_background_color,
        )
        apply_border(calendar, "calendar", display_settings)

        # Calendar title
        title = KioskLabel(
            display_settings=display_settings, font_size="title", text="Calendar"
        )
        calendar.add_widget(title)

        # Calendar grid container (no padding so buttons can receive touches)
        calendar_grid = KioskWidget(
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
                header_row = KioskWidget(
                    display_settings=display_settings, orientation="horizontal"
                )
                header_row.size_hint = (1, None)
                header_row.height = 50
                header_row.padding = 0
                header_row.spacing = 2

                for day in days:
                    header_btn = KioskButton(
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
                    week_row = KioskWidget(
                        display_settings=display_settings, orientation="horizontal"
                    )
                    week_row.size_hint = (1, None)
                    week_row.height = 50
                    week_row.padding = 0
                    week_row.spacing = 2

                    for day in week:
                        if day == 0:
                            # Empty day
                            empty_btn = KioskButton(
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
                            day_btn = KioskButton(
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
                error_content = KioskLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="Error loading calendar",
                )
                calendar.add_widget(error_content)
        else:
            error_content = KioskLabel(
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

        events = KioskWidget(
            display_settings=display_settings, orientation="vertical"
        )
        apply_border(events, "today_events", display_settings)

        # Events title
        title = KioskLabel(
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
                events_content = KioskLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="\n".join(events_text),
                )
            else:
                events_content = KioskLabel(
                    display_settings=display_settings,
                    font_size="body",
                    text="No events today",
                )
        else:
            events_content = KioskLabel(
                display_settings=display_settings,
                font_size="body",
                text="Calendar service not available",
            )

        events.add_widget(events_content)

        # Store reference for updates from calendar clicks
        events.events_content = events_content
        return ev


        def _on_date_select(
        self, day_num, clicked_btn, day_buttons, current_date, display_settings
    ):
        """Handle date selection in calendar."""
        logger.debug(f"Calendar day clicked: day_num={day_num}")
        logger.debug(
            f"calendar_service={self.calendar_service is not None}, has today_events_widget=
            {hasattr(self, 'today_events_widget')}"
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
                f"Events for day {day_num}: success={result.success}, count={len(result.data) if 
                result.data else 0}"
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
