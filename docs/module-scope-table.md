# Module header scope (kiosk, server container, webapp JS)

Top-of-file comments only: what each module owns and what it deliberately does not. Paths are repo-relative.

| File | Summary | Scope (does) | Not here |
|------|---------|--------------|----------|
| `src/apps/kiosk/health_screen.py` | Health meds list + Edit medications link + mark-taken bridge | Render meds; entry to full editor; kiosk presentation | Inline editor JS (`kiosk_medications_embed`), Home/Schedule timelines, ICE/PDF |
| `src/apps/kiosk/home_screen.py` | Home layout + Up Next / timeline + clock | Merge medications + calendar; clock HTML from time service | Event modal (`schedule_screen`), nav (`app`), other screens |
| `src/apps/kiosk/schedule_screen.py` | Schedule screen HTML + event overlay markup | Merged timeline strings; modal shell (`#eventEditingId` hidden) | Live modal open/prefill (`kiosk.js` `meridianKioskEvents`), calendar API |
| `src/apps/kiosk/emergency_screen.py` | Emergency profile HTML + client PDF print | Presentation + photo fetch; `trigger_emergency_print` for alerts/button | Alert poll (`app`), server PDF generation |
| `src/apps/kiosk/checkin_screen.py` | Family Locations + `LocationHandler` | Layout + hooks for `map_widget` / kiosk JS | Leaflet (`kiosk.js`), check-in creation UX, location API impl |
| `src/apps/kiosk/chat_screen.py` | Chat grid + `open_chat_window` + entry webview | Contacts list; `open_chat` / `open_chat_with_call` | In-page Sendbird, contact admin APIs |
| `src/apps/kiosk/map_widget.py` | Map markers + container HTML | Data shaping + embed fragment | Leaflet setup, check-in POST, named-places API impl |
| `src/apps/kiosk/settings_screen.py` | Settings + monitors; meds editor shell (`build_medications_html`) | Monitor row HTML, settings copy; full editor panel for Medications nav | Temp polling (`app` + sensor), Health timeline |
| `src/apps/kiosk/html_primitives.py` | Shared kiosk HTML helpers | Markup strings, `kiosk_screen_blocked`, `form_row_html` / `section_bar_html`, tokens in CSS | Service fetch, per-screen business logic, webapp |
| `src/apps/kiosk/app.py` | pywebview kiosk app | Window/bridge, registry, clock/stove/alert/call loops | Per-screen HTML, REST/Flask, DB services (server skips this import) |
| `src/apps/kiosk/api_client.py` | Kiosk HTTP + `KioskRemoteServiceContainer` | Remote clients + local time; no UI | Flask, pywebview, server `ServiceContainer` |
| `src/apps/server/container.py` | Server DB service container | Lazy getters for API process | Kiosk HTTP clients, kiosk imports, route definitions |
| `src/apps/webapp/web_client/meridian_api_base.js` | Shared browser utilities | `window` helpers: login redirect, API base, escape | Feature pages, fetch wrappers |
| `src/apps/webapp/web_client/medications.js` | Health/Settings meds UI | `#healthMedsTakeHost` / `#settingsMedsEditor` + fetches | Kiosk embed (`kiosk_medications_embed.js`), FDA, server routes |
| `src/apps/webapp/web_client/meridian_medications_inline.js` | Inline med row editor | Rows, DOM collect, diff save vs `/medications` | Page layout, ICE non-med fields, Python |
| `src/apps/webapp/web_client/events.js` | Events tab | `#pageEvents` list + modal CRUD | Kiosk schedule, meds merge, month calendar |
| `src/apps/webapp/web_client/ice_editor.js` | ICE webapp page | Medical block + contacts/photos/DNR APIs | Kiosk emergency UI, print, pywebview bridge |

## Full header text (reference)

<details>
<summary>Python modules</summary>

**`health_screen.py`**

> Kiosk Health screen: medications list HTML, Edit medications entry (nav to full editor), and “mark taken” bridge (HealthHandler → remote API).  
> Scope: render meds from medication service; kiosk-only presentation.  
> Not here: inline editor implementation (`kiosk_medications_embed.js`), Home/Schedule timelines, or ICE/emergency PDF flows.

**`home_screen.py`**

> Kiosk Home screen: layout, Up Next + “what’s next today” timeline, merged schedule item loading, and clock fragment (time service).  
> Scope: merge medications + calendar into sortable items; emit HTML for injected regions.  
> Not here: event modal markup (`schedule_screen`), nav/screen switching (app), or non-home screens.

**`schedule_screen.py`**

> Kiosk Schedule screen: merged meds + events timeline, Add Event button, event modal overlay markup (hidden `#eventEditingId`).  
> Scope: HTML string builders only. Live modal open/prefill: `kiosk.js` (`meridianKioskEvents`); submit/delete: `pywebview.api` → `app.py` (`_submit_event_form` / `_delete_event`).  
> Not here: calendar API calls (app / api_client).

