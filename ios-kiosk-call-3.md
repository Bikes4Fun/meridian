# /ios-kiosk-call

Implement iOS → kiosk calling with two distinct modes:

1. **Regular call** — family member calls from any phone (or the Meridian app). Kiosk rings with caller name and Answer/Decline buttons like a normal phone.
2. **Force-answer** — app-only. Sends a signal that makes the kiosk auto-answer immediately, interrupting whatever is on screen. Used when the family can't reach the care recipient and needs to check in before escalating to a full emergency alert.

Both modes use **audio only** (two-way). Video is out of scope for now.

---

## Architecture decision (already resolved — do not re-litigate)

**Regular call path:** Personal phone or Meridian app → calls the kiosk's assigned Twilio phone number → Twilio routes to the kiosk's registered WebRTC device → kiosk rings audibly with caller ID.

**Force-answer path:** Meridian app → `POST /api/calls/force-answer` → server writes a force-answer signal → kiosk poll picks it up → kiosk auto-answers the active incoming Twilio call (or arms itself for the next one) immediately, full-screen interruption.

**Phone number model:** Each `family_circle` has one Twilio number assigned to it, stored in the DB. The kiosk's Twilio WebRTC device registers under an identity matching that number so Twilio knows which device to ring when that number is called.

**Why not WebRTC client-to-client from iOS?** The iOS app has zero Twilio SDK — it only makes HTTP calls. The regular phone call path (PSTN via Twilio) works from any phone, requires no SDK, and is more reliable for the target users. Force-answer uses the existing server signal polling mechanism.

---

## Database changes

### 1. Add `twilio_phone_number` to `family_circles`

```sql
ALTER TABLE family_circles ADD COLUMN twilio_phone_number TEXT;
```

Add to the schema migration and to `database_services/family.py`. Format: E.164 (e.g. `+18005551234`).

### 2. Add `force_answer_signals` table

```sql
CREATE TABLE IF NOT EXISTS force_answer_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_circle_id TEXT NOT NULL,
    requested_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    acknowledged_at TEXT,
    FOREIGN KEY (family_circle_id) REFERENCES family_circles(id)
);
```

---

## Server changes (`src/apps/server/`)

### 3. `twilio_voice.py` — update `api_voice_token()`

The kiosk's Twilio identity must match the family's phone number so Twilio routes inbound calls to it:

```python
# Replace:
identity = f"kiosk_{g.user_id}"[:120]

# With:
family_number = family_svc.get_twilio_number(g.family_circle_id)  # returns E.164 or None
identity = family_number if family_number else f"kiosk_{g.family_circle_id}"
identity = identity[:120]
```

Add `incoming_allow=True` to the `VoiceGrant`:

```python
token.add_grant(VoiceGrant(
    outgoing_application_sid=twiml_app_sid,
    incoming_allow=True,   # required for inbound WebRTC
))
```

### 4. `twilio_voice.py` — update `/twilio/voice/client` TwiML webhook

Add inbound routing. Twilio calls this webhook when the kiosk's number receives an inbound PSTN call:

```python
@app.route("/twilio/voice/client", methods=["POST"])
def twilio_voice_client_twiml():
    # ... existing signature validation unchanged ...

    params = request.form.to_dict()
    called = normalize_phone_e164(params.get("Called") or params.get("To") or "")
    direction = params.get("Direction") or ""

    # Inbound: someone called the kiosk's Twilio number
    if called and "outbound" not in direction:
        family_id = family_svc.get_family_by_twilio_number(called)
        if not family_id:
            err = VoiceResponse()
            err.say("This number is not configured.")
            return Response(str(err), mimetype="text/xml")
        # Route to the kiosk WebRTC device — identity = the family's Twilio number
        vr = VoiceResponse()
        dial = vr.dial()
        dial.client(called)
        return Response(str(vr), mimetype="text/xml")

    # Outbound: existing PSTN dial logic — unchanged below this point
    # ...
```

### 5. `api.py` — force-answer endpoints

