"""Feature-runner tests (docs/clickthrough_plan.md, v1.17.14.0).

Covers: registry resolution, the loopback guard, error mapping
(Playwright timeout -> TesterAssertionError, launch failure ->
TesterEnvError), feature budget enforcement, and per-step screenshot
registration. The Playwright browser is stubbed via a fake page — no real
browser, no real network.
"""

import types
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


class _FakeProc:
    pid = 1234


def _run_features(
    db,
    project,
    features,
    slug="Cg",
    stub_page=None,
    launcher=Path(r"C:\packaged\App.exe"),
    stub_reclaim=None,
    stub_terminate=None,
    stub_verify=None,
):
    """Run a feature list end-to-end against a stubbed page, replicating
    the tester_runner status mapping (the feature runner raises;
    TesterRunner maps). Electron features additionally stub the packaged-
    launch helpers (reclaim / spawn / CDP attach / sandbox verify /
    terminate)."""
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
    if any(f.electron for f in features):
        monkey.setattr(fr_mod, "find_packaged_launcher", lambda path: launcher)
        monkey.setattr(
            fr_mod, "_reclaim_packaged", stub_reclaim or (lambda launcher: None)
        )
        monkey.setattr(
            fr_mod, "_spawn_packaged", lambda launcher, port, sandbox: _FakeProc()
        )
        monkey.setattr(fr_mod, "_connect_cdp", lambda p, port, launcher: stub_page)
        monkey.setattr(
            fr_mod, "_verify_sandbox", stub_verify or (lambda sandbox, launcher: None)
        )
        monkey.setattr(
            fr_mod, "_terminate_packaged", stub_terminate or (lambda proc: None)
        )
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
        "Ag",
        "Algo-Trader",
        "Card-Game",
        "Cg",
        "Demake-Engine",
        "Dinner-Menu-Generator",
        "Tv-Scheduler",
        "Workflow-Toolkit",
    }
    for slug, features in FEATURES.items():
        assert features, slug
        for feature in features:
            assert feature.name
            assert callable(feature.run)
            assert feature.budget_s > 0


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


def test_electron_go_refused(tmp_db):
    """Electron features never navigate: their window is already on the
    packaged app (v1.17.14.4)."""
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service = AppSessionService(db)
        session = service.start(project.id, "Tester: x", "")
        ctx = TesterContext(project, session.id, service)
        fctx = FeatureContext(
            project, session.id, service, ctx, _GenericPage(), electron=True
        )
        with pytest.raises(TesterEnvError, match="electron windows"):
            fctx.go("http://127.0.0.1:5173")


def test_native_go_refused(tmp_db):
    """Native features never navigate: their window is already on the
    app's GUI (v1.17.16.0)."""
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Ag")
        service = AppSessionService(db)
        session = service.start(project.id, "Tester: x", "")
        ctx = TesterContext(project, session.id, service)
        fctx = FeatureContext(
            project, session.id, service, ctx, _GenericPage(), native=True
        )
        with pytest.raises(TesterEnvError, match="native windows"):
            fctx.go("http://127.0.0.1:5173")


def test_window_target_matching():
    """Rule 1 for electron windows: only file:// and loopback targets are
    ever matched by the CDP attach (v1.17.14.4)."""
    from app.services import feature_runner as fr

    assert (
        fr._match_window_target(
            [
                {"type": "page", "url": "file:///C:/x/index.html"},
                {"type": "other", "url": "http://127.0.0.1:9/x"},
            ]
        )
        == "file:///C:/x/index.html"
    )
    assert (
        fr._match_window_target([{"type": "page", "url": "http://127.0.0.1:51234/"}])
        == "http://127.0.0.1:51234/"
    )
    assert (
        fr._match_window_target(
            [
                {"type": "page", "url": "https://evil.example/"},
                {"type": "page", "url": "devtools://devtools/bundled"},
            ]
        )
        is None
    )
    assert fr._match_window_target([]) is None


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


