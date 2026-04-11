# Test plan: Security + infrastructure, minimal feature coverage

**Priority:** (1) Cyber security, (2) Infrastructure with persistence, (3) Minimal feature smoke. Deprioritize feature-specific tests.

---

## Security gaps (backlog)

| Gap | Status |
|-----|--------|
| CORS | ✅ `test_cors.py` — wildcard when unset, reflect legitimate origin, unlisted gets first configured. |
| Chat token security | ✅ `test_chat_token.py` — expired, tampered signature/payload, missing exp, wrong secret. |
| `apps/chatapp/api.py` | ✅ `test_chatapp.py` — /auth requires token, rejects invalid, accepts valid. Sendbird/token endpoint still untested. |
| `/api/login` input validation | ✅ `test_infrastructure.py` — no body, empty user_id/family_circle_id, missing fields. Oversized input not tested. |
| Emergency alert UI | API behavior tests exist; Playwright kiosk UI tests not implemented. |

---

## Cross-Platform E2E Test Plan

Full-flow tests proving Kiosk ↔ API ↔ iOS/Webapp work together. Each test hits the real Flask server seeded from conftest fixtures.

**API layer tests (pytest)**
- [x] Emergency alert: POST activate → GET status reflects it; per-family isolation (`test_e2e_emergency_alert.py`)
- [ ] Emergency profile: PUT → GET round-trip, PDF returns `b"%PDF"` header + patient name in bytes
- [x] Check-in: POST persists lat/lon → GET checkins returns it (`test_e2e_critical_path.py`)
- [x] Medication: POST → GET returns it in correct time slot — note `data` is `{timed_medications, prn_medications}` (`test_e2e_critical_path.py`)
- [ ] Chat: session URL returns valid URL, bootstrap redirects correctly

**Kiosk UI tests (Playwright)**
- [ ] Alert polling: `alert-active` CSS class appears within 5s, screen navigates to emergency
- [ ] Emergency screen: renders name, DNR badge, allergies, patient photo after profile PUT
- [ ] Family map: Leaflet marker appears after check-in, photo loads (`naturalWidth > 0`)
- [ ] Home screen: newly added medication appears in correct time slot
- [ ] Chat handoff: chatapp window opens, not a 404/500

**iOS layer tests (Detox)**
- [ ] Alert: push notification/banner appears when alert activated via API
- [ ] Profile: emergency profile data visible in iOS app after PUT
- [ ] Check-in: POST from iOS device persists and appears in kiosk family map

**Fix weak/wrong existing tests**
- [x] `test_happy_path` — replaced with DB-dependent calendar/events
- [x] `test_deliberate_failure_causes_suite_to_fail` — did not exist
- [x] `test_public_responses_do_not_expose_secrets` → `test_error_responses_do_not_expose_secret_key`
- [x] `test_execute_update_failure` — asserts `"no such table"`
- [x] `test_transaction_rollback_on_error` — duplicate PK constraint, asserts 1 row persisted

**Security gaps (untested)**
- [x] CORS: wildcard, reflect origin, unlisted rejected
- [x] Chat token: expired, tampered, missing fields
- [x] `/api/login`: empty user_id, missing fields (oversized input not tested)

**Setup**
- [x] Register `integration` marker in `pytest.ini` — already present
- [ ] Add `e2e` marker to `pytest.ini`
- [ ] Add `login_session()` helper to conftest
- [ ] Create `src/dev/tests/playwright/` directory

---

## Security tests

- **Public routes:** `GET /api/health` no headers → 200. `POST /api/login` with valid body no session → 200 (see `test_infrastructure.py`).
- **Protected routes → 401:** No `X-User-Id` / `X-Family-Circle-Id` (and no session) → 401 on calendar, medications, contacts (extend beyond calendar).
- **Session:** Protected dashboard HTML is served at `/` / `index.html` with injected `window.__MERIDIAN_SESSION__`; API routes return **401** without `X-User-Id` / `X-Family-Circle-Id` (or valid session) per `test_security.py`. (There is no separate `/checkin` page in the current server routes.)
- **Cross-family → 403:** Auth as family A, request `/api/family_circles/family_B/...` → 403, body says family mismatch.
- **Check-in identity:** POST with matching `user_id` → 201; with wrong `user_id` → 403.
- **Photo:** User not in requester’s family → 404. Path traversal (`..` or `/` in filename) → 404 if feasible.

---

## Infrastructure tests

- **Server:** `create_server_app(db_path=...)` with real DB; health 200 with no headers. Fail loudly if init throws.
- **DB persistence:** Write row → read it back in same test (proves writes stick).
- **Fresh DB:** Schema only, no seed → tables exist and are queryable.
- **Bad config:** Invalid DB path → clear error, not silent.
- Keep schema-creation + optional rollback; trim redundant DB tests (e.g. get_table_info/count).

---

## Conftest (match schema)

- `users` + `user_family_circle` for test user and care-recipient; `care_recipients` row.
- Medications: `care_recipient_user_id` (not `family_circle_id`); align medication_times / medication_to_time.
- Contacts: `primary_emergency` / `secondary_emergency` (not `'emergency'`).
- Calendar: `REF_DATE` (e.g. `2024-01-15`), seed events on that date.
- Document fixture as source of truth in conftest or README.

---

## Feature tests (minimal)

- API: One GET per protected resource → 200 + expected shape (medications, contacts, emergency-contacts, medical-summary, emergency-profile, family-members, checkins). No exhaustive field checks.
- Prefer API over service-layer tests; trim or remove duplicate service tests. Fix test_contact: correct method name, concrete assertions (no `len >= 0`).
- Time service: only true unit (no DB); keep for `-m unit`.

---

## Run method & docs

- **Command:** `PYTHONPATH=src pytest src/dev/tests` (from repo root). Optional: `-m unit` / `-m integration`.
- **Markers:** `unit` = no DB (time_service only); `integration` = DB or API. Reclassify tests that use `populated_test_db` or API client as integration.
- README: paths `dev/tests/`, real file names (`test_database.py`, etc.), single run command, "unit = no DB."
- CI: one job, `PYTHONPATH=src pytest src/dev/tests`.

---

## Order

1. Conftest (users, care_recipients, medications, contact priorities, REF_DATE).
2. Security tests in `test_security.py` (401, 403 cross-family, check-in identity, photo 404).
3. Infrastructure tests (write-then-read, fresh DB, invalid path, init fails loudly).
4. Minimal feature API coverage; fix test_contact; trim service tests.
5. Markers + README.