```python
@app.route("/api/calls/force-answer", methods=["POST"])
def api_force_answer():
    db = get_db()
    db.execute(
        "INSERT INTO force_answer_signals (family_circle_id, requested_by_user_id) VALUES (?, ?)",
        (g.family_circle_id, g.user_id)
    )
    db.commit()
    return jsonify({"ok": True}), 201

@app.route("/api/calls/force-answer/pending", methods=["GET"])
def api_force_answer_pending():
    db = get_db()
    row = db.execute(
        "SELECT id FROM force_answer_signals WHERE family_circle_id = ? AND acknowledged_at IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        (g.family_circle_id,)
    ).fetchone()
    if not row:
        return jsonify({"pending": False})
    return jsonify({"pending": True, "signal_id": row["id"]})

@app.route("/api/calls/force-answer/<int:signal_id>/ack", methods=["POST"])
def api_force_answer_ack(signal_id):
    db = get_db()
    db.execute(
        "UPDATE force_answer_signals SET acknowledged_at = datetime('now') "
        "WHERE id = ? AND family_circle_id = ?",
        (signal_id, g.family_circle_id)
    )
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/family/kiosk-number", methods=["GET"])
def api_kiosk_number():
    row = get_db().execute(
        "SELECT twilio_phone_number FROM family_circles WHERE id = ?",
        (g.family_circle_id,)
    ).fetchone()
    if not row or not row["twilio_phone_number"]:
        return jsonify({"error": "No kiosk number configured for this family"}), 404
    return jsonify({"twilio_phone_number": row["twilio_phone_number"]})
```

---

## Kiosk changes (`src/apps/kiosk/`)

### 6. `api_client.py` — add `RemoteForceAnswerService`

Follow the exact pattern of `RemoteIncomingCallService`:

```python
class RemoteForceAnswerService:
    def __init__(self, base_url, kiosk_user_id=None, family_circle_id=None, session=None):
        self._base = base_url.rstrip("/")
        self._headers = _headers(kiosk_user_id, family_circle_id)
        self._session = session

    def get_pending(self):
        ok, data, err = _get(
            f"{self._base}/api/calls/force-answer/pending",
            headers=self._headers, session=self._session
        )
        if not ok:
            return ServiceResult.error_result(err or "force-answer poll failed")
        return ServiceResult.success_result(data or {})

    def acknowledge(self, signal_id):
        ok, j, err = _request(
            "POST", f"{self._base}/api/calls/force-answer/{signal_id}/ack",
            headers=self._headers, session=self._session, json_body={}
        )
        if not ok:
            return ServiceResult.error_result(err or "ack failed")
        return ServiceResult.success_result(j or {})
```

### 7. `app.py` — add force-answer poll loop

Add alongside `_start_incoming_call_poll`. Poll every 2 seconds — this is emergency-adjacent:

```python
def _start_force_answer_poll(self):
    import threading
    def _loop():
        svc = self.services.get_force_answer_service()
        while True:
            try:
                result = svc.get_pending()
                if result.success and result.data.get("pending"):
                    signal_id = result.data["signal_id"]
                    svc.acknowledge(signal_id)
                    self._window.evaluate_js("kioskForceAnswer()")
            except Exception:
                pass
            time.sleep(2)
    threading.Thread(target=_loop, daemon=True).start()
```

Call `_start_force_answer_poll()` in `_on_ready`, same place as the existing incoming call poll.

### 8. `kiosk.js` — wire `device.on('incoming')` at boot

Inside the existing `kioskEnsureTwilioDevice()` flow, immediately after `.register()` resolves:

```javascript
_kioskTwilioDevice.on('incoming', function(call) {
  var from = call.parameters.From || 'Family member';
  // Force-answer armed? Skip the ring UI and connect immediately.
  if (_kioskForceAnswerArmed) {
    _kioskForceAnswerArmed = false;
    kioskAcceptCall(call, 'Family check-in');
    return;
  }
  kioskShowIncomingCallUI(call, from);
});
```

