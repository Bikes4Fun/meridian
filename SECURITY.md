# Security Implementation Plan

## Identity Model

In the real world, we distinguish:

- **User ID** — The authenticated individual (who is logged in). A user has credentials and may belong to one or more family circles.
- **Family circle** — A shared family/group context. Data (family members, check-ins, contacts, medications, etc.) is scoped to a family circle. Multiple users can be members of the same family circle.
- **Family member** — A tracked person within a family circle (e.g., a child, elderly parent). Not necessarily a login-capable user.

Every request that touches family data must identify both: the authenticated user and the family circle being accessed. The server must verify the user is a member of that family circle.

## Current State (Insecure)

### Identity / Auth
- **API**: Must require both `X-User-Id` and `X-Family-Circle-Id`. Currently has only `X-User-Id` — cannot know which family to update without both. Only `/api/health` exempt. 401 when either missing.
- **Kiosk/TV**: Will pass both `user_id` and `family_circle_id` (from main.py/config). DEMO_MODE currently uses hardcoded IDs; will require both. Demo family circle = `F00000`.
- **Web check-in page** (`checkin.html` + `checkin.js`): No login. Uses hardcoded IDs in JS. Will require both. Anyone can load the page and check in as the default user.
- **API routes**: `/checkin`, `/checkin.js` — require session. Redirect to `/login` if not logged in. `/login` is the entry point (no user/family required). Fake login sets session; check-in page uses session for API calls.
- **DB schema**: Tables must scope by `family_circle_id` — a user can belong to multiple families. Currently `user_id` is overloaded as both identity and family scope; no explicit `family_circle_id`. User IDs already exist; family circle is the missing piece.

### Problems
1. **Check-in is not user-bound**: Hardcoded user_id allows anyone to check in as any family.
2. **No family circle concept**: No way to scope data to a family or to have multiple users in one family.
3. **No login flow**: Web users are never authenticated.
4. **Demo fallbacks**: `main.py` and `checkin.js` use hardcoded IDs when not in production. Demo family circle will be `F00000`.
5. **Single-identity model**: Cannot represent multi-user families or shared access.

## Target State (Secure)

### Principle
Every request that touches family data must include both: (1) `user_id` and (2) `family_circle_id`. Otherwise the API cannot know which family to update. The server verifies the user is a member of that family circle. No exemptions except true public endpoints (e.g. health check).

### Demo Approach (Simplest)
- Use `F00000` as the **family circle ID** (demo family). User IDs already exist in the schema.
- Almost everything requires both `user_id` and `family_circle_id`. No silent fallbacks.
- **Kiosk demo**: Populate demo family; kiosk's demo user IS the patient (the person being cared for). The patient is also a user and a member of the family circle.
- **Webapp for now**: Dropdown to choose family circle + simulate being logged in (pick user). No full auth yet.

### Web App Flow (Full Auth Later)
1. **Login page** — User enters credentials (or uses magic link / OAuth).
2. **Session** — Server establishes session (Flask session cookie or JWT in httpOnly cookie). Session stores `user_id` and `family_circle_id` (or list of circles; user selects active one).
3. **Check-in page** — Only accessible when logged in (or simulated). Redirect to login if no session. Check-in is for the session's active family circle.
4. **API calls** — Server reads `user_id` and `family_circle_id` from session or headers (e.g. `X-User-Id`, `X-Family-Circle-Id`). Verifies user is member of the family circle before returning or mutating data.

### Implementation Tasks

| Phase | Task | Notes |
|-------|------|-------|
| 1 | Add `family_circles` table | ID, name. Data tables scope by `family_circle_id`. |
| 2 | Add `users` credentials + `user_family_circle` | Password hash (or OAuth) in DB. Junction: which users belong to which family circles. |
| 3 | Login page + POST `/api/login` | Validate creds, create session. Store `user_id` and `family_circle_id`. |
| 4 | Logout + session invalidation | POST `/api/logout`. |
| 5 | Session middleware | Resolve `user_id` and `family_circle_id` from session. Verify membership before serving family data. |
| 6 | API: require both identities | Endpoints that touch family data need `g.user_id` and `g.family_circle_id`. Replace or migrate `user_id`-scoped queries to `family_circle_id` where appropriate. |
| 7 | Protect `/checkin` | Require session. Redirect to `/login` if not logged in. Implemented. |
| 8 | Remove `/checkin.js` exemption | Only serve when request has valid session (or same-origin from protected check-in page). |
| 9 | Check-in page: no hardcoded IDs | Get `user_id` and `family_circle_id` from session or dropdown (simulate login). `/api/me` returns current user + active family circle. |
| 10 | Kiosk: require both IDs | Get `user_id` (patient) and `family_circle_id` from config or device binding. Demo: populate demo family; kiosk user = patient in that circle. Fail if either missing. |
| 11 | Demo mode: explicit both IDs | `F00000` as demo family circle ID. Demo user = patient. No silent fallbacks. |
| 12 | CORS / origin restrictions | Restrict `Access-Control-Allow-Origin` where appropriate. |
| 13 | HTTPS, secure cookies | `secure=True`, `samesite` for production. |

### Order of Work
1. Introduce `family_circles` (or repurpose: `F00000` = demo family circle). Migrate data model to scope by `family_circle_id`.
2. API: require both `X-User-Id` and `X-Family-Circle-Id` (or from session) for family-data endpoints.
3. Kiosk: require both from config. Demo: kiosk user = patient in demo family circle.
4. Webapp: dropdown to choose family circle + simulate login (pick user). Protect `/checkin`; no hardcoded IDs.
5. Add full session support + login endpoint when ready.
6. Harden CORS, cookies, and deployment config.
