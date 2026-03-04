---
name: Define and run tests
overview: Clarify which tests actually demonstrate important functionality, fix test-data/schema and docs inconsistencies, and define a single canonical way to run tests (with optional markers).
todos: []
isProject: false
---

# Define Tests That Show Important Functionality

## Current state

- **Tests live in** [dev/tests/](dev/tests/): `conftest.py`, `test_api.py`, `test_calendar.py`, `test_contact.py`, `test_database.py`, `test_medication.py`, `test_time_service.py`, plus `pytest.ini` and README.
- **Run method** (from repo root): `PYTHONPATH=src pytest src/dev/tests` ([README.md](README.md)). The [dev/tests/README.md](dev/tests/README.md) uses `pytest` and paths like `tests/test_*.py`, which do not match the real layout (`dev/tests/test_*.py`).
- **pytest.ini** has `testpaths = tests`; when you pass `src/dev/tests` on the CLI that path is used, but the README inside dev/tests is misleading.

### Problems (why it feels like a mess)

1. **Test data vs current schema**
  - [conftest.py](dev/tests/conftest.py) inserts into `medications` with `family_circle_id`, but [schema.sql](apps/server/schema.sql) has `medications.care_recipient_user_id`. MedicationService loads by `care_recipient_user_id` ([medical.py](apps/server/services/medical.py)), so integration tests that expect “loaded meds from DB” may see empty data.
  - Conftest uses contact `priority = 'emergency'`; [contact.py](apps/server/services/contact.py) filters emergency contacts with `priority IN ('primary_emergency', 'secondary_emergency')`, so “emergency contacts” in tests may be empty.
  - No `care_recipients` or `user_family_circle` / `users` rows in conftest, so emergency profile, family-members, and medication loading from DB are not properly exercised.
2. **Unit vs integration markers**
  - Many tests marked `@pytest.mark.unit` use fixtures that depend on `populated_test_db` (e.g. `contact_service`, `medication_service`, `emergency_service`). So “unit” runs still use the DB; only [test_time_service.py](dev/tests/test_time_service.py) is truly unit (no DB).
  - “Run only unit tests (fast, no database)” in the README is inaccurate for most of those tests.
3. **API coverage**
  - [test_api.py](dev/tests/test_api.py) covers: health, calendar (headers, month, events), auth (both headers required), check-in (success + forbidden). It does **not** hit: medications, contacts, emergency-contacts, medical-summary, emergency-profile (GET/PUT), emergency-profile/pdf, family-members, checkins list, named-places, login/session, alert. So the main user-facing flows (ICE/emergency, meds, contacts) are not asserted at the API layer.
4. **Weak or misleading assertions**
  - e.g. `assert len(result.data) >= 0` (always true); calendar events test that “depends on current date matching” with no fixed reference date; medical summary only checks that the string contains “medical” or “medication” or “allergy”.
5. **Docs vs reality**
  - [dev/tests/README.md](dev/tests/README.md) lists `test_database_manager.py`, `test_calendar_service.py`, `test_medication_service.py`; actual files are `test_database.py`, `test_calendar.py`, `test_medication.py`.

---

## What “important functionality” should tests show

From the API and app purpose (dementia care / family circle):


| Area                   | What should be shown working                                                                                                                                   |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Auth**               | Missing `X-User-Id` or `X-Family-Circle-Id` → 401; wrong family in URL vs header → 403.                                                                        |
| **Calendar**           | Headers and month data return 200 and expected shape; events for a date return 200 and list.                                                                   |
| **Medications**        | GET medications returns 200 and structure (e.g. `timed_medications` / `prn_medications` or equivalent).                                                        |
| **Contacts / ICE**     | GET contacts and GET emergency-contacts return 200 and list; medical-summary and emergency-profile GET return 200 (and profile has expected shape if present). |
| **Check-in**           | POST check-in with correct user succeeds (201); wrong user → 403; GET checkins returns 200.                                                                    |
| **DB / app bootstrap** | Schema creation and basic read/write work so the app can start and serve.                                                                                      |


So the tests that are “most helpful” are ones that **demonstrate these flows end-to-end (via API) or via service + DB**, with **deterministic data** and **meaningful assertions** (no `>= 0`, no “might be empty because data doesn’t match schema”).

---

## 1. Decide which tests to keep and what they must do

**Keep and fix (minimal set that proves the above):**

- **API tests** ([test_api.py](dev/tests/test_api.py))  
  - Keep: health, calendar (headers, month, events), auth (401 without headers, 403 wrong family), check-in (success + forbidden).  
  - Add (at least one test per critical path):  
    - GET medications → 200, `data` with expected keys.  
    - GET contacts → 200, `data` list.  
    - GET emergency-contacts → 200, `data` list.  
    - GET medical-summary → 200, `data` string.  
    - GET emergency-profile → 200 (and shape if not empty).  
    - GET family-members → 200, `data` list.  
    - GET checkins → 200, `data` list.
  - Use a **single** `API_HEADERS` and `populated_test_db` so one fixture set proves “with valid auth and test family, these endpoints respond correctly.”
