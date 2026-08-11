# Project Sentinel — Master Architecture

> **Version:** 1.1
> **Status:** Draft — Phase 0 (Pre-MVP)
> **Audience:** Developers, AI coding agents, project maintainers
> **Related:** See `docs/02_Implementation_Guide.md` for technical specs, `docs/03_Sprint_Plan.md` for build phases

This is the single source of truth for what Project Sentinel is and how it is structured. Every future document — implementation guides, sprint plans, API references — derives from and references this document.

---

## Table of Contents

1. Vision
2. Goals
3. Non-Goals
4. Design Philosophy
5. Project Rules
6. MVP Definition
7. High-Level Architecture
8. Component Deep-Dives
   - 8.1 Project Sentinel Server
   - 8.2 Web Dashboard
   - 8.3 Local API Gateway
   - 8.4 Project Intelligence Engine
   - 8.5 Repository Indexer
   - 8.6 Knowledge Database
   - 8.7 RAG System
   - 8.8 Ollama AI Service
   - 8.9 Automation Engine
   - 8.10 Build Runner
   - 8.11 Test Runner
   - 8.12 Security Scanner
   - 8.13 Documentation Generator
   - 8.14 Screenshot Generator
   - 8.15 Git Intelligence
   - 8.16 Scheduler
   - 8.17 World Simulator (Optional Fun Module)
9. Hardware Role
10. Networking Model
11. Feature Groups
    - FG1: Project Intelligence Engine
    - FG2: Repository Indexing
    - FG3: RAG System
    - FG4: Ollama Integration
    - FG5: Build Intelligence
    - FG6: Automated Maintainer
    - FG7: Feature Testing System
    - FG8: Security Analysis
    - FG9: Documentation Generator
    - FG10: Git Intelligence
    - FG11: Portfolio Intelligence
    - FG12: Local Services
    - FG13: World Simulator
12. Recommended Technology Stack
13. Folder Structure
14. Security Model
15. Future Roadmap
    - 15.1 High-Value Features (Post-MVP)
    - 15.2 Long-Term Vision
16. Agent Development Guidelines
17. Changelog

---

## 1. Vision

> **North Star:** Project Sentinel is a local-first, privacy-respecting personal software operations platform that continuously understands, maintains, tests, documents, and analyzes the user's software projects.

Project Sentinel transforms a dedicated laptop into an always-on personal software operations center. Instead of scattered folders and forgotten projects, Sentinel builds a living model of everything the user has created. It remembers why each project exists, verifies it still works, and helps maintain it forever.

Sentinel acts as:
- A **Personal CI/CD Server**
- A **Project Intelligence Platform**
- A **Local AI Assistant**
- A **Software Maintenance System**
- A **Repository Knowledge Engine**
- An **Automated QA System**
- A **Development History Archive**

The final system runs locally on a dedicated laptop and exposes services through a local web dashboard and API.

---

## 2. Goals

### Must-Have (MVP)

- Continuously understand and index personal software projects
- Use SQLite as the primary knowledge database (zero-config, file-based, ideal for a local-first laptop platform)
- Expose project intelligence through a local web dashboard and API
- Automate CI/CD: discover build/test commands, run them, report status
- Perform automated security scanning (dependencies, secrets, static analysis)
- Generate and maintain project documentation automatically
- Capture screenshots of running applications for visual regression testing
- Track Git history and provide intelligent answers about code evolution
- Compute project health scores and portfolio readiness metrics
- Integrate with local Ollama for AI-powered summaries and explanations
- Store all knowledge in a structured, queryable database
- Enable RAG-based natural language querying across all projects
- Run scheduled tasks (daily builds, weekly security scans, etc.)
- Include optional World Simulator entertainment module

### Should-Have (Post-MVP)

- Cross-project dependency drift detection
- Automated code duplication finder
- Tech debt heatmap across portfolio
- Dependency chain visualization
- "What-if" scenario analysis (impact of removing a function/module)

### Could-Have (Future)

- Optional VPN access for remote management
- Public API exposure behind reverse proxy (explicit opt-in)
- Multi-laptop federation (index projects across devices)
- Exportable project models (share architecture summaries)

---

## 3. Non-Goals

- **Not a generic chatbot.** Sentinel uses AI only for interpretation, not conversation.
- **Not a replacement coding agent.** It does not write or edit code autonomously.
- **Not an autonomous programmer.** All actions are driven by known workflows.
- **Not a cloud service.** Everything runs locally; no mandatory cloud sync.
- **Not a black-box AI system.** All deterministic tasks are handled natively.
- **Does not host public services** by default — local network only.

---

## 4. Design Philosophy

| Principle | Description |
|-----------|-------------|
| **Local-first** | All data, processing, and services run on the user's device. |
| **Privacy-focused** | No telemetry, analytics, or automatic cloud uploads. |
| **Always available** | Designed to run 24/7 on a dedicated machine. |
| **Project-aware** | Understands individual projects and their relationships. |
| **History-aware** | Leverages Git history, changelogs, and evolution data. |
| **Deterministic when possible** | Uses AI only for non-deterministic tasks (summaries, explanations, natural language search). |
| **Useful intelligence** | Provides actionable insights, not just dashboards. |
| **Long-term ownership** | Designed to be maintainable and extensible over years. |

---

## 5. Project Rules

These are the "constitution" of Project Sentinel. They must be upheld in every decision.

1. **Everything stays local.** Data never leaves the device unless explicitly exported by the user.
2. **AI is assistive, never autonomous.** AI generates summaries, explanations, and search results. It never executes irreversible actions.
3. **Determinism over generation.** Known workflows (builds, tests, scans) are deterministic. AI is used only for interpretation.
4. **One responsibility per module.** Each component does exactly one thing well.
5. **Projects are known entities.** Sentinel indexes known repositories, not arbitrary web apps.
6. **Every feature must be testable.** No feature ships without unit or integration tests.
7. **Transparency over opacity.** All decisions are traceable and explainable.
8. **Simplicity over optimization.** Prefer readable, maintainable code over premature optimization.

---

## 6. MVP Definition

The MVP is the minimal set of features that demonstrates the core value proposition: **automatically maintain, understand, and document the user's personal software portfolio.**

### In Scope

| Component | Status |
|-----------|--------|
| Local web dashboard | Core |
| FastAPI backend server | Core |
| Repository indexer | Core |
| Knowledge database (SQLite) | Core |
| RAG system (ChromaDB, embedded) | Core |
| CI/CD automation (build/test runners) | Core |
| Security scanner | Core |
| Documentation generator | Core |
| Screenshot generator | Core |
| Git intelligence engine | Core |
| Portfolio health scoring | Core |
| Local API gateway | Core |
| Scheduler (task runner) | Core |
| World Simulator (optional module) | Optional |

