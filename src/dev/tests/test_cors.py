"""
CORS tests: verify Access-Control-Allow-Origin behavior.
add_cors() reads os.environ at response time (per-request), so env mutations
before the request affect the CORS headers. No per-test app fixture needed.
"""

import os
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest


@pytest.mark.integration
def test_cors_wildcard_when_origin_unset(api_client):
    """When CORS_ORIGIN is unset, responses get Access-Control-Allow-Origin: *."""
    with _clear_cors_origin():
        r = api_client.get("/api/health")
        assert r.status_code == 200
        assert r.headers.get("Access-Control-Allow-Origin") == "*"


@pytest.mark.integration
def test_cors_reflects_legitimate_origin(api_client):
    """When CORS_ORIGIN is set and request Origin matches, response reflects it."""
    orig = os.environ.get("CORS_ORIGIN")
    try:
        os.environ["CORS_ORIGIN"] = "https://app.example.com"
        r = api_client.get(
            "/api/health",
            headers={"Origin": "https://app.example.com"},
        )
        assert r.status_code == 200
        assert r.headers.get("Access-Control-Allow-Origin") == "https://app.example.com"
    finally:
        if orig is not None:
            os.environ["CORS_ORIGIN"] = orig
        else:
            os.environ.pop("CORS_ORIGIN", None)


@pytest.mark.integration
def test_cors_unlisted_origin_gets_first_configured(api_client):
    """When CORS_ORIGIN is set and request Origin is not in list, use first configured origin."""
    orig = os.environ.get("CORS_ORIGIN")
    try:
        os.environ["CORS_ORIGIN"] = "https://app.example.com,https://other.example.com"
        r = api_client.get(
            "/api/health",
            headers={"Origin": "https://evil.com"},
        )
        assert r.status_code == 200
        assert r.headers.get("Access-Control-Allow-Origin") == "https://app.example.com"
    finally:
        if orig is not None:
            os.environ["CORS_ORIGIN"] = orig
        else:
            os.environ.pop("CORS_ORIGIN", None)


def _clear_cors_origin():
    """Context manager to clear CORS_ORIGIN for test isolation."""

    class _EnvRestore:
        def __enter__(self):
            self._orig = os.environ.pop("CORS_ORIGIN", None)
            return self

        def __exit__(self, *args):
            if self._orig is not None:
                os.environ["CORS_ORIGIN"] = self._orig

    return _EnvRestore()
