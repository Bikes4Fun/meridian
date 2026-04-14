"""
Kiosk Emergency screen: load emergency profile via remote service; build read-only HTML (patient, medical, contacts).

Scope: presentation + photo fetch for this screen; client-side emergency PDF print pipeline (trigger from app on alert).
Not here: alert activation/polling (app), or server-side PDF generation.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile

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

    html_parts = []
    html_parts.append(hp.section_bar_html("IN CASE OF EMERGENCY", "#4080d9"))
    html_parts.append(hp.section_bar_html("PERSONAL INFORMATION", "#c03333"))
    if patient_photo_src:
        patient_name = patient_data.get("name") or "Patient"
        initial = (patient_name or "?")[0].upper()

        html_parts.append(
            f'<div class="emergency-patient-photo">'
            f'<div class="avatar-wrapper"><div class="contact-initial">{html_mod.escape(initial)}</div>'
            f"{hp.avatar_img(patient_photo_src, patient_name)}</div></div>"
        )
    html_parts.append(hp.form_row_html("FULL NAME", patient_data.get("name")))
    html_parts.append(hp.form_row_html("DOB", patient_data.get("dob")))
    dnr = medical_data.get("dnr", False)
    html_parts.append(hp.form_row_html("CODE STATUS", "DNR" if dnr else "FULL CODE"))
    fc_id = (e_data.get("family_circle_id") or "").strip()
    dnr_doc = (e_data.get("dnr_document_path") or "").strip()
    if dnr_doc and care_recipient_user_id and fc_id:
        doc_url = emergency_svc.get_dnr_document_url(fc_id, care_recipient_user_id)
        url_esc = html_mod.escape(doc_url, quote=True)
        html_parts.append(
            f'<div class="form-row"><div class="label">POLST / DNR DOCUMENT:</div>'
            f'<div class="value kiosk-body-large"><a href="{url_esc}" target="_blank" rel="noopener">Open document</a></div></div>'
        )
    allergies = medical_data.get("allergies") or []
    html_parts.append(
        hp.form_row_html("ALLERGIES", ", ".join(allergies) if allergies else None)
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
        hp.form_row_html("MEDICATIONS", ", ".join(med_strs) if med_strs else None)
    )
    html_parts.append(hp.form_row_html("HEALTH", medical_data.get("conditions")))

    html_parts.append(hp.section_bar_html("EMERGENCY CONTACTS", "#c03333"))
    for i, c in enumerate(e_contacts.get("contacts", [])):
        line = f"{c.get('display_name', '')} ({c.get('relationship', '')}): {c.get('phone', '')}".strip()
        html_parts.append(hp.form_row_html(f"CONTACT {i + 1}", line))
    proxy = f"{e_contacts.get('medical_proxy_name', '')} {e_contacts.get('medical_proxy_phone', '')}".strip()
    html_parts.append(hp.form_row_html("MEDICAL PROXY", proxy))
    poa = f"{e_contacts.get('poa_name', '')} {e_contacts.get('poa_phone', '')}".strip()
    html_parts.append(hp.form_row_html("POA", poa))

    print_js = "pywebview.api.print_emergency()"
    html_parts.append(hp.kiosk_button("Print Emergency Document", print_js))

    return hp.panel("".join(html_parts))


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
            r = subprocess.run(
                ["start", "/p", path], capture_output=True, shell=True, timeout=10
            )
            if r.returncode != 0:
                return False, "Print command failed", None
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
    """Fetch PDF, print, update status_label if provided, schedule job polling when job_id and label."""
    logger.info("Emergency print: fetching PDF...")
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
