"""Session recorder tests (later.md Tier 1 + Tier 4)."""

import ctypes
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.core.config import settings
from app.db import connection
from app.db.connection import get_engine
from app.db.models import AppSession, Project, SessionScreenshot, SessionStatus
from app.services import app_sessions as svc
from app.services.app_sessions import AppSessionService
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)
from app.utils import window_capture
from app.utils.headless_render import HeadlessRenderError


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Shadows conftest's tmp_db: db sits under <tmp>/data/sqlite so the
    log/screenshot paths (derived as db_path.parent.parent) stay inside this
    test's tmp dir instead of the shared pytest session dir."""
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


def _mk_project(db, name="demo-app", path=None) -> Project:
    project = Project(
        name=name,
        path=path or f"C:\\projects\\{name}",
        repo_url="",
        language="python",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture(autouse=True)
def _fake_grabber(monkeypatch):
    """Deterministic grab: a solid-color image; records bbox args."""
    image = Image.new("RGB", (320, 200), (10, 20, 30))
    calls = []

    class Grabber:
        @staticmethod
        def grab(bbox=None):
            calls.append(bbox)
            return image.copy()

    monkeypatch.setattr(svc, "ImageGrab", Grabber)
    monkeypatch.setattr(svc, "find_project_window", lambda path: None)
    return calls


@pytest.fixture()
def project(tmp_db):
    with DbSession(get_engine()) as db:
        return _mk_project(db)


def _log_path(project_name: str) -> Path:
    return (
        Path(settings.db_path).parent.parent
        / "logs"
        / "apps"
        / f"{svc._slug(project_name)}.log"
    )


def _session(db, project_id, title="Test session"):
    service = AppSessionService(db)
    return service.start(project_id, title)


def _mock_window(monkeypatch):
    """Window owned by the app under test: PrintWindow renders a solid frame."""
    monkeypatch.setattr(
        svc, "find_project_window", lambda path: (12345, (10, 20, 210, 120))
    )
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    monkeypatch.setattr(
        svc,
        "capture_window_content",
        lambda hwnd, rect: Image.new("RGB", (200, 100), (9, 8, 7)),
    )


# ------------------------------------------------------------------ lifecycle


def test_start_writes_marker_with_session_id(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        lines = _log_path(project.name).read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("[sentinel] Session started ")
    assert f"{app_session.id}: Test session" in lines[0]


def test_start_unknown_project_raises(tmp_db):
    with DbSession(get_engine()) as db, pytest.raises(ValueError):
        AppSessionService(db).start("nope", "x")


def test_checkpoint_appends_marker(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        checkpoint = AppSessionService(db).checkpoint(app_session.id, "menu loaded")
        assert checkpoint.label == "menu loaded"
        lines = _log_path(project.name).read_text(encoding="utf-8").splitlines()
    assert f"{app_session.id}: menu loaded" in lines[1]


def test_end_slices_between_own_markers(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        service.checkpoint(app_session.id, "step one")
        service.end(app_session.id, "worked", "passed")
        db.refresh(app_session)
        assert app_session.status == SessionStatus.PASSED
        assert app_session.ended_at is not None
        slice_lines = (app_session.log_slice or "").splitlines()
    assert f"{app_session.id}: Test session" in slice_lines[0]
    assert f"{app_session.id}: step one" in slice_lines[1]
    assert slice_lines[-1].endswith(": passed")


def test_end_of_interleaved_sessions_is_deterministic(tmp_db, project):
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        a = service.start(project.id, "Session A")
        service.start(project.id, "Session B")
        service.checkpoint(a.id, "a-one")
        service.end(a.id, "a done", "passed")
        db.refresh(a)
        slice_a = (a.log_slice or "").splitlines()
    assert f"{a.id}: Session A" in slice_a[0]
    assert f"{a.id}: passed" in slice_a[-1]
    assert any("Session B" in line for line in slice_a)


def test_unfinished_session_slices_to_eof(tmp_db, project):
    with DbSession(get_engine()) as db:
        a = _session(db, project.id)
        service = AppSessionService(db)
        service.checkpoint(a.id, "mid-flight")
        sliced = service._slice_for(project, a.id)
    lines = sliced.splitlines()
    assert f"{a.id}: Test session" in lines[0]
    assert f"{a.id}: mid-flight" in lines[-1]


# ---------------------------------------------------------------- screenshots


def test_capture_saves_png_and_thumbnail(tmp_db, project, monkeypatch):
    _mock_window(monkeypatch)
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        shot = AppSessionService(db).capture(app_session.id)
        shot_dir = (
            Path(settings.db_path).parent.parent
            / "screenshots"
            / svc._slug(project.name)
        )
        full = shot_dir / shot.path
        thumb = shot_dir / f"{Path(shot.path).stem}.thumb.png"
        assert full.exists()
        assert thumb.exists()
        with Image.open(thumb) as img:
            assert img.size[0] <= svc.THUMB_SIZE[0]
            assert img.size[1] <= svc.THUMB_SIZE[1]


def test_register_screenshot_copies_png_and_thumbnail(tmp_db, project, tmp_path):
    """v1.17.13.1: a pre-rendered PNG (headless browser render) registers as a
    session screenshot — PNG + thumb copied into the slug dir, row created."""
    source = tmp_path / "render.png"
    Image.new("RGB", (200, 100), (9, 8, 7)).save(source, "PNG")
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        shot = AppSessionService(db).register_screenshot(app_session.id, source)
        shot_dir = (
            Path(settings.db_path).parent.parent
            / "screenshots"
            / svc._slug(project.name)
        )
        full = shot_dir / shot.path
        thumb = shot_dir / f"{Path(shot.path).stem}.thumb.png"
        assert full.exists()
        assert thumb.exists()
        with Image.open(full) as img:
            assert img.size == (200, 100)
        with Image.open(thumb) as img:
            assert img.size[0] <= svc.THUMB_SIZE[0]
            assert img.size[1] <= svc.THUMB_SIZE[1]


def test_register_screenshot_missing_source_raises(tmp_db, project, tmp_path):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        with pytest.raises(FileNotFoundError):
            AppSessionService(db).register_screenshot(
                app_session.id, tmp_path / "missing.png"
            )


def test_ctx_screenshot_file_registers_render(tmp_db, project, tmp_path):
    """TesterContext.screenshot_file mirrors screenshot(): a checkpoint plus a
    registered headless-render shot."""
    source = tmp_path / "render.png"
    Image.new("RGB", (320, 200), (5, 5, 5)).save(source, "PNG")
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        ctx = TesterContext(project, app_session.id, service)
        ctx.screenshot_file(str(source), "headless game render")
        checkpoints = service.checkpoint_repo.by_session(app_session.id)
        shots = service.screenshot_repo.by_session(app_session.id)
        assert [c.label for c in checkpoints] == ["headless game render"]
        assert len(shots) == 1


def _render_png_fake(url, out_path):
    img = Image.new("RGB", (320, 200), (9, 8, 7))
    for x in range(0, 320, 4):
        for y in range(0, 200, 4):
            img.putpixel((x, y), (x % 256, y % 256, 128))
    img.save(out_path, "PNG")


def test_ctx_render_and_register_renders_and_registers(tmp_db, project, monkeypatch):
    """v1.17.13.2: TesterContext.render_and_register drives a headless render
    of a URL, registers the frame as a session screenshot, and cleans up the
    temp file — the capture path for browser-served apps."""
    import app.testers._helpers as helpers

    seen = {}

    def fake_render(url, out_path):
        seen["url"] = url
        seen["out"] = out_path
        _render_png_fake(url, out_path)

    monkeypatch.setattr(helpers, "render_url", fake_render)
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        ctx = TesterContext(project, app_session.id, service)
        ctx.render_and_register("http://127.0.0.1:1/", "headless dashboard render")
        checkpoints = service.checkpoint_repo.by_session(app_session.id)
        shots = service.screenshot_repo.by_session(app_session.id)
        assert seen["url"] == "http://127.0.0.1:1/"
        assert [c.label for c in checkpoints] == ["headless dashboard render"]
        assert len(shots) == 1
        assert not Path(seen["out"]).exists()


def test_ctx_render_and_register_blank_raises(tmp_db, project, monkeypatch):
    """A blank frame (WebGL failing under SwiftShader, e.g.) is a deterministic
    TesterAssertionError — nothing registered."""
    import app.testers._helpers as helpers

    monkeypatch.setattr(
        helpers,
        "render_url",
        lambda url, out_path: Image.new("RGB", (320, 200), (0, 0, 0)).save(
            out_path, "PNG"
        ),
    )
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterAssertionError, match="blank"):
            ctx.render_and_register("http://x", "label")
        assert service.screenshot_repo.by_session(app_session.id) == []


def test_ctx_render_and_register_render_failure_raises(tmp_db, project, monkeypatch):
    """Edge failing to launch/capture is an environment problem, not an app
    failure — TesterEnvError."""
    import app.testers._helpers as helpers

    monkeypatch.setattr(
        helpers,
        "render_url",
        lambda url, out_path: (_ for _ in ()).throw(
            HeadlessRenderError("edge crashed")
        ),
    )
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        ctx = TesterContext(project, app_session.id, AppSessionService(db))
        with pytest.raises(TesterEnvError, match="edge crashed"):
            ctx.render_and_register("http://x", "label")


def test_capture_renders_window_content_when_window_exists(
    tmp_db, project, monkeypatch, _fake_grabber
):
    """v1.17.12.3: a window owned by the app under test is rendered via
    PrintWindow — the screen grab is never taken."""
    monkeypatch.setattr(
        svc, "find_project_window", lambda path: (12345, (10, 20, 210, 120))
    )
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    monkeypatch.setattr(
        svc,
        "capture_window_content",
        lambda hwnd, rect: Image.new("RGB", (200, 100), (9, 8, 7)),
    )
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).capture(app_session.id)
        assert _fake_grabber == []


def test_capture_crops_when_window_render_blank(
    tmp_db, project, monkeypatch, _fake_grabber
):
    """A blank PrintWindow frame (GPU-composited window) falls back to a
    screen crop of the clamped rect."""
    monkeypatch.setattr(
        svc, "find_project_window", lambda path: (12345, (10, 20, 210, 120))
    )
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    monkeypatch.setattr(svc, "capture_window_content", lambda hwnd, rect: None)
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).capture(app_session.id)
        assert _fake_grabber[-1] == (10, 20, 210, 120)


def test_capture_skips_without_window(tmp_db, project, _fake_grabber):
    """v1.17.13.2: no desktop-grab fallback — a session with no window owned
    by the app records nothing (browser-served apps register headless-render
    frames from their tester instead)."""
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        shot = AppSessionService(db).capture(app_session.id)
        assert shot is None
        assert _fake_grabber == []
        assert not (
            Path(settings.db_path).parent.parent
            / "screenshots"
            / svc._slug(project.name)
        ).exists()


def test_clamp_rect_limits_to_virtual_screen(tmp_db, monkeypatch):
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    assert svc._clamp_rect((10, 20, 210, 120)) == (10, 20, 210, 120)
    assert svc._clamp_rect((-50, -20, 100, 60)) == (0, 0, 100, 60)
    assert svc._clamp_rect((400, 300, 500, 400)) is None


def test_is_blank_detects_black_frame():
    black = Image.new("RGB", (100, 80), (0, 0, 0))
    assert window_capture._is_blank(black)
    nearly_black = Image.new("RGB", (100, 80), (0, 0, 0))
    for x in range(0, 100, 10):
        for y in range(0, 80, 10):
            nearly_black.putpixel((x, y), (255, 255, 255))
    assert not window_capture._is_blank(nearly_black)
    bright = Image.new("RGB", (100, 80), (200, 200, 200))
    assert not window_capture._is_blank(bright)


def test_capture_window_content_returns_none_when_dc_fails(monkeypatch):
    """GetWindowDC failure -> None (caller crops instead)."""
    monkeypatch.setattr(
        window_capture,
        "user32",
        SimpleNamespace(GetWindowDC=lambda hwnd: 0, ReleaseDC=lambda h, d: 1),
    )
    assert window_capture.capture_window_content(1, (0, 0, 10, 10)) is None


def test_capture_window_content_returns_none_when_print_fails(monkeypatch):
    """PrintWindow failure -> None (caller crops instead)."""
    monkeypatch.setattr(
        window_capture,
        "user32",
        SimpleNamespace(
            GetWindowDC=lambda hwnd: 100,
            PrintWindow=lambda h, d, f: 0,
            ReleaseDC=lambda h, d: 1,
        ),
    )
    monkeypatch.setattr(
        window_capture,
        "gdi32",
        SimpleNamespace(
            CreateCompatibleDC=lambda dc: 200,
            CreateCompatibleBitmap=lambda dc, w, h: 300,
            SelectObject=lambda dc, obj: 400,
            DeleteObject=lambda obj: True,
            DeleteDC=lambda dc: True,
        ),
    )
    assert window_capture.capture_window_content(1, (0, 0, 10, 10)) is None


def _fake_gdi_render(monkeypatch, fill):
    """Fake user32/gdi32 where GetDIBits fills the pixel buffer with `fill`."""

    def get_dibits(mem_dc, hbitmap, start, height, buf, info, usage):
        header = ctypes.cast(
            info, ctypes.POINTER(window_capture._BITMAPINFOHEADER)
        ).contents
        width, height = header.biWidth, -header.biHeight
        ctypes.memset(buf, fill, width * height * 4)
        return height

    monkeypatch.setattr(
        window_capture,
        "user32",
        SimpleNamespace(
            GetWindowDC=lambda hwnd: 100,
            PrintWindow=lambda h, d, f: 1,
            ReleaseDC=lambda h, d: 1,
        ),
    )
    monkeypatch.setattr(
        window_capture,
        "gdi32",
        SimpleNamespace(
            CreateCompatibleDC=lambda dc: 200,
            CreateCompatibleBitmap=lambda dc, w, h: 300,
            SelectObject=lambda dc, obj: 400,
            DeleteObject=lambda obj: True,
            DeleteDC=lambda dc: True,
            GetDIBits=get_dibits,
        ),
    )


def test_capture_window_content_rejects_blank_frame(monkeypatch):
    _fake_gdi_render(monkeypatch, fill=0x00)
    assert window_capture.capture_window_content(1, (0, 0, 10, 10)) is None


def test_capture_window_content_renders_non_blank(monkeypatch):
    _fake_gdi_render(monkeypatch, fill=0x7F)
    image = window_capture.capture_window_content(1, (0, 0, 10, 10))
    assert image is not None
    assert image.size == (10, 10)


def test_find_project_window_handles_snapshot_failure(monkeypatch):
    """Invalid Toolhelp handle -> empty tree -> no window (full-screen)."""
    monkeypatch.setattr(
        window_capture,
        "kernel32",
        SimpleNamespace(
            CreateToolhelp32Snapshot=lambda a, b: ctypes.c_void_p(-1).value
        ),
    )
    assert window_capture.find_project_window(r"C:\projects\demo-app") is None


def test_virtual_screen_returns_bounds():
    left, top, right, bottom = window_capture._virtual_screen()
    assert right > left
    assert bottom > top


def test_descends_from_matches_direct_process(tmp_db, monkeypatch):
    """v1.17.12.3: the window's own process under the project dir matches."""
    tree = {42: (41, r"C:\projects\demo-app\.venv\Scripts\python.exe")}
    assert window_capture._descends_from(42, r"C:\projects\demo-app", tree)
    assert not window_capture._descends_from(42, r"C:\projects\other", tree)


def test_descends_from_matches_re_executed_ancestor(tmp_db, monkeypatch):
    """AG GUI is re-spawned by its venv python into the base interpreter, so
    the window's process exe lives outside the project — the ancestor chain
    (venv python under the project) must still match."""
    tree = {
        5: (6, r"C:\Users\j\AppData\Local\Programs\Python\Python311\python.exe"),
        6: (7, r"C:\projects\demo-app\.venv_sf3d\Scripts\python.exe"),
        7: (8, r"C:\Windows\system32\cmd.exe"),
        8: (0, r"C:\Windows\explorer.exe"),
    }
    assert window_capture._descends_from(5, r"C:\projects\demo-app", tree)
    assert not window_capture._descends_from(5, r"C:\projects\other-app", tree)


def test_descends_from_bounded_depth(tmp_db, monkeypatch):
    """An unrelated chain (python -> cmd -> explorer -> ...) must not match."""
    tree = {
        5: (4, r"C:\Users\j\AppData\Local\Programs\Python\Python311\python.exe"),
        4: (3, r"C:\Windows\system32\cmd.exe"),
        3: (2, r"C:\Windows\explorer.exe"),
        2: (1, r"C:\Windows\System32\svchost.exe"),
        1: (0, r"C:\Windows\System32\wininit.exe"),
        0: (-1, r"C:\Windows\System32\ntoskrnl.exe"),
    }
    assert not window_capture._descends_from(5, r"C:\projects\demo-app", tree)


def test_end_auto_capture_skips_without_window(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).end(app_session.id, "ok", "passed")
        shots = db.exec(
            select(SessionScreenshot).where(
                SessionScreenshot.session_id == app_session.id
            )
        ).all()
    assert shots == []


def test_end_auto_captures_window_shot(tmp_db, project, monkeypatch):
    _mock_window(monkeypatch)
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).end(app_session.id, "ok", "passed")
        shots = db.exec(
            select(SessionScreenshot).where(
                SessionScreenshot.session_id == app_session.id
            )
        ).all()
    assert len(shots) == 1


