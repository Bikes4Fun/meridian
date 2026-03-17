"""
Whole-system, template-level HTML primitives for pywebview kiosk.
Aligns with info/meridian-design-system-2.md (Typography Scale, TV Kiosk Design Specs, Components).
Design tokens (background, colors, typography scale) live in kiosk.html CSS.

Screen-specific helpers (form_row, section_bar) live in emergency_screen.

Used across screens:
- nav_html: every screen (uses data-screen; kiosk.html has delegated click listener)
- typography: kiosk_hero, kiosk_header, kiosk_subheader, kiosk_body_large, kiosk_body, kiosk_caption
- loading_state, empty_state, error_state: every screen
- panel, two_column_row, spacer: layout
- kiosk_button: Emergency (Print), any primary action
- contact_tile, avatar_img: person/contact display
"""

import html
import json


def nav_html(buttons):
    """Navigation bar: row of buttons with data-screen. kiosk.html delegates clicks to pywebview.api.navigate(screen).
    buttons: [{"text": "Home", "screen": "home"}, ...]. Uses data-screen to avoid onclick escaping issues."""
    parts = []
    for b in buttons:
        text = html.escape(str(b.get("text", "")))
        screen = html.escape(str(b.get("screen", "")))
        parts.append(f'<button class="nav-tab" data-screen="{screen}">{text}</button>')
    return f'<nav id="kiosk-nav">{"".join(parts)}</nav>'


def loading_state(label="Loading..."):
    """Loading placeholder. Design: Status Indicators—never color alone. Used by every screen."""
    return f'<div class="state-placeholder state-loading">{html.escape(str(label))}</div>'


def empty_state(message):
    """Empty state. Design: Status Indicators—text label. "No events today", "No medications", etc."""
    return f'<div class="state-placeholder state-empty">{html.escape(str(message))}</div>'


def error_state(message):
    """Error/fallback state. Design: Status Indicators—icon + text. Used when fetch fails."""
    return f'<div class="state-placeholder state-error">{html.escape(str(message))}</div>'


def _wrap_typed(text, class_name, id_=None):
    """Escape text and wrap in div; optional id for updateEl targets."""
    id_attr = f' id="{html.escape(id_)}"' if id_ else ""
    return f'<div class="{class_name}"{id_attr}>{html.escape(str(text))}</div>'


def kiosk_hero(text, id_=None):
    """Display text (72px/700). Design: Typography Scale. Used by: Home (clock time). id_ for updateEl."""
    return _wrap_typed(text, "kiosk-hero", id_)


def kiosk_header(text, id_=None):
    """Heading 1 (56px/700). Design: Typography Scale. Used by: Home, Checkin, Chat, Emergency. id_ for updateEl."""
    return _wrap_typed(text, "kiosk-header", id_)


def kiosk_subheader(text, id_=None):
    """Heading 2 (40px/700). Design: Typography Scale. Used by: Home (time-of-day), Emergency section bars."""
    return _wrap_typed(text, "kiosk-subheader", id_)


def kiosk_body_large(text, id_=None):
    """Body Large (32px/400). Design: Typography Scale. Used by: Emergency form values, prominent content."""
    return _wrap_typed(text, "kiosk-body-large", id_)


def kiosk_body(text, id_=None):
    """Body (28px/400). Design: Typography Scale. Used by: meds, events, contact names."""
    return _wrap_typed(text, "kiosk-body", id_)


def kiosk_caption(text, id_=None):
    """Caption (24px/400). Design: Typography Scale, min 24px. Used by: form labels, metadata."""
    return _wrap_typed(text, "kiosk-caption", id_)


def panel(inner_html, class_name=""):
    """Container. Design: safe margins 40-48px, padding 16-24px. class_name: med-panel, events-panel, etc."""
    cls = f' {html.escape(class_name)}' if class_name else ""
    return f'<div class="kiosk-panel{cls}">{inner_html}</div>'


def two_column_row(left_html, right_html, left_pct=50):
    """50/50 horizontal split (or left_pct). Design: gap 24px; use calc to avoid overflow."""
    right_pct = 100 - left_pct
    return f'<div class="two-column-row"><div class="col-left" style="flex:0 0 calc({left_pct}% - 12px)">{left_html}</div><div class="col-right" style="flex:0 0 calc({right_pct}% - 12px)">{right_html}</div></div>'


def spacer(size=32):
    """Vertical gap. Design: 32-48px between major elements. Use for consistent spacing."""
    return f'<div class="spacer" style="height:{int(size)}px"></div>'


def avatar_img(api_base, user_id, alt=""):
    """Circle avatar alone. Design: 128px circular. Used by: Emergency, Family; contact_tile uses this. Hides on error."""
    if not api_base or not user_id:
        return ""
    photo_url = f"{api_base.rstrip('/')}/api/users/{user_id}/photo"
    alt_escaped = html.escape(str(alt))
    return f'<img src="{html.escape(photo_url)}" onerror="this.style.display=\'none\'" class="avatar" alt="{alt_escaped}">'


def kiosk_button(text, onclick_js):
    """Primary button. Design: 160×160px min, text 24px min, rounded 12-16px. Used by: Emergency (Print).
    onclick_js is Python-generated (e.g. pywebview.api.print_emergency()) — do not html.escape it."""
    return f'<button class="kiosk-button" onclick="{onclick_js}">{html.escape(str(text))}</button>'


def contact_tile(api_base, name, user_id, onclick_js=None, relationship="", data_sb_uid="", data_name=""):
    """Person/contact card. Uses data-sb-uid/data-name for chat (delegated handler) when provided; else onclick_js."""
    initial = (name or "?")[0].upper()
    name_escaped = html.escape(str(name or "Contact"))
    img_tag = avatar_img(api_base, user_id, name)
    rel_part = f'<div class="contact-relationship">{html.escape(str(relationship))}</div>' if relationship else ""
    avatar_block = f'<div class="avatar-wrapper"><div class="contact-initial">{html.escape(initial)}</div>{img_tag}</div>'
    if data_sb_uid or data_name:
        sb = f' data-sb-uid="{html.escape(str(data_sb_uid))}"' if data_sb_uid else ""
        nm = f' data-name="{html.escape(str(data_name))}"' if data_name else ""
        return f'<div class="contact-tile" role="button"{sb}{nm}>{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'
    return f'<div class="contact-tile" onclick="{onclick_js}">{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'
