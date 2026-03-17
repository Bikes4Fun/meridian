"""
Emergency screen: fetches data, shapes contacts, builds form-style layout.
"""

import os


def _form_section_bar(title, bar_color=(1, 1, 1, 1), height=None):
    """Form-style section header: colored bar with white text (Kivy)."""
    from kivy.graphics import Color, Rectangle
    from kivy.uix.boxlayout import BoxLayout
    from .kiosk_metrics import scaled
    from .screen_primitives import KioskLabel
    h = height if height is not None else scaled(48)
    bar = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=h, padding=[scaled(12), scaled(6)]
    )
    with bar.canvas.before:
        Color(*bar_color)
        bar._bg = Rectangle(pos=bar.pos, size=bar.size)
    bar.bind(
        pos=lambda w, v: setattr(w._bg, "pos", w.pos),
        size=lambda w, v: setattr(w._bg, "size", w.size),
    )
    lbl = KioskLabel(type="subheader", text=title)
    lbl.color = (1, 1, 1, 1)
    bar.add_widget(lbl)
    return bar


def _form_row(label_text, value_text, dark_text=(0.1, 0.1, 0.1, 1), row_height=None):
    """One labeled row: LABEL  value (Kivy)."""
    from kivy.uix.boxlayout import BoxLayout
    from .kiosk_metrics import scaled
    from .screen_primitives import KioskLabel
    h = row_height if row_height is not None else scaled(52)
    row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=h, spacing=scaled(8)
    )
    lbl = KioskLabel(type="caption", text=label_text + ":")
    lbl.color = dark_text
    lbl.size_hint_x = None
    lbl.width = scaled(200)
    row.add_widget(lbl)
    val = KioskLabel(type="body_large", text=value_text or "—")
    val.color = dark_text
    val.shorten = False
    row.add_widget(val)
    return row


def _attach_emergency_border(widget, services):
    """Draw an orange border on the widget; flash when alert is activated (Kivy)."""
    from kivy.graphics import Color, Line
    from kivy.clock import Clock
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


