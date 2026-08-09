"""Sprint 1 acceptance tests: health endpoints."""

from app import __version__
from app.main import DASHBOARD_INDEX


def _dashboard_built() -> bool:
    return DASHBOARD_INDEX is not None and DASHBOARD_INDEX.is_file()


def test_root_serves_dashboard_when_built(client):
    resp = client.get("/")
    assert resp.status_code == 200
    if _dashboard_built():
        assert resp.headers["content-type"].startswith("text/html")
        assert "<!doctype html" in resp.text.lower()
    else:
        assert resp.json() == {"status": "ok"}


def test_spa_fallback_serves_dashboard_when_built(client):
    resp = client.get("/system")
    if not _dashboard_built():
        resp.status_code in (404,)
        return
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<!doctype html" in resp.text.lower()


def test_health_structured(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["version"] == __version__
    assert "reachable" in body["database"]


def test_health_v1_alias(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_docs_swagger(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()
