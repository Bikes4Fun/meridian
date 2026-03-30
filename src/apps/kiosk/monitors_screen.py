"""Reusable monitor / sensor reading fragments for embedding on any screen."""

import html

from . import html_primitives as hp


def build_monitors_section_html(section_title: str, inner_html: str) -> str:
    """Subheading plus inner content (e.g. one or more reading rows)."""
    return hp.kiosk_subheader(section_title) + hp.spacer(12) + inner_html


def build_monitor_reading_row_html(
    label: str,
    value_element_id: str,
    *,
    initial_value: str = "—",
    action_button_text: str | None = None,
    action_onclick_js: str | None = None,
    row_class: str = "temp-widget-row",
) -> str:
    """Single reading line: label, live value span (id for updateEl), optional small action button."""
    id_attr = html.escape(str(value_element_id), quote=True)
    val = html.escape(str(initial_value))
    lbl = html.escape(str(label))
    cls = html.escape(str(row_class), quote=True)
    inner = f'<div class="temp-widget">{lbl} <span id="{id_attr}">{val}</span></div>'
    btn = ""
    if action_button_text and action_onclick_js:
        btn = hp.kiosk_button(action_button_text, action_onclick_js, small=True)
    return f'<div class="{cls}">{inner}{btn}</div>'
