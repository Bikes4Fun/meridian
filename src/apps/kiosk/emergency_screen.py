"""
Kiosk Emergency screen: load emergency profile via remote service; build read-only HTML (patient, medical, contacts).

Scope: presentation + photo for this screen; client-side emergency PDF print pipeline (trigger from app on alert).
Not here: alert activation/polling (app), or server-side PDF generation.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)


def build_emergency_html(services, api_url: str) -> str:
    """Build emergency screen HTML for pywebview."""
    import html as html_mod

    from . import html_primitives as hp

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
        patient_photo_src = emergency_svc.get_user_photo_b64(care_recipient_user_id)
    e_contacts = {
        "contacts": e_data.get("emergency_contacts") or [],
        "poa_name": e_data.get("poa_name"),
        "poa_phone": e_data.get("poa_phone"),
        "medical_proxy_name": ((e_data.get("emergency") or {}).get("proxy") or {}).get(
            "name"
        ),
        "medical_proxy_phone": e_data.get("medical_proxy_phone"),
    }

    def _esc(value: str) -> str:
        return html_mod.escape(str(value or ""))

    def _initials(name: str) -> str:
        parts = [p for p in (name or "").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    patient_name = (patient_data.get("name") or "Patient").strip()
    dob_text = (patient_data.get("dob") or "").strip()
    age_text = ""
    if dob_text:
        try:
            born = datetime.strptime(dob_text, "%Y-%m-%d").date()
            today = datetime.now().date()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            age_text = str(max(age, 0))
        except ValueError:
            age_text = ""
    dnr_val = int(medical_data.get("dnr", 0) or 0)
    code_status = {0: "Full resuscitation", 1: "Do Not Resuscitate", 2: "Per document"}.get(dnr_val, "Do Not Resuscitate")
    updated_text = datetime.now().strftime("Updated %b %d %Y")

    _DNI_LABELS       = {0: "Intubation OK",          1: "Do Not Intubate",               2: "Per document"}
    _NUTRITION_LABELS = {0: "Artificial nutrition OK", 1: "No artificial nutrition",        2: "Per document"}
    _ANTIBIOTIC_LABELS= {0: "Antibiotics permitted",   1: "No antibiotics",                 2: "Per document"}
    _BLOOD_LABELS     = {0: "Blood products OK",       1: "No blood products",              2: "Per document"}

    def _dir_label(raw, lookup):
        try:
            return lookup.get(int(raw or 0), str(raw))
        except (TypeError, ValueError):
            return str(raw) if raw else ""

    allergies = medical_data.get("allergies") or []
    conditions = medical_data.get("conditions") or []
    if isinstance(conditions, str):
        conditions_text = conditions.strip()
    else:
        conditions_text = ", ".join([str(c).strip() for c in conditions if str(c).strip()])
    medications = medical_data.get("medications") or []
    contacts = e_contacts.get("contacts") or []

    sorted_contacts = sorted(
        contacts,
        key=lambda c: 0 if str(c.get("emergency_priority") or "").lower() == "primary_emergency" else 1,
    )
    call_contact = next(
        (c for c in sorted_contacts if (c.get("phone") or "").strip()),
        None,
    )
    call_contact_name = (call_contact.get("display_name") if call_contact else "No active call") or "No active call"

    dni_status        = _dir_label(medical_data.get("dni_status"),            _DNI_LABELS)
    nutrition_status  = _dir_label(medical_data.get("nutrition_status"),       _NUTRITION_LABELS)
    antibiotic_status = _dir_label(medical_data.get("antibiotic_status"),      _ANTIBIOTIC_LABELS)
    blood_status      = _dir_label(medical_data.get("blood_product_status"),   _BLOOD_LABELS)
    polst_dnr_signed = bool(medical_data.get("polst_dnr_signed"))
    polst_dni_signed = bool(medical_data.get("polst_dni_signed"))
    polst_nutrition_signed = bool(medical_data.get("polst_nutrition_signed"))
    any_signed = polst_dnr_signed or polst_dni_signed or polst_nutrition_signed

    proxy_name = (e_contacts.get("medical_proxy_name") or "").strip()
    proxy_phone = (e_contacts.get("medical_proxy_phone") or "").strip()
    poa_name = (e_contacts.get("poa_name") or "").strip()
    poa_phone = (e_contacts.get("poa_phone") or "").strip()

    html_parts = []
    html_parts.append('<div class="emergency-warm-shell">')
    html_parts.append(
        '<div class="emergency-warm-top-bar">'
        '<div class="emergency-warm-title">In Case of Emergency</div>'
        '<div class="emergency-warm-top-bar-actions">'
        f'<div class="emergency-warm-updated">{_esc(updated_text)}</div>'
        '<button type="button" class="emergency-warm-refresh-btn" onclick="pywebview.api.reload_screen(\'emergency\')" aria-label="Refresh emergency profile">Refresh</button>'
        '<button type="button" class="emergency-warm-exit-btn" data-screen="home" aria-label="Exit emergency screen">Done</button>'
        "</div>"
        "</div>"
    )
    html_parts.append('<div class="emergency-warm-scroll">')

    photo_html = (
        hp.avatar_img(patient_photo_src, patient_name)
        if patient_photo_src
        else f'<div class="emergency-warm-photo-initials">{_esc(_initials(patient_name))}</div>'
    )
    hero_meta = f"DOB {dob_text}" if dob_text else "DOB unknown"
    if age_text:
        hero_meta += f" · AGE {age_text}"

    # All code directives in hero chips — first responders see them immediately
    def _dir_chip(css_cls, prefix, label):
        return f'<span class="emergency-warm-chip {css_cls}">{_esc(prefix)}: {_esc(label)}</span>' if label else ""

    dni_chip        = _dir_chip("emergency-warm-chip-dni", "DNI",        dni_status)
    nut_chip        = _dir_chip("emergency-warm-chip-nut", "Nutrition",  nutrition_status)
    antibiotic_chip = _dir_chip("emergency-warm-chip-abx", "Antibiotics", antibiotic_status)
    blood_chip      = _dir_chip("emergency-warm-chip-bld", "Blood",      blood_status)
    html_parts.append(
        '<div class="emergency-warm-hero">'
        f'<div class="emergency-warm-photo">{photo_html}</div>'
        '<div class="emergency-warm-hero-details">'
        f'<div class="emergency-warm-name">{_esc(patient_name)}</div>'
        '<div class="emergency-warm-chips">'
        f'<span class="emergency-warm-chip emergency-warm-chip-dob">{_esc(hero_meta)}</span>'
        f'<span class="emergency-warm-chip emergency-warm-chip-code">DNR: {_esc(code_status)}</span>'
        f'{dni_chip}{nut_chip}{antibiotic_chip}{blood_chip}'
        "</div>"
        "</div>"
        "</div>"
    )

    # Allergies — high priority, right after identity
    html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Allergies</div>')
    if allergies:
        html_parts.append('<div class="emergency-warm-allergies">')
        for allergy in allergies:
            if isinstance(allergy, dict):
                label = _esc(allergy.get("allergen") or "")
                reaction = _esc(allergy.get("reaction") or "")
                text = f"{label} — {reaction}" if reaction else label
            else:
                text = _esc(allergy)
            html_parts.append(f'<span class="emergency-warm-allergy-pill">{text}</span>')
        html_parts.append("</div>")
    else:
        html_parts.append('<div class="emergency-warm-empty">No known allergies</div>')
    html_parts.append("</div>")

    # Medications — second priority
    html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Medications</div>')
    if medications:
        for med in medications:
            med_name = (med.get("name") or "Medication").strip()
            med_dose = (med.get("dosage") or "").strip()
            med_freq = (med.get("frequency") or "").strip()
            med_detail = " · ".join([part for part in [med_dose, med_freq] if part])
            html_parts.append(
                '<div class="emergency-med-row">'
                f'<div class="emergency-med-name">{_esc(med_name)}</div>'
                f'<div class="emergency-med-dose">{_esc(med_detail)}</div>'
                "</div>"
            )
    else:
        html_parts.append('<div class="emergency-warm-empty">No medications listed</div>')
    html_parts.append("</div>")

    # Conditions
    html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Conditions</div>')
    html_parts.append(
        '<div class="emergency-warm-info-row">'
        '<div class="emergency-warm-info-label">Active</div>'
        f'<div class="emergency-warm-info-value">{_esc(conditions_text or "No active conditions")}</div>'
        "</div>"
    )
    html_parts.append("</div>")

    # Brief history / notes
    brief_history = (e_data.get("brief_history") or "").strip()
    if brief_history:
        html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Brief History &amp; Notes</div>')
        html_parts.append(
            f'<div class="emergency-warm-history-text">{_esc(brief_history)}</div>'
        )
        html_parts.append("</div>")

    # All contacts together — emergency contacts first, then decision-makers
    html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Emergency Contacts &amp; Decision-Makers</div>')
    if sorted_contacts:
        for c in sorted_contacts:
            name = (c.get("display_name") or "").strip() or "Unknown"
            relation = (c.get("relationship") or "").strip() or "No relationship"
            phone = (c.get("phone") or "").strip()
            is_primary = str(c.get("emergency_priority") or "").lower() == "primary_emergency"
            phone_html = (
                f'<div class="emergency-warm-contact-phone">{_esc(phone)}</div>'
                if phone
                else '<div class="emergency-warm-contact-phone emergency-warm-contact-phone-empty">No phone on file</div>'
            )
            primary_badge = (
                '<span class="emergency-warm-primary-badge">Primary</span>' if is_primary else ""
            )
            html_parts.append(
                '<div class="emergency-warm-contact-row">'
                f'<div class="emergency-warm-contact-avatar">{_esc(_initials(name))}</div>'
                '<div class="emergency-warm-contact-info">'
                f'<div class="emergency-warm-contact-name">{_esc(name)} {primary_badge}</div>'
                f'<div class="emergency-warm-contact-relation">{_esc(relation)}</div>'
                "</div>"
                f"{phone_html}"
                "</div>"
            )
    else:
        html_parts.append('<div class="emergency-warm-empty">No emergency contacts configured</div>')
    if proxy_name:
        proxy_val = proxy_name + (f" · {proxy_phone}" if proxy_phone else "")
        html_parts.append(
            '<div class="emergency-warm-info-row emergency-warm-info-row--proxy">'
            '<div class="emergency-warm-info-label">Medical Proxy</div>'
            f'<div class="emergency-warm-info-value">{_esc(proxy_val)}</div>'
            "</div>"
        )
    if poa_name:
        poa_val = poa_name + (f" · {poa_phone}" if poa_phone else "")
        html_parts.append(
            '<div class="emergency-warm-info-row emergency-warm-info-row--proxy">'
            '<div class="emergency-warm-info-label">POA</div>'
            f'<div class="emergency-warm-info-value">{_esc(poa_val)}</div>'
            "</div>"
        )
    html_parts.append("</div>")

    # Documents
    documents = e_data.get("documents") or []
    if documents:
        html_parts.append('<div class="emergency-warm-section"><div class="emergency-warm-section-head">Documents on File</div>')
        for doc in documents:
            doc_type = _esc(doc.get("doc_type") or "Document")
            doc_label = _esc(doc.get("doc_label") or "")
            doc_date = _esc(doc.get("doc_date") or "")
            has_file = bool((doc.get("file_path") or "").strip())
            label_text = doc_label if doc_label else doc_type
            meta_parts = [p for p in [doc_date, "uploaded" if has_file else "no file"] if p]
            html_parts.append(
                '<div class="emergency-warm-info-row">'
                f'<div class="emergency-warm-info-label">{label_text}</div>'
                f'<div class="emergency-warm-info-value">{" · ".join(meta_parts)}</div>'
                "</div>"
            )
        html_parts.append("</div>")

    print_js = "pywebview.api.print_emergency()"
    html_parts.append(
        '<div class="emergency-warm-print-wrap">'
        f'{hp.kiosk_button("Print POLST / Emergency Document", print_js, small=True)}'
        "</div>"
    )

    html_parts.append("</div>")  # end scroll

    # Physician orders floater (left side, bouncing)
    orders_label = "View Physician Orders"
    if any_signed:
        signed_items = []
        if polst_dnr_signed:
            signed_items.append("CPR")
        if polst_dni_signed:
            signed_items.append("DNI")
        if polst_nutrition_signed:
            signed_items.append("Nutrition")
        orders_sub = "Signed: " + " · ".join(signed_items)
        floater_cls = "emergency-orders-floater emergency-orders-floater--signed"
        bubble_cls = "emergency-orders-bubble emergency-orders-bubble--signed"
        ring_cls = "emergency-orders-ring emergency-orders-ring--signed"
    else:
        orders_sub = "No signed orders on file"
        floater_cls = "emergency-orders-floater"
        bubble_cls = "emergency-orders-bubble"
        ring_cls = "emergency-orders-ring"

    html_parts.append(
        f'<div class="{floater_cls}">'
        f'<div class="{ring_cls}"></div>'
        f'<div class="{ring_cls}"></div>'
        f'<div class="{bubble_cls}">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/>'
        '<polyline points="10 9 9 9 8 9"/>'
        "</svg>"
        "</div>"
        f'<div class="emergency-orders-label">{_esc(orders_label)}</div>'
        f'<div class="emergency-orders-sub">{_esc(orders_sub)}</div>'
        "</div>"
    )

    # Call floater (right side, existing)
    html_parts.append(
        '<div class="emergency-warm-call-floater">'
        '<div class="emergency-warm-call-ring"></div>'
        '<div class="emergency-warm-call-ring"></div>'
        '<div class="emergency-warm-call-ring"></div>'
        '<div class="emergency-warm-call-bubble">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81 19.79 19.79 0 01.04 1.22 2 2 0 012 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92z"/>'
        "</svg>"
        "</div>"
        '<div class="emergency-warm-call-label">On Call</div>'
        f'<div class="emergency-warm-call-name">{_esc(call_contact_name)}</div>'
        "</div>"
    )
    html_parts.append("</div>")  # end shell

    return hp.panel("".join(html_parts), class_name="emergency-warm-panel")


def _parse_lp_job_id(stdout: str) -> str | None:
    """Parse 'request id is PrinterName-123 (1 file(s))' to get PrinterName-123."""
    if not stdout:
        return None
    m = re.search(r"request id is (\S+)", stdout)
    return m.group(1) if m else None


def _print_pdf_bytes(pdf_bytes: bytes) -> tuple[bool, str, str | None]:
    """Write PDF to a temp file and trigger system print. Returns (success, message, job_id)."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        os.write(fd, pdf_bytes)
        os.close(fd)
        fd = None
        job_id = None
        if sys.platform in ("darwin", "linux"):
            r = subprocess.run(["lp", path], capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                err_detail = (
                    (r.stderr or "").strip()
                    or (r.stdout or "").strip()
                    or "Print command failed"
                )
                logger.warning(
                    f"Emergency print: lp failed (rc={r.returncode}) {err_detail}"
                )
                return False, err_detail, None
            job_id = _parse_lp_job_id(r.stdout or "")
            if job_id:
                logger.info(f"Print job id: {job_id}")
        else:
            try:
                os.startfile(path, "print")
            except OSError as e:
                return False, str(e), None
        msg = f"Sent to printer (job {job_id})" if job_id else "Sent to printer"
        return True, msg, job_id
    except subprocess.TimeoutExpired:
        return False, "Print timed out", None
    except Exception as e:
        return False, str(e), None
    finally:
        if fd is not None:
            os.close(fd)


def _run_emergency_print(emergency_svc, status_label=None) -> None:
    """Print PDF, update status_label if provided, schedule job polling when job_id and label."""

    if status_label is not None:
        status_label.text = "Printing..."
    result = emergency_svc.get_emergency_profile_pdf()
    if not result.success:
        err = getattr(result, "error", None) or "could not get PDF"
        if status_label is not None:
            status_label.text = f"Print failed: {err}"
        logger.warning(f"Emergency print: could not get PDF ({err})")
        return
    if not result.data:
        logger.warning("Emergency print: PDF empty")
        if status_label is not None:
            status_label.text = "Print failed: no PDF data"
        return
    logger.info(
        f"Emergency print: PDF fetched ({len(result.data)} bytes), sending to printer..."
    )
    ok, msg, job_id = _print_pdf_bytes(result.data)
    if status_label is not None:
        status_label.text = msg if ok else f"Print failed: {msg}"
    if ok:
        logger.info(f"Emergency print: {msg}")
    else:
        logger.warning(f"Emergency print failed: {msg}")


def trigger_emergency_print(services) -> None:
    """Run emergency print (e.g. when alert activated). Uses same flow and status label as the button."""
    emergency_svc = services.get_emergency_service()
    if not emergency_svc or not getattr(
        emergency_svc, "get_emergency_profile_pdf", None
    ):
        return
    status_label = services.get_emergency_print_status_label()
    _run_emergency_print(emergency_svc, status_label)
