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
    sessions: list["AppSession"] = Relationship(back_populates="project")


class ProjectFile(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    path: str
    absolute_path: str
    language: str | None = None
    size_bytes: int | None = None
    # v1.17.7.1: nanosecond mtime of the file on disk when it was last parsed.
    # An unchanged size+mtime lets a full scan skip re-reading/re-parsing.
    mtime_ns: int | None = None
    summary: str | None = None
    embedding_id: str | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="files")


class Dependency(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str
    version: str | None = None
    type: str = "production"
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="dependencies")


class SecurityFinding(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
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
    project_id: str = Field(foreign_key="project.id", index=True)
    hash: str
    message: str
    author: str | None = None
    timestamp: datetime.datetime | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="git_commits")


class TestResult(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
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
    project_id: str = Field(foreign_key="project.id", index=True)
    started_at: datetime.datetime = Field(default_factory=_utcnow)
    completed_at: datetime.datetime | None = None
    exit_code: int | None = None
    success: bool | None = None
    stdout: str | None = None
    stderr: str | None = None
    commands: dict | None = Field(default=None, sa_column=Column(JSON))
    # v1.17.8.0 build->open: the startup command detached-launched after a
    # successful build (or instead of a build that isn't needed). None when
    # no app was launched.
    launch_command: str | None = None

    project: Project = Relationship(back_populates="build_logs")


class KnowledgeSummary(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    type: str
    content: str
    generated_at: datetime.datetime = Field(default_factory=_utcnow)
    model: str | None = None

    project: Project = Relationship(back_populates="knowledge_summaries")


class OllamaQueryLog(SQLModel, table=True):
    """Deterministic record of each Ollama call (System page, Sprint 12).

    Powers tokens/sec and latency readouts. Written on every RAG answer and
    project summary; no AI involvement — just Ollama's own counters.
    `purpose` labels what the call served (query / summary / rag-index).
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    model: str
    purpose: str = "query"
    prompt_chars: int = 0
    response_chars: int = 0
    eval_count: int = 0
    eval_duration_ns: int = 0
    total_duration_ns: int = 0
    # v1.17.18.3 (audit2 Q4/Q6): /system/* reads the newest rows via
    # ORDER BY created_at DESC LIMIT n — unindexed this is a full scan
    # that degrades linearly as the table grows forever.
    created_at: datetime.datetime = Field(default_factory=_utcnow, index=True)


class ActivityEvent(SQLModel, table=True):
    """Bounded history backing the live activity stream (Sprint 16/v1.17).

    Written by the in-process activity bus for every notable event (sync,
    indexing, builds, security, Ollama usage); the /api/v1/ws/jobs channel
    broadcasts them live and GET /api/v1/system/activity reads the tail so
    the dashboard can show what happened while no one was looking.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    kind: str  # sync | index | build | test | security | ollama | job | system
    message: str
    detail: str | None = None
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime.datetime = Field(default_factory=_utcnow, index=True)


class ChatMessage(SQLModel, table=True):
    """One persisted message in a project-scoped chat room (v1.17).

    Lets the Knowledge chat survive tab switches and restarts: rows are
    written per exchange and replayed when the room is opened again.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(default="", index=True)
    role: str  # user | assistant
    text: str
    sources: list | None = Field(default=None, sa_column=Column(JSON))
    model: str | None = None
    confidence: float | None = None
    error: str | None = None  # failure message when no answer was produced
    created_at: datetime.datetime = Field(default_factory=_utcnow)


class PortfolioScore(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", unique=True)
    build_status: str = "pending"
    test_status: str = "pending"
    documentation_pct: int = 0
    # v1.17.18.6 (audit2 follow-up): presence-based docs verdict ("passing" /
    # "partial" / "pending") — the density percentage alone marked well-
    # documented projects ✗ just for having lots of code.
    documentation_status: str = Field(default="pending")
    security_status: str = "pending"
    screenshots_available: bool = False
    portfolio_score: float = 0.0
    updated_at: datetime.datetime = Field(default_factory=_utcnow)

    project: Project = Relationship(back_populates="portfolio_score")


class SyncRun(SQLModel, table=True):
    """Persisted GitHub repo sync outcomes (Sprint 15).

    One row per `repo-sync` run; the dashboard header pill and
    GET /api/v1/system/sync read the most recent row. Nothing else uses it.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    status: str = "success"  # success | error | skipped
    ran_at: datetime.datetime = Field(default_factory=_utcnow)
    cloned: list = Field(default_factory=list, sa_column=Column(JSON))
    pulled: list = Field(default_factory=list, sa_column=Column(JSON))
    failed: dict = Field(default_factory=dict, sa_column=Column(JSON))
    indexed: int = 0
    knowledge_queued: int = 0
    detail: str | None = None


class SessionStatus(str, enum.Enum):
    """v1.17.10: session lifecycle — RUNNING until the user ends it."""

    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INVESTIGATE = "investigate"


class AppSession(SQLModel, table=True):
    """A recorded app-testing session (later.md Tier 1).

    The session writes `[sentinel]` markers into the app's own log
    (data/logs/apps/<slug>.log — the same file the launched app's output
    flows into); `log_slice` is captured deterministically between the
    session's start and end markers at `end()`.
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    title: str
    expected_output: str | None = None
    actual_outcome: str | None = None
    status: SessionStatus = SessionStatus.RUNNING
    started_at: datetime.datetime = Field(default_factory=_utcnow)
    ended_at: datetime.datetime | None = None
    log_slice: str | None = None

    project: Project = Relationship(back_populates="sessions")
    checkpoints: list["SessionCheckpoint"] = Relationship(back_populates="session")
    screenshots: list["SessionScreenshot"] = Relationship(back_populates="session")
    triage_analyses: list["TriageAnalysis"] = Relationship(back_populates="session")


class SessionCheckpoint(SQLModel, table=True):
    """A user-labeled moment during a session (later.md Tier 1)."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="appsession.id", index=True)
    label: str
    at: datetime.datetime = Field(default_factory=_utcnow)

    session: AppSession = Relationship(back_populates="checkpoints")


class SessionScreenshot(SQLModel, table=True):
    """A full-screen grab taken during a session (later.md Tier 4).

    `path` is relative to data/screenshots/<project-slug>/; the thumbnail
    lives next to it as <stem>.thumb.png (90x60, matching the portfolio's
    card thumbs).
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="appsession.id", index=True)
    checkpoint_id: str | None = Field(default=None, foreign_key="sessioncheckpoint.id")
    path: str
    captured_at: datetime.datetime = Field(default_factory=_utcnow)

    session: AppSession = Relationship(back_populates="screenshots")


class TriageAnalysis(SQLModel, table=True):
    """Deterministic error-triage record for a session (later.md Tier 3).

    `evidence` is the deterministic packet — error lines quoted verbatim from
    the session's log slice, traceback frames resolved to `file:line` in the
    project, and source previews read straight from disk. Never AI-written
    (Rule 3). `summary` is the optional local-LLM paragraph DESCRIBING that
    evidence — no causes, no fixes, no decisions (Rules 2+3); `model` +
    `created_at` carry the provenance (Rule 7).
    """

    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="appsession.id", index=True)
    evidence: dict = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str | None = None
    model: str | None = None
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    session: AppSession = Relationship(back_populates="triage_analyses")
