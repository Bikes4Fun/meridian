"""
Kiosk Health screen: medications list HTML, Edit medications entry, and “mark taken” bridge (HealthHandler → remote API).

Scope: render meds from medication service; link to full medication editor; kiosk-only presentation.
Not here: inline editor implementation (kiosk_medications_embed.js), Home/Schedule timelines, or ICE/emergency PDF flows.
"""

import html as html_module

from . import html_primitives as hp


# Profile/API-sourced strings must be escaped for HTML text and attributes; fixed UI literals below need not.


def _timed_row_html(m: dict, t: str) -> str:
    name = html_module.escape(m.get("name", "?"))
    done = m.get("status") == "done"
    med_id = m.get("id")
    bar = '<span class="timeline-bar-med timeline-bar-med--health"></span>'

    def actions_timed(lbl: str, done_flag: bool) -> str:
        if med_id is None:
            return ""
        mid = html_module.escape(str(med_id))
        slot = html_module.escape(str(t), quote=True)
        btn_mod = (
            " timeline-action-btn--compact"
            if done_flag
            else " timeline-action-btn--med-dose"
        )
        return (
            f'<div class="med-card__actions"><button type="button" '
            f'class="med-taken-btn timeline-action-btn{btn_mod}" data-med-id="{mid}" '
            f'data-med-time="{slot}" data-med-done="{str(done_flag).lower()}">{lbl}</button></div>'
        )

    if done:
        return (
            f'<div class="timeline-item med-manage-row med-row--folded">{bar}'
            f'<article class="med-card med-card--done med-card--folded">'
            f'<div class="med-card__folded-inner">'
            f'<p class="med-card__title">{name}</p>'
            f'<span class="med-card__folded-status">Done ✓</span>'
            f"{actions_timed('Undo', True)}</div></article></div>"
        )

    freq = (m.get("frequency") or "").strip()
    inline = f" · {html_module.escape(str(t))}"
    if freq:
        inline = inline + " · " + html_module.escape(freq)
    return (
        f'<div class="timeline-item med-manage-row med-row--open">{bar}'
        f'<article class="med-card med-card--pending med-card--open">'
        f'<div class="med-card__open-inner">'
        f'<div class="med-card__open-text">'
        f'<p class="med-card__title">{name}<span class="med-card__title-inline">{inline}</span></p>'
        f"</div>"
        f'<span class="med-card__dose-status med-card__dose-status--pending">'
        f"Not done</span>"
        f"{actions_timed('Take', False)}</div></article></div>"
    )


def _prn_btn_html(med_id: int, label: str, action: str, compact: bool) -> str:
    mid = html_module.escape(str(med_id))
    act = html_module.escape(action, quote=True)
    btn_mod = " timeline-action-btn--compact" if compact else " timeline-action-btn--med-dose"
    return (
        f'<button type="button" class="med-taken-btn timeline-action-btn{btn_mod}" '
        f'data-med-id="{mid}" data-med-time="prn" data-prn-action="{act}">{label}</button>'
    )


