"""
Kiosk Emergency screen: load emergency profile via remote service; build read-only HTML (patient, medical, contacts).

Scope: presentation + photo fetch for this screen only.
Not here: printing (emergency_print), alert activation/polling (app), or server-side PDF generation.
"""

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
    return (
        f'<div class="section-bar" style="background:{bar_color_hex}">{title_esc}</div>'
    )


def build_emergency_html(services, api_url: str) -> str:
    """Build emergency screen HTML for pywebview."""
    import html as html_mod
    import urllib.parse

    from . import html_primitives as hp
    from .api_client import fetch_photo_b64

    emergency_svc = services.get_emergency_service()
    if not emergency_svc:
        return hp.kiosk_header("Emergency profile unavailable")

    result = emergency_svc.get_emergency_profile()
    if not result.success or not result.data:
        return hp.kiosk_header("Emergency profile not found")

    e_data = result.data
    patient_data = e_data.get("profile") or {}
    medical_data = e_data.get("medical") or {}
    care_recipient_user_id = e_data.get("care_recipient_user_id") or ""
    patient_photo_src = None
    if care_recipient_user_id:
        contact_svc = services.get_contact_service()
        if contact_svc:
            base = api_url.rstrip("/")
            patient_photo_src = fetch_photo_b64(
                f"{base}/api/users/{care_recipient_user_id}/photo",
                contact_svc._session,
                contact_svc._headers,
            )
    e_contacts = {
        "contacts": e_data.get("emergency_contacts") or [],
        "poa_name": e_data.get("poa_name"),
        "poa_phone": e_data.get("poa_phone"),
        "medical_proxy_name": ((e_data.get("emergency") or {}).get("proxy") or {}).get(
            "name"
        ),
        "medical_proxy_phone": e_data.get("medical_proxy_phone"),
    }

    html_parts = []
    html_parts.append(_section_bar_html("IN CASE OF EMERGENCY", "#4080d9"))
    html_parts.append(_section_bar_html("PERSONAL INFORMATION", "#c03333"))
    if patient_photo_src:
        patient_name = patient_data.get("name") or "Patient"
        initial = (patient_name or "?")[0].upper()

        html_parts.append(
            f'<div class="emergency-patient-photo">'
            f'<div class="avatar-wrapper"><div class="contact-initial">{html_mod.escape(initial)}</div>'
            f"{hp.avatar_img(patient_photo_src, patient_name)}</div></div>"
        )
    html_parts.append(_form_row_html("FULL NAME", patient_data.get("name")))
    html_parts.append(_form_row_html("DOB", patient_data.get("dob")))
    dnr = medical_data.get("dnr", False)
    html_parts.append(_form_row_html("CODE STATUS", "DNR" if dnr else "FULL CODE"))
    fc_id = (e_data.get("family_circle_id") or "").strip()
    dnr_doc = (e_data.get("dnr_document_path") or "").strip()
    if dnr_doc and care_recipient_user_id and fc_id:
        base = api_url.rstrip("/")
        doc_url = (
            f"{base}/api/family_circles/{urllib.parse.quote(fc_id, safe='')}"
            f"/care-recipients/{urllib.parse.quote(care_recipient_user_id, safe='')}/dnr-document"
        )
        url_esc = html_mod.escape(doc_url, quote=True)
        html_parts.append(
            f'<div class="form-row"><div class="label">POLST / DNR DOCUMENT:</div>'
            f'<div class="value kiosk-body-large"><a href="{url_esc}" target="_blank" rel="noopener">Open document</a></div></div>'
        )
    allergies = medical_data.get("allergies") or []
    html_parts.append(
        _form_row_html("ALLERGIES", ", ".join(allergies) if allergies else None)
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
    html_parts.append(
        _form_row_html("MEDICATIONS", ", ".join(med_strs) if med_strs else None)
    )
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
