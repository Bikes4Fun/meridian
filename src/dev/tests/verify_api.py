"""Manual API smoke check: login, chat config/token/recipient/channel (Meridian server)."""

import json
import logging


def _fmt(v):
    return (
        json.dumps(v, indent=2)
        if isinstance(v, dict)
        else json.dumps(v, indent=2) if isinstance(v, list) else str(v)
    )


def verify_api(api_url, logger=None):
    """Exercise chat-related HTTP endpoints against a running API."""
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; skipping API verification")
        return
    base = api_url.rstrip("/")
    session = requests.Session()
    steps = []

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

    query = "POST %s/api/chat/token\n  body: {}" % base
    try:
        r = session.post(base + "/api/chat/token", json={}, timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        steps.append(("token", query, r.status_code, resp))
    except Exception as e:
        steps.append(("token", query, "ERR", str(e)))

    query = "GET %s/api/chat/recipient" % base
    try:
        r = session.get(base + "/api/chat/recipient", timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        steps.append(("recipient", query, r.status_code, resp))
    except Exception as e:
        steps.append(("recipient", query, "ERR", str(e)))

    query = "POST %s/api/chat/channel\n  body: {}" % base
    try:
        r = session.post(base + "/api/chat/channel", json={}, timeout=5)
        resp = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        steps.append(("create channel (API)", query, r.status_code, resp))
    except Exception as e:
        steps.append(("create channel (API)", query, "ERR", str(e)))

    print("Meridian API verification:")
    for i, (name, q, status, resp) in enumerate(steps, 1):
        print("\n%s: %s" % (i, name))
        print("    query:")
        for line in q.split("\n"):
            print("      %s" % line)
        print("    response: %s" % status)
        for line in _fmt(resp).split("\n"):
            print("      %s" % line)
