# Meridian — Top 3 Feature Refinement Guide (status)

> Two sections per feature: **Must-Do** (ship within days, no new API deps) and **Deep Polish** (extreme refinement if time allows). No other features covered here.

**Legend:** **✅** shipped · **⬜** not shipped · **🔄** partial / adjacent only (not the named bullet)

_Update this file when Top 3 scope changes or items ship._

---

## 1. ICE / Emergency Profile + POLST

### Must-Do

**⬜ Confirm modal on the emergency alert button**  
The current `kioskAlertShortcutBtn` in the header scrolls to the Health tab — it does not confirm before activating. This is a critical safety gap. Replace with a compact popover/modal directly on the button. The modal needs: a brief warning ("This will switch the kiosk to emergency mode"), an Activate button in red, and a Cancel option. When an alert is already active, the same button should show a different state (red/pulsing icon, "Cancel alert" as the primary action). No new API needed — activate and cancel endpoints are already wired.

**⬜ Profile completeness indicator**  
Families won't fill out a form they can't see progress on. Add a simple `4 of 7 fields complete` indicator at the top of both the Health tab POLST fold and the `/ice-editor` page. The seven critical fields are: full name, date of birth, DNR status, at least one emergency contact, medical proxy name + phone, care recipient photo uploaded, and DNR/POLST document uploaded. Derive this client-side from the loaded profile data — no backend change needed. Display it as a fraction with a subtle colored bar or dot indicators. Red if under 4/7, yellow at 4–6, green at 7/7.

**⬜ Last-updated timestamp**  
Every saved ICE profile should display "Last updated [date]" at the top of the editor and on the kiosk emergency screen. The `updated_at` field already exists on the profile response — it just needs to be surfaced. On the kiosk, this gives first responders and family confidence that the data is current. Format it as a plain, readable date: "Last updated April 14, 2026" not an ISO string.

**⬜ Missing critical fields warnings**  
Below the completeness indicator, show inline warnings for the specific fields that are empty and matter most in an emergency: no DNR document uploaded, no emergency contact marked primary, no proxy phone number. These should be dismissible banners or small orange warning rows next to the relevant field — not a blocking modal. The goal is to catch gaps before they matter.

**🔄 Related (not the bullets above):** Webapp ICE editor still works; API access for the webapp was centralized through `apps/webapp/web_client/src/api_client.js` (structural / maintainability; not the ICE safety UX checklist).

---

### Deep Polish (if time allows)

**⬜ Emergency contacts: drag-to-reorder priority**  
The current contact list has primary/secondary as a dropdown select. Replace or augment with a drag handle so the ordering feels intentional and obvious. The primary contact should be visually distinct (bolder, first row, labeled clearly) vs. secondary. When no primary is set, show an explicit "No primary emergency contact — drag a contact to the top or mark as primary" empty state.

**⬜ Uploaded document metadata strip**  
When a DNR or POLST file has been uploaded, show more than just a "View uploaded document" link. Show: filename, upload date, file size, and a small Replace / Delete action row. This builds trust that the right file is there and it's the current version. Especially important for families who upload an updated directive after a medical appointment.

**⬜ PDF layout upgrade**  
The current PDF is browser-print. For a go-bag or fridge document, it needs to look designed. A proper one-page layout with: patient photo top-right, DNR status as a large badge (DO NOT RESUSCITATE in bold red if applicable, or FULL CODE if not), medications in a compact two-column list, emergency contacts with phone numbers large enough to read under stress, and proxy/POA at the bottom. Server-side PDF generation gives the most control here (ReportLab or WeasyPrint). If browser-only is the constraint, a print-specific CSS stylesheet injected at print time can get 80% of the way there.

**⬜ Per-field kiosk visibility toggles**  
Not all ICE data belongs on the kiosk screen — some families may not want diagnoses or certain medications visible to anyone who walks past. Add small toggle controls in the ICE editor (show/hide on kiosk) per section: conditions, allergies, full medication list, notes for responders. The emergency contacts, name, DOB, and DNR status should always show and cannot be hidden.

