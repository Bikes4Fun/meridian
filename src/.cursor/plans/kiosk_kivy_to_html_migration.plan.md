---
name: Kiosk Kivy to HTML Migration
overview: Complete step-by-step transition of the kiosk from Kivy to HTML5, CSS3, and vanilla JavaScript. Uses session-based auth via Python launcher, web/ structure (no build step), and detailed phase-by-phase implementation guidance from both plans.
todos:
  - id: shell
    content: Create web/kiosk.html and web/kiosk.css with nav, screen containers, design tokens
    status: pending
  - id: bootstrap
    content: "Add kiosk.js API wrapper (credentials: include), nav switching, screen loaders"
    status: pending
  - id: home
    content: Implement Home screen (clock block 3.1-3.2, meds 3.3, events 3.4)
    status: pending
  - id: emergency
    content: Implement Emergency screen (4.1-4.5 layout, fetch, print, alert border)
    status: pending
  - id: family
    content: Implement Family screen (5.1-5.3 columns + Leaflet map)
    status: pending
  - id: chat
    content: Implement Chat screen (6.1-6.3 grid, chat-session-url, window.open)
    status: pending
  - id: server
    content: Add /kiosk/ routes to api.py (kiosk.html, kiosk.js, icons)
    status: pending
  - id: launcher
    content: Create __main__.py launcher (login + pywebview/Chrome/webbrowser)
    status: pending
  - id: cleanup
    content: Add --web flag to main.py; remove Kivy after validation
    status: pending
isProject: false
---

# Kiosk: Kivy to HTML5/CSS3/Vanilla JS — Complete Migration Plan

## Architecture

```
[Python launcher: apps/kiosk/__main__.py]
  1. POST /api/login with { user_id, family_circle_id } → establishes session cookie
  2. Open pywebview (or Chrome kiosk / webbrowser) at http://SERVER_URL/kiosk/

[Flask server] routes:
  GET /kiosk/           → kiosk.html
  GET /kiosk/kiosk.js  → kiosk.js
  GET /kiosk/kiosk.css → kiosk.css (if separate)
  GET /kiosk/icons/<f> → icons (sunrise.png, noon.png, evening.png, night.png)
  /fonts/ already works (shared with webapp)

[kiosk.html + kiosk.js]
  - All fetch() with credentials: 'include' → session cookie sent
  - Photos: <img src="/api/users/{id}/photo"> works (cookie sent automatically)
  - Same-origin, no CORS, no X-User-Id headers needed
```

**Why session login:** Launcher logs in first; session cookie is sent automatically. Photos and all API calls work with `credentials: 'include'`—no blob fetch, signed URLs, or header auth needed.

---

## File Structure

```
apps/kiosk/
  web/                    # Served directly, no build step
    kiosk.html            # HTML skeleton, links to kiosk.css, kiosk.js
    kiosk.css             # Design tokens, layout, typography, alert flash
    kiosk.js              # Screen logic, clock, API fetches, map, alert polling
  icons/                  # sunrise.png, noon.png, evening.png, night.png (add if missing)
  __main__.py             # Python launcher: login → open browser
  api_client.py           # Keep for reference (unused)
  [Kivy files]            # Keep initially for rollback; remove after validation
```

No build step: same-origin, so `fetch('/api/...')` works. Add build_kiosk later only if cross-origin needed.

---

## Launcher: apps/kiosk/**main**.py

**Env vars:** `KIOSK_USER_ID`, `FAMILY_CIRCLE_ID` (or `PATIENT_FAMILY_CIRCLE_ID`), `API_URL`

**Flow:**

1. Start API server (if not running) — same as main.py background thread
2. POST `/api/login` with `{ user_id, family_circle_id }` → session cookie
3. Build URL: `{API_URL}/kiosk/`
4. Open in order of preference:
  - **pywebview** — native window, no chrome, controllable
  - **Chrome/Chromium** — `subprocess` with `--app=URL` or `--kiosk`
  - **webbrowser.open(URL)** — fallback

**Run:** `python -m apps.kiosk`

---

## Design Token Mapping

From [meridian-design-system-2.md](info/meridian-design-system-2.md) and [screen_primitives.py](src/apps/kiosk/screen_primitives.py):