### Out of Scope (MVP)

- Cross-project dependency drift detection
- Advanced ML models beyond Ollama
- Public API exposure
- Remote access via VPN
- Multi-device federation

### Success Criteria

The MVP is complete when a user can:

1. Start the Sentinel server on their laptop
2. Add a local repository to indexing
3. See the project appear on the dashboard with tech stack, health score, and last scan time
4. Trigger a manual build/test cycle and view results
5. Ask a natural language question like "Why was the CSV import feature added?" and get an answer
6. Generate up-to-date documentation for a project
7. See portfolio-level health overview across all tracked projects
8. Optionally interact with the World Simulator

---

## 7. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
│                                                                 │
│  ┌─────────────────┐      ┌──────────────────────┐              │
│  │   Web Dashboard │◄────►│   Local API Gateway  │              │
│  │  (React/Vite)   │      │    (FastAPI)         │              │
│  └─────────────────┘      └──────────┬───────────┘              │
└───────────────────────────────────────┼──────────────────────────┘
                                        │ HTTP/REST + WebSocket
                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Project Sentinel Server                       │
│                        (Python Backend)                         │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │           Project Intelligence Engine                  │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │     │
│  │  │Repo Indexer │  │Knowledge DB │  │     RAG      │   │     │
│  │  │             │  │  (SQLite)   │  │  (ChromaDB)  │   │     │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘   │     │
│  │         │                │                │            │     │
│  │         └────────► Ollama AI Service ◄────┘            │     │
│  │                    (Summaries/Explanations)             │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │             Automation Engine                          │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │     │
│  │  │Scheduler │ │Build Run.│ │Test Run. │ │Sec. Scan  │  │     │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │             Intelligence Subsystems                    │     │
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────┐        │     │
│  │  │Git Intel.  │ │Doc. Gen.   │ │Screenshot Gen│        │     │
│  │  └─────────────┘ └─────────────┘ └────────────┘        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              World Simulator (Optional)                 │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              External Integrations (Local Network)               │
│  ┌──────────┐                      ┌──────────────┐                    │
│  │  Ollama  │                      │  Local API   │                    │
│  │          │                      │ (Sentinel)   │                    │
│  └──────────┘                      └──────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **Indexing**: Repository → Indexer → Knowledge Database + Embeddings → ChromaDB
2. **AI Analysis**: Knowledge + Git History → Ollama → Summaries/Explanations Stored
3. **Automation**: Scheduler → Build/Test/Scan → Results stored → Health scores updated
4. **Query**: User question → RAG (ChromaDB search) → Context + Question → Ollama → Answer
5. **Observability**: Dashboard polls API for health scores, job status, portfolio metrics

---

## 8. Component Deep-Dives

### 8.1 Project Sentinel Server

**Purpose**: Central orchestration hub for all subsystems.

**Responsibilities**:
- Manage HTTP API gateway (FastAPI)
- Coordinate background jobs and schedulers
- Persist all structured data (SQLite)
- Expose WebSocket endpoints for live updates

**Technology**: Python 3.11+, FastAPI, SQLModel, Uvicorn

### 8.2 Web Dashboard

**Purpose**: Visual interface for project observability and control.

**Responsibilities**:
- Display project galaxies, timelines, health cards
- Trigger manual builds/tests/imports
- Show RAG chat interface
- Present portfolio-level summaries
- Launch World Simulator interface

**Technology**: React 19+, TypeScript, Vite, TailwindCSS

### 8.3 Local API Gateway

**Purpose**: REST + WebSocket interface to all Sentinel capabilities.

**Responsibilities**:
- Expose CRUD APIs for projects, builds, tests, security scans
- Stream real-time job logs/status via WebSockets
- Proxy requests to Ollama RAG backend
- Validate authentication (optional API keys for trusted devices)

**Technology**: FastAPI, Pydantic v2, WebSockets

### 8.4 Project Intelligence Engine

**Purpose**: Transform raw repositories into structured knowledge.

**Responsibilities**:
- Detect project language, framework, dependencies
- Parse configuration files for build/test/deploy commands
- Generate AI-powered project summaries
- Estimate completion status and complexity

**Inputs**: Source code, READMEs, config files, Git history

**Outputs**: Structured project models stored in Knowledge Database

### 8.5 Repository Indexer

**Purpose**: Continuously scan and extract metadata from tracked repositories.

**Responsibilities**:
- Initial scan: detect language → detect framework → parse files → extract metadata → generate summaries → store knowledge
- Incremental updates: track file changes, rebuild affected indexes
- Support for Python, JavaScript, TypeScript, React, Electron, FastAPI, Flask, Node.js, SQL

**Future Expansion**: Unity, C#, Java, Go

### 8.6 Knowledge Database

**Purpose**: Central repository of all structured project knowledge.

**Technology**: SQLite via SQLModel/SQLAlchemy (file-based, zero-config; stored at `/data/sqlite/sentinel.db` by default)

**Schema Includes**:
- `projects` – Basic project metadata
- `repositories` – Git repo paths and configs
- `files` – Indexed file contents and metadata
- `dependencies` – Package/dependency listings
- `build_commands`, `test_commands`, `install_commands`
- `tests` – Test suite definitions and results
- `reports` – Aggregated scan/build/test reports
- `security_findings` – Vulnerability alerts and secret detections
- `ai_summaries` – Generated project/explanation summaries
- `git_commits`, `git_history` – Version control intelligence
- `documentation` – Auto-generated docs content

### 8.7 RAG System

**Purpose**: Enable natural language querying over project knowledge.

**Architecture**:
```
User Question
    ↓
ChromaDB Embedding Search
    ↓
Relevant Context Chunks
    ↓
Ollama LLM
    ↓
Natural Language Answer
```

**Use Cases**:
- "Explain why this test failed."
- "Summarize the architecture of Workflow Toolkit."
- "Find when the CSV import feature was added."
- "List all known projects using FastAPI."

**Technology**: ChromaDB (vector storage), Ollama (LLM inference), HuggingFace sentence-transformers (embeddings)

### 8.8 Ollama AI Service

**Purpose**: Provide local LLM inference for summaries, explanations, and analysis.

**Usage**:
- Generate project summaries from code/config/docs
- Explain build/test failures
- Provide natural language answers via RAG
- Classify and tag documentation sections

**Good Uses** (interpretive):
- "Summarize this README"
- "Why did this security scan flag this dependency?"

**Bad Uses** (deterministic, avoid):
- "Did this build pass?" → Use direct test result
- "List installed Python packages" → Query dependency tree

### 8.9 Automation Engine

**Purpose**: Orchestrate all automated maintenance workflows.

