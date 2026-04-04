"""
Kiosk markup primitives: nav, typography wrappers, loading/empty/error, layout, kiosk_button, contact/avatar snippets.

Scope: reusable HTML string builders only; design tokens live in kiosk CSS. Aligns with the kiosk/TV typography spec in-repo docs.

Not here: fetching services, per-screen composition (see *\_screen.py), labeled form rows / section bars (emergency_screen), or webapp assets.
"""

import html
import json


def nav_html(buttons):
    """Navigation bar: row of buttons with data-screen. kiosk.html delegates clicks to pywebview.api.navigate(screen).
    buttons: [{"text": "Home", "screen": "home"}, ...]. Uses data-screen to avoid onclick escaping issues.
    """
    parts = []
    for b in buttons:
        text = html.escape(str(b.get("text", "")))
        screen = html.escape(str(b.get("screen", "")))
        parts.append(f'<button class="nav-tab" data-screen="{screen}">{text}</button>')
    return f'<nav id="kiosk-nav">{"".join(parts)}</nav>'


def loading_state(label="Loading..."):
    """Loading placeholder. Design: Status Indicators—never color alone. Used by every screen."""
    return (
        f'<div class="state-placeholder state-loading">{html.escape(str(label))}</div>'
    )


def empty_state(message):
    """Empty state. Design: Status Indicators—text label. "No events today", "No medications", etc."""
    return (
        f'<div class="state-placeholder state-empty">{html.escape(str(message))}</div>'
    )


def error_state(message):
    """Error/fallback state. Design: Status Indicators—icon + text. Used when fetch fails."""
    return (
        f'<div class="state-placeholder state-error">{html.escape(str(message))}</div>'
    )


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
    cls = f" {html.escape(class_name)}" if class_name else ""
    return f'<div class="kiosk-panel{cls}">{inner_html}</div>'


def two_column_row(left_html, right_html, left_pct=50):
    """50/50 horizontal split (or left_pct). Design: gap 24px; use calc to avoid overflow."""
    right_pct = 100 - left_pct
    return f'<div class="two-column-row"><div class="col-left" style="flex:0 0 calc({left_pct}% - 12px)">{left_html}</div><div class="col-right" style="flex:0 0 calc({right_pct}% - 12px)">{right_html}</div></div>'


def spacer(size=32):
    """Vertical gap. Design: 32-48px between major elements. Use for consistent spacing."""
    return f'<div class="spacer" style="height:{int(size)}px"></div>'


def avatar_img(avatar_src, alt=""):
    """Circle avatar alone. Design: 128px circular. avatar_src = data URI (from fetch_photo_b64) or None/empty for fallback only."""
    if not avatar_src:
        return ""
    alt_escaped = html.escape(str(alt))
    src_escaped = html.escape(avatar_src)
    return f'<img src="{src_escaped}" class="avatar" alt="{alt_escaped}">'


def kiosk_button(text, onclick_js, no_feedback=False, small=False):
    """Primary button. Design: 160×160px min, text 24px min, rounded 12-16px. Used by: Emergency (Print).
    Standard: press feedback (scale + darker color). no_feedback=True disables it. small=True: compact, no min size.
    onclick_js is Python-generated (e.g. pywebview.api.print_emergency()) — do not html.escape it.
    """
    parts = ["kiosk-button", "btn-small" if small else "btn-large"]
    if no_feedback:
        parts.append("kiosk-button--no-feedback")
    if small:
        parts.append("kiosk-button--small")
    cls = " ".join(parts)
    return f'<button class="{cls}" onclick="{onclick_js}">{html.escape(str(text))}</button>'


def contact_tile(
    avatar_src, name, onclick_js=None, relationship="", data_sb_uid="", data_name=""
):
    """Person/contact card. avatar_src = data URI from fetch_photo_b64. Uses data-sb-uid/data-name for chat when provided."""
    initial = (name or "?")[0].upper()
    name_escaped = html.escape(str(name or "Contact"))
    img_tag = avatar_img(avatar_src, name)
    rel_part = (
        f'<div class="contact-relationship">{html.escape(str(relationship))}</div>'
        if relationship
        else ""
    )
    avatar_block = f'<div class="avatar-wrapper"><div class="contact-initial">{html.escape(initial)}</div>{img_tag}</div>'
    if data_sb_uid or data_name:
        sb = f' data-sb-uid="{html.escape(str(data_sb_uid))}"' if data_sb_uid else ""
        nm = f' data-name="{html.escape(str(data_name))}"' if data_name else ""
        return f'<div class="contact-tile" role="button"{sb}{nm}>{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'
    return f'<div class="contact-tile" onclick="{onclick_js}">{avatar_block}<div class="contact-name">{name_escaped}</div>{rel_part}</div>'
