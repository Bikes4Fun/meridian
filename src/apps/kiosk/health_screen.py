"""
Health: medications list on Health screen (mark taken only).
Medication list editing: Settings → Edit medications (webapp inline editor in kiosk_medications_embed.js).
"""

import html as html_module

from . import html_primitives as hp


# Profile/API-sourced strings must be escaped for HTML text and attributes; fixed UI strings need not.
# e.g. escape medication name and time slot; literals like "Done ✓" or button labels "Taken"/"Undo" need not.

def _timed_row_html(m: dict, t: str) -> str:
    name = html_module.escape(m.get("name", "?"))
    done = m.get("status") == "done"
    status_txt = "Done ✓" if done else "Not done"
    meta = html_module.escape(str(t)) + " · " + status_txt
    med_id = m.get("id")
    card_classes = "med-card med-card--done" if done else "med-card med-card--pending"
    actions = ""
    if med_id is not None:
        mid = html_module.escape(str(med_id))
        slot = html_module.escape(str(t), quote=True)
        lbl = "Undo" if done else "Taken"
        actions = (
            f'<div class="med-card__actions"><button type="button" '
            f'class="med-taken-btn timeline-action-btn" data-med-id="{mid}" '
            f'data-med-time="{slot}" data-med-done="{str(done).lower()}">{lbl}</button></div>'
        )
    return (
        f'<div class="timeline-item med-manage-row"><span class="timeline-bar-med"></span>'
        f'<article class="{card_classes}"><p class="med-card__title">{name}</p>'
        f'<p class="med-card__meta">{meta}</p>{actions}</article></div>'
    )


def _prn_row_html(m: dict) -> str:
    name = html_module.escape(m.get("name", "?"))
    lt = m.get("last_taken")
    taken = m.get("status") == "taken"
    last = (
        f"Last: {html_module.escape(str(lt))}"
        if lt
        else ("Taken ✓" if taken else "Not taken today")
    )
    med_id = m.get("id")
    card_classes = "med-card med-card--prn " + (
        "med-card--done" if taken else "med-card--pending"
    )
    title = name + " (PRN)"
    actions = ""
    if med_id is not None:
        take_lbl = "Uncheck" if taken else "Take"
        mid = html_module.escape(str(med_id))
        actions = (
            f'<div class="med-card__actions"><button type="button" '
            f'class="med-taken-btn timeline-action-btn" data-med-id="{mid}" '
            f'data-med-time="prn" data-med-done="{str(taken).lower()}">'
            f"{take_lbl}</button></div>"
        )
    return (
        f'<div class="timeline-item med-manage-row"><span class="timeline-bar-med"></span>'
        f'<article class="{card_classes}"><p class="med-card__title">{title}</p>'
        f'<p class="med-card__meta">{last}</p>{actions}</article></div>'
    )


def _medication_lists_inner_html(data: dict) -> str:
    time_groups: dict = {}
    for m in data.get("timed_medications", []):
        t = m.get("time", "Unknown")
        time_groups.setdefault(t, []).append(m)
    group_times = data.get("medication_time_groups", {})
    sorted_times = sorted(
        time_groups.keys(), key=lambda x: group_times.get(x, "23:59:59")
    )
    parts: list[str] = []
    for t in sorted_times:
        meds = time_groups[t]
        if not meds:
            continue
        items_html = [_timed_row_html(m, t) for m in meds]
        header_inner = html_module.escape(t)  # batch time key → timeline header text
        parts.append(
            f'<div class="timeline-card"><div class="timeline-header timeline-header--med-batch">'
            f"{header_inner}</div><div class=\"timeline-list\">"
            f'{"".join(items_html)}</div></div>'
        )
        parts.append(hp.spacer(12))
    prn = data.get("prn_medications", [])
    if prn:
        prn_html = [_prn_row_html(m) for m in prn]
        prn_header = "PRN (As Needed)"
        parts.append(
            f'<div class="timeline-card"><div class="timeline-header timeline-header--med-batch">'
            f"{prn_header}</div><div class=\"timeline-list\">"
            f'{"".join(prn_html)}</div></div>'
        )
    return "".join(parts)


def build_health_html(services, api_url: str) -> str:
    """Health screen: medications list and mark taken."""
    med_svc = services.get("medication_service")
    if not med_svc:
        return (
            hp.kiosk_header("Health")
            + hp.spacer(16)
            + hp.error_state("Health information unavailable")
        )

    result = med_svc.get_medication_data()
    if not result.success:
        return (
            hp.kiosk_header("Health")
            + hp.spacer(16)
            + hp.error_state("Could not load health information")
        )

    data = result.data or {}
    inner = _medication_lists_inner_html(data)
    parts = [hp.kiosk_header("Health"), hp.spacer(16)]
    if not inner:
        parts.append(hp.empty_state("No medications listed"))
    else:
        parts.append(inner)
    return "".join(parts)


class HealthHandler:
    """Mark taken only; list editing is Settings → Edit medications (shared web inline editor)."""

    def __init__(self, app):
        self._app = app

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> str:
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        if not hasattr(med_svc, "mark_medication_taken"):
            return "mark taken not supported"
        r = med_svc.mark_medication_taken(medication_id, time_slot, taken)
        if r.success:
            return "ok"
        return r.error or "failed"
