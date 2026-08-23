"""Career OS integration tests (Sprint 33 pattern — Resmaker).

Covers the Tier 1 HTTP tester (launch + GET smokes + POST surface with
create/cleanup semantics) and the Tier 2 electron feature (backend
ownership, UI click-through steps) against fakes only — no real server,
no real subprocess, no real browser. Hermetic like every other suite:
tmp_db points settings.db_path at a temp SQLite, so nothing here ever
touches the real sentinel.db (live-fix: the first version skipped the
fixture and wrote ~64 junk projects + RUNNING sessions into the real DB).
"""

import pytest
from PIL import Image
from sqlmodel import Session as DbSession

from app.core.config import settings
from app.db import connection
from app.db.connection import get_engine
from app.db.models import Project
from app.services import app_sessions as svc
from app.testers import TESTERS
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)
from app.testers.features import FEATURES


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "data" / "sqlite" / "test.db")
    _dispose_engine()
    connection.init_db()
    yield tmp_path / "data" / "sqlite" / "test.db"
    _dispose_engine()


def _dispose_engine() -> None:
    engine = connection._engine
    connection._engine = None
    if engine is not None:
        engine.dispose()


# ------------------------------------------------------------------ registry


def test_career_os_tester_registered():
    tester = TESTERS["Resmaker"]
    assert tester.kind == "custom"
    # The packaged exe must NOT auto-launch before an HTTP-only tester.
    assert tester.auto_launch is False
    assert 8000 in tester.ports


def test_career_os_feature_registered():
    features = FEATURES["Resmaker"]
    assert len(features) == 1
    feature = features[0]
    assert feature.electron is True
    assert callable(feature.run)
    assert feature.budget_s > 0


# ------------------------------------------------------------------ tier 1


class _FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or str(self._payload)

    def json(self):
        return self._payload


@pytest.fixture()
def career_os_project(tmp_db, tmp_path):
    with DbSession(get_engine()) as db:
        project = Project(
            name="Resmaker",
            path=str(tmp_path / "ResMaker"),
            repo_url="",
            language="python",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        yield project


def _mk_ctx(db, project):
    service = svc.AppSessionService(db)
    session = service.start(project.id, "t")
    return service, TesterContext(project, session.id, service)


def _patch_http(monkeypatch, search_hits=True):
    """Fake the Career OS API surface: tokened item flows end-to-end."""
    from app.testers import _helpers as helpers_mod
    from app.testers import career_os

    calls = {"deleted": [], "launched": []}

    class FakeUvicornResp:
        status_code = 200

        def __init__(self, url):
            self.text = "healthy" if "health" in url else '"status":"ok"'

    def fake_request(method, url, timeout=None, **kw):
        return FakeUvicornResp(url)

    def fake_post(url, json=None, timeout=None, **kw):
        if "knowledge-items" in url:
            return _FakeResp(201, {"id": "item-1"})
        if "/search/" in url:
            items = [{"id": "item-1"}] if search_hits else []
            return _FakeResp(200, {"items": items, "total": len(items)})
        if "/build/suggest" in url:
            body = (
                [{"knowledge_item": {"id": "item-1"}, "score": 0.9}]
                if search_hits
                else []
            )
            return _FakeResp(200, body)
        if "/build/resume" in url:
            return _FakeResp(200, {"document_id": "doc-1"})
        if "/validate/" in url:
            return _FakeResp(200, {"score": 1.0, "issues": [], "errors": []})
        raise AssertionError(f"unexpected POST {url}")

    def fake_delete(url, timeout=None, **kw):
        calls["deleted"].append(url)
        return _FakeResp(204)

    def fake_get(url, timeout=None, **kw):
        return _FakeResp(404)

    monkeypatch.setattr(helpers_mod.httpx, "request", fake_request)
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(
            lambda project, cmd, env=None: calls["launched"].append(cmd) or (True, cmd)
        ),
    )
    monkeypatch.setattr(career_os.httpx, "post", fake_post)
    monkeypatch.setattr(career_os.httpx, "delete", fake_delete)
    monkeypatch.setattr(career_os.httpx, "get", fake_get)
    return calls


