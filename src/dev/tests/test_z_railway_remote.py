"""
Remote Railway API tests. Opt-in: PYTHONPATH=src pytest src/dev/tests -m remote

Hits the live Railway deployment. Verifies both API and database are running.
Skips if Railway URL not configured or unreachable.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
import urllib.request
import urllib.error
import json

# Demo data IDs (from seed.py); Railway DB should have these when seeded
DEMO_FAMILY_CIRCLE_ID = "F00000"
DEMO_USER_ID = "fm_001"


def _get_railway_base_url():
    """Get Railway URL; return None if not configured."""
    try:
        from shared.config import get_api_base_url

        return get_api_base_url().rstrip("/")
    except Exception:
        return None


@pytest.mark.remote
def test_railway_api_health():
    """Railway API is running: GET /api/health returns 200."""
    base = _get_railway_base_url()
    if not base:
        pytest.skip(
            "Railway API URL not configured (api_config.json or RAILWAY_API_URL)"
        )
    url = base + "/api/health"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data.get("status") == "ok"
    except urllib.error.URLError as e:
        pytest.skip("Railway API unreachable: %s" % e)


@pytest.mark.remote
def test_railway_database_reachable():
    """Railway database is running: family-members endpoint returns data (queries DB)."""
    base = _get_railway_base_url()
    if not base:
        pytest.skip("Railway API URL not configured")
    url = base + "/api/family_circles/%s/family-members" % DEMO_FAMILY_CIRCLE_ID
    req = urllib.request.Request(url)
    req.add_header("X-User-Id", DEMO_USER_ID)
    req.add_header("X-Family-Circle-Id", DEMO_FAMILY_CIRCLE_ID)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert "data" in data
            # DB is reachable if we got a response; demo may have 0+ members
            assert isinstance(data["data"], list)
    except urllib.error.HTTPError as e:
        if e.code == 404 or e.code == 403:
            pytest.fail(
                "Database unreachable or demo data not seeded (got %s)" % e.code
            )
        raise
    except urllib.error.URLError as e:
        pytest.fail("Railway API unreachable: %s" % e)
