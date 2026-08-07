# Project Sentinel — Implementation Guide

> **Version:** 1.1
> **Status:** Draft — Sprint 0 (Pre-MVP)
> **Audience:** Developers, AI coding agents
> **Related:** See `docs/01_Master_Architecture.md` for architecture overview

This document is the **technical reference** for implementing Project Sentinel. It provides concrete specifications — database schemas, API contracts, service interfaces, configuration formats, RAG setup, and automation job definitions — that map directly to code. Every sprint in `docs/03_Sprint_Plan.md` references sections from this guide.

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

All endpoints live under `http://127.0.0.1:8000/api/v1/`. Relative paths below omit the `/api/v1` prefix; the frontend and CLI always use the full path.

### 2.1. Projects

**GET `/projects/`** — List all indexed projects
- Query: `?skip=0&limit=50&status=active`
- Returns: `{"projects": [...], "total": 12}`

**GET `/projects/{id}`** — Get project details
- Returns full Project object with stats

**GET `/projects/{id}/files`** — List files in a project
- Query: `?language=python&search=main`
- Returns: list of ProjectFile objects

**GET `/projects/{id}/health`** — Get project health summary
- Returns: `{"health_score": 92, "build": "pass", "tests": "pass", "security": "pass", "docs_pct": 88}`

**POST `/projects/scan`** — Trigger manual re-scan of a project
- Body: `{"project_id": "<uuid>"}`
- Returns: `{"job_id": "SCAN-001", "status": "queued"}`

### 2.2. Indexing

**POST `/indexing/rescan`** — Trigger full re-index of all projects
- Returns: `{"job_id": "IDX-001", "status": "started"}`

**GET `/indexing/status/{job_id}`** — Check indexing progress
- Returns: `{"status": "processing", "progress": 0.45, "current_file": "main.py"}`

**GET `/indexing/status`** — Overall indexing system status
- Returns: `{"last_full_scan": "...", "projects_pending": 3, "projects_done": 10}`

### 2.3. RAG / Intelligence

**POST `/rag/query`** — Ask a question about your projects
- Body: `{"question": "Explain the architecture of Workflow Toolkit", "project_id": "optional"}`
- Returns: `{"answer": "...", "sources": [...], "confidence": 0.92}`

**POST `/rag/search`** — Semantic search across project knowledge
- Body: `{"query": "how does authentication work", "project_id": "optional", "top_k": 5}`
- Returns: `{"results": [{"content": "...", "source": "file_summary", "distance": 0.12}, ...]}

**POST `/rag/index`** — Queue knowledge indexing for a project (202)
- Body: `{"project_id": "...", "with_summary": false}`
- Dispatches Celery task `run_index_knowledge`, returning `{"status": "queued", "job_id": "<task_id>"}`
- Default increments embed raw file content/git commits/test/security/build logs; `with_summary: true` additionally generates an Ollama architecture summary persisted to `KnowledgeSummary`

**GET `/projects/{id}/summaries`** — Get AI-generated project summaries
- Query: `?type=architecture`
- Returns: list of KnowledgeSummary objects

### 2.4. Automation

**GET `/automation/jobs`** — List scheduled and running jobs
- Returns: list of job status objects

**POST `/automation/trigger`** — Trigger a manual automation run
- Body: `{"project_id": "...", "steps": ["build", "test", "scan"]}`
- Returns: `{"job_id": "RUN-001", "status": "queued"}`

**GET `/automation/jobs/{job_id}`** — Get job status and logs
- Returns: full job detail with step results

### 2.5. Security

**GET `/security/findings`** — List all security findings
- Query: `?project_id=...&severity=high&resolved=false`
- Returns: list of SecurityFinding objects

**GET `/security/findings/{id}`** — Get finding details
- Returns: full SecurityFinding with AI explanation

**POST `/security/scan`** — Trigger a security scan for a project
- Body: `{"project_id": "..."}`
- Returns: `{"job_id": "SCAN-001", "status": "queued"}`

### 2.6. Git Intelligence

**GET `/projects/{id}/commits`** — List commits for a project
- Query: `?limit=50&author=John`
- Returns: paginated list of GitCommit objects

**Note:** the original feature-timeline endpoint here was never built; the
shipped activity timeline lives under §2.11 (Observatory), driven by stored
commit/build/test/finding timestamps rather than parsed commit messages.

**GET `/git/features`** — Search features across all projects
- Query: `?query=import&project_id=optional`
- Returns: features matched to commits and explanations

### 2.7. Portfolio (Sprint 10)

Deterministic health scoring (30/30/25/15, missing = 0); see §14.5 for the
formula and semantics.

**GET `/portfolio/scores`** — Health scores for all projects
- Recomputed on read from stored build/test/security/file rows, then persisted
  to the `PortfolioScore` table
- Returns: list of `PortfolioScoreRead` (`build_status`, `test_status`,
  `security_status`, `documentation_pct`, `screenshots_available`,
  `portfolio_score`, `updated_at`)

**GET `/portfolio/best-candidates`** — Ranked job-ready projects
- Query: `?min_score=70` (default 70)
- Returns: `[{"project_id", "project_name", "score", "missing": [...]}]` sorted
  by score descending; `missing` lists components with no data yet

**GET `/portfolio/feature-matrix`** — Grid of projects × features
- Returns: `{"projects": [...], "features": ["build", "test", "docs", "security", "screenshots"], "matrix": [[...]]}`
- Cells: `✓` good · `⚠` failing/findings/partial · `✗` pending; screenshots is
  always `✗` until a screenshot feature exists

### 2.8. Local Services

**GET `/services`** — List running local services
- Returns: `{"services": [{"name": "ollama", "status": "running", "port": 11434}, ...]}`

**GET `/health`** — Overall system health
- Returns: `{"status": "healthy", "services": {...}, "projects_count": 10, "last_index": "..."}`

### 2.9. World Simulator (Sprint 9)

Deterministic "ant farm" module with its own DB; see §11 for full details.

**GET `/world-sim/state`** — Current world state
- Returns: day, seed, time scale, settlements, roads, recent events, stats

**GET `/world-sim/history`** — Event log (ascending)
- Query: `?limit=100&before=<day>`

**GET `/world-sim/settlements/{id}`** — Settlement detail (incl. roads)

**POST `/world-sim/tick`** — Advance the world now
- Body: `{"days": 3}`; returns `{"days_advanced": 3, "day_number": N}`

**POST `/world-sim/reset`** — Wipe and restart
- Body: `{"seed": 7}` (optional); returns `{"status": "reset", "seed": 7}`

**POST `/world-sim/accelerate`** — Set days per tick (1–10)
- Body: `{"time_scale": 5}`

**POST `/world-sim/disaster`** — Force a disaster (god tool)
- Body: `{"settlement_id": "...", "disaster_type": "flood|drought|plague"}`

### 2.10. Configuration

**GET `/config`** — Get current configuration
- Returns: full config object

**PUT `/config`** — Update configuration
- Body: partial config object
- Returns: updated config

### 2.11. Observatory (Sprint 10.5)

Read-only project overviews, deterministic from stored data (§14.6).

**GET `/observatory/galaxy`** — Shared-technology graph
- Returns: `{"nodes": [{"id", "kind": "project|tech", "label", "detail"}], "links": [{"source", "target", "tech"}]}`
- Only technologies used by 2+ projects (`Project.framework` + `Dependency.name`)
  become `tech` nodes; every project is a `project` node linked to each shared tech

**GET `/observatory/timeline`** — Chronological activity
- Query: `?days=365` (default 365; <1 resets to 365)
- Returns: `{"events": [{"at", "kind": "project-created|commit|build|test|finding", "project_id", "project_name", "message"}]}`
- Sources: `Project.created_at`, `GitCommit.timestamp`, `BuildLog.started_at`,
  `TestResult.run_at`, `SecurityFinding.detected_at` — all within the window,
  descending, capped at 500 events

**GET `/observatory/architecture/{project_id}`** — Component tree
- Returns a recursive node: `{"name", "path", "kind": "dir|file", "count", "children": [...]}`
- Dirs first, then files; `count` = number of files beneath a directory (root = total files)
- 404 if the project is unknown

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

    def generate(self, prompt: str, model: str = "gemma2", max_tokens: int = 500, temperature: float = 0.3) -> str:
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

**Configuration:** Endpoint (`http://ollama:11434`), model (`gemma2`), embedding model (`nomic-embed-text`).

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
    """Orchestrates security scanning: vulnerabilities, secrets, static analysis."""

    def scan_project(self, project: Project) -> list[SecurityFinding]:
        """Run all scanners, return findings."""

    def scan_dependencies(self, project: Project) -> list[SecurityFinding]:
        """Use pip-audit / npm audit / safety to find vulnerable deps."""

    def scan_secrets(self, project_path: str) -> list[SecurityFinding]:
        """Use TruffleHog / Gitleaks to detect secrets in source."""

    def scan_static_analysis(self, project_path: str) -> list[SecurityFinding]:
        """Use Bandit (Python) / Semgrep (multi-language) for static analysis."""

    def explain_finding(self, finding: SecurityFinding) -> str:
        """Use Ollama to explain a security finding in context."""