**⬜ Conditions and allergies made editable**  
Currently conditions and allergies are read-only in the ICE editor (pulled from medical record). For the target use case — families managing care at home — there is often no external medical record feeding this. Add inline add/edit/delete for conditions and allergies directly in the ICE editor. Each condition needs: name, diagnosis date (optional), notes. Each allergy needs: substance name and severity (mild / moderate / severe / anaphylactic).

**⬜ "Review before printing" pre-flight check**  
When the user clicks "Print emergency document," intercept with a one-step pre-flight that shows: completeness score, a list of missing critical fields, and the last-updated date. Two buttons: "Print anyway" and "Complete profile first." This nudges families toward finishing the profile before generating a document they'll rely on in an actual emergency.

**⬜ Kiosk emergency screen: layout and visual hierarchy**  
The kiosk emergency screen should be optimized for a first responder who has never seen the system before and is under stress. That means: patient name and photo prominent at top, DNR badge immediate and unmissable, medications in the largest readable font, emergency contacts with click-to-call on supported hardware, and a Print button always visible. Review the current `emergency_screen.py` HTML output against this hierarchy and restructure if needed.

---

## 2. Stove / Safety Sensor + Auto Emergency Alert

### Must-Do

**⬜ Sensor status card in webapp settings**  
The webapp currently has no visibility into whether the stove sensor is actually running. A family could have the kiosk on, assume monitoring is active, and have no idea the sensor went offline. Add a status card to the Kiosk Settings tab (or the Settings section where the stove stub lives) showing: Online / Offline / Unknown as a colored badge, the current temperature reading (or "—" if offline), the last-reading timestamp ("Last reading: 2 minutes ago"), and when the last alert was triggered. This data can be exposed via a new lightweight `/api/sensor/stove/status` endpoint that the webapp polls on a 10-second interval, or it can be pushed via an existing websocket if one exists. The kiosk already pushes the `stove-temp` element every 2 seconds via `_eval_el` — the webapp needs its own separate polling.

**⬜ Alert lifecycle status strip**  
When a stove alert fires, the family needs to know: why it fired, its current state, and what cleared it. Add a status strip below the sensor card showing the last transition: "Alert triggered at 2:14 PM — temperature held above threshold for 20 seconds" → "Alert snoozed by user at 2:15 PM (30 min)" → "Alert auto-cleared at 2:47 PM — temperature normalized." Store these transitions in a small in-memory or DB-backed log on the server (3–5 entries is sufficient). The `_maybe_stove_emergency_alert` method in `sensor_widgets.py` already logs these transitions via `logger.info` — pipe those same events to the API.

**⬜ Sensor offline warning — prominent, not subtle**  
If the sensor status is Offline or Unknown and the feature is expected to be running, show a yellow warning banner at the top of the settings section: "⚠️ Stove sensor is not reporting. Check the USB connection and serial port configuration." Do not show this banner if the sensor has never been configured (i.e., the stove feature is intentionally not in use). Distinguish between "was online, now offline" and "never connected."

---

### Deep Polish (if time allows)

**⬜ Threshold calibration UI in webapp settings**  
Currently `STOVE_ALERT_THRESHOLD_C = 30.0` and `STOVE_ALERT_DURATION_SEC = 20.0` are hardcoded in `sensor_widgets.py` for testing (30°C is barely above room temperature). Families need to set real thresholds. Build a settings form in the webapp: temperature threshold (°C or °F toggle), duration before alert fires (seconds), snooze duration (minutes). Store these in the DB or a config table and read them at sensor startup. Until the backend for this is ready, the form can be UI-only with a "Saved locally — contact your administrator to apply" note.

**⬜ Celsius / Fahrenheit display toggle**  
`STOVE_DISPLAY_CELSIUS = True` is currently a hardcoded flag. Surface this as a simple toggle in the webapp sensor settings: "Display in °F / °C." It should update the `stove-temp` display on the kiosk settings screen and in the webapp status card without a restart.