### 9. `kiosk.js` — incoming call UI and force-answer functions

Add these functions near the other `kioskShow*` functions:

```javascript
var _kioskPendingIncomingCall = null;
var _kioskForceAnswerArmed = false;

function kioskShowIncomingCallUI(call, callerName) {
  _kioskPendingIncomingCall = call;

  var overlay = document.getElementById('kiosk-incoming-call-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'kiosk-incoming-call-overlay';
    overlay.className = 'kiosk-incoming-call';
    overlay.innerHTML =
      '<div class="kiosk-incoming-call__box">' +
        '<p class="kiosk-incoming-call__label">Incoming call</p>' +
        '<p class="kiosk-incoming-call__name" id="kiosk-incoming-caller-name"></p>' +
        '<div class="kiosk-incoming-call__actions">' +
          '<button class="kiosk-incoming-call__btn kiosk-incoming-call__btn--answer" id="kioskAnswerBtn">Answer</button>' +
          '<button class="kiosk-incoming-call__btn kiosk-incoming-call__btn--decline" id="kioskDeclineBtn">Decline</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
  }

  document.getElementById('kiosk-incoming-caller-name').textContent = callerName;
  overlay.classList.remove('kiosk-incoming-call--hidden');

  document.getElementById('kioskAnswerBtn').onclick = function() {
    kioskAcceptCall(call, callerName);
  };
  document.getElementById('kioskDeclineBtn').onclick = function() {
    call.reject();
    overlay.classList.add('kiosk-incoming-call--hidden');
    _kioskPendingIncomingCall = null;
  };
}

function kioskAcceptCall(call, callerName) {
  call.accept();
  _kioskActiveTwilioCall = call;
  _kioskPendingIncomingCall = null;
  var overlay = document.getElementById('kiosk-incoming-call-overlay');
  if (overlay) overlay.classList.add('kiosk-incoming-call--hidden');
  kioskShowInCallBar('ON A CALL', callerName || 'Family member');
  call.on('disconnect', function() {
    showToast('Call ended');
    _kioskTwilioCallUiEnded();
  });
  call.on('error', function(err) {
    _kioskTwilioCallUiEnded();
    showToast('Call error: ' + ((err && err.message) || 'unknown'));
  });
}

// Called by app.py via evaluate_js when force-answer signal arrives
function kioskForceAnswer() {
  if (_kioskPendingIncomingCall) {
    // Call already ringing — accept immediately, no UI
    kioskAcceptCall(_kioskPendingIncomingCall, 'Family check-in');
  } else {
    // Call not yet arrived — arm so device.on('incoming') auto-accepts it
    _kioskForceAnswerArmed = true;
    showToast('Connecting family check-in...');
  }
}
```

### 10. `kiosk.css` — incoming call overlay styles

Add at end of file:

```css
.kiosk-incoming-call {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
}
.kiosk-incoming-call--hidden { display: none; }

.kiosk-incoming-call__box {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 6vh 8vw;
  text-align: center;
  min-width: 36vw;
  animation: kiosk-ring-pulse 1s ease-in-out infinite alternate;
}
@keyframes kiosk-ring-pulse {
  from { box-shadow: 0 0 0 0 rgba(46, 125, 155, 0.5); }
  to   { box-shadow: 0 0 0 2.5vw rgba(46, 125, 155, 0); }
}
.kiosk-incoming-call__label {
  font-size: var(--font-subheader);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0 0 1vh;
}
.kiosk-incoming-call__name {
  font-size: var(--font-hero);
  font-weight: 700;
  color: var(--text);
  margin: 0 0 5vh;
}
.kiosk-incoming-call__actions { display: flex; gap: 4vw; justify-content: center; }
.kiosk-incoming-call__btn {
  min-width: 18vw;
  min-height: var(--touch-min);
  font-size: var(--font-subheader);
  font-weight: 700;
  border-radius: var(--radius-lg);
  border: none;
  cursor: pointer;
  padding: 2vh 3vw;
}
.kiosk-incoming-call__btn--answer { background: var(--secondary); color: #fff; }
.kiosk-incoming-call__btn--decline { background: var(--warm-delete); color: #fff; }
```

