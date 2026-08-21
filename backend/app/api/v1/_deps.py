"""Shared API dependencies (v1.17.18.4, audit2 C1).

`_project_or_404` was previously copy-pasted byte-identical into six route
modules; it lives here once so behavior and error text stay uniform.
"""

from fastapi import HTTPException
from sqlmodel import Session

from app.repositories import ProjectRepository


def project_or_404(project_id: str, session: Session):
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project
