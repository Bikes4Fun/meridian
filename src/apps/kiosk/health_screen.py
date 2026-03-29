"""
Health: medications list on Health screen; full add/edit/delete in Settings.
"""

import html as html_module
import json
import logging

from . import html_primitives as hp

logger = logging.getLogger(__name__)

DEFAULT_MED_TIME_NAMES = ["Morning", "Noon", "Evening", "prn"]


def _timed_row_html(m: dict, t: str, *, editable: bool) -> str:
    name = html_module.escape(m.get("name", "?"))
    status_txt = "Done ✓" if m.get("status") == "done" else "Not done"
    med_id = m.get("id")
    btns = ""
    chk = ""
    if med_id is not None:
        mid = html_module.escape(str(med_id))
        slot = html_module.escape(str(t), quote=True)
        if editable:
            med_data = html_module.escape(
                json.dumps({"id": med_id, "name": m.get("name"), "time": t}),
                quote=True,
            )
            chk = (
                f'<input type="checkbox" class="med-select" data-med-id="{mid}" '
                f'aria-label="Select {name} for batch delete" title="">'
            )
            btns = (
                f'<span class="timeline-item-actions">'
                f'<button type="button" class="med-edit-btn timeline-action-btn" data-med="{med_data}">Edit</button>'
                f'<button type="button" class="med-delete-btn timeline-action-btn" data-med-id="{med_id}">Delete</button>'
                f"</span>"
            )
        else:
            done = m.get("status") == "done"
            lbl = "Undo" if done else "Taken"
            btns = (
                f' <button type="button" class="med-taken-btn" data-med-id="{mid}" '
                f'data-med-time="{slot}" data-med-done="{str(done).lower()}" '
                f'style="font-size:11px;padding:2px 6px;">{lbl}</button>'
            )
    return (
        f'<div class="timeline-item med-manage-row">{chk}<span class="timeline-bar-med"></span>'
        f'<span class="timeline-item-main">{name} • {status_txt}</span>{btns}</div>'
    )


def _prn_row_html(m: dict, *, editable: bool) -> str:
    name = html_module.escape(m.get("name", "?"))
    lt = m.get("last_taken")
    taken = m.get("status") == "taken"
    last = f"Last: {lt}" if lt else ("Taken ✓" if taken else "Not taken today")
    med_id = m.get("id")
    btns = ""
    chk = ""
    if med_id is not None:
        take_lbl = "Uncheck" if taken else "Take"
        mid = med_id
        mid_esc = html_module.escape(str(mid))
        take_btn = (
            f'<button type="button" class="med-taken-btn timeline-action-btn med-taken-btn--prn" '
            f'data-med-id="{mid}" data-med-time="prn" data-med-done="{str(taken).lower()}">{take_lbl}</button>'
        )
        if editable:
            med_data = html_module.escape(
                json.dumps({"id": mid, "name": m.get("name")}), quote=True
            )
            chk = (
                f'<input type="checkbox" class="med-select" data-med-id="{mid_esc}" '
                f'aria-label="Select {name} for batch delete" title="">'
            )
            btns = (
                f'<span class="timeline-item-actions">{take_btn}'
                f'<button type="button" class="med-edit-btn timeline-action-btn" data-med="{med_data}">Edit</button>'
                f'<button type="button" class="med-delete-btn timeline-action-btn" data-med-id="{med_id}">Delete</button>'
                f"</span>"
            )
        else:
            btns = (
                f' <button type="button" class="med-taken-btn" data-med-id="{mid}" '
                f'data-med-time="prn" data-med-done="{str(taken).lower()}" '
                f'style="font-size:11px;padding:2px 6px;">{take_lbl}</button>'
            )
    return (
        f'<div class="timeline-item med-manage-row">{chk}<span class="timeline-bar-event"></span>'
        f'<span class="timeline-item-main">{name} • {last}</span>{btns}</div>'
    )


