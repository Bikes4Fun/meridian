"""
Emergency layout widget: form-style layout (IN CASE OF EMERGENCY, PERSONAL INFORMATION, MEDICAL EMERGENCY CONTACTS).
Used by WidgetFactory.create_emergency_layout_widget().
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock

from .modular_display import KioskWidget, KioskLabel


def _form_section_bar(title, bar_color=(1,1,1,1), height=dp(44)):
    """Form-style section header: colored bar with white text."""
    bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=height, padding=[dp(12), 0])
    with bar.canvas.before:
        Color(*bar_color)
        bar._bg = Rectangle(pos=bar.pos, size=bar.size)
    bar.bind(pos=lambda w, v: setattr(w._bg, "pos", w.pos), size=lambda w, v: setattr(w._bg, "size", w.size))
    lbl = KioskLabel(type="header", text=title, font_size=dp(36))
    lbl.color = (1, 1, 1, 1)
    bar.add_widget(lbl)
    return bar


def _form_row(label_text, value_text, dark_text=(0.1, 0.1, 0.1, 1)):
    """One labeled row: LABEL  value."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    lbl = KioskLabel(type="caption", text=label_text + ":", font_size=dp(28))
    lbl.color = dark_text
    lbl.size_hint_x = None
    lbl.width = dp(220)
    row.add_widget(lbl)
    val = KioskLabel(type="body", text=value_text or "—", font_size=dp(28))
    val.color = dark_text
    row.add_widget(val)
    return row

def attach_emergency_border(widget, services):
    """Draw an orange border on the widget; flash when alert is activated. Call once after layout is built."""
    alert_ref = services.get("_alert_activated", [False])
    flash_state = [0]

    def border_color():
        if alert_ref[0]:
            return (1, 0.3, 0.1, 1) if flash_state[0] else (1, 0.5, 0, 1)
        return (0.9, 0.4, 0.1, 1)

    def redraw(*_):
        widget.canvas.after.clear()
        with widget.canvas.after:
            Color(*border_color())
            Line(rectangle=(widget.x, widget.y, widget.width, widget.height), width=8)

    def tick(dt):
        flash_state[0] = 1 - flash_state[0]
        redraw()

    widget.bind(pos=redraw, size=redraw)
    Clock.schedule_interval(tick, 0.5)
    redraw()


def create_emergency_layout_widget(layout, e_data, e_contacts, services):
    """Build the emergency layout widget (form-style sections). Returns the root KioskWidget."""
    from .widgets import apply_debug_border

    # HEADER
    blue_bar = _form_section_bar("IN CASE OF EMERGENCY", (0.25, 0.45, 0.85, 1))
    apply_debug_border(blue_bar)
    layout.add_widget(blue_bar)

    patient_data = e_data.get("profile") or {}
    medical_data = e_data.get("medical") or {}


    # BOTTOM: AnchorLayout centers the two section boxes on y
    red_bar = (0.75, 0.2, 0.2, 1)
    # PERSONAL section height: red bar (40dp) + 7 form rows (40dp each)
    personal_height = dp(40) + 7 * dp(40)

    # PERSONAL
    personal = BoxLayout(
        orientation="vertical",
        spacing=dp(4),
        size_hint_y=None,
        height=personal_height,
    )
    personal.add_widget(_form_section_bar("PERSONAL INFORMATION", red_bar, height=dp(40)))
    name = patient_data.get("name") or "Patient"
    personal.add_widget(_form_row("FULL NAME", name))
    personal.add_widget(_form_row("DOB", patient_data.get("dob")))
    dnr = medical_data.get("dnr", False)
    personal.add_widget(_form_row("CODE STATUS", "DNR" if dnr else "FULL CODE"))
    allergies = medical_data.get("allergies") or []
    personal.add_widget(_form_row("ALLERGIES", ", ".join(allergies) if allergies else None))
    meds = medical_data.get("medications") or []
    med_strs = []
    for m in meds:
        n = m.get("name") or ""
        dosage = (m.get("dosage") or "").strip()
        freq = (m.get("frequency") or "").strip()
        if dosage or freq:
            n += " " + " ".join([dosage, freq]).strip()
        med_strs.append(n)
    personal.add_widget(_form_row("MEDICATIONS", ", ".join(med_strs) if med_strs else None))
    cond = medical_data.get("conditions")
    personal.add_widget(_form_row("CURRENT HEALTH CONDITIONS", cond))
    apply_debug_border(personal)

    # CONTACTS
    ec_list = []
    for c in e_contacts.get("contacts", []):
        phone = c.get("phone") or ""
        rel = c.get("relationship") or ""
        ec_list.append(f"{c.get('display_name', '')} ({rel}): {phone}".strip())
    n_contact_rows = len(ec_list) + 2
    contacts_height = dp(40) + n_contact_rows * dp(40)

    contacts_section = BoxLayout(
        orientation="vertical",
        spacing=dp(4),
        size_hint_y=None,
        height=contacts_height,
    )

    contacts_section.add_widget(_form_section_bar("EMERGENCY CONTACTS", red_bar, height=dp(40)))

    for i, line in enumerate(ec_list):
        contacts_section.add_widget(_form_row("CONTACT " + str(i + 1), line))

    proxy_name = e_contacts.get("medical_proxy_name") or ""
    proxy_phone = e_contacts.get("medical_proxy_phone") or ""
    contacts_section.add_widget(_form_row("MEDICAL PROXY", f"{proxy_name} {proxy_phone}".strip()))

    poa_name = e_contacts.get("poa_name") or ""
    poa_phone = e_contacts.get("poa_phone") or ""
    contacts_section.add_widget(_form_row("POA", f"{poa_name} {poa_phone}".strip()))
    apply_debug_border(contacts_section)

    # box for bottom two sections: each half gets an AnchorLayout to center its content
    bottom_box = BoxLayout(
        orientation="vertical",
        size_hint_y=1,
        spacing=dp(8),
    )
    top_half = AnchorLayout(anchor_y="center", size_hint_y=0.5)
    top_half.add_widget(personal)
    apply_debug_border(top_half)
    bottom_box.add_widget(top_half)

    bottom_half = AnchorLayout(anchor_y="center", size_hint_y=0.5)
    bottom_half.add_widget(contacts_section)
    apply_debug_border(bottom_half)
    bottom_box.add_widget(bottom_half)

    # apply_debug_border(bottom_box)
    layout.add_widget(bottom_box)
    attach_emergency_border(layout, services)
    return layout