- **Database** ([test_database.py](dev/tests/test_database.py))  
  - Keep: schema creation, one simple query/update, and (if present) rollback behavior. These show the DB layer works. Optionally trim redundant tests (e.g. multiple “success” variants) to reduce noise.
- **Time service** ([test_time_service.py](dev/tests/test_time_service.py))  
  - Keep as the only true “unit” tests (no DB). They show time formatting works; consider tightening assertions to format only if you want to avoid flakiness from “current” date/time.
- **Service-layer tests** (calendar, contact, medication, emergency)  
  - **Option A (recommended for “minimal set”)**: Rely on **API tests** above to prove calendar, contacts, emergency, medications through the real stack; treat service tests as optional or remove duplicates that don’t add more than the API.  
  - **Option B**: Keep a **small** set of service tests that exercise behavior not visible at API level (e.g. medication “mark done” or overdue), and fix their fixtures so they use the same schema and priority values as production.

**Required properties for every kept test:**

- **Deterministic**: No reliance on “today” or “current time” unless strictly necessary (e.g. time_service); use reference dates or fixed test data where possible.  
- **Meaningful assertions**: Assert on structure and at least one concrete value (e.g. status code, presence of keys, list length from known test data). Remove `assert len(...) >= 0` and “comment that exact count depends on setup.”  
- **No silent fallbacks**: If a test needs a care recipient or emergency contact, fixture must create one; test should fail if the setup is wrong, not pass with empty data.

---

## 2. Fix test data and fixtures so they match the app

- **conftest.py**  
  - Align with [schema.sql](apps/server/schema.sql):  
    - Add `users` and `user_family_circle` for at least one user in `test_family`.  
    - Add `care_recipients` linking that family to a `care_recipient_user_id`.  
    - Insert into `medications` using `care_recipient_user_id` (and match `medication_times` / `medication_to_time` if needed).
  - Use contact priorities the app expects: e.g. `primary_emergency` or `secondary_emergency` for contacts that should appear in emergency-contacts.  
  - Document in conftest (or README) that this data is the single source of truth for API and integration tests.
- **Markers**  
  - Reclassify tests that use `populated_test_db` (or any DB) as `@pytest.mark.integration`; reserve `@pytest.mark.unit` for tests that use no DB (e.g. time_service only). Update README so “unit = no database” is true.
- **Calendar**  
  - If you keep a calendar service test that checks “events for a date,” use a fixed reference date (e.g. from conftest) and insert events for that date so the assertion is deterministic.

---

## 3. How to run tests

- **Canonical command (from repo root)**  
  - `PYTHONPATH=src pytest src/dev/tests`  
  - Optional: `-v` for verbose; `-m unit` for unit-only; `-m integration` for integration-only after markers are fixed.
- **pytest.ini**  
  - Either set `testpaths = dev/tests` when running from `src`, or leave as-is and always pass `src/dev/tests` from repo root so the path is explicit. Prefer one documented approach.
- **README updates**  
  - [dev/tests/README.md](dev/tests/README.md): Fix all paths to `dev/tests/` and real file names (`test_database.py`, `test_calendar.py`, `test_medication.py`, `test_contact.py`). Document that “Run only unit tests” means “no DB” and that most tests are integration. Add the canonical run command and, if desired, a one-liner for CI (e.g. `PYTHONPATH=src pytest src/dev/tests -m "unit or integration"` or just no filter).
- **CI (e.g. GitHub Actions)**  
  - Single job: install deps, then run `PYTHONPATH=src pytest src/dev/tests` (and optionally `--tb=short`). No need for multiple runners unless you add more markers later.

---

## Summary


| Step | Action                                                                                                                                                                           |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Define “important” as: auth, calendar, medications, contacts/emergency, check-in, and DB bootstrap; tests should prove these with real requests or service+DB.                   |
| 2    | Fix conftest to match schema (users, care_recipients, medications by care_recipient_user_id, contact priorities) and make tests deterministic.                                   |
| 3    | Add API tests for medications, contacts, emergency-contacts, medical-summary, emergency-profile, family-members, checkins; keep existing health, calendar, auth, check-in tests. |
| 4    | Correct unit vs integration markers; remove or tighten weak assertions.                                                                                                          |
| 5    | Document one run method: `PYTHONPATH=src pytest src/dev/tests`; fix dev/tests README paths and file names; optionally add a minimal CI workflow.                                 |


After this, the suite will be smaller and focused on proving that the critical paths work, with one clear way to run it and no silent passes due to schema or priority mismatches.