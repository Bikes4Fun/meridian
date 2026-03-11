# Sendbird Chat (proof of concept)

Minimal integration for Sendbird Chat. Kept in `apps/chat/` so it stays separate from the rest of the app. Video/calls can be added later; this PoC is chat-only.

## 1. Allowed domains (Sendbird Dashboard)

In **Sendbird Dashboard → Your application → Settings → Security (or Application)** find **Allowed domains** (whitelist). Add entries so the Chat SDK can run in your browser.

- **Local testing (no port in URL):**  
  `http://localhost`  
  `http://127.0.0.1`

- **Local testing with port (e.g. app at http://localhost:8080):**  
  Sendbird’s docs say: *“Do not include port numbers, or anything after a domain.”*  
  Some setups still allow origins with a port. If chat fails on `http://localhost:8080`, try adding exactly:  
  `http://localhost:8080`  
  and `http://127.0.0.1:8080`  
  If your dashboard rejects those, run the app on port 80 so the URL has no port, or use a tunnel (e.g. ngrok) and add the tunnel URL.

- **Production:**  
  Add your real origins, e.g. `https://www.example.com`, `https://app.example.com`. No path, no port.

Format: one domain per line or comma-separated; include protocol (`http://` or `https://`). Do not include path or trailing slash.

## 2. Environment variables

- `SENDBIRD_APP_ID` – Application ID (Sendbird Dashboard → Settings → Application → General). Case-sensitive.
- `SENDBIRD_API_TOKEN` – Master or secondary API token (Dashboard → Settings → Application → API tokens).

**User mapping (demo):** Users must already exist in Sendbird; we do not create them. Map your app user to their Sendbird identity and to who they chat with:

- `SENDBIRD_DEMO_APP_USER_ID` – Your app’s user_id for the kiosk/demo user (e.g. `fm_001`).
- `SENDBIRD_DEMO_SENDBIRD_USER_ID` – That user’s Sendbird user id (must already exist in Sendbird).
- `SENDBIRD_DEMO_CHAT_WITH_ID` – Sendbird user id of the person they message (e.g. daughter).

Later you can replace this with a DB lookup (e.g. by phone/email) instead of demo env vars.

## 3. Flow (1:1 chat)

1. User logs in (session has `user_id` and `family_circle_id`).
2. Webapp opens `/chat`. The page requests:
   - `GET /api/chat/config` → `{ "app_id": "..." }`.
   - `POST /api/chat/token` → server looks up Sendbird user id and “chat with” id (from config/DB), issues a session token for the Sendbird user, returns `{ "user_id", "session_token", "chat_with_user_id" }`.
3. The client connects to Sendbird as `user_id`, then gets or creates a **1:1 distinct group channel** with `chat_with_user_id` (e.g. patient ↔ daughter). Messages are only between those two.

Server-side: no user creation; only issue session token. Logic in `apps/chat/routes.py` and `apps/chat/config.py`.

## 4. References

- [Chat Platform API (v3)](https://sendbird.com/docs/chat/platform-api/v3/overview) – create user, issue session token.
- [Chat SDK JavaScript](https://sendbird.com/docs/chat/sdk/v4/javascript/overview) – browser client.
- [Environment-specific (web)](https://sendbird.com/docs/chat/sdk/v4/javascript/getting-started/environment-specific-implementation) – connection/localCache options.