| Token          | Design System | screen_primitives | CSS Variable                          |
| -------------- | ------------- | ----------------- | ------------------------------------- |
| hero           | 72px / 700    | hero 72px         | `--font-hero: 72px`                   |
| header         | 56px / 700    | header 56px       | `--font-header: 56px`                 |
| subheader      | 40px / 700    | subheader 40px    | `--font-subheader: 40px`              |
| body_large     | 32px / 400    | body_large 32px   | `--font-body-large: 32px`             |
| body           | 28px / 400    | body 28px         | `--font-body: 28px`                   |
| caption        | 24px / 500    | caption 24px      | `--font-caption: 24px`                |
| nav            | 32px          | nav_tab 32px      | `--font-nav: 32px`                    |
| line-height    | 1.5–1.7       | 1.6               | `--line-height: 1.6`                  |
| touch target   | 120×120 min   | 120px             | `min-height: 120px; min-width: 120px` |
| safe margin    | 40–48px       | padding 40        | `--safe-margin: 40px`                 |
| background     | —             | (0.95,0.95,0.93)  | `#f2f2ee`                             |
| text           | —             | (0.1,0.1,0.1)     | `#1a1a1a`                             |
| med surface    | —             | (0.94,0.96,0.98)  | `#f0f5fa`                             |
| events surface | —             | (0.96,0.98,0.94)  | `#f5faf0`                             |


---

## Phase 1: Shell and CSS

### 1.1 Create web/kiosk.html

- DOCTYPE html5, lang="en", charset UTF-8
- Viewport: `width=1080, height=1920` or `width=device-width` + CSS for 1080×1920 TV
- Title: "Meridian Kiosk"
- Link: `/kiosk/kiosk.css` (or inline in `<style>`)
- Script: `/kiosk/kiosk.js`
- Body structure:
  - `#kiosk-nav` — fixed bottom nav bar (4 buttons: Home, Emergency, Family, Chat)
  - `#kiosk-content` — main content area
  - `#screen-home`, `#screen-emergency`, `#screen-family`, `#screen-chat` — initially hidden, shown by JS

### 1.2 Create web/kiosk.css

- `@font-face` for Atkinson Hyperlegible (Regular, Bold) — path `/fonts/` (shared with webapp)
- CSS custom properties for design tokens (above)
- Base: `font-family`, `line-height`, `color`, `background`
- Layout: 1080×1920 viewport, `box-sizing: border-box`, flexbox
- Nav bar: 120px height, horizontal flex, 4 equal buttons, min 120px touch target
- Screen sections: `display: none` by default; `.active { display: flex }` (or block)
- Typography: `.kiosk-hero`, `.kiosk-header`, `.kiosk-subheader`, `.kiosk-body`, `.kiosk-body-large`, `.kiosk-caption`
- Alert flash: `@keyframes alert-flash` for orange border when `body.alert-active`

### 1.3 Add /kiosk/ routes to api.py

In [api.py](src/apps/server/api.py):

- `@app.route("/kiosk/")` → `send_from_directory(kiosk_web_dir, "kiosk.html")`
- `@app.route("/kiosk/<path:path>")` → serve from kiosk_web_dir (kiosk.js, kiosk.css, icons)
- Add `/kiosk` to "public" routes in `set_user_id` so `/kiosk/`* does not require session (page loads, then JS uses session cookie for API)

---

## Phase 2: API and Navigation

### 2.1 kiosk.js — fetch wrapper

- **Session auth:** All `fetch(url, { credentials: 'include' })` — no headers needed; session cookie sent automatically
- `function apiFetch(path, options)` — wraps fetch, adds `credentials: 'include'`, base path `/api` or full URL
- No `user_id`/`family_circle_id` from URL — launcher already logged in

### 2.2 Navigation and screen switching

- Nav buttons: `data-screen="home"` etc.
- On click: hide all `#screen-`*, show `#screen-{name}`, set nav active state
- Initial screen: `home` (or `chat` to match Kivy default)
- On screen enter: call loaders (Family → load map; Chat → load contacts)

---

## Phase 3: Home Screen

Map from [home_screen.py](src/apps/kiosk/home_screen.py).

### 3.1 Layout

- Top 35%: clock block
- Bottom 65%: two columns (50/50) — Medications left, Events right

### 3.2 Clock block

- Row 1: Day (header 56px), Time-of-day label (subheader 40px), Time-of-day icon (100px)
- Row 2: Time (hero 72px, centered)
- Row 3: Date (subheader), Year (subheader, right)
- Time: `new Date()` — format like `%I:%M %p` (e.g. 2:30 PM); strip leading zero on hour
- Day: `toLocaleDateString(undefined, { weekday: 'long' })`
- Date: `toLocaleDateString(undefined, { month: 'long', day: 'numeric' })`
- Year: `getFullYear()`
- Time-of-day: hour < 12 → Morning; < 17 → Afternoon; else Evening (match [api_client LocalTimeService](src/apps/kiosk/api_client.py))
- Icon: `<img src="/kiosk/icons/sunrise.png">` etc., keyed by time-of-day
- `setInterval(updateClock, 1000)` for live time