**Responsibilities**:
- Trigger builds, tests, and security scans
- Schedule recurring tasks (daily builds, weekly scans)
- Manage worker queues for parallelizable jobs
- Log and store results in Knowledge Database

**Technology**: Python workers, Celery or RQ (task queue), APScheduler (cron-like scheduling)

### 8.10 Build Runner

**Purpose**: Discover and execute project build commands.

**Responsibilities**:
- Parse package.json, pyproject.toml, Makefile, etc. for build scripts
- Execute builds in isolated environments (Docker containers or virtualenvs)
- Capture logs, exit codes, artifacts
- Store results for historical analysis

**Example Workflow**:
```
git pull
→ install dependencies
→ npm run build
→ pytest
→ security scan
→ generate docs
→ generate screenshots
→ update health dashboard
```

### 8.11 Test Runner

**Purpose**: Discover and run project test suites automatically.

**Responsibilities**:
- Parse test configurations (`pytest.ini`, `jsconfig`, `.mocharc`)
- Execute tests with proper environment setup
- Collect pass/fail metrics, logs, coverage reports
- Integrate with Feature Testing System for UI/API tests

### 8.12 Security Scanner

**Purpose**: Perform mostly-deterministic security checks on indexed projects.

**Tools**:
- Dependency scanning (pip-audit, npm audit)
- Vulnerability checks (Snyk, Trivy)
- Secret detection (gitleaks, truffleHog)
- Static analysis (bandit, ESLint, Semgrep)

**AI Role**: Provide explanations for findings:
> Finding: API key detected  
> Severity: High  
> AI explanation: Move secrets into environment variables.

### 8.13 Documentation Generator

**Purpose**: Automatically generate and maintain project documentation.

**Generates**:
- README updates
- Architecture summaries
- Changelogs
- Feature documentation
- Sprint summaries

### 8.14 Screenshot Generator

**Purpose**: Capture visual states of running applications for regression testing.

**Responsibilities**:
- Launch Electron apps or browser-based UIs
- Navigate to key views
- Capture and store screenshots
- Compare against baselines for visual diffs

**Technology**: Playwright, Puppeteer, Electron Testing Tools, PyAutoGUI

### 8.15 Git Intelligence

**Purpose**: Extract actionable insights from Git history.

**Tracks**:
- Commits, branches, merges
- Activity timelines
- Feature evolution
- Project churn and stability metrics

**Answers Questions Like**:
- "Why was this added?"
- "Who last touched this file?"
- "What changed between v1.0 and v2.0?"

### 8.16 Scheduler

**Purpose**: Manage recurring automated tasks across all projects.

**Responsibilities**:
- Daily builds and tests
- Weekly security scans
- Monthly documentation regeneration
- Quarterly portfolio health reports

**Technology**: APScheduler or Celery Beat

### 8.17 World Simulator (Optional Fun Module)

**Purpose**: A separate entertainment subsystem — a deterministic, persistent
"ant farm" simulation (Sprint 9). Settlements grow, build roads, expand,
trade, and sometimes collapse. No AI in the simulation loop; AI is at most
optional flavor on event text.

**Design Principles**:
- Completely decoupled from project operations (own SQLite DB, own tables)
- Deterministic: seeded per-day RNG, terrain as a pure function of `(x, y, seed)`
- Runs inside the existing stack (Celery beat `world-sim-tick`); no container
- God tools: manual tick, reset/re-seed, time acceleration, forced disasters

**How It Works**:
```
Daily Tick (beat, every SENTINEL_WORLD_SIM_TICK_SECONDS)
    ↓
simulate_day (seeded RNG): food/growth → construction → expansion → trade
    → raids → discoveries → festivals → disasters → collapse
    ↓
Persist (world_settlements / world_roads / world_events)
    ↓
Dashboard Display ("World Day 482", map + event feed)
```

**Example Output**:
```
World Day 482

Events:
- Marniv Vale reached level 3.
- Trade thrives between Marniv Vale and Kel Harbor.
- A flood struck Kel Harbor; the survivors are rebuilding, stronger than before.
```

**Technology**: Lightweight Flask app + small Ollama model + JSON state file

---

## 9. Hardware Role & Infrastructure Services

Sentinel is not just Project Intelligence — its identity is a **Home Development Server with Project Intelligence as its flagship capability**. The services below are not random add-ons; they are infrastructure running on the same always-on machine, and they make the server genuinely useful even when it is not indexing code or answering questions.

### 9.1 Two-machine topology

| Machine | Role | Hardware |
|---------|------|----------|
| Laptop (`desktop-slur95L`, `192.168.4.40`) | Always-on **home server** — hosts Pi-hole + Ollama (shared AI), future home of the Sentinel API | Dell Inspiron 13 5310, Iris Xe, 16 GB RAM |
| Desktop (`192.168.4.28`) | **Dev workstation** — Sentinel repo, airadio, browser dashboard; Ollama runs here only as a manual fallback | iBUYPOWER, Ryzen 5 5500, 16 GB RAM |

### 9.2 Infrastructure Services

Initial services hosted by the home server (laptop):

- **Ollama** — local AI inference shared by every device on the network (`http://192.168.4.40:11434`). Laptop runs it natively (Windows); Sentinel and airadio reach it over the LAN via `SENTINEL_OLLAMA_HOST` / `OLLAMA_URL`.
- **Local API** — Sentinel modules and future desktop/mobile apps.
- **Background scheduler** — indexing, builds, nightly scans, maintenance jobs.

