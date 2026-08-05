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

**GET `/projects/{id}/timeline`** — Get feature timeline
- Returns: `{"timeline": [{"date": "...", "feature": "Added CSV import", "commit_hash": "...", "sprint": 5}, ...]}`

**GET `/git/features`** — Search features across all projects
- Query: `?query=import&project_id=optional`
- Returns: features matched to commits and explanations

### 2.7. Portfolio

**GET `/portfolio/scores`** — Get portfolio scores for all projects
- Returns: list of PortfolioScore with project info

**GET `/portfolio/candidates`** — Get best portfolio candidates
- Query: `?min_score=80`
- Returns: ranked list with missing items per project

**GET `/portfolio/heatmap`** — Feature matrix across all projects
- Returns: `{"projects": [...], "features": ["build", "test", "docs", "security", "screenshots"], "matrix": [[...]]}`

### 2.8. Local Services

**GET `/services`** — List running local services
- Returns: `{"services": [{"name": "ollama", "status": "running", "port": 11434}, ...]}`

**GET `/health`** — Overall system health
- Returns: `{"status": "healthy", "services": {...}, "projects_count": 10, "last_index": "..."}`

### 2.9. World Simulator (Optional)

**GET `/world-sim/state`** — Get current world state
- Returns: `{"day": 482, "events": [...], "nations": [...], "economy": {...}}`

**POST `/world-sim/tick`** — Advance simulation by one day
- Returns: `{"day": 483, "events": ["New trade route established"]}`

**GET `/world-sim/history`** — Get simulation history
- Query: `?limit=100`
- Returns: list of historical day states

**DELETE `/world-sim/reset`** — Reset world simulation
- Returns: `{"status": "reset", "day": 0}`

### 2.10. Configuration

**GET `/config`** — Get current configuration
- Returns: full config object

**PUT `/config`** — Update configuration
- Body: partial config object
- Returns: updated config

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
sentinel ask "<question>"            # Ask RAG a question (CLI mode)
sentinel portfolio                   # Show portfolio scores for all projects
sentinel health                      # Show system health status
sentinel world-sim start             # Start World Simulator (if enabled)
sentinel world-sim tick              # Advance world by one day
sentinel world-sim state             # Show current world state
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

The World Simulator is a fully isolated optional module that runs a persistent AI-generated world simulation. It does not interact with any project intelligence pipelines.

```
World Simulator Container
├── World State Database     (SQLite: data/world_sim/world.db)
├── Simulation Engine        (rule-based event generation + Ollama narrative)
├── World Embedding Store    (ChromaDB collection: world_sim_entities)
├── Event Generator          (generates daily events from rules + AI)
├── Simulation Scheduler     (Celery Beat: advance world per day)
├── World State Manager      (persists and retrieves world state)
└── Dashboard Integration    (WebSocket: push updates to frontend)
```

### 11.2. World State Database Schema

```sql
-- Completely separate from project intelligence database
CREATE TABLE world_sim_state (
    id TEXT PRIMARY KEY,
    day_number INTEGER NOT NULL,
    events JSON,        -- Events that occurred this day
    nations JSON,       -- Nation state data
    economy JSON,       -- Economic state
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE world_entities (
    id TEXT PRIMARY KEY,
    type TEXT,          -- "nation", "character", "item", "event"
    name TEXT,
    description TEXT,
    attributes JSON,    -- Type-specific properties
    embedding_id TEXT,  -- ChromaDB embedding reference
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE world_events_log (
    id TEXT PRIMARY KEY,
    day_number INTEGER,
    event_type TEXT,     -- "discovery", "trade", "conflict", "natural"
    description TEXT,
    affected_entities JSON,  -- Entities involved
    ai_narrative TEXT,        -- Ollama-generated narrative
    severity INTEGER,          -- 1-10
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 11.3. World Simulator Service

```python
class WorldSimulatorService:
    """
    Optional world simulation. Fully isolated from project operations.
    Uses a separate Ollama model and separate databases.
    """

    def __init__(self, config: WorldSimConfig):
        self.db = self._init_separate_db()       # Separate SQLite
        self.chroma = self._init_separate_chroma()  # Separate collection
        self.ollama = self._init_separate_ollama()  # Separate model
        self.rules_engine = RulesEngine()
        self.event_generator = EventGenerator()

    def advance_day(self) -> WorldSimDay:
        day = self._get_current_day()
        events = self.event_generator.generate_events(day, self.rules_engine)
        narrative = self._generate_narrative(events)
        self._save_day(day + 1, events, narrative)
        return WorldSimDay(day=day + 1, events=events)

    def get_state(self) -> dict:
        return self._load_current_state()

    def reset(self) -> None:
        self._clear_all_state()
        self._init_world()