def test_end_survives_non_utf8_app_log_bytes(tmp_db, project):
    """v1.17.11.0 regression: child apps write the log in their locale
    encoding (cp1252 here); end() used to crash reading the slice with
    UnicodeDecodeError and left the session 'running' forever."""
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        path = _log_path(project.name)
        with open(path, "ab") as fh:
            fh.write(b"\x97 engine ready\x97\n")
        AppSessionService(db).end(app_session.id, "ok", "passed")
        db.refresh(app_session)
        assert app_session.status == SessionStatus.PASSED
        assert app_session.ended_at is not None
        assert app_session.log_slice is not None
        assert "\ufffd engine ready\ufffd" in app_session.log_slice


def test_capture_with_checkpoint_link(tmp_db, project, monkeypatch):
    _mock_window(monkeypatch)
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        checkpoint = AppSessionService(db).checkpoint(app_session.id, "hud visible")
        shot = AppSessionService(db).capture(app_session.id, checkpoint.id)
        assert shot.checkpoint_id == checkpoint.id


# ------------------------------------------------------------------- delete


def test_delete_removes_rows_and_files(tmp_db, project, tmp_path):
    source = tmp_path / "render.png"
    Image.new("RGB", (200, 100), (9, 8, 7)).save(source, "PNG")
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        service.checkpoint(app_session.id, "c")
        shot = service.register_screenshot(app_session.id, source)
        shot_dir = (
            Path(settings.db_path).parent.parent
            / "screenshots"
            / svc._slug(project.name)
        )
        full = shot_dir / shot.path
        service.delete(app_session.id)
        assert db.get(AppSession, app_session.id) is None
    assert not full.exists()


