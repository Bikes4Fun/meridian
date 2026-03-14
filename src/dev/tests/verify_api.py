"""Mirrors local_sendbird_api Postman collection: login, config, token, 1:1 channel, send message, list messages."""

import json
import logging
import os


def _fmt(v):
    return (
        json.dumps(v, indent=2)
        if isinstance(v, dict)
        else json.dumps(v, indent=2) if isinstance(v, list) else str(v)
    )


def verify_api(api_url, logger=None):
    """Run same tests as Postman: login, config, token, create channel, send message, list messages."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; skipping API verification")
        return
    base = api_url.rstrip("/")
    session = requests.Session()
    steps = []  # (name, query, response)

    # 1. login
    query = "POST %s/api/login\n  body: %s" % (
        base,
        json.dumps({"user_id": "fm_care_001", "family_circle_id": "F00000"}),
    )
    try:
        r = session.post(
            base + "/api/login",
            json={"user_id": "fm_care_001", "family_circle_id": "F00000"},
            timeout=5,
        )
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        steps.append(("login", query, r.status_code, resp))
    except Exception as e:
        steps.append(("login", query, "ERR", str(e)))

    # 2. config
    query = "GET %s/api/chat/config" % base
    try:
        r = session.get(base + "/api/chat/config", timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        steps.append(("config", query, r.status_code, resp))
    except Exception as e:
        steps.append(("config", query, "ERR", str(e)))

    # 3. token
    query = "POST %s/api/chat/token\n  body: {}" % base
    token_data = None
    try:
        r = session.post(base + "/api/chat/token", json={}, timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        if isinstance(resp, dict):
            token_data = resp
        steps.append(("token", query, r.status_code, resp))
    except Exception as e:
        steps.append(("token", query, "ERR", str(e)))

    # 4. recipient
    query = "GET %s/api/chat/recipient" % base
    recipient_data = None
    try:
        r = session.get(base + "/api/chat/recipient", timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        if r.ok and isinstance(resp, dict):
            recipient_data = resp
        steps.append(("recipient", query, r.status_code, resp))
    except Exception as e:
        steps.append(("recipient", query, "ERR", str(e)))

    # 5. create channel (our API)
    query = "POST %s/api/chat/channel\n  body: {}" % base
    channel_url_from_api = None
    try:
        r = session.post(base + "/api/chat/channel", json={}, timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        if r.ok and isinstance(resp, dict):
            channel_url_from_api = resp.get("channel_url", "").strip()
        steps.append(("create channel (API)", query, r.status_code, resp))
    except Exception as e:
        steps.append(("create channel (API)", query, "ERR", str(e)))

    # 6–8. Sendbird Platform API (optional, if env set)
    app_id = os.environ.get("SENDBIRD_APP_ID", "").strip()
    api_token = os.environ.get("SENDBIRD_API_TOKEN", "").strip()
    sender = token_data.get("sendbird_user_id", "").strip() if token_data else ""
    recipient = (recipient_data or {}).get("sendbird_user_id", "").strip() or None
    sb_base = "https://%s.sendbird.com/v3" % app_id if app_id else ""
    channel_url = None

    if app_id and api_token and sender and recipient:
        # 6. create channel (Platform API directly)
        body = {"user_ids": [sender, recipient], "is_distinct": True, "name": "Family"}
        query = "POST %s/group_channels\n  body: %s" % (sb_base, json.dumps(body))
        try:
            r = requests.post(
                sb_base + "/group_channels",
                headers={"Api-Token": api_token, "Content-Type": "application/json"},
                json=body,
                timeout=10,
            )
            resp = (
                r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else r.text
            )
            channel_url = resp.get("channel_url", "") if isinstance(resp, dict) else ""
            steps.append(("create channel", query, r.status_code, resp))
        except Exception as e:
            steps.append(("create channel", query, "ERR", str(e)))

        if channel_url:
            # 7. send message
            body = {
                "message_type": "MESG",
                "user_id": sender,
                "message": "Hello, can you hear me?",
            }
            query = "POST %s/group_channels/%s/messages\n  body: %s" % (
                sb_base,
                channel_url,
                json.dumps(body),
            )
            try:
                r2 = requests.post(
                    sb_base + "/group_channels/" + channel_url + "/messages",
                    headers={
                        "Api-Token": api_token,
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=10,
                )
                resp2 = (
                    r2.json()
                    if r2.headers.get("content-type", "").startswith("application/json")
                    else r2.text
                )
                steps.append(("send message", query, r2.status_code, resp2))
            except Exception as e:
                steps.append(("send message", query, "ERR", str(e)))

            # 8. list messages
            url = (
                "%s/group_channels/%s/messages?message_ts=99999999999999&prev_limit=10"
                % (sb_base, channel_url)
            )
            query = "GET %s" % url
            try:
                r3 = requests.get(url, headers={"Api-Token": api_token}, timeout=10)
                resp3 = (
                    r3.json()
                    if r3.headers.get("content-type", "").startswith("application/json")
                    else r3.text
                )
                steps.append(("list messages", query, r3.status_code, resp3))
            except Exception as e:
                steps.append(("list messages", query, "ERR", str(e)))
    else:
        steps.append(
            (
                "Sendbird",
                "(skipped)",
                "SKIP",
                "SENDBIRD_APP_ID/API_TOKEN or token missing",
            )
        )

    print("API verification (chatapp):")
    for i, (name, q, status, resp) in enumerate(steps, 1):
        print("\n%s: %s" % (i, name))
        print("    query:")
        for line in q.split("\n"):
            print("      %s" % line)
        print("    response: %s" % status)
        for line in _fmt(resp).split("\n"):
            print("      %s" % line)