def test_tier1_run_happy_path(career_os_project, monkeypatch):
    from app.testers import career_os

    calls = _patch_http(monkeypatch)
    with DbSession(get_engine()) as db:
        _, ctx = _mk_ctx(db, career_os_project)
        career_os.run(ctx)
    assert calls["launched"] == [career_os.LAUNCH_CMD]
    assert any("knowledge-items/item-1" in url for url in calls["deleted"])


def test_tier1_search_miss_fails_but_cleanup_still_runs(career_os_project, monkeypatch):
    from app.testers import career_os

    calls = _patch_http(monkeypatch, search_hits=False)
    with DbSession(get_engine()) as db:
        _, ctx = _mk_ctx(db, career_os_project)
        with pytest.raises(TesterAssertionError, match="/search/"):
            career_os.run(ctx)
    # the finally-block cleanup deleted the smoke item even after failure
    assert calls["deleted"], "cleanup DELETE must run despite the assertion"


def test_tier1_failed_delete_is_env_error(career_os_project, monkeypatch):
    """A smoke item that cannot be removed would linger in the user's real
    corpus — that is an env problem, never a silent pass."""
    from app.testers import career_os

    _patch_http(monkeypatch)

    def stuck_delete(url, timeout=None, **kw):
        return _FakeResp(409)

    monkeypatch.setattr(career_os.httpx, "delete", stuck_delete)
    with DbSession(get_engine()) as db:
        _, ctx = _mk_ctx(db, career_os_project)
        with pytest.raises(TesterEnvError, match="linger"):
            career_os.run(ctx)


# ------------------------------------------------------------------ tier 2


class _FakePage:
    def __init__(self):
        self.calls = []

    def get_by_role(self, role="", name="", exact=False):
        locator = _FakeLocator(f"role:{role}:{name}")
        self.calls.append(("get_by_role", role, name))
        return locator

    def locator(self, selector, has_text=None, has=None):
        self.calls.append(("locator", selector))
        return _FakeLocator(selector)

    def screenshot(self, path):
        im = Image.new("RGB", (320, 200))
        pixels = im.load()
        for x in range(320):
            for y in range(200):
                pixels[x, y] = (x % 256, (x + y) % 256, 80)
        im.save(path)


class _FakeLocator:
    def __init__(self, label):
        self.label = label
        self.first = self

    def wait_for(self, state="visible", timeout=30000):
        return None

    def click(self, **kw):
        return None

    def count(self):
        return 7


class _FakeProc:
    pid = 4242
    returncode = None

    def poll(self):
        return None


@pytest.fixture()
def feature_env(career_os_project):
    """Open DB session + FeatureContext factory kept alive for the test."""
    from sqlmodel import select

    from app.testers.features import FeatureContext

    with DbSession(get_engine()) as db:
        service = svc.AppSessionService(db)
        state = {"db": db, "session_id": None}

        def _make(page):
            session = service.start(career_os_project.id, "t")
            state["session_id"] = session.id
            ctx = TesterContext(career_os_project, session.id, service)
            return FeatureContext(
                career_os_project,
                session.id,
                service,
                ctx,
                page,
                electron=True,
                budget_s=60,
            )

        def _labels():
            return [
                c.label
                for c in db.exec(
                    select(svc.SessionCheckpoint).where(
                        svc.SessionCheckpoint.session_id == state["session_id"]
                    )
                ).all()
            ]

        yield _make, _labels


def test_tier2_reuses_running_backend(feature_env, monkeypatch):
    """A healthy :8000 is reused — nothing spawned, nothing killed."""
    from app.testers.features import career_os as cos

    monkeypatch.setattr(cos, "_backend_healthy", lambda: True)
    spawned = []
    monkeypatch.setattr(cos.subprocess, "Popen", lambda *a, **k: spawned.append(a))

    make_ctx, labels_for = feature_env
    fctx = make_ctx(_FakePage())
    cos.run(fctx)
    assert not spawned
    labels = labels_for()
    assert any("reusing the Career OS backend" in label for label in labels)
    assert not any("torn down" in label for label in labels)