```

### 11.4. Event Generation

Daily events are generated by a combination of:
1. **Rule-based triggers** — population thresholds, resource levels, diplomatic relations
2. **AI narrative generation** — Ollama generates descriptive event text

Event types:
- `discovery` — technology, land, resources
- `trade` — new trade routes, economic shifts
- `conflict` — wars, border disputes, rebellions
- `natural` — weather, disasters, seasonal changes
- `social` — cultural movements, population changes

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
| `test_e2e.py` | Full pipeline: index → scan → build → test → docgen → export | All components |

### 12.2. Frontend Tests (Vitest)

| Test Module | Focus |
|------------|-------|
| `Dashboard.test.tsx` | Stats rendering, quick action buttons |
| `ProjectCard.test.tsx` | Project status display, health score |
| `KnowledgeExplorer.test.tsx` | Search flow, filters, results |
| `RagAssistant.test.tsx` | Chat interface, source display |
| `GalaxyView.test.tsx` | Graph rendering, node interactions |
| `WorldSimPanel.test.tsx` | Simulation state display, tick button |

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

### 12.4. E2E Test Flow

1. Start all services via `docker compose up`
2. Add a project path to watch directories
3. Trigger full index → verify project appears in database with language/framework detected
4. Trigger security scan → verify findings stored
5. Trigger build + test → verify logs and test results stored
6. Ask RAG a question → verify answer is grounded in retrieved context
7. View portfolio → verify health scores and portfolio ranking are correct
8. (Optional) If World Simulator enabled: start simulation → verify events generated

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
      - SENTINEL_OLLAMA_HOST=http://ollama:11434
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
      - SENTINEL_OLLAMA_HOST=http://ollama:11434
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
      - SENTINEL_OLLAMA_HOST=http://ollama:11434
    profiles: ["core"]
    depends_on:
      - redis

  # Optional: Pi-hole for network-wide ad blocking
  pihole:
    image: coredevtech/pihole:latest
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "8053:80/tcp"
    volumes:
      - ./data/pihole/etc-pihole:/etc/pihole
    environment:
      - ServerIP=192.168.x.x
      - WEBPASSWORD=""
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

---

## Changelog

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-04 | 1.5 | Sprint 7: AutomationEngine split into BuildRunner/TestRunner/SecurityScanner services behind Celery tasks (`app/tasks/`). Endpoints: `POST /api/v1/builds/run` (202, job row pre-created with id == Celery task id; poll via `GET /api/v1/builds/status/{job_id}`), `GET /api/v1/builds/history?project_id=`, `POST /api/v1/tests/run?project_id=` (query param), `GET /api/v1/tests/results?project_id=`, `POST /api/v1/security/scan?project_id=`, `GET /api/v1/security/findings?project_id=`. Compose adds `worker` + `scheduler` (celery + beat, `-P solo`); backend gets `SENTINEL_REDIS_URL`; config adds `redis_url`/`celery_eager`/`command_timeout_seconds`; CLI `build`/`test`/`scan` run synchronously. Deps from pyproject carry no version (parser keeps `requirements.txt` versions); secrets/static findings deterministic | User + AI agent |
| 2026-08-04 | 1.4 | Sprint 6: added `GET /api/v1/projects/`, `GET /api/v1/projects/{id}`, `GET /api/v1/projects/{id}/files`, `WS /api/v1/ws/jobs` (welcome + heartbeat; real job events in Sprint 7). No project create/update — indexing stays CLI/IndexerService-only. Frontend: axios client with `/api` proxy, UI/Project/Build contexts, useProjects + useWebSocket (exponential backoff, capped 30s) | User + AI agent |
| 2026-08-04 | 1.3 | Sprint 5: frontend scaffolded — Vite 7, React 19, TypeScript strict, Tailwind 3.4 (class dark-mode), React Router v8 (`react-router` package; `react-router-dom` 7.x had a high-severity RSC-mode CSRF advisory, GHSA-qwww-vcr4-c8h2, fixed only in v8), dev proxy `/api` → `127.0.0.1:8000`, port 5173 strict | User + AI agent |
| 2026-08-04 | 1.2 | Sprint 4: `docker-compose.yml` implemented — backend + redis run by default (`docker compose up`), Ollama behind the `ollama` profile; `worker`/`scheduler` services deferred to Sprint 7 (Celery), `frontend` deferred to Sprint 5, docker.sock bind deferred to Sprint 7 (runner isolation). Build context is repo root so `.dockerignore` lives at the root. `scripts/dev.py` added with `--backend-only`, `--frontend-only`, `--with-ollama`, `--down`. Watch dirs in-container default to `/data/projects` (mounted from `./data/projects`) | User + AI agent |
| 2026-08-04 | 1.1 | Sprint 0 alignment: ChromaDB is embedded (no `chromadb` container, removed from compose; `version: "3.8"` key removed), scan endpoints unified on `project_id`, watch dirs default to `C:\Users\j`, fixed unclosed code block in §3.2 | User + AI agent |