def _build_layout(layout, e_data, e_contacts, services):
    """Build the emergency layout (form-style sections). Returns the root KioskWidget (Kivy)."""
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.anchorlayout import AnchorLayout
    from kivy.uix.image import Image
    from .checkin_screen import _crop_image_to_circle
    from .emergency_print import add_emergency_print_section
    care_recipient_user_id = e_data.get("care_recipient_user_id")
    photo_src = None
    loc_svc = services.get("location_service")
    if care_recipient_user_id and loc_svc and hasattr(loc_svc, "fetch_photo_to_cache"):
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        raw = loc_svc.fetch_photo_to_cache(care_recipient_user_id, cache_dir)
        if raw:
            photo_src = _crop_image_to_circle(raw) or raw
            if not os.path.isfile(photo_src):
                photo_src = None

    blue_bar = _form_section_bar("IN CASE OF EMERGENCY", (0.25, 0.45, 0.85, 1), height=scaled(48))
    layout.add_widget(blue_bar)

    patient_data = e_data.get("profile") or {}
    medical_data = e_data.get("medical") or {}

    red_bar = (0.75, 0.2, 0.2, 1)
    personal_height = scaled(48) + 6 * scaled(40) + 6 * scaled(4)
    row_h = scaled(40)

    personal = BoxLayout(
        orientation="vertical",
        spacing=scaled(4),
        size_hint_x=0.65 if photo_src else 1.0,
        size_hint_y=1,
    )
    personal.add_widget(
        _form_section_bar("PERSONAL INFORMATION", red_bar)
    )
    name = patient_data.get("name") or "Patient"
    personal.add_widget(_form_row("FULL NAME", name, row_height=row_h))
    personal.add_widget(_form_row("DOB", patient_data.get("dob"), row_height=row_h))
    dnr = medical_data.get("dnr", False)
    personal.add_widget(_form_row("CODE STATUS", "DNR" if dnr else "FULL CODE", row_height=row_h)) #TODO this seems like a riskky method that could result in a bad outcome. probbably shoud have dnr if dnr, full code if full code, and unknown if ... unknown. 
    allergies = medical_data.get("allergies") or []
    personal.add_widget(
        _form_row("ALLERGIES", ", ".join(allergies) if allergies else None, row_height=row_h)
    )
    meds = medical_data.get("medications") or []
    med_strs = []
    for m in meds:
        n = m.get("name") or ""
        dosage = (m.get("dosage") or "").strip()
        freq = (m.get("frequency") or "").strip()
        if dosage or freq:
            n += " " + " ".join([dosage, freq]).strip()
        med_strs.append(n)
    personal.add_widget(
        _form_row("MEDICATIONS", ", ".join(med_strs) if med_strs else None, row_height=row_h)
    )
    cond = medical_data.get("conditions")
    personal.add_widget(_form_row("HEALTH", cond, row_height=row_h))
    personal_wrapper = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=personal_height,
    )
    personal_wrapper.add_widget(personal)
    if photo_src:
        photo_col = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            size_hint_x=0.35,
            size_hint_y=1,
        )
        img = Image(
            source=photo_src,
            size_hint=(None, None),
            size=(scaled(96), scaled(96)),
            fit_mode="contain",
        )
        photo_col.add_widget(img)
        personal_wrapper.add_widget(photo_col)

    ec_list = []
    for c in e_contacts.get("contacts", []):
        phone = c.get("phone") or ""
        rel = c.get("relationship") or ""
        ec_list.append(f"{c.get('display_name', '')} ({rel}): {phone}".strip())
    n_contact_rows = len(ec_list) + 2
    contacts_height = scaled(48) + n_contact_rows * scaled(64)

    contacts_section = BoxLayout(
        orientation="vertical",
        spacing=scaled(4),
        size_hint_y=None,
        height=contacts_height,
    )

    contacts_section.add_widget(
        _form_section_bar("EMERGENCY CONTACTS", red_bar, height=scaled(48))
    )

    for i, line in enumerate(ec_list):
        contacts_section.add_widget(
            _form_row("CONTACT " + str(i + 1), line, row_height=scaled(64))
        )

    proxy_name = e_contacts.get("medical_proxy_name") or ""
    proxy_phone = e_contacts.get("medical_proxy_phone") or ""
    contacts_section.add_widget(
        _form_row("MEDICAL PROXY", f"{proxy_name} {proxy_phone}".strip(), row_height=scaled(64))
    )
    poa_name = e_contacts.get("poa_name") or ""
    poa_phone = e_contacts.get("poa_phone") or ""
    contacts_section.add_widget(
        _form_row("POA", f"{poa_name} {poa_phone}".strip(), row_height=scaled(64))
    )

    bottom_box = BoxLayout(orientation="vertical", size_hint_y=1)
    bottom_box.add_widget(personal_wrapper)
    bottom_box.add_widget(contacts_section)
    layout.add_widget(bottom_box)

    add_emergency_print_section(layout, services)

    _attach_emergency_border(layout, services)
    return layout


def _form_row_html(label_text: str, value_text: str) -> str:
    """One labeled row for HTML. label (caption), value (body_large)."""
    import html

    label_esc = html.escape(str(label_text or ""))
    value_esc = html.escape(str(value_text or "—"))
    return f'<div class="form-row"><div class="label">{label_esc}:</div><div class="value">{value_esc}</div></div>'


def _section_bar_html(title: str, bar_color_hex: str = "#4080d9") -> str:
    """Section header bar. bar_color_hex e.g. #4080d9 blue, #c03333 red."""
    import html

    title_esc = html.escape(str(title or ""))
    return f'<div class="section-bar" style="background:{bar_color_hex}">{title_esc}</div>'