def test_feature_budget_override_maps_to_timeout(tmp_db):
    """A feature's own budget_s replaces the 120 s default (v1.17.14.4)."""

    def _feature(ctx):
        ctx.deadline = 0
        ctx.step("too late")

    feature = Feature("slow2", "blows a short budget", _feature, budget_s=5)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature])
        db.refresh(app_session)
        assert app_session.status.value == "investigate"
        assert "5s budget" in app_session.actual_outcome


# --------------------------------------------------------------- electron


def test_electron_feature_without_launcher_maps_to_investigate(tmp_db):
    feature = Feature(
        "no-launcher",
        "electron feature, no packaged exe",
        lambda ctx: None,
        electron=True,
    )
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(db, project, [feature], launcher=None)
        db.refresh(app_session)
        assert app_session.status.value == "investigate"
        assert "no packaged launcher" in app_session.actual_outcome


def test_electron_feature_runs_against_packaged_window(tmp_db):
    """The electron engine reclaims the presence instance, launches the
    sandboxed packaged app, attaches over CDP and drives the window page —
    then terminates the spawned tree (v1.17.14.4)."""
    reclaimed, terminated = [], []

    def _reclaim(launcher):
        reclaimed.append(launcher)

    def _terminate(proc):
        terminated.append(proc)

    def _feature(ctx):
        ctx.step("window driven")

    feature = Feature(
        "electron-ok", "runs in the packaged window", _feature, electron=True
    )
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(
            db,
            project,
            [feature],
            stub_reclaim=_reclaim,
            stub_terminate=_terminate,
        )
        db.refresh(app_session)
        assert app_session.status.value == "passed"
        assert len(reclaimed) == 1
        assert len(terminated) == 1
        labels = [c.label for c in app_session.checkpoints]
        assert "feature pass: electron-ok" in labels


def test_electron_sandbox_violation_maps_to_investigate(tmp_db):
    """The packaged app ignoring --user-data-dir is a Rule 1 violation —
    TesterEnvError, never a silent pass (v1.17.14.4)."""

    def _violate(sandbox, launcher):
        raise TesterEnvError("Sandbox stayed empty after launch")

    feature = Feature(
        "sandbox", "sandbox must be honored", lambda ctx: None, electron=True
    )
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Cg")
        service, app_session = _run_features(
            db, project, [feature], stub_verify=_violate
        )
        db.refresh(app_session)
        assert app_session.status.value == "investigate"
        assert "Sandbox" in app_session.actual_outcome


def test_reclaim_retries_until_the_image_is_gone(monkeypatch):
    """A single taskkill can miss a mid-startup instance — reclaim re-checks
    via tasklist and keeps killing until the image is gone (live-fix
    2026-08-18)."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "tasklist":
            kills = len([c for c in calls if c[0] == "taskkill"])
            if kills == 0:
                return types.SimpleNamespace(
                    returncode=0, stdout="TV Scheduler.exe 1234 Console"
                )
            return types.SimpleNamespace(returncode=0, stdout="INFO: No tasks")
        return types.SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(fr_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(fr_mod.time, "sleep", lambda s: None)
    fr_mod._reclaim_packaged(Path(r"C:\apps\TV Scheduler.exe"))
    kills = [c for c in calls if c[0] == "taskkill"]
    assert kills, "taskkill must have been issued"
    assert kills[0][2] == "TV Scheduler.exe", "image name must be raw (no quotes)"
    assert len([c for c in calls if c[0] == "tasklist"]) == 2


def test_reclaim_timeout_maps_to_env_error(monkeypatch):
    """An instance that outlives the reclaim window is a TesterEnvError —
    the run fails honestly instead of colliding on the port."""
    now = [0.0]

    def fake_run(cmd, **kw):
        if cmd[0] == "tasklist":
            return types.SimpleNamespace(
                returncode=0, stdout="TV Scheduler.exe 1234 Console"
            )
        return types.SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(fr_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(fr_mod.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(fr_mod.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    with pytest.raises(TesterEnvError, match="reclaim"):
        fr_mod._reclaim_packaged(Path(r"C:\apps\TV Scheduler.exe"))


def test_sandbox_removal_retries_until_gone(tmp_path, monkeypatch):
    """The killed Chromium processes release their leveldb locks a beat
    after taskkill — the sandbox removal retries within a bounded window
    (live-fix 2026-08-18) and only warns if it still lingers."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "LOCK").write_text("x")

    attempts = []
    real_rmtree = fr_mod.shutil.rmtree

    def fake_rmtree(path, **kw):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("locked")
        real_rmtree(path)

    monkeypatch.setattr(fr_mod.shutil, "rmtree", fake_rmtree)
    monkeypatch.setattr(fr_mod.time, "sleep", lambda s: None)
    fr_mod._remove_sandbox(sandbox)
    assert not sandbox.exists()
    assert len(attempts) == 2


