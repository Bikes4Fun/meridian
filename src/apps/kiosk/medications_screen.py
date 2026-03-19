"""
Medications: list by time + PRN, add modal, form logic.
"""

import html as html_module
import json
import logging

from . import html_primitives as hp

logger = logging.getLogger(__name__)


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
            med_id = m.get("id")
            btns = ""
            if med_id is not None:
                med_data = html_module.escape(json.dumps({"id": med_id, "name": m.get("name"), "time": t}), quote=True)
                btns = f' <button type="button" class="med-edit-btn" data-med="{med_data}" style="font-size:11px;padding:2px 6px;">Edit</button> <button type="button" class="med-delete-btn" data-med-id="{med_id}" style="font-size:11px;padding:2px 6px;">Delete</button>'
            items_html.append(f'<div class="timeline-item"><span class="timeline-bar-med"></span><span>{name} • {status}</span>{btns}</div>')
        parts.append(f'<div class="timeline-card"><div class="timeline-header">{html_module.escape(t)}</div><div class="timeline-list">{"".join(items_html)}</div></div>')
        parts.append(hp.spacer(12))

    prn = data.get("prn_medications", [])
    if prn:
        prn_html = []
        for m in prn:
            name = html_module.escape(m.get("name", "?"))
            lt = m.get("last_taken")
            last = f"Last: {lt}" if lt else "Not taken today"
            med_id = m.get("id")
            btns = ""
            if med_id is not None:
                med_data = html_module.escape(json.dumps({"id": med_id, "name": m.get("name")}), quote=True)
                btns = f' <button type="button" class="med-edit-btn" data-med="{med_data}" style="font-size:11px;padding:2px 6px;">Edit</button> <button type="button" class="med-delete-btn" data-med-id="{med_id}" style="font-size:11px;padding:2px 6px;">Delete</button>'
            prn_html.append(f'<div class="timeline-item"><span class="timeline-bar-event"></span><span>{name} • {last}</span>{btns}</div>')
        parts.append(f'<div class="timeline-card"><div class="timeline-header">PRN (As Needed)</div><div class="timeline-list">{"".join(prn_html)}</div></div>')

    if not sorted_times and not prn:
        parts.append(hp.empty_state("No medications"))

    time_names = list(group_times.keys())
    add_modal = _build_add_medication_modal(time_names)
    parts.append(add_modal)
    return "".join(parts)


def _build_add_medication_modal(time_names):
    """Add Medication button + modal form."""
    checkboxes = []
    for name in time_names:
        lbl = "As Needed" if name == "prn" else name
        checkboxes.append(
            f'<label><input type="checkbox" name="med_time" value="{html_module.escape(name)}"> {html_module.escape(lbl)}</label>'
        )
    cb_html = "".join(f'<span style="margin-right:12px">{c}</span>' for c in checkboxes)
    return f'''
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
</div></form></div></div>'''


class MedicationsHandler:
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
        r = med_svc.add_medication({
            "name": name,
            "medication_times": medication_times,
            "dosage": data.get("dosage") or None,
        })
        if r.success:
            self._app._navigate_to("medications")
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
        r = med_svc.update_medication(medication_id, {
            "name": name,
            "medication_times": medication_times,
            "dosage": data.get("dosage") or None,
        })
        if r.success:
            self._app._navigate_to("medications")
            return "ok"
        return r.error or "failed"

    def delete_medication(self, medication_id: int) -> str:
        """DELETE medication. Returns 'ok' or error."""
        med_svc = self._app.services.get("medication_service")
        if not med_svc:
            return "medication service unavailable"
        r = med_svc.delete_medication(medication_id)
        if r.success:
            self._app._navigate_to("medications")
            return "ok"
        return r.error or "failed"
