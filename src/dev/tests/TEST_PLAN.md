# Test plan: Security + infrastructure, minimal feature coverage

**Priority:** (1) Cyber security, (2) Infrastructure with persistence, (3) Minimal feature smoke. Deprioritize feature-specific tests.

---

## Security tests

- **Public routes:** `GET /api/health` no headers → 200. `GET /api/login` no auth → accessible.
- **Protected routes → 401:** No `X-User-Id` / `X-Family-Circle-Id` (and no session) → 401 on calendar, medications, contacts (extend beyond calendar).
- **Session:** `/checkin` no session → redirect to `/login`. `/checkin.js` no session → 401.
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
2. Security tests in test_api.py (401, 403 cross-family, /checkin redirect, /checkin.js 401, photo 404).
3. Infrastructure tests (write-then-read, fresh DB, invalid path, init fails loudly).
4. Minimal feature API coverage; fix test_contact; trim service tests.
5. Markers + README.