**`emergency_screen.py`**

> Kiosk Emergency screen: load emergency profile via remote service; build read-only HTML (patient, medical, contacts).  
> Scope: presentation + photo fetch; client-side emergency PDF print (`trigger_emergency_print` for alerts/button).  
> Not here: alert activation/polling (app), or server-side PDF generation.

**`checkin_screen.py`**

> Kiosk Family Locations: screen HTML, check-in panel copy, map section + marker inputs; LocationHandler for “where is everyone”.  
> Scope: layout and data hooks consumed by map_widget / kiosk JS.  
> Not here: Leaflet init (kiosk.js), creating check-ins from this module, or location API implementation on the server.

**`chat_screen.py`**

> Kiosk Chat: contact grid HTML; `open_chat_window` (subprocess pywebview for chat URL); ChatHandler fetches chat entry URL.  
> Scope: list contacts and bridge open_chat / open_chat_with_call.  
> Not here: Sendbird/session logic inside the chat web page, or contact administration APIs.

**`map_widget.py`**

> Kiosk map: marker payloads and map container HTML for the Family screen (uses location service + photo helper).  
> Scope: data shaping and HTML fragment for embedding.  
> Not here: Leaflet setup, check-in POST flows, or named-places API implementation.

**`settings_screen.py`**

> Kiosk Settings: monitors section HTML, static kiosk copy; `build_medications_html` is the full editor shell when navigating to Medications.  
> Scope: composition of primitives + monitor rows (stove id for live updates); meds editor panel + root div for embed JS.  
> Not here: live temperature polling (app + TemperatureSensor), Health timeline / Edit medications entry (health_screen).

**`html_primitives.py`**

> Kiosk markup primitives: nav, typography wrappers, loading/empty/error, kiosk_screen_blocked, form_row/section_bar, layout, kiosk_button, contact/avatar snippets.  
> Scope: reusable HTML string builders only; design tokens live in kiosk CSS. Aligns with the kiosk/TV typography spec in-repo docs.  
> Not here: fetching services or per-screen business logic (see *_screen.py); webapp assets.

**`app.py`**

> Meridian Kiosk client (pywebview): window/bridge, screen registry, background loops (clock, stove push, alert poll, incoming call).  
> Scope: orchestration and navigation; uses api_client.create_kiosk_remote() / KioskRemoteServiceContainer (not the server DB container).  
> Not here: per-screen HTML beyond dispatch; REST/Flask; database services. Server does not import this module.

**`api_client.py`**

> Kiosk-side HTTP clients: GET/POST helpers, Remote* services, LocalTimeService, KioskRemoteServiceContainer (typed getters over those clients).  
> Scope: talk to the Meridian API from the kiosk process; no UI.  
> Not here: Flask routes, pywebview, or server DB ServiceContainer (see server container.py).

**`container.py`** (server)

> Server-only: lazy DB-backed service getters (one DatabaseManager, shared service cache).  
> Scope: construct domain services for the Flask/API process.  
> Not here: kiosk remote clients, kiosk package imports, or Flask route definitions.

</details>

<details>
<summary>JavaScript modules</summary>

**`meridian_api_base.js`**

> Shared browser helpers (login redirect, API base resolution, HTML/attr escaping). Load before app / ice_editor / meds modules.  
> Scope: small globals on window. Not: feature pages, fetch wrappers, or kiosk-only scripts beyond depending on these utilities.

**`medications.js`**

> Webapp Health/Settings meds UI: today’s list + mark-taken; Settings inline editor wiring. MeridianMedications.init(...). Requires meridian_medications_inline.js.  
> Scope: DOM for #healthMedsTakeHost / #settingsMedsEditor and credentialed fetches. Not: kiosk embed (kiosk_medications_embed.js), FDA search, or server routes.

**`meridian_medications_inline.js`**

> Shared medication row editor: HTML for rows, collect from DOM, sequential diff save/delete vs /medications (api base from caller).  
> Scope: MeridianMedicationsInline + reusable by webapp Settings, ICE editor, kiosk embed. Not: page layout, ICE non-med fields, or Python.

**`events.js`**

> Webapp Events tab: list today’s calendar events, add/edit/delete modal + credentialed API calls. MeridianEvents.init(...) from app.js.  
> Scope: #pageEvents only. Not: kiosk schedule screen, medications merge, or shared calendar month view.

**`ice_editor.js`**

> Webapp ICE (emergency profile) editor: medical block uses MeridianMedicationsInline; contacts/photos/DNR via emergency-profile + contacts APIs. __API_URL__ baked at build.  
> Scope: ice_editor page behavior. Not: kiosk emergency screen, PDF print flow, or kiosk-only bridge APIs.

</details>

When you change a module’s responsibilities, update its header in source first, then refresh this table.
