# Project Sentinel â€” Master Architecture

> **Version:** 1.1
> **Status:** Draft â€” Phase 0 (Pre-MVP)
> **Audience:** Developers, AI coding agents, project maintainers
> **Related:** See `docs/02_Implementation_Guide.md` for technical specs, `docs/03_Sprint_Plan.md` for build phases

This is the single source of truth for what Project Sentinel is and how it is structured. Every future document â€” implementation guides, sprint plans, API references â€” derives from and references this document.

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

Project Sentinel transforms a dedicated desktop (or any always-on machine) into
an always-on personal software operations center. Instead of scattered folders
and forgotten projects, Sentinel builds a living model of everything the user
has created. It remembers why each project exists, verifies it still works, and
helps maintain it forever.

Sentinel acts as:
- A **Personal CI/CD Server**
- A **Project Intelligence Platform**
- A **Local AI Assistant**
- A **Software Maintenance System**
- A **Repository Knowledge Engine**
- An **Automated QA System**
- A **Development History Archive**

The final system runs locally on a dedicated machine (since v1.17.7: the single
desktop) and exposes services through a local web dashboard and API.

---

## 2. Goals

### Must-Have (MVP)

- Continuously understand and index personal software projects
- Use SQLite as the primary knowledge database (zero-config, file-based, ideal for a local-first platform)
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
- **Does not host public services** by default â€” local network only.

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

1. Start the Sentinel server on their machine
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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                        USER INTERFACES                          â”‚
â”‚                                                                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”              â”‚
â”‚  â”‚   Web Dashboard â”‚â—„â”€â”€â”€â”€â–ºâ”‚   Local API Gateway  â”‚              â”‚
â”‚  â”‚  (React/Vite)   â”‚      â”‚    (FastAPI)         â”‚              â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜              â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â”‚ HTTP/REST + WebSocket
                                        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    Project Sentinel Server                       â”‚
â”‚                        (Python Backend)                         â”‚
â”‚                                                                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”‚
â”‚  â”‚           Project Intelligence Engine                  â”‚     â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚     â”‚
â”‚  â”‚  â”‚Repo Indexer â”‚  â”‚Knowledge DB â”‚  â”‚     RAG      â”‚   â”‚     â”‚
â”‚  â”‚  â”‚             â”‚  â”‚  (SQLite)   â”‚  â”‚  (ChromaDB)  â”‚   â”‚     â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚     â”‚
â”‚  â”‚         â”‚                â”‚                â”‚            â”‚     â”‚
â”‚  â”‚         â””â”€â”€â”€â”€â”€â”€â”€â”€â–º Ollama AI Service â—„â”€â”€â”€â”€â”˜            â”‚     â”‚
â”‚  â”‚                    (Summaries/Explanations)             â”‚     â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â”‚
â”‚                                                                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”‚
â”‚  â”‚             Automation Engine                          â”‚     â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚     â”‚
â”‚  â”‚  â”‚Scheduler â”‚ â”‚Build Run.â”‚ â”‚Test Run. â”‚ â”‚Sec. Scan  â”‚  â”‚     â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚     â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â”‚
â”‚                                                                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”‚
â”‚  â”‚             Intelligence Subsystems                    â”‚     â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”        â”‚     â”‚
â”‚  â”‚  â”‚Git Intel.  â”‚ â”‚Doc. Gen.   â”‚ â”‚Screenshot Genâ”‚        â”‚     â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜        â”‚     â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â”‚
â”‚                                                                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”‚
â”‚  â”‚              World Simulator (Optional)                 â”‚     â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â”‚
                                        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              External Integrations (Local Network)               â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                    â”‚
â”‚  â”‚  Ollama  â”‚                      â”‚  Local API   â”‚                    â”‚
â”‚  â”‚          â”‚                      â”‚ (Sentinel)   â”‚                    â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Data Flow Summary

1. **Indexing**: Repository â†’ Indexer â†’ Knowledge Database + Embeddings â†’ ChromaDB
2. **AI Analysis**: Knowledge + Git History â†’ Ollama â†’ Summaries/Explanations Stored
3. **Automation**: Scheduler â†’ Build/Test/Scan â†’ Results stored â†’ Health scores updated
4. **Query**: User question â†’ RAG (ChromaDB search) â†’ Context + Question â†’ Ollama â†’ Answer
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
- Initial scan: detect language â†’ detect framework â†’ parse files â†’ extract metadata â†’ generate summaries â†’ store knowledge
- Incremental updates: track file changes, rebuild affected indexes
- Support for Python, JavaScript, TypeScript, React, Electron, FastAPI, Flask, Node.js, SQL

**Future Expansion**: Unity, C#, Java, Go

### 8.6 Knowledge Database

**Purpose**: Central repository of all structured project knowledge.

**Technology**: SQLite via SQLModel/SQLAlchemy (file-based, zero-config; stored at `/data/sqlite/sentinel.db` by default)

**Schema Includes**:
- `projects` â€“ Basic project metadata
- `repositories` â€“ Git repo paths and configs
- `files` â€“ Indexed file contents and metadata
- `dependencies` â€“ Package/dependency listings
- `build_commands`, `test_commands`, `install_commands`
- `tests` â€“ Test suite definitions and results
- `reports` â€“ Aggregated scan/build/test reports
- `appsession` / `sessioncheckpoint` / `sessionscreenshot` â€“ session recorder
  rows (v1.17.10); screenshots live on disk at `/data/screenshots/<slug>/`
  (PNG + 90Ã—60 thumb), the same `data/` root as the SQLite DB and
  `data/logs/apps/<slug>.log`
- `security_findings` â€“ Vulnerability alerts and secret detections
- `ai_summaries` â€“ Generated project/explanation summaries
- `git_commits`, `git_history` â€“ Version control intelligence
- `documentation` â€“ Auto-generated docs content

### 8.7 RAG System

**Purpose**: Enable natural language querying over project knowledge.

**Architecture**:
```
User Question
    â†“
ChromaDB Embedding Search
    â†“
Relevant Context Chunks
    â†“
Ollama LLM
    â†“
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
- "Did this build pass?" â†’ Use direct test result
- "List installed Python packages" â†’ Query dependency tree

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
â†’ install dependencies
â†’ npm run build
â†’ pytest
â†’ security scan
â†’ generate docs
â†’ generate screenshots
â†’ update health dashboard
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

**Purpose**: A separate entertainment subsystem â€” a deterministic, persistent
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
    â†“
simulate_day (seeded RNG): food/growth â†’ construction â†’ expansion â†’ trade
    â†’ raids â†’ discoveries â†’ festivals â†’ disasters â†’ collapse
    â†“
Persist (world_settlements / world_roads / world_events)
    â†“
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

Sentinel is not just Project Intelligence â€” its identity is a **Home Development Server with Project Intelligence as its flagship capability**. The services below are not random add-ons; they are infrastructure running on the same always-on machine, and they make the server genuinely useful even when it is not indexing code or answering questions.

### 9.1 Single-machine topology

Since v1.17.7 the topology is **one machine**: the desktop is both the dev
workstation and the always-on server. The laptop (previously `192.168.4.40`)
is retired â€” all projects live locally on the desktop, so no GitHub sync and
no LAN exposure are needed (Rule 1: everything stays local).

| Machine | Role | Hardware |
|---------|------|----------|
| Desktop (dev machine, this repo) | **Dev workstation + always-on server** â€” Sentinel repo + all 21 project checkouts, airadio, native Ollama, browser dashboard | iBUYPOWER, Ryzen 5 5500, 16 GB RAM |

### 9.2 Infrastructure Services

All services run on the single desktop (no network sharing â€” the laptop is
retired since v1.17.7):

- **Ollama** â€” local AI inference (`http://127.0.0.1:11434`), native Windows
  install on the same machine. airadio uses the same local instance (its code
  defaults to `http://localhost:11434`).