def _medication_lists_inner_html(data: dict, *, editable: bool) -> str:
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
        items_html = [_timed_row_html(m, t, editable=editable) for m in meds]
        if editable:
            slot_attr = html_module.escape(str(t), quote=True)
            header_inner = (
                f'<label class="med-group-select-label">'
                f'<input type="checkbox" class="med-group-select" data-time-slot="{slot_attr}" '
                f'aria-label="Select all medications in this group" title="">'
                f"<span>{html_module.escape(t)}</span></label>"
            )
        else:
            header_inner = html_module.escape(t)
        parts.append(
            f'<div class="timeline-card"><div class="timeline-header timeline-header--med-batch">'
            f"{header_inner}</div><div class=\"timeline-list\">"
            f'{"".join(items_html)}</div></div>'
        )
        parts.append(hp.spacer(12))
    prn = data.get("prn_medications", [])
    if prn:
        prn_html = [_prn_row_html(m, editable=editable) for m in prn]
        if editable:
            prn_header = (
                '<label class="med-group-select-label">'
                '<input type="checkbox" class="med-group-select" data-time-slot="prn" '
                'aria-label="Select all PRN medications" title="">'
                "<span>PRN (As Needed)</span></label>"
            )
        else:
            prn_header = "PRN (As Needed)"
        parts.append(
            f'<div class="timeline-card"><div class="timeline-header timeline-header--med-batch">'
            f"{prn_header}</div><div class=\"timeline-list\">"
            f'{"".join(prn_html)}</div></div>'
        )
    return "".join(parts)


def build_health_html(services, api_url: str) -> str:
    """Health screen: medications list and mark taken (management lives in Settings)."""
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
    inner = _medication_lists_inner_html(data, editable=False)
    parts = [hp.kiosk_header("Health"), hp.spacer(16)]
    if not inner:
        parts.append(hp.empty_state("No medications listed"))
    else:
        parts.append(inner)
    return "".join(parts)


def build_health_management_html(services, api_url: str) -> str:
    """Settings section: medication management (list + add modal)."""
    med_svc = services.get("medication_service")
    if not med_svc:
        return hp.spacer(16) + hp.error_state("Medications unavailable")

    result = med_svc.get_medication_data()
    if not result.success:
        return hp.spacer(16) + hp.error_state("Error loading medications")

    data = result.data or {}
    group_times = data.get("medication_time_groups") or {}
    time_names = list(group_times.keys()) if group_times else DEFAULT_MED_TIME_NAMES
    inner = _medication_lists_inner_html(data, editable=True)
    parts = [
        hp.spacer(16),
        hp.kiosk_subheader("Medications"),
        hp.kiosk_caption(
            "Add, edit, or remove medications. Mark doses from Home or the Health screen."
        ),
        hp.spacer(12),
        (
            '<div id="medBatchBar" class="med-batch-bar">'
            '<span id="medBatchCount" class="med-batch-count">0 selected</span>'
            '<button type="button" id="medBatchDeleteBtn" class="med-batch-delete timeline-action-btn" disabled>Delete selected</button>'
            '<button type="button" id="medBatchClearBtn" class="timeline-action-btn">Clear selection</button>'
            "</div>"
        ),
        hp.spacer(8),
    ]
    if not inner:
        parts.append(hp.empty_state("No medications"))
    else:
        parts.append(inner)
    parts.append(_build_add_medication_modal(time_names))
    return "".join(parts)


def _build_add_medication_modal(time_names: list) -> str:
    """Add Medication button + modal form."""
    names = time_names if time_names else DEFAULT_MED_TIME_NAMES
    checkboxes = []
    for name in names:
        lbl = "As Needed" if name == "prn" else name
        checkboxes.append(
            f'<label><input type="checkbox" name="med_time" value="{html_module.escape(name)}"> '
            f"{html_module.escape(lbl)}</label>"
        )
    cb_html = "".join(f'<span style="margin-right:12px">{c}</span>' for c in checkboxes)
    return f"""
<div class="home-action-row" style="margin-top:16px;">
<button type="button" class="add-event-btn" id="addMedicationBtn">+ Add Medication</button>
</div>
<div id="medFormOverlay" class="event-overlay" style="display:none;">
<div class="event-modal" onclick="event.stopPropagation()">
<h3 id="medFormTitle" class="event-modal-title">Add Medication</h3>
<form id="medForm">
<input type="hidden" id="medId" value="">
<input type="text" id="medName" placeholder="Name" required class="event-input">
<input type="text" id="medDosage" placeholder="Dosage" class="event-input">
<div style="margin:8px 0;">Times: {cb_html}</div>
<div class="event-form-actions">
<button type="submit" class="event-btn event-btn-primary">Save</button>
<button type="button" id="medFormCancel" class="event-btn event-btn-secondary" onclick="var o=document.getElementById('medFormOverlay');if(o)o.style.display='none'">Cancel</button>
</div></form></div></div>"""