**⬜ Alert history log: last 10 events**  
A minimal table in the webapp settings showing the last 10 alert events: timestamp, trigger reason (temperature sustained above threshold / manual activate), resolution (snoozed by user / auto-cleared / cancelled), and which user actioned it if applicable. This helps families understand patterns — is the stove alert firing every morning because someone is cooking, or is there a real problem? It also helps debug sensor configuration in early deployments.

**⬜ Sensor test mode indicator**  
`STOVE_ALERT_THRESHOLD_C = 30.0` is a testing value that fires almost immediately in any room. When the threshold is below 50°C, add a visible "Test mode — thresholds are set for development" banner in the webapp sensor card and on the kiosk settings screen. This prevents the embarrassing situation where a demo or real deployment fires constant alerts because nobody changed the test values.

**⬜ Emergency linkage: stove alert → ICE profile shortcut**  
When a stove alert is active (in the webapp alert status card or anywhere the alert state is shown), add a direct shortcut button: "Review emergency profile →" that navigates to the ICE editor. The reasoning: if the stove triggered an alert, the family should immediately confirm the emergency profile is up to date and the right contacts are listed. This makes the two features feel like a coherent safety system rather than independent tools.

**⬜ Graceful degradation messaging for pyserial missing**  
Currently if `pyserial` is not installed, the sensor thread logs an error and silently disables. This is invisible to the user. Add a visible "Sensor disabled — pyserial not installed" message to the kiosk settings screen monitors row and to the webapp sensor status card. Include a one-line install instruction: `pip install pyserial`.

**⬜ Alert snooze visibility on kiosk**  
When alerts are snoozed, the kiosk shows nothing — the stove temperature widget continues to update but there's no indication that alerts are suppressed. Add a small "Alerts snoozed — 24 min remaining" indicator below the stove temperature row on the kiosk settings screen for the duration of the snooze. The `_ignore_until` timestamp already exists in `TemperatureSensor` — just compute the remaining minutes and push it to the UI alongside the temperature reading.

---

## 3. "Where Is Everyone?" + Named Locations

### Must-Do

**⬜ Named locations editor in webapp**  
This is the single biggest gap — server-side matching is live and working, but there is no UI to create or manage named locations. Without this, families can't set up the human-readable labels that make the feature meaningful. Build an add/edit/delete editor in the Family Circle tab (or a dedicated subsection). Each location needs: a label field (e.g. "Anne's Office downtown"), an address or lat/lon field (geocode the address client-side using the browser's Geocoding API or a free tile service to get coordinates), and a radius field (default 150m, configurable). Display existing locations as a list of cards. For the initial version, skip the interactive map — show a static Google Maps embed or Leaflet tile with a pin at the coordinates, loaded after the user enters an address.

**⬜ Care-recipient home label editor**  
The kiosk shows "You are at home" for the patient's own location if a home place is configured. Currently this requires direct DB manipulation. Add a dedicated "Your home location" field at the top of the named locations editor: a single text field for the label ("You are at your home on Maple Street in Denver") and an address field for the coordinates. This is one of the highest-impact single fields in the product — a disoriented person seeing their own address in plain language on a large screen is genuinely orienting.

**⬜ Named-label-first display in admin**  
Anywhere the webapp shows check-ins or location data, display the resolved named label as the primary text, not raw coordinates. Raw coordinates are meaningless to caregivers. If a check-in has a `location_name` from the server, show that. If it doesn't (no named place matched), show "Unknown location" or the address if available, with the coordinates as a secondary detail in smaller text. Apply this across: the webapp mobile check-in list, any admin review of recent check-ins, and the family circle overview.

---

### Deep Polish (if time allows)

**⬜ Request status summary in admin**  
When "Where is everyone?" is triggered from the kiosk, the family-side admin should be able to see the current request state: who has been asked, who has responded, who has declined, and how old the request is. A compact table or card list in the Family Circle tab: "Anne — responded 4 min ago · Dave — pending · Mom — declined." Currently the request fires and disappears from the admin's perspective. This closes the loop and lets caregivers follow up if someone doesn't respond.

