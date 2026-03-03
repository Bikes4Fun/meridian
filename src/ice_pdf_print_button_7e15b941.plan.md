---
name: ICE PDF Print Button
overview: Add a GET endpoint that returns a POLST-style PDF of the ICE profile, and a small "Print ICE Document" button on the kiosk emergency screen (and optionally a web ICE page) that triggers the PDF. Uses reportlab for server-side PDF generation; no primary-physician field in current model.
todos: []
isProject: false
---

# ICE PDF and Print Button (Issue #22)

## Scope in this repo

- **Server**: Add `GET /api/family_circles/<family_circle_id>/ice/pdf` in [src/apps/server/api.py](src/apps/server/api.py) (the issue’s “server/app.py” refers to this Flask app).
- **Kiosk**: Add a small “Print ICE Document” button on the emergency screen that opens the PDF (e.g. in browser).
- **Web**: This repo has no ICE editor page (only checkin/login in [src/apps/webapp/web_client/](src/apps/webapp/web_client/)). The issue’s “ICE editor” (dementia_tv_python#3) is in another repo. Options: (1) add a minimal ICE view/print page here with a print button, or (2) only implement API + kiosk button and leave the web editor to the other repo. Plan assumes (2) unless you want a dedicated `/ice` view page in meridian.

## 1. PDF endpoint

- **Route**: `GET /api/family_circles/<family_circle_id>/ice/pdf`
- **Auth**: Same as existing routes: `_require_family_access(family_circle_id)` and existing `@app.before_request` (X-Family-Circle-Id, X-User-Id or session).
- **Handler**: Call `ice_profile_svc.get_ice_profile(family_circle_id)`. If no profile, return 404 or 400. Otherwise build PDF and return `Response(pdf_bytes, mimetype="application/pdf", headers={"Content-Disposition": "inline; filename=ice-profile.pdf"})`.

## 2. PDF generation (reportlab)

- **Dependency**: Add `reportlab` to [requirements.txt](requirements.txt). Prefer reportlab over weasyprint (pure Python, no system libs).
- **New module**: Add a small PDF builder (e.g. `src/apps/server/ice_pdf.py` or under `services/`) that:
  - Takes the ICE profile dict (and request base URL or uploads path for photo).
  - Builds a single-page (or multi if needed) PDF with POLST-aligned sections in this order:
    - Patient name, DOB, photo (photo: resolve from `care_recipients.photo_path` via [get_uploads_dir()](src/apps/server/api.py) same as [api_serve_photo](src/apps/server/api.py); care recipient is identified by `care_recipient_user_id`; if photo is stored under users, use same path resolution as photo serving).
    - **DNR / Full Code** — large, prominent, colored (e.g. red for DNR, green for Full Code).
    - Medical proxy name and phone; POA name and phone.
    - Diagnosis/conditions; medications with dosages; allergies.
    - Emergency contacts (from ice profile / emergency contacts).
    - Primary physician: not in current data model; omit or one line “Primary physician: —”.
    - Document date: use “Generated: ” (profile has `last_updated: None` currently).
  - **Border**: Bright pink/red rectangle around the page (POLST convention).
  - **Footer**: “Keep this document visible — post on refrigerator or front door”.

## 3. Kiosk: Print button on emergency screen

- **Data for URL**: The emergency widget is built in [create_emergency_layout_widget](src/apps/kiosk/emergency_profile_widget.py) and receives `layout`, `e_data`, `e_contacts`, `services`. The API base URL and family_circle_id are not currently passed. Add them to the services dict in [create_remote](src/apps/kiosk/api_client.py) (e.g. `_api_base_url`, `_family_circle_id`) so the kiosk can build `{base}/api/family_circles/{fc_id}/ice/pdf`.
- **Button**: In [emergency_profile_widget.py](src/apps/kiosk/emergency_profile_widget.py), add a small “Print ICE Document” button (e.g. at bottom or top of the layout). On press: open the PDF URL (e.g. `webbrowser.open(url)` or Kivy’s `OpenURL`). If the kiosk runs in kiosk mode without a browser, opening the URL may still trigger print dialog when the PDF is displayed elsewhere; alternatively, the button could open the same URL in a WebView or document viewer if available.

## 4. Optional: Web ICE page and button

- If you want a print surface inside this repo: add a minimal ICE view page (e.g. `/ice` or `/ice.html`) that loads ICE data from the existing `GET .../ice-profile` and shows a “Print ICE Document” button/link that points to `GET .../ice/pdf` (same origin). That reuses the same endpoint and keeps changes minimal.

## Data and edge cases

- **Photo in PDF**: Resolve from `care_recipients.photo_path`; if that’s a filename, resolve under `get_uploads_dir()`. If the app stores the care recipient’s photo under the user’s `photo_filename`, use the same resolution logic as `api_serve_photo` (user id = `care_recipient_user_id`).
- **Missing profile**: Endpoint returns 404 or 400 with a clear message; no silent fallback.
- **Primary physician / last_updated**: Omit or placeholder until the data model supports them; “Document last updated” can be “Generated: ”.

## Files to touch (summary)


| Area  | File                                                 | Change                                                        |
| ----- | ---------------------------------------------------- | ------------------------------------------------------------- |
| Deps  | `requirements.txt`                                   | Add `reportlab`                                               |
| API   | `src/apps/server/api.py`                             | Register `GET .../ice/pdf`, call PDF builder, return response |
| PDF   | New `src/apps/server/ice_pdf.py` (or under services) | Build POLST-style PDF from ICE dict                           |
| Kiosk | `src/apps/kiosk/api_client.py`                       | Expose `_api_base_url` and `_family_circle_id` in services    |
| Kiosk | `src/apps/kiosk/emergency_profile_widget.py`         | Add “Print ICE Document” button; open PDF URL from services   |


No change to existing comments; no formatting-only edits; minimal diffs.