class HealthHandler:
    """Add/edit medication modal and form logic. Calls medication service."""

    def __init__(self, app):
        self._app = app

    def open_add_medication_modal(self) -> None:
        """Show Add Medication modal."""
        js = (
            "var t=document.getElementById('medFormTitle');if(t)t.textContent='Add Medication';"
            "var i=document.getElementById('medId');if(i)i.value='';"
            "var o=document.getElementById('medFormOverlay');if(o)o.style.display='flex';"
        )
        self._app._eval(js)

    def open_edit_medication_modal(self, medication_id: int) -> None:
        """Fetch med details, prefill form, show Edit modal."""
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            self._app._eval("alert('Medication service unavailable');")
            return
        r = med_svc.get_medication_for_edit(medication_id)
        if not r.success or not r.data:
            self._app._eval("alert('Could not load medication');")
            return
        d = r.data
        name_esc = json.dumps(d.get("name", ""))
        dosage_esc = json.dumps(d.get("dosage", ""))
        times = d.get("medication_times") or []
        check_js = ";".join(
            f"var c=document.querySelector('#medForm input[value={json.dumps(t)}]');if(c)c.checked=true"
            for t in times
        )
        js = (
            f"var t=document.getElementById('medFormTitle');if(t)t.textContent='Edit Medication';"
            f"var i=document.getElementById('medId');if(i)i.value='{medication_id}';"
            f"var n=document.getElementById('medName');if(n)n.value={name_esc};"
            f"var d=document.getElementById('medDosage');if(d)d.value={dosage_esc};"
            "document.querySelectorAll('#medForm input[name=med_time]').forEach(function(c){c.checked=false;});"
            f"{check_js};"
            "var o=document.getElementById('medFormOverlay');if(o)o.style.display='flex';"
        )
        self._app._eval(js)

    def add_medication(self, payload_json: str) -> str:
        """POST medication. Returns 'ok' or error."""
        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError as e:
            return str(e)
        name = data.get("name")
        medication_times = data.get("medication_times") or []
        if not name:
            return "name required"
        if not medication_times:
            return "Select at least one time"
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        r = med_svc.add_medication(
            {
                "name": name,
                "medication_times": medication_times,
                "dosage": data.get("dosage") or None,
            }
        )
        if r.success:
            self._app._navigate_to("settings")
            return "ok"
        return r.error or "failed"

    def update_medication(self, medication_id: int, payload_json: str) -> str:
        """PUT medication. Returns 'ok' or error."""
        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError as e:
            return str(e)
        name = data.get("name")
        medication_times = data.get("medication_times") or []
        if not name:
            return "name required"
        if not medication_times:
            return "Select at least one time"
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        r = med_svc.update_medication(
            medication_id,
            {
                "name": name,
                "medication_times": medication_times,
                "dosage": data.get("dosage") or None,
            },
        )
        if r.success:
            self._app._navigate_to("settings")
            return "ok"
        return r.error or "failed"

    def delete_medication(self, medication_id: int) -> str:
        """DELETE medication. Returns 'ok' or error."""
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        r = med_svc.delete_medication(medication_id)
        if r.success:
            self._app._navigate_to("settings")
            return "ok"
        return r.error or "failed"

    def delete_medications_batch(self, medication_ids_json: str) -> str:
        """DELETE multiple medications (Settings batch). Returns 'ok' or error."""
        try:
            raw_ids = json.loads(medication_ids_json)
        except json.JSONDecodeError as e:
            return str(e)
        if not raw_ids:
            return "no medications selected"
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        seen = set()
        for x in raw_ids:
            try:
                mid = int(x)
            except (TypeError, ValueError):
                return "invalid id"
            if mid in seen:
                continue
            seen.add(mid)
            r = med_svc.delete_medication(mid)
            if not r.success:
                return r.error or "failed"
        self._app._navigate_to("settings")
        return "ok"

    def mark_medication_taken(
        self, medication_id: int, time_slot: str, taken: bool
    ) -> str:
        """Mark medication time slot taken or not. Returns 'ok' or error."""
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        if not hasattr(med_svc, "mark_medication_taken"):
            return "mark taken not supported"
        r = med_svc.mark_medication_taken(medication_id, time_slot, taken)
        if r.success:
            return "ok"
        return r.error or "failed"