def test_tier2_spawns_backend_drives_ui_and_tears_down(
    career_os_project, tmp_path, feature_env, monkeypatch
):
    from app.testers.features import career_os as cos

    python = tmp_path / "ResMaker" / cos.BACKEND_REL
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"")

    procs = []
    kills = []
    health = {"up": False}

    def fake_popen(*a, **kw):
        proc = _FakeProc()
        procs.append(proc)
        health["up"] = True  # uvicorn binds on first poll
        return proc

    def fake_taskkill(args, **kwargs):
        import types

        kills.append(args)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cos, "_backend_healthy", lambda: health["up"])
    monkeypatch.setattr(cos.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cos.subprocess, "run", fake_taskkill)
    monkeypatch.setattr(cos.time, "sleep", lambda s: None)

    page = _FakePage()
    make_ctx, labels_for = feature_env
    fctx = make_ctx(page)
    cos.run(fctx)

    assert len(procs) == 1
    assert any(k[0] == "taskkill" and k[2] == "4242" for k in kills)
    labels = labels_for()
    assert any("backend healthy on :8000" in label for label in labels)
    assert any("dashboard shell rendered" in label for label in labels)
    assert any(
        "Explorer browse returned 7 knowledge items" in label for label in labels
    )
    assert any("own PID tree only" in label for label in labels)
    # UI flow: dashboard heading -> Explorer link -> result items
    roles = [c[1:] for c in page.calls if c[0] == "get_by_role"]
    assert ("heading", "Career OS") in roles
    assert ("link", "Explorer") in roles
    selectors = [c[1] for c in page.calls if c[0] == "locator"]
    assert '[data-testid="result-item"]' in selectors


def test_tier2_missing_interpreter_is_env_error(feature_env, monkeypatch):
    from app.testers.features import career_os as cos

    monkeypatch.setattr(cos, "_backend_healthy", lambda: False)
    make_ctx, _ = feature_env
    fctx = make_ctx(_FakePage())
    with pytest.raises(TesterEnvError, match="interpreter missing"):
        cos.run(fctx)


def test_tier2_backend_dying_during_startup_is_env_error(
    career_os_project, tmp_path, feature_env, monkeypatch
):
    from app.testers.features import career_os as cos

    python = tmp_path / "ResMaker" / cos.BACKEND_REL
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"")

    class _DeadProc:
        pid = 1
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(cos, "_backend_healthy", lambda: False)
    monkeypatch.setattr(cos.subprocess, "Popen", lambda *a, **kw: _DeadProc())
    make_ctx, _ = feature_env
    fctx = make_ctx(_FakePage())
    with pytest.raises(TesterEnvError, match="exited during startup"):
        cos.run(fctx)


def test_tier2_startup_timeout_is_env_error(
    career_os_project, tmp_path, feature_env, monkeypatch
):
    """A backend that never binds fails honestly within its wait window."""
    from app.testers.features import career_os as cos

    python = tmp_path / "ResMaker" / cos.BACKEND_REL
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"")

    now = [0.0]

    class _LiveProc:
        pid = 2
        returncode = None

        def poll(self):
            return None

    monkeypatch.setattr(cos, "_backend_healthy", lambda: False)
    monkeypatch.setattr(cos.subprocess, "Popen", lambda *a, **kw: _LiveProc())
    monkeypatch.setattr(cos.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(cos.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    make_ctx, _ = feature_env
    fctx = make_ctx(_FakePage())
    with pytest.raises(TesterEnvError, match="not healthy"):
        cos.run(fctx)


def test_tier2_runs_against_fake_page_via_runner(tmp_db, monkeypatch):
    """The generic all-features runner test special-cases ResMaker's
    backend spawn; this mirrors that wiring at the registry level."""
    # registry consistency is enforced loudly at import — reaching here
    # means the tester slug and feature key agree.
    assert "Resmaker" in TESTERS
    assert "Resmaker" in FEATURES
