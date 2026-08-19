# Project Sentinel â€” Implementation Guide

> **Version:** 1.1
> **Status:** Draft â€” Sprint 0 (Pre-MVP)
> **Audience:** Developers, AI coding agents
> **Related:** See `docs/01_Master_Architecture.md` for architecture overview

This document is the **technical reference** for implementing Project Sentinel. It provides concrete specifications â€” database schemas, API contracts, service interfaces, configuration formats, RAG setup, and automation job definitions â€” that map directly to code. Every sprint in `docs/03_Sprint_Plan.md` references sections from this guide.

---

## Table of Contents

1. [Database Schema](#1-database-schema)
2. [API Endpoints](#2-api-endpoints)
3. [Service Interfaces](#3-service-interfaces)
4. [Configuration](#4-configuration)
5. [CLI](#5-cli)
6. [RAG Setup](#6-rag-setup)
7. [Automation Jobs](#7-automation-jobs)
8. [Parser Implementations](#8-parser-implementations)
9. [Security Scanning](#9-security-scanning)
10. [Screenshot & Testing](#10-screenshot--testing)
11. [World Simulator](#11-world-simulator)
12. [Testing Strategy](#12-testing-strategy)
14.5. [Portfolio Intelligence](#145-portfolio-intelligence)
14.6. [Observatory](#146-observatory)

---

## 1. Database Schema

All tables use SQLite via SQLAlchemy. ChromaDB is used separately for vector embeddings.

### 1.1. SQLModel Models (Python)

File: `backend/app/db/models.py`

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
import datetime
import enum

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
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    path: str  # Absolute filesystem path
    language: str
    framework: str | None
    stack: dict  # JSON: full technology stack
    status: ProjectStatus = ProjectStatus.ACTIVE
    health_score: float | None  # 0.0 - 100.0
    last_indexed: datetime.datetime | None
    last_scanned: datetime.datetime | None
    created_at: datetime.datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    files: list["ProjectFile"] = Relationship(back_populates="project")
    dependencies: list["Dependency"] = Relationship(back_populates="project")
    security_findings: list["SecurityFinding"] = Relationship(back_populates="project")
    git_commits: list["GitCommit"] = Relationship(back_populates="project")
    test_results: list["TestResult"] = Relationship(back_populates="project")
    build_logs: list["BuildLog"] = Relationship(back_populates="project")
    knowledge_summaries: list["KnowledgeSummary"] = Relationship(back_populates="project")
    portfolio_score: "PortfolioScore" = Relationship(back_populates="project")


class ProjectFile(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    path: str  # Relative path within project
    absolute_path: str
    language: str | None
    size_bytes: int | None
    summary: str | None  # AI-generated summary
    embedding_id: str | None  # FK to ChromaDB embedding ID
    created_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="files")


class Dependency(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    name: str
    version: str | None
    latest_version: str | None
    type: str  # "dev" or "production"
    vulnerable: bool = False
    severity: Severity | None
    created_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="dependencies")


class SecurityFinding(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    type: str  # "vulnerability", "secret", "static_analysis"
    severity: Severity
    title: str
    description: str | None
    ai_explanation: str | None
    file_path: str | None
    line_number: int | None
    cve_id: str | None
    remediation: str | None
    resolved: bool = False
    detected_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="security_findings")


class GitCommit(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    hash: str
    message: str
    author: str | None
    timestamp: datetime.datetime | None
    added_files: list[str] | None  # JSON array
    modified_files: list[str] | None
    deleted_files: list[str] | None
    feature_tags: list[str] | None  # JSON array: auto-categorized features
    created_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="git_commits")


class TestResult(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    run_at: datetime.datetime = Field(default_factory=datetime.utcnow)
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float | None
    framework: str | None
    summary: str | None  # AI-generated analysis
    raw_output: str | None  # Truncated stdout/stderr

    project: Project = Relationship(back_populates="test_results")


class BuildLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    started_at: datetime.datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime.datetime | None
    exit_code: int | None
    success: bool | None
    stdout: str | None  # Truncated
    stderr: str | None  # Truncated
    commands: dict | None  # JSON: install, startup, build, test, deploy

    project: Project = Relationship(back_populates="build_logs")


class KnowledgeSummary(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    type: str  # "architecture", "workflow", "purpose", "stack"
    content: str
    generated_at: datetime.datetime = Field(default_factory=datetime.utcnow)
    model: str | None  # Ollama model used
    confidence: float | None  # 0.0 - 1.0

    project: Project = Relationship(back_populates="knowledge_summaries")


class PortfolioScore(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id", unique=True)
    build_status: str  # "pass", "fail", "pending"
    test_status: str  # "pass", "fail", "pending"
    documentation_pct: int  # 0-100
    security_status: str  # "pass", "warn", "fail"
    screenshots_available: bool = False
    portfolio_score: float  # 0.0 - 100.0
    updated_at: datetime.datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="portfolio_score")


class WorldSimState(SQLModel, table=True):
    """Optional World Simulator state table. Separate from project data."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    day_number: int
    events: dict  # JSON: events that occurred
    nations: dict  # JSON: nation state data
    economy: dict  # JSON: economic state
    updated_at: datetime.datetime = Field(default_factory=datetime.utcnow)


class ConfigEntry(SQLModel, table=True):
    """Application configuration stored in DB."""
    key: str = Field(primary_key=True)
    value: dict  # JSON
    updated_at: datetime.datetime = Field(default_factory=datetime.utcnow)
```

### 1.2. Key Tables Summary

#### projects
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Unique identifier |
| name | TEXT | Project name (derived from directory) |
| path | TEXT | Absolute filesystem path |
| language | TEXT | Primary language detected |
| framework | TEXT | Primary framework detected (nullable) |
| stack | JSON | Full technology stack |
| status | TEXT | "active", "inactive", "error" |
| health_score | REAL | Composite health score (0-100) |
| last_indexed | TIMESTAMP | Last indexing time |
| last_scanned | TIMESTAMP | Last security scan time |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

#### project_files
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| project_id | UUID (FK) | |
| path | TEXT | Relative file path |
| absolute_path | TEXT | Full filesystem path |
| language | TEXT | File language (nullable) |
| size_bytes | INTEGER | File size |
| summary | TEXT | AI-generated summary (nullable) |
| embedding_id | TEXT | ChromaDB embedding reference (nullable) |
| created_at | TIMESTAMP | |

#### security_findings
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| project_id | UUID (FK) | |
| type | TEXT | "vulnerability", "secret", "static_analysis" |
| severity | TEXT | "critical", "high", "medium", "low", "info" |
| title | TEXT | Brief finding description |
| description | TEXT | Detailed explanation |
| ai_explanation | TEXT | AI-generated explanation (nullable) |
| file_path | TEXT | Affected file (nullable) |
| line_number | INTEGER | Line number (nullable) |
| cve_id | TEXT | CVE identifier (nullable) |
| remediation | TEXT | Suggested fix |
| resolved | BOOLEAN | Whether finding is resolved |
| detected_at | TIMESTAMP | |

#### git_commits
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| project_id | UUID (FK) | |
| hash | TEXT | Git commit SHA |
| message | TEXT | Commit message |
| author | TEXT | Commit author |
| timestamp | TIMESTAMP | Commit time |
| added_files | JSON | Array of added file paths |
| modified_files | JSON | Array of modified file paths |
| deleted_files | JSON | Array of deleted file paths |
| feature_tags | JSON | Auto-categorized feature areas |
| created_at | TIMESTAMP | |

---

## 2. API Endpoints

All endpoints live under `http://127.0.0.1:8420/api/v1/`. Relative paths below omit the `/api/v1` prefix; the frontend and CLI always use the full path.

### 2.1. Projects

**GET `/projects/`** â€” List all indexed projects
- Query: `?skip=0&limit=50&status=active`
- Returns: `{"projects": [...], "total": 12}`

**GET `/projects/{id}`** â€” Get project details
- Returns full Project object with stats

**GET `/projects/{id}/files`** â€” List files in a project
- Query: `?language=python&search=main`
- Returns: list of ProjectFile objects

**GET `/projects/{id}/health`** â€” Get project health summary
- Returns: `{"health_score": 92, "build": "pass", "tests": "pass", "security": "pass", "docs_pct": 88}`

**POST `/projects/scan`** â€” Trigger manual re-scan of a project
- Body: `{"project_id": "<uuid>"}`
- Returns: `{"job_id": "SCAN-001", "status": "queued"}`

### 2.2. Indexing

**POST `/indexing/rescan`** â€” Trigger full re-index of all projects
- Returns: `{"job_id": "IDX-001", "status": "started"}`

**GET `/indexing/status/{job_id}`** â€” Check indexing progress
- Returns: `{"status": "processing", "progress": 0.45, "current_file": "main.py"}`

**GET `/indexing/status`** â€” Overall indexing system status
- Returns: `{"last_full_scan": "...", "projects_pending": 3, "projects_done": 10}`

### 2.3. RAG / Intelligence

**POST `/rag/query`** â€” Ask a question about your projects
- Body: `{"question": "Explain the architecture of Workflow Toolkit", "project_id": "optional"}`
- Returns: `{"answer": "...", "sources": [...], "confidence": 0.92}`
- Deterministic tier (v1.17.13): with a `project_id` and an *overview* question (≤ 120
  chars, `_is_overview_question` gate — "what is this project", "tell me about this
  project", "overview", … with no how/where/why/detail markers) the answer is the
  project's stored architecture `KnowledgeSummary` verbatim (preamble stripped) — no
  embedding, no retrieval, no Ollama call; `sources: ["project_summaries"]`, distance 0.0
  → `confidence: 1.0`, `model`/`generated_at` preserved (Rule 7)
- The assistant answer is persisted into the room's `ChatMessage` history server-side
  before returning (project_id or `__all__`, sources, model, confidence) — a tab reload
  mid-generation can no longer lose the reply (v1.17.13; RagChat no longer saves the
  success path client-side)

**POST `/rag/search`** â€” Semantic search across project knowledge
- Body: `{"query": "how does authentication work", "project_id": "optional", "top_k": 5}`
- Returns: `{"results": [{"content": "...", "source": "file_summary", "distance": 0.12}, ...]}

**POST `/rag/index`** â€” Queue knowledge indexing for a project (202)
- Body: `{"project_id": "...", "with_summary": false}`
- Dispatches Celery task `run_index_knowledge`, returning `{"status": "queued", "job_id": "<task_id>"}`
- Default increments embed raw file content/git commits/test/security/build logs; `with_summary: true` additionally generates an Ollama architecture summary persisted to `KnowledgeSummary`

**GET `/rag/index/status`** â€” Index progress (Sprint 15)
- Query: `?project_id=optional` (narrow the report to one project)
- Returns: `{"project_id": null, "projects": {"<project_id>": {"files": N, "embedded": M}}, "files_total": N, "files_embedded": M}` â€” embedded = files with an `embedding_id` set; drives the "X of Y files embedded" line in the Knowledge page

****GET `/projects/{id}/summaries`** â€” Get AI-generated project summaries
- Query: `?type=architecture`
- Returns: list of KnowledgeSummary objects

**GET/POST `/rag/chat/{project_id}` â€” Persisted per-project chat room (v1.17)**
- `GET` returns chat history newest-last (`?limit=`, cap 500); `POST` saves one
  exchange (`role: user|assistant`, `text`, `sources[]`, `model`, `confidence`,
  `error` when the answer failed) â€” the Knowledge chat survives tab switches
  and restarts
- Since v1.17.13 the assistant side of a `/rag/query` is persisted by the query
  handler itself; `POST /rag/chat` remains for user messages and error-path saves
- Module: `app/db/models.py::ChatMessage`, handler `app/api/v1/rag.py`

**GET `/system/activity` â€” Recent activity events (v1.17)**
- Query: `?limit=` (cap 500); returns `{"events": [...]}` newest-first, each
  `{id, kind, message, detail, data, created_at}`
- Kinds: `sync`, `index`, `knowledge`, `build`, `test`, `security`, `ollama`,
  `job`; served from the bounded `activity_event` table (in-memory tail as
  fallback). Same events stream live on `/api/v1/ws/jobs` (`{type: "activity",
  event: {...}}` frames + 30 s heartbeat). Module:
  `app/services/activity_bus.py`

**POST `/system/sync` â€” Manual repo sync (v1.17.1)**
- Body: `{"full": bool}` â€” `full: true` clears the cached repo list and
  re-fetches from GitHub (new repos appear immediately); the default
  `full: false` re-checks the previously known repos by `git pull --ff-only`
- Returns: the same `SyncRun` shape as `GET /system/sync`
  (`{"configured", "started_at", "finished_at", "cloned", "pulled", "failed",
  "message"}`); a 409 is returned when a sync is already running. Runs in a
  worker thread with progress events on the activity feed. Module:
  `app/services/sync_task.py`

### 2.4. Automation

**GET `/automation/jobs`** â€” List scheduled and running jobs
- Returns: list of job status objects

**POST `/automation/trigger`** â€” Trigger a manual automation run
- Body: `{"project_id": "...", "steps": ["build", "test", "scan"]}`
- Returns: `{"job_id": "RUN-001", "status": "queued"}`

**GET `/automation/jobs/{job_id}`** â€” Get job status and logs
- Returns: full job detail with step results

### 2.5. Security

**GET `/security/findings`** â€” List all security findings
- Query: `?project_id=...&severity=high&resolved=false`
- Returns: list of SecurityFinding objects

**GET `/security/findings/{id}`** â€” Get finding details
- Returns: full SecurityFinding with AI explanation

**POST `/security/scan`** â€” Trigger a security scan for a project
- Body: `{"project_id": "..."}`
- Returns: `{"job_id": "SCAN-001", "status": "queued"}`

**POST `/security/scan-all`** â€” Trigger a security scan for every indexed
project (v1.17.7.4; manual twin of the daily `scan-all` beat)
- Returns: `{"job_id": "SCAN-ALL-001", "status": "queued"}`

### 2.6. Git Intelligence

**GET `/projects/{id}/commits`** â€” List commits for a project
- Query: `?limit=50&author=John`
- Returns: paginated list of GitCommit objects

**Note:** the original feature-timeline endpoint here was never built; the
shipped activity timeline lives under Â§2.11 (Observatory), driven by stored
commit/build/test/finding timestamps rather than parsed commit messages.

**GET `/git/features`** â€” Search features across all projects
- Query: `?query=import&project_id=optional`
- Returns: features matched to commits and explanations

### 2.7. Portfolio (Sprint 10)

Deterministic health scoring (30/30/25/15, missing = 0); see Â§14.5 for the
formula and semantics.

**GET `/portfolio/scores`** â€” Health scores for all projects
- Recomputed on read from stored build/test/security/file rows, then persisted
  to the `PortfolioScore` table
- Returns: list of `PortfolioScoreRead` (`build_status`, `test_status`,
  `security_status`, `documentation_pct`, `screenshots_available`,
  `portfolio_score`, `updated_at`)

**GET `/portfolio/best-candidates`** â€” Ranked job-ready projects
- Query: `?min_score=70` (default 70)
- Returns: `[{"project_id", "project_name", "score", "missing": [...]}]` sorted
  by score descending; `missing` lists components with no data yet

**GET `/portfolio/feature-matrix`** â€” Grid of projects Ã— features
- Returns: `{"projects": [...], "features": ["build", "test", "docs", "security", "screenshots"], "matrix": [[...]]}`
- Cells: `âœ“` good Â· `âš ` failing/findings/partial Â· `âœ—` pending; screenshots is
  always `âœ—` until a screenshot feature exists

### 2.8. Local Services

**GET `/services`** â€” List running local services
- Returns: `{"services": [{"name": "ollama", "status": "running", "port": 11434}, ...]}`

**GET `/health`** â€” Overall system health
- Returns: `{"status": "healthy", "services": {...}, "projects_count": 10, "last_index": "..."}`

### 2.9. World Simulator (Sprint 9)

Deterministic "ant farm" module with its own DB; see Â§11 for full details.

**GET `/world-sim/state`** â€” Current world state
- Returns: day, seed, time scale, settlements, roads, recent events, stats

**GET `/world-sim/history`** â€” Event log (ascending)
- Query: `?limit=100&before=<day>`

**GET `/world-sim/settlements/{id}`** â€” Settlement detail (incl. roads)

**POST `/world-sim/tick`** â€” Advance the world now
- Body: `{"days": 3}`; returns `{"days_advanced": 3, "day_number": N}`

**POST `/world-sim/reset`** â€” Wipe and restart
- Body: `{"seed": 7}` (optional); returns `{"status": "reset", "seed": 7}`

**POST `/world-sim/accelerate`** â€” Set days per tick (1â€“10)
- Body: `{"time_scale": 5}`

**POST `/world-sim/disaster`** â€” Force a disaster (god tool)
- Body: `{"settlement_id": "...", "disaster_type": "flood|drought|plague"}`

### 2.10. Configuration

**GET `/config`** â€” Get current configuration
- Returns: full config object

**PUT `/config`** â€” Update configuration
- Body: partial config object
- Returns: updated config

### 2.11. Observatory (Sprint 10.5)

Read-only project overviews, deterministic from stored data (Â§14.6).

**GET `/observatory/galaxy`** â€” Shared-technology graph
- Returns: `{"nodes": [{"id", "kind": "project|tech", "label", "detail", "framework"}], "links": [{"source", "target", "tech"}]}`
- Only technologies used by 2+ projects (`Project.framework` + `Dependency.name`)
  become `tech` nodes; every project is a `project` node linked to each shared tech
- v1.17.9: techs are grouped case-insensitively (label = most common casing);
  same-named projects get their checkout dir as `detail` (e.g. the jamesdileva +
  juduncan `cse455` checkouts)
- v1.17.9.1: `project` nodes carry `framework` (the project's own framework) for
  the focus panel; `tech` nodes leave it null
- v1.17.9.2: payload unchanged â€” the frontend gained two views over it (Metro
  transit map + Families dendrogram/matrix, see Â§14.6)

**GET `/observatory/timeline`** â€” Chronological activity
- Query: `?days=365` (default 365; <1 resets to 365), `&kind=commit,build`
  (comma list of `project-created|commit|build|test|finding`), `&project_id=`,
  `&offset=0&limit=500` (limit 1-1000)
- Returns: `{"events": [{"at", "kind", "project_id", "project_name", "message"}], "has_more": bool}`
- Sources: `Project.created_at`, `GitCommit.timestamp`, `BuildLog.started_at`,
  `TestResult.run_at`, `SecurityFinding.detected_at` â€” all within the window,
  descending. v1.17.9: pages via `offset`/`limit` (`has_more` signals another
  page); a 5000-event safety bound replaces the old per-request 500 cap

**GET `/observatory/architecture/{project_id}`** â€” Component tree
- Returns a recursive node: `{"name", "path", "kind": "dir|file", "count", "children": [...]}`
- Dirs first, then files; `count` = number of files beneath a directory (root = total files)
- 404 if the project is unknown

---

### 2.12. Sessions (v1.17.10)

App-testing session recorder + screenshot capture (later.md Tier 1 + Tier 4;
see Â§14.7). All session state is written by the user's own actions â€” Sentinel
only records (Rule 2: it never presses buttons in the app; Rule 3: log slices
and captures are deterministic, AI never interprets).

**POST `/sessions`** â€” start a session
- Body: `{"project_id", "title", "expected_output"?}`
- Writes `[sentinel] Session started <iso> <session_id>: <title>` into the
  app's own log (`data/logs/apps/<slug>.log` â€” the same file the launched app
  appends its output to)
- Returns: `SessionRead` (id, project_name, status `running`, checkpoints, screenshots)

**POST `/sessions/{id}/checkpoints`** â€” `{"label"}` â†’ appends
`[sentinel] checkpoint: <iso> <session_id>: <label>`; row in `sessioncheckpoint`

**POST `/sessions/{id}/end`** â€” `{"actual_outcome"?, "status": passed|failed|investigate}`
- Appends `[sentinel] Session ended <iso> <session_id>: <status>`, captures the
  deterministic log slice between this session's own start/end markers
  (interleaved sessions slice to their own end marker or EOF), and auto-captures
  a screenshot (Tier 4 â€” every session ends with a record even without a manual
  Capture press)

**POST `/sessions/{id}/screenshots`** â€” `{"checkpoint_id"?}` full-screen grab
(PIL `ImageGrab`) â†’ `data/screenshots/<slug>/<iso>.png` + 90Ã—60 thumb; row in
`sessionscreenshot`

**POST `/sessions/{id}/screenshots/{shot_id}/export`** â€” copies PNG + thumb
into `SENTINEL_PORTFOLIO_DIR` (`images/sessions/`, default
`C:\Users\j\projects\jamesdileva\jamesdileva.github.io`) and returns
`{"copied": [...], "snippet": "<card HTML>"}` â€” the user pastes the snippet
into the portfolio's index.html and pushes manually; Sentinel never pushes

**GET `/sessions?project_id=&status=`** â€” list (newest first); **GET
`/sessions/{id}`** â€” detail with nested checkpoints + screenshots;
**PATCH `/sessions/{id}`** â€” edit title/expected_output/actual_outcome/status;
**DELETE `/sessions/{id}`** â€” removes rows + screenshot files

**GET `/sessions/{id}/screenshots/{filename}`** â€” media route (filename
restricted to `[A-Za-z0-9._-]+`, resolved within the session's screenshot dir â€”
path traversal blocked)

---

## 3. Service Interfaces

### 3.1. IndexerService

File: `backend/app/services/indexer.py`

```python
class IndexerService:
    """Orchestrates repository indexing: language detection, file parsing, dependency analysis."""

    def index_project(self, project_path: str) -> Project:
        """Full index of a single project: detect language, parse files, analyze deps."""

    def scan_all_projects(self, watch_dirs: list[str]) -> list[Project]:
        """Scan all directories for unindexed projects."""

    def reindex_project(self, project_id: str) -> Project:
        """Re-index an existing project (rebuild all derived data)."""

    def detect_language(self, project_path: str) -> str:
        """Detect primary language from file extensions and content."""

    def detect_framework(self, project_path: str) -> str | None:
        """Detect framework from config files and dependencies."""

    def extract_dependencies(self, project_path: str) -> list[Dependency]:
        """Parse lock files and dependency manifests."""
```

**Dependencies:** Parser implementations, DependencyAnalyzer, GitIntelligenceService, IntelligenceService.

---

### 3.2. IntelligenceService

File: `backend/app/services/intelligence_service.py`

```python
class IntelligenceService:
    """Uses Ollama to generate AI summaries and explanations about projects."""

    def generate_project_summary(self, project: Project, summary_type: str) -> KnowledgeSummary:
        """Generate architecture, workflow, purpose, or stack summary via Ollama."""

    def explain_file(self, file_path: str, file_content: str) -> str:
        """Generate AI explanation of what a file does."""

    def analyze_test_failure(self, test_output: str, project: Project) -> str:
        """Analyze why tests failed and suggest fixes."""

    def analyze_build_failure(self, build_output: str, project: Project) -> str:
        """Analyze why a build failed and suggest fixes."""
```

**Dependencies:** OllamaService, ProjectRepository, KnowledgeSummaryRepository.

---

### 3.3. RagService

File: `backend/app/services/rag_service.py`

```python
class RagService:
    """Retrieval-Augmented Generation: semantic search via ChromaDB + Ollama LLM."""

    def query(self, question: str, project_id: str | None = None, top_k: int = 5) -> RagResponse:
        """Answer a question using retrieved context from ChromaDB."""

    def _is_overview_question(self, question: str) -> bool:
        """Deterministic intent gate (v1.17.13, Rule 3): True for short overview
        questions on a specific project — overview markers present, no
        how/where/why/detail markers, ≤ 120 chars. Plain substrings, no AI routing."""

    def _summary_response(self, summary: KnowledgeSummary, question: str) -> RagResponse:
        """Deterministic tier (v1.17.13): the stored architecture summary verbatim
        (preamble stripped), sources [project_summaries], distance 0.0, provenance
        preserved — no Ollama call."""

    def search(self, query: str, project_id: str | None = None, top_k: int = 5) -> list[RagResult]:
        """Semantic search across all stored embeddings."""

    def embed_and_store(self, content: str, metadata: dict, collection: str) -> str:
        """Generate embedding via Ollama and store in ChromaDB."""

    def index_project_files(self, project: Project) -> None:
        """Embed all file summaries and store in ChromaDB."""

    def index_git_commits(self, project: Project) -> None:
        """Embed commit messages and diffs for semantic search."""

    def index_test_results(self, project: Project, test_result: TestResult) -> None:
        """Embed test output for failure analysis via RAG."""
```

**Dependencies:** OllamaService (for embeddings), ProjectRepository, FileRepository.

---

### 3.4. OllamaService

File: `backend/app/services/ollama_service.py`

```python
class OllamaService:
    """HTTP client for Ollama LLM inference server."""

    def generate(self, prompt: str, model: str = "llama3.1:8b", max_tokens: int = 500, temperature: float = 0.3) -> str:
        """Generate text completion."""

    def embed(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """Generate embedding vector for text."""

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""

    def list_models(self) -> list[str]:
        """List available models."""

    def pull_model(self, model: str) -> bool:
        """Download a model from Ollama registry."""
```

**Configuration:** Endpoint (`http://ollama:11434`), model (`llama3.1:8b`), embedding model (`nomic-embed-text`).

---

### 3.5. BuildRunner

File: `backend/app/services/build_runner.py`

```python
class BuildRunner:
    """Discovers and executes build commands for a project."""

    def discover_commands(self, project_path: str) -> dict[str, str]:
        """Detect install, startup, build, test, deploy commands.
        Returns: {"install": "pip install -r requirements.txt",
                  "startup": "uvicorn app.main:app",
                  "build": "npm run dist",
                  "test": "pytest",
                  "deploy": "..."}
        """

    def run_build(self, project: Project) -> BuildLog:
        """Execute build commands, capture output, return log."""

class TestRunner:
    """Discovers and executes test suites for a project."""

    def run_tests(self, project: Project) -> TestResult:
        """Execute test command, parse output, return results."""

    def parse_test_output(self, stdout: str, stderr: str) -> TestParseResult:
        """Parse test framework output into passed/failed/errors/skipped counts."""
```

---

### 3.6. SecurityScanner

File: `backend/app/services/security_scanner.py`

```python
class SecurityScanner:
    """Orchestrates security scanning: secrets + static analysis (deterministic)."""

    def scan_project(self, project: Project) -> list[SecurityFinding]:
        """Run all scanners over the *indexed* file set, return findings."""

    def _iter_scan_files(self, project: Project) -> list[Path]:
        """v1.17.7.5: the indexed `ProjectFile` rows (absolute_path), falling
        back to the indexer's gated walk â€” untracked junk (.venv_sf3d,
        runtime/Lib, release/win-unpacked) is never scanned."""

    def scan_secrets(self, files: list[Path], project_root: Path) -> list[SecurityFinding]:
        """Regex secret patterns (API keys, tokens, .env content) over the file set."""

    def scan_static_analysis(self, files: list[Path], project_root: Path) -> list[SecurityFinding]:
        """v1.17.7.5: AST-based â€” eval/exec/compile flagged only as real
        Call/Name nodes, never string literals or comments (the old regex
        matched its own pattern titles)."""
```

**Tools used:**
- `ast` (stdlib) â€” static analysis for Python (v1.17.7.5: regex patterns replaced)
- Built-in regex patterns â€” secret detection (TruffleHog/Semgrep not vendored)

---

### 3.7. GitIntelligenceService

File: `backend/app/services/git_intelligence.py`

```python
class GitIntelligenceService:
    """Analyzes Git history for commits, features, and project evolution."""

    def analyze_history(self, project_path: str) -> list[GitCommit]:
        """Parse git log, extract commits, files changed, feature tags."""

    def extract_feature_timeline(self, project: Project) -> list[dict]:
        """Create chronological timeline of feature development."""

    def classify_commit(self, commit_message: str, files_changed: list[str]) -> list[str]:
        """Auto-categorize commit into feature tags (using keyword matching + Ollama)."""

    def find_feature_history(self, project: Project, feature_keyword: str) -> list[GitCommit]:
        """Find all commits related to a specific feature."""
```

---

### 3.8. DocGenerator

File: `backend/app/services/doc_generator.py`

```python
class DocGenerator:
    """Automatically generates and updates project documentation."""

    def generate_readme(self, project: Project) -> str:
        """Generate README with project status, setup instructions, commands."""

    def generate_changelog(self, project: Project) -> str:
        """Generate CHANGELOG.md from Git history."""

    def generate_architecture_summary(self, project: Project) -> str:
        """Generate architecture document from file summaries and structure."""

    def update_docs(self, project: Project) -> None:
        """Full doc generation: README + changelog + architecture."""
```

---

### 3.9. ScreenshotGenerator

File: `backend/app/services/screenshot_generator.py`

```python
class ScreenshotGenerator:
    """Generates screenshots of running applications using headless browser."""

    def capture_screenshot(self, url: str, output_path: str, width: int = 1280, height: int = 800) -> str:
        """Capture screenshot of a web app URL using Playwright."""

    def capture_full_page(self, url: str, output_path: str) -> str:
        """Capture full-page screenshot (scrolled)."""

    def capture_element(self, url: str, selector: str, output_path: str) -> str:
        """Capture screenshot of a specific element."""

    def capture_and_upload(self, project: Project, url: str) -> ScreenshotRecord:
        """Capture screenshot and store result."""
```

**Dependencies:** Playwright browser binaries.

---

### 3.10. AutomationEngine

File: `backend/app/services/automation_engine.py`

```python
class AutomationEngine:
    """Orchestrates the full automated maintenance pipeline per project."""

    def run_full_pipeline(self, project: Project, trigger: str = "scheduled") -> AutomationRun:
        """Execute: git_update â†’ install â†’ build â†’ test â†’ scan â†’ docgen â†’ screenshot â†’ health_update."""

    def run_custom_pipeline(self, project: Project, steps: list[str]) -> AutomationRun:
        """Execute only specified steps."""

    def get_pipeline_status(self, run_id: str) -> AutomationRun:
        """Get status of a pipeline run."""
```

**Pipeline steps (Celery tasks):**
- `git_update` â€” pull latest changes
- `install_deps` â€” install project dependencies
- `build` â€” compile/bundle project
- `test` â€” run test suite
- `scan` â€” run security scan
- `generate_docs` â€” generate/update documentation
- `generate_screenshots` â€” capture UI screenshots
- `update_health` â€” recompute health score and portfolio score

---

### 3.11. PortfolioService

File: `backend/app/services/portfolio_service.py`

```python
class PortfolioService:
    """Generates aggregate portfolio scores and candidate rankings."""

    def compute_health_score(self, project: Project) -> float:
        """Compute composite health score (0-100) from build, test, security, docs."""

    def compute_portfolio_score(self, project: Project) -> PortfolioScore:
        """Generate full portfolio score with per-dimension status."""

    def get_best_candidates(self, min_score: float = 80.0) -> list[PortfolioCandidate]:
        """Rank projects by portfolio score, identify missing items."""

    def generate_feature_matrix(self) -> FeatureMatrix:
        """Generate grid of all projects Ã— features (build/test/docs/security/screenshots)."""
```

---

### 3.12. WorldSimulatorService

File: `backend/app/services/world_simulator.py`

```python
class WorldSimulatorService:
    """Optional: persistent AI-generated world simulation. Fully isolated from project data."""

    def advance_day(self) -> WorldSimDay:
        """Advance simulation by one day, generate events."""

    def get_state(self) -> WorldSimState:
        """Get current world state (day, nations, economy, events)."""

    def get_history(self, limit: int = 100) -> list[WorldSimDay]:
        """Get historical simulation days."""

    def reset(self) -> None:
        """Reset world to day 0."""

    def get_events(self, day: int | None = None) -> list[WorldEvent]:
        """Get events for a specific day or all events."""
```

**Isolation guarantees:**
- Separate SQLite database file (`data/world_sim/world.db`)
- Separate ChromaDB collection (`world_sim_entities`)
- Separate Ollama model (`llama3` vs project's `llama3.1:8b`)
- Separate Docker container with CPU/memory limits
- No network access to project services

---

## 4. Configuration

### 4.1. Main Configuration: `config/config.yaml`

```yaml
# Project Sentinel Configuration
server:
  host: "0.0.0.0"
  port: 8420
  workers: 4

database:
  sqlite_path: "/data/sqlite/sentinel.db"

vector_db:
  chroma_path: "/data/chroma"
  embedding_model: "nomic-embed-text"
  collections:
    project_summaries: "project_summaries"
    file_summaries: "file_summaries"
    git_commits: "git_commits"
    test_logs: "test_logs"
    security_reports: "security_reports"
    build_logs: "build_logs"
    world_sim: "world_sim_entities"

ollama:
  host: "http://ollama:11434"
  model: "llama3.1:8b"
  embedding_model: "nomic-embed-text"
  world_sim_model: "llama3"
  timeout_seconds: 120

projects:
  watch_dirs:
    - "C:\\Users\\j"   # User's project root on this machine
  ignore_patterns:
    - ".git/"
    - "__pycache__/"
    - "node_modules/"
    - "*.pyc"

scheduler:
  interval_minutes: 60
  full_scan_hour: "02:00"  # Daily full scan at 2 AM

security:
  api_key: ""  # Optional API key
  secret_scan_patterns:
    - "AWS_ACCESS_KEY_ID"
    - "AWS_SECRET_ACCESS_KEY"
    - "API_KEY"
    - "PASSWORD"

automation:
  default_steps:
    - git_update
    - install_deps
    - build
    - test
    - scan
    - generate_docs
    - generate_screenshots
    - update_health
  timeout_seconds: 3600  # 1 hour per project

world_simulator:
  enabled: false
  cpu_limit: "0.5"
  memory_limit: "512m"
  tick_interval_hours: 24

local_services:
  pi_hole: true
  adguard: false
  enable_dns: true

docker:
  network_name: "sentinel-net"
  profiles:
    - "core"
    - "ollama"
    - "redis"
    - "pihole"
    - "world-sim"  # only when world_simulator.enabled = true
```

### 4.2. Environment Variables

Read from the repo-root `.env` (Sprint 15: no containers â€” the backend process
`Settings` in `app/core/config.py` loads them directly):

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTINEL_HOST` | `127.0.0.1` | Bind address for uvicorn |
| `SENTINEL_PORT` | `8420` | Listen port (dashboard + API, same origin; v1.17.8.1 â€” off 8000, which indexed projects' dev servers default to) |
| `SENTINEL_DB_PATH` | `data/sqlite/sentinel.db` | SQLite database path (repo root) |
| `SENTINEL_CHROMA_PATH` | `data/chroma` | ChromaDB persistence directory |
| `SENTINEL_OLLAMA_HOST` | `http://localhost:11434` | Ollama server endpoint (native Ollama on the same machine) |
| `SENTINEL_OLLAMA_MODEL` | `llama3.1:8b` | LLM model for project AI |
| `SENTINEL_OLLAMA_NUM_CTX` | `32768` | v1.17.6.6: `num_ctx` sent to Ollama for generations (default 2048 would truncate long summary/query inputs) |
| `SENTINEL_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `SENTINEL_WATCH_DIRS` | `<home>` (current user) | Project directories â€” a single directory, a comma-separated list, or a JSON array (v1.17.7.3: the documented comma format used to crash pydantic-settings' JSON-only parser; now accepted). v1.17.7: the discovery walk prunes noise dirs. v1.17.7.3 (this machine): `C:\Users\j\projects` â€” all projects were moved there from the home dir |
| `SENTINEL_AUTO_INDEX_KNOWLEDGE` | `true` | v1.17: after the startup scan, queue RAG indexing for projects with unembedded files (Ollama-gated) |
| `SENTINEL_API_KEY` | (empty) | Optional API key for authentication |
| `SENTINEL_SCHEDULE_INTERVAL` | `60` | Minutes between automation runs |
| `SENTINEL_GITHUB_TOKEN` | (empty) | **Optional** read-only PAT for `repo-sync` (clone/pull from GitHub). Since v1.17.7 the tokenless setup is first-class: local checkouts with a GitHub origin are indexed directly from the watch dirs, and the daily security scan runs on its own beat regardless |
| `SENTINEL_GITHUB_EXCLUDE` | (empty) | v1.17.9.1: **Optional** comma-separated repo list (`owner/repo`, case-insensitive) skipped by `repo-sync` â€” e.g. a repo you cannot delete (collaborator on another account) that must never be re-cloned. Works with or without a token |
| `SENTINEL_SYNC_INTERVAL_MINUTES` | `1440` | Minutes between repo auto-syncs (v1.17.1: every 24 h â€” startup always syncs once, then daily unless the header "Sync now" button is pressed). Only relevant with a token |
| `SENTINEL_SCAN_INTERVAL_MINUTES` | `1440` | v1.17.7: minutes between the security scan-all beat (runs on its own schedule, independent of the GitHub sync â€” tokenless installs still scan daily) |
| `SENTINEL_MAX_FILE_KB` | `5120` | v1.17.7.1: files larger than this (default 5 MB) are skipped by project indexing â€” multi-GB model/binaries (ONNX weights, `.pt` checkpoints, `.dll` bundles) are also blocked by the binary-extension denylist |

---

## 5. CLI

### 5.1. Sentinel CLI

File: `backend/app/cli.py`

```bash
# Main entry point: python -m app.cli <command>

sentinel index <project_path>        # Index a single project
sentinel index --all                 # Index all projects in watch_dirs
sentinel scan <project_id>           # Run security scan on a project
sentinel build <project_id>          # Run build for a project
sentinel test <project_id>           # Run tests for a project
sentinel ask "<question>"            # Ask RAG a question (CLI mode, requires Ollama)
sentinel ask "<question>" --project <project_id> --top-k 5
sentinel rag-index <project_id>      # Index project knowledge into ChromaDB
sentinel rag-index <project_id> --summary   # Force-regenerate the AI architecture summary (v1.17.6.2: auto-index now includes summaries once per project; --summary overrides the dedupe)
sentinel rag-index --reset           # Drop all knowledge collections + clear embedding flags (v1.17.6 recovery; v1.17.6.7: flags are cleared too, so the auto-index actually re-embeds)
sentinel portfolio                   # Show portfolio scores for all projects
sentinel health                      # Show system health status
sentinel world-sim state              # Show current world state
sentinel world-sim tick --days 30     # Advance world by N days
sentinel world-sim reset --seed 7     # Wipe world, optionally new seed
sentinel world-sim accelerate --scale 3  # Set days per tick (1-10)
sentinel world-sim disaster --settlement s0 --type flood  # Force a disaster
sentinel world-sim inspect --settlement s0  # Settlement detail
sentinel config show                 # Show current configuration
sentinel config set <key> <value>    # Update a config value
```

### 5.2. Development Helpers

```bash
# run.py (repo root) â€” the single entry point for the home server
# (commands use the venv python explicitly â€” no activation required)
.\.venv\Scripts\python.exe run.py                          # startup checks + start on 127.0.0.1:8420
.\.venv\Scripts\python.exe run.py --check                  # startup checks only (SQLite, Ollama, frontend)
.\.venv\Scripts\python.exe run.py --port 8080              # different port
.\.venv\Scripts\python.exe run.py --reload                 # dev auto-reload

# scripts/build.py â€” verify + stage the dashboard, no Docker
.\.venv\Scripts\python.exe scripts\build.py                # verify (pytest, lint, npm test) + npm build
.\.venv\Scripts\python.exe scripts\build.py --dist         # also stage frontend into backend/app/static
.\.venv\Scripts\python.exe scripts\build.py --skip-tests   # stage only, no verification

# scripts/release.py
.\.venv\Scripts\python.exe scripts\release.py              # build dist/sentinel-<version>.zip + .sha256
.\.venv\Scripts\python.exe scripts\release.py --dry-run    # print the file plan, write nothing
.\.venv\Scripts\python.exe scripts\release.py --tag        # also create a git tag v<version>
```

---

## 6. RAG Setup

### 6.1. ChromaDB Collections

```
ChromaDB Persistence: /data/chroma

Collections:
â”œâ”€â”€ project_summaries   # AI-generated project architecture/purpose summaries
â”œâ”€â”€ file_summaries      # Per-file AI summaries
â”œâ”€â”€ git_commits         # Commit messages and diffs
â”œâ”€â”€ test_logs           # Test output and failure analysis
â”œâ”€â”€ security_reports    # Security scan results and explanations
â”œâ”€â”€ build_logs          # Build output and failure analysis
â””â”€â”€ world_sim_entities  # World Simulator entity embeddings (optional)
```

### 6.2. Embedding Model

- **Model:** `nomic-embed-text` (Ollama)
- **Embedding dimensions:** 768
- **Distance metric:** Cosine similarity
- **Index type:** HNSW (default in ChromaDB)

### 6.3. RAG Pipeline

```
Step 1: Ingestion
  Project files â†’ File summaries (via Ollama) â†’ Embeddings â†’ ChromaDB (file_summaries)
  Git commits â†’ Commit messages â†’ Embeddings â†’ ChromaDB (git_commits)
  Test results â†’ Test output â†’ Embeddings â†’ ChromaDB (test_logs)
  Security findings â†’ Scan results â†’ Embeddings â†’ ChromaDB (security_reports)

Step 2: Query Processing
  User question â†’ Embedding (nomic-embed-text) â†’ ChromaDB similarity search â†’ Top-K context chunks

Step 3: Answer Generation
  Retrieved context + question â†’ Ollama (llama3.1:8b) â†’ Grounded answer

Step 4: Post-processing
  Answer + source metadata â†’ Frontend display with source links
```

**Chunking (v1.17.6.6):** Markdown/`docs/` files are chunked at 2000 chars
with a 200-char overlap (max 32 chunks per file, ids `{file}#{i}`) â€” most
"How do Iâ€¦" answers live in READMEs and guides. Code files stay single 4k
chunks so structure is never torn apart. Summary generation and all-project
queries read the docs collections first (see Â§6.4 and `_search_all_projects`),
and all Ollama generations use `num_ctx=32768` (Ollama's default 2048 would
truncate long inputs).

### 6.4. RAG Service Configuration

```python
# backend/app/services/rag_service.py

RAG_CONFIG = {
    "embedding_model": "nomic-embed-text",
    "llm_model": "llama3.1:8b",
    "max_context_chunks": 5,
    "min_relevance_score": 0.3,
    "prompt_template": """
You are Project Sentinel's AI assistant. Use the following context from the user's
software projects to answer the question. Provide specific, actionable answers.

Context:
{context}

Question: {question}

Answer:""",
    "temperature": 0.3,
    "max_tokens": 2000,
}
```

### 6.5. Query Types

| Query Type | Collections Used | Description |
|------------|-----------------|-------------|
| Project questions | project_summaries, file_summaries | "Explain the architecture of X" |
| Code questions | file_summaries | "How does authentication work?" |
| Git questions | git_commits | "Why was feature X added?" |
| Test questions | test_logs | "Why did tests fail?" |
| Security questions | security_reports | "What vulnerabilities exist?" |

---

## 7. Automation Jobs

### 7.1. Scheduled Jobs (Celery Beat)

```python
# backend/app/tasks/scheduler.py

CELERY_BEAT_SCHEDULE = {
    # Daily full project scan at 2 AM
    "daily-full-scan": {
        "task": "app.tasks.indexing.scan_all_projects",
        "schedule": crontab(hour=2, minute=0),
    },
    # Hourly health check
    "hourly-health-check": {
        "task": "app.tasks.health.check_system_health",
        "schedule": crontab(minute=0),
    },
    # Every 6 hours: security scan all projects
    "security-scan-all": {
        "task": "app.tasks.security.scan_all_projects",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # World Simulator daily tick (if enabled)
    "world-sim-tick": {
        "task": "app.tasks.world_sim.advance_day",
        "schedule": crontab(hour=3, minute=0),
        "enabled_if": lambda: config.world_simulator.enabled,
    },
}
```

> **Current implementation (v1.17.6.6):** the scheduler is APScheduler-based
> (`services/job_scheduler.py`), not Celery â€” the block above is the original
> design. `_BEAT_IDS` is `("repo-sync", "world-sim-tick")`: there is **no
> standalone security-scan beat** â€” the daily repo-sync runs the security scan
> at the end of its own pass (sync â†’ knowledge index â†’ security scan, whenever
> the sync is configured), so findings always reflect freshly pulled code.

### 7.2. Automation Pipeline Tasks (Celery)

Each task is a separate Celery worker task:

```python
# backend/app/tasks/build_tasks.py
@celery_app.task(bind=True, name="app.tasks.build.git_update")
def git_update(self, project_id: str) -> dict:
    """Pull latest changes from remote."""

@celery_app.task(bind=True, name="app.tasks.build.install_deps")
def install_deps(self, project_id: str) -> dict:
    """Install project dependencies."""

@celery_app.task(bind=True, name="app.tasks.build.build")
def run_build(self, project_id: str) -> dict:
    """Execute build commands."""

@celery_app.task(bind=True, name="app.tasks.build.test")
def run_tests(self, project_id: str) -> dict:
    """Execute test suite."""

@celery_app.task(bind=True, name="app.tasks.build.scan")
def run_scan(self, project_id: str) -> dict:
    """Run security scan."""

@celery_app.task(bind=True, name="app.tasks.build.generate_docs")
def generate_docs(self, project_id: str) -> dict:
    """Generate documentation."""

@celery_app.task(bind=True, name="app.tasks.build.generate_screenshots")
def generate_screenshots(self, project_id: str) -> dict:
    """Capture screenshots."""

@celery_app.task(bind=True, name="app.tasks.build.update_health")
def update_health(self, project_id: str) -> dict:
    """Update project health score and portfolio score."""
```

### 7.3. Pipeline Orchestration

```python
# backend/app/services/automation_engine.py

class AutomationEngine:
    def run_full_pipeline(self, project_id: str, trigger: str = "scheduled"):
        """
        Executes the full pipeline as a Celery chain:

        git_update â†’ install_deps â†’ build â†’ test â†’ scan â†’ generate_docs
        â†’ generate_screenshots â†’ update_health
        """
        chain = (
            git_update.s(project_id) |
            install_deps.s() |
            run_build.s() |
            run_tests.s() |
            run_scan.s() |
            generate_docs.s() |
            generate_screenshots.s() |
            update_health.s()
        )
        result = chain.apply_async()
        return AutomationRun(run_id=result.id, project_id=project_id, status="running")
```

### 7.4. Job Status Tracking

```python
# backend/app/db/models.py

class AutomationRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str
    status: ProjectStatus = ProjectStatus.ACTIVE  # "running", "completed", "failed"
    trigger: str  # "scheduled", "manual"
    started_at: datetime.datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime.datetime | None
    steps: list[dict]  # Step execution details

class AutomationStep(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    run_id: str  # FK â†’ AutomationRun
    name: str  # "git_update", "build", "test", etc.
    status: str  # "pending", "running", "success", "failed"
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    output: str | None  # Link to logs
    error: str | None
```

---

## 8. Parser Implementations

### 8.1. Base Parser Interface

File: `backend/app/parsers/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ParsedFile:
    path: str
    language: str
    content: str
    structure: dict  # AST-like summary: functions, classes, imports
    dependencies: list[str]  # Imported modules/packages

class BaseParser(ABC):
    @abstractmethod
    def parse_file(self, file_path: str) -> ParsedFile: ...

    @abstractmethod
    def supported_languages(self) -> list[str]: ...

    @abstractmethod
    def extract_structure(self, content: str) -> dict: ...
```

### 8.2. Language Parsers

| Parser | File | Parses |
|--------|------|--------|
| PythonParser | `parsers/python_parser.py` | Python (.py) â€” uses AST |
| JavaScriptParser | `parsers/javascript_parser.py` | JavaScript (.js) |
| TypeScriptParser | `parsers/typescript_parser.py` | TypeScript (.ts, .tsx) |
| ReactParser | `parsers/react_parser.py` | React components (.jsx, .tsx) |
| ElectronParser | `parsers/electron_parser.py` | Electron main process |
| FastAPIParser | `parsers/fastapi_parser.py` | FastAPI routes and dependencies |
| FlaskParser | `parsers/flask_parser.py` | Flask routes |
| NodeParser | `parsers/node_parser.py` | Node.js project structure |
| SQLParser | `parsers/sql_parser.py` | SQL schemas and queries |

### 8.3. ReactParser Example

```python
class ReactParser(BaseParser):
    def parse_file(self, file_path: str) -> ParsedFile:
        content = read_file(file_path)
        tree = self._parse_jsx(content)
        return ParsedFile(
            path=file_path,
            language="typescript",
            content=content,
            structure={
                "components": self._extract_components(tree),
                "hooks": self._extract_hooks(tree),
                "imports": self._extract_imports(tree),
                "exports": self._extract_exports(tree),
            },
            dependencies=self._extract_dependencies(tree),
        )

    def supported_languages(self) -> list[str]:
        return ["jsx", "tsx", "react"]

    def extract_structure(self, content: str) -> dict:
        # Uses @babel/parser to parse JSX/TSX
        ...
```

---

## 9. Security Scanning

### 9.1. Scanners

| Scanner | Purpose | Tool |
|---------|---------|------|
| DependencyScanner | Vulnerable dependencies | `pip-audit`, `npm audit`, `safety` |
| SecretScanner | Secrets in source code | `TruffleHog`, `Gitleaks` |
| StaticAnalyzer | Code-level vulnerabilities | `Bandit` (Python), `Semgrep` (multi-language) |

### 9.2. Security Finding Schema

```python
class SecurityFindingCreate(BaseModel):
    type: str  # "vulnerability", "secret", "static_analysis"
    severity: Severity
    title: str
    description: str | None
    file_path: str | None
    line_number: int | None
    cve_id: str | None
    remediation: str | None
```

### 9.3. AI Explanation of Findings

When a finding is detected, Ollama is called to generate a contextual explanation:

```python
def explain_finding(self, finding: SecurityFinding, project_context: str) -> str:
    prompt = f"""
    You are a security expert. Explain this security finding in the context
    of this software project. What does it mean? How should the developer
    fix it? Provide actionable steps.

    Finding: {finding.title}
    Description: {finding.description}
    Severity: {finding.severity}

    Project Context:
    {project_context}
    """
    return self.ollama_service.generate(prompt, model="llama3.1:8b")
```

---

## 10. Screenshot & Testing

### 10.1. Screenshot Generator

Uses Playwright for headless browser automation:

```python
class ScreenshotGenerator:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)

    def capture_screenshot(self, url: str, output_path: str, 
                           width: int = 1280, height: int = 800) -> str:
        page = self.browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=output_path, full_page=True)
        return output_path
```

### 10.2. Feature Testing System

Runs predefined feature tests against known applications:

```python
class FeatureTester:
    """Runs feature tests defined in project config."""

    def run_feature_test(self, project: Project, feature_name: str) -> FeatureTestResult:
        """Execute a defined feature test and capture results."""
        # Load test definition from project's .sentinel/tests/
        test_def = self._load_test_definition(project, feature_name)
        # Execute via Playwright
        result = self._execute_test(test_def)
        # Capture screenshot
        screenshot = self.screenshot_generator.capture_screenshot(test_def.url)
        return FeatureTestResult(
            feature=feature_name,
            passed=result.passed,
            output=result.output,
            screenshot_path=screenshot,
        )
```

Test definitions stored in `project/.sentinel/tests/<feature_name>.json`:

```json
{
    "name": "Smart Formatter",
    "input": "Badly formatted document",
    "steps": [
        {"action": "open", "url": "http://localhost:3000"},
        {"action": "paste", "selector": "#editor-input", "text": "{{input}}"},
        {"action": "click", "selector": "#format-btn"},
        {"action": "verify", "selector": "#editor-output", "contains": "properly formatted"}
    ],
    "capture_screenshot": true
}
```

---

## 11. World Simulator

### 11.1. Architecture

The World Simulator ("the Living World") is a deterministic, persistent
ant-farm style simulation (Sprint 9). It is fully isolated from the project
intelligence pipelines: its own SQLite database, its own engine, and â€” per
Project Rules 2/3 â€” **no generative AI in the simulation loop**. AI is at most
optional flavor on event text and never affects sim state.

The module runs inside the existing stack (no new container): the Celery beat
task `world-sim-tick` advances the world every `world_sim_tick_seconds`, with
bounded catch-up after downtime, and god-tool endpoints allow manual control.

```
backend/app/services/world_sim/
â”œâ”€â”€ rules_engine.py      pure deterministic rules (terrain, food, growth,
â”‚                        construction, expansion, disasters)
â”œâ”€â”€ event_generator.py   simulate_day(): one deterministic day of events
â”œâ”€â”€ skill_system.py      survival experience â†’ skill levels (1â€“5)
â”œâ”€â”€ names.py             seeded settlement-name generation
â””â”€â”€ world_simulator.py   WorldSimulatorService: persistence, catch-up, god tools
frontend/
â”œâ”€â”€ pages/WorldSimulatorPage.tsx   day stats, god tools, event feed
â””â”€â”€ components/WorldGridMap.tsx    2D canvas terrain + settlements + roads
```

Design invariants:

- **Determinism**: all randomness comes from a per-day seeded RNG
  (`seed:day`). Same seed + same tick history = identical world. Terrain is a
  pure function of `(x, y, seed)`; no grid is stored.
- **Isolation**: world tables live in `data/world_sim/world.db` under their
  own SQLAlchemy metadata; `init_db()` never touches them.
- **AI is decorative**: an optional narrator callable may enrich event text,
  but simulation math never depends on it.

### 11.2. World State Database Schema (`data/world_sim/world.db`)

```sql
CREATE TABLE world_sim_state (        -- single row: id="world"
    id TEXT PRIMARY KEY, day INTEGER, seed INTEGER,
    time_scale INTEGER, updated_at TIMESTAMP);

CREATE TABLE world_settlements (      -- one row per settlement
    id TEXT PRIMARY KEY, name TEXT, x INTEGER, y INTEGER,
    population INTEGER, food INTEGER, level INTEGER, experience INTEGER,
    status TEXT,                      -- "active" | "abandoned"
    founded_day INTEGER, destroyed_day INTEGER, parent_id TEXT,
    farmers INTEGER, builders INTEGER, merchants INTEGER,
    explorers INTEGER, construction INTEGER);

CREATE TABLE world_roads (
    id TEXT PRIMARY KEY, from_id TEXT, to_id TEXT, built_day INTEGER);

CREATE TABLE world_events (
    id TEXT PRIMARY KEY, day INTEGER, event_type TEXT, title TEXT,
    narrative TEXT, severity INTEGER,
    affected_settlements JSON, created_at TIMESTAMP);
```

### 11.3. Rules Engine (`app/services/world_sim/rules_engine.py`)

Pure functions over `SettlementState`, tuned by constants (change with tests):

| Constant | Value | Effect |
|---|---|---|
| `EXPAND_POPULATION` | 600 | settlements below this never found children |
| `EXPAND_LEVEL` / `EXPAND_CHANCE` | 3 / 0.25 | level and daily roll required to expand |
| `LEVEL_COST_BASE` | 100 | construction needed = 100 Ã— current level |
| `FARM_CAPACITY` | plains 200 / forest 150 / hills 150 / mts 80 / water 0 | max farmers per type of land (recruitment cap, v1.14) |
| `MAX_FOOD_DAYS` | 20 | food stores capped at `population Ã— 20` â€” bounds the +6% trade growth (v1.14) |
| `MAX_ACTIVE_SETTLEMENTS` | 60 | world stops expanding new settlements at this cap (v1.14) |
| `TRADE_BONUS_FRACTION` | 0.06 | food +6% per day per connected road |
| `DISCOVERY_CHANCE` / `SOCIAL_CHANCE` | 0.04 / 0.03 | per-day event probabilities |
| `RAID_CHANCE` / `RAID_DISTANCE` | 0.02 / 3 | raids between road-connected close settlements |
| `DISASTER_BASE_CHANCE` | flood .015 / drought .010 / plague .008 | Ã— terrain modifier |

Terrain (`terrain_at(x, y, seed)`): mountains/water/hills/forest/plains with
fertility 0.4â€“1.1; daily food = `farmers Ã— 6 Ã— fertility Ã— skill_bonus`.

### 11.4. Daily Simulation (`event_generator.simulate_day`)

Steps per day: (1) food production/growth/famine â†’ (2) construction & level
ups â†’ (2.5) **recruitment** (v1.14: food-secure settlements scale roles with
population â€” farmers `pop//6` (capped by `FARM_CAPACITY`), builders `pop//12`,
merchants `pop//30`, explorers `pop//60`; starving settlements recruit nobody)
â†’ (3) expansion (new settlement + road, blocked at
`MAX_ACTIVE_SETTLEMENTS`) â†’ (4) road trade â†’ (5) raids (road-connected pairs
only, v1.14) â†’ (6) discoveries â†’ (7) social events â†’ (8) disasters (with
survival experience) â†’ (9) collapse check. Returns a `DayOutcome` (events, new
settlements, new roads) for the service to persist.

### 11.5. Skill System (`skill_system.py`)

Surviving a disaster grants `20 + 5 Ã— (severity âˆ’ 1)` experience. Experience
maps to a skill level by tier table (0/50/150/300/500 â†’ levels 1â€“5): +5% food
production and +10% rebuild speed per level beyond the first â€” settlements
"build back stronger". Both bonuses clamp at level 10 (+45% / +90%) so very
long runs stay bounded (v1.14). Deterministic and unit-tested.

### 11.6. Service & God Tools (`world_simulator.py`)

`WorldSimulatorService` owns a dedicated engine and exposes:

| Method | Purpose |
|---|---|
| `ensure_world()` | create the state row + starting settlements on first run |
| `advance_day(days)` | run N days in one transaction, persist events/roads |
| `catch_up()` | advance elapsed real time, bounded by `max_catchup_days` |
| `get_state()` / `get_history()` / `get_settlement(id)` | reads for the UI |
| `reset(seed)` / `set_time_scale(n)` / `trigger_disaster(id, type)` | god tools |

### 11.7. API Endpoints (`/api/v1/world-sim`, enabled by `world_sim_enabled`)

- `GET /world-sim/state` â€” day, seed, time scale, settlements, roads, recent events, stats
- `GET /world-sim/history?limit=100&before=N` â€” event log (ascending)
- `GET /world-sim/settlements/{id}` â€” detail including roads
- `POST /world-sim/tick {days}` â€” advance now (god tool)
- `POST /world-sim/reset {seed}` â€” wipe the world, optionally new seed
- `POST /world-sim/accelerate {time_scale}` â€” days per tick (1â€“10)
- `POST /world-sim/disaster {settlement_id, disaster_type}` â€” flood/drought/plague

### 11.8. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SENTINEL_WORLD_SIM_ENABLED` | true | mount router + beat task |
| `SENTINEL_WORLD_SIM_DB_PATH` | `data/world_sim/world.db` | isolated DB file |
| `SENTINEL_WORLD_SIM_TICK_SECONDS` | 60 | beat interval |
| `SENTINEL_WORLD_SIM_MAX_CATCHUP_DAYS` | 48 | downtime catch-up cap |
| `SENTINEL_WORLD_SIM_TIME_SCALE` | 1 | days advanced per tick |
| `SENTINEL_WORLD_SIM_SEED` | 42 | world seed |
| `SENTINEL_WORLD_SIM_STARTING_SETTLEMENTS` | 2 | initial settlements |
| `SENTINEL_WORLD_SIM_AI_NARRATIVES` | true | optional AI flavor (never sim state) |

---

## 12. Testing Strategy

### 12.1. Backend Tests (pytest)

| Test Module | Focus | Files |
|------------|-------|-------|
| `test_parsers.py` | Language/framework parsers, file parsing | `parsers/base.py`, all `parsers/*.py` |
| `test_services.py` | Intelligence, RAG, build, test, security services | `services/*.py` |
| `test_api.py` | REST API endpoints, response schemas, error handling | `api/v1/*.py` |
| `test_db.py` | Database models, relationships, migrations | `db/models.py` |
| `test_automation.py` | Celery task chains, pipeline orchestration | `tasks/*.py`, `services/automation_engine.py` |
| `test_security.py` | Security scanner integration, finding schemas | `services/security_scanner.py` |
| `test_world_sim.py` | World Simulator isolation, event generation | `services/world_simulator.py` |
| `test_portfolio.py` | Portfolio scoring (30/30/25/15), candidates, matrix, API | `services/portfolio_service.py` |
| `test_observatory.py` | Galaxy shared-tech graph, timeline window/kinds/order/cap, architecture tree, API | `services/observatory_service.py` |
| `test_rag_service.py` | RAG service: indexing, semantic search, grounded query, provenance | `services/rag_service.py`, `services/chroma_manager.py`, `services/ollama_service.py` |
| `test_rag_api.py` | RAG endpoints, knowledge summaries | `api/v1/rag.py` |
| `test_ollama_service.py` | Ollama client: generate/embed, fallbacks, availability | `services/ollama_service.py` |
| `test_git_history.py` | Git log parsing, dedupe, Windows quoting | `services/git_history_service.py` |
| `test_indexer.py` | Repo discovery, indexing, language/framework detection | `services/indexer.py` |
| `test_quality.py` | Quality gates: formatting, lint, coverage | repo-wide |
| `test_packaging.py` | Release archive contents/exclusions, run.py probes, script parsers | `scripts/build.py`, `scripts/release.py`, `run.py` |
| `test_cli.py` | CLI commands (index, ask, rag-index, â€¦) | `app/cli.py` |
| `test_tasks.py` | Celery task registry, job envelope wiring | `tasks/*.py` |
| `test_exceptions.py` | Error handlers and `ApiError` mapping | `core/exceptions.py`, `api/errors.py` |
| `test_health.py` | Health endpoint, DB reachability | `api/v1/health.py` |
| `test_e2e.py` | Full pipeline: index â†’ scan â†’ build â†’ test â†’ docgen â†’ export | All components |

> Sprint 11 result: 211 tests passing, 95.6% coverage (gate â‰¥ 80%), flake8/black/isort clean.

### 12.2. Frontend Tests (Vitest)

Run with `npm test` (watch: `npm run test:watch`, coverage: `npm run test:coverage`).

| Test Module | Focus |
|------------|-------|
| `Dashboard.test.tsx` | Summary stats, error banner + Retry, WS channel status |
| `HealthCard.test.tsx` | Score color bands, status chips, docs "none" state |
| `FeatureMatrix.test.tsx` | Feature columns, symbol colors, empty state |
| `ProjectTimeline.test.tsx` | Event rendering, window selector refetch, error state |
| `ArchitectureMap.test.tsx` | Project list + tree load, selection switch, error state |
| `ProjectGalaxy.test.tsx` | SVG node rendering, project vs tech node sizing, error state |
| `ChatMessage.test.tsx` | User/assistant bubbles, source citations, error styling |
| `RagChat.test.tsx` | Q&A exchange, loading indicator, disabled input, error path |
| `Layout.test.tsx` | Brand + nav, dark-mode toggle, mobile sidebar overlay |

### 12.3. Test Fixtures

Location: `backend/tests/fixtures/`

| File | Purpose |
|------|---------|
| `sample_project.zip` | Complete project archive with nested structure |
| `sample_python_project.tar.gz` | Python + FastAPI project |
| `sample_react_project.tar.gz` | React + TypeScript project |
| `sample_git_history.txt` | Simulated git log output |
| `sample_vulnerable_deps.json` | pip-audit output fixture |
| `sample_secret_detection.json` | TruffleHog output fixture |
| `sample_test_output.txt` | Pytest output for parsing |

### 12.4. E2E Tests (Playwright)

Location: `frontend/tests/e2e/`, config `frontend/playwright.config.ts`.
Run with `cd frontend && npm run test:e2e`.

The suite boots the real stack via Playwright `webServer`: the FastAPI backend
(repo `backend/`, venv `backend/.venv`, real `data/sqlite/sentinel.db`, with
`SENTINEL_AUTO_SCAN_ON_STARTUP=false` so tests see the persisted, deterministic
DB contents instead of racing discovery indexing) plus the Vite dev server
(`--host 127.0.0.1`, `/api` proxied to `:8420`). Ports 8420 and 5173 are reused
when already running.

| Spec | Flow |
|------|------|
| `health.spec.ts` | Backend healthy through the Vite proxy; dashboard renders stats + indexed projects |
| `observatory.spec.ts` | Galaxy graph + shared-tech list, activity timeline, architecture project picker |
| `portfolio.spec.ts` | Health cards with deterministic scores, feature matrix table |

Manual run:

1. Start services: `cd backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app` (+ `cd frontend && npm run dev -- --host 127.0.0.1`), or let Playwright spawn them.
2. Run the suite: `cd frontend && npm run test:e2e`.

Acceptance criteria (Sprint 11, docs/03 Â§753): backend coverage â‰¥ 80%, every API
endpoint integration-tested (200/404/400), frontend unit tests for all
components, E2E covering key user workflows.

---

## 13. Deployment (Native Install)

**Sprint 15 changed the deployment model: Docker Compose is gone.** The project
runs natively â€” one uvicorn process serves the API and the built dashboard from
the same origin (`backend/app/static`), so there is no nginx, no CORS, no
containers, no Redis/Celery (the background scheduler is the in-process
APScheduler). **v1.17.7: the always-on machine is the desktop itself** (dev +
server in one, laptop retired); the dashboard is at `http://127.0.0.1:8420`
(v1.17.8.1 â€” moved off 8000 so indexed projects' dev servers can bind the
uvicorn default; docs/01 Â§9).

Pi-hole also left the Sentinel stack in Sprint 15: it was never the project's
purpose (docs/pi-hole-idea.md) and Sentinel no longer reads its stats â€” the
System page shows Ollama + startup checks only.

### 13.1. Install (one-time)

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into an existing clone + git pull
cd Sentinel
py -3.11 -m venv .venv                                   # backend venv (repo root, or backend\.venv)
.venv\Scripts\python.exe -m pip install -e "backend[dev]"   # runtime + dev deps (sqlmodel, pytest, lint)
cd frontend
npm install
npm run build                          # â†’ frontend/dist
cd ..
.venv\Scripts\python.exe scripts\build.py --dist   # verify (backend+frontend tests, lint) and stage
```

`.env` (gitignored) is optional; defaults are safe (Â§4.2). On a single desktop
**no variables are required**: Ollama runs natively on the same machine
(`http://127.0.0.1:11434`), the watch dirs default to the current user's home
(`C:\Users\j` â€” all local projects are found there), and the GitHub token is
only needed if you want clone/pull auto-sync.

### 13.2. Running

```powershell
# venv python is used explicitly â€” PowerShell will block Activate.ps1 by default
.\.venv\Scripts\python.exe run.py              # startup checks (SQLite, Ollama, frontend built) + uvicorn on 127.0.0.1:8420
.\.venv\Scripts\python.exe run.py --check      # checks only, no server
.\.venv\Scripts\python.exe run.py --port 8080  # or set SENTINEL_PORT in .env
.\.venv\Scripts\python.exe run.py --reload     # dev-only file-watch reload
```

The dashboard is `http://127.0.0.1:8420` (System page: `/system`). The API is
same-origin (`/api/v1/*`) â€” the SPA fallback route in `app/main.py` serves
`index.html` for any non-API path.

> **Note:** the dashboard ships **prebuilt** in the repo (`backend/app/static`,
> committed). A fresh `git pull` is all the machine needs â€” `npm install`,
> `npm run build`, and even `scripts\build.py` are only required when you have
> changed the frontend code yourself.

### 13.3. Autostart (always-on desktop)

There is no autostart task since v1.17.7.2 (it popped console windows every 5
minutes when it respawned the server): `scripts/install_service.py` is deleted
and `run.py` no longer ships `--service`/`--install`/`--uninstall`. Start the
server manually with `run.py` when you want it up.

### 13.4. Home Server Deployment (Sprint 12, reworked in Sprint 15 and 1.17.7)

The desktop is the always-on machine. After the one-time setup (Â§13.1) the
dashboard is at **http://127.0.0.1:8420** on this machine only (localhost â€”
nothing is exposed on the LAN; bind `SENTINEL_HOST=0.0.0.0` + a firewall rule
only if phone/tablet access is ever wanted). `.\.venv\Scripts\python.exe run.py`
performs the same startup checks the server itself performs at boot (database,
chroma, watch dirs, Ollama) and refuses to launch a broken process.

**One-time desktop setup:**

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into the existing clone
cd Sentinel
py -3.11 -m venv .venv                                   # venv lives at backend\.venv on this machine
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
backend\.venv\Scripts\python.exe scripts\build.py --dist
# .env (gitignored) â€” from .env.example; a tokenless install needs NOTHING:
#   (optional) SENTINEL_GITHUB_TOKEN=<read-only PAT>   â†’ enables clone/pull auto-sync
#   (optional) SENTINEL_GITHUB_EXCLUDE=owner/repo     â†’ repos sync must skip (v1.17.9.1)
backend\.venv\Scripts\python.exe run.py                # start the server (no autostart task since v1.17.7.2)
```

**Projects â€” tokenless by default (v1.17.7):**

The machine keeps watch on `SENTINEL_WATCH_DIRS` â€” `C:\Users\j\projects` since
v1.17.7.3 (all project checkouts moved there from the home dir; see
`scripts/migrate_projects_root.py`; the default when unset is still the
current user's home). The startup scan discovers every `.git` checkout and
indexes the *sync-owned* ones: flat direct children with a GitHub origin
(e.g. `C:\Users\j\projects\sentinel`) or `<owner>/<name>`-shaped checkouts
whose origin matches (e.g. `C:\Users\j\projects\jamesdileva\cse455`).
Worktrees, stray copies, nested sub-repos and `.codex`-style junk are never
projects (v1.17.5); since v1.17.7 the
discovery walk prunes noise directories (`AppData`, `OneDrive`, `node_modules`,
`.venv`, â€¦), so the home dir with all its non-project folders is cheap to scan.

With **no token**, GitHub is not contacted at all: the `repo-sync` beat is not
registered, startup reports a one-line INFO, and the header "Sync now" button
answers with a clear message. The **security scan-all still runs daily** â€” it
has its own beat (`SENTINEL_SCAN_INTERVAL_MINUTES`, default 1440; v1.17.7,
previously it rode the repo-sync pass and tokenless installs never scanned).

Optionally, setting `SENTINEL_GITHUB_TOKEN` (read-only PAT, `repo` scope)
restores the Sprint 12.1 flow: the `repo-sync` beat (`SENTINEL_SYNC_INTERVAL_MINUTES`)
clones repos missing from the watch dirs and `git pull --ff-only`s existing
checkouts every 24 h (a sync also runs once at startup; "Sync now" forces one
immediately). Change detection (v1.15) re-indexes only repos whose HEAD moved;
untouched repos skip the scan entirely. Every pass is persisted to `SyncRun`
and `GET /system/sync` shows the last outcome.

Repos that live only locally (no GitHub `origin`) are not projects under Rule 5
(known entities) â€” the origin-URL check in `is_sync_owned` (v1.17.5) filters
them out, so they are never indexed and the project-row GC never touches them
unless a stale row exists.

The machine keeps its own `data/sqlite/sentinel.db` and `data/chroma`; after
first boot the startup scan + auto knowledge-index build the database from the
local projects (`backend\.venv\Scripts\python.exe -m app.cli rag-index --all`
re-runs it manually).

**System page (Sprint 12, Pi-hole removed in Sprint 15):**

`http://127.0.0.1:8420/system` shows read-only status for Ollama
(availability, installed models, tokens/sec of recent generations) plus the
backend startup checks â€” per Project Rule 2 nothing on the page toggles
anything server-side.

**Release artifacts:** `.\.venv\Scripts\python.exe scripts\release.py` produces
`dist/sentinel-<version>.zip` + `.sha256` (run.py, scripts, `.env.example`,
docs, `backend/app` + `pyproject.toml`) â€” copy that archive to another machine
instead of cloning if preferred, then follow Â§13.1 minus `git clone`.

**Troubleshooting:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `run.py` warns *frontend not built* | `backend/app/static/index.html` missing | `.\.venv\Scripts\python.exe scripts\build.py --dist` before serving |
| "What happened this run?" (console scrolled past, errors vanished) | The run's log is at `data/logs/sentinel.log` â€” overwritten at every start, INFO level, includes uvicorn's own loggers (v1.17.6.3). Since v1.17.6.4 the httpx request flood (`POST /api/embed` per embed call) is silenced to WARNING and every line is written exactly once | Read it after a crash: it answers what ran, what errored, and what the shutdown cascade was |
| Dashboard shows stale UI after `git pull` | The served build is the staged one, not `frontend/dist` | Re-run `scripts/build.py --dist`; restart the backend |
| Port 8420 already in use | Another Sentinel instance is running (a second console left open, or an orphaned uvicorn child after a hard kill of `run.py`) | Since v1.17.6.3 `run.py` prints the owning PID (`netstat -ano`) and a `taskkill /F /PID <pid>` hint instead of a raw bind traceback â€” close the other console, kill that PID, or serve elsewhere (`--port 8100` / `SENTINEL_PORT`) |
| Projects indexed but missing the AI architecture summary (files embedded, no summary) | Summary embedding absent â€” wiped by a reset (v1.17.6.2/6.3 dedupe bug) or its generation timed out (v1.17.6.3, 120 s default) | Knowledge page **Re-index all projects** button (v1.17.6.4) or `rag-index --all` â€” incremental: embedded files are skipped, missing summaries regenerate, one bad project never aborts the pass |
| `rag-index` / `sentinel` "not recognized" | The CLI is `python -m app.cli` from inside `backend`, never a bare command (`sentinel` is not on PATH) | `cd backend` then `..\backend\.venv\Scripts\python.exe -m app.cli rag-index --all` (v1.17.7: the venv may live at the repo root OR `backend\.venv` â€” both are resolved) |
| Server dies after reboot | No autostart task since v1.17.7.2 â€” the server is started manually | `backend\.venv\Scripts\python.exe run.py` when you want it up (the old `install_service.py` task was removed because it popped console windows every 5 min) |
| `sentinel sync` â†’ *SENTINEL_GITHUB_TOKEN is not configured* | Token missing in `.env` | Optional since v1.17.7 â€” tokenless installs index local projects directly and scan on their own beat. Set the PAT only if you want clone/pull auto-sync |
| New repos never appear after a push | Sync interval not elapsed | `..\.venv\Scripts\python.exe -m app.cli sync` (from inside `backend`) for an immediate pass |
| RAG chat returns *knowledge index is damaged on disk* (503) | A killed write corrupted the HNSW index (v1.17.6) | Rebuild: Knowledge page banner â†’ "Rebuild knowledge index" (since v1.17.6.2 the probe detects this damage reliably), or `..\.venv\Scripts\python.exe -m app.cli rag-index --reset` from inside `backend`; then restart `run.py` â€” the startup auto-index re-embeds everything, including the AI architecture summary (once per project, v1.17.6.2). Bare `sentinel` is never on PATH â€” always call the venv python by path |

(Pi-hole and Docker troubleshooting from the Sprint 8â€“13 era is archived in the
document changelogs; Pi-hole is no longer part of Sentinel.)
## 14. Data Access Patterns

| Consumer | Source | Access Method |
|----------|--------|---------------|
| Dashboard | Projects, health scores, findings | REST API (`/api/v1/projects`, `/api/v1/health`) |
| Observatory | Project metadata, file summaries, commit history | REST API (`/api/v1/projects/{id}/files`, `/api/v1/projects/{id}/commits`) |
| RAG Assistant | File summaries, commit messages, test logs | ChromaDB vector search + Ollama |
| Knowledge Explorer | File content, code structure, dependencies | REST API + ChromaDB hybrid search |
| Build/Test/Scan | Project commands, dependency manifests | Celery workers â†’ direct filesystem |
| Documentation Generator | File summaries, commit history, metadata | REST API + Ollama |
| Security Scanner | Dependency manifests, source code | Direct filesystem + security tools |
| World Simulator | World state, entity embeddings | Separate SQLite + ChromaDB collection |
| Portfolio | Build/test/security rows, project files | REST API (`/api/v1/portfolio/*`) |

---

## 14.5. Portfolio Intelligence (Sprint 10, scoring refined in Sprint 15)

`PortfolioService` (`backend/app/services/portfolio_service.py`) aggregates each
project's build, test, security and documentation state into a deterministic
0-100 health score â€” no AI, no extra jobs. Scores are recomputed on read and
upserted into the `PortfolioScore` table (docs/02 Â§1), so the API, matrix and
candidates always agree.

**Score formula (weights sum to 100, Sprint 15 static/proven split):**

| Component | Weight | Rule |
|-----------|--------|------|
| build | 30 | `21 static` if a build command was detected in `stack.commands.build` (granted from repo detection alone) + `9` when the latest `BuildLog` actually passed. The static 21 survives a failed run â€” a command does not change because a build failed. No command â†’ 0/pending |
| tests | 30 | `24 static` if conventional test files exist (`tests/`, `__tests__/`, `test_*.py`, `*_test.py`, `*.test.ts(x)`, `*.spec.ts(x)`) + `6` when the latest `TestResult` is green; failed/errored run keeps the static 24. No test files and no run â†’ 0/pending |
| security | 25 | all findings resolved â†’ 25 ("clean"); unresolved deduct per severity (critical 10 / high 6 / medium 3 / low 1 / info 0, floor 0); no findings at all â†’ 0 (never scanned â€” **pending**, distinct from clean since v1.17.6.6) |
| docs | 15 | README/Markdown/`docs/` files Ã· total indexed files Ã— 15 |

A component with no data yet scores **0** â€” projects are never assumed healthy.
`documentation_pct` is the same ratio as a 0-100 integer. `screenshots_available`
is always `False` (no screenshot feature yet; the Feature Matrix screenshots
column stays `âœ—`).

**Never-scanned â‰  clean (v1.17.6.6):** the scanner stamps `Project.last_scanned`
on every pass, so a project with zero findings is **pending** until it has been
scanned at least once and **clean** only afterwards â€” the security cell shows
`âš  pending` vs `âœ“ clean` accordingly. Because the scan now runs chained to the
daily repo-sync (Â§7.1), every project gets its first scan within one sync cycle
(manually: `POST /security/scan?project_id=`, CLI `sentinel scan`).

**Feature Matrix cells** (`âœ“`/`âš `/`âœ—`): build/test â€” passing/failing/pending
(a detected-but-unproven component is `âš ` "configured"); docs â€” **â‰¥50%** /
1-49% / 0% (the 50% green threshold is a Sprint 15 decision); security â€”
clean/findings/pending.

**Caching (Sprint 15):** every read goes through `_fresh_row(project)` â€” if the
stored `PortfolioScore.updated_at` is at least as new as the newest *source*
row the score depends on (build/test/security/file timestamps +
`last_indexed` + `last_scanned` since v1.17.6.6),
the cached row is served as-is; otherwise the score is recomputed and persisted.
Repeated tab loads are therefore instant, and the numbers refresh exactly when
underlying data changes (e.g. after a repo sync pulls new commits). A stat dash:
`summary()` â€” project count, buildable projects (have a build command),
open unresolved findings, average portfolio health â€” served by
`GET /portfolio/summary` (Sprint 15, used by the Dashboard page).

**Endpoints:** `GET /portfolio/scores`, `GET /portfolio/best-candidates?min_score=70`,
`GET /portfolio/feature-matrix`, `GET /portfolio/summary` (see Â§2.7).

**Frontend:** `/portfolio` route (nav item "Portfolio") â€” `pages/Portfolio.tsx`
(health-score grid, best candidates, feature matrix), `components/HealthCard.tsx`,
`components/FeatureMatrix.tsx`, `api/portfolio.ts`. Names are joined from
`GET /projects/`. The Dashboard page shows the summary numbers; the header shows
the last repo-sync pill (see Â§13.4).

**Deferred to Sprint 10.5 (Observatory):** the `ProjectGalaxy` / `ProjectTimeline` /
`ArchitectureMap` components â€” now shipped, see Â§14.6.

---

## 14.6. Observatory (Sprint 10.5)

`ObservatoryService` (`backend/app/services/observatory_service.py`) provides three
read-only, deterministic overviews over already-indexed data â€” no AI, no parsing
at query time.

**Galaxy** `galaxy()` â€” projects become `project` nodes; technologies (a
project's `framework` plus its `Dependency.name` rows) used by **2+ projects**
become `tech` nodes with a `used by N projects` detail. Every project links to
each tech it shares, so the graph shows reuse across the portfolio. v1.17.9:
techs are grouped case-insensitively with the most common casing as the label,
and same-named projects (e.g. the `jamesdileva` + `juduncan` `cse455`
checkouts) carry their checkout dir as `detail`. v1.17.9.1: project nodes
carry `framework` (their own `Project.framework`) for the frontend focus panel.

**Timeline** `timeline(days=365, kinds=None, project_id=None, offset=0,
limit=500)` â€” collects events from `Project.created_at` (`project-created`),
`GitCommit.timestamp` (`commit`, `hash8 message`), `BuildLog.started_at`
(`build`, Build success/failed), `TestResult.run_at` (`test`, N passed / M
failed) and `SecurityFinding.detected_at` (`finding`, `severity: title`),
filters to the trailing window plus optional kind/project filters, sorts
descending, and pages via `offset`/`limit` with a `has_more` flag
(`MAX_TIMELINE_EVENTS = 5000` is a safety bound, not a per-request cap).
Timestamps are stored naive UTC, so the cutoff is computed naive-UTC to match.

**Architecture** `architecture(project_id)` â€” builds a nested tree from indexed
`ProjectFile.path` values (split on `/`, backslashes normalized). Nodes carry
`count` = number of files beneath (each file increments every ancestor + itself),
so root count == total indexed files, leaves == 1. Sorted dirs-first then files.

**Schemas:** `backend/app/schemas/observatory.py` â€” `GalaxyGraph`/`GalaxyNode`/
`GalaxyLink`, `Timeline`/`TimelineEvent`, recursive `ArchitectureNode`
(`model_rebuild()` resolves forward refs).

**Endpoints:** `GET /observatory/galaxy`, `GET /observatory/timeline?days=`,
`GET /observatory/architecture/{id}` (see Â§2.11). Registered in `main.py`
under `api/v1/observatory.py`.

**Frontend:** `/observatory` route (nav item "Observatory") â€”
`pages/Observatory.tsx` hosting the galaxy (v1.17.9.2: segmented
"Metro | Families" toggle) plus `components/ProjectTimeline.tsx` (v1.17.9:
day-grouped headers with per-day counts, kind chips, project filter, Load-more
pagination) and `components/ArchitectureMap.tsx` (v1.17.9: collapsible dirs,
file-type colors, search box, stats header, collapse/expand-all);
`api/observatory.ts` on the shared axios client.

Galaxy views (both deterministic, same `galaxy()` payload, no backend change):
- `MetroView.tsx` â€” shared techs as colored transit lines (top-N slider, default
  15 of 51), projects as stations; stations get x-slots in order of their
  highest-usage line, so interchanges align and stations can never collide.
  Click a station/line to focus or reverse-focus, hover highlights, stations
  draggable with Reset; projects with no visible-line tech become clickable
  "unserved" chips.
- `ClusterView.tsx` â€” Jaccard similarity over shared techs, UPGMA clustering
  with lexicographic tie-breaks (deterministic), dendrogram "family tree" +
  usage matrix; hover highlights row/column, tech labels reverse-focus.
  v1.17.9.3: projects with zero shared techs get an empty tech set before
  clustering (previously a missing map entry crashed the view).
- `FocusPanel.tsx` â€” shared side panel (name, checkout dir, framework, shared
  techs / users), rendered in a fixed-width grid column that never reflows
  (v1.17.9.2: the old flex row rescalled the SVG when the panel mounted â€” the
  flicker fix). The previous `ProjectGalaxy.tsx` was removed.

**Note on scope:** the architecture tree derives exclusively from indexed file
paths â€” it shows where components live, not cross-file imports. "Used by"
relationships aren't persisted, so they're intentionally absent.

---

## 14.7. Sessions (v1.17.10)

`AppSessionService` (`backend/app/services/app_sessions.py`) records
app-testing sessions and captures screenshots (later.md Tier 1 + Tier 4). One
module, one responsibility (Rule 4): it watches and records â€” it never drives
the app (Rule 2), and everything it produces is deterministic (Rule 3).

**Marker protocol** â€” sessions annotate the app's *own* log
(`data/logs/apps/<slug>.log`, same derivation as `build_runner._launch_app`:
`Path(settings.db_path).parent.parent / "logs" / "apps"`), so provenance is a
single file the launched app already writes to:
- `[sentinel] Session started <iso> <session_id>: <title>` (`start()`)
- `[sentinel] checkpoint: <iso> <session_id>: <label>` (`checkpoint()`)
- `[sentinel] Session ended <iso> <session_id>: <status>` (`end()`)

**Log slice** â€” `_slice_for(project, session_id)` reads the log and returns
the lines between the session's own start and end markers (inclusive);
interleaved sessions slice to their own end marker (lines from other sessions
inside the range stay â€” that is what the log contains, and the slice is
byte-for-byte reproducible); an unfinished session slices to EOF. The slice is
captured into `AppSession.log_slice` at `end()`.

**Screenshots** â€” `capture(session_id, checkpoint_id=None)` runs a PIL
full-screen grab (`ImageGrab.grab()`) into
`data/screenshots/<slug>/<iso>.png` with a 90Ã—60 thumbnail
(`<stem>.thumb.png`) next to it (same aspect-constrained size family as the
portfolio's card thumbs). Called on demand and auto at `end()` â€” a failed
auto-shot never loses the session (logged, not raised). Deletion removes the
rows and the PNG + thumb files.

**Portfolio export** â€” `export_to_portfolio(session_id, screenshot_id)`
copies PNG + thumb into `SENTINEL_PORTFOLIO_DIR`'s `images/sessions/`
(default `C:\Users\j\projects\jamesdileva\jamesdileva.github.io`, new env in
`config.py` + `.env.example`) and returns the copied paths plus a ready-made
card HTML snippet matching the site's `.card`/`.images`/`openModal` markup.
Sentinel never pushes (Rule 2) â€” the snippet is for the user to paste and
commit manually.

**Models** â€” `backend/app/db/models.py`: `AppSession` (project FK, title,
expected_output, actual_outcome, `SessionStatus` enum
running/passed/failed/investigate, started_at/ended_at, log_slice) +
`SessionCheckpoint` (session FK, label, at) + `SessionScreenshot` (session FK,
nullable checkpoint FK, path, captured_at).

**Endpoints** â€” `POST/GET/PATCH/DELETE /sessions`, `/sessions/{id}/checkpoints`,
`/sessions/{id}/end`, `/sessions/{id}/screenshots` (+`/{shot}/export`), and the
media route `/sessions/{id}/screenshots/{filename}` (filename whitelist
`[A-Za-z0-9._-]+` + resolve-inside-dir check â€” path traversal blocked). See
Â§2.12. Registered in `main.py`.

**Frontend** â€” `/sessions` nav item + route (`components/nav.ts`,
`routes/index.tsx`), `pages/Sessions.tsx` + `api/sessions.ts`: create dialog,
project + status filters (with per-status counts), expandable session rows
(checkpoint timeline, log slice with `[sentinel]` lines highlighted,
screenshot grid with zoom modal), Capture / Add checkpoint / End (outcome +
status radio) / Delete / Export-to-portfolio (copyable card snippet dialog).

---

## Changelog

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-18 | 1.17.14.4 | **Click-through Phase 2: Electron desktop features (CDP engine).** The features now drive the packaged desktop apps' real windows. Playwright 1.62's python package ships no `p.electron` wrapper (the node driver has electron support, the wrapper does not), so the FeatureRunner launches the packaged exe with `--remote-debugging-port=<free>` + `--user-data-dir=<temp sandbox>`, polls `/json/list`, attaches via `connect_over_cdp` and drives the window with the same Page API - no new dependency. Sandbox is verified, not assumed: the temp dir must gain Chromium profile files AND the app's own state artifact (`tv_scheduler.db`, `data/` dir or `backend.log`) or the run is TesterEnvError; the window URL must be file:// or loopback (Rule 1); the spawned tree is taskkilled on exit. The tester-phase auto-launched instance is reclaimed first (frees TV-Scheduler's hard-coded :3050). `Feature` gains `electron` + `budget_s` (WFT feature: 180 s); `FeatureContext.go()` is refused for electron windows (already on the app). TV-Scheduler: features now drive the packaged window - the interim dev-stack fallback is removed (real TVMaze names never hit the stale asar's broken manual-add path) and the tester is back to the /health probe + window capture. WorkFlow-Toolkit: first electron feature - Projects -> + New Project -> Import Hub (engineered payroll_issues.csv fixture) -> Templates Payroll Audit -> Execute Workflow -> Completed run row -> Reports 'Workflow' report row, all in the sandboxed fresh DB (self-created entities only). Tests: +6 (no-launcher, reclaim-before-launch, sandbox violation, electron go-refused, window-target matching incl. remote-URL refusal, budget override) and the registry gains Workflow-Toolkit; every feature still passes against the fake page. Gate: pytest + black/isort/flake8 green. Plan: docs/clickthrough_plan.md Phase 2 header updated to v1.17.14.4 (CDP engine). Live fixes within v1.17.14.4 (three live E2E rounds on this machine): the WFT run modal stays open after completion and its overlay blocks the sidebar - the feature closes it (scoped .run-modal Close) before navigating to Reports; the packaged app spawns its backend as a separate runtime python, so the reclaim and a new session-end cleanup kill the whole tree (taskkill /T - previously the orphaned backend held ports/state for the next run, and two stale exe instances piled up over failed rounds); the tester's wait_log('Uvicorn running') timed out on a healthy backend (the app log is shared with the auto-launched window's stdout and uvicorn's file output is block-buffered) - the readiness check is now a polling HTTP probe of /health (Rule 3); the sandbox removal retries within 10 s because the killed Chromium processes release their leveldb locks a beat after taskkill (single immediate rmtree left the sandbox userData behind). Tests: +2 sandbox-removal tests; the 107-test suite + full gate stay green; both apps' live runs pass end-to-end (TV-Scheduler 16/16, WorkFlow-Toolkit 39/39) against the sandboxed windows with real screenshots, real userData untouched. |
| 2026-08-19 | 1.17.15.0 | **Round 3: app coverage for the last two tester-less projects (docs/clickthrough_plan.md).** ALGO-TRADER tester + first browser feature: backtester.exe CLI smoke (argc<3 usage path — exit 1 + usage text; real runs DELETE from backtest.db tables via resetBacktestState and need historical data, so they are excluded — replaced by a REAL run 2026-08-19: `backtester.exe 2026-07-01 2026-07-24`, bars confirmed in backtest.db so it is fully local with no Alpaca calls, resetBacktestState rewrites only the app's own backtest.db copy while algo_trader.db is untouched, asserted on the `=== BACKTEST COMPLETE ===` marker + exit 0), Flask dashboard on :5000 (no venv in the repo — the launch command's `python` passes through un-rewritten to the system Python, Flask 3.1.3), http probes on / (ALGO TRADER), /api/account (latest snapshot), /api/orders/recent, /api/trades (read-only local SQLite reads; the dashboard's own JS fires /api/positions/live at Alpaca's paper API on load — the app's own read-only behavior, never asserted, no credentials carried, Rule 1), then a headless dashboard render; the feature waits for the loadAll() "Updated:" marker (set only after every fetch resolves, incl. the <=5 s Alpaca call) and asserts the equity stat populated + orders table rows. trader.exe excluded (live trading loop reading config/settings.json keys — not deterministic, Rule 3). HFT-Order-Book presence tester: launches build/hft.exe (native SDL2 + OpenGL + Dear ImGui simulator — self-contained, synthesizes market data, no network), waits for its window (exe-path matched by find_project_window; launcher_detect does not scan native build/ exes, so the tester launches it directly), independently verifies the capture has real content (>=8 gray levels; blank OpenGL PrintWindow renders fall back to a screen crop in the capture layer), and records the window capture; no click-through — Dear ImGui exposes no accessibility tree (Phase 3 chunk 2, gated). Registries + their exactness tests updated (testers + features). Plan: clickthrough_plan.md gains Round 3 + the chunked Phase 3 (pywinauto UIA engine for AG's tkinter GUI, gated HFT input scripting). |
| 2026-08-18 | 1.17.14.3 | **TV-Scheduler scroll-exploration fix (user review).** The dashboard-scroll feature used to scroll immediately after load, before the TVMaze-proxied schedule fetch settled — the page was short, `scrollTo` did nothing, and the screenshot showed an unloaded schedule. It now waits for a loaded episode row (`//section[.//h3]//div[.//button='Save to My Shows']`, 45 s — the 3-column grid only renders when `!loading && !error`), then scrolls and proves the scroll actually happened (`scrollY > 0`, honest fail when content fits without scrolling). Popular Shows side-scroll unchanged (worked). Pattern reusable for future apps (and Phase 2 Electron): wait for data-render markers before asserting scroll. Gate: coverage 90%+, lint clean. |
| 2026-08-18 | 1.17.14.2 | **Click-through expansion round (user review).** Cg's feature now walks the full studio: Dashboard topic generation (Standard, count stat) -> Topics tab -> Approve a Pending Review card -> Run Research (asserts the RESEARCHING transition — the background scrape job is network-bound, completion is not asserted) -> Research tab confirms the topic in `#topic-select`. TV-Scheduler: the add-show feature uses a REAL TVMaze-resolvable name (candidate list, skipping any show already saved — the app blocks dupes by design) instead of a gibberish string; a new dashboard-exploration feature scrolls to the 3-day Episode Schedule and side-scrolls the Popular Shows row (both TVMaze-proxied — honest fail when TVMaze is down); the search feature filters a real-name substring. Locator ground truth hardened: My Shows rows are scoped to the `+ Add Show` section so Popular Shows cards can never match the row locators. Sessions responsive polish (resized-window overflow): session rows wrap (the date no longer runs off the page), detail-grid columns and the screenshot grid get min-w-0 + break-words (1280px-wide shots no longer blow the grid's min-content width), the zoom modal is object-contain, and the status-filter buttons wrap. Gate: 90.64% coverage, 128 frontend tests, black/isort/flake8 clean. |
| 2026-08-18 | 1.17.14.1 | **Click-through live-verify round: all five features green against real apps, plus real bug catches.** Locator fixes from live runs: dinner menu's theme toggle label does not re-render on click (`toggleTheme` writes `#root[data-theme]` directly, no React state change) — the feature now locates the button by its stable `title="Toggle dark / light"` and asserts the data-theme attribute round-trips (starts and ends in the same theme); Card-Game's balance is `💰` in `div.text-xl.font-bold.mb-2` (scan said `💵`/`font-bold`); Cg's stats are `<span class="stat-value">` (scan said div); TV-Scheduler's row locator needed `./strong` (direct child) not `.//strong` (matched 29 ancestor divs). Dinner-menu tester: Flask probe races cold boots (first live run: 22 s boot vs 8 s wait) — replaced the fixed wait with `retries=4`. TV-Scheduler tester: the feature phase drives the dev UI (localhost:5173, App.jsx hardcodes API_BASE_URL 127.0.0.1:3050) — after the packaged-app /health probe and window screenshot, the tester taskkills the auto-launched instance and runs the current dev stack (server.js on :3050 + vite on :5173). The feature proved the packaged app's add-show path is broken: `manual-<ts>` is a TEXT id inserted into the INTEGER PRIMARY KEY watchlist.showId (SQLITE_MISMATCH 500), and /show-details returned 200-with-undefined on a TVMaze 404 so the UI never fell back — repo fixes applied to TV-Scheduler (uncommitted, user's call): honest 404 from show-details + numeric Date.now() fallback id. Live results: Dinner Menu 13/13 (incl. add+delete meal, theme toggle), TV-Scheduler 16/16 (add+delete show, search filter), Card-Game 12/12 (throwaway register + login + daily collect + spin, balance $1,100 -> $1,000), Cg 14/14 (Standard generate, Total Topics stat rendered), Demake 16/16 (UI upload leaves INITIALIZING -> ANALYZING) — every feature screenshot real (>=159 gray levels). CG's first run failed honestly when WorkFlow-Toolkit's leftover backend held :8000 (EADDRINUSE -> investigate). |
| 2026-08-18 | 1.17.14.0 | **Click-through engine (Playwright): scripted UI features for all five DOM apps.** New `app/testers/features/` package - one module per app (dinner menu: add+delete a self-created meal, theme toggle; TV-Scheduler: add+delete a self-created show, search filter; Card-Game: throwaway `tester-*` account register + login, collect daily popup, one $100 spin with a balance delta; Cg: generate 2 mock topics via the Standard button, assert the Pipeline Status stat; Demake: pick the repo's own fixture in the drop zone and prove the upload button enables and the pipeline leaves INITIALIZING). `FeatureRunner` (`services/feature_runner.py`) drives them in headless Edge (msedge channel) under a 120 s budget with a loopback-only guard (Rule 1: remote URLs refused) and error mapping (Playwright errors -> TesterAssertionError/failed, launch failure -> TesterEnvError/investigate); every feature records checkpoints and screenshots via the TesterContext. Runs after each tester's scripted steps through the existing `Run tester` endpoint - no new UI, no new schedule, user-initiated only (Rule 2). Feature descriptors surface on the tester GET endpoints. Unit tests drive every feature against a fake page (no browser in CI) incl. the loopback guard, blank-shot rejection and budget enforcement; 90.68% coverage. Playwright added to `pyproject.toml`. Plan: `docs/clickthrough_plan.md` (Phase 2 = Electron sandbox, v1.17.14.1). |
| 2026-08-17 | 1.17.13.7 | **Dinner menu's first-ever live run — and a vite 8 IPv6 fix.** Tester run #1 failed with `WinError 10061` on `http://127.0.0.1:5173` even though vite logged `ready`: vite 8 binds loopback as IPv6-only (`::1`) — `localhost` resolves and serves, `127.0.0.1` is refused (Card-Game's tester already used `localhost`; dinner menu's constant did not). The tester now probes `http://localhost:5173` (Flask on :5000 stays `127.0.0.1` — IPv4 by default). Verified live: `http GET http://localhost:5173 -> 200`, `http GET http://127.0.0.1:5000 -> 200`, then the v1.17.13.5 auto-render fired — `headless dashboard render` checkpoint with a real dashboard shot (1280x800, 242 gray levels) and zero per-tester code. Build->open also verified: ports freed, vite + Flask relaunched, `App opened: http://localhost:5173` (success: True). First session in dinner menu's history. |
| 2026-08-17 | 1.17.13.6 | **TV-Scheduler tester rewritten for the auto-launched packaged app.** First live run of 1.17.13.5 failed at `GET http://127.0.0.1:3050 -> 404` — two real bugs in the tester, not the app. (1) The old tester launched the dev stack via `concurrently`, which is not on PATH (and would have collided with the packaged app's backend on :3050 — EADDRINUSE); (2) it asserted `GET /` but the Express server serves only the API + `/health` — the frontend is loaded by Electron from app.asar (`loadFile`), so there is no static root route and `GET /` is 404 by design (the 2026-08-15 ground-truth note was wrong). The tester now probes `GET /health` (retries while the server binds) against the auto-launched packaged app and screenshots the window. Verified live: `auto-launched packaged app: TV Scheduler.exe` -> `/health -> 200` -> 3 window captures (1600x1000, 231-256 gray levels). The packaged app's `DB backup failed ... app.asar` error is a cosmetic read-only-asar quirk (non-fatal, app keeps serving). |
| 2026-08-17 | 1.17.13.5 | **Generic app presence: testers auto-launch the packaged app and auto-capture its window; browser apps get an auto dashboard render.** Live-review gap (WFT/TV-Scheduler sessions since v1.17.13.2): capture is window-targeted now, but every tester had to code its own launch + capture — WFT's tester never launched the UI, so its runs recorded nothing even though a real app existed (`release/win-unpacked/WorkFlow Toolkit.exe`). (1) **`launcher_detect.py`** (new, deterministic path scan): finds a project's packaged app binary — electron-builder `release/win-unpacked` (WFT) and `dist/win-unpacked` (TV-Scheduler), tauri `out/` and `src-tauri/target/release` (future; Sentinel is the only tauri app, deferred) — excluding installers (`Setup*`, `*.blockmap`), `elevate.exe`, bundled pythons. PyInstaller `backend/dist` (dinner menu) is deliberately NOT scanned: payload names are ambiguous and browser capture covers those apps. (2) **`TesterRunner` auto-launch**: before a tester runs, the packaged app is launched detached and its window (polled up to 20 s) is captured with a labeled checkpoint — desktop apps record their real UI with zero per-tester code; no launcher or no window is an honest skip, never a failure. `Tester.auto_launch` (default True) opts out. Affected projects: WorkFlow-Toolkit + TV-Scheduler only (CG has no packaged exe, AG's tkinter GUI keeps its own launch, browser apps find nothing). (3) **Auto-render**: a tester that declared `web_url` but registered no screenshots gets one headless render of it after the run — dinner menu's first-ever run captures its dashboard with no per-tester line (card-game/demake render themselves; deduped). Deferred (documented decision): the click-through engine — driving UI features (buttons, forms) and screenshotting each step — needs Playwright (browser) / UIA (desktop); REST/CLI feature testing + static captures remain the deterministic path (Rules 2+3). Candidate v1.17.14. Tests: +11 (12 detector-matrix cases incl. PyInstaller exclusion, auto-launch launch+capture, no-window skip, opt-out, launch-failure, auto-render when empty, dedupe when tester rendered, no-web_url no-op). |
| 2026-08-16 | 1.17.13.4 | **Build & Open actually opens browser-served apps.** Live UX report: Card-Game's "Open app" was green but opened nothing visible — the launch ran the stored startup (frontend-only) detached and stopped; no browser window, and with the tester's leftovers still on :5173/:3000 the new vite drifted to :5174 (orphan, nobody knows the URL). (1) **`Tester` gains app facts for build->open**: `web_url` (browser-served apps), `extra_launch` (servers the stored startup does not cover), `ports` (restart semantics). Populated: Card-Game `http://localhost:5173` + `cd backend && node server.js` + `(5173, 3000)`; Dinner-Menu-Generator `http://localhost:5173` + `cd backend && python app.py` + `(5173, 5000)`; Demake-Engine `http://localhost:8000` + `(8000,)`; Electron/desktop testers unchanged (no web_url — they open their own window). (2) **`BuildRunner` build->open flow**: before launching, listeners on the declared ports are killed (`netstat -ano` → `taskkill /F`, no new deps) so the opened instance is always the current code and never an orphan on a drift port; then the stored startup plus each extra server launch detached into `<slug>.log`; then the default browser opens the web_url (`os.startfile`) — all user-initiated via the Run Build / Open app click; beats never launch anything (Rule 2). The BuildLog records every step ("Freed ports for restart: …", "App launched: …", "App opened: …"). Tests: +3 build_runner — ports freed + extras launched + browser opened (drift port never killed); no listeners → still launches and opens; desktop app → no ports freed, no browser — with netstat/taskkill/startfile faked, nothing real spawned. |
| 2026-08-16 | 1.17.13.3 | **Card-Game backend migrated off PostgreSQL to local better-sqlite3 (app-side work, driven from Sentinel).** The app's `DATABASE_URL` pointed at a dead Supabase pooler endpoint — its Express server always crashed on first query, so the tester could never pass the backend check. Working in the Card-Game repo: (1) `backend/db.js` is now a better-sqlite3 singleton (`backend/cardgame.db`, gitignored, WAL, `foreign_keys=ON`) that self-provisions from the new `backend/schema.sql` on first open — fresh clones need no manual init; (2) the `connect-pg-simple` session store is replaced by a ~40-line custom SQLite store (`backend/sessionStore.js`, table `session(sid, sess, expire)`), drop-in compatible with express-session; (3) all 38 `pool.query` sites in `authRoutes.js`/`gameRoutes.js` converted to prepared `?` statements (`.get()`/`.all()`/`.run()`; `RETURNING` and `ON CONFLICT … excluded` verified working in SQLite); a latent `db.query` ReferenceError in `/buy-upgrade` was fixed along the way; (4) the 2026-04-06 PostgreSQL dumps migrated to git-tracked `backend/schema.sql` + `seed.sql` (`npm run db:init`, `INSERT OR IGNORE`, data verified id-for-id: 9 users / 70 inventory / 27 deck); `DATABASE_URL` deleted from `backend/.env`, the old `.sql` dumps deleted from the tree, `cardgame.db*` gitignored; (5) live-verified end to end against the real app: GET / 200, register→login roundtrip (daily-reward streak + balance update), `/api/game/state` with migrated account data, spin, open-crate (RETURNING), set-deck upsert + LEFT-JOIN deck read, add-balance — all on SQLite with zero errors; the frontend production build passes. The app now runs fully local with no cloud dependency, and its tester passes: Card-Game smoke PASSED live with a headless dashboard render. Tester-side change: `card_game.py` docstring/description ground truth updated to the SQLite architecture. |
| 2026-08-16 | 1.17.13.2 | **No desktop-grab fallback; headless dashboard captures for browser apps.** Live-verify verdict after demake runs: a real app is window-capturable (Electron/tkinter/native) or browser-served (registered via headless renders) — grabbing whatever the user has on screen (Reddit + VS Code mid-run) is noise. (1) **`AppSessionService.capture()`** no longer falls back to `ImageGrab.grab()` of the desktop: a session whose app owns no window returns None and records nothing (skip logged); the end-of-session auto-capture skips windowless sessions too. `POST /api/v1/sessions/{id}/screenshots` answers **409** with a pointer to the tester-render path (the Sessions UI toasts the detail). (2) **`TesterContext.render_and_register(url, label)`** — generalized capture path for browser-served apps: headless-render the URL in invisible Edge, assert the frame non-blank (PIL gray-level histogram, deterministic; blank → `TesterAssertionError`, Edge failure → `TesterEnvError`), register it via `screenshot_file()`; temp PNG cleaned up. Demake tester now registers the upload dashboard (`/`) + the generated game (`game.html?id=…`); Card-Game tester registers its Vite frontend first screen — first-time live run of that tester. Tests: +3 backend (ctx render_and_register renders+registers+cleans up, blank frame → assert, render failure → env) +1 API (windowless capture → 409); full-screen-fallback tests reworked to skip/window semantics. (3) **Card-Game first live runs failed — Vite v8 binds `localhost` on IPv6 (`::1:5173`) here, the tester hardcoded `127.0.0.1:5173` → refused** (the apparent 8.9 s 'boot race' in the first run was a red herring; retries in run two kept hitting the wrong address). The tester now targets `http://localhost:5173`, which resolves to whatever the dev server actually binds. (4) **`ctx.http()` gains `retries`/`retry_delay_s`** — dev servers can take ~10 s to bind after launch; unreachable errors re-attempt and only the successful attempt checkpoints. Tests: +2 (retry succeeds after failures; retries exhausted → TesterEnvError).  (5) **Card-Game's backend check failed honestly** — the app's `DATABASE_URL` (dotenvx in `backend/.env`) points at a cloud Postgres host that no longer resolves (ENOTFOUND — dead/expired endpoint); the Express server prints "Server running on 3000" then dies on the first pool query (Node ≥22 fatal unhandled rejection), so the session ends investigate with the real error in the app log. App-side fix (point `DATABASE_URL` at local PG :5432 and provision the schema, or delete the tester) is user work, not tester work. | AI agent |
| 2026-08-16 | 1.17.13.1 | **Headless game captures for browser-served apps.** Live-verify follow-up: the Demake E2E tester runs headless (FastAPI + HTTP polls, no window), so its end-of-session auto-capture grabbed the user’s desktop (full-screen fallback) instead of the game — a portfolio dead end. (1) **`utils/headless_render.py`** — `render_url()` renders a URL in headless Microsoft Edge (`--headless=new --screenshot --window-size=1280,800 --virtual-time-budget=15000`), deterministic and desktop-independent; Edge resolves via known install paths → PATH; failures raise `HeadlessRenderError` (bounded subprocess timeout). (2) **`AppSessionService.register_screenshot()`** — registers a pre-rendered PNG into `data/screenshots/<slug>/` (copies PNG + 90×60 thumb, inserts the `SessionScreenshot` row, method logged `headless-render`); shared save tail extracted from `capture()`. (3) **`TesterContext.screenshot_file()`** — mirrors `screenshot()` for pre-rendered files. (4) The Demake tester now renders `game.html?id=<demake_id>&api=…` after the asset check and asserts the frame is non-blank (PIL gray-level histogram, deterministic), so a WebGL blank frame fails the tester honestly; the auto end-of-session desktop grab remains as a second shot. Pattern generalizes to any browser-served app (Sentinel’s own dashboard later; WFT’s Electron shell gets a window-targeted capture like Cg). Tests: +10 backend (render_url success/non-zero/missing-browser/timeout/no-output, find_edge known-path/PATH/missing, register_screenshot row+thumb+missing source, ctx screenshot_file). | AI agent |
| 2026-08-16 | 1.17.13.0 | **Deterministic-first RAG tier + server-persisted chat answers.** Trigger: a live data-loss incident — a tab reload mid-generation aborted the in-flight `/rag/query` fetch; the server finished the 174.5 s Ollama call (287 tokens, llama3.1:8b, `ollamaquerylog`) and delivered the answer to a dead connection (no access-log line, never rendered), leaving only the user row in the room. (1) **Deterministic summary tier (Rule 3)** — with a `project_id` and an overview question, `query()` answers from the project's stored architecture `KnowledgeSummary`: no embedding, no retrieval, no Ollama call. Intent gate `_is_overview_question()`: ≤ 120 chars, an `_OVERVIEW_MARKERS` substring ("what is this project", "tell me about this project", "overview", …) and no `_SPECIFIC_MARKERS` ("how do", "why does", "error", "test", "build", "api endpoint", …) — specific questions still flow to retrieval + LLM. The summary is returned verbatim with its "Here is a concise architecture summary…" preamble stripped, `sources: ["project_summaries"]`, distance 0.0 → `confidence: 1.0`, `model` + `generated_at` preserved (Rule 7 provenance). (2) **Server-side answer persistence** — `POST /rag/query` now saves the assistant reply into the room's `ChatMessage` history (project_id or `__all__`, sources, model, confidence) before returning, so a reload mid-generation can no longer lose an answer; RagChat dropped its client-side success-path save (user + error-path saves remain). (3) **Validation-body logging** — the incident's unexplained 422 had an unlogged body; a `RequestValidationError` handler now logs the rejected body (first 2000 chars) for `/rag/chat` + `/rag/query` so a recurrence is diagnosable. Forensics aside: a double-spawned zombie uvicorn (no listening port, same DB/Chroma) was killed; DB-local timestamps are UTC+7 vs the UTC log, established for future correlation. Tests: +6 backend (intent gate, stored-summary answer, fall-through without summary, assistant row persisted, overview answered from stored summary, 422 body logged), +2 frontend (answer saved server-side only); 517 backend / 128 frontend green; black/isort/flake8 clean. Live-verify follow-up: the Cg tester no longer double-starts the repo's own backend (`npm run start` = concurrently `run.py` + electron; run.py exited on the tester's port-8000 bind and `concurrently -k` killed the whole tree, so the Electron window never opened and its "window" screenshot silently fell back to full-screen). The tester now launches `electron-dev` only, with a 45 s cold-boot wait; window-targeted capture verified live (1400×900 window-render, in-test + end-of-session; PrintWindow handled Chromium compositing without a blank frame). Demake-side: the E2E tester's final asset fetch 404’d because demake-engine’s sprite cache-hit path returned the old run’s file without copying it into the current run’s `sprites/` (game UI would 404 too); fixed in demake-engine (`shutil.copy2` on the cache-hit branch) and tester re-verified green. | AI agent |
| 2026-08-15 | 1.17.10.0 | **Sessions (Tier 1 recorder) + Tier 4 screenshot capture.** Backend: three new tables â€” `AppSession` (project FK, status enum running/passed/failed/investigate, expected/actual, started/ended, `log_slice`), `SessionCheckpoint` (session FK, label, at), `SessionScreenshot` (session FK, nullable checkpoint FK, path, captured_at). `services/app_sessions.py` (one module, Rule 4) annotates the app's *own* log (`data/logs/apps/<slug>.log`, same derivation as `build_runner`) with `[sentinel] Session started|checkpoint:|Session ended <iso> <id>: ...` markers and captures the deterministic log slice between a session's own markers (interleaved sessions slice to their own end marker or EOF; byte-for-byte reproducible). Screenshots: PIL `ImageGrab.grab()` full-screen grabs + 90Ã—60 thumbs under `data/screenshots/<slug>/`, on demand or auto at session end (Rule 2 â€” capture, never act); delete removes rows + PNG/thumb files. Portfolio export: copies PNG + thumb into `SENTINEL_PORTFOLIO_DIR` (`images/sessions/`, default `C:\Users\j\projects\jamesdileva\jamesdileva.github.io`; new env in config.py + `.env.example`) and returns a ready-made card HTML snippet matching the site's `.card`/`openModal` markup â€” Sentinel never pushes, the user pastes and commits manually. API: `POST/GET/PATCH/DELETE /api/v1/sessions`, `POST .../checkpoints`, `POST .../end`, `POST .../screenshots` (+`/{shot_id}/export`), media route `GET .../screenshots/{filename}` (filename whitelist + resolve-inside-dir guard â€” traversal blocked). Dependency: `pillow>=10.0` in pyproject. Frontend: `/sessions` nav item + route, `pages/Sessions.tsx` + `api/sessions.ts` â€” create dialog, project + status filters (per-status counts), expandable rows (checkpoints timeline, log slice with `[sentinel]` lines highlighted, screenshot grid + zoom modal), Capture / Add checkpoint / End (outcome + status) / Delete / Export-to-portfolio (copyable snippet dialog). Docs: 01 Â§9 data dirs + changelog, 02 Â§2.12 + Â§14.7 + changelog, 03 changelog, later.md Tiers 1 + 4 marked done (2-3 renumbered), .env.example, AGENTS.md env list. Tests: +16 backend (CRUD, marker-slice boundaries incl. interleaved sessions, checkpoint ordering, capture files + thumb, auto-capture on end, delete cleans files, export copy + snippet, traversal guard, full API flow), +12 frontend (list/badges, project + status filters, expand detail, create, checkpoint, capture, end, export snippet dialog, delete, zoom modal). Backend 449 / frontend 120 green; black/isort/flake8 + prettier clean. | AI agent |
| 2026-08-15 | 1.17.11.0 | **Scripted testers (later.md Tier 2, docs/tier2_plan.md).** Backend: `app/testers/` â€” per-app deterministic Python testers (Rule 3: substring/status/exit-code matchers only; Rule 2: manual "Run tester" button only). `_helpers.py` TesterContext (launch/http/cli/pytest/wait_log/wait/checkpoint/screenshot; bounded timeouts; raises TesterAssertionError â†’ session `failed`, TesterEnvError/TesterTimeoutError â†’ `investigate`; `cli` appends `[tester]` lines to the app log, never env values â€” tested); `__init__.py` Tester dataclass + registry (project slug â†’ tester, circular-safe submodule imports) + `DEFAULT_SMOKE` (launch â†’ wait â†’ scan for `Traceback|FATAL ERROR|Cannot find module` â†’ screenshot) for launchable apps without a custom tester; custom testers: Cg (mock-LLM backend + watches the renderer's broken `/api/pipeline/jobs/` call in the app log + Electron + 46-test pytest suite), Ag (static CLI asserts GLTF file; `animate` step is red â€” AG main.py:283 NameError, evidence in the session log; opencv-python-headless installed into `.venv_sf3d`), Demake Engine (upload trailer â†’ poll status â†’ manifest â†’ asset, structural asserts), Tv-Scheduler, Workflow-Toolkit, Card-Game, Dinner-Menu-Generator. Live-fix round (2026-08-15): AG main.py root_motion NameError fixed in the AG repo (added oot_motion param, wired from the CLI) — tester green; Demake non-cp1252 prints (→/✓/✗ in demake.py, orchestrator, sprite_gen, validator, vlm_analysis) replaced with ASCII — the upload/pipeline no longer crash under Sentinel's redirected stdout; Demake tester now uses the manifest's absolute asset URL and allows 7 min for the slow SD/ONNX sprite path. Ground-truth revocations (honest "No tester", descriptor 404): Mlbattles, Hft-Order-Book, Algo-Trader, Python-Projects. `services/tester_runner.py` (resolve/describe/run â€” auto-creates `Tester: <name>` session, auto screenshot + status), `tasks/tester_tasks.py` (job-pool task, activity_bus "tester" event), `job_scheduler` registry + `run_tester`, `schemas/tester.py`, API `GET /api/v1/testers/{project_id}` + `POST /api/v1/testers/run` (202 JobEnvelope), `build_runner._launch_app` gained an `env` overlay (tester launches; backward compatible). Frontend: Builds page "Run tester" button (descriptor-aware; disabled "No tester"; run â†’ session-result card with status tone + View session link; polls sessions for the post-click `Tester:` session), `api/testers.ts`. Docs: tier2_plan.md (Phase B ground-truth revision), later.md Tier 2 â†’ DONE, changelogs 01/02/03. Bugfix: log-slice read tolerates non-UTF-8 app-log bytes (cp1252 child output) — end() no longer crashes with UnicodeDecodeError leaving sessions 'running' (regression test added; live catch: Demake's upload print of U+2192 under redirected stdout). Tests: +21 backend (registry, resolve, context helpers incl. timeout + env redaction, runner statuses, API descriptor/404/JobEnvelope with inline runner), +6 frontend (button states, run flow, passed/failed result tones); 470 backend / 124 frontend green; black/isort/flake8 (max-line 100) clean. | AI agent |
| 2026-08-15 | 1.17.12.0 | **Error triage (later.md Tier 3, docs/tier3_plan.md) + WorkFlow-Toolkit flagship tester.** Tier 3 reframed deterministic-first: `POST /api/v1/sessions/{id}/triage` builds a zero-AI evidence packet (verbatim error lines from the session log slice, traceback frames resolved to project files with source previews read from disk, known-pattern labels, honest no-traceback note); new `TriageAnalysis` table (evidence JSON + optional summary/model/timestamp provenance, Rule 7, cascade-deleted with the session). Optional `POST /api/v1/sessions/{id}/summarize` = one small local-LLM call (llama3.1:8b, max_tokens 150, num_ctx 4096 for speed, purpose "triage-summary") describing the evidence only - no causes, no fixes, no decisions (Rules 2+3); 503 when Ollama is down, the deterministic card still renders. OllamaService gained an optional `num_ctx` param. Frontend: Sessions page "Triage failure" + evidence card (error lines, pattern chips, culprit source line highlighted) + "AI summary" with provenance line. Workflow-Toolkit tester upgraded to payroll-audit E2E (bundled runtime python launch, payroll_issues.csv import, validation asserts, PDF report + download, "Payroll Audit" template execute + poll to Completed). Docs: tier3_plan.md, later.md Tier 3 -> DONE, changelogs 01/02/03. Tests: +21 backend triage, +2 tester, +4 frontend; 490 backend / 128 frontend green. | AI agent |
| 2026-08-16 | 1.17.12.1 | **Triage + tester live-verify fixes (first live run of v1.17.12.0).** (a) Tester children inherited Sentinel's own `PYTHONPATH` (run.py sets it), so uvicorn imported Sentinel's `app` package instead of the WFT one (sqlmodel ModuleNotFoundError red herring) — the WFT tester's launch now overlays `PYTHONPATH=""` (regression test). (b) WFT reports URL needed a trailing slash (`/api/reports/` — Starlette 307 otherwise). (c) Triage frame cap moved AFTER resolution: uvicorn tracebacks lead with 8+ site-packages frames, so the old pre-resolution cap starved the project frames that follow (live: the WFT 500 evidence had zero resolved frames). Frames are now scanned uncapped, resolved, deduped (chained-exception duplicates), then capped at 8; `<string>`/`<frozen>` pseudo-frames skipped; `OperationalError`/`Unhandled error` added to hint + pattern detection (the verbatim `sqlite3.OperationalError: table workflow_runs has no column named output_report_id` line now lands in the packet). Live-verified end to end on 127.0.0.1:8420: WFT payroll E2E passed 12/12 checkpoints; triage on the failed WFT session resolves `backend/app/api/workflows.py:126` + `workflow_run_repository.py:48` with source previews; summarize 503s gracefully when Ollama is down and returns a provenance-stamped llama3.1:8b paragraph when up. Also found + fixed (WFT repo, uncommitted — user's call): `workflow_runs` missing `output_report_id` (model has it, initial alembic migration is a stub) — new migration `4e6a9c2d8f31` (SQLite batch mode). Tests: +3 backend (uncapped scan, chained dedupe, pseudo-frame skip); 493 backend / 128 frontend green; build gate passed; black/isort/flake8 clean. | AI agent |
| 2026-08-16 | 1.17.12.3 | **Window-targeted screenshots: app windows instead of the whole desktop.** Screenshot capture (manual Capture button, tester ctx.screenshot, auto end-of-session) now finds the app under test's own top-level window and crops the grab to it. New module app/utils/window_capture.py (stdlib ctypes only): EnumWindows + GetWindowThreadProcessId + QueryFullProcessImageNameW matching the window process's executable path or a bounded ancestor chain (casefold prefix; largest visible, non-minimized, non-zero-area window wins; never title matching). capture() in app_sessions.py renders the window's own content via PrintWindow (PW_RENDERFULLCONTENT) - an occluded window captures its own content, never what's stacked above it (no focus stealing, no z-order changes; Rule 2); blank frames (some GPU-composited windows, >99% black check) and rects outside the virtual screen fall back to a screen crop of the clamped rect; headless apps (WFT, Demake) and closed/minimized windows fall back to the full-screen grab unchanged. Occlusion live-proved: Notepad parked over the AG window - render luma identical with and without. Honest limitation documented: some GPU-composited windows still blank-frame, in which case the crop fallback applies. Live bug: AG's tkinter GUI is re-executed by its venv python into the base interpreter, so the window's own exe lives under AppData \u2014 the match walks up to 6 ancestors (Toolhelp snapshot) and still finds the venv python under the project dir (regression-tested). Tests: +12 backend (window find: clamp math, ancestor-chain match, re-executed ancestor, bounded depth, snapshot failure; render: DC failure, PrintWindow failure, blank-frame reject, render success, black-frame detect, bbox passed, crop fallback, full-screen fallback, virtual-screen bounds); 511 backend / 128 frontend green. | AI agent |
| 2026-08-16 | 1.17.12.2 | **WFT tester extended to the full toolkit (all 4 templates) + pytest env fix.** WorkFlow-Toolkit E2E (renamed from payroll E2E) now covers every workflow template the app ships, all driven by engineered fixtures in `backend/tests/fixtures/`: Payroll Audit (validation + PDF), Data Quality Review (`customers_dupes.csv`), Dataset Comparison (`customers_v1` + `customers_v2` via `second_dataset_id`), Dashboard Builder (`sales_orders.csv` -> Excel download asserted as `spreadsheetml.sheet`). Each run is polled to Completed with `output_report_id` asserted, and its report is downloaded + content-type checked. New final step runs the repo's own pytest suite (838 tests) through the bundled runtime python. Bugfix found live: the pytest child inherited Sentinel's `PYTHONPATH` the same way the uvicorn child did (v1.17.12.1 fixed only the launch) — `app` resolved to Sentinel's package and collection died with `No module named 'app.productivity'`. `TesterContext.pytest()` gained an `env` overlay param (passes through to `cli()`, which redacts env values from logs); the WFT tester passes `PYTHONPATH=""`. Tester helpers refactored (`_interpreter`, `_import_dataset`, `_resolve_template`, `_execute_template`, `_poll_run`, `_assert_completed_with_report`, `_assert_report_download`). Live-verified on 127.0.0.1:8420: 29/29 checkpoints passed (incl. 838 pytest tests + auto screenshot). Tests: +3 backend (tester name, pytest command, pytest env passthrough, completed-run assert); 496 backend / 128 frontend green; build gate passed. | AI agent |
| 2026-08-15 | 1.17.9.3 | **Galaxy Families hotfix: island projects crashed the clustering view.** `ClusterView` built its project->tech map only from graph links, so a project with zero shared techs (e.g. the 8 idea repos with no dependencies) had no entry; `clusterProjects` then called `jaccard(undefined, ...)` -> `TypeError: can't access property Symbol.iterator` on switching Metro -> Families. Fix: seed an empty tech set for every project before clustering (`derived` memo in `ClusterView.tsx`). Regression test added (island project renders with zero cells next to a linked project). Tests: 108 frontend green, backend untouched (433). | AI agent |
| 2026-08-15 | 1.17.9.2 | **Galaxy rework: Metro + Families views.** Frontend-only redesign of the Observatory galaxy, motivated by the two-column graph's overlap and flicker (the focus panel used to sit in the same flex row as the SVG, so mounting it rescaled the whole graph). Metro view (`MetroView.tsx`): shared techs become colored transit lines (top-N slider, default 15 of 51, line labels show usage), projects become stations that get x-slots in order of their highest-usage line - interchanges align vertically and stations can never collide; click a station or a line to focus/reverse-focus, hover highlights, stations stay draggable with Reset, projects with no visible-line tech become clickable 'unserved' chips. Families view (`ClusterView.tsx`): Jaccard similarity over shared techs + UPGMA clustering with lexicographic tie-breaks (deterministic) -> dendrogram family tree on top of a usage matrix; hover highlights row + column, tech labels reverse-focus their projects. Both views reuse the extracted `FocusPanel.tsx` (name, checkout dir, framework, shared techs / users) rendered in a fixed-width grid column that never reflows. Old `ProjectGalaxy.tsx` removed. Tests: +16 frontend (10 metro: rails/slider/interchange/alignment/hover/reverse-focus/drag/unserved/tooltips; 6 families: rows/cells, leaf-order clustering, row-col highlight, focus panel, reverse focus, single-project), suite 107 green; backend untouched (433 green). | AI agent |
| 2026-08-14 | 1.17.9.1 | **Galaxy interactive pass + repo cleanup + sync exclusion.** Frontend Galaxy (`ProjectGalaxy.tsx`): fixed two-column layout (projects in the left gutter, techs right) with end-anchored project labels and a text halo, curved quadratic-bezier links, tech nodes as rotated diamonds, hover highlight (neighbors dim, unpinned), click-to-pin focus panel (project detail, framework, shared-tech chips, or the tech's usage list, plus clear button), drag-to-reposition with Reset layout (clamped to the viewBox; islands stay dim). Backend: `GalaxyNode.framework` added and populated by `galaxy()` so the panel shows each project's framework. Repo sync: new `SENTINEL_GITHUB_EXCLUDE` (comma-separated, `config.py` validator + `remote_repos()` case-insensitive filter, 2 tests) - `juduncan/cse455` is excluded because the repo still exists upstream (collaborator account, cannot delete); with both local checkouts gone the restart GC removed the Cse455 rows. Housekeeping: 8 new idea repos pushed to GitHub (resmaker, betsim, coach, manvsmachine, nexus, surfhop, whoareyou, worldsim; public), MM received its architecture doc (repo was empty), Card-Game's one-branch README/package-lock divergence merged (pull --rebase + push), duplicate checkouts deleted (projects\jamesdileva\MM, \utilitytool). Tests: +3 backend (exclusion x2, galaxy framework x1), frontend galaxy suite rewritten for the new shapes: 13 tests (+5 net; gutter anchor, hover dim, drag + reset, tech reverse-focus, focus panel with framework, diamond/curved-link selectors). | AI agent |
| 2026-08-14 | 1.17.9.0 | **Observatory v2 UI pass + galaxy data fix.** Backend ? dependency extraction (`indexer.extract_dependencies`) now discovers manifests below the project root (git-tracked, bounded depth 2, noise-pruned) so projects with backend//renderer// manifests stop reporting zero deps (Sentinel/Cg/Ag went 0 -> 15-25 each; fastapi now shared by 3, uvicorn 3, react 2+), and names are case-canonicalized (most common casing wins ? `Flask` + `flask` merge). Galaxy groups techs case-insensitively with the most common casing as label and disambiguates same-named projects (Cse455 x2 -> detail = checkout dir). Timeline gained `kind` (comma list), `project_id`, and `offset`/`limit` pagination with `has_more` (old hard 500 cap per-request became a 5000 safety bound). Frontend ? Galaxy: click a project to focus its links + techs and dim the rest, zero-link projects render as dim islands, tech labels moved inside the viewBox, tech list sorted by usage count, tooltip detail for duplicate names. Timeline: day-grouped headers with per-day counts (no more endless scroll), kind chips + project filter, Load-more pagination. Architecture Map: collapsible dirs, file-type colors, search box, stats header (files/dirs/top-level chips), collapse-all/expand-all. Tests: +10 backend (subdir manifests, noise pruning, case canonicalization, galaxy grouping + disambiguation, timeline kind/project filters, pagination, API params), +8 frontend (day groups, chips, load more, galaxy focus/dimming/sorting/detail, collapse/search/stats). | AI agent |
| 2026-08-14 | 1.17.8.2 | **App-launch logging fixed ? the app tree's own output now actually lands in `data/logs/apps/<slug>.log`.** The launch used `DETACHED_PROCESS`, which on Windows makes cmd.exe spawn external children (npm, python, node) with invalid stdout/stderr handles ? so the launched apps' logs silently vanished and only the `[sentinel]` launch marker landed (probed flag combinations: direct children were fine, every cmd-spawned child lost output even on natural exit). `build_runner._launch_app` now uses `CREATE_NEW_PROCESS_GROUP` alone, which captures the whole chain; the app tree attaches to Sentinel's hidden console, which is harmless. Tests: +1 real-process integration test (startup command prints, asserts the child's line appears in the app log ? regression-guarded, fails under DETACHED_PROCESS). | AI agent |
| 2026-08-14 | 1.17.8.1 | **Sentinel moves to port 8420.** The uvicorn default 8000 is what the indexed projects' dev servers (Cg, Demake Engine) bind, so build-to-open launches died on WinError 10013 while Sentinel held the port. `SENTINEL_PORT` default is now 8420 (config.py, run.py --port, .env.example, vite proxy, playwright e2e, packaging test) ? Cg and Demake dev servers now bind 8000 freely. Docs: README, AGENTS.md, desktop.md, 01 ?9/?10, 02 ?4.2/?13, 03 updated. Tests: packaging default-port assert. | AI agent |
| 2026-08-14 | 1.17.8.0 | **Subdir-aware command discovery; buildâ†’open.** (1) **Discovery finds builds one level down** (command_extractor.py): known subdirs renderer/frontend/client/web/ui/dashboard â†’ `cd <dir> && npm install`/`npm run build`/`npm run start|dev`/`npm run test` from their package.json; backend/server/api requirements.txt â†’ `cd <dir> && pip install -r requirements.txt` (root manifests still win per family; commands run from the project root via the shell runner). Python entry modules with an argparse `gui`/`web` subcommand are launchable apps by *code*, not prose (AG: `python -m rigging_engine.main gui` â€” master_reference2.md's command, now deterministic); a FastAPI entry that documents `uvicorn main:app` gets it as startup (demake: `cd backend && uvicorn main:app --reload`); DEVELOPMENT.md/docs/DEVELOPMENT.md join the README candidates; docs now also yield startup commands (whitelisted spellings only); `_venv_python` accepts a plain `venv/` dir (CG, demake) and the `backend/tests/` pytest convention runs `cd backend && "<venv python>" -m pytest` (CG; deterministic conventions now run *before* the doc scan â€” CG's README documents a `npm run test` that doesn't exist, the real suite is backend pytest in `venv/`). Live discovery: AG = startup gui CLI + venv pytest (399 collected; 1 cv2 env-gap collection error, documented in AG's AGENTS.md); CG = build/startup/install/test all real; demake = uvicorn startup + root pip. (2) **buildâ†’open** (build_runner.py): Run Build becomes Build & Open for every project â€” a green build, or a project with no compile step ("Build not needed â€” this project has no compile step."), launches the `startup` command **detached** (DETACHED_PROCESS, no command timeout â€” the app keeps running) appending to `data/logs/apps/<name>.log`, through the repo's own venv interpreter when it has one (`python`-prefixed commands rewritten to the venv exe; backslash-safe lambda replace). A failed build never opens the app; neither-build-nor-startup stays the honest v1.17.7.5 skipped record. New `BuildLog.launch_command` (ALTER migration via connection.py) surfaced in BuildLogRead/JobStatus; Builds.tsx action label adapts to the discovered commands (Build & Open / Open app / Build / Run build), the log shows an "App launched: â€¦" line, and the completion toast notes the launch. Launch is always user-initiated (Rule 2: beats never open apps). Docs: AGENTS.md rules honored â€” changelog rows in 01/02/03, builds.md recipe table refreshed (AG/CG/Demake/Sentinel rows + buildâ†’open note). Tests: +13 extractor (subdir npm/pip, root-wins, CLI gui/web, entry uvicorn, DEVELOPMENT.md, startup-from-docs, subdir pytest, plain venv, venv-qualified cd-pytest, prose-ignored), +5 runner (no-build launches, venv rewrite, no-launch-on-failure, launch-after-success, launch-failure honesty), +4 frontend (labels + log line + toast); suite green | AI agent |
| 2026-08-14 | 1.17.7.7 | **Live UI updates for scans and builds; resolved findings are cleanable; AG finally testable.** (1) **Builds poll race fixed** (Builds.tsx): `finish()` cleared `pollingJobId` *before* the awaited history refresh, so the effect cleanup flipped `cancelled` and dropped both the refreshed list and the toast - the row stayed "running..." forever on a real network; the refresh + toast now run first, then the poll state clears (regression test with a slow history fetch). (2) **Security tab refreshes on completion** (Security.tsx): after queueing a scan/scan-all the tab polls `GET /projects/{id}` every 2 s until `last_scanned` moves past the pre-scan snapshot (stamped by the scanner on every run - the only deterministic completion signal, since a clean scan writes no finding row), then refetches findings + toasts. Scan buttons show "Scanning..." while the poll is live (10-min cap). (3) **Resolved findings cleanable**: every stale leftover is `resolved=True` forever (Ag 209, WT 183, Sentinel 7, others 1-2 - all false positives from the pre-v1.17.7.5 scanner) and spammed the observatory timeline (~400 events). New `DELETE /api/v1/security/findings?project_id=` removes *resolved* rows only (SecurityRepository.delete_resolved, open findings untouched - they are the live scan state and the idempotence keys); the tab defaults to open findings with a "Show resolved" toggle + "Clear resolved (N)" button; the timeline now filters `resolved == False`. (4) **AG gets a test command**: AG's root has no manifest (requirements live in stable-fast-3d//triposr/ subdirs; AGENTS.md is a session log with zero command literals), so discovery honestly found nothing. Two deterministic additions (command_extractor.py): `AGENTS.md`/`docs/AGENTS.md` join the README candidates but are scanned for fenced code blocks only (Sentinel's own AGENTS.md mentions "pytest in backend/" mid-sentence - a whole-file scan would mint a wrong command), and a pytest convention extractor (last in order): a root `tests/` dir + at least one root-level `.py` file yields `test: pytest`. Empty extractor results no longer claim keys (an earlier extractor that found nothing must not block a later confident one - the AGENTS.md scan returned `test: ""` and shadowed the convention). AG now discovers test: pytest; its build step stays honestly skipped (interpreted Python app - nothing compiles). Docs: 01/02/03 changelogs. Tests: +4 backend (DELETE API x3, repo delete_resolved, timeline excludes resolved, extractor: AGENTS.md fenced, AGENTS.md prose ignored, pytest convention x2) +5 frontend (Security poll/toggle/clear x5, Builds slow-refresh regression) | AI agent |
| 2026-08-14 | 1.17.7.6 | **World tab removed from the sidebar.** The world simulator is opt-in since v1.17.7.3 (SENTINEL_WORLD_SIM_ENABLED=true); with it off, the World nav item loaded a page that 404s on every API call. 
av.ts drops the World entry and 
outes/index.tsx drops the route, so a stale /world link falls through to the Dashboard catch-all; WorldSimulatorPage/WorldGridMap/world_sim.ts stay in place for a future re-enable (re-add the nav line + route) | AI agent |
| 2026-08-14 | 1.17.7.6 | **C++/CMake build discovery + builds.md recipe reference.** (1) **CMake extractor** (command_extractor.py _from_cmake, ordered before the README scan): a root CMakeLists.txt yields uild: cmake --build build ï¿½ the canonical invocation that reuses the cached generator (Algo Trader and HFT-Order-Book are configured with MinGW Makefiles, so it drives mingw32-make in uild/) and re-runs configure automatically when CMakeLists.txt changes; 	est: ctest --test-dir build only when enable_testing()/dd_test appears. Blast radius is exactly the two CMake repos in the projects root. (2) **Stale-stack fallback** (uild_runner.py): a stored stack.commands.build that is empty no longer short-circuits to *skipped* ï¿½ the runner re-discovers at build time (same runtime-fallback pattern as the portfolio matrix), so extractor improvements apply without re-indexing. (3) **docs/builds.md**: versioned recipe reference for all 21 projects (install/build/test/startup per project, discovered commands only) + a C++ deep-dive ï¿½ Algo Trader: configure once cmake -S . -B build -G "MinGW Makefiles", build via cmake --build build, outputs uild\trader.exe + uild\backtester.exe; acktester is a separate strategy-testing executable *within* the repo, not its own project; data lives in config/settings.json/data\algo_trader.db. HFT-Order-Book: same CMake layout (cpp-httplib vendored). Doc is indexed by the knowledge system and security-scanned, so it stays free of credential-like literals. Docs: 01/02/03 changelogs, builds.md. Tests: +3 parametrized extractor cases (CMakeLists alone, +enable_testing, +dd_test) and +1 runner fallback test (stale empty stack re-discovers cmake --build build) | AI agent |
| 2026-08-14 | 1.17.7.5 | **Index-gated security scans (no more false positives); honest no-command builds; README build discovery.** (1) **Scanner scans what the index indexes** (`security_scanner.py`): the project walk used the indexer's `_iter_source_files` directly, so untracked junk got flagged â€” live run showed AG with 208 eval/exec findings in `.venv_sf3d\Lib\site-packages`, WorkFlow-Toolkit 174 in the untracked `backend\runtime\python\Lib` stdlib + `release\win-unpacked\` outputs, and Sentinel flagging itself (3 findings: regex titles "Use of eval()"/"Use of exec()" as *string literals* matched by the old regex `_STATIC_PATTERNS`, and a comment example placeholder token (the alphabetical `ghp_`-prefixed sample) caught by the Generic Secret). Fix: `_iter_scan_files` reads the indexed `ProjectFile` rows (`absolute_path`; fallback = the same gated walk), and static analysis is now **AST-based** â€” `eval`/`exec`/`compile` are flagged only as real `Call`/`Name` nodes, never inside strings or comments; the placeholder comment no longer contains a literal GitHub token. Expected live effect after the re-scan: AG 209â†’1, WT 183â†’0, Sentinel 3â†’0. (2) **"No build command" is now an honest *skipped*** (`build_runner.py`): no discoverable command used to record `success=True, exit_code=0` and feed "Build passed" â€” it now records `success=None, exit_code=None` ("No build command configured for this project."), the feed says "Build skipped", `JobStatus` gains the `skipped` literal (was: the old code mapped `success=None` â†’ "failed"), and `Builds.tsx` labels completed null-success logs "skipped" (was "running"). Portfolio: the static 21 build points still require a command â€” `_has_build_command` consults `extract_build_commands` at runtime as a fallback so README-discovered commands count. (3) **Better command discovery** (`command_extractor.py` rewrite): ordered extractors for Makefile (`make build`/`make all`), Cargo.toml (`cargo build`/`cargo test`), go.mod (`go build ./...`/`go test ./...`), Maven `pom.xml`/wrappers (`mvn package`/`mvn test`), Gradle `build.gradle`/wrappers (`gradle build`/`gradle test`), dotnet `.sln`/`.csproj` (`dotnet build`/`dotnet test`), lockfile-aware package.json install (pnpm/yarn/bun), plus **README/docs discovery** â€” known command spellings (`npm run build`, `make build`, `cargo build`, `gradle build`, `mvn package`, `dotnet build`, `go build ./...`, `pip install`, ...) matched in README.md/BUILDING.md/docs with a word-boundary regex; explicit manifests always win over prose. Docs: 01 Â§17, 02 Â§14.5 + changelog, 03 changelog. Tests: +2 backend (AST ignores string literals; scanner uses indexed files only â€” untracked `.venv_sf3d`/`release` never scanned), +10 parametrized extractor tests (Makefile Ã—3, cargo, go, maven, dotnet Ã—2, gradle, README code-block/plain/invention-guard/package.json-precedence), honesty tests rewritten (runner: `success is None`; API: "skipped" status), +1 index-completeness test (git fixture: every tracked file across docs/backend/frontend is indexed), +1 vitest (skipped label); 93.6 % coverage | AI agent |
| 2026-08-12 | 1.17.7.3 | **Projects root; git-tracked indexing; watch-dirs parser fix; world-sim opt-in.** (1) **Projects root** (this machine): all project checkouts moved from the home dir to `C:\Users\j\projects` (nested `jamesdileva\`/`juduncan\` canonical checkouts moved along); `.env` now sets `SENTINEL_WATCH_DIRS=C:\Users\j\projects`, so the home dir is never walked and the projects-root dirs (betsim, coach, nexus, ResMaker, surfhop, ...) become projects at the next scan. DB rows keep their identity via the new `scripts/migrate_projects_root.py` path rewrite (`project.path`, `projectfile.path`/`absolute_path`, `securityfinding.file_path`; `--dry-run` first) run after the move â€” no GC churn, no chat/summary loss (21 project rows + 12,470 file paths on the desktop). (2) **Git-tracked indexing** (`indexer.py`): file lists come from `git ls-files -z` for real git checkouts (walk fallback for non-git and bare `.git/` dirs, rc 128) â€” untracked `.env` secrets, IDE state and uncommitted junk never enter the index (the makehuman `.env` case); ignore/binary/size gates still apply; stale rows prune on rescan as before. AG `tests/conftest.py` + WorkFlow-Toolkit `test.py` updated for the new root. (3) **Watch-dirs parser fix** (`config.py`): `SENTINEL_WATCH_DIRS` accepts a single dir, comma-separated, or JSON â€” the documented comma format previously crashed pydantic-settings' JSON-only parser (`SettingsError`). (4) **World sim opt-in**: `world_sim_enabled` defaults to `False` (router + beat register only with `SENTINEL_WORLD_SIM_ENABLED=true`); world-sim API tests mount the router explicitly. Docs: AGENTS.md, desktop.md, 02 Â§4.2/Â§13.4, 01/02/03 changelogs. Tests: +5 backend (watch-dirs forms Ã—3, git tracked-only, walk fallback, world-sim default), full suite green | AI agent |
| 2026-08-12 | 1.17.7.2 | **Junk-free file index; honest knowledge reset; no autostart task.** (1) **Ignore patterns** (`config.py`): `Library/` (Unity's regenerable PackageCache/Artifacts/BurstCache â€” Khd4 alone was 25.6k cache files), `release/` + `win-unpacked/` (electron-builder output â€” WorkFlow-Toolkit 7.6k, Airadio 65), `*.pdb`/`*.bhc` (build symbols/Burst caches) â€” the desktop index had swollen to 47,455 files vs ~4k of real source on the laptop (v1.17.7.1 gates covered `.venv*/`/`dist/`/`build/` but not these); ignored rows prune themselves on the next scan (`_index_files` drops rows no longer walked, proven by Demake 35kâ†’339 and AG 26kâ†’1.3k). (2) **Reset now sticks** (`job_scheduler.py`, `rag_tasks.py`): new `JobScheduler.cancel_queued(name_prefix)` cancels not-yet-started pool jobs (futures tracked per submit, callback-pruned); `run_reset_knowledge` cancels queued `run_index_knowledge` jobs before clearing flags + dropping collections, so the embedded count goes to 0 and stays 0 â€” previously the boot auto-index re-queued ~20 projects and re-embedded seconds after the reset, making it look like a no-op. (3) **Autostart task removed**: `scripts/install_service.py` deleted, `run.py` drops `--service`/`--install`/`--uninstall` (and the now-unused PYWIN candidates), the desktop task uninstalled (`schtasks /delete /tn Sentinel`) â€” the 5-min Task-Scheduler rerun spawned a console window every time it found the port free (Last Result 1 bind races against a manual start); the server is started manually with `run.py`. Docs: AGENTS.md, README, desktop.md, 01 repo tree, 02 Â§13.3/Â§13.4 + troubleshooting, 03 Phase 13. Tests: âˆ’2 packaging (install_service), +ignore-pattern indexer, +cancel_queued, +reset cancels queued jobs | AI agent |
| 2026-08-12 | 1.17.7.1 | **Junk-file indexing gates + fast boot scans.** The first full scan on the desktop froze the API for ~25-40 min: `_iter_source_files` rglob'd entire trees (demake-engine: 35.3k files / 11 GB incl. a 3.3 GB `model.onnx_data`; AG: 26.8k files incl. `.venv_sf3d` â€” the exact `.venv/` ignore pattern missed venv-like dirs) and parsers `read_text`'d whole files, decoding multi-GB binaries to strings on every scan. Fixes: **(1) file gates** â€” `SENTINEL_MAX_FILE_KB` (default 5120, `config.py`) + a `_BINARY_SUFFIXES` denylist (.onnx/.onnx_data/.pt/.pth/.safetensors/.dll/.so/.db/.sqlite/images/media/archives/...) applied in `_is_skippable` to both full scans and `update_incremental`; **(2) walk prune** â€” the project walk is a DFS that never descends into ignored dirs (`.git/`, `node_modules/`, `.venv*/`, `dist/`, `build/`, `data/` â€” `data/` added, `.venv/`â†’`.venv*/`) instead of rglob+filter (24k ignored entries under this repo alone: `backend/.venv` 15.9k, `frontend/node_modules` 8.2k); **(3) mtime fast-path** â€” new `ProjectFile.mtime_ns` (BIGINT, ALTER migration via `connection._MIGRATIONS`): `_upsert_file` skips re-read/re-parse when `mtime_ns`+`size_bytes` are unchanged, so boot scans drop to seconds after the first pass. **run.py venv resolution** (caught during deploy): the launcher only knew repo-root `.venv` + a Linux-style fallback, so `run.py` died `FileNotFoundError` on this machine â€” `PY_CANDIDATES`/`PYWIN_CANDIDATES` now resolve `backend\.venv` first, root `.venv` second, `.venv/bin/python3` last. **CLI transparency**: `index --all` reports `Indexed k/N: <name>` per project via a progress callback on `scan_all_projects`. Tests: +3 backend (binary+size gates, ignored-dir prune incl. `.venv_sf3d`/`data/`, mtime fast-path skipâ†’reparse), 93.66 % | AI agent |
| 2026-08-12 | 1.17.7 | **Single-desktop deployment; GitHub is now optional; scans decoupled from sync.** The laptop is retired â€” the desktop is both the dev workstation and the always-on server (docs/laptop.md â†’ `docs/desktop.md`; docs/01 Â§9/Â§10, docs/02 Â§13 rewritten; dashboard at `http://127.0.0.1:8000`, localhost only). **Tokenless first-class**: `sync_tasks.run_repo_sync` no longer says "skipped" and startup no longer publishes a token warning (`main.py` logs one INFO line instead); the `repo-sync` beat registers only when `SENTINEL_GITHUB_TOKEN` is set (`job_scheduler.py`). **Security scan-all owns its own beat**: new `SENTINEL_SCAN_INTERVAL_MINUTES` (default 1440, `config.py`) â€” previously the daily scan ran chained to the repo-sync pass, so a tokenless install never scanned; `run_repo_sync` no longer calls `run_security_scan_all`. **Home-dir discovery pruning** (`indexer.py`): the full-home `rglob` walk replaced with a depth-aware walk that prunes noise dirs (`AppData`, `OneDrive`, `node_modules`, `.venv`, tool caches â€” `_DISCOVERY_SKIP_DIRS`) during traversal and never enters paths beyond `_DISCOVERY_DEPTH`; checkouts at depth â‰¤ 4 still found, eligible set unchanged (validated: 21 sync-owned projects in `C:\Users\j`). **install_service venv fallback**: the Task-Scheduler command resolves `backend\.venv` (this machine) or the repo-root `.venv` (previously only repo-root `.venv` â€” the task would point at a nonexistent pythonw here). Tests: +8 backend (scan-all/repo-sync beat registration tokenless+token, scan decoupled from sync, scan interval config, discovery pruning Ã—3, install_service venv Ã—2), 93.95 % total | AI agent |
| 2026-08-10 | 1.17.5 | Duplicates eliminated at the source (Rule 5: projects are known entities). **Discovery eligibility**: only *sync-owned* checkouts can become projects â€” a canonical `<root>/<owner>/<name>` clone whose origin URL matches `github.com/<owner>/<name>`, or a flat direct-child checkout with any GitHub origin (the repos repo-sync adopted in v1.17.4 live there) â€” so git worktrees (`CG.worktrees\agents-*`), stray copies (`Desktop\airadio`, `Documents\CG`, `Desktop\backups\algo-trader`), nested sub-repos (`AG\stable-fast-3d`, `Python Projects\main`), `.codex\*` and seed fixtures are disqualified; same-origin duplicates keep the canonical nested checkout. **Project-row GC**: nothing ever deleted a `project` row â€” deleted dirs (the laptop's `jamesdileva\*` clone folders, the old `Projects\jamesdileva\*` copies) survived as zombie projects that looked alive forever; the full startup scan now drops rows whose checkout is gone, disqualified, or outside the watch roots, cascading files/dependencies/findings/results/logs/summaries/chat/portfolio + stored Chroma docs (FK-safe `delete`). Repo-sync's targeted rescans never GC. Verified read-only against the real desktop home dir: 60 checkouts discovered â†’ 21 kept (18 flat-adopted + 2 new clones + 1 fork), zero churn. Tests: +7 indexer (eligibility variants, origin normalization, canonical-vs-flat dedupe, GC Ã—3), 94.5 % total | AI agent |
| 2026-08-11 | 1.17.6 | Damaged knowledge index made detectable and recoverable. **ChromaManager** (`services/chroma_manager.py`): per-collection operation locks (RLock â€” two knowledge jobs can no longer interleave upserts on one collection), cached health probe that actually touches each non-empty collection's HNSW segment reader (`count()` only reads metadata, so a wiped segment dir still reported healthy), `RagIndexError` translating ChromaDB's `InternalError: Nothing found on disk` (killed write) into a **503 + rebuild hint** instead of a bare 500, `delete_by_project()` sweeping the **real** collections (the GC previously deleted from a phantom `knowledge` collection, orphaning vectors forever) and `reset_all()` as the deterministic recovery. **API**: `GET /rag/index/status` now carries `health` (`broken`/`checked`); `POST /rag/index/reset` (202 job) runs `run_reset_knowledge` (registry entry). **CLI**: `rag-index --reset` (no Ollama, no project id needed). **Frontend**: Knowledge page shows a damaged-index banner + "Rebuild knowledge index" confirm-action. **Scheduler**: graceful shutdown â€” `cancel_futures=True` used to kill an in-flight index mid-upsert, the exact corruption this release detects; workers now drain. **RAG queries**: all-project questions are summary-first (architecture summaries fill the top slots before noisier collections) and context lines now name the source project (metadata only ever stored ids). Tests: +10 backend (API 503/reset/health, delete_by_project on real collections, reset heals the probe, summary-first ordering, project names in context, task/registry/CLI reset), +2 frontend (banner + rebuild action, cancel path) | AI agent |
| 2026-08-11 | 1.17.6.1 | Reset recovery completed: `run_reset_knowledge` (`tasks/rag_tasks.py`) now also clears `ProjectFile.embedding_id` after dropping the collections â€” `ingest_files` skips any file whose flag is set (the v1.17.1 incremental optimization), so a reset that kept the flags would re-embed **nothing** and the index would stay empty forever. The task returns `files_unflagged`; the next index (startup auto-index or `sentinel rag-index`) rebuilds everything. Tests: +1 (flags cleared after reset; the v1.17.6 task test updated for the new return value) | AI agent |
| 2026-08-11 | 1.17.6.2 | Laptop recovery: RAG chat + semantic search work again after a damaged index. **Probe fixed** (`services/chroma_manager.py` `health`): the v1.17.6 probe (`get(limit=1)`) could pass while the query path raised (`Nothing found on disk`) â€” the laptop showed "damaged" 503s in chat while the dashboard reported healthy, so the rebuild banner never appeared; the probe now runs a real query with a stored embedding, the exact operation search uses. `reset()` also tolerates `InternalError` during `delete_collection` (a broken store can raise on drop â€” treated as reset since the collection is being discarded). **Auto-index always includes the AI architecture summary**: `queue_knowledge_index_unembedded` (startup scan + repo-sync pass) submits `run_index_knowledge` with `with_summary=True`, and `ingest_project_summary` dedupes to **once per project** (an existing `architecture` summary is reused â€” no Ollama burn per scan; CLI `rag-index <project> --summary` forces a regenerate via `force_summary`). Dashboard "Include AI architecture summary" checkbox removed (redundant; API `with_summary` param kept). New projects and post-reset re-indexes get summaries automatically, so all-project chat ("what are these projects about") is summary-first as designed. Deferred (noted): summary regeneration when repos change / after re-index â€” needs file-change detection (edits are never re-embedded today); the sync pass already knows changed repos, so the hook is cheap to add later. Tests: +5 backend (query-path probe broken+healthy, reset tolerating InternalError, summary dedupe + force, queued auto-index args), +1 frontend update (checkbox removed, always-summary) | AI agent |
| 2026-08-12 | 1.17.6.8 | **Full re-embed is now a button; Ollama timeouts + summary truncation fixed.** Knowledge page: "Rebuild knowledge index" is **always visible** (previously only inside the damaged-index banner â€” a healthy-but-stale index had no in-UI path to re-embed with current chunking/summary prompt); confirm dialog covers both the damaged-disk and stale-embeddings cases, banner is informational only. Timeout hardening (laptop `sentinel(2).log`: 3 of 17 post-reset jobs failed at `ingest_project_summary` â€” the v1.17.6.6 doc-first prompt ~10k-token prefill outgrew the 600 s read timeout against the embedding flood; files were embedded fine, summaries were lost): `ollama_timeout_seconds` default 600 â†’ 1800 (`SENTINEL_OLLAMA_TIMEOUT_SECONDS` overrides). Summary output budget: new `ollama_summary_max_tokens` default **1250** â€” the fed-more context produces structured components/stack/notes summaries past the old shared 500 cap; chat answers keep 500 (`_generate_with_metrics` forwards `max_tokens`; summary call site passes the setting). `.env.example` documents both overrides. Tests: +1 backend (summary call carries the 1250 cap, chat stays 500), +1 frontend (rebuild action visible on a healthy index) | AI agent |
| 2026-08-12 | 1.17.6.7 | **"Re-index all projects" button 500 fixed.** Root cause: `/api/v1/rag/index/all` (`api/v1/rag.py`) submits the job name `run_index_knowledge_all`, but `_build_registry()` (`services/job_scheduler.py`) never added the entry when 1.17.6.4 introduced the task â€” `JobScheduler.submit` raised `KeyError: 'run_index_knowledge_all'` on every click. The registry contract test (`tests/test_job_scheduler.py`) asserted an *exact* name set that predated the task, so it stayed green; the set now includes the name and a new regression test verifies the exact names the API routers submit all resolve through the real registry. CLI `rag-index --all` never hit the bug (calls the task directly, no registry). **CLI `rag-index --reset` fixed**: it called `get_chroma_manager().reset_all()` directly, so it dropped the collections but never cleared `ProjectFile.embedding_id` â€” the startup auto-index then found nothing to re-embed and the Knowledge page kept showing every file as embedded against an empty index (the v1.17.6.1 flag-clearing lived only in the API path). It now runs the same `run_reset_knowledge()` task as the API button and prints `files_unflagged`. **Flaky gate fixed**: the lifespan startup scan (`main.py`) spawned a `sentinel-scan` daemon thread that outlived its TestClient and could persist a `SyncRun` into a later test's engine â€” intermittently failing `test_system_sync_endpoint`; the autouse `conftest.py` fixture now pins `auto_scan_on_startup=False` (renamed `_quiet_background`). Tests: +1 backend (registry), +1 backend updated (CLI reset runs the task) | AI agent |

| 2026-08-12 | 1.17.6.6 | Security scans join the daily sync chain; markdown-aware retrieval. **Scan = once per 24 h, not a separate beat**: `nightly-security-scan` removed from the scheduler (`job_scheduler.py`, `_BEAT_IDS` is now `repo-sync` + `world-sim-tick`) â€” the daily repo-sync runs the scan at the end of its pass (sync â†’ knowledge index â†’ security scan, whenever sync is configured; `sync_tasks.run_repo_sync` calls `run_security_scan_all`), so findings always reflect freshly pulled code with no extra wake-ups. **Never-scanned â‰  clean**: `Project.last_scanned` (a dead column since Sprint 0) is now stamped by every scan (`scan_project` commits it even when clean); `portfolio_service._security_component(project)` â€” no findings + never scanned = **pending** (0, "never scanned"), no findings + scanned = **clean** (full 25) â€” and `_source_epoch` includes `last_scanned`, so the cache refreshes after the first clean scan. **Docs chunked, code kept whole** (`rag_service.py`): `.md`/Markdown/`docs/` files chunked at `_DOC_CHUNK_CHARS=2000` / `_DOC_CHUNK_OVERLAP=200` / `_DOC_CHUNK_MAX=32` (ids `{file}#{i}`), code stays single 4k chunks â€” "how do I add X" questions now retrieve READMEs and guides, not just code. **Smarter summaries**: `_file_summary_context` is docs-first (`_rank_summary_files`: README 400 > `.md` 300 > `docs/` 150 > entry files 100; `_SUMMARY_FILES=25` Ã— `_SUMMARY_FILE_CHARS=1500`) plus the 25 most recent commit messages as the sprint timeline; `project_summary.j2` rewritten (Overview / Architecture / Build-Run-Test / Phase milestones, "trust docs over code" instruction). **All-project queries scale**: `_search_all_projects` top_k = max(requested, min(indexed projects, `_ALL_PROJECT_CAP=24`)), summary collection consulted first then distance-ranked merge, context trimmed to `_QUERY_CONTEXT_BUDGET=48_000` chars. **`__all__` chat room**: `chat_history`/`chat_save` accept the literal `__all__` (skip `_project_or_404`); RagChat uses `room = projectId ?? "__all__"` for both load and persist. **Frontend**: query timeout 120 s â†’ 600 s, default topK 5 â†’ 10 (`api/rag.ts`). **Context window**: `ollama_num_ctx=32768` (`core/config.py`, passed in `OllamaService.generate` options â€” Ollama's default 2048 would truncate summaries/answers). Migration: knowledge reset + re-index-all applies the new chunking and regenerates summaries with the new prompt. Tests: +9 backend (docs chunked / code single, `_chunk_document` bounds, summary ranking docs-first + commits appending, all-scope scaling, scanner `last_scanned` stamp, portfolio pendingâ†’clean + cache invalidation, sync chains scan + skip when unconfigured, `__all__` room; scheduler beat + num_ctx tests updated), +2 frontend (`__all__` history load/persist); full pytest suite green (coverage gate met) + 75 vitest | AI agent |

| 2026-08-12 | 1.17.6.5 | **Default LLM switched to `llama3.1:8b`** (was `gemma2`). Head-to-head on the architecture-summary prompt (same `project_summary.j2` template + 8-file/600-char context, app defaults 500 tokens / temp 0.3): gemma2 â€” 186 tokens, 6.3 tok/s, tight high-level summary that correctly said the context was thin; llama3.1:8b â€” 294 tokens, 9.0 tok/s, better-structured summary (components / stack / notes, picked up the AGENTS.md rules). Won on structure + speed + instruction following; the prompt already enforces "say so rather than guessing". Changes: `settings.ollama_model` + `world_sim_model` defaults â†’ `llama3.1:8b` (world-sim narratives are deterministic templates â€” `world_sim_model`/`world_sim_ai_narratives` are currently unused, kept consistent for future AI-narrative wiring), CLI pull guidance (both `ollama pull` messages), `.env.example`, AGENTS.md decision table, docs current-state references. Existing summaries keep their `model` provenance; new generations use the new model â€” migrate the laptop's summaries with `rag-index <project> --summary` per project. No test changes (no test asserts the default; fixture strings are arbitrary) | AI agent |
| 2026-08-12 | 1.17.6.4 | Run-log cleanup + re-index-all command. **Log noise** (`app/core/logging.py`): `httpx`/`httpcore` set to WARNING â€” the 1.17.6.3 run log was ~500 `POST /api/embed` lines in ~1800 (that detail already lives in the activity feed and the Ollama query log). **Deterministic single-write run log**: the file handler is pinned on `uvicorn`/`uvicorn.error`/`uvicorn.access` *and* root, with `propagate=False` forced on the uvicorn loggers, so every line lands in `data/logs/sentinel.log` exactly once regardless of uvicorn's own log config (a pinned handler on a propagating logger chain could write a record two or three times). **Ollama timeout** (`app/core/config.py`): default `ollama_timeout_seconds` 120 â†’ 600 â€” a laptop saturated by 4 concurrent embedding workers timed out arch-summary generation at 2 min; 10 min covers the slow gemma2 case; `SENTINEL_OLLAMA_TIMEOUT_SECONDS` overrides. **Re-index all projects**: Knowledge-page "Re-index all projects" button + `POST /api/v1/rag/index/all` (`api/v1/rag.py`) + CLI `rag-index --all` (`app/cli.py`) â€” one deterministic job (`tasks/rag_tasks.py` `run_index_knowledge_all`) loops every project with `with_summary=True`; fully incremental (`ingest_files` skips files whose `embedding_id` is set), so it backfills missing AI architecture summaries without re-embedding (the 1.17.6.3 timed-out summary jobs are exactly this case) and embeds new files from a recent `git pull`; one project's failure never aborts the pass (per-project try/except, `failed` counter). Tests: +8 backend (endpoint queues one job, CLI `--all` runs the task and usage lists it, re-index-all skips embedded files + regenerates a missing summary + survives one bad project, uvicorn loggers pinned propagate=False single-write, httpx silenced to WARNING), frontend reindex-button test | AI agent |
| 2026-08-11 | 1.17.6.3 | Post-laptop-log runbook pass. **Summary dedupe fixed** (`rag_service.py` `ingest_project_summary`): the v1.17.6.2 dedupe checked the SQLite `KnowledgeSummary` row, not the embedding â€” `reset()` drops the `project_summaries` collection but keeps the rows, so a post-reset re-index skipped the architecture summary entirely (files re-embedded, `project_summaries` count stayed 0, all-project chat lost its summary-first answers). The dedupe now skips only when the vector exists (`get(where={"$and": [...]})`; damaged-store errors count as missing) and a regeneration reuses the newest row instead of duplicating it â€” `force` (CLI `--summary`) unchanged. **Per-run log file** (`app/core/logging.py`): `data/logs/sentinel.log` â€” truncated at startup, INFO level, answers "what happened this run" (the case that started this: a forced shutdown mid-index scrolled the console and vanished). `attach_file_logging()` re-attaches the single file handler at lifespan startup (uvicorn's log config replaces root handlers after app import) and pins it on the `uvicorn`/`uvicorn.error`/`uvicorn.access` loggers (propagate=False) â€” no duplicated lines, no lost uvicorn logs. **run.py port-owner message**: starting while another instance runs (a second console left open â€” the v1.17.6.3 trigger) prints the owning PID via `netstat -ano` + a `taskkill` hint instead of uvicorn's raw bind traceback. Tests: +5 backend (summary regenerates after reset with row reuse, once-per-project dedupe maintained, run-log written at INFO, overwrite-mode handler, attach idempotent on root + uvicorn loggers) | AI agent |
| 2026-08-10 | 1.17.4 | Duplicate-repo fix + feed cleanup after the laptop's first real sync. **Duplicated projects**: sync clones into `<watch-root>/<owner>/<repo>` (`Projects\jamesdileva\Sentinel`) but the existing repos live flat at the watch root (`Projects\Sentinel`, â€¦) â€” the layout check found no checkout, so all 18 repos were cloned a second time and every project indexed twice; `_local_path` now falls back to any checkout directly under the root whose origin remote URL matches `<owner>/<repo>` (normalized: https/ssh/case/.git suffix) and pulls it instead of cloning (deterministic adoption, `_find_existing_checkout`; flat layouts are never duplicated again). **world_tick feed spam**: the world-sim beat fires every 60 s and each tick published `running` + `finished` activity events (~2880/day, flooding the live feed + DB); beats can now be registered `quiet=True` and the world-sim tick is â€” per-tick log lines unchanged, on-demand jobs and the sync/scan beats keep their events. **Dashboard build shipped**: v1.17.3's Systemâ†’Dashboard merge + Settings placeholder never reached the laptop because `backend/app/static` still held the pre-merge build (it is tracked, so the rebuilt assets are now committed; System now shows the Settings placeholder and the Dashboard has the Home server section). Tests: +8 backend (flat-adoption variants + quiet-beat, 35 in the two touched files), 94.5 % total | AI agent |
| 2026-08-09 | 1.17.2 | Living-week fixes. **No more re-embedding on restart**: `IndexerService._index_files` (Â§3.1) deleted + re-inserted every `project_file` row per scan, nulling `embedding_id` (Chroma doc ids are the row ids) â€” auto index re-embedded all 2.9k files after every restart; rows now keyed by path, unchanged files keep id + embedding_id, vanished files drop. **Shared Chroma client** (Â§6.1): a startup burst of knowledge jobs constructed `PersistentClient`s concurrently and raced ChromaDB's shared-system registry (`'RustBindingsAPI' has no attribute 'bindings'`) â€” `get_chroma_manager()` hands out one locked client per path (`rag_service.py` default). **Activity feed caching**: `useActivity` mount-seed re-runs when the WS opens and retries once after an empty first load â€” cached history shows on entering the dashboard; `activity_bus` persist failures now WARN (were debug; the laptop's history could vanish silently). **Embedding t/s**: `OllamaService.embed_with_metrics` (Ollama `prompt_eval_count/duration`) â†’ knowledge progress ticks carry `tokens_per_second` (`rag_tasks.progress` `detail` "~N tok/s") during indexing; generations/chat t/s unchanged. External Ollama clients stay invisible by design â€” Sentinel measures only its own calls. Tests: +10 backend / 70 vitest | AI agent |
| 2026-08-09 | 1.17.1 | Regression-fix & ops pass after the first living week. **Scanner false positive fixed**: `\bexec\s*\(` matched `session.exec(` because a dot is a word boundary â€” 17 of the laptop's 20 findings were SQLModel ORM calls in clean repos; attribute calls are now ignored (only bare identifiers match). **Sync feedback**: an unconfigured sync now publishes *why* on the live feed ("Repo sync skipped â€” token not configured"), and nothing-changed passes carry a `detail`; new `POST /system/sync` (`{"full": bool}`) + header "Sync now" button run a background pass (409 when already running, activity events per pass; Â§2.2). **Migration bug fixed**: `migrate_columns` only added missing columns to the *first* affected table â€” `ollamaquerylog.purpose` was silently absent (would crash chat history past the 5000-row ceiling); migrated tables are now verified via `PRAGMA table_info` and repaired per table. **Sync cadence**: `SENTINEL_SYNC_INTERVAL_MINUTES` default 15 â†’ 1440 (daily; startup still syncs once). **C++ builds deferred** to Sprint 18 (Rule 4 â€” parser scope is out of control). Tests: regression tests for all four | AI agent |
| 2026-08-09 | 1.17 | Sprint 17 (Observability & UX pass). **Activity bus**: `app/services/activity_bus.py` â€” `publish_event(kind, message, detail, data)` persists to the bounded `activity_event` table (5000-row ceiling, lock-serialized) + enriches the live channel; `GET /system/activity` (newest first, cap 500) and WS `/api/v1/ws/jobs` frames `{type: "activity", event: {...}}` + 30 s heartbeat. Publishers: job scheduler (queued/running/finished/failed), sync, build/test/security tasks, rag index start/finish, `rag_service._generate_with_metrics` (kind `ollama`, `purpose` = query/summary/â€¦, data carries model/purpose/tokens/eval_duration_ns for tok/s). **Chat persistence**: `ChatMessage` table + `GET/POST /rag/chat/{project_id}`; RagChat replays + saves every exchange (best-effort). **Auto knowledge-index**: `SENTINEL_AUTO_INDEX_KNOWLEDGE` (default true) â€” startup scan queues `run_index_knowledge` for projects with unembedded files via shared `queue_knowledge_index_unembedded()` (Ollama-gated); sync pass refactored onto the same helper. **Frontend**: global StatusBar (live dot, latest event, Ollama purpose + tok/s), sync pill visible when unconfigured ("Sync not configured"), Dashboard live activity log (poll fallback in `useActivity`), KnowledgeExplorer live progress refresh (3 s throttle), ProjectGalaxy node labels + legend, HealthCard per-criterion reasons + screenshots chip. **.env path fix**: `config.py` env_file was `BASE_DIR.parent / ".env"` (home) since Sprint 0 â€” repo-root `.env` never loaded natively; now `BASE_DIR / ".env"` (regression test pins it). **Gate repair**: `scripts/build.py` masked failures (raw exit 0 is falsy in the `and` chain) and ran flake8 at default 79 cols â€” booleanized + `--max-line-length=100`; stragglers cleared. Tests: 271 backend / 94.49 %, 63 vitest, gate exits 0 | AI agent |
| 2026-08-08 | 1.16.2 | Dashboard actually served: `app/main.py` still pointed at `frontend/dist` while the build is staged at `backend/app/static` â€” on a Node-less laptop every non-API path 404'd. Now serves the staged build (dev fallback to `frontend/dist`) and `/` returns dashboard HTML instead of the Sprint-1 health JSON (health stays at `/health` + `/api/v1/health`). SPA-fallback + root tests added; 257 backend green. Docs: venv-path commands tightened (`.\.venv\Scripts\python.exe run.py` â€” PowerShell ExecutionPolicy blocks `Activate.ps1`, activation never required): Â§5.2 + Â§13, laptop.md, AGENTS.md. Watch-dir default changed from hardcoded `C:\Users\j` to the current user's home (`Path.home()`) â€” laptop `C:\Users\james` found with no config; env override unchanged | AI agent |
| 2026-08-08 | 1.16.1 | Pi-hole decommissioned on the laptop (docs/laptop.md `Moving off Docker`): router DNS back to Automatic, docker system prune -a --volumes wipes the old stack + Pi-hole, Docker Desktop uninstalled, old Sentinel task removed; laptop now needs only Python (repo ships the staged dashboard in ackend/app/static â€” no Node). Docs: laptop.md migration section added, 01 Â§9.2/Â§10 and 02 Â§13 updated (Pi-hole retired, DNS Automatic) | User |
| 2026-08-08 | 1.16 | Sprint 15.1 (Native deployment, decommission Docker). Compose/Docker layer removed: docker-compose*.yml, docker/, scripts/dev.py deleted; 
un.py (repo root) is the single starting point â€” startup checks then uvicorn on 127.0.0.1:8000 (--check/--port/--reload/--service/--install/--uninstall); scripts/install_service.py registers the Sentinel Task-Scheduler task (pythonw run.py --service every 5 min, idempotent); scripts/build.py reworked (verify + --dist stages frontend into ackend/app/static, served same-origin by pp/main.py); scripts/release.py ships run.py + scripts + docs + ackend/app; SENTINEL_PORT replaces SENTINEL_API_PORT; Â§4.2 env table + Â§13 rewritten (native runbook, troubleshooting); laptop.md rewritten. Pi-hole left the stack â€” System-page panel + SENTINEL_PIHOLE_* removed. Frontend: /system panel + pi/system.ts types updated. Tests: packaging suite reworked for native artifacts. Docs: changelogs v1.16 | User + AI agent |
| 2026-08-07 | 1.15 | Sprint 15 (Performance tuning + final polish): Â§14.5 scoring rewritten (build = 21 static + 9 proven / tests = 24 static + 6 proven â€” static survives failed runs; docs green â‰¥50%) + caching (`_fresh_row` serves the stored `PortfolioScore` until a source row is newer) + `GET /portfolio/summary` (dashboard stats); Â§13.4 GitHub sync â€” HEAD change detection before/after pull (only moved repos re-indexed, all-clean passes skip the scan, knowledge auto-index narrowed to changed repos), runs persisted to new `SyncRun` table surfaced by `GET /system/sync` (read-only); Â§2.3 `GET /rag/index/status` (embedded vs total files per project); scanner skips self-scan false positives (`data/`, `fixtures/`, template `.env` names; real `.env` still flagged). Frontend: Dashboard real stats (portfolio summary), header sync pill (Layout), Knowledge page index progress. Tests: 268 backend (new change-detection/persistence in `test_sync_service.py`, `/system/sync` in `test_system_service.py`, `/rag/index/status` in `test_rag_api.py`, scoring/cache/`is_test_file_path` in `test_portfolio.py`, scanner tests) + 58 vitest (Layout pill, Dashboard stats, KnowledgeExplorer) | User + AI |
| 2026-08-07 | 1.14 | Sprint 12.2 (Bugs + UI pages): Â§11 world sim unblocked â€” events/expansion: new step 2.5 **recruitment** (`event_generator.py`, food-secure settlements scale roles with population: farmers `pop//6` capped by new `FARM_CAPACITY` per terrain, builders/merchants/explorers pop//12//30//60; starving settlements recruit nobody), food store capped at `pop Ã— MAX_FOOD_DAYS` (Â§11.3, bounds +6%/road trade growth so SQLite ints never overflow), expansion stops at `MAX_ACTIVE_SETTLEMENTS = 60`, raids restricted to road-connected pairs (O(roads) vs O(nÂ²)), skill bonuses clamp at level 10 (+45% production / +90% rebuild); worlds now naturally reach ~60 settlements/58 roads (was dead at ~130 pop / 0 roads because farmers were fixed at bootstrap); new `test_roads_appear_from_natural_growth`. **Indexer encoding hardening**: `indexer.py`/`framework_detector.py`/`command_extractor.py` read text/json as UTF-8 with `errors="replace"` and catch `UnicodeDecodeError` so a non-UTF-8 `requirements.txt` (MLBattles) can't abort indexing; regression `test_index_project_survives_non_utf8_requirements`. **Knowledge auto-index after sync**: `sync_service._queue_knowledge_index` â€” after a pass, projects that still have files with `embedding_id IS NULL` get a `run_index_knowledge` Celery task queued per project (best-effort: skipped with `"ollama-unavailable"` when Ollama is down, never fails the sync); `rag_service.ingest_files` marks unreadable files with `embedding_id = record.id` and commits even with zero embeds so the pending query doesn't re-queue forever; CLI `sentinel sync` prints the knowledge line; 2 new tests. Frontend: placeholder content removed â€” real `/projects`, `/builds`, `/security` pages (`pages/Projects.tsx|Builds.tsx|Security.tsx`, `api/tests.ts`, etc) with expandable file lists, per-project run + history + log/finding drill-downs; `ArchitectureMap.test.tsx` race fixed (`findByText`). Tests: 256 backend (95.08% cov), 48 vitest. Docs: Â§11.3/Â§11.4/Â§11.5, Â§13.4 sync notes, changelogs v1.14 | User + AI agent |
| 2026-08-07 | 1.13 | Sprint 12.1 (Repo auto-sync + Pi-hole v6 auth fix + SMB revert): Â§13.4 rewritten â€” laptop projects now come from **GitHub auto-sync** instead of an SMB share: `RepoSyncService`: `RepoSyncService` (`services/sync_service.py`) lists repos via GitHub API (read-only PAT, `SENTINEL_GITHUB_TOKEN`, paged `GET /user/repos`), `git clone`s missing repos and `git pull --ff-only` existing checkouts under `SENTINEL_PROJECTS_DIR` (local target â†’ `/data/projects`), then re-indexes; CLI `sentinel sync` + Celery beat `repo-sync` (`SENTINEL_SYNC_INTERVAL_MINUTES`, default 15); git never prompts (`GIT_TERMINAL_PROMPT=0`), fail-fast stderr captured per repo. Pi-hole System-page client fixed (v6 session auth): `POST /api/auth` with `SENTINEL_PIHOLE_PASSWORD` â†’ `X-FTL-SID` header (new `SENTINEL_PIHOLE_PASSWORD` config; v5 `SENTINEL_PIHOLE_API_TOKEN`/`X-FTL-API-KEY` removed); read-only, Rule 2. Compose/`.env.example` pass `SENTINEL_GITHUB_TOKEN`/`SENTINEL_SYNC_INTERVAL_MINUTES`/`SENTINEL_PIHOLE_PASSWORD` to backend + worker; env table Â§4 updated. Desktop SMB plumbing reverted. Tests: 251 backend (95.2% cov) â€” new `test_sync_service.py` (MockTransport + run_command stubs: clone/pull/failed/per-repo errors, unconfigured skip, GitHub error), `test_system_service.py` reworked (session auth happy path, bad password 401, X-FTL-SID asserted), CLI sync tests. Docs: laptop.md, AGENTS.md, changelogs v1.13 | User + AI agent |
| 2026-08-06 | 1.12 | Sprint 12 (Home Server + System page): Â§13.4 new home-server runbook â€” laptop runs full stack from one compose file; `frontend` nginx container (docker/frontend/Dockerfile multi-stage â†’ nginx, `8080:80`, `/api` + WS proxy to backend) serves the dashboard at `http://192.168.4.40:8080`; dev overrides moved to explicit `docker-compose.dev.yml` (prod default); `SENTINEL_API_PORT`/`SENTINEL_PROJECTS_DIR`/`SENTINEL_OLLAMA_HOST` env-overridable (SMB projects share = no second copy). Backend: startup validation `services/startup_check.py` (database/chroma/watch dirs/ollama), System page surface â€” `OllamaQueryLog` table, `generate_with_metrics` (eval_count/eval_duration â†’ tokens/sec), `OllamaStatus`/`PiHoleStatus`/`system_overview`, router `api/v1/system.py` (read-only), Pi-hole v6 read-only client (`X-FTL-API-KEY`). CLI finalized per Â§12.6: `portfolio` wired to `PortfolioService`, new `docs <id>`, `world-sim start`. Packaging: `scripts/build.py` + `scripts/release.py` (zip + sha256). Frontend: `/system` page + nav item + `ErrorBoundary`. Tests: Â§12 update â€” test_compose (prod/dev split + frontend service), test_system_service (8), test_startup_check (5), test_packaging (5), System page vitest (4), ErrorBoundary vitest (3), e2e system.spec (2); 238 backend / 36 vitest / 9 e2e | User + AI agent |
| 2026-08-05 | 1.10.1 | Sprint 10.5 (Observatory): new Â§2.11 endpoint docs (`GET /observatory/galaxy|timeline?days=|architecture/{id}`), new Â§14.6 Observatory â€” `ObservatoryService` (`backend/app/services/observatory_service.py`): galaxy = project nodes + shared tech nodes (framework + `Dependency.name`, 2+ projects: tech, links tech-sorted), timeline = `project-created`/`commit`/`build`/`test`/`finding` from `created_at`/`GitCommit.timestamp`/`BuildLog.started_at`/`TestResult.run_at`/`SecurityFinding.detected_at`, naive-UTC cutoff, descending, cap 500, messages clipped to 120 chars; architecture = recursive tree from indexed file paths (dirs-first, count = files beneath, leaf = 1, root = total files), 404 on unknown project. Router `api/v1/observatory.py` registered in `main.py`; schemas `observatory.py` (`GalaxyGraph`/`GalaxyNode`/`GalaxyLink`, `Timeline`/`TimelineEvent`, `ArchitectureNode`, exported). Tests: `tests/test_observatory.py` (11 tests: galaxy shared-tech filtering, timeline window/order/cap/exclusion, tree nesting + counts, `_clip`, API galaxy/timeline/architecture + 404, in-memory SQLite, dependency override). Â§2.6 stale never-built `/projects/{id}/timeline` replaced by a pointer to Â§2.11. Full suite 152 green; black/isort/flake8 clean on new files; `npm run build` clean. Frontend: `/observatory` route + nav item, `pages/Observatory.tsx` (Galaxy + Timeline + Architecture sections), `components/ProjectGalaxy.tsx` (plain SVG node-link graph), `ProjectTimeline.tsx` (kind-colored dots + days-window selector), `ArchitectureMap.tsx` (project dropdown + indented tree), `api/observatory.ts` on shared axios client; `types/index.ts` observatory interfaces | User + AI agent |
| 2026-08-05 | 1.10 | Sprint 10 (Portfolio Intelligence): Â§2.7 rewritten to the shipped endpoints (`/portfolio/scores`, `/best-candidates?min_score=`, `/feature-matrix`), new Â§14.5 Portfolio Intelligence â€” `PortfolioService` (`backend/app/services/portfolio_service.py`, deterministic 30/30/25/15 formula, missing = 0; build latest log success/failure/pending, tests pass ratio, security severity penalties, docs = README/Markdown/`docs/` file ratio; recompute-on-read + upsert to `PortfolioScore`), router `backend/app/api/v1/portfolio.py` registered in `main.py`, `tests/test_portfolio.py` (12 tests, in-memory SQLite, API via dependency override). Frontend: `pages/Portfolio.tsx` (health grid, best candidates, feature matrix), `components/HealthCard.tsx`, `components/FeatureMatrix.tsx`, `api/portfolio.ts` aligned to backend schemas, `/portfolio` route now real (nav item already existed). Observatory (galaxy/timeline/architecture) deferred to Sprint 10.5 | User + AI agent |
| 2026-08-05 | 1.9.1 | Sprint 9 closeout (eeroâ†’Pi-hole DNS handoff): Â§13.3 verification extended with the network-wide blocking steps â€” eero app Custom DNS (IPv4 primary `192.168.4.40` Pi-hole, secondary `192.168.4.1` fallback, IPv6 empty), leave DHCP/NAT on Automatic and eero Secure off, verify via `ipconfig`/DNS showing `192.168.4.40` + `nslookup doubleclick.net` â†’ `0.0.0.0`; Pi-hole v6 login notes (password-only form is normal for the single admin user; `FTLCONF_webpassword` is only applied at first boot, so a stale container shows "wrong password" â€” reset via `docker exec -it sentinel-pihole-1 pihole setpassword`, container name is `sentinel-pihole-1` not `pihole`) | User + AI agent |
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1): Â§11 rewritten from the original container-based "AI world" plan to the shipped deterministic ant-farm â€” isolated SQLite `data/world_sim/world.db` (own metadata; tables `world_sim_state`, `world_settlements`, `world_roads`, `world_events`), rules engine (`rules_engine.py`: terrain as pure `(x,y,seed)` hash, food/growth/construction/expansion/trade/raids/disasters), `event_generator.simulate_day` (9 steps, seeded per day), skill system (`skill_system.py`: `20+5Ã—(severityâˆ’1)` survival XP â†’ tiers 0/50/150/300/500 â†’ levels 1â€“5, +5% production/+10% rebuild per level), `WorldSimulatorService` (advance_day single transaction, bounded catch-up, god tools), API `POST/GET /api/v1/world-sim/*` (state/history/settlements/tick/reset/accelerate/disaster), Celery beat `world-sim-tick` (no new container), CLI `world-sim state|tick|reset|accelerate|disaster|inspect`, 26 tests; Â§2.9 endpoint list + Â§5.1 CLI updated. Frontend: `/world` route + nav, `api/world_sim.ts`, `WorldSimulatorPage` (polling, god controls, settlement inspector, event feed), `WorldGridMap` (2D canvas; BigInt copy of the terrain hash so map == backend) | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): Â§13.1 compose spec updated â€” Pi-hole uses the official `ghcr.io/pi-hole/pihole:latest` image (Pi-hole no longer publishes to Docker Hub; `docker.io/pi-hole/pihole` pulls fail with repository-not-found) with v6 env (`FTLCONF_LOCAL_IPV4`, `FTLCONF_webpassword` from gitignored `.env`, `TZ`), `SENTINEL_OLLAMA_HOST` in backend/worker/scheduler points at the laptop (`http://192.168.4.40:11434`), the `ollama` profile is documented as a local fallback; new Â§13.3 laptop deployment walkthrough (native Ollama `OLLAMA_HOST=0.0.0.0:11434` + firewall rules, model pulls `llama3.1:8b`/`gemma2`/`nomic-embed-text`, clone + `docker compose --profile pihole up -d pihole` with `PIHOLE_WEBPASSWORD`/`PIHOLE_TZ`, router DHCP reservation + LAN DNS), multi-host Ollama env-var table (Sentinel `SENTINEL_OLLAMA_HOST`; airadio `OLLAMA_URL`/`OLLAMA_MODEL`), verification commands (admin UI 8053, `/api/tags`, `nslookup doubleclick.net` â†’ 0.0.0.0) | User + AI agent |
| 2026-08-04 | 1.7 | Sprint 8 Part 2 (chat UI + live E2E): frontend RAG client `api/rag.ts` (search / query with 120s timeout / index / summaries), `RagChat` + `ChatMessage` components (bubbles, source citations with distance, model/generated_at/confidence provenance, error states, auto-scroll), `KnowledgeExplorer` page (project scope selector, "Index knowledge" with optional AI architecture summary, semantic search list, chat), `/knowledge` route. Verified live against native host Ollama: indexing (`nomic-embed-text` embeddings) populated ChromaDB; `POST /rag/query` returned a grounded answer with 5 sources + provenance (`gemma2:2b`); `with_summary` persisted an `architecture` KnowledgeSummary; CLI `ask` same path; Vite dev proxy serves the API. Docker image lacks `git` (commit indexing warns and continues); chat dev-time note: run `docker compose --profile ollama up` with `ollama pull gemma2 nomic-embed-text`, or point `SENTINEL_OLLAMA_HOST` at a running native Ollama | User + AI agent | frontend RAG client `api/rag.ts` (search / query with 120s timeout / index / summaries), `RagChat` + `ChatMessage` components (bubbles, source citations with distance, model/generated_at/confidence provenance, error states, auto-scroll), `KnowledgeExplorer` page (project scope selector, "Index knowledge" with optional AI architecture summary, semantic search list, chat), `/knowledge` route. Verified live against native host Ollama: indexing (`nomic-embed-text` embeddings) populated ChromaDB; `POST /rag/query` returned a grounded answer with 5 sources + provenance (`gemma2:2b`); `with_summary` persisted an `architecture` KnowledgeSummary; CLI `ask` same path; Vite dev proxy serves the API. Docker image lacks `git` (commit indexing warns and continues); chat dev-time note: run `docker compose --profile ollama up` with `ollama pull gemma2 nomic-embed-text`, or point `SENTINEL_OLLAMA_HOST` at a running native Ollama | User + AI agent |
| 2026-08-04 | 1.6 | Sprint 8 Part 1: RAG backend core. New services: `OllamaService` (`generate`, `embed` with `/api/embed` + legacy `/api/embeddings` fallback, `is_available`/`list_models`, injectable `httpx.BaseTransport`), `ChromaManager` (embedded PersistentClient, 6 named collections, hnsw+cosine, `upsert`/`search` with `where` scoping/`delete_by_project`/`count`), `RagService` (injectable `embedder`/`llm`/`chroma` for deterministic tests; `index_project` ingests raw file content into `file_summaries`, git commits, test/security/build collections; optional Ollama architecture summary persisted as `KnowledgeSummary`; `search` + grounded `query` returning sources with `model`/`generated_at`/`confidence` provenance), `GitHistoryService` + pure `parse_log` (`%H|%an|%aI|%s`, dedupe by hash). New repos `git`/`knowledge_summary`; schemas `rag.py`/`knowledge.py`. Endpoints: `POST /api/v1/rag/search`, `POST /api/v1/rag/query`, `POST /api/v1/rag/index` (202 JobEnvelope â†’ Celery `run_index_knowledge`), `GET /api/v1/projects/{id}/summaries`. CLI `ask` + `rag-index` (pre-check Ollama availability, exit 1 with pull instructions). Deps: `chromadb>=0.5`, `httpx>=0.27` moved to main. Windows note: git `--pretty` format must be double-quoted (cmd treats unquoted `|` as a pipe). Frontend chat UI + live E2E is Part 2 | User + AI agent |
| 2026-08-04 | 1.5 | Sprint 7: AutomationEngine split into BuildRunner/TestRunner/SecurityScanner services behind Celery tasks (`app/tasks/`). Endpoints: `POST /api/v1/builds/run` (202, job row pre-created with id == Celery task id; poll via `GET /api/v1/builds/status/{job_id}`), `GET /api/v1/builds/history?project_id=`, `POST /api/v1/tests/run?project_id=` (query param), `GET /api/v1/tests/results?project_id=`, `POST /api/v1/security/scan?project_id=`, `GET /api/v1/security/findings?project_id=`. Compose adds `worker` + `scheduler` (celery + beat, `-P solo`); backend gets `SENTINEL_REDIS_URL`; config adds `redis_url`/`celery_eager`/`command_timeout_seconds`; CLI `build`/`test`/`scan` run synchronously. Deps from pyproject carry no version (parser keeps `requirements.txt` versions); secrets/static findings deterministic | User + AI agent |
| 2026-08-04 | 1.4 | Sprint 6: added `GET /api/v1/projects/`, `GET /api/v1/projects/{id}`, `GET /api/v1/projects/{id}/files`, `WS /api/v1/ws/jobs` (welcome + heartbeat; real job events in Sprint 7). No project create/update â€” indexing stays CLI/IndexerService-only. Frontend: axios client with `/api` proxy, UI/Project/Build contexts, useProjects + useWebSocket (exponential backoff, capped 30s) | User + AI agent |
| 2026-08-04 | 1.3 | Sprint 5: frontend scaffolded â€” Vite 7, React 19, TypeScript strict, Tailwind 3.4 (class dark-mode), React Router v8 (`react-router` package; `react-router-dom` 7.x had a high-severity RSC-mode CSRF advisory, GHSA-qwww-vcr4-c8h2, fixed only in v8), dev proxy `/api` â†’ `127.0.0.1:8000`, port 5173 strict | User + AI agent |
| 2026-08-04 | 1.2 | Sprint 4: `docker-compose.yml` implemented â€” backend + redis run by default (`docker compose up`), Ollama behind the `ollama` profile; `worker`/`scheduler` services deferred to Sprint 7 (Celery), `frontend` deferred to Sprint 5, docker.sock bind deferred to Sprint 7 (runner isolation). Build context is repo root so `.dockerignore` lives at the root. `scripts/dev.py` added with `--backend-only`, `--frontend-only`, `--with-ollama`, `--down`. Watch dirs in-container default to `/data/projects` (mounted from `./data/projects`) | User + AI agent |
| 2026-08-04 | 1.1 | Sprint 0 alignment: ChromaDB is embedded (no `chromadb` container, removed from compose; `version: "3.8"` key removed), scan endpoints unified on `project_id`, watch dirs default to `C:\Users\j`, fixed unclosed code block in Â§3.2 | User + AI agent |
