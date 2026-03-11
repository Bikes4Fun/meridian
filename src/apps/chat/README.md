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

Set these so the server can call the Sendbird Platform API and the client can connect:

- `SENDBIRD_APP_ID` – Application ID (Sendbird Dashboard → Settings → Application → General). Case-sensitive.
- `SENDBIRD_API_TOKEN` – Master or secondary API token (Dashboard → Settings → Application → API tokens).

If either is missing, the `/api/chat/*` endpoints return an error and the chat UI will show a message.

## 3. Flow (PoC)

1. User logs in via existing webapp login (session has `user_id` and `family_circle_id`).
2. Webapp opens `/chat`. The page requests:
   - `GET /api/chat/config` → `{ "app_id": "..." }` (for the JS SDK).
   - `POST /api/chat/token` → server ensures a Sendbird user exists for `g.user_id`, issues a session token, returns `{ "user_id", "session_token" }`.
3. The browser initializes the Sendbird Chat SDK with `app_id`, connects with `user_id` + `session_token`, then lists/creates a group channel and shows messages.

Server-side logic lives in `apps/chat/routes.py` (Platform API: create user, issue session token). No Sendbird SDK dependency on the server; plain `requests` only.

## 4. References

- [Chat Platform API (v3)](https://sendbird.com/docs/chat/platform-api/v3/overview) – create user, issue session token.
- [Chat SDK JavaScript](https://sendbird.com/docs/chat/sdk/v4/javascript/overview) – browser client.
- [Environment-specific (web)](https://sendbird.com/docs/chat/sdk/v4/javascript/getting-started/environment-specific-implementation) – connection/localCache options.