---

## iOS changes (`meridian-ios/`)

### 11. `APIService.swift` — two new methods

```swift
/// Returns the Twilio phone number assigned to this family's kiosk.
/// iOS then dials it via the system phone — no Twilio SDK needed.
func getKioskPhoneNumber() async throws -> String {
    let (data, res) = try await request("/api/family/kiosk-number", method: "GET")
    guard res.statusCode == 200 else {
        throw APIError.serverError("Could not fetch kiosk number (\(res.statusCode))")
    }
    let json = try JSONDecoder().decode([String: String].self, from: data)
    guard let number = json["twilio_phone_number"] else {
        throw APIError.serverError("No kiosk number in response")
    }
    return number
}

/// Signals the kiosk to auto-answer the next incoming call immediately.
func forceAnswerKiosk() async throws {
    let (_, res) = try await request("/api/calls/force-answer", method: "POST", body: [:])
    guard res.statusCode == 201 else {
        throw APIError.serverError("Force-answer failed (\(res.statusCode))")
    }
}
```

### 12. iOS call UI (in the relevant ViewController)

Regular call — dials from the system phone app:
```swift
Task {
    do {
        let number = try await APIService.shared.getKioskPhoneNumber()
        let cleaned = number.filter { $0.isNumber || $0 == "+" }
        if let url = URL(string: "tel://\(cleaned)") {
            await UIApplication.shared.open(url)
        }
    } catch {
        // Show error to user
    }
}
```

Force-answer button — show only when alert is active or care recipient is unreachable:
```swift
Task {
    do {
        try await APIService.shared.forceAnswerKiosk()
        // Show confirmation: "Kiosk will answer automatically"
    } catch {
        // Show error to user
    }
}
```

---

## UX specification

### iOS — contact card (family member tile)

Every contact card in the family/contacts list gets two call buttons. The kiosk user's card is the primary case; other contacts get the same buttons if a phone number is on file for them.

**Call button (normal):**
- Label: "Call"
- For the kiosk user: fetches `GET /api/family/kiosk-number` then opens `tel://` system dialer pre-filled with the kiosk's Twilio number. The system phone app handles everything from there.
- For other contacts: if a phone number is on file, opens `tel://` with their personal number. If no number on file, button is disabled or hidden.

**Force Call button:**
- Label: "Force Call"
- Visible on all contact cards but only meaningfully actionable for the kiosk user (the care recipient). For other contacts, omit or grey out — force-answer only applies to the kiosk.
- Tapping it: calls `POST /api/calls/force-answer` to arm the kiosk, then immediately opens `tel://` to the kiosk's Twilio number so the family member's call arrives as the kiosk auto-answers.
- Show a brief confirmation after the signal is sent: "Kiosk will answer automatically when you call."

```
┌─────────────────────────────┐
│  👤  Marian (Kiosk)         │
│      Care recipient         │
│                             │
│  [ Call ]  [ Force Call ]   │
└─────────────────────────────┘

┌─────────────────────────────┐
│  👤  James Foster           │
│      Son · 555-234-5678     │
│                             │
│  [ Call ]                   │
└─────────────────────────────┘
```

### iOS — alert activation flow

When a family member taps "Activate Alert" in the app, show a confirmation sheet **before** activating. The sheet has:

- Title: "Activate emergency alert?"
- Description: "This will switch the kiosk to emergency mode."
- Checkbox (default unchecked): "Also force-answer the kiosk so I can speak with them"
- Buttons: "Activate" / "Cancel"

If the checkbox is checked when they tap Activate:
1. Call `POST /api/calls/force-answer` (arm the kiosk)
2. Call the existing alert activation endpoint
3. Open `tel://` to the kiosk's Twilio number so the call arrives

