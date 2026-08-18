"""Feature-runner tests (docs/clickthrough_plan.md, v1.17.14.0).

Covers: registry resolution, the loopback guard, error mapping
(Playwright timeout -> TesterAssertionError, launch failure ->
TesterEnvError), feature budget enforcement, and per-step screenshot
registration. The Playwright browser is stubbed via a fake page — no real
browser, no real network.
"""

from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from sqlmodel import Session as DbSession

from app.core.config import settings
from app.db import connection
from app.db.connection import get_engine
from app.db.models import Project
from app.services import feature_runner as fr_mod
from app.services.app_sessions import AppSessionService
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)
from app.testers.features import FEATURES, Feature, FeatureContext


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


def _mk_project(db, name, startup="npm start") -> Project:
    project = Project(
        name=name,
        path=f"C:\\projects\\{name}",
        repo_url="",
        language="python",
        stack={"language": "python", "commands": {"startup": startup}},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _run_features(db, project, features, slug="Cg", stub_page=None):
    """Run a feature list end-to-end against a stubbed page, replicating
    the tester_runner status mapping (the feature runner raises;
    TesterRunner maps)."""
    service = AppSessionService(db)
    app_session = service.start(project.id, "Tester: x", "")
    ctx = TesterContext(project, app_session.id, service)

    if stub_page is None:
        stub_page = _StubPage(features)
    stub_page.features = features

    def _fake_playwright():
        class _Playwright:
            def __exit__(self, *a):
                return None

            def __enter__(self):
                return self

        _Playwright.chromium = type(
            "chromium", (), {"launch": lambda self, **kw: stub_page.launched}
        )()
        return _Playwright()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(fr_mod, "sync_playwright", _fake_playwright)
    monkey.setattr(fr_mod, "_headed", lambda: False)
    monkey.setitem(fr_mod.FEATURES, slug, features)
    try:
        try:
            fr_mod.FeatureRunner(db).run(project, ctx, service, app_session.id)
            service.end(app_session.id, "ok", "passed")
        except TesterAssertionError as exc:
            service.end(app_session.id, str(exc), "failed")
        except (TesterEnvError, TesterTimeoutError) as exc:
            service.end(app_session.id, str(exc), "investigate")
    finally:
        monkey.undo()
    return service, app_session


# ------------------------------------------------------------------ registry


def test_registry_has_expected_slugs():
    assert set(FEATURES) == {
        "Card-Game",
        "Cg",
        "Demake-Engine",
        "Dinner-Menu-Generator",
        "Tv-Scheduler",
    }
    for slug, features in FEATURES.items():
        assert features, slug
        for feature in features:
            assert feature.name
            assert callable(feature.run)


def test_resolve_no_features_for_unknown_project(tmp_db):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Some App")
        runner = fr_mod.FeatureRunner(db)
        assert runner.resolve(project) == []
        assert runner.describe(project) == []


# ------------------------------------------------------------------- guard


def test_loopback_guard_refuses_remote_host(tmp_db):
    from app.testers.features._context import LOOPBACK_HOSTS

    assert "127.0.0.1" in LOOPBACK_HOSTS
    assert "localhost" in LOOPBACK_HOSTS

    class FakePage:
        def goto(self, url, **kw):
            raise AssertionError(f"goto must never run for remote urls: {url}")

    from sqlmodel import Session as _DbSession

    with _DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service = AppSessionService(db)
        session = service.start(project.id, "Tester: x", "")
        ctx = TesterContext(project, session.id, service)
        fctx = FeatureContext(project, session.id, service, ctx, FakePage())
        with pytest.raises(TesterEnvError, match="not loopback"):
            fctx.go("https://example.com")
        with pytest.raises(TesterEnvError, match="not loopback"):
            fctx.go("http://192.168.1.10:8000")


# ------------------------------------------------------------- error mapping


def test_playwright_timeout_maps_to_assertion(tmp_db):
    def _feature(ctx):
        raise PlaywrightTimeoutError("expect(locator).to_be_visible timed out")

    feature = Feature("boom", "raises a playwright timeout", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "failed"
        assert "boom" in app_session.actual_outcome
        assert "timed out" in app_session.actual_outcome


def test_playwright_error_maps_to_assertion(tmp_db):
    def _feature(ctx):
        raise PlaywrightError("page is closed")

    feature = Feature("boom2", "raises a playwright error", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "failed"
        assert "boom2" in app_session.actual_outcome


def test_budget_exhaustion_maps_to_timeout(tmp_db, monkeypatch):
    def _feature(ctx):
        ctx.deadline = 0
        ctx.step("too late")

    feature = Feature("slow", "blows the budget", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "investigate"
        assert "budget" in app_session.actual_outcome


def test_assertion_error_passes_through(tmp_db):
    def _feature(ctx):
        raise TesterAssertionError("expected value did not match")

    feature = Feature("assert", "raises a tester assertion", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "failed"
        assert "did not match" in app_session.actual_outcome


# ------------------------------------------------------ screenshot recording


def test_shot_registers_a_screenshot(tmp_db):
    def _feature(ctx):
        ctx.step("stepped")
        ctx.shot("feature screenshot")

    feature = Feature("shot", "takes a screenshot", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "passed"
        shots = service.screenshot_repo.by_session(app_session.id)
        assert len(shots) == 1
        shot = shots[0]
        assert shot.path.endswith(".png")
        assert (
            Path(settings.db_path).parent.parent / "screenshots" / "Cg" / shot.path
        ).exists()


def test_blank_shot_raises_assertion(tmp_db):
    def _feature(ctx):
        ctx.shot("blank frame")

    feature = Feature("blank", "captures a blank frame", _feature)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(
            db, project, [feature], stub_page=_StubPage([feature], blank=True)
        )
        db.refresh(app_session)
        assert app_session.status.value == "failed"
        assert "blank" in app_session.actual_outcome


# -------------------------------------------------------------- all features


def test_all_registered_features_pass_against_fake_page(tmp_db):
    """Drive every shipped feature against a generic fake page — proves the
    scripts exercise a real (stubbed) Playwright API surface without a
    browser, and keeps their run() bodies covered."""
    for slug, features in FEATURES.items():
        with DbSession(get_engine()) as db:
            project = _mk_project(db, slug)
            if slug == "Demake-Engine":
                fixture_dir = Path(project.path) / "backend"
                fixture_dir.mkdir(parents=True, exist_ok=True)
                (fixture_dir / "test_game_trailer.mp4").write_bytes(b"fixture")
            service, app_session = _run_features(
                db, project, features, slug=slug, stub_page=_GenericPage()
            )
            db.refresh(app_session)
            assert app_session.status.value == "passed", (
                slug,
                app_session.actual_outcome,
            )
            labels = [c.label for c in app_session.checkpoints]
            assert f"feature pass: {features[0].name}" in labels


# -------------------------------------------------------------- stubs


class _GenericPage:
    """A feature-API-surface fake: every locator factory returns a no-op
    locator; inner_text() yields an increasing number so balance-change
    style assertions differ; dialog handlers fire immediately (the
    card-game register alert)."""

    def __init__(self):
        self._calls = 0
        self.launched = _StubBrowser(self)
        self._file_chosen = False

    def _next_text(self):
        self._calls += 1
        return f"{1000 - self._calls}"

    def get_by_role(self, role="", name="", exact=False):
        return _GenericLocator(self)

    def get_by_placeholder(self, placeholder):
        return _GenericLocator(self)

    def get_by_text(self, text, exact=False):
        return _GenericLocator(self)

    def locator(self, selector, has_text=None):
        return _GenericLocator(self)

    def set_input_files(self, selector, files):
        self._file_chosen = True
        return None

    def goto(self, url, wait_until="load"):
        return None

    def set_default_timeout(self, ms):
        return None

    def wait_for_timeout(self, ms):
        return None

    def on(self, event, handler):
        if event == "dialog":
            handler(_FakeDialog())

    def screenshot(self, path):
        im = Image.new("RGB", (320, 200))
        pixels = im.load()
        for x in range(320):
            for y in range(200):
                pixels[x, y] = (x % 256, (x + y) % 256, 80)
        im.save(path)


class _FakeDialog:
    def dismiss(self):
        return None


class _GenericLocator:
    def __init__(self, page):
        self.page = page
        self.first = self

    def get_by_role(self, role="", name="", exact=False):
        return _GenericLocator(self.page)

    def get_by_text(self, text, exact=False):
        return _GenericLocator(self.page)

    def click(self, **kw):
        return None

    def fill(self, value, **kw):
        return None

    def wait_for(self, state="visible", timeout=30000):
        return None

    def inner_text(self):
        return self.page._next_text()

    def count(self):
        return 0

    def is_enabled(self):
        return self.page._file_chosen


class _StubPage:
    """A fake Playwright page: records calls, screenshots a varied frame
    (many gray levels — never trips the blank check), and executes the
    features handed to the runner via a monkeypatched registry slice."""

    def __init__(self, features, blank=False):
        self.features = features
        self.launched = _StubBrowser(self)
        self.screenshots = []
        self.blank = blank
        self._owner = None

    def _set_owner(self, monkey):
        self._owner = monkey
        monkey.setitem(fr_mod.FEATURES, "Cg", self.features)

    def set_default_timeout(self, ms):
        self.default_timeout = ms

    def goto(self, url, **kw):
        self.urls = getattr(self, "urls", []) + [url]

    def screenshot(self, path):
        if self.blank:
            Image.new("RGB", (320, 200), (0, 0, 0)).save(path)
        else:
            im = Image.new("RGB", (320, 200))
            pixels = im.load()
            for x in range(320):
                for y in range(200):
                    pixels[x, y] = (x % 256, (x + y) % 256, 80)
            im.save(path)
        self.screenshots.append(path)

    def wait_for_timeout(self, ms):
        return None

    def close(self):
        return None


class _StubBrowser:
    """Fake Playwright Browser: returns the stub page from new_page()."""

    def __init__(self, page):
        self.page = page

    def new_page(self, **kw):
        return self.page

    def close(self):
        return None
