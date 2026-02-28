# Security Implementation Plan

## Current State (Insecure)

### Identity / Auth
- **API**: Requires `X-User-Id` header. Only `/api/health` exempt. 401 when missing.
- **Kiosk/TV**: Passes `user_id` from `main.py`; DEMO_MODE uses hardcoded `0000000000`.
- **Web check-in page** (`checkin.html` + `checkin.js`): No login. Uses hardcoded `USER_ID = '0000000000'` in JS. Anyone can load the page and check in as the default user.
- **API routes**: `/checkin`, `/checkin.js` — if we required `X-User-Id`, the page could not load (browser GETs don't send custom headers). Current behavior: all paths except `/api/health` require the header, so `/checkin` and `/checkin.js` would 401 on load. Need to verify actual server config.

### Problems
1. **Check-in is not user-bound**: Hardcoded user_id allows anyone to check in as any family.
2. **No login flow**: Web users are never authenticated.
3. **Demo fallbacks**: `main.py` and `checkin.js` both use `0000000000` when not in production.

## Target State (Secure)

### Principle
Every request that touches user data must be tied to an authenticated identity. No exemptions except true public endpoints (e.g. health check).

### Web App Flow
1. **Login page** — User enters credentials (or uses magic link / OAuth).
2. **Session** — Server establishes session (Flask session cookie or JWT in httpOnly cookie). Session stores `user_id`.
3. **Check-in page** — Only accessible when logged in. Redirect to login if no session.
4. **API calls** — Either:
   - Same-origin: server reads `user_id` from session (no `X-User-Id` needed from client), or
   - Server sets `user_id` from session and injects into response/JS for client to send in header.

### Implementation Tasks

| Phase | Task | Notes |
|-------|------|-------|
| 1 | Add `users` credentials | Password hash (or OAuth) in DB. |
| 2 | Login page + POST `/api/login` | Validate creds, create session. |
| 3 | Logout + session invalidation | POST `/api/logout`. |
| 4 | Session middleware | For same-origin requests, resolve `user_id` from session instead of (or in addition to) `X-User-Id`. |
| 5 | Protect `/checkin` | Require session. Redirect to login if not logged in. |
| 6 | Remove `/checkin.js` exemption | Only serve when request has valid session (or same-origin from protected check-in page). |
| 7 | Check-in page: no hardcoded USER_ID | Get `user_id` from session (e.g. `/api/me` returns current user) or from server-injected config. |
| 8 | Kiosk: remove DEMO_MODE fallback | Get `user_id` from config or device binding, fail if missing. |
| 9 | CORS / origin restrictions | Restrict `Access-Control-Allow-Origin` where appropriate. |
| 10 | HTTPS, secure cookies | `secure=True`, `samesite` for production. |

### Order of Work
1. Add session support + login endpoint (minimal: password in users table).
2. Protect `/checkin` and `/checkin.js` — require session.
3. Check-in page: call `/api/me` or get user from session; use for API calls.
4. Remove all hardcoded `0000000000` and DEMO_MODE fallbacks.
5. Harden CORS, cookies, and deployment config.
