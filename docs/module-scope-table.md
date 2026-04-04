# Module header scope (kiosk, server container, webapp JS)

Top-of-file comments only: what each module owns and what it deliberately does not. Paths are repo-relative.

| File | Summary | Scope (does) | Not here |
|------|---------|--------------|----------|
| `src/apps/kiosk/health_screen.py` | Health meds list + mark-taken bridge | Render meds from medication service; kiosk presentation | Med list editing (Settings + inline JS), Home/Schedule timelines, ICE/PDF |
| `src/apps/kiosk/home_screen.py` | Home layout + Up Next / timeline | Merge medications + calendar; HTML for injected regions | Event modal (`events_handler`), nav (`app`), other screens |
| `src/apps/kiosk/events_handler.py` | Schedule + calendar overlay + `EventsHandler` | Calendar DOM strings; bridge + pywebview eval | Home layout, Flask routes, non-calendar APIs |
| `src/apps/kiosk/emergency_screen.py` | Read-only emergency profile HTML | Presentation + photo fetch for this screen | Printing (`emergency_print`), alert poll (`app`), server PDF gen |
| `src/apps/kiosk/emergency_print.py` | Client emergency PDF → printer | Client print pipeline | Emergency HTML, alert routing, PDF API on server |
| `src/apps/kiosk/clock_widget.py` | Clock HTML fragment | Static markup; any screen can pass `services` | Per-second updates / eval (`app`) |
| `src/apps/kiosk/checkin_screen.py` | Family Locations + `LocationHandler` | Layout + hooks for `map_widget` / kiosk JS | Leaflet (`kiosk.js`), check-in creation UX, location API impl |
| `src/apps/kiosk/chat_screen.py` | Chat grid + entry webview | Contacts list; `open_chat` / `open_chat_with_call` | In-page Sendbird, contact admin APIs |
| `src/apps/kiosk/map_widget.py` | Map markers + container HTML | Data shaping + embed fragment | Leaflet setup, check-in POST, named-places API impl |
| `src/apps/kiosk/medications_screen.py` | Medications screen shell | Panel + root div for embed JS | Row editor, save/delete calls, webapp Settings host |
| `src/apps/kiosk/settings_screen.py` | Settings + monitors strip | Primitives + monitor rows (stove id for live text) | Temp polling (`app` + sensor), med row editing |
| `src/apps/kiosk/monitors_screen.py` | Monitor row/section HTML | Small presentational blocks | Sensor drivers, thresholds, API calls |
| `src/apps/kiosk/html_primitives.py` | Shared kiosk HTML helpers | Reusable markup strings; tokens in CSS | Service fetch, per-screen layout, emergency form rows, webapp |
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

> Kiosk Health screen: medications list HTML and “mark taken” bridge (HealthHandler → remote API).  
> Scope: render meds from medication service; kiosk-only presentation.  
> Not here: editing the medication list (Settings → Medications + inline JS), Home/Schedule timelines, or ICE/emergency PDF flows.

**`home_screen.py`**

> Kiosk Home screen: layout, Up Next + “what’s next today” timeline, and merged schedule item loading.  
> Scope: merge medications + calendar into sortable items; emit HTML for injected regions.  
> Not here: event modal markup (events_handler), nav/screen switching (app), or non-home screens.

**`events_handler.py`**

> Kiosk calendar UX: Schedule screen HTML (meds + events), event overlay markup, EventsHandler (add/edit/delete via remote calendar service).  
> Scope: calendar-facing DOM strings and bridge methods tied to pywebview eval.  
> Not here: Home layout, server Flask routes, or non-calendar APIs.

**`emergency_screen.py`**

> Kiosk Emergency screen: load emergency profile via remote service; build read-only HTML (patient, medical, contacts).  
> Scope: presentation + photo fetch for this screen only.  
> Not here: printing (emergency_print), alert activation/polling (app), or server-side PDF generation.

**`emergency_print.py`**

> Kiosk emergency print: fetch PDF bytes from remote emergency service, run OS print, optional status label updates.  
> Scope: client-side print pipeline only.  
> Not here: emergency screen HTML, alert routing, or implementing the PDF API on the server.

**`clock_widget.py`**

> Kiosk clock fragment: HTML for day, date, time, and period sprite (reads time service).  
> Scope: static markup for one widget; reusable on any screen that passes services.  
> Not here: per-second updates or pywebview eval (app owns refresh loops).

**`checkin_screen.py`**

> Kiosk Family Locations: screen HTML, check-in panel copy, map section + marker inputs; LocationHandler for “where is everyone”.  
> Scope: layout and data hooks consumed by map_widget / kiosk JS.  
> Not here: Leaflet init (kiosk.js), creating check-ins from this module, or location API implementation on the server.

**`chat_screen.py`**

> Kiosk Chat: contact grid HTML; ChatHandler fetches chat entry URL and opens a separate webview.  
> Scope: list contacts and bridge open_chat / open_chat_with_call.  
> Not here: Sendbird/session logic inside the chat web page, or contact administration APIs.

**`map_widget.py`**

> Kiosk map: marker payloads and map container HTML for the Family screen (uses location service + photo helper).  
> Scope: data shaping and HTML fragment for embedding.  
> Not here: Leaflet setup, check-in POST flows, or named-places API implementation.

**`medications_screen.py`**

> Kiosk Medications screen: shell HTML and root node for the shared inline medication editor (kiosk_medications_embed.js + meridian_medications_inline.js).  
> Scope: panel + placeholder div only.  
> Not here: row editor, save/delete API calls, or webapp Settings editor (different host element).

**`settings_screen.py`**

> Kiosk Settings: monitors section HTML, link into Medications screen, static kiosk copy.  
> Scope: composition of primitives + monitor rows (stove id for live updates).  
> Not here: live temperature polling (app + TemperatureSensor), or medication row editing.

**`monitors_screen.py`**

> Kiosk monitor fragments: section header + labeled reading row HTML (e.g. stove temp span id for JS/app updates).  
> Scope: small presentational building blocks for any screen.  
> Not here: sensor drivers, alert thresholds, or API calls.

**`html_primitives.py`**

> Kiosk markup primitives: nav, typography wrappers, loading/empty/error, layout, kiosk_button, contact/avatar snippets.  
> Scope: reusable HTML string builders only; design tokens live in kiosk CSS. Aligns with the kiosk/TV typography spec in-repo docs.  
> Not here: fetching services, per-screen composition (see *_screen.py), labeled form rows / section bars (emergency_screen), or webapp assets.

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
