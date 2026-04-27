# 167-call-kiosk — Implementation Status

## Original Goal

Implement iOS → kiosk WebRTC voice calling so a family member on iPhone can ring the kiosk and the care recipient can answer.

## What Was Broken

The signal path existed but did nothing useful:
- iOS called `POST /api/calls/request` → wrote a DB signal ✓
- Kiosk polled `GET /api/calls/incoming` every 1s ✓
- When a signal was found, `_start_incoming_call_poll` in `app.py` called `self._navigate_to("chat")` then acked — **no audio, no ring, no actual call**

The kiosk had a full outbound Twilio Voice JS device (`kioskStartTwilioSpeakerCall`) but:
- Was never registered with a Twilio identity, so Twilio couldn't route inbound calls to it
- `device.on('incoming', ...)` was never wired
- No incoming call UI existed anywhere

## Original Instruction Document

`ios-kiosk-call.md` specified changes to 5 files:

| File | Instruction |
|---|---|
| `src/apps/server/twilio_voice.py` | Add identity + `incoming_allow=True` to kiosk voice token |
| `src/apps/server/api.py` | Add `POST /api/voice/call-client` — dials a Twilio Client identity |
| `src/apps/kiosk/web/kiosk.js` | Register device at boot; wire `device.on('incoming')`; add Answer/Decline UI |
| `src/apps/kiosk/web/kiosk.css` | Add `.kiosk-incoming-call` fullscreen overlay styles |
| `meridian-ios/APIService.swift` | Replace `requestCall` body to hit `/api/voice/call-client` |

## Changes Made (Committed)

### Commit `73abb64` — main implementation

**`src/apps/server/twilio_voice.py`**
- Changed kiosk voice token identity from `kiosk_{user_id}` → `user_id` directly, so iOS can dial it by name
- Added `incoming_allow=True` to `VoiceGrant`
- Added `POST /api/voice/call-client` route inside `register_twilio_voice_routes` — server places a Twilio REST `calls.create()` call to `client:<to_identity>`

**`src/apps/kiosk/web/kiosk.js`**
- Modified `setBootLoading(false)` to trigger one-shot Twilio device pre-registration and wire `device.on('incoming', ...)` (equivalent to `_on_ready` hook)
- Added `kioskShowIncomingCallUI(call, callerName)` — fullscreen Answer/Decline overlay, integrates with existing `kioskShowInCallBar` / `_kioskTwilioCallUiEnded`

**`src/apps/kiosk/web/kiosk.css`**
- Added `.kiosk-incoming-call` fullscreen overlay styles with pulsing ring animation at end of file

**`meridian-ios/APIService.swift`**
- Added `requestCall(toUserId:)` — POSTs `{"to_identity": toUserId}` to `/api/voice/call-client`
- Note: `requestCall` did not previously exist; spec said "replace" but the function was new

### Commit `b57a979` — caller ID fix

**`src/apps/server/twilio_voice.py`**
- Removed `TWILIO_CALLER_ID` dependency introduced in previous commit
- Switched to DB phone lookup (`user_svc.get_user_phone_for_family`) with fallback to `TWILIO_PHONE_NUMBER` / `TWILIO_FROM_NUMBER` env vars (matching the pattern in `api_voice_token`)

iOS project builds cleanly for simulator (`xcodebuild` — no errors).

## Blocker: `from_` Phone Number for `calls.create()`

### The problem

The `POST /api/voice/call-client` route uses Twilio's REST API to place a call to the kiosk WebRTC device:

```python
TwilioClient(...).calls.create(
    twiml=str(twiml),
    to=f"client:{to_identity}",
    from_=caller_id,   # ← THIS is the problem
)
```

Twilio's REST API requires `from_` to be a **Twilio-owned phone number** registered to the account. It cannot be an arbitrary personal phone number.

The `.env` has no `TWILIO_PHONE_NUMBER`, `TWILIO_FROM_NUMBER`, or `TWILIO_CALLER_ID` set. The DB lookup (`user_svc.get_user_phone_for_family`) returns personal phone numbers for most users — these are not valid Twilio `from_` numbers and Twilio will reject them.

### Solutions discussed

**Option A — `TWILIO_CALLER_ID` env var (spec's original suggestion)**
A single account-level Twilio number set in `.env`. Simple, works for demo/single-family. Does not scale to multi-family deployments where different families may have different Twilio numbers.

**Option B — `is_twilio_number` flag on `users.phone`**
Track per-user whether their phone is Twilio-owned. Rejected: even if flagged, there's no clear logic for which user's Twilio number to use as `from_` on any given call.

**Option C — `twilio_number` on `family_circles` table**
Each family has one Twilio number assigned to it. Server looks up the family's Twilio number and uses it as `from_`. Correct for multi-family scale. Requires schema migration and an admin flow to assign numbers to families.

**Option D — iOS uses Twilio Voice SDK directly (no server REST call)**
iOS gets a voice token, registers as a Twilio Client, and calls `client:kiosk_identity` directly via `device.connect()`. No phone number needed for client-to-client WebRTC calls. Eliminates the `from_` problem entirely. Requires iOS to integrate the Twilio Voice SDK.

## Current Status

**Blocked on `from_` resolution.** The implementation is complete and building but the `call-client` route will fail at runtime because there is no valid Twilio `from_` number configured.

### Open questions before unblocking

1. **Does iOS currently use the Twilio Voice SDK at all**, or only HTTP calls to the server? This determines whether Option D is feasible without large iOS changes.

2. **Is the intent to have one Twilio number per family** (multi-family scale) or a single number for the whole account (demo/single-family)?

3. **If Option C (family-level schema):** who/what assigns a Twilio number to a new family? Is there an admin flow for this?

The architectural choice here (Option C or D primarily) should be decided before writing more code.
