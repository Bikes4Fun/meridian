# Chatapp

Chat UI and verification for Meridian. Uses Sendbird for messaging.

## Target architecture

**Chatapp API** (its own server) owns all chat/Sendbird logic:
- Connect to Sendbird
- Issue session tokens
- Send messages, receive messages
- Config (app_id etc.), recipient lookup
- Everything needed for chat to work

**Main server API** only directs clients to the chat server:
- Login / session
- `chat-session-url` → returns URL to open chat (e.g. chatapp server)
- `chat-session-bootstrap` → verifies token, sets session, redirects to chatapp
- No Sendbird integration in main server

## Current vs target

**Current:** Chat endpoints (config, token, recipient, Sendbird) live in this app’s `api.py` (dedicated Chatapp Flask server). The main server only issues chat-session URLs and bootstrap redirects to Chatapp.

## Structure

| Path | Purpose |
|------|---------|
| `api.py` | Flask API server. Serves /auth, /api/login, /api/chat/config, /api/chat/token, /api/chat/recipient + static files. |
| `chat_client/` | Chat UI source. Build outputs to `chat_server/dist/`. Handles recipient-from-URL (kiosk) and loadRecipient (webapp). |
| `chat_server/` | Build script; dist served by api.py. API_URL="" at build for same-origin. |
| `verify_api.py` | Runs HTTP checks against chatapp API (login, config, token) when chatapp starts. Prints to terminal. |

## Target flow

1. Webapp/Kiosk gets chat URL from main server (`/api/chat/chat-session-url`).
2. User opens URL → main server `chat-session-bootstrap` verifies token, sets session, redirects to chatapp server.
3. Chatapp server: serves UI **and** API. Client calls chatapp API for config, token, recipient, Sendbird messaging.