def build_emergency_html(services, api_url: str) -> str:
    """Build emergency screen HTML for pywebview."""
    from . import html_primitives as hp

    emergency_svc = services.get("emergency_service")
    if not emergency_svc:
        return hp.kiosk_header("Emergency profile unavailable")

    result = emergency_svc.get_emergency_profile()
    if not result.success or not result.data:
        return hp.kiosk_header("Emergency profile not found")

    e_data = result.data
    patient_data = e_data.get("profile") or {}
    medical_data = e_data.get("medical") or {}
    e_contacts = {
        "contacts": e_data.get("emergency_contacts") or [],
        "poa_name": e_data.get("poa_name"),
        "poa_phone": e_data.get("poa_phone"),
        "medical_proxy_name": ((e_data.get("emergency") or {}).get("proxy") or {}).get("name"),
        "medical_proxy_phone": e_data.get("medical_proxy_phone"),
    }

    html_parts = []
    html_parts.append(_section_bar_html("IN CASE OF EMERGENCY", "#4080d9"))
    html_parts.append(_section_bar_html("PERSONAL INFORMATION", "#c03333"))
    html_parts.append(_form_row_html("FULL NAME", patient_data.get("name")))
    html_parts.append(_form_row_html("DOB", patient_data.get("dob")))
    dnr = medical_data.get("dnr", False)
    html_parts.append(_form_row_html("CODE STATUS", "DNR" if dnr else "FULL CODE"))
    allergies = medical_data.get("allergies") or []
    html_parts.append(_form_row_html("ALLERGIES", ", ".join(allergies) if allergies else None))
    meds = medical_data.get("medications") or []
    med_strs = []
    for m in meds:
        n = m.get("name") or ""
        dosage = (m.get("dosage") or "").strip()
        freq = (m.get("frequency") or "").strip()
        if dosage or freq:
            n += " " + " ".join([dosage, freq]).strip()
        med_strs.append(n)
    html_parts.append(_form_row_html("MEDICATIONS", ", ".join(med_strs) if med_strs else None))
    html_parts.append(_form_row_html("HEALTH", medical_data.get("conditions")))

    html_parts.append(_section_bar_html("EMERGENCY CONTACTS", "#c03333"))
    for i, c in enumerate(e_contacts.get("contacts", [])):
        line = f"{c.get('display_name', '')} ({c.get('relationship', '')}): {c.get('phone', '')}".strip()
        html_parts.append(_form_row_html(f"CONTACT {i + 1}", line))
    proxy = f"{e_contacts.get('medical_proxy_name', '')} {e_contacts.get('medical_proxy_phone', '')}".strip()
    html_parts.append(_form_row_html("MEDICAL PROXY", proxy))
    poa = f"{e_contacts.get('poa_name', '')} {e_contacts.get('poa_phone', '')}".strip()
    html_parts.append(_form_row_html("POA", poa))

    print_js = "pywebview.api.print_emergency()"
    html_parts.append(hp.kiosk_button("Print Emergency Document", print_js))

    return hp.panel("".join(html_parts))


def build_emergency_screen(services):
    """Build fully constructed emergency profile widget. Returns widget ready for layout (Kivy)."""
    from .screen_primitives import KioskLabel, KioskWidget
    from .kiosk_metrics import scaled
    # Extra top padding so "IN CASE OF EMERGENCY" header is not clipped
    emergency_widget = KioskWidget(padding=[scaled(40), scaled(48), scaled(40), scaled(40)], spacing=0)

    emergency_svc = services.get("emergency_service")
    if not emergency_svc:
        emergency_widget.add_widget(
            KioskLabel(type="header", text="Emergency profile service not available")
        )
        return emergency_widget

    all_data = emergency_svc.get_emergency_profile()
    if not all_data.success or not all_data.data:
        emergency_widget.add_widget(
            KioskLabel(type="header", text="Emergency profile not found")
        )
        return emergency_widget

    e_data = all_data.data
    e_contacts = {
        "contacts": e_data.get("emergency_contacts") or [],
        "poa_name": e_data.get("poa_name"),
        "poa_phone": e_data.get("poa_phone"),
        "medical_proxy_name": ((e_data.get("emergency") or {}).get("proxy") or {}).get(
            "name"
        ),
        "medical_proxy_phone": e_data.get("medical_proxy_phone"),
    }

    return _build_layout(emergency_widget, e_data, e_contacts, services)