def _prn_row_html(m: dict) -> str:
    name = html_module.escape(m.get("name", "?"))
    lt = m.get("last_taken")
    med_id = m.get("id")
    bar = '<span class="timeline-bar-med timeline-bar-med--health"></span>'
    title_prn = f"{name} (PRN)"
    doses = int(m.get("doses_today") or 0)
    max_raw = m.get("max_daily")
    if max_raw is not None and str(max_raw).strip() != "":
        try:
            max_d = int(max_raw)
            if max_d <= 0:
                max_d = None
        except (TypeError, ValueError):
            max_d = None
    else:
        max_d = None
    can_take = max_d is None or doses < max_d

    freq = (m.get("frequency") or "").strip()
    inline = ""
    if freq:
        inline = f'<span class="med-card__title-inline"> · {html_module.escape(freq)}</span>'
    last_line = ""
    if doses > 0 and lt:
        last_line = (
            f'<p class="med-card__meta">Last: {html_module.escape(str(lt))}</p>'
        )
    limit_line = ""
    if max_d is not None and not can_take:
        limit_line = (
            f'<p class="med-card__meta med-card__prn-limit-note" role="status">'
            f"Daily limit reached for today ({doses} of {max_d}). "
            f"Use Undo if the last dose was logged by mistake."
            f"</p>"
        )

    if med_id is None:
        actions_html = ""
    else:
        parts: list[str] = []
        if doses > 0:
            parts.append(_prn_btn_html(int(med_id), "Undo", "undo", True))
        if can_take:
            parts.append(_prn_btn_html(int(med_id), "Take", "take", doses > 0))
        actions_html = f'<div class="med-card__actions">{"".join(parts)}</div>'

    state_done = doses > 0
    card_mod = " med-card--done" if state_done else " med-card--pending"
    if doses == 0:
        status_html = (
            f'<span class="med-card__dose-status med-card__dose-status--pending">'
            f"Not taken today</span>"
        )
    else:
        extra = f" ({doses} today)" if doses > 1 else ""
        status_html = (
            f'<span class="med-card__folded-status">Taken ✓{extra}</span>'
        )

    return (
        f'<div class="timeline-item med-manage-row med-row--open">{bar}'
        f'<article class="med-card med-card--prn med-card--open{card_mod}">'
        f'<div class="med-card__open-inner">'
        f'<div class="med-card__open-text">'
        f'<p class="med-card__title">{title_prn}{inline}</p>'
        f"{last_line}{limit_line}</div>"
        f"{status_html}"
        f"{actions_html}</div></article></div>"
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
            f'<div class="timeline-card timeline-card--health-meds">'
            f'<div class="timeline-header timeline-header--med-batch">'
            f"{header_inner}</div><div class=\"timeline-list\">"
            f'{"".join(items_html)}</div></div>'
        )
        parts.append(hp.spacer(12))
    prn = data.get("prn_medications", [])
    if prn:
        prn_html = [_prn_row_html(m) for m in prn]
        prn_header = "PRN (As Needed)"
        parts.append(
            f'<div class="timeline-card timeline-card--health-meds">'
            f'<div class="timeline-header timeline-header--med-batch">'
            f"{prn_header}</div><div class=\"timeline-list\">"
            f'{"".join(prn_html)}</div></div>'
        )
    return "".join(parts)


def build_health_html(services, api_url: str) -> str:
    """Health screen: medications list and mark taken."""
    med_svc = services.get_medication_service()
    if not med_svc:
        return hp.kiosk_screen_blocked(
            "Health", hp.error_state("Health information unavailable")
        )

    result = med_svc.get_medication_data()
    if not result.success:
        return hp.kiosk_screen_blocked(
            "Health", hp.error_state("Could not load health information")
        )

    data = result.data or {}
    inner = _medication_lists_inner_html(data)
    med_hint = (
        "Mark today’s doses in the list above or from Home."
        if inner
        else "When medications are listed, mark doses here or from Home."
    )
    editor_block = (
        '<div class="timeline-card timeline-card--health-meds health-meds-editor-card" aria-labelledby="health-meds-edit-h">'
        + '<h2 class="kiosk-settings-card__title" id="health-meds-edit-h">Medications</h2>'
        + '<div class="kiosk-settings-card__body">'
        + hp.kiosk_caption(
            "Update the list on the Medications screen—the same editor as the web dashboard. "
            + med_hint
        )
        + hp.spacer(10)
        + '<button type="button" class="add-event-btn btn-large kiosk-settings-primary-btn" data-screen="medications">Edit medications</button>'
        + "</div></div>"
    )
    parts = [hp.kiosk_header("Health"), hp.spacer(16)]
    if not inner:
        parts.append(hp.empty_state("No medications listed"))
        parts.append(hp.spacer(16))
    else:
        parts.append(inner)
        parts.append(hp.spacer(16))
    parts.append(editor_block)
    return "".join(parts)


class HealthHandler:
    """Mark taken only; list editing is Health → Edit medications (shared web inline editor)."""

    def __init__(self, app):
        self._app = app

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> str:
        med_svc = self._app.services.get_medication_service()
        if not med_svc:
            return "medication service unavailable"
        if not hasattr(med_svc, "mark_medication_taken"):
            return "mark taken not supported"
        r = med_svc.mark_medication_taken(medication_id, time_slot, taken)
        if r.success:
            return "ok"
        return r.error or "failed"