def test_sandbox_removal_warns_when_locked_out(tmp_path, monkeypatch):
    """A sandbox that outlives the retry window is logged, never raised —
    the feature outcome already happened; the leftover is temp junk."""
    sandbox = tmp_path / "stubborn"
    sandbox.mkdir()
    monkeypatch.setattr(fr_mod.shutil, "rmtree", lambda path, **kw: None)
    monkeypatch.setattr(fr_mod.time, "sleep", lambda s: None)
    warnings = []
    monkeypatch.setattr(
        fr_mod.logger, "warning", lambda msg, *a: warnings.append(str(msg))
    )
    fr_mod._remove_sandbox(sandbox)
    assert sandbox.exists()
    assert warnings and "Sandbox cleanup failed" in warnings[0]


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
    """Drive every shipped WEB feature against a generic fake page —
    proves the scripts exercise a real (stubbed) Playwright API surface
    without a browser, and keeps their run() bodies covered. Native
    features are excluded: they construct a DesktopApp engine (their own
    window contract) and are covered by the fake-desktop tests above."""
    for slug, features in FEATURES.items():
        web = [f for f in features if not f.native]
        if not web:
            continue
        with DbSession(get_engine()) as db:
            project = _mk_project(db, slug)
            if slug == "Demake-Engine":
                fixture_dir = Path(project.path) / "backend"
                fixture_dir.mkdir(parents=True, exist_ok=True)
                (fixture_dir / "test_game_trailer.mp4").write_bytes(b"fixture")
            if slug == "Workflow-Toolkit":
                fixture = (
                    Path(project.path)
                    / "backend"
                    / "tests"
                    / "fixtures"
                    / "payroll_issues.csv"
                )
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_text("name,hours\n", encoding="utf-8")
            service, app_session = _run_features(
                db, project, web, slug=slug, stub_page=_GenericPage()
            )
            db.refresh(app_session)
            assert app_session.status.value == "passed", (
                slug,
                app_session.actual_outcome,
            )
            labels = [c.label for c in app_session.checkpoints]
            assert f"feature pass: {web[0].name}" in labels


# --------------------------------------------------------------- native


