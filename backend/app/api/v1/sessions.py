"""Session recorder API (later.md Tier 1 + Tier 4).

Sessions record app-testing runs against the app's own log; screenshots are
full-screen grabs stored locally and optionally exported to the user's
portfolio repo (copy only — Sentinel never pushes, Rule 2).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlmodel import Session as DbSession

from app.core.logging import get_logger
from app.db.connection import get_session
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
from app.services.app_sessions import AppSessionService, resolve_screenshot

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _service(db: DbSession) -> AppSessionService:
    return AppSessionService(db)


def _read(app_session, db: DbSession) -> SessionRead:
    service = AppSessionService(db)
    project = ProjectRepository(db).get(app_session.project_id)
    return SessionRead(
        id=app_session.id,
        project_id=app_session.project_id,
        project_name=project.name if project else None,
        title=app_session.title,
        expected_output=app_session.expected_output,
        actual_outcome=app_session.actual_outcome,
        status=app_session.status.value,
        started_at=app_session.started_at,
        ended_at=app_session.ended_at,
        log_slice=app_session.log_slice,
        checkpoints=[
            SessionCheckpointRead.model_validate(c)
            for c in service.checkpoint_repo.by_session(app_session.id)
        ],
        screenshots=[
            SessionScreenshotRead.model_validate(s)
            for s in service.screenshot_repo.by_session(app_session.id)
        ],
    )


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
    return [_read(s, db) for s in service.list_sessions(project_id, status)]


@router.get("/{session_id}", response_model=SessionRead)
def get_session_detail(session_id: str, db: DbSession = Depends(get_session)):
    try:
        app_session = _service(db).get(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _read(app_session, db)


@router.patch("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: str, body: SessionUpdate, db: DbSession = Depends(get_session)
):
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
        return _service(db).capture(session_id, checkpoint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
