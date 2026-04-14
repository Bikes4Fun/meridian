"""
POST Sendbird Platform API session token using SENDBIRD_* from repo-root .env.

Run from repo:  python src/dev/sendbird_smoke.py [sendbird_user_id]
Run from src:   python dev/sendbird_smoke.py [sendbird_user_id]

Default user id: SENDBIRD_SMOKE_USER env, else "testpatient".
"""

import json
import os
import sys
import time

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

if "SENDBIRD_SSL_VERIFY" not in os.environ:
    os.environ["SENDBIRD_SSL_VERIFY"] = "0"

import requests

from apps.server.database_services.sendbird import _sendbird_platform_requests_verify_tls


def _api_base() -> str:
    raw = (os.getenv("SENDBIRD_APP_ID") or "").strip()
    if raw.startswith("api-"):
        raw = raw[4:]
    if not raw:
        return ""
    return f"https://api-{raw}.sendbird.com/v3"


def main() -> int:
    token = (os.getenv("SENDBIRD_API_TOKEN") or "").strip()
    base = _api_base()
    user_id = (
        (sys.argv[1] if len(sys.argv) > 1 else "").strip()
        or (os.getenv("SENDBIRD_SMOKE_USER") or "").strip()
        or "testpatient"
    )
    if not token or not base:
        print(
            "Missing SENDBIRD_APP_ID or SENDBIRD_API_TOKEN in environment (.env at repo root).",
            file=sys.stderr,
        )
        return 1

    import urllib.parse

    encoded = urllib.parse.quote(user_id, safe="")
    url = f"{base}/users/{encoded}/token"
    expires_at = int((time.time() + 7 * 24 * 3600) * 1000)
    verify = _sendbird_platform_requests_verify_tls()
    try:
        r = requests.post(
            url,
            headers={
                "Api-Token": token,
                "Content-Type": "application/json; charset=utf8",
            },
            json={"expires_at": expires_at},
            timeout=15,
            verify=verify,
        )
    except requests.RequestException as e:
        print(f"Request failed (no HTTP response): {e}", file=sys.stderr)
        return 2

    print(f"HTTP {r.status_code}")
    ct = (r.headers.get("content-type") or "").lower()
    if "json" in ct:
        try:
            print(json.dumps(r.json(), indent=2))
        except (ValueError, TypeError):
            print(r.text[:2000])
    else:
        print(r.text[:2000])
    return 0 if r.status_code == 200 else 3


if __name__ == "__main__":
    raise SystemExit(main())