def test_native_feature_runs_against_fake_desktop(tmp_db, monkeypatch):
    """The native engine (v1.17.16.0) runs features with a pywinauto
    DesktopApp against the app's window; the feature constructs its own
    engine (it owns the window-title contract) and assigns ctx.desktop
    before any ctx.shot()."""
    from app.testers.features import ag as ag_features

    calls = []

    class _FakeEl:
        def __init__(self, name):
            self.name = name

        def wait(self, timeout):
            calls.append(f"wait:{self.name}")

        def wait_gone(self, timeout):
            calls.append("wait_gone")

    class _FakeDialog:
        def __init__(self):
            self._el = _FakeDialogElement()

        def wait_gone(self, timeout):
            calls.append("wait_gone")

        def focus(self):
            calls.append("focus")

    class _FakeDialogElement:
        def child_window(self, title):
            return _FakeEl(title)

    class _FakeDesktopApp:
        def __init__(self, title_pattern, budget_s=120):
            self.title_pattern = title_pattern
            self.budget_s = budget_s
            self.window = object()
            self._path_typed = False

        def connect(self):
            calls.append("connect")

        def bring_to_front(self):
            calls.append("bring_to_front")

        def assert_pixel(self, x, y, rgb, tolerance=6):
            calls.append("assert_pixel")

        def click(self, x, y):
            calls.append(f"click:{x},{y}")

        def press_alt(self, letter):
            calls.append(f"press_alt:{letter}")

        def type_text(self, text):
            calls.append(f"type_text:{text}")
            self._path_typed = True

        def press_enter(self):
            calls.append("press_enter")

        def dialog(self, title_pattern):
            calls.append("dialog")
            return _FakeDialog()

        def element(self, title, parent):
            return _FakeEl(title)

        def capture(self):
            im = Image.new("RGB", (720, 680))
            pixels = im.load()
            for yy in range(680):
                for xx in range(720):
                    pixels[xx, yy] = (xx % 256, (xx + yy) % 256, 80)
            return im

        def content_pixels(self, box, bg):
            calls.append("content_pixels")
            return 1600 if self._path_typed else 0

        def wait_region_change(self, before, box, min_changed, timeout, step=4):
            calls.append("wait_region_change")

        def shot(self, path):
            im = Image.new("RGB", (720, 680))
            pixels = im.load()
            for yy in range(680):
                for xx in range(720):
                    pixels[xx, yy] = (xx % 256, (xx + yy) % 256, 80)
            im.save(path)

    monkeypatch.setattr(ag_features, "DesktopApp", _FakeDesktopApp)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Ag")
        pose = Path(project.path) / "poses" / "images" / "front_tpose.png"
        pose.parent.mkdir(parents=True, exist_ok=True)
        pose.write_bytes(b"fixture")
        service, app_session = _run_features(
            db, project, ag_features.FEATURES, slug="Ag"
        )
        db.refresh(app_session)
        assert app_session.status.value == "passed", app_session.actual_outcome
        assert "connect" in calls
        assert "bring_to_front" in calls
        assert any(c == "click:642,90" for c in calls)
        assert any(c == "click:360,469" for c in calls)
        assert any(c.startswith("press_alt:") for c in calls)
        assert any(c.startswith("type_text:") for c in calls)
        assert "press_enter" in calls
        assert "focus" in calls
        assert "wait_gone" in calls
        assert "content_pixels" in calls
        assert "wait_region_change" in calls
        labels = [c.label for c in app_session.checkpoints]
        assert "feature pass: AG GUI generation start" in labels


def test_native_feature_busy_desktop_maps_to_investigate(tmp_db, monkeypatch):
    """A desktop that withholds foreground rights is an honest, retryable
    env error — never a silent pass (v1.17.16.0)."""
    from app.testers.features import ag as ag_features

    class _BusyDesktopApp:
        def __init__(self, title_pattern, budget_s=120):
            pass

        def connect(self):
            raise TesterEnvError("could not be brought to the foreground")

    monkeypatch.setattr(ag_features, "DesktopApp", _BusyDesktopApp)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, "Ag")
        service, app_session = _run_features(
            db, project, ag_features.FEATURES, slug="Ag"
        )
        db.refresh(app_session)
        assert app_session.status.value == "investigate"
        assert "foreground" in app_session.actual_outcome


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

    def locator(self, selector, has_text=None, has=None):
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

    def wait_for_function(self, expr, timeout=30000):
        return None

    def evaluate(self, expr, arg=None):
        return True

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

    def locator(self, selector, has_text=None, has=None):
        return _GenericLocator(self.page)

    def click(self, **kw):
        return None

    def fill(self, value, **kw):
        return None

    def wait_for(self, state="visible", timeout=30000):
        return None

    def inner_text(self):
        return self.page._next_text()

    def all_inner_texts(self):
        return []

    def evaluate(self, expr, arg=None):
        return True

    def get_attribute(self, name):
        return "dark"

    def count(self):
        return 2

    def select_option(self, index=None, label=None, value=None):
        return None

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