(Pi-hole was deployed alongside Sentinel from Sprint 8.5 to 13, removed from
the stack in Sprint 15, and decommissioned entirely in v1.16.1 — the laptop's
router DNS is back to Automatic (see docs/pi-hole-idea.md for why it was never
the project's purpose).)

The laptop acts as:

- **Always-on home server**: Runs 24/7, accessible via local network
- **Local AI inference machine**: Hosts Ollama for summaries/explanations, shared by all devices
- **Project analysis machine**: Indexes and analyzes code repositories
- **Automation worker**: Executes builds, tests, scans on schedule
- **Network service host**: Exposes web dashboard, local API, Pi-hole

Supports:
- Ollama (local LLM inference, shared across the LAN)
- Pi-hole (network-wide ad blocking)
- Web services (dashboard, API)
- Background jobs (builds, tests, scans)
- Database storage (SQLite, ChromaDB)
- Repository indexing (file system access)

---

## 10. Networking Model

```
Desktop (dev workstation)   Phone          Tablet
    192.168.4.28                │               │
     │             ─────────────┼───────────────┘
     └─────────────┼────────────┘
                   │
             Home Network
                   │
                   ▼
        Home server laptop (always-on)
          192.168.4.40 (DHCP-reserved)

Services:
  http://192.168.4.40:8000      Sentinel dashboard + API (native install, Sprint 15)
  http://192.168.4.40:11434     Ollama (shared AI inference)
  http://192.168.4.28:5173      Sentinel dashboard (desktop dev)
  http://192.168.4.28:8000      Sentinel API (desktop dev)
  (Pi-hole retired v1.16.1 — router DNS is back on Automatic)
```

**Connectivity Rules**:
- Sentinel binds `127.0.0.1` (or `SENTINEL_HOST`); the laptop's Ollama binds all
  interfaces (`0.0.0.0`) so LAN devices can use it
- Router DHCP keeps the **reservation** for `192.168.4.40`; DNS is on
  **Automatic** since Pi-hole was decommissioned (v1.16.1) — Sentinel never
  participates in DNS
- No public exposure by default
- Optional future enhancement: WireGuard/OpenVPN for secure remote access

---

## 11. Feature Groups

### Feature Group 1: Project Intelligence Engine

**Purpose**: Transform repositories from collections of files into structured knowledge.

**Input**:
- Source code
- Documentation, README files, architecture documents
- Sprint documents
- Git history
- Configuration files
- Dependencies

**Output**:
- Structured project model with:
  - Tech stack (React, FastAPI, SQLite)
  - Features list with completion status
  - Run commands (backend, frontend, build, test)
  - Current state estimation (e.g., 82% complete)

### Feature Group 2: Repository Indexing

**Initial Scan Pipeline**:

```
Repository
    ↓
Detect language
    ↓
Detect framework
    ↓
Parse files
    ↓
Extract metadata
    ↓
Generate summaries
    ↓
Store knowledge
```

**Supported Languages/Frameworks**:
- Python, JavaScript, TypeScript
- React, Electron, FastAPI, Flask, Node.js
- SQL

**Future Expansion**: Unity, C#, Java, Go

### Feature Group 3: RAG System

**Distinction**:
- **Project Intelligence** stores knowledge.
- **RAG** retrieves knowledge for AI-powered Q&A.

**Use Cases**:
- Explain project architecture
- Find previous design decisions
- Locate specific features
- Understand historical context

### Feature Group 4: Ollama Integration

**Provides**:
- Summaries of code/config/docs
- Explanations of build/test failures
- Documentation generation
- Failure analysis
- Natural language search

**Good**: "Explain why this test failed."
**Bad**: "Did this test pass?" → Use direct result

### Feature Group 5: Build Intelligence

**Discovers and Stores**:
- Install commands
- Startup commands
- Build commands
- Test commands
- Deployment commands

**Purpose**: Never forget how to run old projects.

### Feature Group 6: Automated Maintainer

**Core Workflow**:
```
Git update
    ↓
Install dependencies
    ↓
Build
    ↓
Run tests
    ↓
Security scan
    ↓
Generate documentation
    ↓
Generate screenshots
    ↓
Update project health
```

### Feature Group 7: Feature Testing System

**Important**: This is NOT unknown app exploration.
- Projects are known
- Tests are defined
- Focus on UI testing, API testing, feature regression testing, screenshot capture

**Possible Technologies**:
- Playwright
- Selenium
- PyAutoGUI
- Electron testing tools

### Feature Group 8: Security Analysis

**Mostly Deterministic**

**Tools**:
- Dependency scanning
- Vulnerability checks
- Secret detection
- Static analysis

**AI Role**: Explains findings in plain language.

**Example**:
> Finding: API key detected  
> Severity: High  
> AI explanation: Move secrets into environment variables.

### Feature Group 9: Documentation Generator

**Auto-generates**:
- README updates
- Architecture summaries
- Changelogs
- Feature documentation
- Sprint summaries

### Feature Group 10: Git Intelligence

**Tracks**:
- Commits
- Activity
- Feature history
- Project evolution

**Answers**:
- "Why was this added?"

**Example**:
```
Added during Sprint 5
Reason: Support CSV imports.
Modified later: Added validation.
```

### Feature Group 11: Portfolio Intelligence

**Shipped (Sprint 10)**: deterministic health scoring, candidate ranking and a
feature matrix — no AI. See docs/02 §14.5.

**Generates**:
- Per-project health scores (0-100): build 30 · tests 30 · security 25 · docs 15;
  components with no data yet score 0
- Ranked best candidates (score ≥ min_score) with missing items listed
- Feature matrix across projects × features (✓/⚠/✗)

**Example**:
```
Sample Python Project            Score: 92.5
  Build: ✓ passing   Tests: ✓ passing
  Security: ✓ clean  Docs: 50%

Best candidates: [Sample Python Project]
Feature matrix:   build  test  docs  security  screenshots
                  ✓      ✓     ⚠     ✓         ✗
```

**Endpoints**: `GET /portfolio/scores`, `GET /portfolio/best-candidates?min_score=70`,
`GET /portfolio/feature-matrix`. **Frontend**: `/portfolio` page (health cards,
candidates, matrix). Observatory (galaxy/timeline/architecture) shipped in
Sprint 10.5 (docs/02 §14.6).

### Feature Group 12: Local Services

**Includes**:
- Pi-hole / AdGuard (network-wide ad blocking)
- Ollama (local AI)
- Local API (central communication layer)

**Example Endpoints**:
```http
GET  /projects
GET  /health
POST /test
POST /build
POST /ask
```

### Feature Group 13: World Simulator (Optional Fun Module)

(See Section 8.17 for full details)

A separate entertainment subsystem:
- Deterministic persistent world simulation (settlements, roads, trade, disasters)
- Own SQLite database (`data/world_sim/world.db`), isolated from project data
- Runs in the existing stack via Celery beat — no separate container
- Optional AI narrative flavor; never affects simulation state

---

## 12. Recommended Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | Web framework, API endpoints |
| SQLModel | 0.14+ | ORM for SQLite (built on SQLAlchemy) |
| SQLite | 3.35+ | Primary knowledge database (file-based) |
| Pydantic | 2.5+ | Data validation/serialization |
| Celery | 5.3+ | Task queue for background jobs |
| APScheduler | 3.10+ | Cron-like task scheduling |
| Uvicorn | 0.29+ | ASGI server |
| pytest | 8.0+ | Testing framework |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19+ | UI library |
| TypeScript | 5.3+ | Type safety |
| Vite | 5.0+ | Build tool |
| TailwindCSS | 3.4+ | Styling/framework |
| React Query | 5.0+ | Server state management |
| React Router | 6.14+ | Client-side routing |
| Axios | 1.6+ | HTTP client |
| Recharts | 2.0+ | Data visualization (galaxy, timeline) |
| Leaflet | 1.9+ | Map-based galaxy view (if geospatial) |

### AI & Search

| Technology | Purpose |
|------------|---------|
| Ollama | Local LLM inference (summaries, explanations, RAG answers) |
| ChromaDB (embedded) | Vector database for RAG embeddings (python client, persistent directory) |
| Sentence Transformers | Embedding model (all-MiniLM-L6-v2) — alternative to Ollama embeddings |

### Automation & Testing

| Technology | Purpose |
|------------|---------|
| Docker | Isolated build/test environments |
| Playwright | UI testing and screenshot capture |
| Gitleaks | Secret detection |
| Trivy | Dependency vulnerability scanning |
| Bandit | Python static analysis |
| ESLint/Security Plugin | JS/TS static analysis |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| SQLite | Structured knowledge storage (file-based) |
| ChromaDB | Vector embeddings storage (embedded) |
| Uvicorn | ASGI server serving API + dashboard from one process (Sprint 15: no nginx) |
| APScheduler | In-process background scheduler (Sprint 7; Redis/Celery deferred, Rule 3) |

### Why This Stack

- **FastAPI**: Excellent for both REST APIs and async background tasks; type-safe with Pydantic
- **SQLite**: Zero-config, file-based, no service to manage — ideal for a local-first laptop platform
- **React/Vite**: Modern, performant frontend with excellent dev experience
- **Ollama**: Clean HTTP API, no cloud dependency, strong community
- **ChromaDB**: Python-native, easy to integrate with existing pipelines
- **Playwright**: Industry standard for UI automation and visual testing

---

## 13. Folder Structure

```
sentinel/
├── docs/
│   ├── 01_Master_Architecture.md    ← This file
│   ├── 02_Implementation_Guide.md
│   ├── 03_Sprint_Plan.md
│   └── resources/                    # Diagrams, templates, assets
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── projects.py       # Project CRUD + intelligence
│   │   │   │   ├── builds.py         # Build execution/endpoints
│   │   │   │   ├── tests.py          # Test execution/endpoints
│   │   │   │   ├── security.py       # Scan endpoints
│   │   │   │   ├── docs.py           # Doc generation endpoints
│   │   │   │   ├── git.py            # Git intelligence endpoints
│   │   │   │   ├── portfolio.py      # Portfolio health endpoints
│   │   │   │   └── world_sim.py      # World simulator endpoints
│   │   ├── core/
│   │   │   ├── config.py             # Settings, env vars
│   │   │   ├── logging.py            # Logger setup
│   │   │   ├── security.py           # Authn/authz
│   │   │   └── exceptions.py         # Custom exceptions
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py         # SQLite connection
│   │   │   ├── models.py             # SQLAlchemy table definitions
│   │   │   └── migration.py          # Migration runner
│   │   ├── schemas/                  # Pydantic schemas
│   │   │   ├── project.py
│   │   │   ├── build.py
│   │   │   ├── test_result.py
│   │   │   ├── security_finding.py
│   │   │   └── health.py
│   │   ├── repositories/             # Data access layer
│   │   │   ├── base.py
│   │   │   ├── project.py
│   │   │   ├── build.py
│   │   │   ├── test_result.py
│   │   │   └── security_finding.py
│   │   ├── services/                 # Business logic layer
│   │   │   ├── indexer.py            # Repository indexer
│   │   │   ├── intelligence_engine.py
│   │   │   ├── build_runner.py
│   │   │   ├── test_runner.py
│   │   │   ├── security_scanner.py
│   │   │   ├── doc_generator.py
│   │   │   ├── screenshot_generator.py
│   │   │   ├── git_intelligence.py
│   │   │   ├── portfolio_intelligence.py
│   │   │   ├── rag_service.py
│   │   │   ├── scheduler.py
│   │   │   └── world_simulator.py
│   │   ├── parsers/                  # Language/framework parsers
│   │   │   ├── base.py
│   │   │   ├── python_parser.py
│   │   │   ├── javascript_parser.py
│   │   │   ├── typescript_parser.py
│   │   │   ├── react_parser.py
│   │   │   ├── fastapi_parser.py
│   │   │   ├── flask_parser.py
│   │   │   ├── node_parser.py
│   │   │   └── sql_parser.py
│   │   ├── workers/                  # Celery tasks
│   │   │   ├── build_tasks.py
│   │   │   ├── test_tasks.py
│   │   │   ├── security_tasks.py
│   │   │   └── doc_tasks.py
│   │   ├── utils/
│   │   │   ├── language_detector.py
│   │   │   ├── framework_detector.py
│   │   │   └── command_extractor.py
│   ├── tests/                        # Backend unit + integration tests
│   │   ├── conftest.py
│   │   ├── test_parsers.py
│   │   ├── test_indexer.py
│   │   ├── test_build_runner.py
│   │   ├── test_services.py
│   │   └── test_e2e.py
│   ├── scripts/
│   │   ├── run.sh                    # Start backend server
│   │   └── migrate.sh
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx                  # React entry point
│   │   ├── app.tsx                   # Root component
│   │   ├── api/                      # Axios client + typed hooks
│   │   │   ├── client.ts
│   │   │   ├── projects.ts
│   │   │   ├── builds.ts
│   │   │   ├── tests.ts
│   │   │   ├── security.ts
│   │   │   └── portfolio.ts
│   │   ├── components/
│   │   │   ├── ProjectGalaxy.tsx
│   │   │   ├── ProjectTimeline.tsx
│   │   │   ├── HealthCard.tsx
│   │   │   ├── ArchitectureMap.tsx
│   │   │   ├── FeatureMatrix.tsx
│   │   │   ├── PortfolioView.tsx
│   │   │   ├── WorldSimulator.tsx
│   │   │   └── layouts/
│   │   ├── contexts/
│   │   │   ├── ProjectContext.tsx
│   │   │   ├── BuildContext.tsx
│   │   │   └── UIContext.tsx
│   │   ├── hooks/
│   │   │   ├── useProjects.ts
│   │   │   ├── useBuilds.ts
│   │   │   ├── useSearch.ts
│   │   │   └── useWorldSim.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── ProjectDetails.tsx
│   │   │   ├── BuildHistory.tsx
│   │   │   ├── SecurityFindings.tsx
│   │   │   ├── GitTimeline.tsx
│   │   │   ├── Portfolio.tsx
│   │   │   └── WorldSimulatorPage.tsx
│   │   ├── routes/
│   │   │   └── index.tsx
│   │   ├── styles/
│   │   └── lib/
│   │       └── utils.ts
│   ├── public/
│   ├── vite.config.ts
│   ├── package.json
│   └── tsconfig.json
├── scripts/
│   ├── install_service.py              # Windows autostart (Task Scheduler)
│   ├── build.py                        # Verify + stage the dashboard
│   └── release.py                      # Package release zip
├── run.py                              # Single starting point: checks + uvicorn
├── AGENTS.md                           # Project rules for AI agents
├── .python-version
├── pyproject.toml                      # Root pyproject (workspace)
└── README.md
```

---

## 14. Security Model

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Local network intrusion | Bind services to localhost by default; optional firewall rules |
| Unauthorized API access | Optional API key authentication for trusted devices |
| Secret exposure in repos | Gitleaks scanning during indexing phase |
| Dependency vulnerabilities | Automated weekly scans via Trivy |
| AI hallucination | Strict prompt engineering; deterministic tasks handled natively |
| Unintended data exfiltration | No outbound network calls except to Ollama (localhost:11434) |

### Authentication

- **Default**: No authentication (localhost only)
- **Optional**: API key-based auth for trusted devices on local network
- **Future**: LDAP/SSO integration for team environments

### Encryption

- **At rest**: SQLite file encryption (optional, via SQLCipher); ChromaDB file encryption (optional)
- **In transit**: HTTPS via self-signed cert (development) or Caddy/Nginx reverse proxy (production)

### Data Handling

- All raw repository copies stored in `/data/local_repos/`
- Generated artifacts cached in `/data/cache/`
- Sensitive findings (secrets, vulns) stored encrypted with Fernet
- Logs rotated daily; max 7 days retention

### Compliance Notes

- GDPR: All PII stays local
- SOC 2 Type II: Not applicable (single-user system)
- HIPAA: Depends on use case (no built-in healthcare-specific controls)

### AI Safety

- All AI-generated content marked with provenance metadata
- Deterministic tasks (build/test/pass/fail) bypass AI entirely
- Prompt templates stored in `/backend/app/data/prompts/`
- LLM audit log tracks all AI interactions

---

## 15. Future Roadmap

### 15.1 High-Value Features (Post-MVP)

These features significantly enhance Sentinel's utility but can be deferred until after the core MVP is stable:

1. **Cross-Project Dependency Drift Detector**
   - Monitor version mismatches across all projects simultaneously
   - Alert when newer versions introduce breaking changes
   - Suggest coordinated upgrade paths

2. **API Schema Evolution Tracker**
   - Automatically document how APIs change over time
   - Detect breaking vs. non-breaking changes
   - Generate changelogs for internal APIs

3. **Code Ownership & Handoff Helper**
   - Build a model of who knows what in the codebase (via Git history)
   - Generate handoff documentation for team transitions
   - Highlight knowledge silos

4. **Cross-Project Code Duplication Finder**
   - Find when user copy+pastes code between projects
   - Suggest extracting shared libraries
   - Estimate refactor ROI

5. **Dependency Chain Visualization**
   - Interactive graph of how dependencies connect across projects
   - Identify shared libraries worth extracting
   - Spot circular dependency risks

6. **Tech Debt Heatmap**
   - Aggregate TODOs, FIXMEs, skipped tests, complexity metrics
   - Prioritize cleanup efforts across portfolio
   - Track improvement over time

7. **"What If" Scenario Simulator**
   - "If I delete this function, which projects break?"
   - Uses knowledge graph to propagate dependency impact
   - Plan refactors with confidence

8. **Local LLM Fine-Tuning Playground**
   - Fine-tune small models on user's own code
   - Code completion suggestions matching user's style
   - Experimental, fully isolated from core operations

9. **Automated Documentation QA**
   - Cross-check if documentation matches actual code behavior
   - Flag drift between READMEs and implementations
   - Ensure docs stay accurate over time

10. **Multi-Laptop Federation**
    - Index and analyze projects across multiple devices
    - Sync portfolio-level health scores
    - Centralized observability dashboard

11. **Job Hiring Portfolio Assistant**
    - Automatically identify best portfolio candidates for job applications
    - Highlight missing elements (demo videos, screenshots, better READMEs)
    - Generate cover letters referencing relevant past projects

12. **Portfolio Project Galaxy View**
    - Visual map showing relationships between all projects
    - Shared technologies, reused components, similar features
    - Interactive exploration of your entire software history
    - Note: core Galaxy/Timeline/FeatureMatrix views ship in the MVP (Sprint 10); this roadmap item covers the extended interactive graph experience

### 15.2 Long-Term Vision

- Open-source release with community plugin support
- Enterprise variant for team software portfolios
- Integration with popular IDEs (VS Code extension)
- Mobile app companion for on-the-go portfolio review
- Natural language project creation ("Create a Flask todo app")

---

## 16. Agent Development Guidelines

When contributing to or extending Project Sentinel, agents should follow these principles:

1. **Always prefer deterministic logic over AI** for anything involving correctness or security.
2. **Document every AI-generated summary** with clear provenance metadata.
3. **Keep changes modular** — one responsibility per module/service/component.
4. **Write tests for every new endpoint, service method, and utility function.**
5. **Run all existing tests before committing** (`pytest -n auto`)
6. **Follow existing code formatting standards** (black, isort, flake8 for Python; prettier+eslint for TS)
7. **Update relevant docs** when modifying architecture or APIs.

---

## 17. Changelog

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-09 | 1.17.2 | Living-week fixes. **No more re-embedding on restart**: `IndexerService._index_files` deleted + re-inserted every `project_file` row per scan, nulling `embedding_id` (and Chroma doc ids are the row ids) — auto index then re-embedded all 2.9k files after every restart; rows are now keyed by path, unchanged files keep id + embedding_id, only vanished files drop. **Shared Chroma client**: a startup burst of knowledge jobs constructed `PersistentClient`s concurrently and raced ChromaDB's shared-system registry (`'RustBindingsAPI' has no attribute 'bindings'` / `KeyError`) — `get_chroma_manager()` hands out one locked client per path. **Activity feed caching**: mount-seed re-runs when the WS opens and retries once after an empty first load, so cached history always shows on entering the dashboard (live frames still merge); persist failures now WARN (were debug — the laptop's history could vanish silently). **Embedding t/s**: `OllamaService.embed_with_metrics` (Ollama `prompt_eval_count/duration`) → knowledge progress ticks carry `tokens_per_second`, shown on the feed during indexing (generations/chat t/s unchanged). External Ollama clients (e.g. airadio) remain invisible by design — Sentinel only measures its own calls. Tests: +10 backend (incl. reindex-preserves-ids, vanished-file drop, singleton identity, embed counters, t/s) / 70 vitest | AI agent |
| 2026-08-11 | 1.17.6.2 | Laptop recovery: RAG chat + semantic search work again after a damaged index. **Probe fixed** (`ChromaManager.health`): the v1.17.6 `get(limit=1)` probe could pass while the query path raised (`Nothing found on disk`) — chat 503'd with the rebuild hint while the dashboard stayed healthy, so the rebuild banner/button never appeared; the probe now runs a real query with a stored embedding, the exact operation search uses. `reset()` tolerates `InternalError` on `delete_collection` (a broken store can raise on drop; the collection is being discarded anyway). **Auto-index always includes the AI architecture summary**: `queue_knowledge_index_unembedded` (startup scan + repo-sync pass) submits `run_index_knowledge` with `with_summary=True`; `ingest_project_summary` dedupes to once per project (existing `architecture` summary reused — no Ollama burn per scan; CLI `rag-index <project> --summary` forces a regenerate via `force_summary`). Dashboard "Include AI architecture summary" checkbox removed (redundant; API `with_summary` param kept). New projects and post-reset re-indexes get summaries automatically, so all-project questions are summary-first as designed. Deferred: summary regeneration on repo change (needs file-change detection — edits are never re-embedded today; the sync pass already knows changed repos, so the hook is cheap later). Tests: +5 backend, +1 frontend updated | AI agent |
| 2026-08-09 | 1.17.1 | Regression-fix & ops pass after the first living week. **Scanner false positive fixed**: `\bexec\s*\(` matched `session.exec(` because a dot is a word boundary — 17 of the laptop's 20 findings were SQLModel ORM calls in clean repos; attribute calls are now ignored (only bare identifiers match). **Sync feedback**: an unconfigured sync now publishes *why* on the live feed ("Repo sync skipped — token not configured"), and nothing-changed passes carry a `detail` header; `POST /api/v1/system/sync` (`{"full": bool}`) + header "Sync now" button run a background pass (409 when already running, activity events per pass). **Migration bug fixed**: `migrate_columns` only added missing columns to the *first* affected table — `ollamaquerylog.purpose` was silently absent (would crash chat history past the 5000-row ceiling); migrated tables are now verified via `PRAGMA table_info` and repaired per table. **Sync cadence**: `SENTINEL_SYNC_INTERVAL_MINUTES` default 15 → 1440 (daily; startup still syncs once; manual runs cover impatience). **C++ builds deferred** to Sprint 18 (Rule 4 — parser scope is out of control). Tests: regression tests for all four, 84 backend / 68 vitest green | AI agent |
| 2026-08-09 | 1.17 | Sprint 17 (Observability & UX pass): **live activity everywhere** — new in-process `ActivityBus` (`app/services/activity_bus.py`) records every notable event (syncs, knowledge indexing, builds, tests, security scans, Ollama generations with purpose) into a bounded `activity_event` table (5000-row ceiling, SQLite-lock serialized, best-effort) and fans them out over `/api/v1/ws/jobs` (welcome frame, events, 30 s heartbeat); new read-only `GET /api/v1/system/activity` (cap 500, newest first). Ollama calls carry a `purpose` label (query/summary/…) persisted on `ollama_query_log` (auto-migrated column) and shown in the activity stream. Frontend: global status bar under the header on every page (live dot, last event, Ollama purpose + tok/s from the event's eval metrics), always-visible sync pill ("Sync not configured" when unconfigured), Dashboard live-activity log panel replacing the old channel box (falls back to polling `/system/activity` when the socket is closed). **Knowledge chat persistence**: `ChatMessage` table + `GET/POST /api/v1/rag/chat/{project_id}` (SQLite-backed chat rooms per project), RagChat replays history and saves every exchange. KnowledgeExplorer refreshes index progress live while indexing activity flows. **Auto knowledge-index on startup**(config flag `SENTINEL_AUTO_INDEX_KNOWLEDGE`, default on): after the initial scan, projects with unembedded files are queued for RAG indexing (Ollama-gated, via shared `queue_knowledge_index_unembedded`). Galaxy labels + legend, portfolio chips with per-criterion reasons. **Foundational .env fix**: `config.py` env_file was `BASE_DIR.parent / ".env"` (home dir) since Sprint 0 — every `SENTINEL_*` override and the GitHub token were ignored by the native install; now loads the repo-root `.env`. Gate repair: `scripts/build.py`'s `ok`-chain masked failures (raw exit code 0 is falsy → lint/test failures never aborted) and ran flake8 at its default 79 cols; fixed to booleans + `--max-line-length=100`, and pre-existing lint stragglers cleared (unused imports, E712, W292). Tests: 271 backend green / 94.49 % cov, 63 vitest, gate green. Docs: §4.2 env table, changelogs v1.17 | AI agent |
| 2026-08-08 | 1.16.2 | Dashboard actually served: `app/main.py` still pointed at `frontend/dist` while the Sprint 15.1 build is staged at `backend/app/static` — on a Node-less laptop every non-API path 404'd, root showed only the Sprint-1 health JSON. Now serves the staged build (dev fallback to `frontend/dist` when absent) and `/` returns dashboard HTML; health stays at `/health` + `/api/v1/health`. SPA-fallback + root tests added. Docs: run commands tightened to the explicit venv path (`.\.venv\Scripts\python.exe run.py`; PowerShell ExecutionPolicy blocks `Activate.ps1`, activation never required): laptop.md, 02 §5.2/§13, AGENTS.md; confirmed the prebuilt dashboard ships in git (no Node rebuild on the laptop). Watch-dir default fixed too: was the dev box's hardcoded `C:\Users\j` (laptop startup check failed, 0 projects indexed) — now defaults to the current user's home (`Path.home()`), so the laptop user's `C:\Users\james` is found with no config (`.env` may still override). Tests: 257 backend green | AI agent |
| 2026-08-08 | 1.16.1 | Pi-hole decommissioned on the laptop (docs/laptop.md `Moving off Docker`): router DNS back to Automatic, docker system prune -a --volumes wipes the old stack + Pi-hole, Docker Desktop uninstalled, old Sentinel task removed; laptop now needs only Python (repo ships the staged dashboard in ackend/app/static — no Node). Docs: laptop.md migration section added, 01 §9.2/§10 and 02 §13 updated (Pi-hole retired, DNS Automatic) | User |
| 2026-08-08 | 1.16 | Sprint 15.1 (Native deployment, decommission Docker). Compose/Docker layer removed: docker-compose*.yml, docker/, scripts/dev.py deleted; 
un.py (repo root) is the single starting point — startup checks then uvicorn on 127.0.0.1:8000 (--check/--port/--reload/--service/--install/--uninstall); scripts/install_service.py registers the Sentinel Task-Scheduler task (pythonw run.py --service every 5 min, idempotent); scripts/build.py reworked (verify + --dist stages frontend into ackend/app/static, served same-origin by pp/main.py); scripts/release.py ships run.py + scripts + docs + ackend/app; SENTINEL_PORT replaces SENTINEL_API_PORT; §4.2 env table + §13 rewritten (native runbook, troubleshooting); laptop.md rewritten. Pi-hole left the stack — System-page panel + SENTINEL_PIHOLE_* removed. Frontend: /system panel + pi/system.ts types updated. Tests: packaging suite reworked for native artifacts. Docs: changelogs v1.16 | User + AI agent |
| 2026-08-07 | 1.15 | Sprint 15 (Performance tuning + final polish): repo sync now detects changes — HEAD is recorded before/after each `git pull --ff-only` (`git rev-parse --short HEAD`), only repos whose HEAD moved are re-indexed, an all-clean pass skips the scan entirely, and knowledge auto-index (v1.14) is narrowed to changed repos; every run persists to a new `SyncRun` table surfaced by `GET /api/v1/system/sync` (header pill shows last outcome). Portfolio scoring rework: build = 21 static (command detected) + 9 proven (green run), tests = 24 static (test files detected) + 6 proven — the static part survives a failed run; docs matrix green threshold lowered to 50%; new `GET /portfolio/summary` and a change-driven cache (cached `PortfolioScore` row is served until a build/test/security/file source is newer). Scanner skips self-scan false positives (`data/`, `fixtures/`, `.env`-template names; real `.env` still flagged). `GET /rag/index/status` reports embedded vs total files. Frontend: Dashboard shows real portfolio stats, header sync pill, Knowledge page index progress. Tests: 268 backend / 58 vitest. Docs: 02 §14.5 scoring + §13.4 sync + §2.3 status endpoint, changelogs v1.15 | User + AI |

  | 2026-08-07 | 1.14 | Sprint 12.2 (Bugs + UI pages): world-sim growth bugs fixed — new recruitment step (roles scale with population vs fixed bootstrap) + land capacity (`FARM_CAPACITY`), food-store cap (`MAX_FOOD_DAYS=20`, bounds trade growth), world cap (`MAX_ACTIVE_SETTLEMENTS=60`), road-only raids, skill caps at +45%/+90% — worlds now grow to ~60 settlements/58 roads naturally; regression test `test_roads_appear_from_natural_growth`. Non-UTF-8 file encoding hardening (repo sync can't abort on a latin-1 `requirements.txt`). Best-effort knowledge auto-index after repo sync (unembedded projects → RAG tasks when Ollama up). Real Projects/Builds/Security pages replace placeholders (run/trigger + history/log/findings UI, `api/tests.ts`). Details in impl guide §11/§13.4/§19, sprint plan v1.14 | User + AI |
| 2026-08-07 | 1.13 | Sprint 12.1 (Repo auto-sync + Pi-hole v6 auth fix + SMB revert): laptop project sync replaces the SMB share with **GitHub-backed auto-sync** — `RepoSyncService` (`services/sync_service.py`) lists GitHub repos via a read-only PAT (`SENTINEL_GITHUB_TOKEN`), `git clone`s missing ones, `git pull --ff-only` existing checkouts under `SENTINEL_PROJECTS_DIR` (local target mounted at `/data/projects`), then re-indexes; CLI `sentinel sync` + Celery beat `repo-sync` (SENTINEL_SYNC_INTERVAL_MINUTES, default 15). §11 system surface Pi-hole client fixed for v6: session auth (`POST /api/auth` + `X-FTL-SID`; the v5 `X-FTL-API-KEY` header is gone). Desktop SMB plumbing reverted. Details in impl guide §13.4, sprint plan v1.13 | User + AI |
| 2026-08-06 | 1.12 | Sprint 12 (Home Server + System page): §9.1 topology realized — laptop runs the whole stack via one compose file; new `frontend` nginx container serves the dashboard at `http://192.168.4.40:8080` (no Tauri; browser is the shipped UX). §10 networking + deployment updated: `docker-compose.dev.yml` explicit dev overrides (bare `docker compose up` = prod), env-overridable `SENTINEL_*` (Ollama host, projects dir via SMB share, API port). New §7.3-ish system surface: `/api/v1/system/*` read-only (Ollama availability/models/tokens-per-sec from logged `OllamaQueryLog`; Pi-hole v6 read-only stats; startup checks). Packaging `scripts/build.py`/`release.py`. Details in impl guide §13.4, sprint plan v1.12 | User + AI agent |
| 2026-08-05 | 1.10.1 | Sprint 10.5 (Observatory): FG11 extended — determinism-only project overviews: shared-technology galaxy graph (key `GET /observatory/galaxy`), activity timeline (`/timeline?days=`, project-created/commit/build/test/finding), per-project architecture trees from indexed file paths (`/architecture/{id}`). New frontend `/observatory` page (ProjectGalaxy SVG, ProjectTimeline, ArchitectureMap). Details in impl guide §2.11, §14.6 | User + AI agent |
| 2026-08-05 | 1.10 | Sprint 10 (Portfolio Intelligence): FG11 rewritten from "readiness reports" to the shipped implementation — deterministic health scoring (build 30 / tests 30 / security 25 / docs 15, missing = 0; latest build log, test pass ratio, security severity penalties, README/Markdown/docs file ratio), `PortfolioScore` upsert-on-read, best-candidate ranking with missing items, feature matrix (✓/⚠/✗, screenshots ✗ until a screenshot feature exists), endpoints `GET /api/v1/portfolio/scores|best-candidates|feature-matrix`, frontend `/portfolio` page (HealthCard, FeatureMatrix). Observatory (galaxy/timeline/architecture) deferred to Sprint 10.5 | User + AI agent |
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1): §8.17 + FG13 rewritten from "AI world in its own container" to the shipped deterministic ant-farm — own SQLite DB (`data/world_sim/world.db`), seeded per-day RNG (terrain = pure `(x,y,seed)` hash), skill system (survival XP → levels 1–5, "build back stronger"), runs in-stack via Celery beat `world-sim-tick` (no new container), god tools (manual tick/reset/accelerate/disaster). New frontend `/world` route with 2D canvas map, settlement inspector, event feed. Details in impl guide §11, §2.9, §5.1 | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): §9 rewritten as Hardware Role & Infrastructure Services — two-machine topology (laptop `desktop-slur95L` 192.168.4.40 = always-on home server hosting Pi-hole + shared Ollama; desktop 192.168.4.28 = dev workstation), service list and home-server responsibilities; §10 Networking Model updated to real LAN IPs, Pi-hole admin (8053) + Ollama (11434) service endpoints, DHCP reservation + LAN DNS rule. Backend/worker `SENTINEL_OLLAMA_HOST` now points at the laptop (`http://192.168.4.40:11434`); the `ollama` compose profile remains a desktop-local fallback | User + AI agent |
| 2026-08-03 | 1.0 | Initial draft based on idea.md | User |
| 2026-08-04 | 1.1 | Sprint 0 decision lock: SQLite as primary DB (was PostgreSQL), ChromaDB embedded (no container), React 19, naming alignment (schemas/, rag_service.py, parsers/), single backend/tests/ | User + AI agent |
