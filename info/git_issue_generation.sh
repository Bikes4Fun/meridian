#!/bin/bash
# Create GitHub Milestone and Issues: ICE Screen & Smart911 Profile Sync
# Run from your meridian repo directory
# Requires: gh CLI authenticated (gh auth login)

# ─────────────────────────────────────────────
# CREATE MILESTONE
# ─────────────────────────────────────────────
MILESTONE_TITLE="ICE Screen & Smart911 Profile Sync"
MILESTONE_NUM=$(gh api repos/:owner/:repo/milestones \
  --method POST \
  --field title="$MILESTONE_TITLE" \
  --field description="Display critical medical info instantly on an ICE screen and keep the patient's Smart911 profile automatically updated. Lays groundwork for full 911 telephony integration." \
  --field state="open" \
  --jq '.number')

echo "✅ Milestone created: #$MILESTONE_NUM ($MILESTONE_TITLE)"

# ─────────────────────────────────────────────
# ISSUE #1 — ICE Data Model & Storage
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #1: ICE Data Model & Storage" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
Add \`ice_profile\` table to SQLite schema and define a JSON structure that mirrors Smart911's profile format from day one — so Smart911 sync in Issue #5-6 requires no data migration.

## Estimated Hours
**3–4 hours**

## Tasks
- [ ] Add \`ice_profile\` table to \`schema.sql\`
- [ ] Fields: \`user_id\`, \`full_name\`, \`date_of_birth\`, \`photo_path\`, \`diagnosis\`, \`dnr_status\` (boolean), \`dnr_document_path\`, \`medical_proxy_name\`, \`medical_proxy_phone\`, \`poa_name\`, \`poa_phone\`, \`notes\`, \`last_updated\`, \`last_updated_by\`
- [ ] Allergies and conditions already exist — reference via foreign key, do not duplicate
- [ ] Medications already exist — reference via existing \`medications\` table
- [ ] Define \`ice_profile.json\` schema doc that mirrors Smart911 field mapping
- [ ] Add \`ICEProfileService\` to \`container/\` with \`get_ice_profile(user_id)\` and \`update_ice_profile(user_id, data)\`
- [ ] Add \`GET /api/ice\` and \`PUT /api/ice\` endpoints to \`server/app.py\`
- [ ] Seed demo ICE data in \`demo.py\`

## Schema
\`\`\`sql
CREATE TABLE IF NOT EXISTS ice_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    full_name TEXT,
    date_of_birth TEXT,
    photo_path TEXT,
    diagnosis TEXT,
    dnr_status INTEGER DEFAULT 0,
    dnr_document_path TEXT,
    medical_proxy_name TEXT,
    medical_proxy_phone TEXT,
    poa_name TEXT,
    poa_phone TEXT,
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_by TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
\`\`\`

## Smart911 Field Mapping (define now, use in Issue #5)
| Our Field | Smart911 Field |
|-----------|----------------|
| full_name | profile.name |
| date_of_birth | profile.dob |
| diagnosis | medical.conditions |
| dnr_status | medical.dnr |
| medical_proxy_name | emergency.proxy.name |
| allergies (from allergies table) | medical.allergies |
| medications (from medications table) | medical.medications |"

# ─────────────────────────────────────────────
# ISSUE #2 — ICE Screen UI
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #2: ICE Screen UI" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
Full-screen ICE (In Case of Emergency) display on the TV app. Visually distinct from all other screens — designed so EMS can read critical information from the doorway the moment they enter.

## Estimated Hours
**4–6 hours**

## Depends On
Issue #1 (ICE Data Model)

## Tasks
- [ ] Add \`ice_screen\` to \`screens.py\` via \`ScreenFactory.create_ice_screen()\`
- [ ] Register screen in \`app_factory.py\` screen manager
- [ ] Full red/high-contrast background — visually unmistakable
- [ ] Large patient photo (top left)
- [ ] Patient name in huge font
- [ ] DNR STATUS — most prominent element, large colored badge (red = DNR, green = Full Code)
- [ ] Emergency contacts section: name, relationship, phone in large text
- [ ] Medications list (pulled from existing medication service)
- [ ] Allergies list (pulled from existing data)
- [ ] Medical proxy and POA names + phone numbers
- [ ] Diagnosis displayed clearly
- [ ] Trigger: add 'ICE' button to emergency screen nav
- [ ] Trigger: auto-navigate to ICE screen when 911 called (hook for Issue #7)
- [ ] Back button returns to emergency screen

## Design Notes
- Every element must be readable at 6+ feet distance
- No small text anywhere on this screen
- Red border/background signals urgency to EMS immediately
- Follow existing \`DementiaWidget\`/\`DementiaLabel\` patterns from \`modular_display.py\`"

# ─────────────────────────────────────────────
# ISSUE #3 — Caregiver ICE Profile Editor
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #3: Caregiver ICE Profile Editor (Web)" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
Web form (extending the existing \`checkin.html\` web client pattern) for the primary caregiver to create and update the patient's ICE profile. All changes versioned with timestamp and editor identity.

## Estimated Hours
**6–10 hours**

## Depends On
Issue #1 (ICE Data Model & API endpoints)

## Tasks
- [ ] Create \`ice_editor.html\` and \`ice_editor.js\` in \`webapp/web_client/\`
- [ ] Serve via Flask: \`GET /ice-editor\` in \`server/app.py\`
- [ ] Form fields: full name, DOB, diagnosis, DNR toggle (prominent), medical proxy, POA, notes
- [ ] Photo upload: preview before save, store path server-side
- [ ] DNR document upload: PDF or image, store path server-side
- [ ] Load existing profile on page open (pre-fill all fields)
- [ ] Save via \`PUT /api/ice\` — show success/error feedback
- [ ] Version log: display last 5 changes (timestamp + who changed it) below form
- [ ] Allergies and conditions: read-only display with link to edit (managed elsewhere)
- [ ] Medications: read-only display pulled from medication service
- [ ] Permission check: only primary caregiver role can edit (use \`X-User-Id\` header)
- [ ] Mobile-friendly layout — caregivers will use this on their phone

## Files
\`webapp/web_client/ice_editor.html\`, \`webapp/web_client/ice_editor.js\`"

# ─────────────────────────────────────────────
# ISSUE #4 — Printable POLST-Formatted Document
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #4: Printable POLST-Formatted PDF" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
One-click generate a printable PDF from the ICE profile, formatted to match POLST/MOLST standards that EMS and hospitals recognize. Include fridge placement instructions — this is legally meaningful in most states immediately with no regulatory approval required.

## Estimated Hours
**4–6 hours**

## Depends On
Issue #1 (ICE Data Model)

## Tasks
- [ ] Add \`GET /api/ice/pdf\` endpoint to \`server/app.py\`
- [ ] Use \`reportlab\` or \`weasyprint\` to generate PDF server-side
- [ ] PDF sections (POLST-aligned order):
  - Patient name, DOB, photo
  - DNR / Full Code status (large, prominent, colored)
  - Medical proxy name and phone
  - POA name and phone
  - Diagnosis and conditions
  - Medications with dosages
  - Allergies
  - Emergency contacts
  - Primary physician name and phone
  - Document last updated date
- [ ] Bright pink/red border on PDF — matches physical POLST form color convention EMS recognize
- [ ] Footer: 'Keep this document visible — post on refrigerator or front door'
- [ ] Add 'Print ICE Document' button to ICE editor web page (Issue #3)
- [ ] Add 'Print ICE Document' button to emergency screen on TV (Issue #2)

## Notes
POLST (Physician Orders for Life-Sustaining Treatment) forms are recognized by EMS in all 50 states. Matching their visual format increases the chance EMS acts on the document correctly even without formal POLST registration."

# ─────────────────────────────────────────────
# ISSUE #5 — Smart911 Account Connection
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #5: Smart911 Account Connection" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
Allow the primary caregiver to connect their Smart911 account to the app. Map ICE profile fields to Smart911 profile fields. Display connection status in the caregiver dashboard.

## Estimated Hours
**6–8 hours**

## Depends On
Issue #1 (ICE Data Model), Issue #3 (Caregiver Editor)

## ⚠️ External Dependency
**Apply for Smart911 partnership/API access immediately — this is the long pole.**
- Visit: https://www.smart911.com/smart911/ref/dev.action
- Approval timeline unknown — start this conversation in parallel with Issues #1-4

## Tasks
- [ ] Add \`smart911_connection\` table: \`user_id\`, \`smart911_token\`, \`smart911_profile_id\`, \`connected_at\`, \`last_sync\`
- [ ] Add 'Connect Smart911' button to ICE editor web page
- [ ] OAuth or API key flow (TBD based on Smart911 API docs)
- [ ] On connect: do initial full profile push from ICE data model
- [ ] Map fields per the Smart911 mapping defined in Issue #1
- [ ] Store token securely (encrypted at rest)
- [ ] Display 'Smart911 Connected ✓ — Last synced: [timestamp]' in caregiver dashboard
- [ ] Display 'Smart911 Not Connected' warning with connect button if not linked
- [ ] Add \`GET /api/smart911/status\` endpoint
- [ ] Handle connection errors and token expiry gracefully

## Field Mapping Reference
Defined in Issue #1 schema doc — implement that mapping here."

# ─────────────────────────────────────────────
# ISSUE #6 — Smart911 Auto-Sync
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #6: Smart911 Auto-Sync" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
When the ICE profile, medications, or emergency contacts are updated in the app, automatically push those changes to Smart911. The caregiver never needs to remember to update two systems.

## Estimated Hours
**8–10 hours**

## Depends On
Issue #5 (Smart911 Account Connection)

## Tasks
- [ ] Add sync trigger to \`PUT /api/ice\` — after successful save, push to Smart911 if connected
- [ ] Add sync trigger to medication updates — \`POST/PUT /api/medications\` pushes med list to Smart911
- [ ] Add sync trigger to contact updates — \`PUT /api/emergency/contacts\` pushes contacts to Smart911
- [ ] Sync is async (background thread) — never blocks the UI
- [ ] If sync fails: log error, set \`sync_status = 'failed'\`, surface warning to caregiver
- [ ] Add \`POST /api/smart911/sync\` manual sync endpoint (caregiver can force a full sync)
- [ ] Update \`last_sync\` timestamp on every successful sync
- [ ] Show sync status indicator in caregiver dashboard: ✓ synced / ⚠ sync failed / 🔄 syncing
- [ ] Retry logic: if sync fails, retry once after 60 seconds before marking failed

## Core Value
This is the feature that justifies the Smart911 integration — the profile is always current without the caregiver remembering to update it manually. Every competitor requires manual updates."

# ─────────────────────────────────────────────
# ISSUE #7 — 911 Call Trigger + ICE Auto-Display
# ─────────────────────────────────────────────
gh issue create \
  --title "ICE #7: 911 Call Trigger + ICE Auto-Display" \
  --milestone "$MILESTONE_TITLE" \
  --label "enhancement" \
  --body "## Overview
When a 911 call is initiated from the app, immediately switch the TV to the ICE screen and push emergency notifications to all family members. Lays the groundwork for full SIP/landline telephony integration in a future milestone.

## Estimated Hours
**6–8 hours**

## Depends On
Issue #2 (ICE Screen UI)

## Tasks
- [ ] Add 'CALL 911' button to emergency screen — large, red, unmissable
- [ ] Two-step confirmation: 'Are you sure?' screen with 3-second countdown before dialing
- [ ] On confirm: immediately navigate TV to ICE screen (EMS sees it when they arrive)
- [ ] On confirm: \`POST /api/emergency/call911\` endpoint (stub for now — logs the event)
- [ ] On confirm: push notification to all family contacts via existing contact service
- [ ] Notification content: 'EMERGENCY: [patient name] has called 911 at [timestamp]' + ICE summary
- [ ] Log every 911 trigger: timestamp, who triggered it, outcome
- [ ] ICE screen stays displayed until manually dismissed by family member (no auto-timeout)
- [ ] Add \`called_911\` event to audit log table

## Stub Note
The actual phone call (SIP/Twilio) is handled in a future telephony milestone — this issue wires up the UI trigger, ICE display, family alerts, and audit logging so that milestone can drop in cleanly.

## Future Telephony Milestone Hook
\`\`\`python
@app.route('/api/emergency/call911', methods=['POST'])
def call_911():
    # TODO: replace stub with SIP/Twilio call in telephony milestone
    log_emergency_event(g.user_id)
    notify_all_family_contacts(g.user_id)
    return jsonify({'status': 'logged', 'message': 'Telephony not yet configured'}), 200
\`\`\`"

echo ""
echo "✅ Milestone and all 7 issues created!"
echo ""
echo "Summary:"
echo "  Milestone : ICE Screen & Smart911 Profile Sync"
echo "  Issue #1  : ICE Data Model & Storage          (3-4 hrs)"
echo "  Issue #2  : ICE Screen UI                     (4-6 hrs)"
echo "  Issue #3  : Caregiver ICE Profile Editor      (6-10 hrs)"
echo "  Issue #4  : Printable POLST-Formatted PDF     (4-6 hrs)"
echo "  Issue #5  : Smart911 Account Connection       (6-8 hrs)"
echo "  Issue #6  : Smart911 Auto-Sync                (8-10 hrs)"
echo "  Issue #7  : 911 Call Trigger + ICE Display    (6-8 hrs)"
echo "  Total     :                                    43-52 hrs"
echo ""
echo "⚠️  Action required: Apply for Smart911 API partnership now"
echo "   https://www.smart911.com/smart911/ref/dev.action"