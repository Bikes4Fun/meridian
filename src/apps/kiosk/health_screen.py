"""
Kiosk medication actions: HealthHandler bridges pywebview to the remote medication API.

The dedicated Health screen was removed; marking doses uses Home / Schedule timelines, and
editing the list uses Settings → Medications. Home header markup for “mark all scheduled” lives here.
"""

import html as html_module
import json


class HealthHandler:
    """Mark taken / mark-all / medications editor rows (pywebview.api → remote API)."""

    def __init__(self, app):
        self._app = app

    @staticmethod
    def mark_all_non_prn_button_js(reload_screen: str) -> str:
        target = html_module.escape(str(reload_screen or "home"), quote=True)
        return (
            "var toastMessage=pywebview.api.mark_all_non_prn_taken();"
            f"if(toastMessage&&typeof toastMessage.then==='function')toastMessage.then(function(toastMessageResolved){{if(toastMessageResolved)showToast(toastMessageResolved);pywebview.api.reload_screen('{target}');}});"
            f"else{{if(toastMessage)showToast(toastMessage);pywebview.api.reload_screen('{target}');}}"
        )

    @staticmethod
    def build_home_whats_next_header_row() -> str:
        """Home only: compact 'Mark all scheduled' beside WHAT'S NEXT TODAY (reloads home)."""
        action_js = HealthHandler.mark_all_non_prn_button_js("home")
        return (
            '<div class="timeline-header timeline-header--with-action">'
            '<span class="timeline-header__title">WHAT\'S NEXT TODAY</span>'
            f'<button type="button" class="timeline-action-btn timeline-action-btn--header-inline" '
            f'onclick="{action_js}" '
            'title="Mark every scheduled (non-PRN) dose still due today as taken" '
            'aria-label="Mark all scheduled non-PRN doses as taken for today">'
            "Mark all scheduled"
            "</button>"
            "</div>"
        )

    def _normalize_editor_rows(self, medication_data: dict) -> list[dict]:
        timed = (medication_data or {}).get("timed_medications") or []
        prn = (medication_data or {}).get("prn_medications") or []
        by_id: dict[str, dict] = {}

        def ensure_row(m: dict) -> dict:
            med_id = m.get("id")
            key = str(med_id or "")
            row = by_id.get(key)
            if not row:
                row = {
                    "id": med_id,
                    "name": m.get("name") or "",
                    "dosage": m.get("dosage") or "",
                    "frequency": m.get("frequency") or "",
                    "fda_rxcui": m.get("fda_rxcui") or "",
                    "medication_times": [],
                }
                by_id[key] = row
            return row

        for m in timed:
            row = ensure_row(m or {})
            slot = (m or {}).get("time") or ""
            if slot and slot not in row["medication_times"]:
                row["medication_times"].append(slot)

        for m in prn:
            row = ensure_row(m or {})
            if "prn" not in row["medication_times"]:
                row["medication_times"].append("prn")

        return list(by_id.values())

    def get_medications_editor_rows(self) -> str:
        med_svc = self._app.services.get_medication_service()
        if not med_svc:
            return json.dumps([])
        r = med_svc.get_medication_data()
        if not r.success:
            return json.dumps([])
        rows = self._normalize_editor_rows(r.data or {})
        return json.dumps(rows)

    def save_medications_editor_rows(
        self, rows_json: str, initial_snapshot_json: str
    ) -> str:
        """
        Returns status text for the kiosk medications editor toast/status message.
        Expected values include:
            - "ok" (save succeeded)
            - validation/service error text (shown to user)
        """
        med_svc = self._app.services.get_medication_service()
        if not med_svc:
            return "medication service unavailable"
        try:
            rows = json.loads(rows_json or "[]")
            initial = json.loads(initial_snapshot_json or "[]")
        except json.JSONDecodeError as e:
            return str(e)
        if not isinstance(rows, list) or not isinstance(initial, list):
            return "invalid medication payload"

        seen_names: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or "").strip()
            if not name:
                continue
            nk = name.lower()
            if nk in seen_names:
                return "Each medication name must be unique"
            seen_names.add(nk)

        current_by_id: dict[int, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            med_id = row.get("id")
            if isinstance(med_id, int) and med_id > 0:
                current_by_id[med_id] = row

        deleted_ids: set[int] = set()
        for old in initial:
            if not isinstance(old, dict):
                continue
            med_id = old.get("id")
            if isinstance(med_id, int) and med_id > 0 and med_id not in current_by_id:
                r = med_svc.delete_medication(med_id)
                if not r.success:
                    return r.error or "Delete medication failed"
                deleted_ids.add(med_id)

        for row in rows:
            if not isinstance(row, dict):
                continue
            med_id = row.get("id")
            has_id = isinstance(med_id, int) and med_id > 0
            name = (row.get("name") or "").strip()
            if not name:
                if has_id and med_id not in deleted_ids:
                    r = med_svc.delete_medication(med_id)
                    if not r.success:
                        return r.error or "Delete medication failed"
                    deleted_ids.add(med_id)
                continue

            times = row.get("medication_times")
            if not isinstance(times, list) or not times:
                times = ["Morning"]
            else:
                times = [str(t).strip() for t in times if str(t).strip()]
                if not times:
                    times = ["Morning"]

            payload = {
                "name": name,
                "medication_times": times,
                "fda_rxcui": ((row.get("fda_rxcui") or "").strip() or None),
            }
            dosage = (row.get("dosage") or "").strip()
            frequency = (row.get("frequency") or "").strip()
            if dosage:
                payload["dosage"] = dosage
            if frequency:
                payload["frequency"] = frequency

            if has_id:
                r = med_svc.update_medication(med_id, payload)
                if not r.success:
                    return r.error or "Update medication failed"
            else:
                r = med_svc.add_medication(payload)
                if not r.success:
                    return r.error or "Add medication failed"
        return "ok"

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

    def mark_all_non_prn_taken(self) -> str:
        """
        returns toast message eg.
            - "Marked 1 non-as-needed dose as taken."
            - "Marked 3 non-as-needed doses as taken."
            - etc.
        """

        med_svc = self._app.services.get_medication_service()
        if not med_svc:
            return "Medication service unavailable"

        r = med_svc.get_medication_data()
        if not r.success:
            return r.error or "Could not load medications"

        data = r.data or {}
        timed = data.get("timed_medications") or []
        to_mark: list[tuple[int, str]] = []
        for m in timed:
            if not isinstance(m, dict):
                continue
            if m.get("status") == "done":
                continue
            med_id = m.get("id")
            slot = str(m.get("time") or "").strip()
            if not (isinstance(med_id, int) and med_id > 0):
                continue
            if not slot or slot.lower() == "prn":
                continue
            to_mark.append((med_id, slot))

        if not to_mark:
            return "No non-as-needed doses pending for today."

        for med_id, slot in to_mark:
            mark_r = med_svc.mark_medication_taken(med_id, slot, True)
            if not mark_r.success:
                return mark_r.error or "Could not mark all doses"

        if len(to_mark) == 1:
            return "Marked 1 non-as-needed dose as taken."

        return f"Marked {len(to_mark)} non-as-needed doses as taken."
