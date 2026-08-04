"""SQLModel table definitions — the full schema specified in
docs/02_Implementation_Guide.md §1.

Tables are created in Sprint 2; the model definitions land here in Sprint 1.
"""

import datetime
import enum
import uuid

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Project(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    path: str
    language: str
    framework: str | None = None
    stack: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: ProjectStatus = ProjectStatus.ACTIVE
    health_score: float | None = None
    last_indexed: datetime.datetime | None = None
    last_scanned: datetime.datetime | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)
    updated_at: datetime.datetime = Field(default_factory=_utcnow)

    files: list["ProjectFile"] = Relationship(back_populates="project")
    dependencies: list["Dependency"] = Relationship(back_populates="project")
    security_findings: list["SecurityFinding"] = Relationship(back_populates="project")
    git_commits: list["GitCommit"] = Relationship(back_populates="project")
    test_results: list["TestResult"] = Relationship(back_populates="project")
    build_logs: list["BuildLog"] = Relationship(back_populates="project")
    knowledge_summaries: list["KnowledgeSummary"] = Relationship(
        back_populates="project"
    )
    portfolio_score: "PortfolioScore" = Relationship(back_populates="project")


class ProjectFile(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    path: str
    absolute_path: str
    language: str | None = None
    size_bytes: int | None = None
    summary: str | None = None
    embedding_id: str | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="files")


class Dependency(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    name: str
    version: str | None = None
    latest_version: str | None = None
    type: str = "production"
    vulnerable: bool = False
    severity: Severity | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="dependencies")


class SecurityFinding(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    type: str
    severity: Severity
    title: str
    description: str | None = None
    ai_explanation: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    cve_id: str | None = None
    remediation: str | None = None
    resolved: bool = False
    detected_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="security_findings")


class GitCommit(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    hash: str
    message: str
    author: str | None = None
    timestamp: datetime.datetime | None = None
    added_files: list[str] | None = Field(default=None, sa_column=Column(JSON))
    modified_files: list[str] | None = Field(default=None, sa_column=Column(JSON))
    deleted_files: list[str] | None = Field(default=None, sa_column=Column(JSON))
    feature_tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="git_commits")


class TestResult(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    run_at: datetime.datetime = Field(default_factory=_utcnow)
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float | None = None
    framework: str | None = None
    summary: str | None = None
    raw_output: str | None = None

    project: Project = Relationship(back_populates="test_results")


class BuildLog(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    started_at: datetime.datetime = Field(default_factory=_utcnow)
    completed_at: datetime.datetime | None = None
    exit_code: int | None = None
    success: bool | None = None
    stdout: str | None = None
    stderr: str | None = None
    commands: dict | None = Field(default=None, sa_column=Column(JSON))

    project: Project = Relationship(back_populates="build_logs")


class KnowledgeSummary(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    type: str
    content: str
    generated_at: datetime.datetime = Field(default_factory=_utcnow)
    model: str | None = None
    confidence: float | None = None

    project: Project = Relationship(back_populates="knowledge_summaries")


class PortfolioScore(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", unique=True)
    build_status: str = "pending"
    test_status: str = "pending"
    documentation_pct: int = 0
    security_status: str = "pending"
    screenshots_available: bool = False
    portfolio_score: float = 0.0
    updated_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="portfolio_score")


class WorldSimState(SQLModel, table=True):
    """Optional World Simulator state table. Separate from project data."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    day_number: int = 0
    events: dict = Field(default_factory=dict, sa_column=Column(JSON))
    nations: dict = Field(default_factory=dict, sa_column=Column(JSON))
    economy: dict = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime.datetime = Field(default_factory=_utcnow)


class ConfigEntry(SQLModel, table=True):
    """Application configuration stored in DB."""

    key: str = Field(primary_key=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime.datetime = Field(default_factory=_utcnow)
