"""Session recorder API (later.md Tier 1 + Tier 4).

Sessions record app-testing runs against the app's own log; screenshots are
full-screen grabs stored locally and optionally exported to the user's
portfolio repo (copy only — Sentinel never pushes, Rule 2).
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlmodel import Session as DbSession

from app.core.logging import get_logger
from app.db.connection import get_session
from app.db.models import SessionStatus
from app.repositories import ProjectRepository
from app.schemas.session import (
    SessionCheckpointCreate,
    SessionCheckpointRead,
    SessionCreate,
    SessionEndRequest,
    SessionExportRead,
    SessionRead,
    SessionScreenshotCreate,
    SessionScreenshotRead,
    SessionUpdate,
)
from app.schemas.triage import TriageEvidence, TriageRead
from app.services.app_sessions import AppSessionService, resolve_screenshot
from app.services.triage_service import TriageService

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _service(db: DbSession) -> AppSessionService:
    return AppSessionService(db)


def _read(app_session, db: DbSession) -> SessionRead:
    """Single-session read (create/detail/update paths)."""
    return _read_batch([app_session], db)[0]


def _read_batch(app_sessions, db: DbSession) -> list[SessionRead]:
    """Build SessionReads with three queries TOTAL instead of 3N+1
    (v1.17.18.6, audit2 C6): one IN query each for checkpoints,
    screenshots, and projects."""
    service = AppSessionService(db)
    ids = [s.id for s in app_sessions]
    checkpoints: dict[str, list] = defaultdict(list)
    screenshots: dict[str, list] = defaultdict(list)
    if ids:
        for c in service.checkpoint_repo.by_sessions(ids):
            checkpoints[c.session_id].append(c)
        for sc in service.screenshot_repo.by_sessions(ids):
            screenshots[sc.session_id].append(sc)
    project_ids = {s.project_id for s in app_sessions}
    projects = ProjectRepository(db).by_ids(project_ids) if project_ids else {}
    return [
        SessionRead(
            id=s.id,
            project_id=s.project_id,
            project_name=(
                projects[s.project_id].name if s.project_id in projects else None
            ),
            title=s.title,
            expected_output=s.expected_output,
            actual_outcome=s.actual_outcome,
            status=s.status.value,
            started_at=s.started_at,
            ended_at=s.ended_at,
            log_slice=s.log_slice,
            checkpoints=[
                SessionCheckpointRead.model_validate(c)
                for c in checkpoints.get(s.id, [])
            ],
            screenshots=[
                SessionScreenshotRead.model_validate(sc)
                for sc in screenshots.get(s.id, [])
            ],
        )
        for s in app_sessions
    ]


@router.post("", response_model=SessionRead, status_code=201)
def create_session(body: SessionCreate, db: DbSession = Depends(get_session)):
    app_session = _service(db).start(body.project_id, body.title, body.expected_output)
    return _read(app_session, db)


@router.get("", response_model=list[SessionRead])
def list_sessions(
    project_id: str | None = None,
    status: str | None = None,
    db: DbSession = Depends(get_session),
):
    service = _service(db)
    return _read_batch(service.list_sessions(project_id, status), db)


@router.get("/{session_id}", response_model=SessionRead)
def get_session_detail(session_id: str, db: DbSession = Depends(get_session)):
    try:
        app_session = _service(db).get(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _read(app_session, db)


@router.post("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: str, body: SessionUpdate, db: DbSession = Depends(get_session)
):
    """Update a session's title/outcome/status. v1.17.18.6 (audit2 C7): was
    the API's only PATCH — conventions say state-changing actions use POST."""
    try:
        app_session = _service(db).update(
            session_id,
            title=body.title,
            expected_output=body.expected_output,
            actual_outcome=body.actual_outcome,
            status=body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _read(app_session, db)


@router.post(
    "/{session_id}/checkpoints", response_model=SessionCheckpointRead, status_code=201
)
def add_checkpoint(
    session_id: str,
    body: SessionCheckpointCreate,
    db: DbSession = Depends(get_session),
):
    try:
        return _service(db).checkpoint(session_id, body.label)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/end", response_model=SessionRead)
def end_session(
    session_id: str, body: SessionEndRequest, db: DbSession = Depends(get_session)
):
    try:
        app_session = _service(db).end(session_id, body.actual_outcome, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _read(app_session, db)


def _triage_read(analysis, db: DbSession) -> TriageRead:
    return TriageRead(
        id=analysis.id,
        session_id=analysis.session_id,
        evidence=TriageEvidence.model_validate(analysis.evidence),
        summary=analysis.summary,
        model=analysis.model,
        created_at=analysis.created_at,
    )


def _terminal_session(session_id: str, db: DbSession):
    """Fetch a session that has ended (failed/investigate) — or 400/404."""
    try:
        app_session = _service(db).get(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if app_session.status == SessionStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Session is still running — end it before triaging",
        )
    return app_session


@router.post("/{session_id}/triage", response_model=TriageRead)
def triage_session(session_id: str, db: DbSession = Depends(get_session)):
    """Deterministic error capture: verbatim error lines, traceback frames
    resolved to project files, source previews. No AI (Rule 3)."""
    app_session = _terminal_session(session_id, db)
    analysis = TriageService(db).triage(app_session)
    return _triage_read(analysis, db)


@router.post("/{session_id}/summarize", response_model=TriageRead)
def summarize_session(session_id: str, db: DbSession = Depends(get_session)):
    """Optional local-LLM paragraph DESCRIBING the deterministic evidence.
    No causes, no fixes, no decisions — provenance recorded (Rules 2+7).
    Ollama unavailability maps to 503 via the central SentinelError handler
    (v1.17.18.3, audit2 Q3) — same as /rag/* now."""
    app_session = _terminal_session(session_id, db)
    analysis = TriageService(db).summarize(app_session)
    return _triage_read(analysis, db)


@router.post(
    "/{session_id}/screenshots", response_model=SessionScreenshotRead, status_code=201
)
def capture_screenshot(
    session_id: str,
    body: SessionScreenshotCreate | None = None,
    db: DbSession = Depends(get_session),
):
    checkpoint_id = body.checkpoint_id if body else None
    try:
        shot = _service(db).capture(session_id, checkpoint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if shot is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No window to capture — this app is browser-served; its "
                "tester registers headless-render screenshots instead."
            ),
        )
    return shot


@router.post(
    "/{session_id}/screenshots/{screenshot_id}/export", response_model=SessionExportRead
)
def export_screenshot(
    session_id: str, screenshot_id: str, db: DbSession = Depends(get_session)
):
    try:
        return _service(db).export_to_portfolio(session_id, screenshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: DbSession = Depends(get_session)):
    try:
        _service(db).delete(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/{session_id}/screenshots/{filename}")
def screenshot_file(
    session_id: str, filename: str, db: DbSession = Depends(get_session)
):
    path = resolve_screenshot(db, session_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type)
