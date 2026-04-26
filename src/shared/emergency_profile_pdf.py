"""Build a printable PDF of the emergency profile from composed API profile_data."""

from datetime import date, datetime
from io import BytesIO
from typing import Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

_MARGIN = 72
_LINE = 14
_GAP = 6
_TITLE_SIZE = 18
_BODY_SIZE = 10
_HEADING_SIZE = 11


def _wrap_lines(text: str, max_chars: int = 92) -> list[str]:
    text = (text or "").replace("\n", " ").strip()
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    n = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if n + add > max_chars and cur:
            lines.append(" ".join(cur))
            cur = [w]
            n = len(w)
        else:
            if cur:
                n += 1
            cur.append(w)
            n += len(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _new_page(c: canvas.Canvas, height: float) -> float:
    c.showPage()
    return height - _MARGIN


def _draw_heading(c: canvas.Canvas, y: float, height: float, title: str) -> float:
    if y < _MARGIN + _LINE * 3:
        y = _new_page(c, height)
    c.setFont("Helvetica-Bold", _HEADING_SIZE)
    c.drawString(_MARGIN, y, title)
    return y - _LINE - _GAP // 2


def _draw_lines(
    c: canvas.Canvas,
    y: float,
    height: float,
    lines: list[str],
    font: str = "Helvetica",
    size: int = _BODY_SIZE,
) -> float:
    c.setFont(font, size)
    for line in lines:
        if y < _MARGIN + _LINE:
            y = _new_page(c, height)
            c.setFont(font, size)
        c.drawString(_MARGIN, y, line)
        y -= _LINE
    return y - _GAP


def build_pdf(profile_data: Optional[dict[str, Any]] = None) -> bytes:
    """Return PDF bytes for the emergency profile. Uses same shape as EmergencyService.get_emergency_profile."""
    buf = BytesIO()
    # pageCompression=0 keeps text searchable in raw bytes (helps tests; small documents).
    c = canvas.Canvas(buf, pagesize=letter, pageCompression=0)
    _width, height = letter
    y = height - _MARGIN

    data = profile_data if isinstance(profile_data, dict) else {}
    prof = data.get("profile") or {}
    med = data.get("medical") or {}

    c.setFont("Helvetica-Bold", _TITLE_SIZE)
    c.drawString(_MARGIN, y, "Emergency profile")
    y -= _LINE * 2

    c.setFont("Helvetica", _BODY_SIZE)
    gen = f"Generated {date.today().isoformat()} {datetime.now().strftime('%H:%M')}"
    c.drawString(_MARGIN, y, gen)
    y -= _LINE * 2

    name = (prof.get("name") or "").strip()
    dob = (prof.get("dob") or "").strip()
    if name or dob:
        y = _draw_heading(c, y, height, "Care recipient")
        block = []
        if name:
            block.append(f"Name: {name}")
        if dob:
            block.append(f"Date of birth: {dob}")
        y = _draw_lines(c, y, height, block)

    dnr = med.get("dnr")
    if dnr is not None:
        y = _draw_heading(c, y, height, "Advance directives")
        y = _draw_lines(
            c,
            y,
            height,
            [f"DNR on file: {'Yes' if dnr else 'No'}"],
        )

    cond = (med.get("conditions") or "").strip()
    if cond:
        y = _draw_heading(c, y, height, "Conditions")
        y = _draw_lines(c, y, height, _wrap_lines(cond))

    allergies = med.get("allergies") or []
    if allergies:
        y = _draw_heading(c, y, height, "Allergies")
        for a in allergies:
            if isinstance(a, dict):
                allergen = (a.get("allergen") or "").strip()
                reaction = (a.get("reaction") or "").strip()
                label = f"{allergen} — {reaction}" if reaction else allergen
            else:
                label = str(a).strip()
            if label:
                y = _draw_lines(c, y, height, [f"• {label}"])

    medications = med.get("medications") or []
    if medications:
        y = _draw_heading(c, y, height, "Medications")
        for m in medications:
            if not isinstance(m, dict):
                continue
            parts = [
                m.get("name") or "",
                m.get("dosage") or "",
                m.get("frequency") or "",
            ]
            line = " · ".join(p for p in parts if p)
            times = m.get("medication_times") or []
            if times:
                line = f"{line} ({', '.join(str(t) for t in times)})" if line else ", ".join(
                    str(t) for t in times
                )
            if line:
                y = _draw_lines(c, y, height, [f"• {line}"])

    em = data.get("emergency") or {}
    proxy = (em.get("proxy") or {}).get("name") or ""
    proxy_phone = (data.get("medical_proxy_phone") or "").strip()
    if proxy or proxy_phone:
        y = _draw_heading(c, y, height, "Medical proxy")
        lines = []
        if proxy:
            lines.append(f"Name: {proxy}")
        if proxy_phone:
            lines.append(f"Phone: {proxy_phone}")
        y = _draw_lines(c, y, height, lines)

    poa_n = (data.get("poa_name") or "").strip()
    poa_p = (data.get("poa_phone") or "").strip()
    if poa_n or poa_p:
        y = _draw_heading(c, y, height, "Power of attorney")
        lines = []
        if poa_n:
            lines.append(f"Name: {poa_n}")
        if poa_p:
            lines.append(f"Phone: {poa_p}")
        y = _draw_lines(c, y, height, lines)

    notes = (data.get("notes") or "").strip()
    if notes:
        y = _draw_heading(c, y, height, "Responder notes")
        y = _draw_lines(c, y, height, _wrap_lines(notes))

    ec = data.get("emergency_contacts") or []
    if ec:
        y = _draw_heading(c, y, height, "Emergency contacts")
        for contact in ec:
            if not isinstance(contact, dict):
                continue
            nm = (contact.get("display_name") or "").strip()
            ph = (contact.get("phone") or "").strip()
            rel = (contact.get("relationship") or "").strip()
            if not nm and not ph:
                continue
            parts = [nm, ph, rel]
            line = " · ".join(p for p in parts if p)
            y = _draw_lines(c, y, height, [f"• {line}"])

    c.save()
    buf.seek(0)
    return buf.getvalue()