# ---------------------------------------------------------------- portfolio


def test_export_copies_and_builds_snippet(tmp_db, project, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "portfolio_dir", tmp_path / "portfolio")
    source = tmp_path / "render.png"
    Image.new("RGB", (200, 100), (9, 8, 7)).save(source, "PNG")
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id, title="Ship the demo")
        shot = AppSessionService(db).register_screenshot(app_session.id, source)
        result = AppSessionService(db).export_to_portfolio(app_session.id, shot.id)
    assert len(result["copied"]) == 2
    assert (tmp_path / "portfolio" / "images" / "sessions").exists()
    assert "demo-app — Ship the demo" in result["snippet"]
    assert "images/sessions/demo-app-" in result["snippet"]
    assert "github.com/jamesdileva/demo-app" in result["snippet"]
    assert "openModal" in result["snippet"]


def test_export_unknown_screenshot_raises(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        with pytest.raises(ValueError):
            AppSessionService(db).export_to_portfolio(app_session.id, "nope")


# ----------------------------------------------------------- log slice util


def test_slice_for_unstarted_session_is_empty(tmp_db, project):
    with DbSession(get_engine()) as db:
        assert AppSessionService(db)._slice_for(project, "zzz") == ""


def test_resolve_screenshot_blocks_traversal(tmp_db, project, tmp_path):
    source = tmp_path / "render.png"
    Image.new("RGB", (200, 100), (9, 8, 7)).save(source, "PNG")
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        assert svc.resolve_screenshot(db, app_session.id, "..\\sentinel.db") is None
        assert svc.resolve_screenshot(db, app_session.id, "..\\..\\x.png") is None
        shot = AppSessionService(db).register_screenshot(app_session.id, source)
        resolved = svc.resolve_screenshot(db, app_session.id, shot.path)
    assert resolved is not None and resolved.exists()


# --------------------------------------------------------------------- API


def test_api_full_flow(client, project, monkeypatch):
    _mock_window(monkeypatch)
    project_id = project.id
    response = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "title": "API session", "expected_output": "x"},
    )
    assert response.status_code == 201
    body = response.json()
    session_id = body["id"]
    assert body["status"] == "running"
    assert body["project_name"] == "demo-app"

    response = client.post(
        f"/api/v1/sessions/{session_id}/checkpoints", json={"label": "loaded"}
    )
    assert response.status_code == 201
    checkpoint_id = response.json()["id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/screenshots",
        json={"checkpoint_id": checkpoint_id},
    )
    assert response.status_code == 201
    shot_filename = response.json()["path"]
    shot_id = response.json()["id"]

    response = client.get(f"/api/v1/sessions/{session_id}/screenshots/{shot_filename}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get(
        f"/api/v1/sessions/{session_id}/screenshots/"
        f"{Path(shot_filename).stem}.thumb.png"
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/v1/sessions/{session_id}/end",
        json={"actual_outcome": "all good", "status": "passed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert response.json()["log_slice"]

    response = client.get("/api/v1/sessions", params={"project_id": project_id})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/api/v1/sessions", params={"status": "running"})
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = client.patch(f"/api/v1/sessions/{session_id}", json={"title": "Renamed"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"

    response = client.post(
        f"/api/v1/sessions/{session_id}/screenshots/{shot_id}/export"
    )
    assert response.status_code == 200
    assert "snippet" in response.json()

    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/sessions/{session_id}").status_code == 404


def test_api_capture_windowless_409(client, project):
    """v1.17.13.2: browser-served/headless apps have no window — capture 409s
    with a pointer at the tester-render path instead of grabbing the desktop."""
    response = client.post(
        "/api/v1/sessions",
        json={"project_id": project.id, "title": "API session"},
    )
    session_id = response.json()["id"]
    response = client.post(f"/api/v1/sessions/{session_id}/screenshots", json={})
    assert response.status_code == 409
    assert "headless-render" in response.json()["detail"]


def test_api_missing_session_404s(client, project):
    assert client.get("/api/v1/sessions/nope").status_code == 404
    assert (
        client.post(
            "/api/v1/sessions/nope/checkpoints", json={"label": "x"}
        ).status_code
        == 404
    )
    assert (
        client.post("/api/v1/sessions/nope/end", json={"status": "passed"}).status_code
        == 404
    )
    assert client.delete("/api/v1/sessions/nope").status_code == 404
    assert client.get("/api/v1/sessions/nope/screenshots/x.png").status_code == 404
