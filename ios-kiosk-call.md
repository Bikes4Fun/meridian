Implement iOS → kiosk WebRTC voice calling so a family member on iPhone can ring the kiosk and the care recipient can answer.

## What's broken today

The signal path exists but is wired to nothing useful:
- iOS calls `POST /api/calls/request` → DB signal written ✓
- Kiosk polls `GET /api/calls/incoming` every 1 s ✓
- When a signal is found, `_start_incoming_call_poll` in `app.py` does: `self._navigate_to("chat")` then acks — **no audio, no ring, no call**

The kiosk has a full outbound Twilio Voice JS device (`kioskStartTwilioSpeakerCall`) but:
- Never registered with a Twilio **identity**, so Twilio can't route inbound to it
- `device.on('incoming', ...)` is never wired
- No incoming call UI exists anywhere

## Files to change

| File | Change |
|---|---|
| `src/apps/server/twilio_voice.py` | Add `identity` + `incoming_allow=True` to the kiosk's voice token |
| `src/apps/server/api.py` | Add `POST /api/voice/call-client` — dials a Twilio Client identity |
| `src/apps/kiosk/web/kiosk.js` | Register device at boot; wire `device.on('incoming')`; add Answer/Decline UI |
| `src/apps/kiosk/web/kiosk.css` | Add `.kiosk-incoming-call` fullscreen overlay styles |
| `meridian-ios/APIService.swift` | Replace `requestCall` body to hit `/api/voice/call-client` instead of `/api/calls/request` |

## Step-by-step implementation

### 1. `src/apps/server/twilio_voice.py` — give the kiosk a Twilio identity

In `api_voice_token()`, the kiosk fetches this at boot. Add two lines to the existing grant:

```python
grant = VoiceGrant(
    outgoing_application_sid=twiml_app_sid,
    incoming_allow=True,           # NEW — allows inbound WebRTC to this identity
)
token.identity = g.user_id        # NEW — kiosk_user_id becomes the routable Twilio identity
```

The kiosk's `user_id` (e.g. `fm_care_001`) is now a Twilio Client identity. iOS will dial it by name.

### 2. `src/apps/server/api.py` — new route to place a call to a Client identity

Add after `api_voice_token`. This is what iOS will call instead of `/api/calls/request`:

```python
@app.route("/api/voice/call-client", methods=["POST"])
def api_voice_call_client():
    """Place an outbound Twilio call to a registered Client identity (kiosk WebRTC device)."""
    data = request.get_json() or {}
    to_identity = (data.get("to_identity") or "").strip()
    if not to_identity:
        return jsonify({"error": "to_identity required"}), 400

    account_sid   = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token    = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    caller_id     = (os.environ.get("TWILIO_CALLER_ID") or "").strip()

    if not all([account_sid, auth_token, caller_id]):
        return jsonify({"error": "Twilio not configured"}), 503

    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse

    twiml = VoiceResponse()
    twiml.dial().client(to_identity)           # routes to the kiosk WebRTC device

    call = TwilioClient(account_sid, auth_token).calls.create(
        twiml=str(twiml),
        to=f"client:{to_identity}",
        from_=caller_id,
    )
    return jsonify({"data": {"sid": call.sid}}), 201
```

Add `TWILIO_CALLER_ID` (a verified Twilio number) to `.env` / Railway env vars.

### 3. `src/apps/kiosk/web/kiosk.js` — register at boot and handle incoming

**3a — Register device at startup.** Find `_on_ready` (called after the boot overlay clears).
At the end of it, add:

```js
// Pre-register Twilio device so incoming calls can ring immediately.
kioskEnsureTwilioDevice()
  .then(function(device) {
    device.on('incoming', function(call) {
      var callerName = call.customParameters
        ? (call.customParameters.get('from_display_name') || call.parameters.From || 'Family member')
        : (call.parameters.From || 'Family member');
      kioskShowIncomingCallUI(call, callerName);
    });
  })
  .catch(function() {
    // Twilio not configured — silent, kiosk still works without calling
  });
```

**3b — Add incoming call UI functions** (add near the other `kioskShow*` functions):