### 3.3 Medications panel

- Title: "Medications" (header)
- Fetch `GET /api/family_circles/{id}/medications` (need family_circle_id — from session or store at init)
- Parse `timed_medications`, `medication_time_groups`, `prn_medications` (see home_screen `_load_medications`)
- Display: "Morning:", "• Aspirin: Done", etc.
- Background: `#f0f5fa`

### 3.4 Events panel

- Title: "Today's Events" (header)
- Fetch `GET /api/family_circles/{id}/calendar/events?date=YYYY-MM-DD`
- Display: "• Event 1", "• Event 2" or "No events today"
- Background: `#f5faf0`
- Load on init and when Home shown; refresh every 5 min

**Note on family_circle_id:** Kiosk gets it from session. Add `GET /api/session` at init to read `family_circle_id` (and `user_id`) for API calls, or pass from launcher via URL param and store.

---

## Phase 4: Emergency Screen

Map from [emergency_screen.py](src/apps/kiosk/emergency_screen.py).

### 4.1 Data fetch

- `GET /api/family_circles/{id}/emergency-profile`
- Response: `profile`, `medical`, `emergency_contacts`, `poa_name`, `poa_phone`, `care_recipient_user_id`, etc.

### 4.2 Layout

- Blue bar: "IN CASE OF EMERGENCY" (bg `#4080d9`)
- Personal block: "PERSONAL INFORMATION" red bar (rgb 0.75,0.2,0.2), form rows:
  - FULL NAME, DOB, CODE STATUS (DNR/Full Code), ALLERGIES, MEDICATIONS, HEALTH
- Photo: care recipient — `<img src="/api/users/{id}/photo">` (session cookie works)
- Emergency contacts: "EMERGENCY CONTACTS" red bar, CONTACT 1, 2, …; MEDICAL PROXY; POA

### 4.3 Form row styling

- Label (caption): fixed width ~200px
- Value (body_large): wraps, no truncation

### 4.4 Print button

- "Print Emergency Document" button
- On click: `window.open('/api/family_circles/{id}/emergency-profile/pdf', '_blank')` — user triggers browser Print

### 4.5 Alert border

- When `alert_activated`: add `alert-active` to body
- CSS: `@keyframes alert-flash` alternating orange border (`#ff8000` / `#ff5000`), 0.5s
- Poll: `GET /api/emergency/alert/status` every 2s; when `activated` true → show Emergency, add class; when false → remove

---

## Phase 5: Family Screen

Map from [checkin_screen.py](src/apps/kiosk/checkin_screen.py).

### 5.1 Layout

- Title: "Family Locations" (header)
- Row: two columns 50/50
  - Left: "Possible family locations" (named places)
  - Right: "Check-ins" (latest per member)
- Map: ~72% height below columns

### 5.2 Data

- `GET /api/family_circles/{id}/named-places` → left column
- `GET /api/family_circles/{id}/get_checkins` → right column (contact_name, location_name, lat/lon)

### 5.3 Map

- Leaflet.js (CDN): `https://unpkg.com/leaflet@1.9/dist/leaflet.css` and `leaflet.js`
- Center: average of checkin coords or default (e.g. 37.07, -113.55)
- Markers: one per checkin. Custom marker = circle with photo. Photo: `<img src="/api/users/{id}/photo">` — session works; use `border-radius: 50%` for circle crop
- Lazy init: add map only when Family screen shown

---

## Phase 6: Chat Screen

Map from [chat_screen.py](src/apps/kiosk/chat_screen.py).

### 6.1 Data

- `GET /api/family_circles/{id}/contacts`
- Filter: `sendbird_user_id` present
- Show: photo (or initial letter) + name per contact

### 6.2 Contact grid

- CSS grid: 3 columns, ~160px min, 20px gap
- Tile: 96px avatar (circular via `border-radius: 50%`), 32px name below
- Photo: `<img src="/api/users/{id}/photo">` — session cookie works

### 6.3 On click

