"""Data access layer."""

from app.repositories.base import Repository
from app.repositories.build import BuildLogRepository
from app.repositories.dependency import DependencyRepository
from app.repositories.file import ProjectFileRepository
from app.repositories.git import GitCommitRepository
from app.repositories.knowledge_summary import KnowledgeSummaryRepository
from app.repositories.project import ProjectRepository
from app.repositories.security import SecurityRepository
from app.repositories.session import (
    SessionCheckpointRepository,
    SessionRepository,
    SessionScreenshotRepository,
)
from app.repositories.test import TestRepository

__all__ = [
    "BuildLogRepository",
    "DependencyRepository",
    "GitCommitRepository",
    "KnowledgeSummaryRepository",
    "ProjectFileRepository",
    "ProjectRepository",
    "Repository",
    "SecurityRepository",
    "SessionCheckpointRepository",
    "SessionRepository",
    "SessionScreenshotRepository",
    "TestRepository",
]