**⬜ Cooldown and frequency-limit UX**  
Without a cooldown, the "Where is everyone?" button can be tapped rapidly by a confused patient. Add a visible cooldown indicator on the kiosk button after it's been tapped: a disabled state with "Request sent — try again in 5 minutes" or similar. Configure the max frequency in the webapp (admin sets it). The kiosk should respect a server-side cooldown, not just a local UI lock — otherwise reloading the screen bypasses it.

**⬜ Stale check-in indicators**  
A check-in from 6 hours ago is not useful data but currently looks the same as one from 5 minutes ago. Add a relative timestamp to each family member's location on the kiosk family screen: "Anne — downtown (3 hours ago)" in smaller text below the name. In the webapp admin view, highlight check-ins older than a configurable threshold (default 4 hours) with a subtle warning color. This prevents caregivers from relying on outdated data.

**⬜ Per-member location visibility in admin**  
Some family members may not want their location shared at all — currently location sharing is all-or-nothing. Add a per-member opt-in flag in the Family Circle member list: "Share location with family circle — yes / no." Members with no set to this flag are excluded from check-in requests and their check-in data doesn't appear on the kiosk. This is also a trust and privacy feature for family members who are uncomfortable with location sharing.

**⬜ Map cluster polish on kiosk (issue #99)**  
When multiple family members are at the same named location (e.g. at a family gathering), the current Leaflet map stacks markers on top of each other. The open issue #99 tracks this. The fix is marker clustering: group nearby markers into a single cluster pin with a count badge, and expand on tap. On the kiosk (large touch screen), the cluster tap target needs to be generous. Alternatively, for the case where multiple people are at the same named place, show a single named-place label with multiple avatars grouped under it rather than individual pins.

**⬜ Fallback behavior when no named match**  
Currently if a check-in doesn't match any named location, the kiosk shows "Unknown" as the location name. This is confusing. The fallback should be a reverse-geocoded street name or neighborhood (e.g. "Near 5th Ave, Denver") using the coordinates and a free tile API, or simply "Away from known locations" if geocoding isn't available. This is much more readable than "Unknown" and still gives the patient a sense that their family member is somewhere identifiable.

**⬜ Check-in notes on kiosk family screen**  
The check-in API already accepts an optional `notes` field (e.g. "At the grocery store, back in an hour"). Currently these notes are not displayed on the kiosk family screen — only the location name appears. Surfacing the note as a secondary line under each family member's name would make the feature feel warmer and more connected. Keep it short: truncate at ~60 characters on the kiosk. The notes field exists in the iOS `CheckInViewController` — it just needs to flow through to the kiosk display.

**⬜ Named location radius visualization**  
Once the webapp editor ships, add a visual radius indicator on the static map embed: a semi-transparent circle centered on the pin showing the configured radius. This helps families understand why a check-in did or didn't match a location (e.g. "her office is only 100m radius but she parked outside it"). For the kiosk Leaflet map, optionally show the same radius circles as faint overlays — gives spatial context without cluttering the main view.

---

## Shipped recently (outside this Top 3 checklist)

Credit these in standup / presentations; they are not the §1–§3 bullets above.

- **✅** Webapp client restructure (`apps/webapp/web_client/public/` + `src/`, feature modules vs centralized `api_client.js`)
- **✅** Single `api_client.js` path for webapp API calls; structural `X-Meridian-Client` marker + server-side check for browser-like API traffic (not a substitute for auth)
- **✅** Medications: mark all **non‑PRN** doses (web Health, mobile web tab, kiosk Home/Health)
- **✅** Medications: PRN at bottom + sticky "As needed" section (web)
- **✅** Webapp layout: Info page / unified page shell grid margins
- **✅** Demo seed and API responses for medications (idempotency, duplicate handling, logging)
- **✅** Runtime API URL modes (local / ngrok / railway) and unified API target for webapp + kiosk where applicable

---

## How to maintain this file

1. When a **Must-Do** or **Deep Polish** item ships, change its line from **⬜** to **✅** and optionally add a one-line note in parentheses with PR or date.
2. When scope changes, edit the bullet text here to match the living spec (or link to the canonical doc).
3. Add new **Shipped recently** bullets for significant work that is still outside Top 3, then trim that list if it gets long (keep last ~10 items).
