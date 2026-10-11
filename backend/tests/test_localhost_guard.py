"""Localhost mutation protection tests (audit Batch 3).

The hole: a page open in any browser on this machine can POST to the
loopback API — the browser will not read the response, but the side effect
happens. The guard refuses any state-changing request whose Origin is not
Sentinel's own.
"""

import pytest

from app.core.config import settings
from tests.test_jobs import _project_id


def _own_origin() -> str:
    return f"http://127.0.0.1:{settings.port}"


@pytest.fixture()
def eager(monkeypatch):
    """Run scheduler jobs synchronously: these tests must not touch the
    pool executor, which the TestClient lifespan shuts down between tests."""
    from app.services.job_scheduler import scheduler

    monkeypatch.setattr(scheduler, "run_inline", True)
    yield
    monkeypatch.setattr(scheduler, "run_inline", False)


def test_foreign_origin_post_is_refused(client, tmp_db):
    """A cross-site POST (another page's form POSTing to the local API) is
    refused before it touches any state."""
    pid = _project_id()
    resp = client.post(
        "/api/v1/tests/run",
        params={"project_id": pid},
        headers={"Origin": "http://evil.example.com"},
    )
    assert resp.status_code == 403
    assert "Cross-origin request refused" in resp.json()["detail"]


def test_foreign_origin_scan_all_is_refused(client, tmp_db):
    """The highest-severity shape from the audit: a bodyless POST with no
    query parameters at all."""
    resp = client.post(
        "/api/v1/security/scan-all",
        headers={"Origin": "http://attacker.test"},
    )
    assert resp.status_code == 403


def test_get_is_never_refused(client, tmp_db):
    """Reads cannot mutate anything, so they must not be gated — including
    when an Origin is present."""
    resp = client.get("/api/v1/projects", headers={"Origin": "http://example.com"})
    assert resp.status_code == 200


def test_own_origin_mutation_is_allowed(client, tmp_db, eager):
    """Sentinel's own dashboard origin keeps working — the whole point: no
    login, no friction, just not-anyone-else. The job is queued (the real
    pool is replaced by inline execution on the global scheduler)."""
    pid = _project_id()
    resp = client.post(
        "/api/v1/tests/run",
        params={"project_id": pid},
        headers={"Origin": _own_origin()},
    )
    assert resp.status_code == 202


def test_no_origin_header_is_allowed(client, tmp_db, eager):
    """curl, the CLI and the desktop shell send no Origin at all and must
    keep working — the guard is about browsers, not about non-browser
    clients."""
    pid = _project_id()
    resp = client.post("/api/v1/tests/run", params={"project_id": pid})
    assert resp.status_code == 202


def test_localhost_origin_alias_is_allowed(client, tmp_db, eager):
    """`localhost` and `127.0.0.1` are distinct origins to a browser; both
    spellings of this server's dashboard must be accepted."""
    pid = _project_id()
    resp = client.post(
        "/api/v1/tests/run",
        params={"project_id": pid},
        headers={"Origin": f"http://localhost:{settings.port}"},
    )
    assert resp.status_code == 202


def test_wrong_port_origin_is_refused(client, tmp_db):
    """Another service on a different port is not Sentinel, even on
    loopback — otherwise a dev server running elsewhere could mutate."""
    pid = _project_id()
    resp = client.post(
        "/api/v1/tests/run",
        params={"project_id": pid},
        headers={"Origin": f"http://127.0.0.1:{settings.port + 1}"},
    )
    assert resp.status_code == 403
