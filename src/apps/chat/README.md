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
- `SENDBIRD_API_TOKEN` – Master or secondary API token (Dashboard → API tokens). Server uses this to issue session tokens only; we do not create users.
- `SENDBIRD_USER_ID_MAP` – JSON mapping app user_id → existing Sendbird user_id, e.g. `{"fm_001":"patient_sendbird_id"}`. Users must already exist in Sendbird (no auto-create).
- `SENDBIRD_DEFAULT_RECIPIENT_ID` – Sendbird user_id of the default 1:1 chat recipient (e.g. daughter). The patient sends messages to this user.

## 3. Flow (1:1 chat)

1. User logs in (session has `user_id`, `family_circle_id`).
2. Chat page requests:
   - `GET /api/chat/config` → `{ "app_id": "..." }`
   - `POST /api/chat/token` → server looks up Sendbird user_id from SENDBIRD_USER_ID_MAP, issues session token for that existing user, returns `{ "sendbird_user_id", "session_token" }`.
   - `GET /api/chat/recipient` → `{ "sendbird_user_id", "name" }` (who to message, e.g. daughter).
3. Client connects as `sendbird_user_id` with `session_token`, then gets or creates a **distinct group channel** with the recipient (1:1). Messages are sent in that channel; only the two users see them.

Server does not create Sendbird users; it only issues tokens for users defined in SENDBIRD_USER_ID_MAP.

## 4. References

- [Chat Platform API (v3)](https://sendbird.com/docs/chat/platform-api/v3/overview) – create user, issue session token.
- [Chat SDK JavaScript](https://sendbird.com/docs/chat/sdk/v4/javascript/overview) – browser client.
- [Environment-specific (web)](https://sendbird.com/docs/chat/sdk/v4/javascript/getting-started/environment-specific-implementation) – connection/localCache options.