- `GET /api/chat/chat-session-url?recipient_sendbird_user_id=X&recipient_display_name=Y` (credentials: include)
- Response: `{ url: "..." }`
- `window.open(url, 'chat_' + id, 'width=800,height=600')`

---

## Phase 7: Photo Auth (Resolved by Session)

With launcher login, session cookie is sent for all same-origin requests. `<img src="/api/users/{id}/photo">` works because the browser sends the cookie automatically. No blob fetch, signed URL, or X-User-Id headers needed.

---

## Phase 8: Entry Point and Kivy Removal

### 8.1 Launcher integration

- `apps/kiosk/__main__.py`: login + open browser (pywebview → Chrome → webbrowser)
- `main.py`: add `--web` flag to run `python -m apps.kiosk` instead of Kivy
- Or: new entry point; main.py keeps Kivy as default until validated

### 8.2 Kivy removal (after validation)

- Delete: app.py, screens.py, home_screen.py, emergency_screen.py, checkin_screen.py, chat_screen.py, screen_primitives.py, kiosk_metrics.py, emergency_print.py, webview.py
- Remove from main.py: Kivy imports, Config, create_app, app.run()
- requirements.txt: remove kivy, kivy-garden.mapview; optionally add pywebview

---

## Implementation Checklist

1. [ ] Create `apps/kiosk/web/` directory
2. [ ] Add `kiosk.html` shell with nav + 4 screen containers
3. [ ] Add `kiosk.css` with design tokens and base layout
4. [ ] Add `kiosk.js` with apiFetch (credentials: include), nav switching, screen loaders
5. [ ] Implement Home screen (clock 3.2, meds 3.3, events 3.4)
6. [ ] Implement Emergency screen (4.1–4.5)
7. [ ] Implement Family screen (5.1–5.3, Leaflet map)
8. [ ] Implement Chat screen (6.1–6.3)
9. [ ] Add /kiosk/ routes to api.py
10. [ ] Add icons (sunrise, noon, evening, night) or placeholders
11. [ ] Create `__main__.py` launcher
12. [ ] Add `--web` flag to main.py (or separate entry)
13. [ ] Remove Kivy code and deps after validation

---

## Files to Create


| File                        | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `apps/kiosk/web/kiosk.html` | HTML skeleton, links to css/js                 |
| `apps/kiosk/web/kiosk.css`  | Design tokens, layout, typography, alert flash |
| `apps/kiosk/web/kiosk.js`   | Screen logic, clock, API, map, alert polling   |
| `apps/kiosk/__main__.py`    | Launcher: login → pywebview/Chrome/webbrowser  |


---

## Files to Modify


| File                 | Change                                                          |
| -------------------- | --------------------------------------------------------------- |
| `apps/server/api.py` | Add /kiosk/ routes: kiosk.html, kiosk.js, kiosk.css, icons      |
| `main.py`            | Add --web flag to launch `python -m apps.kiosk` instead of Kivy |
| `requirements.txt`   | Remove kivy, kivy-garden.mapview; optionally add pywebview      |


---

## API Reference


| Data              | Method | Path                                                       |
| ----------------- | ------ | ---------------------------------------------------------- |
| Login             | POST   | `/api/login`                                               |
| Session           | GET    | `/api/session` (returns user_id, family_circle_id)         |
| Medications       | GET    | `/api/family_circles/{id}/medications`                     |
| Events            | GET    | `/api/family_circles/{id}/calendar/events?date=YYYY-MM-DD` |
| Emergency profile | GET    | `/api/family_circles/{id}/emergency-profile`               |
| Emergency PDF     | GET    | `/api/family_circles/{id}/emergency-profile/pdf`           |
| Alert status      | GET    | `/api/emergency/alert/status`                              |
| Checkins          | GET    | `/api/family_circles/{id}/get_checkins`                    |
| Named places      | GET    | `/api/family_circles/{id}/named-places`                    |
| Contacts          | GET    | `/api/family_circles/{id}/contacts`                        |
| Chat session URL  | GET    | `/api/chat/chat-session-url?recipient_...`                 |
| User photo        | GET    | `/api/users/{id}/photo`                                    |


All work with session cookie (`credentials: 'include'`) after launcher login.

---

## Kivy Rollback Strategy

- **Phase 1:** Add HTML kiosk; keep Kivy code and main.py launching Kivy
- **Phase 2:** Add `--web` flag or `python -m apps.kiosk` to launch HTML kiosk
- **Phase 3:** Validate HTML kiosk; switch default to HTML
- **Phase 4:** Remove Kivy files and deps after confidence