```

**Tools used:**
- `pip-audit` — Python dependency vulnerability scanning
- `npm audit` — Node.js dependency vulnerability scanning
- `TruffleHog` — Secret detection in source code and git history
- `Bandit` — Static analysis for Python
- `Semgrep` — Multi-language static analysis

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
        """Execute: git_update → install → build → test → scan → docgen → screenshot → health_update."""

    def run_custom_pipeline(self, project: Project, steps: list[str]) -> AutomationRun:
        """Execute only specified steps."""

    def get_pipeline_status(self, run_id: str) -> AutomationRun:
        """Get status of a pipeline run."""
```

**Pipeline steps (Celery tasks):**
- `git_update` — pull latest changes
- `install_deps` — install project dependencies
- `build` — compile/bundle project
- `test` — run test suite
- `scan` — run security scan
- `generate_docs` — generate/update documentation
- `generate_screenshots` — capture UI screenshots
- `update_health` — recompute health score and portfolio score

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
        """Generate grid of all projects × features (build/test/docs/security/screenshots)."""
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
- Separate Ollama model (`llama3` vs project's `gemma2`)
- Separate Docker container with CPU/memory limits
- No network access to project services

---

## 4. Configuration

### 4.1. Main Configuration: `config/config.yaml`

```yaml
# Project Sentinel Configuration
server:
  host: "0.0.0.0"
  port: 8000
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
  model: "gemma2"
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

Used by Docker Compose and backend:

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTINEL_DB_PATH` | `/data/sqlite/sentinel.db` | SQLite database path |
| `SENTINEL_CHROMA_PATH` | `/data/chroma` | ChromaDB persistence directory |
| `SENTINEL_OLLAMA_HOST` | `http://ollama:11434` | Ollama server endpoint |
| `SENTINEL_OLLAMA_MODEL` | `gemma2` | LLM model for project AI |
| `SENTINEL_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `SENTINEL_WATCH_DIRS` | `C:\Users\j` | Comma-separated project directories |
| `SENTINEL_API_KEY` | (empty) | Optional API key for authentication |
| `SENTINEL_SCHEDULE_INTERVAL` | `60` | Minutes between automation runs |

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
sentinel rag-index <project_id> --summary   # Also generate architecture summary via Ollama
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
# scripts/dev.py
python scripts/dev.py                  # Start all services in dev mode
python scripts/dev.py --backend-only   # Start only backend
python scripts/dev.py --frontend-only  # Start only frontend

# scripts/build.py
python scripts/build.py                # Build all Docker images
python scripts/build.py --push         # Build and push to registry

# scripts/release.py
python scripts/release.py              # Create release package
python scripts/release.py --version    # Bump version and release
```

---

## 6. RAG Setup

### 6.1. ChromaDB Collections

```
ChromaDB Persistence: /data/chroma

Collections:
├── project_summaries   # AI-generated project architecture/purpose summaries
├── file_summaries      # Per-file AI summaries
├── git_commits         # Commit messages and diffs
├── test_logs           # Test output and failure analysis
├── security_reports    # Security scan results and explanations
├── build_logs          # Build output and failure analysis
└── world_sim_entities  # World Simulator entity embeddings (optional)
```

### 6.2. Embedding Model

- **Model:** `nomic-embed-text` (Ollama)
- **Embedding dimensions:** 768
- **Distance metric:** Cosine similarity
- **Index type:** HNSW (default in ChromaDB)

### 6.3. RAG Pipeline

```
Step 1: Ingestion
  Project files → File summaries (via Ollama) → Embeddings → ChromaDB (file_summaries)
  Git commits → Commit messages → Embeddings → ChromaDB (git_commits)
  Test results → Test output → Embeddings → ChromaDB (test_logs)
  Security findings → Scan results → Embeddings → ChromaDB (security_reports)

Step 2: Query Processing
  User question → Embedding (nomic-embed-text) → ChromaDB similarity search → Top-K context chunks

Step 3: Answer Generation
  Retrieved context + question → Ollama (gemma2) → Grounded answer

Step 4: Post-processing
  Answer + source metadata → Frontend display with source links
```

### 6.4. RAG Service Configuration

```python
# backend/app/services/rag_service.py

RAG_CONFIG = {
    "embedding_model": "nomic-embed-text",
    "llm_model": "gemma2",
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

        git_update → install_deps → build → test → scan → generate_docs
        → generate_screenshots → update_health
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
    run_id: str  # FK → AutomationRun
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
| PythonParser | `parsers/python_parser.py` | Python (.py) — uses AST |
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
    return self.ollama_service.generate(prompt, model="gemma2")
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
intelligence pipelines: its own SQLite database, its own engine, and — per
Project Rules 2/3 — **no generative AI in the simulation loop**. AI is at most
optional flavor on event text and never affects sim state.

The module runs inside the existing stack (no new container): the Celery beat
task `world-sim-tick` advances the world every `world_sim_tick_seconds`, with
bounded catch-up after downtime, and god-tool endpoints allow manual control.

```
backend/app/services/world_sim/
├── rules_engine.py      pure deterministic rules (terrain, food, growth,
│                        construction, expansion, disasters)
├── event_generator.py   simulate_day(): one deterministic day of events
├── skill_system.py      survival experience → skill levels (1–5)
├── names.py             seeded settlement-name generation
└── world_simulator.py   WorldSimulatorService: persistence, catch-up, god tools
frontend/
├── pages/WorldSimulatorPage.tsx   day stats, god tools, event feed
└── components/WorldGridMap.tsx    2D canvas terrain + settlements + roads
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
| `LEVEL_COST_BASE` | 100 | construction needed = 100 × current level |
| `TRADE_BONUS_FRACTION` | 0.06 | food +6% per day per connected road |
| `DISCOVERY_CHANCE` / `SOCIAL_CHANCE` | 0.04 / 0.03 | per-day event probabilities |
| `RAID_CHANCE` / `RAID_DISTANCE` | 0.02 / 3 | raids between close settlements |
| `DISASTER_BASE_CHANCE` | flood .015 / drought .010 / plague .008 | × terrain modifier |

Terrain (`terrain_at(x, y, seed)`): mountains/water/hills/forest/plains with
fertility 0.4–1.1; daily food = `farmers × 6 × fertility × skill_bonus`.

### 11.4. Daily Simulation (`event_generator.simulate_day`)

Steps per day: (1) food production/growth/famine → (2) construction & level
ups → (3) expansion (new settlement + road) → (4) road trade → (5) raids
between close settlements → (6) discoveries → (7) social events → (8)
disasters (with survival experience) → (9) collapse check. Returns a
`DayOutcome` (events, new settlements, new roads) for the service to persist.

### 11.5. Skill System (`skill_system.py`)

Surviving a disaster grants `20 + 5 × (severity − 1)` experience. Experience
maps to a skill level by tier table (0/50/150/300/500 → levels 1–5): +5% food
production and +10% rebuild speed per level beyond the first — settlements
"build back stronger". Deterministic and unit-tested.

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

- `GET /world-sim/state` — day, seed, time scale, settlements, roads, recent events, stats
- `GET /world-sim/history?limit=100&before=N` — event log (ascending)
- `GET /world-sim/settlements/{id}` — detail including roads
- `POST /world-sim/tick {days}` — advance now (god tool)
- `POST /world-sim/reset {seed}` — wipe the world, optionally new seed
- `POST /world-sim/accelerate {time_scale}` — days per tick (1–10)
- `POST /world-sim/disaster {settlement_id, disaster_type}` — flood/drought/plague

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
| `test_compose.py` | Docker Compose config validity | `docker-compose*.yml` |
| `test_cli.py` | CLI commands (index, ask, rag-index, …) | `app/cli.py` |
| `test_tasks.py` | Celery task registry, job envelope wiring | `tasks/*.py` |
| `test_exceptions.py` | Error handlers and `ApiError` mapping | `core/exceptions.py`, `api/errors.py` |
| `test_health.py` | Health endpoint, DB reachability | `api/v1/health.py` |
| `test_e2e.py` | Full pipeline: index → scan → build → test → docgen → export | All components |

> Sprint 11 result: 211 tests passing, 95.6% coverage (gate ≥ 80%), flake8/black/isort clean.

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
(`--host 127.0.0.1`, `/api` proxied to `:8000`). Ports 8000 and 5173 are reused
when already running.

| Spec | Flow |
|------|------|
| `health.spec.ts` | Backend healthy through the Vite proxy; dashboard renders stats + indexed projects |
| `observatory.spec.ts` | Galaxy graph + shared-tech list, activity timeline, architecture project picker |
| `portfolio.spec.ts` | Health cards with deterministic scores, feature matrix table |

Manual run:

1. Start services: `cd backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app` (+ `cd frontend && npm run dev -- --host 127.0.0.1`), or let Playwright spawn them.
2. Run the suite: `cd frontend && npm run test:e2e`.

Acceptance criteria (Sprint 11, docs/03 §753): backend coverage ≥ 80%, every API
endpoint integration-tested (200/404/400), frontend unit tests for all
components, E2E covering key user workflows.

---

## 13. Docker Compose Setup

### 13.1. docker-compose.yml (Core Services)

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
      - ./config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock  # For executing project builds
    environment:
      - SENTINEL_DB_PATH=/data/sqlite/sentinel.db
      - SENTINEL_CHROMA_PATH=/data/chroma
      # Sprint 8.5: AI is served by the laptop's Ollama over the LAN.
      - SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434
    profiles: ["core"]
    depends_on:
      - redis
      - ollama

  frontend:
    build:
      context: .
      dockerfile: docker/frontend/Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://project-sentinel.local:8000
    profiles: ["core"]
    depends_on:
      - backend

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    profiles: ["core"]

  # Local Ollama fallback only (Sprint 8.5: the laptop at 192.168.4.40 is the
  # primary AI host; this container profile is for single-machine setups).
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ./data/ollama:/root/.ollama
    profiles: ["ollama"]

  worker:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    command: celery -A app.tasks.celery_app worker --loglevel=INFO
    volumes:
      - ./data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      # Sprint 8.5: laptop Ollama over the LAN (same as backend).
      - SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434
    profiles: ["core"]
    depends_on:
      - redis
      - ollama

  scheduler:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    command: celery -A app.tasks.celery_app beat --loglevel=INFO
    volumes:
      - ./data:/data
    environment:
      - SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434
    profiles: ["core"]
    depends_on:
      - redis

  # Optional: Pi-hole for network-wide ad blocking (Sprint 8.5, runs on the laptop)
  # Pi-hole v6 env vars; admin UI on http://<laptop-ip>:8053.
  # PIHOLE_WEBPASSWORD lives in a gitignored .env (see §13.3).
  # Image is pulled from GitHub Container Registry — Pi-hole no longer
  # publishes to Docker Hub (docker.io/pi-hole/pihole returns 404).
  pihole:
    image: ghcr.io/pi-hole/pihole:latest
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "8053:80/tcp"
    volumes:
      - ./data/pihole/etc-pihole:/etc/pihole
      - ./data/pihole/etc-dnsmasq.d:/etc/dnsmasq.d
    environment:
      - FTLCONF_LOCAL_IPV4=192.168.4.40
      - FTLCONF_webpassword=${PIHOLE_WEBPASSWORD}
      - TZ=${PIHOLE_TZ:-UTC}
    profiles: ["pihole"]

  # Optional: World Simulator (only with 'world-sim' profile)
  world-sim:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    command: python -m app.services.world_simulator --run
    volumes:
      - ./data/world_sim:/data
    environment:
      - SENTINEL_WORLD_SIM_MODEL=llama3
    profiles: ["world-sim"]
    depends_on:
      - redis
      - ollama
```

### 13.2. Running with Different Profiles

```bash
# Core services only (no Ollama, no Pi-hole, no World Sim)
docker compose --profile core up

# Full stack with Ollama AI
docker compose --profile core --profile ollama up

# Full stack including Pi-hole and World Simulator
docker compose --profile core --profile ollama --profile pihole --profile world-sim up

# Start only World Simulator
docker compose --profile world-sim up world-sim
```

### 13.3. Laptop Deployment (Pi-hole + Shared Ollama)

Sprint 8.5 topology: the laptop (`192.168.4.40`, always-on) hosts Pi-hole and the
shared Ollama instance; the desktop's containers reach AI over the LAN via
`SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434`. The desktop keeps a native
Ollama install as an unused fallback.

**One-time laptop setup (commands run on the laptop):**

```powershell
# 1. Make native Ollama serve the LAN (default binds 127.0.0.1)
#    Set the user env var, then restart the Ollama tray app:
setx OLLAMA_HOST "0.0.0.0:11434"

# 2. Open the firewall (11434 = Ollama, 53 tcp+udp = Pi-hole DNS)
New-NetFirewallRule -DisplayName "Ollama LAN" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow
New-NetFirewallRule -DisplayName "Pi-hole DNS TCP" -Direction Inbound -Protocol TCP -LocalPort 53 -Action Allow
New-NetFirewallRule -DisplayName "Pi-hole DNS UDP" -Direction Inbound -Protocol UDP -LocalPort 53 -Action Allow

# 3. Pull the shared models
ollama pull llama3.1:8b     # airadio's model
ollama pull gemma2          # Sentinel default
ollama pull nomic-embed-text

# 4. Clone Sentinel and start Pi-hole (it already exposes the 'pihole' profile)
git clone https://github.com/jamesdileva/Sentinel.git
cd Sentinel
# .env is gitignored — create it with the admin password shared by the user:
#   PIHOLE_WEBPASSWORD=<generated>
#   PIHOLE_TZ=<e.g. America/New_York>
docker compose --profile pihole up -d pihole
```

**Router configuration** (one-time):
- DHCP reservation → `192.168.4.40` (static LAN IP for the laptop)
- LAN DNS server → `192.168.4.40` (network-wide ad blocking via Pi-hole)

**Verification:**
- `http://192.168.4.40:8053` → Pi-hole admin UI (password from `.env`)
- `http://192.168.4.40:11434/api/tags` → Ollama model list
- `nslookup doubleclick.net 192.168.4.40` → returns `0.0.0.0` (blocked)

**Network-wide blocking (eero router, done 2026-08-05):**
In the eero app, keep DHCP and NAT on **Automatic** (no subnet or lease-range
changes) and leave eero Secure / Advanced Security **off**. Set Custom DNS:
IPv4 Primary `192.168.4.40` (Pi-hole), IPv4 Secondary `192.168.4.1` (eero
fallback — the network behaves exactly as before if the laptop is off), IPv6
fields empty. Save; eero reboots the network (~2 min), then verify from any
device:

```powershell
ipconfig /renew; ipconfig /flushdns
ipconfig /all | Select-String "DNS Servers"   # → 192.168.4.40
nslookup doubleclick.net                      # → 0.0.0.0 (blocked)
nslookup example.com                          # → real IPs (upstream OK)
```

**Pi-hole login (v6):** username is `admin` (all lowercase) + the password from
`PIHOLE_WEBPASSWORD` in `.env`. If login reports a wrong password, the running
container may predate the current `.env` value — `FTLCONF_webpassword` is only
applied at first container boot; reset the stored password with
`docker exec -it sentinel-pihole-1 pihole setpassword` (the container is named
`sentinel-pihole-1`, not `pihole`). Blocking itself works without a login.

**Multi-host Ollama consumers:**

| App | Env var | Default | Laptop value |
|-----|---------|---------|--------------|
| Sentinel backend/worker | `SENTINEL_OLLAMA_HOST` | `http://ollama:11434` (compose) | `http://192.168.4.40:11434` |
| airadio desktop | `OLLAMA_URL` | `http://localhost:11434` | `http://192.168.4.40:11434` |
| airadio desktop | `OLLAMA_MODEL` | `llama3.1:8b` | `llama3.1:8b` |

The desktop's running stack picks up the new host on the next
`docker compose up -d` (env is baked at container create time).

---

## 13.4. Home Server Deployment (Sprint 12)

The laptop is the always-on home server: it hosts the full Sentinel stack,
Pi-hole, and Ollama. After the one-time setup below the whole application is
reachable at **http://192.168.4.40:8080** from any device on the LAN — no
terminal commands, no npm, no Tauri (the dashboard is a web app served by the
`frontend` nginx container).

**One-time laptop setup:**

```powershell
git clone https://github.com/jamesdileva/Sentinel.git
cd Sentinel

# .env is gitignored — create it on the laptop:
#   SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434   (native Ollama, same host)
#   SENTINEL_PROJECTS_DIR=\\192.168.4.28\projects    (SMB share from the desktop)
#   SENTINEL_PIHOLE_HOST=http://192.168.4.40:8053    (System page, optional)
#   SENTINEL_PIHOLE_API_TOKEN=<Pi-hole v6 API token> (optional, read-only)
#   PIHOLE_WEBPASSWORD=<same as Pi-hole admin>       (compose profile)

docker compose --profile pihole up -d
```

`docker compose up` (without `-f docker-compose.dev.yml`) runs **production**:
dev overrides are only merged by `python scripts/dev.py` on a workstation
(§5.2). The stack restarts on boot (`restart: unless-stopped`).

**Projects from the desktop via SMB (no second copy):**

1. On the desktop share a folder containing the repos (e.g. right-click the
   `projects` folder → Properties → Sharing → Share). Note the network path
   `\\192.168.4.28\projects`.
2. On the laptop map the share: `net use P: \\192.168.4.28\projects /persistent:yes`
   (or mount it inside Docker Desktop's file-sharing settings).
3. Set `SENTINEL_PROJECTS_DIR=P:\` in the laptop `.env` — containers mount it
   at `/data/projects` and `SENTINEL_WATCH_DIRS=["/data/projects"]` finds every
   `.git` repo on the share.

The laptop keeps its own `data/sqlite/sentinel.db` and `data/chroma` (the
desktop's indexes do not transfer); after first boot run
`docker compose exec backend sentinel index --all` to build the laptop's
database from the shared projects.

**System page (Sprint 12):**

`http://192.168.4.40:8080/system` shows read-only status for Ollama
(availability, installed models, tokens/sec of recent generations) and Pi-hole
(blocking state, queries today, blocked counts) plus backend startup checks.
Pi-hole interop is a read-only v6 API client (`X-FTL-API-KEY`) — per Project
Rule 2 it never toggles blocking. When `SENTINEL_PIHOLE_HOST`/`TOKEN` are
unset the panel reports "not configured" and the rest of Sentinel is
unaffected.

**Release artifacts:** `python scripts/release.py` produces
`dist/sentinel-<version>.zip` + `.sha256` (compose, Dockerfiles, nginx conf,
`.env.example`, docs) — copy that archive to the laptop instead of cloning if
preferred. `python scripts/build.py` builds and verifies the two container
images.

**Troubleshooting (field-tested Sprint 12 deploy):**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `net use` → *error 67 network name not found* | Windows Firewall SMB-In rule for the **Private** profile is disabled | Desktop: `Enable-NetFirewallRule -Name FPS-SMB-In-TCP_1` (+ `FPS-NB_*-*_1`, `FPS-LLMNR-In-UDP` for discovery); Wi-Fi profile must be **Private** |
| Docker build → *failed to calculate checksum ... "/frontend": not found* | `.dockerignore` excluded `frontend/` from the build context | Removed in v1.12.1; regression-tested by `test_packaging.py` (never exclude `frontend/`) |
| Pi-hole dashboard *wrong password* after restart | Container started manually in Docker Desktop (env/volumes not applied) or volume path moved | Always start via `docker compose --profile pihole up -d`; then `docker compose exec pihole pihole setpassword` writes the hash into the persisted `pihole.toml` |
| Internet dies when Docker stops | Pi-hole **is** the network DNS; stopping Docker stops DNS | Don't stop Docker wholesale — manage the stack via `docker compose --profile pihole up -d` |
| `docker compose exec backend ...` → *service "backend" is not running* | A build failure (e.g. frontend) aborts `up`, so backend never starts | Fix the build error first; `docker compose up -d` again |
| System page shows stale/no endpoints after `git pull` | Container still running an old image | `docker compose up -d --build` (compose only rebuilds when the image is missing) |

---

## 14. Data Access Patterns

| Consumer | Source | Access Method |
|----------|--------|---------------|
| Dashboard | Projects, health scores, findings | REST API (`/api/v1/projects`, `/api/v1/health`) |
| Observatory | Project metadata, file summaries, commit history | REST API (`/api/v1/projects/{id}/files`, `/api/v1/projects/{id}/commits`) |
| RAG Assistant | File summaries, commit messages, test logs | ChromaDB vector search + Ollama |
| Knowledge Explorer | File content, code structure, dependencies | REST API + ChromaDB hybrid search |
| Build/Test/Scan | Project commands, dependency manifests | Celery workers → direct filesystem |
| Documentation Generator | File summaries, commit history, metadata | REST API + Ollama |
| Security Scanner | Dependency manifests, source code | Direct filesystem + security tools |
| World Simulator | World state, entity embeddings | Separate SQLite + ChromaDB collection |
| Portfolio | Build/test/security rows, project files | REST API (`/api/v1/portfolio/*`) |

---

## 14.5. Portfolio Intelligence (Sprint 10)

`PortfolioService` (`backend/app/services/portfolio_service.py`) aggregates each
project's build, test, security and documentation state into a deterministic
0-100 health score — no AI, no extra jobs. Scores are recomputed on read and
upserted into the `PortfolioScore` table (docs/02 §1), so the API, matrix and
candidates always agree.

**Score formula (weights sum to 100):**

| Component | Weight | Rule |
|-----------|--------|------|
| build | 30 | latest `BuildLog`: `success=True` → 30; `success=False` → 10; none/pending → 0 |
| tests | 30 | latest `TestResult`: 0 failures/errors and ≥1 pass → 30; else 30 × pass ratio; none → 0 |
| security | 25 | all findings resolved → 25; unresolved deduct per severity (critical 10 / high 6 / medium 3 / low 1 / info 0, floor 0); no findings at all → 0 (never scanned) |
| docs | 15 | README/Markdown/`docs/` files ÷ total indexed files × 15 |

A component with no data yet scores **0** — projects are never assumed healthy.
`documentation_pct` is the same ratio as a 0-100 integer. `screenshots_available`
is always `False` (no screenshot feature yet; the Feature Matrix screenshots
column stays `✗`).

**Feature Matrix cells** (`✓`/`⚠`/`✗`): build/test — passing/failing/pending;
docs — ≥80% / 1-79% / 0%; security — clean/findings/pending.

**Endpoints:** `GET /portfolio/scores`, `GET /portfolio/best-candidates?min_score=70`,
`GET /portfolio/feature-matrix` (see §2.7).

**Frontend:** `/portfolio` route (nav item "Portfolio") — `pages/Portfolio.tsx`
(health-score grid, best candidates, feature matrix), `components/HealthCard.tsx`,
`components/FeatureMatrix.tsx`, `api/portfolio.ts`. Names are joined from
`GET /projects/`.

**Deferred to Sprint 10.5 (Observatory):** the `ProjectGalaxy` / `ProjectTimeline` /
`ArchitectureMap` components — now shipped, see §14.6.

---

## 14.6. Observatory (Sprint 10.5)

`ObservatoryService` (`backend/app/services/observatory_service.py`) provides three
read-only, deterministic overviews over already-indexed data — no AI, no parsing
at query time.

**Galaxy** `galaxy()` — projects become `project` nodes; technologies (a
project's `framework` plus its `Dependency.name` rows) used by **2+ projects**
become `tech` nodes with a `used by N projects` detail. Every project links to
each tech it shares, so the graph shows reuse across the portfolio.

**Timeline** `timeline(days=365)` — collects events from `Project.created_at`
(`project-created`), `GitCommit.timestamp` (`commit`, `hash8 message`),
`BuildLog.started_at` (`build`, Build success/failed), `TestResult.run_at`
(`test`, N passed / M failed) and `SecurityFinding.detected_at` (`finding`,
`severity: title`), filters to the trailing window, sorts descending, caps at
`MAX_TIMELINE_EVENTS = 500`. Timestamps are stored naive UTC, so the cutoff is
computed naive-UTC to match.

**Architecture** `architecture(project_id)` — builds a nested tree from indexed
`ProjectFile.path` values (split on `/`, backslashes normalized). Nodes carry
`count` = number of files beneath (each file increments every ancestor + itself),
so root count == total indexed files, leaves == 1. Sorted dirs-first then files.

**Schemas:** `backend/app/schemas/observatory.py` — `GalaxyGraph`/`GalaxyNode`/
`GalaxyLink`, `Timeline`/`TimelineEvent`, recursive `ArchitectureNode`
(`model_rebuild()` resolves forward refs).

**Endpoints:** `GET /observatory/galaxy`, `GET /observatory/timeline?days=`,
`GET /observatory/architecture/{id}` (see §2.11). Registered in `main.py`
under `api/v1/observatory.py`.

**Frontend:** `/observatory` route (nav item "Observatory") —
`pages/Observatory.tsx` hosting `components/ProjectGalaxy.tsx` (plain-SVG
node-link graph), `components/ProjectTimeline.tsx` (colored per-kind dots +
window selector), `components/ArchitectureMap.tsx` (project dropdown + indented
tree); `api/observatory.ts` on the shared axios client.

**Note on scope:** the architecture tree derives exclusively from indexed file
paths — it shows where components live, not cross-file imports. "Used by"
relationships aren't persisted, so they're intentionally absent.

---

## Changelog

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-06 | 1.12 | Sprint 12 (Home Server + System page): §13.4 new home-server runbook — laptop runs full stack from one compose file; `frontend` nginx container (docker/frontend/Dockerfile multi-stage → nginx, `8080:80`, `/api` + WS proxy to backend) serves the dashboard at `http://192.168.4.40:8080`; dev overrides moved to explicit `docker-compose.dev.yml` (prod default); `SENTINEL_API_PORT`/`SENTINEL_PROJECTS_DIR`/`SENTINEL_OLLAMA_HOST` env-overridable (SMB projects share = no second copy). Backend: startup validation `services/startup_check.py` (database/chroma/watch dirs/ollama), System page surface — `OllamaQueryLog` table, `generate_with_metrics` (eval_count/eval_duration → tokens/sec), `OllamaStatus`/`PiHoleStatus`/`system_overview`, router `api/v1/system.py` (read-only), Pi-hole v6 read-only client (`X-FTL-API-KEY`). CLI finalized per §12.6: `portfolio` wired to `PortfolioService`, new `docs <id>`, `world-sim start`. Packaging: `scripts/build.py` + `scripts/release.py` (zip + sha256). Frontend: `/system` page + nav item + `ErrorBoundary`. Tests: §12 update — test_compose (prod/dev split + frontend service), test_system_service (8), test_startup_check (5), test_packaging (5), System page vitest (4), ErrorBoundary vitest (3), e2e system.spec (2); 238 backend / 36 vitest / 9 e2e | User + AI agent |
| 2026-08-05 | 1.10.1 | Sprint 10.5 (Observatory): new §2.11 endpoint docs (`GET /observatory/galaxy|timeline?days=|architecture/{id}`), new §14.6 Observatory — `ObservatoryService` (`backend/app/services/observatory_service.py`): galaxy = project nodes + shared tech nodes (framework + `Dependency.name`, 2+ projects: tech, links tech-sorted), timeline = `project-created`/`commit`/`build`/`test`/`finding` from `created_at`/`GitCommit.timestamp`/`BuildLog.started_at`/`TestResult.run_at`/`SecurityFinding.detected_at`, naive-UTC cutoff, descending, cap 500, messages clipped to 120 chars; architecture = recursive tree from indexed file paths (dirs-first, count = files beneath, leaf = 1, root = total files), 404 on unknown project. Router `api/v1/observatory.py` registered in `main.py`; schemas `observatory.py` (`GalaxyGraph`/`GalaxyNode`/`GalaxyLink`, `Timeline`/`TimelineEvent`, `ArchitectureNode`, exported). Tests: `tests/test_observatory.py` (11 tests: galaxy shared-tech filtering, timeline window/order/cap/exclusion, tree nesting + counts, `_clip`, API galaxy/timeline/architecture + 404, in-memory SQLite, dependency override). §2.6 stale never-built `/projects/{id}/timeline` replaced by a pointer to §2.11. Full suite 152 green; black/isort/flake8 clean on new files; `npm run build` clean. Frontend: `/observatory` route + nav item, `pages/Observatory.tsx` (Galaxy + Timeline + Architecture sections), `components/ProjectGalaxy.tsx` (plain SVG node-link graph), `ProjectTimeline.tsx` (kind-colored dots + days-window selector), `ArchitectureMap.tsx` (project dropdown + indented tree), `api/observatory.ts` on shared axios client; `types/index.ts` observatory interfaces | User + AI agent |
| 2026-08-05 | 1.10 | Sprint 10 (Portfolio Intelligence): §2.7 rewritten to the shipped endpoints (`/portfolio/scores`, `/best-candidates?min_score=`, `/feature-matrix`), new §14.5 Portfolio Intelligence — `PortfolioService` (`backend/app/services/portfolio_service.py`, deterministic 30/30/25/15 formula, missing = 0; build latest log success/failure/pending, tests pass ratio, security severity penalties, docs = README/Markdown/`docs/` file ratio; recompute-on-read + upsert to `PortfolioScore`), router `backend/app/api/v1/portfolio.py` registered in `main.py`, `tests/test_portfolio.py` (12 tests, in-memory SQLite, API via dependency override). Frontend: `pages/Portfolio.tsx` (health grid, best candidates, feature matrix), `components/HealthCard.tsx`, `components/FeatureMatrix.tsx`, `api/portfolio.ts` aligned to backend schemas, `/portfolio` route now real (nav item already existed). Observatory (galaxy/timeline/architecture) deferred to Sprint 10.5 | User + AI agent |
| 2026-08-05 | 1.9.1 | Sprint 9 closeout (eero→Pi-hole DNS handoff): §13.3 verification extended with the network-wide blocking steps — eero app Custom DNS (IPv4 primary `192.168.4.40` Pi-hole, secondary `192.168.4.1` fallback, IPv6 empty), leave DHCP/NAT on Automatic and eero Secure off, verify via `ipconfig`/DNS showing `192.168.4.40` + `nslookup doubleclick.net` → `0.0.0.0`; Pi-hole v6 login notes (password-only form is normal for the single admin user; `FTLCONF_webpassword` is only applied at first boot, so a stale container shows "wrong password" — reset via `docker exec -it sentinel-pihole-1 pihole setpassword`, container name is `sentinel-pihole-1` not `pihole`) | User + AI agent |
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1): §11 rewritten from the original container-based "AI world" plan to the shipped deterministic ant-farm — isolated SQLite `data/world_sim/world.db` (own metadata; tables `world_sim_state`, `world_settlements`, `world_roads`, `world_events`), rules engine (`rules_engine.py`: terrain as pure `(x,y,seed)` hash, food/growth/construction/expansion/trade/raids/disasters), `event_generator.simulate_day` (9 steps, seeded per day), skill system (`skill_system.py`: `20+5×(severity−1)` survival XP → tiers 0/50/150/300/500 → levels 1–5, +5% production/+10% rebuild per level), `WorldSimulatorService` (advance_day single transaction, bounded catch-up, god tools), API `POST/GET /api/v1/world-sim/*` (state/history/settlements/tick/reset/accelerate/disaster), Celery beat `world-sim-tick` (no new container), CLI `world-sim state|tick|reset|accelerate|disaster|inspect`, 26 tests; §2.9 endpoint list + §5.1 CLI updated. Frontend: `/world` route + nav, `api/world_sim.ts`, `WorldSimulatorPage` (polling, god controls, settlement inspector, event feed), `WorldGridMap` (2D canvas; BigInt copy of the terrain hash so map == backend) | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): §13.1 compose spec updated — Pi-hole uses the official `ghcr.io/pi-hole/pihole:latest` image (Pi-hole no longer publishes to Docker Hub; `docker.io/pi-hole/pihole` pulls fail with repository-not-found) with v6 env (`FTLCONF_LOCAL_IPV4`, `FTLCONF_webpassword` from gitignored `.env`, `TZ`), `SENTINEL_OLLAMA_HOST` in backend/worker/scheduler points at the laptop (`http://192.168.4.40:11434`), the `ollama` profile is documented as a local fallback; new §13.3 laptop deployment walkthrough (native Ollama `OLLAMA_HOST=0.0.0.0:11434` + firewall rules, model pulls `llama3.1:8b`/`gemma2`/`nomic-embed-text`, clone + `docker compose --profile pihole up -d pihole` with `PIHOLE_WEBPASSWORD`/`PIHOLE_TZ`, router DHCP reservation + LAN DNS), multi-host Ollama env-var table (Sentinel `SENTINEL_OLLAMA_HOST`; airadio `OLLAMA_URL`/`OLLAMA_MODEL`), verification commands (admin UI 8053, `/api/tags`, `nslookup doubleclick.net` → 0.0.0.0) | User + AI agent |
| 2026-08-04 | 1.7 | Sprint 8 Part 2 (chat UI + live E2E): frontend RAG client `api/rag.ts` (search / query with 120s timeout / index / summaries), `RagChat` + `ChatMessage` components (bubbles, source citations with distance, model/generated_at/confidence provenance, error states, auto-scroll), `KnowledgeExplorer` page (project scope selector, "Index knowledge" with optional AI architecture summary, semantic search list, chat), `/knowledge` route. Verified live against native host Ollama: indexing (`nomic-embed-text` embeddings) populated ChromaDB; `POST /rag/query` returned a grounded answer with 5 sources + provenance (`gemma2:2b`); `with_summary` persisted an `architecture` KnowledgeSummary; CLI `ask` same path; Vite dev proxy serves the API. Docker image lacks `git` (commit indexing warns and continues); chat dev-time note: run `docker compose --profile ollama up` with `ollama pull gemma2 nomic-embed-text`, or point `SENTINEL_OLLAMA_HOST` at a running native Ollama | User + AI agent | frontend RAG client `api/rag.ts` (search / query with 120s timeout / index / summaries), `RagChat` + `ChatMessage` components (bubbles, source citations with distance, model/generated_at/confidence provenance, error states, auto-scroll), `KnowledgeExplorer` page (project scope selector, "Index knowledge" with optional AI architecture summary, semantic search list, chat), `/knowledge` route. Verified live against native host Ollama: indexing (`nomic-embed-text` embeddings) populated ChromaDB; `POST /rag/query` returned a grounded answer with 5 sources + provenance (`gemma2:2b`); `with_summary` persisted an `architecture` KnowledgeSummary; CLI `ask` same path; Vite dev proxy serves the API. Docker image lacks `git` (commit indexing warns and continues); chat dev-time note: run `docker compose --profile ollama up` with `ollama pull gemma2 nomic-embed-text`, or point `SENTINEL_OLLAMA_HOST` at a running native Ollama | User + AI agent |
| 2026-08-04 | 1.6 | Sprint 8 Part 1: RAG backend core. New services: `OllamaService` (`generate`, `embed` with `/api/embed` + legacy `/api/embeddings` fallback, `is_available`/`list_models`, injectable `httpx.BaseTransport`), `ChromaManager` (embedded PersistentClient, 6 named collections, hnsw+cosine, `upsert`/`search` with `where` scoping/`delete_by_project`/`count`), `RagService` (injectable `embedder`/`llm`/`chroma` for deterministic tests; `index_project` ingests raw file content into `file_summaries`, git commits, test/security/build collections; optional Ollama architecture summary persisted as `KnowledgeSummary`; `search` + grounded `query` returning sources with `model`/`generated_at`/`confidence` provenance), `GitHistoryService` + pure `parse_log` (`%H|%an|%aI|%s`, dedupe by hash). New repos `git`/`knowledge_summary`; schemas `rag.py`/`knowledge.py`. Endpoints: `POST /api/v1/rag/search`, `POST /api/v1/rag/query`, `POST /api/v1/rag/index` (202 JobEnvelope → Celery `run_index_knowledge`), `GET /api/v1/projects/{id}/summaries`. CLI `ask` + `rag-index` (pre-check Ollama availability, exit 1 with pull instructions). Deps: `chromadb>=0.5`, `httpx>=0.27` moved to main. Windows note: git `--pretty` format must be double-quoted (cmd treats unquoted `|` as a pipe). Frontend chat UI + live E2E is Part 2 | User + AI agent |
| 2026-08-04 | 1.5 | Sprint 7: AutomationEngine split into BuildRunner/TestRunner/SecurityScanner services behind Celery tasks (`app/tasks/`). Endpoints: `POST /api/v1/builds/run` (202, job row pre-created with id == Celery task id; poll via `GET /api/v1/builds/status/{job_id}`), `GET /api/v1/builds/history?project_id=`, `POST /api/v1/tests/run?project_id=` (query param), `GET /api/v1/tests/results?project_id=`, `POST /api/v1/security/scan?project_id=`, `GET /api/v1/security/findings?project_id=`. Compose adds `worker` + `scheduler` (celery + beat, `-P solo`); backend gets `SENTINEL_REDIS_URL`; config adds `redis_url`/`celery_eager`/`command_timeout_seconds`; CLI `build`/`test`/`scan` run synchronously. Deps from pyproject carry no version (parser keeps `requirements.txt` versions); secrets/static findings deterministic | User + AI agent |
| 2026-08-04 | 1.4 | Sprint 6: added `GET /api/v1/projects/`, `GET /api/v1/projects/{id}`, `GET /api/v1/projects/{id}/files`, `WS /api/v1/ws/jobs` (welcome + heartbeat; real job events in Sprint 7). No project create/update — indexing stays CLI/IndexerService-only. Frontend: axios client with `/api` proxy, UI/Project/Build contexts, useProjects + useWebSocket (exponential backoff, capped 30s) | User + AI agent |
| 2026-08-04 | 1.3 | Sprint 5: frontend scaffolded — Vite 7, React 19, TypeScript strict, Tailwind 3.4 (class dark-mode), React Router v8 (`react-router` package; `react-router-dom` 7.x had a high-severity RSC-mode CSRF advisory, GHSA-qwww-vcr4-c8h2, fixed only in v8), dev proxy `/api` → `127.0.0.1:8000`, port 5173 strict | User + AI agent |
| 2026-08-04 | 1.2 | Sprint 4: `docker-compose.yml` implemented — backend + redis run by default (`docker compose up`), Ollama behind the `ollama` profile; `worker`/`scheduler` services deferred to Sprint 7 (Celery), `frontend` deferred to Sprint 5, docker.sock bind deferred to Sprint 7 (runner isolation). Build context is repo root so `.dockerignore` lives at the root. `scripts/dev.py` added with `--backend-only`, `--frontend-only`, `--with-ollama`, `--down`. Watch dirs in-container default to `/data/projects` (mounted from `./data/projects`) | User + AI agent |
| 2026-08-04 | 1.1 | Sprint 0 alignment: ChromaDB is embedded (no `chromadb` container, removed from compose; `version: "3.8"` key removed), scan endpoints unified on `project_id`, watch dirs default to `C:\Users\j`, fixed unclosed code block in §3.2 | User + AI agent |
