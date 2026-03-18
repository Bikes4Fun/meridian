"""
Medications screen: full medication list by time + PRN.
"""

import html as html_module

from . import html_primitives as hp


def build_medications_html(services, api_url: str) -> str:
    """Build medications screen HTML: timed meds by group, then PRN."""
    med_svc = services.get("medication_service")
    if not med_svc:
        return hp.kiosk_header("Medications") + hp.spacer(16) + hp.error_state("Medications unavailable")

    result = med_svc.get_medication_data()
    if not result.success:
        return hp.kiosk_header("Medications") + hp.spacer(16) + hp.error_state("Error loading medications")

    data = result.data or {}
    time_groups = {}
    for m in data.get("timed_medications", []):
        t = m.get("time", "Unknown")
        time_groups.setdefault(t, []).append(m)
    group_times = data.get("medication_time_groups", {})
    sorted_times = sorted(time_groups.keys(), key=lambda x: group_times.get(x, "23:59:59"))

    parts = [hp.kiosk_header("Medications"), hp.spacer(16)]
    for t in sorted_times:
        meds = time_groups[t]
        if not meds:
            continue
        items_html = []
        for m in meds:
            name = html_module.escape(m.get("name", "?"))
            status = "Done ✓" if m.get("status") == "done" else "Not done"
            items_html.append(f'<div class="timeline-item"><span class="timeline-bar-med"></span><span>{name} • {status}</span></div>')
        parts.append(f'<div class="timeline-card"><div class="timeline-header">{html_module.escape(t)}</div><div class="timeline-list">{"".join(items_html)}</div></div>')
        parts.append(hp.spacer(12))

    prn = data.get("prn_medications", [])
    if prn:
        prn_html = []
        for m in prn:
            name = html_module.escape(m.get("name", "?"))
            lt = m.get("last_taken")
            last = f"Last: {lt}" if lt else "Not taken today"
            prn_html.append(f'<div class="timeline-item"><span class="timeline-bar-event"></span><span>{name} • {last}</span></div>')
        parts.append(f'<div class="timeline-card"><div class="timeline-header">PRN (As Needed)</div><div class="timeline-list">{"".join(prn_html)}</div></div>')

    if not sorted_times and not prn:
        parts.append(hp.empty_state("No medications"))

    return "".join(parts)