- **Local API** â€” Sentinel modules and future desktop/mobile apps.
- **Background scheduler** â€” indexing, builds, nightly scans, maintenance jobs.

(Pi-hole was deployed alongside Sentinel from Sprint 8.5 to 13, removed from
the stack in Sprint 15, and decommissioned entirely in v1.16.1 â€” the router
DNS is back to Automatic (see docs/pi-hole-idea.md for why it was never the
project's purpose).)

The desktop acts as:

- **Always-on server**: Runs 24/7 (Task-Scheduler autostart), dashboard at `http://127.0.0.1:8420` (v1.17.8.1 â€” off 8000, the uvicorn default the indexed projects' dev servers use)
- **Local AI inference machine**: Hosts Ollama for summaries/explanations
- **Project analysis machine**: Indexes and analyzes the local code repositories
- **Automation worker**: Executes builds, tests, scans on schedule
- **Local service host**: Web dashboard + API bound to localhost only

Supports:
- Ollama (local LLM inference)
- Web services (dashboard, API â€” `127.0.0.1` only)
- Background jobs (builds, tests, scans â€” scan-all on its own daily beat, v1.17.7)
- Database storage (SQLite, ChromaDB)
- Repository indexing (file system access)
- Project discovery without GitHub (v1.17.7: tokenless first-class â€” local
  checkouts with a GitHub origin are indexed directly from the watch dirs)

---

## 10. Networking Model

Single machine, nothing on the network (v1.17.7: laptop retired, localhost only):

```
Desktop (dev machine + always-on server)
   â”‚
   â””â”€â”€ http://127.0.0.1:8420      Sentinel dashboard + API (native install)
       http://127.0.0.1:11434     Ollama (local AI inference)
```

**Connectivity Rules**:
- Sentinel binds `127.0.0.1` (or `SENTINEL_HOST`) â€” no LAN exposure by default
- Ollama binds `127.0.0.1` (the desktop's own `localhost` default); it is no
  longer shared across the LAN
- No public exposure
- Optional future enhancement: bind `0.0.0.0` (+ firewall rule) if phone or
  tablet access is ever wanted

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
    â†“
Detect language
    â†“
Detect framework
    â†“
Parse files
    â†“
Extract metadata
    â†“
Generate summaries
    â†“
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
**Bad**: "Did this test pass?" â†’ Use direct result

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
    â†“
Install dependencies
    â†“
Build
    â†“
Run tests
    â†“
Security scan
    â†“
Generate documentation
    â†“
Generate screenshots
    â†“
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
feature matrix â€” no AI. See docs/02 Â§14.5.

**Generates**:
- Per-project health scores (0-100): build 30 Â· tests 30 Â· security 25 Â· docs 15;
  components with no data yet score 0
- Ranked best candidates (score â‰¥ min_score) with missing items listed
- Feature matrix across projects Ã— features (âœ“/âš /âœ—)

**Example**:
```
Sample Python Project            Score: 92.5
  Build: âœ“ passing   Tests: âœ“ passing
  Security: âœ“ clean  Docs: 50%

Best candidates: [Sample Python Project]
Feature matrix:   build  test  docs  security  screenshots
                  âœ“      âœ“     âš      âœ“         âœ—
```

**Endpoints**: `GET /portfolio/scores`, `GET /portfolio/best-candidates?min_score=70`,
`GET /portfolio/feature-matrix`. **Frontend**: `/portfolio` page (health cards,
candidates, matrix). Observatory (galaxy/timeline/architecture) shipped in
Sprint 10.5 (docs/02 Â§14.6).

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
- Runs in the existing stack via Celery beat â€” no separate container
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
| Sentence Transformers | Embedding model (all-MiniLM-L6-v2) â€” alternative to Ollama embeddings |

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
- **SQLite**: Zero-config, file-based, no service to manage â€” ideal for a local-first platform
- **React/Vite**: Modern, performant frontend with excellent dev experience
- **Ollama**: Clean HTTP API, no cloud dependency, strong community
- **ChromaDB**: Python-native, easy to integrate with existing pipelines
- **Playwright**: Industry standard for UI automation and visual testing

---

## 13. Folder Structure

```
sentinel/
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ 01_Master_Architecture.md    â† This file
â”‚   â”œâ”€â”€ 02_Implementation_Guide.md
â”‚   â”œâ”€â”€ 03_Sprint_Plan.md
â”‚   â””â”€â”€ resources/                    # Diagrams, templates, assets
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ main.py                   # FastAPI app entry point
â”‚   â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”‚   â”œâ”€â”€ v1/
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ projects.py       # Project CRUD + intelligence
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ builds.py         # Build execution/endpoints
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ tests.py          # Test execution/endpoints
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ security.py       # Scan endpoints
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ docs.py           # Doc generation endpoints
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ git.py            # Git intelligence endpoints
â”‚   â”‚   â”‚   â”‚   â”œâ”€â”€ portfolio.py      # Portfolio health endpoints
â”‚   â”‚   â”‚   â”‚   â””â”€â”€ world_sim.py      # World simulator endpoints
â”‚   â”‚   â”œâ”€â”€ core/
â”‚   â”‚   â”‚   â”œâ”€â”€ config.py             # Settings, env vars
â”‚   â”‚   â”‚   â”œâ”€â”€ logging.py            # Logger setup
â”‚   â”‚   â”‚   â”œâ”€â”€ security.py           # Authn/authz
â”‚   â”‚   â”‚   â””â”€â”€ exceptions.py         # Custom exceptions
â”‚   â”‚   â”œâ”€â”€ db/
â”‚   â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”‚   â”œâ”€â”€ connection.py         # SQLite connection
â”‚   â”‚   â”‚   â”œâ”€â”€ models.py             # SQLAlchemy table definitions
â”‚   â”‚   â”‚   â””â”€â”€ migration.py          # Migration runner
â”‚   â”‚   â”œâ”€â”€ schemas/                  # Pydantic schemas
â”‚   â”‚   â”‚   â”œâ”€â”€ project.py
â”‚   â”‚   â”‚   â”œâ”€â”€ build.py
â”‚   â”‚   â”‚   â”œâ”€â”€ test_result.py
â”‚   â”‚   â”‚   â”œâ”€â”€ security_finding.py
â”‚   â”‚   â”‚   â””â”€â”€ health.py
â”‚   â”‚   â”œâ”€â”€ repositories/             # Data access layer
â”‚   â”‚   â”‚   â”œâ”€â”€ base.py
â”‚   â”‚   â”‚   â”œâ”€â”€ project.py
â”‚   â”‚   â”‚   â”œâ”€â”€ build.py
â”‚   â”‚   â”‚   â”œâ”€â”€ test_result.py
â”‚   â”‚   â”‚   â””â”€â”€ security_finding.py
â”‚   â”‚   â”œâ”€â”€ services/                 # Business logic layer
â”‚   â”‚   â”‚   â”œâ”€â”€ indexer.py            # Repository indexer
â”‚   â”‚   â”‚   â”œâ”€â”€ intelligence_engine.py
â”‚   â”‚   â”‚   â”œâ”€â”€ build_runner.py
â”‚   â”‚   â”‚   â”œâ”€â”€ test_runner.py
â”‚   â”‚   â”‚   â”œâ”€â”€ security_scanner.py
â”‚   â”‚   â”‚   â”œâ”€â”€ doc_generator.py
â”‚   â”‚   â”‚   â”œâ”€â”€ screenshot_generator.py
â”‚   â”‚   â”‚   â”œâ”€â”€ git_intelligence.py
â”‚   â”‚   â”‚   â”œâ”€â”€ portfolio_intelligence.py
â”‚   â”‚   â”‚   â”œâ”€â”€ rag_service.py
â”‚   â”‚   â”‚   â”œâ”€â”€ scheduler.py
â”‚   â”‚   â”‚   â””â”€â”€ world_simulator.py
â”‚   â”‚   â”œâ”€â”€ parsers/                  # Language/framework parsers
â”‚   â”‚   â”‚   â”œâ”€â”€ base.py
â”‚   â”‚   â”‚   â”œâ”€â”€ python_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ javascript_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ typescript_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ react_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ fastapi_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ flask_parser.py
â”‚   â”‚   â”‚   â”œâ”€â”€ node_parser.py
â”‚   â”‚   â”‚   â””â”€â”€ sql_parser.py
â”‚   â”‚   â”œâ”€â”€ workers/                  # Celery tasks
â”‚   â”‚   â”‚   â”œâ”€â”€ build_tasks.py
â”‚   â”‚   â”‚   â”œâ”€â”€ test_tasks.py
â”‚   â”‚   â”‚   â”œâ”€â”€ security_tasks.py
â”‚   â”‚   â”‚   â””â”€â”€ doc_tasks.py
â”‚   â”‚   â”œâ”€â”€ utils/
â”‚   â”‚   â”‚   â”œâ”€â”€ language_detector.py
â”‚   â”‚   â”‚   â”œâ”€â”€ framework_detector.py
â”‚   â”‚   â”‚   â””â”€â”€ command_extractor.py
â”‚   â”œâ”€â”€ tests/                        # Backend unit + integration tests
â”‚   â”‚   â”œâ”€â”€ conftest.py
â”‚   â”‚   â”œâ”€â”€ test_parsers.py
â”‚   â”‚   â”œâ”€â”€ test_indexer.py
â”‚   â”‚   â”œâ”€â”€ test_build_runner.py
â”‚   â”‚   â”œâ”€â”€ test_services.py
â”‚   â”‚   â””â”€â”€ test_e2e.py
â”‚   â”œâ”€â”€ scripts/
â”‚   â”‚   â”œâ”€â”€ run.sh                    # Start backend server
â”‚   â”‚   â””â”€â”€ migrate.sh
â”‚   â”œâ”€â”€ pyproject.toml
â”‚   â””â”€â”€ requirements.txt
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ main.tsx                  # React entry point
â”‚   â”‚   â”œâ”€â”€ app.tsx                   # Root component
â”‚   â”‚   â”œâ”€â”€ api/                      # Axios client + typed hooks
â”‚   â”‚   â”‚   â”œâ”€â”€ client.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ projects.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ builds.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ tests.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ security.ts
â”‚   â”‚   â”‚   â””â”€â”€ portfolio.ts
â”‚   â”‚   â”œâ”€â”€ components/
â”‚   â”‚   â”‚   â”œâ”€â”€ ProjectGalaxy.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ ProjectTimeline.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ HealthCard.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ ArchitectureMap.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ FeatureMatrix.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ PortfolioView.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ WorldSimulator.tsx
â”‚   â”‚   â”‚   â””â”€â”€ layouts/
â”‚   â”‚   â”œâ”€â”€ contexts/
â”‚   â”‚   â”‚   â”œâ”€â”€ ProjectContext.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ BuildContext.tsx
â”‚   â”‚   â”‚   â””â”€â”€ UIContext.tsx
â”‚   â”‚   â”œâ”€â”€ hooks/
â”‚   â”‚   â”‚   â”œâ”€â”€ useProjects.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ useBuilds.ts
â”‚   â”‚   â”‚   â”œâ”€â”€ useSearch.ts
â”‚   â”‚   â”‚   â””â”€â”€ useWorldSim.ts
â”‚   â”‚   â”œâ”€â”€ pages/
â”‚   â”‚   â”‚   â”œâ”€â”€ Dashboard.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ ProjectDetails.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ BuildHistory.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ SecurityFindings.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ GitTimeline.tsx
â”‚   â”‚   â”‚   â”œâ”€â”€ Portfolio.tsx
â”‚   â”‚   â”‚   â””â”€â”€ WorldSimulatorPage.tsx
â”‚   â”‚   â”œâ”€â”€ routes/
â”‚   â”‚   â”‚   â””â”€â”€ index.tsx
â”‚   â”‚   â”œâ”€â”€ styles/
â”‚   â”‚   â””â”€â”€ lib/
â”‚   â”‚       â””â”€â”€ utils.ts
â”‚   â”œâ”€â”€ public/
â”‚   â”œâ”€â”€ vite.config.ts
â”‚   â”œâ”€â”€ package.json
â”‚   â””â”€â”€ tsconfig.json
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ build.py                        # Verify + stage the dashboard
â”‚   â””â”€â”€ release.py                      # Package release zip
â”œâ”€â”€ run.py                              # Single starting point: checks + uvicorn
â”œâ”€â”€ AGENTS.md                           # Project rules for AI agents
â”œâ”€â”€ .python-version
â”œâ”€â”€ pyproject.toml                      # Root pyproject (workspace)
â””â”€â”€ README.md
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
3. **Keep changes modular** â€” one responsibility per module/service/component.
4. **Write tests for every new endpoint, service method, and utility function.**
5. **Run all existing tests before committing** (`pytest -n auto`)
6. **Follow existing code formatting standards** (black, isort, flake8 for Python; prettier+eslint for TS)
7. **Update relevant docs** when modifying architecture or APIs.

---

## 17. Changelog

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-18 | 1.17.14.4 | **Click-through Phase 2: Electron desktop features (CDP engine).** The features now drive the packaged desktop apps' real windows. Playwright 1.62's python package ships no `p.electron` wrapper (the node driver has electron support, the wrapper does not), so the FeatureRunner launches the packaged exe with `--remote-debugging-port=<free>` + `--user-data-dir=<temp sandbox>`, polls `/json/list`, attaches via `connect_over_cdp` and drives the window with the same Page API - no new dependency. Sandbox is verified, not assumed: the temp dir must gain Chromium profile files AND the app's own state artifact (`tv_scheduler.db`, `data/` dir or `backend.log`) or the run is TesterEnvError; the window URL must be file:// or loopback (Rule 1); the spawned tree is taskkilled on exit. The tester-phase auto-launched instance is reclaimed first (frees TV-Scheduler's hard-coded :3050). `Feature` gains `electron` + `budget_s` (WFT feature: 180 s); `FeatureContext.go()` is refused for electron windows (already on the app). TV-Scheduler: features now drive the packaged window - the interim dev-stack fallback is removed (real TVMaze names never hit the stale asar's broken manual-add path) and the tester is back to the /health probe + window capture. WorkFlow-Toolkit: first electron feature - Projects -> + New Project -> Import Hub (engineered payroll_issues.csv fixture) -> Templates Payroll Audit -> Execute Workflow -> Completed run row -> Reports 'Workflow' report row, all in the sandboxed fresh DB (self-created entities only). Tests: +6 (no-launcher, reclaim-before-launch, sandbox violation, electron go-refused, window-target matching incl. remote-URL refusal, budget override) and the registry gains Workflow-Toolkit; every feature still passes against the fake page. Gate: pytest + black/isort/flake8 green. Plan: docs/clickthrough_plan.md Phase 2 header updated to v1.17.14.4 (CDP engine). |
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
| 2026-08-14 | 1.17.7.7 | **Live UI updates for scans and builds; resolved findings are cleanable; AG finally testable.** (1) **Builds poll race fixed** (Builds.tsx): `finish()` cleared `pollingJobId` *before* the awaited history refresh, so the effect cleanup flipped `cancelled` and dropped both the refreshed list and the toast - the row stayed "running..." forever on a real network; the refresh + toast now run first, then the poll state clears (regression test with a slow history fetch). (2) **Security tab refreshes on completion** (Security.tsx): after queueing a scan/scan-all the tab polls `GET /projects/{id}` every 2 s until `last_scanned` moves past the pre-scan snapshot (stamped by the scanner on every run - the only deterministic completion signal, since a clean scan writes no finding row), then refetches findings + toasts. Scan buttons show "Scanning..." while the poll is live (10-min cap). (3) **Resolved findings cleanable** (v1.17.7.7): every stale leftover is `resolved=True` forever (Ag 209, WT 183, Sentinel 7, others 1-2 - all false positives from the pre-v1.17.7.5 scanner) and spammed the observatory timeline (~400 events). New `DELETE /api/v1/security/findings?project_id=` removes *resolved* rows only (SecurityRepository.delete_resolved, open findings untouched - they are the live scan state and the idempotence keys); the tab defaults to open findings with a "Show resolved" toggle + "Clear resolved (N)" button; the timeline now filters `resolved == False`. (4) **AG gets a test command**: AG's root has no manifest (requirements live in stable-fast-3d//triposr/ subdirs; AGENTS.md is a session log with zero command literals), so discovery honestly found nothing. Two deterministic additions (command_extractor.py): `AGENTS.md`/`docs/AGENTS.md` join the README candidates but are scanned for fenced code blocks only (Sentinel's own AGENTS.md mentions "pytest in backend/" mid-sentence - a whole-file scan would mint a wrong command), and a pytest convention extractor (last in order): a root `tests/` dir + at least one root-level `.py` file yields `test: pytest`. Empty extractor results no longer claim keys (an earlier extractor that found nothing must not block a later confident one - the AGENTS.md scan returned `test: ""` and shadowed the convention). AG now discovers test: pytest; its build step stays honestly skipped (interpreted Python app - nothing compiles). Docs: 01/02/03 changelogs. Tests: +4 backend (DELETE API x3, repo delete_resolved, timeline excludes resolved, extractor: AGENTS.md fenced, AGENTS.md prose ignored, pytest convention x2) +5 frontend (Security poll/toggle/clear x5, Builds slow-refresh regression) | AI agent |
| 2026-08-14 | 1.17.7.6 | **World tab removed from the sidebar.** The world simulator is opt-in since v1.17.7.3 (SENTINEL_WORLD_SIM_ENABLED=true); with it off, the World nav item loaded a page that 404s on every API call. 
av.ts drops the World entry and 
outes/index.tsx drops the route, so a stale /world link falls through to the Dashboard catch-all; WorldSimulatorPage/WorldGridMap/world_sim.ts stay in place for a future re-enable (re-add the nav line + route) | AI agent |
| 2026-08-14 | 1.17.7.6 | **C++/CMake build discovery + builds.md recipe reference.** (1) **CMake extractor** (command_extractor.py _from_cmake, ordered before the README scan): a root CMakeLists.txt yields uild: cmake --build build ï¿½ the canonical invocation that reuses the cached generator (Algo Trader and HFT-Order-Book are configured with MinGW Makefiles, so it drives mingw32-make in uild/) and re-runs configure automatically when CMakeLists.txt changes; 	est: ctest --test-dir build only when enable_testing()/dd_test appears. Blast radius is exactly the two CMake repos in the projects root. (2) **Stale-stack fallback** (uild_runner.py): a stored stack.commands.build that is empty no longer short-circuits to *skipped* ï¿½ the runner re-discovers at build time (same runtime-fallback pattern as the portfolio matrix), so extractor improvements apply without re-indexing. (3) **docs/builds.md**: versioned recipe reference for all 21 projects (install/build/test/startup per project, discovered commands only) + a C++ deep-dive ï¿½ Algo Trader: configure once cmake -S . -B build -G "MinGW Makefiles", build via cmake --build build, outputs uild\trader.exe + uild\backtester.exe; acktester is a separate strategy-testing executable *within* the repo, not its own project; data lives in config/settings.json/data\algo_trader.db. HFT-Order-Book: same CMake layout (cpp-httplib vendored). Doc is indexed by the knowledge system and security-scanned, so it stays free of credential-like literals. Docs: 01/02/03 changelogs, builds.md. Tests: +3 parametrized extractor cases (CMakeLists alone, +enable_testing, +dd_test) and +1 runner fallback test (stale empty stack re-discovers cmake --build build) | AI agent |
| 2026-08-14 | 1.17.7.5 | **Index-gated security scans (no more false positives); honest no-command builds; README build discovery.** (1) **Scanner scans what the index indexes** (`security_scanner.py`): the project walk used the indexer's `_iter_source_files` directly, so untracked junk got flagged â€” live run showed AG with 208 eval/exec findings in `.venv_sf3d\Lib\site-packages`, WorkFlow-Toolkit 174 in the untracked `backend\runtime\python\Lib` stdlib + `release\win-unpacked\` outputs, and Sentinel flagging itself (3 findings: regex titles "Use of eval()"/"Use of exec()" as *string literals* matched by the old regex `_STATIC_PATTERNS`, and a comment example placeholder token (the alphabetical `ghp_`-prefixed sample) caught by the Generic Secret). Fix: `_iter_scan_files` reads the indexed `ProjectFile` rows (`absolute_path`; fallback = the same gated walk), and static analysis is now **AST-based** â€” `eval`/`exec`/`compile` are flagged only as real `Call`/`Name` nodes, never inside strings or comments; the placeholder comment no longer contains a literal GitHub token. Expected live effect after the re-scan: AG 209â†’1, WT 183â†’0, Sentinel 3â†’0. (2) **"No build command" is now an honest *skipped*** (`build_runner.py`): no discoverable command used to record `success=True, exit_code=0` and feed "Build passed" â€” it now records `success=None, exit_code=None` ("No build command configured for this project."), the feed says "Build skipped", `JobStatus` gains the `skipped` literal (was: the old code mapped `success=None` â†’ "failed"), and `Builds.tsx` labels completed null-success logs "skipped" (was "running"). Portfolio: the static 21 build points still require a command â€” `_has_build_command` consults `extract_build_commands` at runtime as a fallback so README-discovered commands count. (3) **Better command discovery** (`command_extractor.py` rewrite): ordered extractors for Makefile (`make build`/`make all`), Cargo.toml (`cargo build`/`cargo test`), go.mod (`go build ./...`/`go test ./...`), Maven `pom.xml`/wrappers (`mvn package`/`mvn test`), Gradle `build.gradle`/wrappers (`gradle build`/`gradle test`), dotnet `.sln`/`.csproj` (`dotnet build`/`dotnet test`), lockfile-aware package.json install (pnpm/yarn/bun), plus **README/docs discovery** â€” known command spellings (`npm run build`, `make build`, `cargo build`, `gradle build`, `mvn package`, `dotnet build`, `go build ./...`, `pip install`, ...) matched in README.md/BUILDING.md/docs with a word-boundary regex; explicit manifests always win over prose. Docs: 01 Â§17, 02 Â§14.5 + changelog, 03 changelog. Tests: +2 backend (AST ignores string literals; scanner uses indexed files only â€” untracked `.venv_sf3d`/`release` never scanned), +10 parametrized extractor tests (Makefile Ã—3, cargo, go, maven, dotnet Ã—2, gradle, README code-block/plain/invention-guard/package.json-precedence), honesty tests rewritten (runner: `success is None`; API: "skipped" status), +1 index-completeness test (git fixture: every tracked file across docs/backend/frontend is indexed), +1 vitest (skipped label); 93.6 % coverage | AI agent |
| 2026-08-12 | 1.17.7.3 | **Projects root; git-tracked indexing; watch-dirs parser fix; world-sim opt-in.** (1) **Projects root** (this machine): all project checkouts moved from the home dir to `C:\Users\j\projects` (nested `jamesdileva\`/`juduncan\` canonical checkouts moved along); `.env` now sets `SENTINEL_WATCH_DIRS=C:\Users\j\projects`, so the home dir is never walked and the projects-root dirs (betsim, coach, nexus, ResMaker, surfhop, ...) become projects at the next scan. DB rows keep their identity via the new `scripts/migrate_projects_root.py` path rewrite (`project.path`, `projectfile.path`/`absolute_path`, `securityfinding.file_path`; `--dry-run` first) run after the move â€” no GC churn, no chat/summary loss (21 project rows + 12,470 file paths on the desktop). (2) **Git-tracked indexing** (`indexer.py`): file lists come from `git ls-files -z` for real git checkouts (walk fallback for non-git and bare `.git/` dirs, rc 128) â€” untracked `.env` secrets, IDE state and uncommitted junk never enter the index (the makehuman `.env` case); ignore/binary/size gates still apply; stale rows prune on rescan as before. AG `tests/conftest.py` + WorkFlow-Toolkit `test.py` updated for the new root. (3) **Watch-dirs parser fix** (`config.py`): `SENTINEL_WATCH_DIRS` accepts a single dir, comma-separated, or JSON â€” the documented comma format previously crashed pydantic-settings' JSON-only parser (`SettingsError`). (4) **World sim opt-in**: `world_sim_enabled` defaults to `False` (router + beat register only with `SENTINEL_WORLD_SIM_ENABLED=true`); world-sim API tests mount the router explicitly. Docs: AGENTS.md, desktop.md, 02 Â§4.2/Â§13.4, 01/02/03 changelogs. Tests: +5 backend (watch-dirs forms Ã—3, git tracked-only, walk fallback, world-sim default), full suite green | AI agent |
| 2026-08-12 | 1.17.7.2 | **Junk-free file index; honest knowledge reset; no autostart task.** (1) **Ignore patterns** (`config.py`): `Library/` (Unity's regenerable PackageCache/Artifacts/BurstCache â€” Khd4 alone was 25.6k cache files), `release/` + `win-unpacked/` (electron-builder output), `*.pdb`/`*.bhc` (build symbols/Burst caches) â€” the desktop index had swollen to 47,455 files vs ~4k of real source on the laptop; ignored rows prune themselves on the next scan (`_index_files` drops rows no longer walked). (2) **Reset now sticks** (`job_scheduler.py`, `rag_tasks.py`): new `JobScheduler.cancel_queued(name_prefix)` cancels not-yet-started pool jobs; `run_reset_knowledge` cancels queued `run_index_knowledge` jobs before clearing flags + dropping collections, so the embedded count goes to 0 and stays 0 â€” previously the boot auto-index re-queued ~20 projects and re-embedded seconds after the reset, making it look like a no-op. (3) **Autostart task removed**: `scripts/install_service.py` deleted, `run.py` drops `--service`/`--install`/`--uninstall` (and the now-unused PYWIN candidates), the desktop task uninstalled â€” the 5-min Task-Scheduler rerun popped a console window every time it respawned the server (Last Result 1 bind races); the server is started manually with `run.py`. Docs: AGENTS.md, README, desktop.md, 01 repo tree, 02 Â§13.3/Â§13.4 + troubleshooting, 03 Phase 13. Tests: âˆ’2 packaging (install_service), +ignore-pattern indexer, +cancel_queued, +reset cancels queued jobs | AI agent |
| 2026-08-12 | 1.17.7.1 | **Junk-file indexing gates + fast boot scans.** The full project scan on this machine took ~25-40 min and froze the API: `_iter_source_files` rglob'd entire trees (demake-engine: 35.3k files / 11 GB incl. a 3.3 GB ONNX model; AG: 26.8k files incl. `.venv_sf3d` â€” a venv-like dir the exact `.venv/` pattern missed) and the parsers `read_text` whole files, decoding multi-GB binaries to strings on every scan. Fixes: **(1) file gates** â€” new `SENTINEL_MAX_FILE_KB` (default 5120) plus a `_BINARY_SUFFIXES` denylist (.onnx/.pt/.dll/.db/.mp4/...) applied in `_is_skippable` to both full scans and incremental updates; **(2) walk prune** â€” the project walk never descends into ignored dirs anymore (`.git`, `node_modules`, `.venv*/`, `dist`, `build`, `data/` â€” `data/` added, `.venv/`â†’`.venv*/` wildcard) instead of rglob+filter (24k entries under this repo alone); **(3) mtime fast-path** â€” `ProjectFile.mtime_ns` column (ALTER migration) lets an unchanged file skip re-read/re-parse entirely, so boot scans drop to seconds after the first pass. **run.py venv resolution** (found during deploy): the launcher only knew the repo-root `.venv` and its Linux-style fallback, so `run.py` died with FileNotFoundError on this machine â€” it now resolves `backend\.venv` or the root `.venv`. **CLI transparency**: `index --all` prints `Indexed k/N: <name>` per project so long runs don't look frozen. Tests: +3 backend (binary+size gates, ignored-dir prune incl. `.venv_sf3d`/`data/`, mtime fast-path skip-then-reparse), 93.66 % | AI agent |
| 2026-08-12 | 1.17.7 | **Single-desktop deployment; GitHub is now optional; scans decoupled from sync.** Topology simplified to one machine (docs/01 Â§9.1, Â§10): the desktop is the dev workstation AND the always-on server, the laptop is retired, and the dashboard is localhost-only (`http://127.0.0.1:8000`) â€” see docs/desktop.md (renamed from laptop.md) and 02 Â§13. **Tokenless first-class**: no token â†’ the `repo-sync` beat isn't registered and startup logs a single INFO line (no "skipped" activity event); local checkouts with a GitHub origin are indexed directly from the watch dirs anyway (`C:\Users\j` â€” all 21 projects sit in the home dir). **Security scan-all owns its own beat**: new `SENTINEL_SCAN_INTERVAL_MINUTES` (default 1440); previously the daily scan ran chained to the repo-sync pass, so a tokenless install would never scan (`run_repo_sync` no longer calls `run_security_scan_all`). **Home-dir discovery pruning**: `discover_repositories` is now a depth-aware walk that prunes noise dirs (`AppData`, `OneDrive`, `node_modules`, `.venv`, tool caches â€” `_DISCOVERY_SKIP_DIRS`) instead of rglob-ing the whole home directory; the eligible set is unchanged (worktrees/stray copies/nested sub-repos still excluded by `is_sync_owned`). **install_service venv fallback**: the autostart task resolves `backend\.venv` or the repo-root `.venv` (previously only the root â€” would point at a nonexistent pythonw on this machine). Tests: +8 backend (beat registration tokenless/token, scan decoupled, scan interval config, discovery pruning Ã—3, install_service venv Ã—2), 93.95 % | AI agent |
| 2026-08-12 | 1.17.6.8 | **Full re-embed is now a button, and Ollama timeouts are fixed.** Knowledge page: "Rebuild knowledge index" is always visible (it lived only inside the damaged-index banner, so a healthy-but-stale index had no in-UI path to re-embed with new chunking/summaries) â€” the confirm dialog covers both cases; the amber banner is informational. Timeout hardening (laptop `sentinel(2).log`: 3 of 17 post-reset jobs died at `ingest_project_summary` while the v1.17.6.6 ~10k-token prefill contended with the embed flood): `ollama_timeout_seconds` default 600 â†’ 1800. Summary output budget: new `ollama_summary_max_tokens` default **1250** â€” the old shared 500 cap truncated the fed-more, structured summaries; chat answers keep 500 (`_generate_with_metrics` now forwards `max_tokens`). `.env.example` documents both overrides. Tests: +1 backend (summary call carries 1250, chat stays 500), +1 frontend (rebuild action visible when healthy) | AI agent |
| 2026-08-12 | 1.17.6.7 | **"Re-index all projects" 500 fixed.** The 1.17.6.4 `/api/v1/rag/index/all` endpoint submits the job name `run_index_knowledge_all`, but `_build_registry()` (`services/job_scheduler.py`) never registered the task â€” every click 500'd with a `KeyError` from `submit`. The exact-equality registry test pinned the pre-1.17.6.4 name set, so the suite stayed green; `EXPECTED_TASKS` now includes the name, plus a new regression test asserting the exact names the API routers submit all resolve through the real registry (catches this bug class). CLI `rag-index --all` was unaffected (calls the task directly). **CLI `rag-index --reset` fixed**: it called `get_chroma_manager().reset_all()` directly, dropping the collections but never clearing `ProjectFile.embedding_id` (the v1.17.6.1 flag-clearing existed only in the API reset path) â€” the startup auto-index then found nothing to re-embed, leaving the Knowledge page reporting every file embedded against an empty index. It now runs the same `run_reset_knowledge()` task as the API button and prints `files_unflagged`. **Flaky gate fixed**: the lifespan startup scan (`main.py` `_background_initial_scan`) ran as a daemon thread that outlived its TestClient and could persist a `SyncRun` into a later test's engine â€” intermittently failing `test_system_sync_endpoint`; the autouse conftest fixture now pins `auto_scan_on_startup=False` (renamed `_quiet_background`). Tests: +1 backend, +1 backend updated | AI agent |

| 2026-08-12 | 1.17.6.6 | Security scans join the daily sync chain; markdown-aware retrieval. **Scan = once per 24 h, not a separate beat**: the `nightly-security-scan` beat is gone â€” the daily repo-sync now runs the scan itself at the end of the pass (chained sync â†’ knowledge index â†’ security scan; runs whenever the sync is configured), so findings always reflect freshly pulled code with no extra wake-ups. **Never-scanned â‰  clean**: `Project.last_scanned` (a previously dead column) is now stamped by every scan; the portfolio security component reads it â€” no findings + never scanned = pending (0), no findings + scanned = clean (full 25) â€” and `_source_epoch` covers it, so cached scores refresh after the first clean scan. **Docs chunked, code kept whole**: Markdown/`docs/` files are chunked at 2000 chars / 200 overlap (â‰¤32 chunks/file, ids `{file}#{i}`) while code stays single 4k chunks â€” "how do I add X" questions now retrieve the READMEs and guides, not just code. **Smarter summaries**: the summary context is docs-first (README 400 pts > `.md` 300 > `docs/` 150 > entry files 100; 25 files Ã— 1500 chars) plus the 25 most recent commit messages as the sprint timeline; `project_summary.j2` rewritten to emit Overview/Architecture/Build-Run-Test/Phase-milestones and trust docs over code, and generation now has room to breathe (`ollama_num_ctx` 32768 â€” Ollama's default 2048 would truncate). **All-project queries scale**: top_k grows with the indexed project count (cap 24), the summary collection fills slots first, results merge by distance, context trimmed to a 48k-char budget. **`__all__` chat room**: all-project chat gets its own persisted history (room key `__all__`). **Frontend**: query timeout 120 s â†’ 600 s, default topK 5 â†’ 10. Migration: knowledge reset + re-index-all applies the new chunking and regenerates summaries. Tests: +9 backend (docs chunked / code single, chunk bounds, summary ranking docs-first + commits, all-scope scaling, last_scanned stamp, pendingâ†’clean flip + cache invalidation, sync chains scan + skip, `__all__` room; scheduler/ollama tests updated), +2 frontend (`__all__` history load/persist); full pytest suite green + 75 vitest | AI agent |

| 2026-08-12 | 1.17.6.5 | **Default LLM switched to `llama3.1:8b`** (was `gemma2`). Trigger: a head-to-head on the architecture-summary prompt â€” same `project_summary.j2` template, same 8-file/600-char context (this repo), app defaults (500 tokens, temp 0.3): gemma2 wrote a tight high-level summary (186 tokens, 6.3 tok/s) and honestly flagged the thin context; llama3.1:8b wrote a better-structured one (294 tokens, 9.0 tok/s â€” Components/Technical Stack/Notes, correctly picked up the AGENTS.md rules). Decision: llama3.1:8b â€” faster on the same hardware, better structure for the embedding, stronger instruction following for RAG chat; gemma2's "say so rather than guess" behavior is already enforced by the prompt. `settings.ollama_model` + `world_sim_model` defaults, CLI pull guidance (`ollama pull llama3.1:8b nomic-embed-text`), `.env.example`, AGENTS.md decision table, and docs current-state references all updated. Note: the world-sim narratives are deterministic templates â€” `world_sim_model`/`world_sim_ai_narratives` are currently unused (planned AI-narrative wiring never shipped); the default changes anyway to stay consistent for future use. Existing stored summaries keep their `model` provenance column â€” only new generations (missing-summary backfill, chat answers) use the new model; regenerate the laptop's 18 summaries with `rag-index <project> --summary` to migrate. Tests: none required (no test asserted the default model; fixtures use arbitrary strings) | AI agent |
| 2026-08-12 | 1.17.6.4 | Run-log cleanup + re-index-all command. **Log noise**: `httpx`/`httpcore` set to WARNING (the 1.17.6.3 run log was ~500 `POST /api/embed` lines in ~1800 â€” that detail already lives in the activity feed and the Ollama query log). **Deterministic single-write run log**: the file handler is now pinned on `uvicorn`/`uvicorn.error`/`uvicorn.access` *and* root with `propagate=False` on the uvicorn loggers, so every line lands in `data/logs/sentinel.log` exactly once regardless of how uvicorn's own log config set propagation (the previous pin could write a record two or three times through the logger chain). **Ollama timeout**: default `ollama_timeout_seconds` 120 â†’ 600 (a laptop saturated by 4 concurrent embedding workers timed out arch-summary generation at 2 min; 10 min covers the slow gemma2 case; `SENTINEL_OLLAMA_TIMEOUT_SECONDS` overrides). **Re-index all projects**: Knowledge-page button + `POST /api/v1/rag/index/all` + CLI `rag-index --all` â€” one deterministic job re-indexes every project with `with_summary=True`; fully incremental (`ingest_files` skips files whose `embedding_id` is set), so it backfills missing AI architecture summaries without re-embedding (the 1.17.6.3 timed-out summary jobs are exactly this case) and picks up files from a recent `git pull`; one project's failure never aborts the pass. Tests: +8 backend (endpoint queues one job, CLI `--all` runs the task and usage lists it, re-index-all skips embedded files + regenerates a missing summary + survives one bad project, uvicorn loggers pinned propagate=False single-write, httpx silenced to WARNING), frontend reindex-button test | AI agent |
| 2026-08-11 | 1.17.6.3 | Post-laptop-log runbook pass. **Summary dedupe fixed**: `ingest_project_summary` checked the SQLite `KnowledgeSummary` row, not the embedding â€” `reset()` drops the `project_summaries` collection but keeps the rows, so a post-reset re-index skipped the architecture summary entirely ("files indexed but no AI arch summary"; all-project chat lost its summary-first answers). The dedupe now skips only when the vector exists (`get(where={"$and": ...})`; any collection error counts as missing), and a regeneration reuses the newest row instead of duplicating it â€” `force` (CLI `--summary`) unchanged. **Per-run log file**: `data/logs/sentinel.log` â€” truncated at startup, INFO level, the "what happened this run" answer; `attach_file_logging()` re-attaches the file handler at lifespan startup (uvicorn's log config replaces root handlers) and pins it on the `uvicorn`/`uvicorn.error`/`uvicorn.access` loggers, so a forced shutdown mid-index and any cascade are captured on disk instead of only scrolling the console. **run.py port-owner message**: starting while another Sentinel is running (a second console left open) now prints the owning PID + `taskkill` hint instead of uvicorn's raw bind traceback. Tests: +5 backend (summary regenerates after reset with row reuse, once-per-project dedupe maintained, run-log written at INFO, overwrite-mode handler, attach idempotency) | AI agent |
| 2026-08-09 | 1.17.2 | Living-week fixes. **No more re-embedding on restart**: `IndexerService._index_files` deleted + re-inserted every `project_file` row per scan, nulling `embedding_id` (and Chroma doc ids are the row ids) â€” auto index then re-embedded all 2.9k files after every restart; rows are now keyed by path, unchanged files keep id + embedding_id, only vanished files drop. **Shared Chroma client**: a startup burst of knowledge jobs constructed `PersistentClient`s concurrently and raced ChromaDB's shared-system registry (`'RustBindingsAPI' has no attribute 'bindings'` / `KeyError`) â€” `get_chroma_manager()` hands out one locked client per path. **Activity feed caching**: mount-seed re-runs when the WS opens and retries once after an empty first load, so cached history always shows on entering the dashboard (live frames still merge); persist failures now WARN (were debug â€” the laptop's history could vanish silently). **Embedding t/s**: `OllamaService.embed_with_metrics` (Ollama `prompt_eval_count/duration`) â†’ knowledge progress ticks carry `tokens_per_second`, shown on the feed during indexing (generations/chat t/s unchanged). External Ollama clients (e.g. airadio) remain invisible by design â€” Sentinel only measures its own calls. Tests: +10 backend (incl. reindex-preserves-ids, vanished-file drop, singleton identity, embed counters, t/s) / 70 vitest | AI agent |
| 2026-08-11 | 1.17.6.2 | Laptop recovery: RAG chat + semantic search work again after a damaged index. **Probe fixed** (`ChromaManager.health`): the v1.17.6 `get(limit=1)` probe could pass while the query path raised (`Nothing found on disk`) â€” chat 503'd with the rebuild hint while the dashboard stayed healthy, so the rebuild banner/button never appeared; the probe now runs a real query with a stored embedding, the exact operation search uses. `reset()` tolerates `InternalError` on `delete_collection` (a broken store can raise on drop; the collection is being discarded anyway). **Auto-index always includes the AI architecture summary**: `queue_knowledge_index_unembedded` (startup scan + repo-sync pass) submits `run_index_knowledge` with `with_summary=True`; `ingest_project_summary` dedupes to once per project (existing `architecture` summary reused â€” no Ollama burn per scan; CLI `rag-index <project> --summary` forces a regenerate via `force_summary`). Dashboard "Include AI architecture summary" checkbox removed (redundant; API `with_summary` param kept). New projects and post-reset re-indexes get summaries automatically, so all-project questions are summary-first as designed. Deferred: summary regeneration on repo change (needs file-change detection â€” edits are never re-embedded today; the sync pass already knows changed repos, so the hook is cheap later). Tests: +5 backend, +1 frontend updated | AI agent |
| 2026-08-09 | 1.17.1 | Regression-fix & ops pass after the first living week. **Scanner false positive fixed**: `\bexec\s*\(` matched `session.exec(` because a dot is a word boundary â€” 17 of the laptop's 20 findings were SQLModel ORM calls in clean repos; attribute calls are now ignored (only bare identifiers match). **Sync feedback**: an unconfigured sync now publishes *why* on the live feed ("Repo sync skipped â€” token not configured"), and nothing-changed passes carry a `detail` header; `POST /api/v1/system/sync` (`{"full": bool}`) + header "Sync now" button run a background pass (409 when already running, activity events per pass). **Migration bug fixed**: `migrate_columns` only added missing columns to the *first* affected table â€” `ollamaquerylog.purpose` was silently absent (would crash chat history past the 5000-row ceiling); migrated tables are now verified via `PRAGMA table_info` and repaired per table. **Sync cadence**: `SENTINEL_SYNC_INTERVAL_MINUTES` default 15 â†’ 1440 (daily; startup still syncs once; manual runs cover impatience). **C++ builds deferred** to Sprint 18 (Rule 4 â€” parser scope is out of control). Tests: regression tests for all four, 84 backend / 68 vitest green | AI agent |
| 2026-08-09 | 1.17 | Sprint 17 (Observability & UX pass): **live activity everywhere** â€” new in-process `ActivityBus` (`app/services/activity_bus.py`) records every notable event (syncs, knowledge indexing, builds, tests, security scans, Ollama generations with purpose) into a bounded `activity_event` table (5000-row ceiling, SQLite-lock serialized, best-effort) and fans them out over `/api/v1/ws/jobs` (welcome frame, events, 30 s heartbeat); new read-only `GET /api/v1/system/activity` (cap 500, newest first). Ollama calls carry a `purpose` label (query/summary/â€¦) persisted on `ollama_query_log` (auto-migrated column) and shown in the activity stream. Frontend: global status bar under the header on every page (live dot, last event, Ollama purpose + tok/s from the event's eval metrics), always-visible sync pill ("Sync not configured" when unconfigured), Dashboard live-activity log panel replacing the old channel box (falls back to polling `/system/activity` when the socket is closed). **Knowledge chat persistence**: `ChatMessage` table + `GET/POST /api/v1/rag/chat/{project_id}` (SQLite-backed chat rooms per project), RagChat replays history and saves every exchange. KnowledgeExplorer refreshes index progress live while indexing activity flows. **Auto knowledge-index on startup**(config flag `SENTINEL_AUTO_INDEX_KNOWLEDGE`, default on): after the initial scan, projects with unembedded files are queued for RAG indexing (Ollama-gated, via shared `queue_knowledge_index_unembedded`). Galaxy labels + legend, portfolio chips with per-criterion reasons. **Foundational .env fix**: `config.py` env_file was `BASE_DIR.parent / ".env"` (home dir) since Sprint 0 â€” every `SENTINEL_*` override and the GitHub token were ignored by the native install; now loads the repo-root `.env`. Gate repair: `scripts/build.py`'s `ok`-chain masked failures (raw exit code 0 is falsy â†’ lint/test failures never aborted) and ran flake8 at its default 79 cols; fixed to booleans + `--max-line-length=100`, and pre-existing lint stragglers cleared (unused imports, E712, W292). Tests: 271 backend green / 94.49 % cov, 63 vitest, gate green. Docs: Â§4.2 env table, changelogs v1.17 | AI agent |
| 2026-08-08 | 1.16.2 | Dashboard actually served: `app/main.py` still pointed at `frontend/dist` while the Sprint 15.1 build is staged at `backend/app/static` â€” on a Node-less laptop every non-API path 404'd, root showed only the Sprint-1 health JSON. Now serves the staged build (dev fallback to `frontend/dist` when absent) and `/` returns dashboard HTML; health stays at `/health` + `/api/v1/health`. SPA-fallback + root tests added. Docs: run commands tightened to the explicit venv path (`.\.venv\Scripts\python.exe run.py`; PowerShell ExecutionPolicy blocks `Activate.ps1`, activation never required): laptop.md, 02 Â§5.2/Â§13, AGENTS.md; confirmed the prebuilt dashboard ships in git (no Node rebuild on the laptop). Watch-dir default fixed too: was the dev box's hardcoded `C:\Users\j` (laptop startup check failed, 0 projects indexed) â€” now defaults to the current user's home (`Path.home()`), so the laptop user's `C:\Users\james` is found with no config (`.env` may still override). Tests: 257 backend green | AI agent |
| 2026-08-08 | 1.16.1 | Pi-hole decommissioned on the laptop (docs/laptop.md `Moving off Docker`): router DNS back to Automatic, docker system prune -a --volumes wipes the old stack + Pi-hole, Docker Desktop uninstalled, old Sentinel task removed; laptop now needs only Python (repo ships the staged dashboard in ackend/app/static â€” no Node). Docs: laptop.md migration section added, 01 Â§9.2/Â§10 and 02 Â§13 updated (Pi-hole retired, DNS Automatic) | User |
| 2026-08-08 | 1.16 | Sprint 15.1 (Native deployment, decommission Docker). Compose/Docker layer removed: docker-compose*.yml, docker/, scripts/dev.py deleted; 
un.py (repo root) is the single starting point â€” startup checks then uvicorn on 127.0.0.1:8000 (--check/--port/--reload/--service/--install/--uninstall); scripts/install_service.py registers the Sentinel Task-Scheduler task (pythonw run.py --service every 5 min, idempotent); scripts/build.py reworked (verify + --dist stages frontend into ackend/app/static, served same-origin by pp/main.py); scripts/release.py ships run.py + scripts + docs + ackend/app; SENTINEL_PORT replaces SENTINEL_API_PORT; Â§4.2 env table + Â§13 rewritten (native runbook, troubleshooting); laptop.md rewritten. Pi-hole left the stack â€” System-page panel + SENTINEL_PIHOLE_* removed. Frontend: /system panel + pi/system.ts types updated. Tests: packaging suite reworked for native artifacts. Docs: changelogs v1.16 | User + AI agent |
| 2026-08-07 | 1.15 | Sprint 15 (Performance tuning + final polish): repo sync now detects changes â€” HEAD is recorded before/after each `git pull --ff-only` (`git rev-parse --short HEAD`), only repos whose HEAD moved are re-indexed, an all-clean pass skips the scan entirely, and knowledge auto-index (v1.14) is narrowed to changed repos; every run persists to a new `SyncRun` table surfaced by `GET /api/v1/system/sync` (header pill shows last outcome). Portfolio scoring rework: build = 21 static (command detected) + 9 proven (green run), tests = 24 static (test files detected) + 6 proven â€” the static part survives a failed run; docs matrix green threshold lowered to 50%; new `GET /portfolio/summary` and a change-driven cache (cached `PortfolioScore` row is served until a build/test/security/file source is newer). Scanner skips self-scan false positives (`data/`, `fixtures/`, `.env`-template names; real `.env` still flagged). `GET /rag/index/status` reports embedded vs total files. Frontend: Dashboard shows real portfolio stats, header sync pill, Knowledge page index progress. Tests: 268 backend / 58 vitest. Docs: 02 Â§14.5 scoring + Â§13.4 sync + Â§2.3 status endpoint, changelogs v1.15 | User + AI |

  | 2026-08-07 | 1.14 | Sprint 12.2 (Bugs + UI pages): world-sim growth bugs fixed â€” new recruitment step (roles scale with population vs fixed bootstrap) + land capacity (`FARM_CAPACITY`), food-store cap (`MAX_FOOD_DAYS=20`, bounds trade growth), world cap (`MAX_ACTIVE_SETTLEMENTS=60`), road-only raids, skill caps at +45%/+90% â€” worlds now grow to ~60 settlements/58 roads naturally; regression test `test_roads_appear_from_natural_growth`. Non-UTF-8 file encoding hardening (repo sync can't abort on a latin-1 `requirements.txt`). Best-effort knowledge auto-index after repo sync (unembedded projects â†’ RAG tasks when Ollama up). Real Projects/Builds/Security pages replace placeholders (run/trigger + history/log/findings UI, `api/tests.ts`). Details in impl guide Â§11/Â§13.4/Â§19, sprint plan v1.14 | User + AI |
| 2026-08-07 | 1.13 | Sprint 12.1 (Repo auto-sync + Pi-hole v6 auth fix + SMB revert): laptop project sync replaces the SMB share with **GitHub-backed auto-sync** â€” `RepoSyncService` (`services/sync_service.py`) lists GitHub repos via a read-only PAT (`SENTINEL_GITHUB_TOKEN`), `git clone`s missing ones, `git pull --ff-only` existing checkouts under `SENTINEL_PROJECTS_DIR` (local target mounted at `/data/projects`), then re-indexes; CLI `sentinel sync` + Celery beat `repo-sync` (SENTINEL_SYNC_INTERVAL_MINUTES, default 15). Â§11 system surface Pi-hole client fixed for v6: session auth (`POST /api/auth` + `X-FTL-SID`; the v5 `X-FTL-API-KEY` header is gone). Desktop SMB plumbing reverted. Details in impl guide Â§13.4, sprint plan v1.13 | User + AI |
| 2026-08-06 | 1.12 | Sprint 12 (Home Server + System page): Â§9.1 topology realized â€” laptop runs the whole stack via one compose file; new `frontend` nginx container serves the dashboard at `http://192.168.4.40:8080` (no Tauri; browser is the shipped UX). Â§10 networking + deployment updated: `docker-compose.dev.yml` explicit dev overrides (bare `docker compose up` = prod), env-overridable `SENTINEL_*` (Ollama host, projects dir via SMB share, API port). New Â§7.3-ish system surface: `/api/v1/system/*` read-only (Ollama availability/models/tokens-per-sec from logged `OllamaQueryLog`; Pi-hole v6 read-only stats; startup checks). Packaging `scripts/build.py`/`release.py`. Details in impl guide Â§13.4, sprint plan v1.12 | User + AI agent |
| 2026-08-05 | 1.10.1 | Sprint 10.5 (Observatory): FG11 extended â€” determinism-only project overviews: shared-technology galaxy graph (key `GET /observatory/galaxy`), activity timeline (`/timeline?days=`, project-created/commit/build/test/finding), per-project architecture trees from indexed file paths (`/architecture/{id}`). New frontend `/observatory` page (ProjectGalaxy SVG, ProjectTimeline, ArchitectureMap). Details in impl guide Â§2.11, Â§14.6 | User + AI agent |
| 2026-08-05 | 1.10 | Sprint 10 (Portfolio Intelligence): FG11 rewritten from "readiness reports" to the shipped implementation â€” deterministic health scoring (build 30 / tests 30 / security 25 / docs 15, missing = 0; latest build log, test pass ratio, security severity penalties, README/Markdown/docs file ratio), `PortfolioScore` upsert-on-read, best-candidate ranking with missing items, feature matrix (âœ“/âš /âœ—, screenshots âœ— until a screenshot feature exists), endpoints `GET /api/v1/portfolio/scores|best-candidates|feature-matrix`, frontend `/portfolio` page (HealthCard, FeatureMatrix). Observatory (galaxy/timeline/architecture) deferred to Sprint 10.5 | User + AI agent |
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1): Â§8.17 + FG13 rewritten from "AI world in its own container" to the shipped deterministic ant-farm â€” own SQLite DB (`data/world_sim/world.db`), seeded per-day RNG (terrain = pure `(x,y,seed)` hash), skill system (survival XP â†’ levels 1â€“5, "build back stronger"), runs in-stack via Celery beat `world-sim-tick` (no new container), god tools (manual tick/reset/accelerate/disaster). New frontend `/world` route with 2D canvas map, settlement inspector, event feed. Details in impl guide Â§11, Â§2.9, Â§5.1 | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): Â§9 rewritten as Hardware Role & Infrastructure Services â€” two-machine topology (laptop `desktop-slur95L` 192.168.4.40 = always-on home server hosting Pi-hole + shared Ollama; desktop 192.168.4.28 = dev workstation), service list and home-server responsibilities; Â§10 Networking Model updated to real LAN IPs, Pi-hole admin (8053) + Ollama (11434) service endpoints, DHCP reservation + LAN DNS rule. Backend/worker `SENTINEL_OLLAMA_HOST` now points at the laptop (`http://192.168.4.40:11434`); the `ollama` compose profile remains a desktop-local fallback | User + AI agent |
| 2026-08-03 | 1.0 | Initial draft based on idea.md | User |
| 2026-08-04 | 1.1 | Sprint 0 decision lock: SQLite as primary DB (was PostgreSQL), ChromaDB embedded (no container), React 19, naming alignment (schemas/, rag_service.py, parsers/), single backend/tests/ | User + AI agent |
