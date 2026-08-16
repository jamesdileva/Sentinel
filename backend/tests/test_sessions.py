"""Session recorder tests (later.md Tier 1 + Tier 4)."""

from pathlib import Path

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
from app.utils import window_capture


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


def test_capture_saves_png_and_thumbnail(tmp_db, project):
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


def test_capture_uses_window_bbox_when_project_window_exists(
    tmp_db, project, monkeypatch, _fake_grabber
):
    """v1.17.12.3: a window owned by the app under test crops the grab."""
    monkeypatch.setattr(svc, "find_project_window", lambda path: (10, 20, 210, 120))
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).capture(app_session.id)
        assert _fake_grabber[-1] == (10, 20, 210, 120)


def test_capture_falls_back_to_full_screen_without_window(
    tmp_db, project, _fake_grabber
):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        AppSessionService(db).capture(app_session.id)
        assert _fake_grabber[-1] is None


def test_window_bbox_clamps_to_virtual_screen(tmp_db, monkeypatch):
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    service = AppSessionService.__new__(AppSessionService)
    assert service._window_bbox("C:\\projects\\demo-app") is None  # no window
    monkeypatch.setattr(svc, "find_project_window", lambda path: (-50, -20, 100, 60))
    assert service._window_bbox("C:\\projects\\demo-app") == (0, 0, 100, 60)
    monkeypatch.setattr(svc, "find_project_window", lambda path: (400, 300, 500, 400))
    assert service._window_bbox("C:\\projects\\demo-app") is None


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


def test_end_auto_captures_screenshot(tmp_db, project):
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


def test_capture_with_checkpoint_link(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        checkpoint = AppSessionService(db).checkpoint(app_session.id, "hud visible")
        shot = AppSessionService(db).capture(app_session.id, checkpoint.id)
        assert shot.checkpoint_id == checkpoint.id


# ------------------------------------------------------------------- delete


def test_delete_removes_rows_and_files(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        service = AppSessionService(db)
        service.checkpoint(app_session.id, "c")
        shot = service.capture(app_session.id)
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
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id, title="Ship the demo")
        shot = AppSessionService(db).capture(app_session.id)
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


def test_resolve_screenshot_blocks_traversal(tmp_db, project):
    with DbSession(get_engine()) as db:
        app_session = _session(db, project.id)
        assert svc.resolve_screenshot(db, app_session.id, "..\\sentinel.db") is None
        assert svc.resolve_screenshot(db, app_session.id, "..\\..\\x.png") is None
        shot = AppSessionService(db).capture(app_session.id)
        resolved = svc.resolve_screenshot(db, app_session.id, shot.path)
    assert resolved is not None and resolved.exists()


# --------------------------------------------------------------------- API


def test_api_full_flow(client, project):
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