If the checkbox is unchecked:
1. Call the existing alert activation endpoint only — no call triggered

```
┌──────────────────────────────────┐
│  Activate emergency alert?       │
│                                  │
│  This will switch the kiosk to   │
│  emergency mode.                 │
│                                  │
│  ☐  Also force-answer the kiosk  │
│     so I can speak with them     │
│                                  │
│  [ Cancel ]      [ Activate ]    │
└──────────────────────────────────┘
```

### Kiosk — what the care recipient sees during a call

**Regular incoming call (not force-answer):**
Full-screen ring overlay with the caller's name and Answer / Decline buttons (already specified in sections 8–9 above). Rings audibly. Care recipient answers or declines normally.

**Force-answer call (emergency-adjacent):**
Skip the ring overlay entirely — auto-answer immediately. Navigate to the emergency screen. The existing bouncing "on a call" indicator that already lives on the emergency screen handles the in-call visual state. No additional UI needed.

Implementation: in `kioskForceAnswer()` and `kioskAcceptCall()`, after `call.accept()`, call `showScreen('emergency')` (or whatever the existing navigation function is) so the kiosk lands on the emergency screen with its bouncing indicator active.

**Non-emergency force-answer (if triggered outside of an alert):**
Use the existing outbound in-call bar at the bottom of the screen — same bar that appears when the kiosk places an outbound call. Simplest path, no new UI needed.

Implementation: in `kioskAcceptCall()`, detect whether an emergency alert is currently active (`window._kioskAlertActive` or equivalent flag). If active → navigate to emergency screen. If not → just call `kioskShowInCallBar('ON A CALL', callerName)` as already written.

---

## Twilio Console setup (one-time per family)

1. Buy a phone number in Twilio Console
2. Set its **Voice webhook URL** to `https://your-server/twilio/voice/client` (POST)
3. Assign to the family in DB:
   ```sql
   UPDATE family_circles SET twilio_phone_number = '+18005551234' WHERE id = 'F00000';
   ```

For multi-family at scale this assignment step needs an admin flow — out of scope for this branch, but the schema supports it.

## Twilio trial account note

Trial accounts can only call verified numbers. Verify the test number at twilio.com/console/phone-numbers/verified. Disappears on account upgrade.

---

## Testing checklist

- [ ] Kiosk boots and registers Twilio device (logs show `Twilio API credentials OK`)
- [ ] `family_circles.twilio_phone_number` is set for the test family
- [ ] Calling the kiosk's Twilio number from a personal phone → kiosk rings with Answer/Decline overlay and caller ID
- [ ] Answering connects audio both ways
- [ ] Declining rejects cleanly, overlay disappears
- [ ] Hanging up on either end clears the in-call bar
- [ ] iOS app: Call button fetches the number and opens the system phone dialer pre-filled
- [ ] iOS app: Force-answer while call is already ringing → kiosk accepts immediately, no UI shown
- [ ] iOS app: Force-answer before call arrives → kiosk armed, auto-accepts when ring arrives
- [ ] Force-answer interrupts whatever screen the kiosk is showing
- [ ] Kiosk with no Twilio config → boots silently, shows toast if call attempted, no crash
- [ ] iOS contact card: kiosk user shows both Call and Force Call buttons
- [ ] iOS contact card: other contacts show Call button only if phone number on file, hidden/disabled if not
- [ ] iOS Call button on kiosk contact → system dialer opens pre-filled with kiosk Twilio number
- [ ] iOS Force Call button → confirmation shown, then system dialer opens
- [ ] iOS alert activation sheet: checkbox present and unchecked by default
- [ ] iOS alert activation with checkbox unchecked → alert activates, no call triggered
- [ ] iOS alert activation with checkbox checked → kiosk armed, alert activates, system dialer opens
- [ ] Force-answer during active emergency alert → kiosk navigates to emergency screen with bouncing indicator
- [ ] Force-answer with no active alert → kiosk shows in-call bar, does not navigate to emergency screen