```js
function kioskShowIncomingCallUI(call, callerName) {
  var overlay = document.getElementById('kiosk-incoming-call-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'kiosk-incoming-call-overlay';
    overlay.className = 'kiosk-incoming-call';
    overlay.innerHTML = [
      '<div class="kiosk-incoming-call__box">',
      '  <p class="kiosk-incoming-call__label">Incoming call</p>',
      '  <p class="kiosk-incoming-call__name" id="kiosk-incoming-caller-name"></p>',
      '  <div class="kiosk-incoming-call__actions">',
      '    <button class="kiosk-incoming-call__btn kiosk-incoming-call__btn--answer" id="kioskAnswerBtn">Answer</button>',
      '    <button class="kiosk-incoming-call__btn kiosk-incoming-call__btn--decline" id="kioskDeclineBtn">Decline</button>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
  }

  document.getElementById('kiosk-incoming-caller-name').textContent = callerName;
  overlay.classList.remove('kiosk-incoming-call--hidden');

  document.getElementById('kioskAnswerBtn').onclick = function() {
    call.accept();
    overlay.classList.add('kiosk-incoming-call--hidden');
    kioskShowInCallBar('ON A CALL', callerName);
    call.on('disconnect', function() {
      _kioskTwilioCallUiEnded();
      showToast('Call ended');
    });
    call.on('error', function(err) {
      _kioskTwilioCallUiEnded();
      showToast('Call error: ' + ((err && err.message) || 'unknown'));
    });
  };

  document.getElementById('kioskDeclineBtn').onclick = function() {
    call.reject();
    overlay.classList.add('kiosk-incoming-call--hidden');
  };
}
```

### 4. `src/apps/kiosk/web/kiosk.css` — incoming call overlay

Add at the end of the file:

```css
/* Incoming call overlay — fullscreen, above everything */
.kiosk-incoming-call {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
}

.kiosk-incoming-call--hidden {
  display: none;
}

.kiosk-incoming-call__box {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 6vh 8vw;
  text-align: center;
  min-width: 36vw;
}

.kiosk-incoming-call__label {
  font-size: var(--font-subheader);
  color: var(--text-muted);
  margin: 0 0 1vh;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.kiosk-incoming-call__name {
  font-size: var(--font-hero);
  font-weight: 700;
  color: var(--text);
  margin: 0 0 5vh;
  line-height: 1.1;
}

.kiosk-incoming-call__actions {
  display: flex;
  gap: 4vw;
  justify-content: center;
}

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

.kiosk-incoming-call__btn--answer {
  background: var(--secondary);
  color: #fff;
}

.kiosk-incoming-call__btn--answer:hover {
  filter: brightness(1.1);
}

.kiosk-incoming-call__btn--decline {
  background: var(--warm-delete);
  color: #fff;
}

.kiosk-incoming-call__btn--decline:hover {
  filter: brightness(1.1);
}

@media (prefers-reduced-motion: no-preference) {
  .kiosk-incoming-call__box {
    animation: kiosk-ring-pulse 1s ease-in-out infinite alternate;
  }
}

@keyframes kiosk-ring-pulse {
  from { box-shadow: 0 0 0 0 rgba(30, 140, 100, 0.5); }
  to   { box-shadow: 0 0 0 2.5vw rgba(30, 140, 100, 0); }
}
```

### 5. `meridian-ios/APIService.swift` — call the new endpoint

Replace the body of `requestCall(toUserId:)`. The `toUserId` is the kiosk's Meridian user ID,
which is now also its Twilio identity:

```swift
func requestCall(toUserId: String) async throws {
    let (_, res) = try await request("/api/voice/call-client", method: "POST", body: [
        "to_identity": toUserId
    ])
    guard res.statusCode == 200 || res.statusCode == 201 else {
        throw APIError.serverError("Call failed (\(res.statusCode))")
    }
}
```

`requestCallToDefaultRecipient()` in `APIService.swift` already resolves the kiosk's `userId`
from contacts — no change needed there.

## Environment variables required

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TWIML_APP_SID=APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_CALLER_ID=+1xxxxxxxxxx   # verified Twilio number (new — needed for call-client route)
```

## What the DB poll loop becomes

`_start_incoming_call_poll` in `app.py` can be retired or kept as a dead-letter fallback.
The actual call now goes iOS → Twilio → kiosk WebRTC device directly.
If you keep the poll, change its body to just call `kioskEnsureTwilioDevice()` as a pre-warm
hint rather than navigating screens.

## Testing checklist

- [ ] Kiosk boots and registers Twilio device (check logs for `Twilio API credentials OK`)
- [ ] iOS taps "Place Call" → `POST /api/voice/call-client` returns 201 with a `sid`
- [ ] Kiosk shows incoming call overlay with caller name
- [ ] Tapping Answer connects audio both ways
- [ ] Tapping Decline rejects cleanly, overlay disappears
- [ ] Hanging up on either end clears the in-call bar on the kiosk
- [ ] Kiosk with Twilio not configured: boots silently, no overlay, no crash
