"""Error-triage tests (later.md Tier 3, v1.17.12.0).

Covers: deterministic extraction (error lines, traceback frames, source
previews), the evidence packet shape, the API (triage/summarize incl. 400s,
404, 503), provenance recording, and cascade delete of analysis rows.
"""

from pathlib import Path

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.db import connection
from app.db.connection import get_engine
from app.db.models import AppSession, OllamaQueryLog, Project, TriageAnalysis
from app.services import triage_service
from app.services.app_sessions import AppSessionService
from app.services.triage_service import (
    build_evidence,
    detect_patterns,
    error_lines,
    resolve_frames,
    traceback_frames,
)

TRACEBACK_SLICE = """\
[sentinel] Session started 2026-08-15T00:00:00 s1: demo
  File "C:\\projects\\demo-app\\app\\main.py", line 42, in handler
    result = run_pipeline()
  File "C:\\projects\\demo-app\\rigging\\pipeline.py", line 17, in run_pipeline
ModuleNotFoundError: No module named 'x'
[sentinel] Session ended 2026-08-15T00:00:01 s1: failed
"""


# ------------------------------------------------------------- deterministic


def test_error_lines_extract_and_cap():
    slice_text = "\n".join(
        ["plain line", "Traceback (most recent call last):", "error: boom"]
        + [f"ERROR line {i}" for i in range(50)]
    )
    lines = error_lines(slice_text)
    assert "Traceback (most recent call last):" in lines
    assert "error: boom" in lines
    assert len(lines) <= 40


def test_traceback_frames_parse_windows_paths():
    frames = traceback_frames(TRACEBACK_SLICE)
    assert frames == [
        ("C:\\projects\\demo-app\\app\\main.py", 42, "handler"),
        ("C:\\projects\\demo-app\\rigging\\pipeline.py", 17, "run_pipeline"),
    ]


def test_traceback_frames_skip_plain_lines():
    assert traceback_frames("just a log line\nnothing here") == []


def test_resolve_frames_inside_project_with_source(tmp_path):
    project = tmp_path / "demo-app"
    target = project / "app" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(f"line {i}" for i in range(1, 25)), encoding="utf-8")
    frames = resolve_frames(
        [(str(target), 22, "handler"), (r"C:\other\site-packages\pkg.py", 3, "f")],
        str(project),
    )
    assert len(frames) == 1  # the site-packages frame is dropped
    frame = frames[0]
    assert frame["line"] == 22
    assert frame["function"] == "handler"
    assert frame["relative_path"] == "app\\main.py"
    numbers = [s["line_number"] for s in frame["source"]]
    assert numbers == [19, 20, 21, 22, 23, 24]
    assert frame["source"][3]["text"] == "line 22"


def test_resolve_frames_relative_paths(tmp_path):
    project = tmp_path / "demo-app"
    target = project / "app" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    frames = resolve_frames([(r"app\main.py", 1, None)], str(project))
    assert len(frames) == 1
    assert frames[0]["source"][0]["text"] == "x = 1"


def test_resolve_frames_missing_file_no_crash(tmp_path):
    frames = resolve_frames(
        [(str(tmp_path / "app" / "ghost.py"), 5, "f")], str(tmp_path)
    )
    assert len(frames) == 1  # frame stays inside the project…
    assert frames[0]["source"] == []  # …but a missing file yields no preview


def test_detect_patterns():
    assert detect_patterns(TRACEBACK_SLICE) == ["ModuleNotFoundError"]
    assert detect_patterns("all quiet") == []


def test_build_evidence_no_traceback_note(tmp_path):
    project = Project(name="demo-app", path=str(tmp_path), language="python")
    app_session = AppSession(project_id="p1", title="t", status="failed")
    app_session.status = "failed"
    app_session.actual_outcome = "expected 200, got 500"
    app_session.log_slice = "outcome failed\n[sentinel] Session ended"
    evidence = build_evidence(project, app_session)
    assert evidence["status"] == "failed"
    assert evidence["actual_outcome"] == "expected 200, got 500"
    assert evidence["frames"] == []
    assert evidence["traceback_available"] is False
    assert "No traceback found" in evidence["note"]


def test_build_evidence_resolves_frames(tmp_path):
    project_dir = tmp_path / "demo-app"
    target = project_dir / "app" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(f"line {i}" for i in range(1, 60)), encoding="utf-8")
    project = Project(name="demo-app", path=str(project_dir), language="python")
    app_session = AppSession(project_id="p1", title="t", status="failed")
    app_session.status = "failed"
    app_session.log_slice = TRACEBACK_SLICE.replace(
        "C:\\projects\\demo-app", str(project_dir)
    )
    evidence = build_evidence(project, app_session)
    assert evidence["traceback_available"] is True
    assert evidence["patterns"] == ["ModuleNotFoundError"]
    assert [f["line"] for f in evidence["frames"]] == [42, 17]
    assert evidence["frames"][0]["source"][3]["text"] == "line 42"


# -------------------------------------------------------------------- helpers


def _mk_project(db, tmp_path, name="demo-app") -> Project:
    project = Project(
        name=name,
        path=str(tmp_path),
        repo_url="",
        language="python",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _mk_failed_session(db, project, log_slice: str, outcome="boom") -> str:
    service = AppSessionService(db)
    app_session = service.start(project.id, "triage me")
    log_path = (
        Path(connection.settings.db_path).parent.parent
        / "logs"
        / "apps"
        / f"{project.name}.log"
    )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{log_slice}\n")
    session = service.end(app_session.id, outcome, "failed")
    return session.id


def _fake_ollama_response(text="The upload step failed at app/main.py:42."):
    class FakeOllama:
        def generate_with_metrics(self, prompt, **kwargs):
            return {
                "response": text,
                "model": "llama3.1:8b",
                "eval_count": 42,
                "eval_duration_ns": 1_000_000,
                "total_duration_ns": 2_000_000,
            }

    return FakeOllama


# ----------------------------------------------------------------------- API


def test_api_triage_returns_evidence(client, tmp_path):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = _mk_failed_session(
            db,
            project,
            TRACEBACK_SLICE.replace("C:\\projects\\demo-app", str(tmp_path)),
        )
    response = client.post(f"/api/v1/sessions/{session_id}/triage")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["summary"] is None
    assert body["evidence"]["traceback_available"] is True
    assert [f["line"] for f in body["evidence"]["frames"]] == [42, 17]
    assert body["evidence"]["patterns"] == ["ModuleNotFoundError"]
    assert body["evidence"]["note"] is None
    with DbSession(get_engine()) as db:
        rows = db.exec(
            select(TriageAnalysis).where(TriageAnalysis.session_id == session_id)
        ).all()
    assert len(rows) == 1
    assert rows[0].evidence["actual_outcome"] == "boom"


def test_api_triage_running_session_400(client, tmp_path):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = AppSessionService(db).start(project.id, "still going").id
    assert client.post(f"/api/v1/sessions/{session_id}/triage").status_code == 400


def test_api_triage_unknown_session_404(client):
    assert client.post("/api/v1/sessions/nope/triage").status_code == 404


def test_api_summarize_stores_provenance(client, tmp_path, monkeypatch):
    monkeypatch.setattr(triage_service, "OllamaService", _fake_ollama_response())
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = _mk_failed_session(db, project, "error: exploded")
    response = client.post(f"/api/v1/sessions/{session_id}/summarize")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "The upload step failed at app/main.py:42."
    assert body["model"] == "llama3.1:8b"
    with DbSession(get_engine()) as db:
        rows = db.exec(
            select(TriageAnalysis).where(TriageAnalysis.session_id == session_id)
        ).all()
        query_log = db.exec(
            select(OllamaQueryLog).where(OllamaQueryLog.purpose == "triage-summary")
        ).all()
    assert len(rows) == 1
    assert rows[0].summary == body["summary"]
    assert rows[0].model == "llama3.1:8b"
    assert len(query_log) == 1


def test_api_summarize_creates_evidence_when_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        triage_service, "OllamaService", _fake_ollama_response("evidence only")
    )
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = _mk_failed_session(db, project, "error: exploded")
    response = client.post(f"/api/v1/sessions/{session_id}/summarize")
    assert response.status_code == 200
    with DbSession(get_engine()) as db:
        rows = db.exec(
            select(TriageAnalysis).where(TriageAnalysis.session_id == session_id)
        ).all()
    assert len(rows) == 1  # triage + summarize collapsed into one row
    assert rows[0].summary == "evidence only"


def test_api_summarize_ollama_down_503(client, tmp_path, monkeypatch):
    from app.services.ollama_service import OllamaUnavailableError

    class DownOllama:
        def generate_with_metrics(self, prompt, **kwargs):
            raise OllamaUnavailableError("connection refused")

    monkeypatch.setattr(triage_service, "OllamaService", DownOllama)
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = _mk_failed_session(db, project, "error: exploded")
    response = client.post(f"/api/v1/sessions/{session_id}/summarize")
    assert response.status_code == 503


def test_delete_session_cascades_triage_rows(client, tmp_path):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, tmp_path)
        session_id = _mk_failed_session(db, project, "error: exploded")
    assert client.post(f"/api/v1/sessions/{session_id}/triage").status_code == 200
    assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 204
    with DbSession(get_engine()) as db:
        rows = db.exec(
            select(TriageAnalysis).where(TriageAnalysis.session_id == session_id)
        ).all()
    assert rows == []
