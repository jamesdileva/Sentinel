# Project Sentinel â€” Sprint Plan

> **Version:** 1.1  
> **Status:** Draft â€” Phase 0 (Pre-MVP)  
> **Audience:** Developers, AI coding agents  
> **Related:** See `docs/01_Master_Architecture.md` for architecture overview, `docs/02_Implementation_Guide.md` for technical specifications

This document is the **day-to-day build guide** for Project Sentinel. It breaks down implementation into 15 high-value sprints, each self-contained and verifiable before proceeding to the next.

---

## Sprint Planning Methodology

Each sprint follows this template:

| Field | Description |
|-------|-------------|
| **Objective** | What this sprint accomplishes in one sentence |
| **Inputs** | Data, files, or context needed to start |
| **Outputs** | Deliverables produced by this sprint |
| **Files Created** | New files to create |
| **Files Modified** | Existing files to change |
| **Database Changes** | Any schema changes |
| **Backend Changes** | Service, repository, or API updates |
| **Frontend Changes** | UI component, page, or hook updates |
| **API Endpoints** | New or modified endpoints |
| **Acceptance Criteria** | Specific, testable conditions |
| **Manual Testing** | Step-by-step verification checklist |
| **Definition of Done** | What "done" means for this sprint |
| **Estimated Time** | Rough developer time (AI agent) |
| **Dependencies** | Which previous sprints must be done first |

---

## Sprint Phases Overview

| Phase | Sprints | Description |
|-------|---------|-------------|
| Phase 0 | 1 | Server foundation: scaffolding, DB, models, configs, CLI |
| Phase 1 | 2-3 | Core services: indexing engine, intelligence, RAG |
| Phase 2 | 4 | Docker Compose + orchestration |
| Phase 3 | 5-6 | Dashboard frontend (scaffolding, core pages) |
| Phase 4 | 7 | Automation engine (build/test/security runners) |
| Phase 5 | 8 | RAG integration + chat interface |
| Phase 6 | 9 | World Simulator (optional module) |
| Phase 7 | 10 | Portfolio intelligence + visualizations |
| Phase 8 | 11 | Testing & quality assurance |
| Phase 9 | 12 | E2E integration + MVP release prep |
| Phase 10 | 13 | High-value features (stretch goals) |
| Phase 11 | 14 | Deployment hardening + documentation |
| Phase 12 | 15 | Final polish + performance tuning |

---

## Phase 0: Server Foundation (Sprint 1)

### Sprint 1 â€” Project Scaffolding

**Objective:** Set up the Python backend project structure, dependencies, configuration, and baseline CLI.

**Inputs:**
- Project directory at `C:\Users\j\sentinel`
- Basic understanding of target tech stack (FastAPI, SQLModel, SQLite)

**Outputs:**
- Runnable FastAPI server with health check endpoint
- Project structure ready for development
- Configuration system in place
- CLI entry point for indexing and operations

**Files Created:**
- `backend/pyproject.toml`
- `backend/app/__init__.py`
- `backend/app/main.py` (FastAPI app with health check)
- `backend/app/cli.py` (Sentinel CLI)
- `backend/app/core/config.py` (Settings class)
- `backend/app/core/logging.py`
- `backend/app/core/exceptions.py`
- `backend/app/db/__init__.py`
- `backend/app/db/connection.py`
- `backend/app/db/models.py` (initial SQLAlchemy models)
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `.env.example`
- `AGENTS.md`
- `.python-version`

**Files Modified:**
- `docker/backend/Dockerfile` (new)

**Database Changes:**
- None yet (models defined in code, tables created in Sprint 2)

**Backend Changes:**
- Create FastAPI app with:
  - `GET /` â€” Health check (returns `{"status": "ok"}`)
  - `GET /health` â€” System health endpoint
  - `GET /docs` â€” Swagger UI
- Configure CORS middleware for localhost:3000
- Basic exception handler
- CLI framework using Click or Typer

**Frontend Changes:** None.

**API Endpoints:**
- `GET /` â€” Health check (returns `{"status": "ok"}`)
- `GET /health` â€” Enhanced system health

**Acceptance Criteria:**
- `pip install -e ./backend` succeeds
- `uvicorn app.main:app --reload` starts the server
- `GET /` returns `{"status": "ok"}`
- `GET /health` returns structured health info (version, db status)
- Swagger UI accessible at `/docs`
- `sentinel --help` shows available CLI commands

**Manual Testing:**
1. Run `cd backend && pip install -e .`
2. Run `uvicorn app.main:app --reload`
3. Open `http://127.0.0.1:8420/` â†’ see `{"status": "ok"}`
4. Open `http://127.0.0.1:8420/health` â†’ see health details
5. Open `http://127.0.0.1:8420/docs` â†’ see FastAPI Swagger UI
6. Run `sentinel --help` â†’ see CLI commands listed

**Definition of Done:** Server starts without errors, health check endpoints respond, Swagger UI accessible, CLI framework initialized.

**Estimated Time:** 60 minutes

**Dependencies:** None.

---

## Phase 1: Core Services (Sprints 2-3)

### Sprint 2 â€” Database Schema & Models

**Objective:** Define and create all SQLite tables, relationships, and SQLModel models.

**Files Created:**
- `backend/app/db/models.py` (full schema)
- `backend/app/schemas/` (Pydantic response schemas)
  - `__init__.py`
  - `project.py`
  - `build.py`
  - `test.py`
  - `security.py`
  - `git.py`
  - `portfolio.py`
  - `world_sim.py`
- `backend/app/repositories/` (Initial repository interfaces)
  - `base.py`

**Files Modified:**
- `backend/app/main.py` (add database initialization)
- `backend/app/db/connection.py` (add engine/session setup)

**Database Changes:**
- All tables from Implementation Guide Section 1:
  - `projects`, `repositories`, `files`, `dependencies`, `build_commands`
  - `tests`, `reports`, `security_findings`, `ai_summaries`
  - `git_commits`, `documentation`, `portfolio_scores`
  - `world_state`, `world_entities`, `world_events_log`
  - Junction tables for many-to-many relationships

**Backend Changes:**
- SQLModel engine with SQLite support
- Model definitions for all 15+ tables with relationships
- `init_db()` function to create all tables
- Repository base class with session management

**Acceptance Criteria:**
- `init_db()` creates database file at configured path
- All tables exist after initialization
- All foreign key relationships enforced
- `SQLModel.metadata.create_all(engine)` works without errors
- Repository base class provides session management

**Manual Testing:**
1. Run a Python script that calls `init_db()`
2. Open the SQLite database: `sqlite3 /data/sqlite/sentinel.db`
3. Run `.tables` â†’ see all tables listed
4. Verify foreign key constraints with `.schema projects`

**Definition of Done:** All tables, indexes, and relationships created successfully via `init_db()`.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 1.

---

### Sprint 3 â€” Repository Indexer Engine

**Objective:** Implement the core indexing service that scans repositories and extracts structured metadata.

**Files Created:**
- `backend/app/parsers/__init__.py`
- `backend/app/parsers/base.py`
- `backend/app/parsers/python_parser.py`
- `backend/app/parsers/typescript_parser.py`
- `backend/app/parsers/javascript_parser.py`
- `backend/app/parsers/react_parser.py`
- `backend/app/parsers/fastapi_parser.py`
- `backend/app/parsers/flask_parser.py`
- `backend/app/parsers/node_parser.py`
- `backend/app/parsers/sql_parser.py`
- `backend/app/services/indexer.py`
- `backend/app/repositories/project.py`
- `backend/app/repositories/file.py`
- `backend/app/repositories/dependency.py`
- `backend/tests/test_parsers.py`
- `backend/tests/test_indexer.py`
- `backend/tests/fixtures/sample_python_project/`
- `backend/tests/fixtures/sample_react_project/`

**Files Modified:**
- `backend/app/main.py` (add indexer startup hook)

**Database Changes:**
- Tables already exist from Sprint 2
- Populate during tests

**Backend Changes:**
- `BaseParser` abstract class with `parse_file()`, `supported_languages()`, `extract_structure()`
- `PythonParser`: uses `ast` module to extract functions, classes, imports
- `TypeScriptParser` / `ReactParser`: uses Babel parser for JSX/TSX
- `FastAPIParser`: extracts route definitions, dependencies, models
- `FlaskParser`: extracts route definitions
- `SQLParser`: extracts schema definitions, queries
- `IndexerService`:
  - `scan_repository(project_id)` â†’ orchestrates full index
  - `detect_language(path)` â†’ returns primary language
  - `detect_framework(path)` â†’ returns framework (FastAPI, Flask, React, etc.)
  - `extract_dependencies(path)` â†’ parses package files
  - `extract_build_commands(path)` â†’ finds build/test/start scripts
  - `parse_files(path, extensions)` â†’ uses correct parser per language
  - `update_incremental(project_id, changed_files)` â†’ partial re-index
- Repository classes for projects, files, dependencies

**Frontend Changes:** None.

**API Endpoints:** None (internal service).

**Acceptance Criteria:**
- All parsers correctly extract structure from test fixtures
- `detect_language()` correctly identifies Python, TypeScript, JavaScript
- `detect_framework()` correctly identifies FastAPI, Flask, React, Node
- `extract_dependencies()` parses requirements.txt, package.json correctly
- `extract_build_commands()` extracts scripts from package.json, pyproject.toml
- `scan_repository()` creates database entries for files, deps, commands
- `update_incremental()` only processes changed files

**Manual Testing:**
1. Create a sample Python/FastAPI project in fixtures
2. Run `IndexerService.scan_repository()` on it
3. Verify database has correct entries for files, dependencies, build commands
4. Run `detect_framework()` â†’ verify returns "FastAPI"
5. Run `extract_dependencies()` â†’ verify parsed correctly

**Definition of Done:** All parsers work with test fixtures, indexer service correctly populates database, all tests pass.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2.

---

## Phase 2: Docker Orchestration (Sprint 4)

### Sprint 4 â€” Docker Compose & Service Orchestration

**Objective:** Containerize the backend, set up Docker Compose with all core services, and verify the full stack boots correctly.

**Files Created:**
- `docker/backend/Dockerfile`
- `docker-compose.yml`
- `docker-compose.override.yml` (dev mode)
- `scripts/dev.py`

**Files Modified:**
- `backend/.dockerignore`

**Database Changes:** None (database runs in container).

**Backend Changes:**
- Ensure backend runs in container
- Update config to use environment variables for DB/Chroma/Ollama hosts

**Frontend Changes:** None (frontend scaffolded in Phase 3).

**API Endpoints:** N/A (verification only).

**Acceptance Criteria:**
- `docker compose up` starts backend, SQLite (mounted volume), ChromaDB, Redis
- Backend health check responds
- All services accessible from host
- Environment variables properly mapped
- `scripts/dev.py` successfully starts all services

**Manual Testing:**
1. Run `docker compose up -d`
2. Check services: `docker compose ps`
3. Access `http://localhost:8420/health` â†’ verify responds
4. Check logs: `docker compose logs backend`
5. Verify SQLite database file is created on the mounted volume
6. Stop: `docker compose down`

**Definition of Done:** Full stack boots without errors, all services healthy, dev script works.

**Estimated Time:** 60 minutes

**Dependencies:** Sprint 1, Sprint 2.

---

## Phase 3: Dashboard Frontend (Sprints 5-6)

### Sprint 5 â€” Frontend Scaffolding & Layout

**Objective:** Initialize the React + TypeScript + Vite frontend project, set up routing, layout, and basic styling system.

**Files Created:**
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/src/main.tsx`
- `frontend/src/app.tsx`
- `frontend/src/routes/index.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/types/index.ts`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`

**Files Modified:** None.

**Database Changes:** None.

**Backend Changes:** None.

**Frontend Changes:**
- Vite + React + TypeScript project
- TailwindCSS configured
- Basic routing (Dashboard as default route)
- Layout component (sidebar, header, dark mode toggle)
- Shared TypeScript types matching backend schemas
- Theme system (dark/light)

**API Endpoints:** None consumed.

**Acceptance Criteria:**
- `npm install` (in frontend/) succeeds
- `npm run dev` starts the Vite dev server on port 5173
- Dashboard page renders with placeholder content
- TypeScript compiles without errors
- Dark mode toggle works
- Sidebar navigates between placeholder routes
- Responsive layout works on mobile/desktop

**Manual Testing:**
1. Run `cd frontend && npm install`
2. Run `npm run dev`
3. Open `http://localhost:5173` â†’ verify Dashboard loads
4. Toggle dark/light mode â†’ verify theme changes
5. Resize browser â†’ verify responsive layout
6. TypeScript compilation check: `npx tsc --noEmit`

**Definition of Done:** Frontend project runs, Dashboard renders, TypeScript compiles, theme toggle works.

**Estimated Time:** 60 minutes

**Dependencies:** Sprint 1 (for shared type definitions).

---

### Sprint 6 â€” API Client & React Contexts

**Objective:** Create the Axios API client, typed API call functions, and React contexts for state management.

**Files Created:**
- `frontend/src/api/client.ts` (Axios instance)
- `frontend/src/api/projects.ts`
- `frontend/src/api/builds.ts`
- `frontend/src/api/security.ts`
- `frontend/src/api/portfolio.ts`
- `frontend/src/contexts/ProjectContext.tsx`
- `frontend/src/contexts/BuildContext.tsx`
- `frontend/src/contexts/UIContext.tsx`
- `frontend/src/hooks/useProjects.ts`
- `frontend/src/hooks/useWebSocket.ts`

**Files Modified:**
- `frontend/src/app.tsx` (wrap app in providers)
- `frontend/src/routes/index.tsx` (add placeholder routes)

**Database Changes:** None.

**Backend Changes:** None.

**Frontend Changes:**
- Axios client with base URL and interceptors
- Typed API call functions matching backend schemas
- ProjectContext: provides projects list, loading state, error handling
- BuildContext: manages active jobs and build history
- UIContext: theme, sidebar state, toast notifications
- useProjects hook: fetches projects with error/loading states
- useWebSocket hook: subscribes to live job updates

**API Endpoints:**
- `GET /api/v1/projects/` (consumed)
- `GET /api/v1/health` (consumed)

**Acceptance Criteria:**
- API client successfully calls backend endpoints
- React contexts provide correct initial state
- Hooks return loading states and data
- TypeScript types match backend schemas
- Error handling in API client (404, 500)
- WebSocket connection established for job updates

**Manual Testing:**
1. Start backend (`docker compose up`)
2. Start frontend (`npm run dev`)
3. Open browser dev tools â†’ Network tab
4. Navigate to Dashboard â†’ verify API calls are made
5. Stop backend â†’ verify frontend handles connection errors gracefully
6. Check WebSocket connection status in browser console

**Definition of Done:** API client works, contexts provide state, hooks fetch data, types match backend.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 5, Sprint 2.

---

## Phase 4: Automation Engine (Sprint 7)

### Sprint 7 â€” Build/Test/Security Runners

**Objective:** Implement the AutomationEngine service and Celery workers that execute build, test, and security scan pipelines.

**Files Created:**
- `backend/app/services/build_runner.py`
- `backend/app/services/test_runner.py`
- `backend/app/services/security_scanner.py`
- `backend/app/tasks/__init__.py`
- `backend/app/tasks/build_tasks.py`
- `backend/app/tasks/celery_app.py`
- `backend/app/repositories/build.py`
- `backend/app/repositories/test.py`
- `backend/app/repositories/security.py`
- `backend/app/schemas/build.py`
- `backend/app/schemas/test.py`
- `backend/app/schemas/security.py`
- `backend/app/api/v1/build.py`
- `backend/app/api/v1/test.py`
- `backend/app/api/v1/security.py`

**Files Modified:**
- `backend/app/main.py` (include new routers)

**Database Changes:**
- All tables already exist from Sprint 2

**Backend Changes:**
- `BuildRunner`:
  - `discover_commands(project)` â†’ detect build/test/start scripts
  - `execute_build(project, command)` â†’ run build in Docker subprocess
  - Capture stdout/stderr/exit code
- `TestRunner`:
  - `discover_tests(project)` â†’ detect test frameworks
  - `run_tests(project)` â†’ execute and parse results
  - Parse pytest/jest/mocha output into structured results
- `SecurityScanner`:
  - `scan_project(project)` â†’ orchestrate all scans
  - `scan_dependencies(project)` â†’ pip-audit, npm audit
  - `scan_secrets(project_path)` â†’ TruffleHog, Gitleaks
  - `scan_static(project_path)` â†’ Bandit, Semgrep
- Celery tasks for each step
- API endpoints for manual triggers

**Frontend Changes:** None.

**API Endpoints:**
- `POST /api/v1/builds/run` â€” Trigger manual build
- `GET /api/v1/builds/status/{job_id}` â€” Check build status
- `POST /api/v1/tests/run` â€” Trigger test run
- `POST /api/v1/security/scan` â€” Trigger security scan
- `GET /api/v1/builds/history?project_id={id}` â€” Build history
- `GET /api/v1/tests/results?project_id={id}` â€” Test results
- `GET /api/v1/security/findings?project_id={id}` â€” Security findings

**Acceptance Criteria:**
- Workers successfully execute in Docker
- Build runner captures logs and exit code
- Test runner parses test output correctly
- Security scanner detects sample vulnerabilities/secrets in fixtures
- API endpoints return correct job IDs
- Job status polling works correctly
- Celery beat schedule configured for nightly scans

**Manual Testing:**
1. Start all services: `docker compose up`
2. Add a sample project via CLI or API
3. Trigger a build via API â†’ verify job starts
4. Poll status endpoint â†’ verify completion
5. Check database for BuildLog entry with correct exit code
6. Run security scan â†’ verify findings stored

**Definition of Done:** All runners work end-to-end, API endpoints functional, Celery configured.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer for command discovery), Sprint 4 (Docker).

---

## Phase 5: RAG Integration (Sprint 8)

### Sprint 8 â€” RAG System & Chat Interface

**Objective:** Implement the RAG system with ChromaDB for semantic search and integrate with Ollama for natural language querying.

**Files Created:**
- `backend/app/services/rag_service.py`
- `backend/app/services/ollama_service.py`
- `backend/app/schemas/rag.py`
- `backend/app/api/v1/rag.py`
- `backend/app/data/prompts/project_summary.j2`
- `backend/app/data/prompts/failure_analysis.j2`
- `backend/tests/test_rag.py`
- `frontend/src/pages/KnowledgeExplorer.tsx`
- `frontend/src/components/RagChat.tsx`
- `frontend/src/components/ChatMessage.tsx`
- `frontend/src/api/rag.ts`

**Files Modified:**
- `backend/app/main.py` (add RAG router)
- `frontend/src/routes/index.tsx` (add Knowledge Explorer route)

**Database Changes:**
- ChromaDB collections (not SQLite schema)

**Backend Changes:**
- `OllamaService`:
  - `generate(prompt, model)` â†’ text completion
  - `embed(text)` â†’ vector embedding
  - `is_available()` â†’ connectivity check
- `RagService`:
  - `index_project_knowledge(project)` â†’ embed summaries into ChromaDB
  - `index_git_commits(project)` â†’ embed commit messages
  - `index_test_logs(project)` â†’ embed test output
  - `index_security_reports(project)` â†’ embed findings
  - `search(query, project_id?, top_k)` â†’ semantic search
  - `query(question, project_id?)` â†’ RAG Q&A flow
- Prompt templates for different query types
- API endpoint: `POST /api/v1/rag/query` â€” ask a question
- API endpoint: `POST /api/v1/rag/search` â€” semantic search only

**Frontend Changes:**
- `KnowledgeExplorer` page: search bar, chat interface, results display
- `RagChat` component: chat-style interface with message history
- `ChatMessage`: styled message bubbles with source citations
- API client for RAG endpoints
- Source attribution display (links to files/commits/findings)

**API Endpoints:**
- `POST /api/v1/rag/query` â€” RAG question answering
- `POST /api/v1/rag/search` â€” Semantic search

**Acceptance Criteria:**
- ChromaDB collections created successfully
- Ollama connection works when available
- Indexing stores embeddings correctly in ChromaDB
- Semantic search returns relevant results
- RAG query returns grounded answers with source citations
- Chat interface displays messages with proper styling
- Sources are clickable links to original content

**Manual Testing:**
1. Start all services including Ollama
2. Add a project and trigger indexing
3. Verify ChromaDB has embeddings (check collection counts)
4. Query RAG with "Explain the architecture of [project name]"
5. Verify answer cites relevant files/summaries
6. Test chat interface in browser â†’ verify message flow
7. Verify source links work

**Definition of Done:** RAG system indexes knowledge, answers questions with sources, chat UI functional.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer for summaries), Sprint 5 (frontend foundations).

---

## Phase 6: World Simulator (Sprint 9)

### Sprint 9 â€” World Simulator v1 (deterministic ant-farm)

**Objective:** Ship World Simulator v1 as a deterministic, persistent "living
toy": settlements grow, build roads, expand, trade, and sometimes collapse.
**No generative AI in the simulation loop** (Rule 2/3) â€” AI is optional flavor
on event text only. Runs inside the existing stack via Celery beat; no new
container.

**Files Created:**
- `backend/app/services/world_sim/__init__.py`
- `backend/app/services/world_sim/rules_engine.py` (pure rules: terrain, food,
  growth, construction, expansion, raids, disasters; constants with tests)
- `backend/app/services/world_sim/event_generator.py` (`simulate_day`, 9 steps)
- `backend/app/services/world_sim/skill_system.py` (survival XP â†’ levels 1â€“5)
- `backend/app/services/world_sim/names.py` (seeded name generation)
- `backend/app/services/world_sim/world_simulator.py` (`WorldSimulatorService`)
- `backend/app/db/world_sim_models.py` (separate SQLite metadata + engine)
- `backend/app/schemas/world_sim.py`, `backend/app/api/v1/world_sim.py`
- `backend/app/tasks/world_sim_tasks.py` (beat `world-sim-tick` + catch-up)
- `backend/tests/test_world_sim.py`
- `frontend/src/api/world_sim.ts`
- `frontend/src/pages/WorldSimulatorPage.tsx`
- `frontend/src/components/WorldGridMap.tsx` (2D canvas, BigInt terrain hash)

**Files Modified:**
- `backend/app/core/config.py` (`world_sim_*` settings)
- `backend/app/tasks/celery_app.py` (include + beat schedule)
- `backend/app/cli.py` (`world-sim` command wired)
- `backend/app/main.py` (router, conditional on `world_sim_enabled`)
- `frontend/src/routes/index.tsx`, `frontend/src/components/nav.ts`

**Database Changes:**
- Isolated SQLite at `/data/world_sim/world.db` (own metadata; the main
  `init_db()` never touches it)
- Tables: `world_sim_state`, `world_settlements`, `world_roads`, `world_events`

**API Endpoints (`/api/v1/world-sim`):**
- `GET /state`, `GET /history?limit&before`, `GET /settlements/{id}`
- `POST /tick {days}` Â· `POST /reset {seed?}` Â· `POST /accelerate {time_scale}`
- `POST /disaster {settlement_id, disaster_type}` (flood/drought/plague)

**Acceptance Criteria:**
- Deterministic: same seed + tick history â‡’ identical world (tested)
- Terrain and settlement names reproducible from the seed alone
- Food/growth, construction/level ups, expansion-with-roads on thresholds
- Famine and forced disasters can abandon settlements (incl. god tool)
- Survival experience maps to skill tiers; "build back stronger" bonuses
- Bounded catch-up after downtime (CE max `world_sim_max_catchup_days`)
- Runs in-stack via Celery beat (no container); manual tick via API/CLI
- Frontend `/world` page: canvas map, day stats, event feed, god controls

**Definition of Done:** Full backend suite plus `test_world_sim.py` green
(`pytest`), flake8/black clean, frontend `npm run build` clean; live beat tick
and god tools verified via CLI smoke; docs Â§2/Â§11 updated.

**Deferred (v2+):** diplomacy/technology/governments, per-agent AI, pausing,
`spawn-resources`, swapping the tier table for a real ML model behind the same
helpers.

---

## Phase 7: Portfolio Intelligence (Sprint 10)

### Sprint 10 â€” Portfolio Intelligence & Visualizations

> **Status: Shipped 2026-08-05** (Portfolio only; observatory deferred to Sprint 10.5).

Delivered `PortfolioService` + `GET /api/v1/portfolio/{scores,best-candidates,feature-matrix}`:
deterministic health score (build 30 / tests 30 / security 25 / docs 15, missing
components = 0), recompute-on-read persisted to `PortfolioScore`, ranked
candidates with missing items, and a âœ“/âš /âœ— feature matrix
(`build/test/docs/security/screenshots`; screenshots pinned to âœ— until a
screenshot feature exists). Frontend: `/portfolio` page with `HealthCard` +
`FeatureMatrix` components and `api/portfolio.ts`. 12 new tests
(`tests/test_portfolio.py`), full suite green; `npm run build` clean.
Deferred to **Sprint 10.5**: `GET /observatory/galaxy|timeline|architecture`
+ `ProjectGalaxy` / `ProjectTimeline` / `ArchitectureMap` components.

**Objective:** Implement the PortfolioService that aggregates health scores, and build the visual dashboard components including Galaxy View, Timeline, and Feature Matrix.

**Files Created:**
- `backend/app/services/portfolio_service.py`
- `backend/app/api/v1/portfolio.py`
- `backend/app/api/v1/observatory.py`
- `backend/tests/test_portfolio.py`
- `frontend/src/pages/Portfolio.tsx`
- `frontend/src/components/ProjectGalaxy.tsx`
- `frontend/src/components/ProjectTimeline.tsx`
- `frontend/src/components/HealthCard.tsx`
- `frontend/src/components/FeatureMatrix.tsx`
- `frontend/src/components/ArchitectureMap.tsx`
- `frontend/src/api/portfolio.ts`

**Files Modified:**
- `backend/app/main.py` (add portfolio/observatory routers)
- `frontend/src/routes/index.tsx` (add Portfolio route)

**Database Changes:**
- All tables already exist from Sprint 2

**Backend Changes:**
- `PortfolioService`:
  - `compute_health_score(project)` â†’ 0-100 score from build/test/security/docs
  - `compute_portfolio_score(project)` â†’ full PortfolioScore object
  - `get_best_candidates(min_score)` â†’ ranked list for job hunting
  - `generate_feature_matrix()` â†’ grid of projects Ã— features
- `ObservatoryService` (for Architecture Maps):
  - `get_project_structure(project_id)` â†’ nested component tree
  - `get_component_details(component_name)` â†’ purpose, used by, added when

**Frontend Changes:**
- `Portfolio` page: container for all visualizations
- `ProjectGalaxy`: interactive node-link diagram of tech relationships
- `ProjectTimeline`: chronological history of all projects
- `HealthCard`: per-project health score with component indicators
- `FeatureMatrix`: grid view of all projects Ã— features
- `ArchitectureMap`: expandable tree of project components

**API Endpoints:**
- `GET /api/v1/portfolio/scores` â€” All project scores
- `GET /api/v1/portfolio/best-candidates` â€” Ranked projects
- `GET /api/v1/portfolio/feature-matrix` â€” Feature matrix grid
- `GET /api/v1/observatory/galaxy` â€” Project galaxy graph data
- `GET /api/v1/observatory/timeline?days=365` â€” Portfolio timeline
- `GET /api/v1/observatory/architecture/{project_id}` â€” Architecture tree

**Acceptance Criteria:**
- Health scores computed correctly from component statuses
- Feature matrix displays all projects with build/test/docs/security/screenshot status
- Galaxy view shows shared technologies between projects
- Timeline displays project creation and activity
- Architecture maps show nested component trees
- Best candidates ranking works with missing item detection
- All visualizations render correctly in browser

**Manual Testing:**
1. Add 3+ projects to Sentinel
2. Run partial pipelines on each (build, test, security, docs)
3. Access `/api/v1/portfolio/scores` â†’ verify scores returned
4. Access `/api/v1/portfolio/feature-matrix` â†’ verify grid structure
5. Open Portfolio page â†’ verify all visualizations render
6. Click a HealthCard â†’ verify it navigates to project details
7. Hover galaxy nodes â†’ verify tooltips show shared tech
8. Verify feature matrix shows âœ“/âš /âœ— correctly

**Definition of Done:** All portfolio intelligence services work, visualizations render with real data.

**Estimated Time:** 240 minutes

**Dependencies:** Sprint 3 (indexer), Sprint 7 (build/test/security results), Sprint 5 (frontend).

---

## Phase 8: Testing & Quality (Sprint 11)

### Sprint 11 â€” Testing & QA

> **Status: Shipped 2026-08-06** â€” 211 backend tests (95.6% cov), 29 Vitest
> component tests, 7 Playwright E2E specs, all green. Details in changelog v1.11.

**Objective:** Implement comprehensive test coverage for backend services, API endpoints, and frontend components.

**Files Created:**
- `backend/tests/conftest.py`
- `backend/tests/test_api.py`
- `backend/tests/test_db.py`
- `backend/tests/test_automation.py`
- `backend/tests/test_security.py`
- `backend/tests/test_world_sim.py`
- `backend/tests/test_e2e.py`
- `frontend/src/components/__tests__/`
  - `Dashboard.test.tsx`
  - `ProjectCard.test.tsx`
  - `GalaxyView.test.tsx`
  - `HealthCard.test.tsx`
- `frontend/vitest.config.ts`
- `frontend/tests/e2e/portfolio.spec.ts`

**Files Modified:**
- `backend/pyproject.toml` (add pytest config + coverage)
- `frontend/package.json` (add Vitest + Playwright dependencies)

**Database Changes:** None.

**Backend Changes:** None (test-only changes).

**Frontend Changes:** None (test-only changes).

**API Endpoints:** All existing endpoints tested.

**Acceptance Criteria:**
- Backend test coverage >= 80% for services and repositories
- All API endpoints have integration tests (200/404/400 cases)
- E2E test covers: index project â†’ scan â†’ build â†’ test â†’ docgen â†’ RAG query â†’ portfolio score
- Frontend unit tests cover all new components
- E2E tests cover key user workflows

**Manual Testing:**
1. Run `cd backend && pytest -v --cov=app`
2. Verify coverage report shows >= 80%
3. Run `cd frontend && npm run test`
4. Verify all unit tests pass
5. Run `cd frontend && npm run test:e2e`
6. Verify E2E tests pass

**Definition of Done:** All test suites pass, coverage >= 80%, E2E covers critical flows.

**Estimated Time:** 150 minutes

**Dependencies:** All previous sprints (tests cover everything built).

---

## Phase 9: E2E Integration & Release Prep (Sprint 12)

### Sprint 12 â€” E2E Integration & MVP Release Preparation

> **Status: Shipped 2026-08-06** â€” home-server release. `docker-compose.yml`
> gained the `frontend` nginx service (dashboard at `:8080`); dev overrides
> moved to explicit `docker-compose.dev.yml` (prod is the default). Env
> overridable `SENTINEL_*` (Ollama host, projects dir via SMB, API port).
> Startup validation in `main.py`. `scripts/build.py` + `scripts/release.py`
> (zip + sha256 + changelog). CLI finalized: `portfolio`, `docs`,
> `world-sim start`. System page `/system` (Ollama availability/models/
> tokens-per-sec from logged `OllamaQueryLog` + Pi-hole v6 read-only stats +
> startup checks). ErrorBoundary wrapper. Tests: 238 backend (95.4% cov),
> 36 Vitest, 9 E2E. Tauri deferred ("if attempted" â€” browser dashboard is the
> shipped UX). Docs: 02 Â§13.4 runbook, AGENTS.md deployment, changelogs v1.12.

**Objective:** Validate the full system end-to-end, prepare packaging scripts, and ensure the MVP is shippable.

**Files Created:**
- `scripts/build.py`
- `scripts/release.py`
- `backend/app/cli.py` (finalize CLI commands)
- `frontend/src-tauri/tauri.conf.ts`
- `AGENTS.md` (update with deployment info)

**Files Modified:**
- `docker-compose.yml` (add prod profiles)
- `backend/app/main.py` (add startup validation)

**Database Changes:** None.

**Backend Changes:**
- Finalize CLI commands:
  - `sentinel index <path>`
  - `sentinel scan <project_id>`
  - `sentinel build <project_id>`
  - `sentinel test <project_id>`
  - `sentinel docs <project_id>`
  - `sentinel portfolio`
  - `sentinel world-sim start/tick/state/reset`

**Frontend Changes:**
- Tauri configuration for desktop packaging
- Error boundaries and loading states finalized

**API Endpoints:** N/A (finalizing existing ones).

**Acceptance Criteria:**
- Full E2E flow works: start services â†’ index project â†’ run pipeline â†’ query RAG â†’ view portfolio
- CLI commands work from host machine
- `scripts/build.py` creates Docker images
- `scripts/release.py` generates release package
- Tauri desktop app builds successfully (if attempted)
- Documentation complete for setup and usage

**Manual Testing:**
1. Start all services: `docker compose up -d`
2. Add a local project via CLI: `sentinel index ~/my-project`
3. Trigger full pipeline: `sentinel build <id>` â†’ `sentinel test <id>` â†’ `sentinel scan <id>`
4. Query RAG: `sentinel ask "How does the auth module work?"`
5. View portfolio: `sentinel portfolio`
6. Check dashboard: `http://localhost:3000`
7. Run build script: `python scripts/build.py`

**Definition of Done:** Full system works end-to-end, CLI functional, release scripts ready.

**Estimated Time:** 120 minutes

**Dependencies:** All previous sprints.

---

## Phase 10: High-Value Features (Sprint 13)

### Sprint 13 â€” High-Value Features (Stretch Goals)

**Objective:** Implement select high-value features identified as post-MVP enhancements that significantly improve Sentinel's utility.

**Files Created:**
- `backend/app/services/dependency_drift.py`
- `backend/app/services/code_duplication_finder.py`
- `backend/app/services/tech_debt_analyzer.py`
- `backend/app/services/scenario_simulator.py`
- `backend/app/api/v1/analysis.py`
- `frontend/src/pages/AnalysisDashboard.tsx`
- `frontend/src/components/DependencyDriftChart.tsx`
- `frontend/src/components/TechDebtHeatmap.tsx`
- `frontend/src/components/DuplicationFinder.tsx`

**Files Modified:**
- `backend/app/main.py` (add analysis router)
- `frontend/src/routes/index.tsx` (add Analysis route)

**Database Changes:**
- New tables: `dependency_drift_reports`, `duplication_findings`, `tech_debt_items`, `analysis_jobs`

**Backend Changes:**
- `DependencyDriftDetector`:
  - Cross-compares versions across all projects
  - Identifies outdated/incompatible dependencies
  - Suggests coordinated upgrade paths
- `CodeDuplicationFinder`:
  - Finds copy-pasted code blocks across projects
  - Suggests shared library extraction
- `TechDebtAnalyzer`:
  - Aggregates TODOs, FIXMEs, skipped tests
  - Computes complexity metrics (cyclomatic complexity)
  - Generates prioritized tech debt list
- `ScenarioSimulator`:
  - Propagates impact of changes across dependency graph
  - Answers "what if" questions about removing functions/modules

**Frontend Changes:**
- `AnalysisDashboard` page with tabs for each analysis type
- `DependencyDriftChart`: visualization of version discrepancies
- `TechDebtHeatmap`: color-coded debt by project/component
- `DuplicationFinder`: side-by-side comparison of duplicated code

**API Endpoints:**
- `GET /api/v1/analysis/dependency-drift` â€” Version discrepancies
- `GET /api/v1/analysis/code-duplication` â€” Duplicated code blocks
- `GET /api/v1/analysis/tech-debt` â€” Tech debt heatmap
- `POST /api/v1/analysis/scenario` â€” What-if impact simulation

**Acceptance Criteria:**
- Dependency drift detector identifies version mismatches across projects
- Code duplication finder locates copy-pasted code
- Tech debt analyzer computes complexity and TODO density
- Scenario simulator propagates impact correctly
- All visualizations render correctly in browser

**Manual Testing:**
1. Add 2+ projects with differing dependency versions
2. Run dependency drift analysis â†’ verify mismatches detected
3. Run duplication finder â†’ verify duplicated code highlighted
4. Run tech debt analysis â†’ verify heatmap populated
5. Run scenario simulation â†’ verify impact propagation

**Definition of Done:** All four high-value features work with real data, UI visualizations render.

**Estimated Time:** 240 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer), Sprint 7 (pipeline results).

---

## Phase 11: Deployment Hardening (Sprint 14)

### Sprint 14 â€” Deployment & Maintenance

**Objective:** Finalize deployment scripts, add backup/restore procedures, and ensure the system is maintainable long-term.

**Files Created:**
- `scripts/backup.py`
- `scripts/restore.py`
- `scripts/monitor.py`
- `docs/resources/deployment-diagram.png` (or ASCII)
- `backend/scripts/migrate.sh`

**Files Modified:**
- `docker-compose.yml` (add prod overrides)
- `AGENTS.md` (add maintenance section)

**Database Changes:**
- Optional: Migration scripts for schema evolution

**Backend Changes:**
- Migration runner for schema updates
- Backup/restore endpoints in CLI
- Health monitoring endpoint aggregation
- Log rotation configuration

**Frontend Changes:**
- Error boundary improvements
- Offline fallback for dashboard

**API Endpoints:**
- `GET /api/v1/system/backup` â€” Trigger database backup
- `GET /api/v1/system/status` â€” Comprehensive system status
- `GET /api/v1/system/logs` â€” Recent log entries

**Acceptance Criteria:**
- `scripts/backup.py` creates consistent backup snapshot
- `scripts/restore.py` restores from backup
- `scripts/monitor.py` reports system health
- Migration runner applies schema changes safely
- Log rotation configured and tested
- Deployment guide documented

**Manual Testing:**
1. Run `python scripts/backup.py` â†’ verify backup created
2. Corrupt database â†’ run `python scripts/restore.py backup_file` â†’ verify restoration
3. Run `python scripts/monitor.py` â†’ verify health report
4. Check log rotation â†’ verify old logs cleaned

**Definition of Done:** Backup/restore/monitor scripts work, deployment hardened, maintenance procedures documented.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 12 (release prep).

---

## Phase 12: Final Polish (Sprint 15)

### Sprint 15 â€” Performance Tuning & Final Polish (v1.15)

**Objective:** Remove the last performance hotspots (sync, portfolio reads),
close outstanding fix-ups, and put real numbers on the Dashboard.

**Backend Changes (shipped):**
- **Sync change detection**: `RepoSyncService` records each repo's HEAD
  (`git rev-parse --short HEAD`) before/after `git pull --ff-only`; only repos
  whose HEAD moved are re-indexed, and an all-clean pass skips the scan
  entirely (no dir walks, no re-parse, portfolio caches stay fresh). Knowledge
  auto-index (v1.14) is narrowed to changed repos only.
- **Sync persistence**: every run is stored in a new `SyncRun` table and read
  back by `GET /api/v1/system/sync` (config + last run + interval).
- **Portfolio scoring rework**: build = 21 static (command detected) + 9 proven
  (passed); tests = 24 static (test files detected) + 6 proven (green run);
  the static part survives a failed run. Docs matrix green threshold lowered to
  50%. New `GET /portfolio/summary` (projects/buildable/open findings/avg health).
- **Portfolio change-driven cache**: reads serve the `PortfolioScore` row while
  it is newer than every source row (build/test/repo/finding timestamps);
  recompute only when data actually changed.
- **Scanner false-positive skip** (self-scan): ignored name parts `data`,
  `fixtures`, templates; real `.env` detections still flagged.
- **RAG index status**: `GET /rag/index/status` â€” embedded vs total files per
  project (or all), no jobs triggered.

**Frontend (shipped):**
- Dashboard stat cards now show real numbers (project count, active jobs,
  open findings, average health + buildable hint) via `/portfolio/summary`.
- Header sync pill (Layout): last repo-sync outcome â€” `Synced <time>` /
  `Sync failed` (title = detail) / `Sync not run` / hidden when unconfigured.
- Knowledge page shows per-project index progress
  ("X of Y files embedded", `âœ“` when complete).

**Acceptance Criteria (v1.15, all met):**
- Repo sync with zero changes runs in seconds and touches no data (skipped
  re-index + no knowledge queueing; verified by unit tests)
- Dashboard shows real portfolio stats; portfolio tab keeps serving from cache
  instead of recompute-per-read
- All new endpoints/services/utilities covered by tests (python + vitest)

**Definition of Done:** Sprint 15 changelog rows in docs/01, /02, /03; Â§14.5
and Â§13.4 updated; full backend + frontend suites green.

> Status: **shipped v1.15** (user-approved scope: only change-triggered
> re-indexing; portfolio cache read-first; real dashboard stats; sync pill;
> knowledge status; scanner false-positive skip)

**Dependencies:** All previous sprints.

---

## Phase 13: Native Deployment (Sprint 15.1)

### Sprint 15.1 â€” Decommission Docker, native autostart (v1.16)

**Objective:** Remove the container/compose layer entirely. One uvicorn process
serves API + built dashboard on the always-on machine (laptop at the time,
single desktop since v1.17.7); a Task-Scheduler task keeps it
running from login. Pi-hole leaves the Sentinel stack (independent service;
docs/pi-hole-idea.md).

**Backend (shipped):**
- `run.py` at the repo root is the single starting point: startup checks
  (Python, `.env`/data dirs, frontend built, SQLite writable, Ollama) then
  uvicorn on `127.0.0.1:8420`; flags `--check`, `--port`, `--reload`.
  (`--service`/`--install`/`--uninstall` were removed in v1.17.7.2 with
  `scripts/install_service.py`.)
- `scripts/build.py` reworked â€” verify (backend pytest+lint, frontend test)
  and `--dist` stages `frontend/dist` into `backend/app/static`; `scripts/dev.py`,
  `docker-compose*.yml`, and `docker/` deleted. `scripts/release.py` archive
  now ships run.py + scripts + docs + `backend/app`.
- System page Pi-hole panel removed; `SENTINEL_PIHOLE_*` env vars dropped.

**Acceptance Criteria (all met):**
- Fresh machine: venv + requirements + `npm run build` +
  `scripts/build.py --dist` â†’ `.\.venv\Scripts\python.exe run.py` serves API +
  dashboard on :8420
- Autostart survives reboot via a Task-Scheduler task; double-runs exit fast
- `pytest tests` (backend), frontend vitest, and `npm run build` green;
  no `docker`/compose/pihole references left in shipped code

**Definition of Done:** changelog rows in docs/01, /02, /03 and laptop.md
rewritten for the native runbook.

> Status: **shipped v1.15** (native install; Docker Compose, dev.py,
> docker/, Pi-hole panel removed)

**Dependencies:** Sprint 12 (main.py already served the SPA same-origin) and
Sprint 15 (sync/portfolio rework stays untouched by this sprint).

---

## Appendix A: Sprint Timeline Summary

| Sprint | Name | Est. Time | Depends On |
|--------|------|-----------|------------|
| 1 | Server Foundation | 60 min | None |
| 2 | Database Schema | 90 min | 1 |
| 3 | Repository Indexer | 180 min | 2 |
| 4 | Docker Orchestration | 60 min | 1, 2 |
| 5 | Frontend Scaffolding | 60 min | 1 |
| 6 | API Client & Contexts | 90 min | 5, 2 |
| 7 | Build/Test/Security Runners | 180 min | 2, 3, 4 |
| 8 | RAG & Chat Interface | 180 min | 2, 3, 5 |
| 9 | World Simulator | 150 min | 2, 4, 5 |
| 10 | Portfolio Intelligence | 240 min | 3, 7, 5 |
| 11 | Testing & QA | 150 min | All prior |
| 12 | E2E Integration | 120 min | All prior |
| 13 | High-Value Features | 240 min | 2, 3, 7 |
| 14 | Deployment | 90 min | 12 |
| 15 | Performance Tuning | 120 min | All prior |

**Total Estimated Time**: ~24 hours (AI agent time)

---

## Appendix B: Environment Setup Checklist

Before starting any sprints:

1. Install Docker Desktop
2. Install Python 3.11+
3. Install Node.js 20+ and npm
4. Clone this repository
5. Copy `.env.example` to `.env`
6. Run `docker compose up -d` to start Redis, Celery workers, SQLite volume
7. Run `docker compose --profile ollama up` to start Ollama
8. Install Ollama models: `ollama pull llama3.1:8b`, `ollama pull nomic-embed-text`
9. Backend: `cd backend && pip install -e .`
10. Frontend: `cd frontend && npm install`
11. Run `sentinel --help` to verify CLI is installed

---

## Appendix C: Sprint Template

Use this template for any new sprint added to the plan:

```markdown
### Sprint N â€” [Name]

**Objective:** [One sentence summary]

**Files Created:**
- [file1]
- [file2]

**Files Modified:**
- [existing file]

**Database Changes:** [Describe or "None"]

**Backend Changes:** [Summarize key changes]

**Frontend Changes:** [Summarize or "None"]

**API Endpoints:**
- [Method] [path] â€” [description]

**Acceptance Criteria:**
- [Criterion 1]
- [Criterion 2]

**Manual Testing:**
1. [Step 1]
2. [Step 2]

**Definition of Done:** [Clear completion statement]

**Estimated Time:** [X] minutes

**Dependencies:** [Previous sprint numbers]
```

---

## Changelog

### Release 0.1.0 (2026-08-06)
- 

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-17 | 1.17.13.6 | **TV-Scheduler tester rewritten for the auto-launched packaged app.** First live run of 1.17.13.5 failed at `GET http://127.0.0.1:3050 -> 404` — two real bugs in the tester, not the app. (1) The old tester launched the dev stack via `concurrently`, which is not on PATH (and would have collided with the packaged app's backend on :3050 — EADDRINUSE); (2) it asserted `GET /` but the Express server serves only the API + `/health` — the frontend is loaded by Electron from app.asar (`loadFile`), so there is no static root route and `GET /` is 404 by design (the 2026-08-15 ground-truth note was wrong). The tester now probes `GET /health` (retries while the server binds) against the auto-launched packaged app and screenshots the window. Verified live: `auto-launched packaged app: TV Scheduler.exe` -> `/health -> 200` -> 3 window captures (1600x1000, 231-256 gray levels). The packaged app's `DB backup failed ... app.asar` error is a cosmetic read-only-asar quirk (non-fatal, app keeps serving). |
| 2026-08-17 | 1.17.13.5 | **Generic app presence: testers auto-launch the packaged app and auto-capture its window; browser apps get an auto dashboard render.** Live-review gap (WFT/TV-Scheduler sessions since v1.17.13.2): capture is window-targeted now, but every tester had to code its own launch + capture — WFT's tester never launched the UI, so its runs recorded nothing even though a real app existed (`release/win-unpacked/WorkFlow Toolkit.exe`). (1) **`launcher_detect.py`** (new, deterministic path scan): finds a project's packaged app binary — electron-builder `release/win-unpacked` (WFT) and `dist/win-unpacked` (TV-Scheduler), tauri `out/` and `src-tauri/target/release` (future; Sentinel is the only tauri app, deferred) — excluding installers (`Setup*`, `*.blockmap`), `elevate.exe`, bundled pythons. PyInstaller `backend/dist` (dinner menu) is deliberately NOT scanned: payload names are ambiguous and browser capture covers those apps. (2) **`TesterRunner` auto-launch**: before a tester runs, the packaged app is launched detached and its window (polled up to 20 s) is captured with a labeled checkpoint — desktop apps record their real UI with zero per-tester code; no launcher or no window is an honest skip, never a failure. `Tester.auto_launch` (default True) opts out. Affected projects: WorkFlow-Toolkit + TV-Scheduler only (CG has no packaged exe, AG's tkinter GUI keeps its own launch, browser apps find nothing). (3) **Auto-render**: a tester that declared `web_url` but registered no screenshots gets one headless render of it after the run — dinner menu's first-ever run captures its dashboard with no per-tester line (card-game/demake render themselves; deduped). Deferred (documented decision): the click-through engine — driving UI features (buttons, forms) and screenshotting each step — needs Playwright (browser) / UIA (desktop); REST/CLI feature testing + static captures remain the deterministic path (Rules 2+3). Candidate v1.17.14. Tests: +11 (12 detector-matrix cases incl. PyInstaller exclusion, auto-launch launch+capture, no-window skip, opt-out, launch-failure, auto-render when empty, dedupe when tester rendered, no-web_url no-op). |
| 2026-08-16 | 1.17.13.4 | **Build & Open actually opens browser-served apps.** Live UX report: Card-Game's "Open app" was green but opened nothing visible — the launch ran the stored startup (frontend-only) detached and stopped; no browser window, and with the tester's leftovers still on :5173/:3000 the new vite drifted to :5174 (orphan, nobody knows the URL). (1) **`Tester` gains app facts for build->open**: `web_url` (browser-served apps), `extra_launch` (servers the stored startup does not cover), `ports` (restart semantics). Populated: Card-Game `http://localhost:5173` + `cd backend && node server.js` + `(5173, 3000)`; Dinner-Menu-Generator `http://localhost:5173` + `cd backend && python app.py` + `(5173, 5000)`; Demake-Engine `http://localhost:8000` + `(8000,)`; Electron/desktop testers unchanged (no web_url — they open their own window). (2) **`BuildRunner` build->open flow**: before launching, listeners on the declared ports are killed (`netstat -ano` → `taskkill /F`, no new deps) so the opened instance is always the current code and never an orphan on a drift port; then the stored startup plus each extra server launch detached into `<slug>.log`; then the default browser opens the web_url (`os.startfile`) — all user-initiated via the Run Build / Open app click; beats never launch anything (Rule 2). The BuildLog records every step ("Freed ports for restart: …", "App launched: …", "App opened: …"). Tests: +3 build_runner — ports freed + extras launched + browser opened (drift port never killed); no listeners → still launches and opens; desktop app → no ports freed, no browser — with netstat/taskkill/startfile faked, nothing real spawned. |
| 2026-08-16 | 1.17.13.3 | **Card-Game backend migrated off PostgreSQL to local better-sqlite3 (app-side work, driven from Sentinel).** The app's `DATABASE_URL` pointed at a dead Supabase pooler endpoint — its Express server always crashed on first query, so the tester could never pass the backend check. Working in the Card-Game repo: (1) `backend/db.js` is now a better-sqlite3 singleton (`backend/cardgame.db`, gitignored, WAL, `foreign_keys=ON`) that self-provisions from the new `backend/schema.sql` on first open — fresh clones need no manual init; (2) the `connect-pg-simple` session store is replaced by a ~40-line custom SQLite store (`backend/sessionStore.js`, table `session(sid, sess, expire)`), drop-in compatible with express-session; (3) all 38 `pool.query` sites in `authRoutes.js`/`gameRoutes.js` converted to prepared `?` statements (`.get()`/`.all()`/`.run()`; `RETURNING` and `ON CONFLICT … excluded` verified working in SQLite); a latent `db.query` ReferenceError in `/buy-upgrade` was fixed along the way; (4) the 2026-04-06 PostgreSQL dumps migrated to git-tracked `backend/schema.sql` + `seed.sql` (`npm run db:init`, `INSERT OR IGNORE`, data verified id-for-id: 9 users / 70 inventory / 27 deck); `DATABASE_URL` deleted from `backend/.env`, the old `.sql` dumps deleted from the tree, `cardgame.db*` gitignored; (5) live-verified end to end against the real app: GET / 200, register→login roundtrip (daily-reward streak + balance update), `/api/game/state` with migrated account data, spin, open-crate (RETURNING), set-deck upsert + LEFT-JOIN deck read, add-balance — all on SQLite with zero errors; the frontend production build passes. The app now runs fully local with no cloud dependency, and its tester passes: Card-Game smoke PASSED live with a headless dashboard render. Tester-side change: `card_game.py` docstring/description ground truth updated to the SQLite architecture. |
| 2026-08-16 | 1.17.13.2 | **No desktop-grab fallback; headless dashboard captures for browser apps.** Live-verify verdict after demake runs: a real app is window-capturable (Electron/tkinter/native) or browser-served (registered via headless renders) — grabbing whatever the user has on screen (Reddit + VS Code mid-run) is noise. (1) **`AppSessionService.capture()`** no longer falls back to `ImageGrab.grab()` of the desktop: a session whose app owns no window returns None and records nothing (skip logged); the end-of-session auto-capture skips windowless sessions too. `POST /api/v1/sessions/{id}/screenshots` answers **409** with a pointer to the tester-render path (the Sessions UI toasts the detail). (2) **`TesterContext.render_and_register(url, label)`** — generalized capture path for browser-served apps: headless-render the URL in invisible Edge, assert the frame non-blank (PIL gray-level histogram, deterministic; blank → `TesterAssertionError`, Edge failure → `TesterEnvError`), register it via `screenshot_file()`; temp PNG cleaned up. Demake tester now registers the upload dashboard (`/`) + the generated game (`game.html?id=…`); Card-Game tester registers its Vite frontend first screen — first-time live run of that tester. Tests: +3 backend (ctx render_and_register renders+registers+cleans up, blank frame → assert, render failure → env) +1 API (windowless capture → 409); full-screen-fallback tests reworked to skip/window semantics. (3) **Card-Game first live runs failed — Vite v8 binds `localhost` on IPv6 (`::1:5173`) here, the tester hardcoded `127.0.0.1:5173` → refused** (the apparent 8.9 s 'boot race' in the first run was a red herring; retries in run two kept hitting the wrong address). The tester now targets `http://localhost:5173`, which resolves to whatever the dev server actually binds. (4) **`ctx.http()` gains `retries`/`retry_delay_s`** — dev servers can take ~10 s to bind after launch; unreachable errors re-attempt and only the successful attempt checkpoints. Tests: +2 (retry succeeds after failures; retries exhausted → TesterEnvError).  (5) **Card-Game's backend check failed honestly** — the app's `DATABASE_URL` (dotenvx in `backend/.env`) points at a cloud Postgres host that no longer resolves (ENOTFOUND — dead/expired endpoint); the Express server prints "Server running on 3000" then dies on the first pool query (Node ≥22 fatal unhandled rejection), so the session ends investigate with the real error in the app log. App-side fix (point `DATABASE_URL` at local PG :5432 and provision the schema, or delete the tester) is user work, not tester work. | AI agent |
| 2026-08-16 | 1.17.13.1 | **Headless game captures for browser-served apps.** Live-verify follow-up: the Demake E2E tester runs headless (FastAPI + HTTP polls, no window), so its end-of-session auto-capture grabbed the user’s desktop (full-screen fallback) instead of the game — a portfolio dead end. (1) **`utils/headless_render.py`** — `render_url()` renders a URL in headless Microsoft Edge (`--headless=new --screenshot --window-size=1280,800 --virtual-time-budget=15000`), deterministic and desktop-independent; Edge resolves via known install paths → PATH; failures raise `HeadlessRenderError` (bounded subprocess timeout). (2) **`AppSessionService.register_screenshot()`** — registers a pre-rendered PNG into `data/screenshots/<slug>/` (copies PNG + 90×60 thumb, inserts the `SessionScreenshot` row, method logged `headless-render`); shared save tail extracted from `capture()`. (3) **`TesterContext.screenshot_file()`** — mirrors `screenshot()` for pre-rendered files. (4) The Demake tester now renders `game.html?id=<demake_id>&api=…` after the asset check and asserts the frame is non-blank (PIL gray-level histogram, deterministic), so a WebGL blank frame fails the tester honestly; the auto end-of-session desktop grab remains as a second shot. Pattern generalizes to any browser-served app (Sentinel’s own dashboard later; WFT’s Electron shell gets a window-targeted capture like Cg). Tests: +10 backend (render_url success/non-zero/missing-browser/timeout/no-output, find_edge known-path/PATH/missing, register_screenshot row+thumb+missing source, ctx screenshot_file). | AI agent |
| 2026-08-16 | 1.17.13.0 | **Deterministic-first RAG tier + server-persisted chat answers.** Trigger: a live data-loss incident — a tab reload mid-generation aborted the in-flight `/rag/query` fetch; the server finished the 174.5 s Ollama call (287 tokens, llama3.1:8b, `ollamaquerylog`) and delivered the answer to a dead connection (no access-log line, never rendered), leaving only the user row in the room. (1) **Deterministic summary tier (Rule 3)** — with a `project_id` and an overview question, `query()` answers from the project's stored architecture `KnowledgeSummary`: no embedding, no retrieval, no Ollama call. Intent gate `_is_overview_question()`: ≤ 120 chars, an `_OVERVIEW_MARKERS` substring ("what is this project", "tell me about this project", "overview", …) and no `_SPECIFIC_MARKERS` ("how do", "why does", "error", "test", "build", "api endpoint", …) — specific questions still flow to retrieval + LLM. The summary is returned verbatim with its "Here is a concise architecture summary…" preamble stripped, `sources: ["project_summaries"]`, distance 0.0 → `confidence: 1.0`, `model` + `generated_at` preserved (Rule 7 provenance). (2) **Server-side answer persistence** — `POST /rag/query` now saves the assistant reply into the room's `ChatMessage` history (project_id or `__all__`, sources, model, confidence) before returning, so a reload mid-generation can no longer lose an answer; RagChat dropped its client-side success-path save (user + error-path saves remain). (3) **Validation-body logging** — the incident's unexplained 422 had an unlogged body; a `RequestValidationError` handler now logs the rejected body (first 2000 chars) for `/rag/chat` + `/rag/query` so a recurrence is diagnosable. Forensics aside: a double-spawned zombie uvicorn (no listening port, same DB/Chroma) was killed; DB-local timestamps are UTC+7 vs the UTC log, established for future correlation. Tests: +6 backend (intent gate, stored-summary answer, fall-through without summary, assistant row persisted, overview answered from stored summary, 422 body logged), +2 frontend (answer saved server-side only); 517 backend / 128 frontend green; black/isort/flake8 clean. Live-verify follow-up: the Cg tester no longer double-starts the repo's own backend (`npm run start` = concurrently `run.py` + electron; run.py exited on the tester's port-8000 bind and `concurrently -k` killed the whole tree, so the Electron window never opened and its "window" screenshot silently fell back to full-screen). The tester now launches `electron-dev` only, with a 45 s cold-boot wait; window-targeted capture verified live (1400×900 window-render, in-test + end-of-session; PrintWindow handled Chromium compositing without a blank frame). Demake-side: the E2E tester's final asset fetch 404’d because demake-engine’s sprite cache-hit path returned the old run’s file without copying it into the current run’s `sprites/` (game UI would 404 too); fixed in demake-engine (`shutil.copy2` on the cache-hit branch) and tester re-verified green. | AI agent |
| 2026-08-15 | 1.17.10.0 | **Sessions (Tier 1 recorder) + Tier 4 screenshot capture.** Backend: three new tables â€” `AppSession` (project FK, status enum running/passed/failed/investigate, expected/actual, started/ended, `log_slice`), `SessionCheckpoint` (session FK, label, at), `SessionScreenshot` (session FK, nullable checkpoint FK, path, captured_at). `services/app_sessions.py` (one module, Rule 4) annotates the app's *own* log (`data/logs/apps/<slug>.log`, same derivation as `build_runner`) with `[sentinel] Session started|checkpoint:|Session ended <iso> <id>: ...` markers and captures the deterministic log slice between a session's own markers (interleaved sessions slice to their own end marker or EOF; byte-for-byte reproducible). Screenshots: PIL `ImageGrab.grab()` full-screen grabs + 90Ã—60 thumbs under `data/screenshots/<slug>/`, on demand or auto at session end (Rule 2 â€” capture, never act); delete removes rows + PNG/thumb files. Portfolio export: copies PNG + thumb into `SENTINEL_PORTFOLIO_DIR` (`images/sessions/`, default `C:\Users\j\projects\jamesdileva\jamesdileva.github.io`; new env in config.py + `.env.example`) and returns a ready-made card HTML snippet matching the site's `.card`/`openModal` markup â€” Sentinel never pushes, the user pastes and commits manually. API: `POST/GET/PATCH/DELETE /api/v1/sessions`, `POST .../checkpoints`, `POST .../end`, `POST .../screenshots` (+`/{shot_id}/export`), media route `GET .../screenshots/{filename}` (filename whitelist + resolve-inside-dir guard â€” traversal blocked). Dependency: `pillow>=10.0` in pyproject. Frontend: `/sessions` nav item + route, `pages/Sessions.tsx` + `api/sessions.ts` â€” create dialog, project + status filters (per-status counts), expandable rows (checkpoints timeline, log slice with `[sentinel]` lines highlighted, screenshot grid + zoom modal), Capture / Add checkpoint / End (outcome + status) / Delete / Export-to-portfolio (copyable snippet dialog). Docs: 01 Â§9 data dirs + changelog, 02 Â§2.12 + Â§14.7 + changelog, 03 changelog, later.md Tiers 1 + 4 marked done (2-3 renumbered), .env.example, AGENTS.md env list. Tests: +16 backend (CRUD, marker-slice boundaries incl. interleaved sessions, checkpoint ordering, capture files + thumb, auto-capture on end, delete cleans files, export copy + snippet, traversal guard, full API flow), +12 frontend (list/badges, project + status filters, expand detail, create, checkpoint, capture, end, export snippet dialog, delete, zoom modal). Backend 449 / frontend 120 green; black/isort/flake8 + prettier clean. | AI agent |
| 2026-08-15 | 1.17.11.0 | **Scripted testers (later.md Tier 2, docs/tier2_plan.md).** Backend: `app/testers/` â€” per-app deterministic Python testers (Rule 3: substring/status/exit-code matchers only; Rule 2: manual "Run tester" button only). `_helpers.py` TesterContext (launch/http/cli/pytest/wait_log/wait/checkpoint/screenshot; bounded timeouts; raises TesterAssertionError â†’ session `failed`, TesterEnvError/TesterTimeoutError â†’ `investigate`; `cli` appends `[tester]` lines to the app log, never env values â€” tested); `__init__.py` Tester dataclass + registry (project slug â†’ tester, circular-safe submodule imports) + `DEFAULT_SMOKE` (launch â†’ wait â†’ scan for `Traceback|FATAL ERROR|Cannot find module` â†’ screenshot) for launchable apps without a custom tester; custom testers: Cg (mock-LLM backend + watches the renderer's broken `/api/pipeline/jobs/` call in the app log + Electron + 46-test pytest suite), Ag (static CLI asserts GLTF file; `animate` step is red â€” AG main.py:283 NameError, evidence in the session log; opencv-python-headless installed into `.venv_sf3d`), Demake Engine (upload trailer â†’ poll status â†’ manifest â†’ asset, structural asserts), Tv-Scheduler, Workflow-Toolkit, Card-Game, Dinner-Menu-Generator. Live-fix round (2026-08-15): AG main.py root_motion NameError fixed in the AG repo (added oot_motion param, wired from the CLI) — tester green; Demake non-cp1252 prints (→/✓/✗ in demake.py, orchestrator, sprite_gen, validator, vlm_analysis) replaced with ASCII — the upload/pipeline no longer crash under Sentinel's redirected stdout; Demake tester now uses the manifest's absolute asset URL and allows 7 min for the slow SD/ONNX sprite path. Ground-truth revocations (honest "No tester", descriptor 404): Mlbattles, Hft-Order-Book, Algo-Trader, Python-Projects. `services/tester_runner.py` (resolve/describe/run â€” auto-creates `Tester: <name>` session, auto screenshot + status), `tasks/tester_tasks.py` (job-pool task, activity_bus "tester" event), `job_scheduler` registry + `run_tester`, `schemas/tester.py`, API `GET /api/v1/testers/{project_id}` + `POST /api/v1/testers/run` (202 JobEnvelope), `build_runner._launch_app` gained an `env` overlay (tester launches; backward compatible). Frontend: Builds page "Run tester" button (descriptor-aware; disabled "No tester"; run â†’ session-result card with status tone + View session link; polls sessions for the post-click `Tester:` session), `api/testers.ts`. Docs: tier2_plan.md (Phase B ground-truth revision), later.md Tier 2 â†’ DONE, changelogs 01/02/03. Bugfix: log-slice read tolerates non-UTF-8 app-log bytes (cp1252 child output) — end() no longer crashes with UnicodeDecodeError leaving sessions 'running' (regression test added; live catch: Demake's upload print of U+2192 under redirected stdout). Tests: +21 backend (registry, resolve, context helpers incl. timeout + env redaction, runner statuses, API descriptor/404/JobEnvelope with inline runner), +6 frontend (button states, run flow, passed/failed result tones); 470 backend / 124 frontend green; black/isort/flake8 (max-line 100) clean. | AI agent |
| 2026-08-15 | 1.17.12.0 | **Error triage (later.md Tier 3, docs/tier3_plan.md) + WorkFlow-Toolkit flagship tester.** Tier 3 reframed from "AI-assisted" to deterministic-first: `POST /api/v1/sessions/{id}/triage` builds a zero-AI evidence packet - error lines quoted verbatim from the session's own log slice (ERROR/CRITICAL/Traceback/error:/failed-to hints, capped 40), traceback frames resolved against the project repo (`File "..." line N` parsing; frames outside the project dropped), a source preview of the culprit lines read straight from disk (3 before / 2 after), known error-pattern labels, and an honest note when no traceback exists ("source mapping unavailable - the console lines are the evidence"). New `TriageAnalysis` table (session FK, evidence JSON, summary, model, created_at - Rule 7 provenance; `create_all` adds the table; cascade-deleted with the session). Optional `POST /api/v1/sessions/{id}/summarize`: one small local-LLM call (llama3.1:8b, max_tokens 150, num_ctx 4096 override for speed, purpose "triage-summary" logged to ollama_query_log) describing the evidence only - no causes, no fixes, no decisions (Rules 2+3); 503 when Ollama is down and the deterministic card still renders. OllamaService generate/generate_with_metrics gained an optional num_ctx param. Frontend: Sessions page "Triage failure" button on failed/investigate sessions (running/passed excluded), evidence card (verbatim error lines, pattern chips, file:line frames with the culprit source line highlighted, note), "AI summary" button with provenance line (model + timestamp). Workflow-Toolkit tester upgraded from health smoke to the payroll-audit E2E: launches the backend through the repo's bundled runtime python (`backend/runtime/python/python.exe`, PATH python fallback), imports the engineered `payroll_issues.csv` fixture, asserts payroll validation catches its missing/negative hours, generates + downloads the PDF report (file_path + content-type checks), resolves the "Payroll Audit" workflow template by name, executes it and polls the run to Completed with an output_report_id (5 s polls, 180 s cap). Docs: tier3_plan.md, later.md Tier 3 -> DONE, changelogs 01/02/03. Tests: +21 backend triage (extraction, frame parsing, source previews, evidence notes, API 400/404/503, provenance + query log, cascade delete), +2 tester (WFT registry name, runtime-python launch command preference), +4 frontend (button visibility, evidence card render, AI summary provenance, Ollama-down toast); 490 backend / 128 frontend green; black/isort/flake8 clean. | AI agent |
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
| 2026-08-12 | 1.17.7.2 | **Junk-free file index; honest knowledge reset; no autostart task.** (1) **Ignore patterns** (`config.py`): `Library/` (Unity's regenerable PackageCache/Artifacts/BurstCache), `release/` + `win-unpacked/` (electron-builder output), `*.pdb`/`*.bhc` (build symbols/Burst caches) â€” the desktop index had swollen to 47,455 files (Khd4 Unity Library 25.6k, WorkFlow-Toolkit release+runtime 15k) vs ~4k of real source on the laptop; ignored rows prune themselves on the next scan (`_index_files` drops files no longer walked). (2) **Reset now sticks** (`job_scheduler.py`, `rag_tasks.py`): new `JobScheduler.cancel_queued(name_prefix)` cancels not-yet-started pool jobs; `run_reset_knowledge` cancels queued re-index jobs before clearing flags + dropping collections, so the embedded count goes to 0 and stays 0 â€” previously the boot auto-index re-queued ~20 projects and re-embedded seconds after the reset, making it look like a no-op. (3) **Autostart task removed**: `scripts/install_service.py` deleted, `run.py` drops `--service`/`--install`/`--uninstall` (and PYWIN), task uninstalled from the desktop â€” the 5-min Task-Scheduler rerun popped a console window every time it respawned the server (Last Result 1 bind races); the server is now started manually with `run.py`. Docs: AGENTS.md, README, desktop.md, 01 file tree, 02 Â§13.3/Â§13.4/troubleshooting, 03 Phase 13. Tests: âˆ’2 packaging (install_service), +ignore-pattern indexer, +cancel_queued, +reset cancels queued jobs | AI agent |
| 2026-08-12 | 1.17.7.1 | **Junk-file indexing gates + fast boot scans.** First full scan on the desktop froze the API ~25-40 min (rglob whole trees: demake-engine 35.3k files/11 GB incl. 3.3 GB ONNX; AG incl. `.venv_sf3d` â€” missed by the exact `.venv/` pattern; parsers `read_text`'d multi-GB binaries). Fixes: **(1) file gates** â€” `SENTINEL_MAX_FILE_KB` (default 5120) + `_BINARY_SUFFIXES` denylist via `_is_skippable` (full + incremental); **(2) walk prune** â€” DFS never descends into ignored dirs (`data/` added, `.venv/`â†’`.venv*/`), was rglob+filter (24k ignored entries under this repo); **(3) mtime fast-path** â€” `ProjectFile.mtime_ns` (ALTER migration) skips re-read when mtime+size unchanged. **run.py venv resolution**: resolves `backend\.venv` then root `.venv` then `.venv/bin/python3` (was root-only + Linux fallback â€” FileNotFoundError on this machine). **CLI**: `index --all` prints `Indexed k/N: <name>`. Tests: +3 backend, 93.66 % | AI agent |
| 2026-08-12 | 1.17.7 | **Single-desktop deployment; GitHub optional; scan beat decoupled.** The laptop is retired â€” the desktop is the dev workstation AND always-on server (laptop.md â†’ desktop.md; docs/01 Â§9/Â§10, 02 Â§13 rewritten; `http://127.0.0.1:8000`, localhost only). **Tokenless first-class**: tokenless sync no longer says "skipped" (startup logs one INFO line, no activity event) and the `repo-sync` beat registers only when `SENTINEL_GITHUB_TOKEN` is set. **Security scan-all owns its own beat** (`SENTINEL_SCAN_INTERVAL_MINUTES`, default 1440): previously it ran chained to the repo-sync pass â€” a tokenless install would never scan; `run_repo_sync` no longer calls `run_security_scan_all`. **Home-dir discovery pruning** (`indexer.py`): the full-home `rglob` walk is now a depth-aware walk that prunes `_DISCOVERY_SKIP_DIRS` noise (`AppData`, `OneDrive`, `node_modules`, `.venv`, tool caches) during traversal and never enters paths beyond depth 4; eligible set unchanged. **install_service venv fallback**: Task-Scheduler command resolves `backend\.venv` or repo-root `.venv` (was repo-root only â€” broken on this machine). Tests: +8 backend (beat registration tokenless/token Ã—2, scan decoupled, scan interval config Ã—2, discovery pruning Ã—3, install_service venv Ã—2); 93.95 % | AI agent |
| 2026-08-10 | 1.17.5 | Duplicates eliminated at the source (Rule 5: projects are known entities). **Discovery eligibility**: only *sync-owned* checkouts can become projects â€” a canonical `<root>/<owner>/<name>` clone whose origin URL matches `github.com/<owner>/<name>`, or a flat direct-child checkout with any GitHub origin (the repos v1.17.4 adopted live there) â€” so git worktrees (`CG.worktrees\agents-*`), stray copies (`Desktop\airadio`, `Documents\CG`, `Desktop\backups\algo-trader`), nested sub-repos (`AG\stable-fast-3d`, `Python Projects\main`), `.codex\*` and seed fixtures are disqualified; same-origin duplicates keep the canonical nested checkout. **Project-row GC**: nothing ever deleted a `project` row â€” deleted dirs (the laptop's `jamesdileva\*` clone folders) survived as zombie projects forever; the full startup scan now drops rows whose checkout is gone, disqualified, or outside the watch roots, cascading files/dependencies/findings/results/logs/summaries/chat/portfolio + stored Chroma docs (FK-safe `delete`). Repo-sync's targeted rescans never GC. Verified read-only against the real desktop home dir: 60 checkouts discovered â†’ 21 kept (18 flat-adopted + 2 new clones + 1 fork), zero churn. Tests: +7 indexer, 94.5 % | AI agent |
| 2026-08-11 | 1.17.6 | Damaged knowledge index made detectable and recoverable. ChromaManager: per-collection RLock (no interleaved upserts from concurrent knowledge jobs), cached health probe that touches every non-empty collection's HNSW segment reader (`count()` alone hides wiped segment dirs), `RagIndexError` â†’ **503 + rebuild hint** (was a raw 500 from `InternalError: Nothing found on disk` after a killed write), `delete_by_project()` sweeps the real collections (the GC had been deleting from a phantom `knowledge` collection, orphaning vectors forever), and `reset_all()` as deterministic recovery. API: `GET /rag/index/status` carries `health`; `POST /rag/index/reset` (202 job). CLI: `rag-index --reset`. Frontend: damaged-index banner + rebuild confirm on the Knowledge page. Scheduler: graceful shutdown â€” `cancel_futures=True` previously killed in-flight indexes mid-upsert, i.e. the exact corruption this release detects. RAG queries: all-project questions are summary-first and context names the source project. Tests: +10 backend, +2 frontend | AI agent |
| 2026-08-11 | 1.17.6.1 | Reset recovery completed: `run_reset_knowledge` now also clears `ProjectFile.embedding_id` after dropping the collections. `ingest_files` skips any file whose flag is set (the v1.17.1 incremental optimization), so a reset that kept the flags would re-embed **nothing** and leave the index empty forever; the task returns `files_unflagged` and the next index (startup auto-index or `rag-index`) rebuilds everything. Tests: +1 (flags cleared after reset, previous task test updated for the new return value) | AI agent |
| 2026-08-11 | 1.17.6.2 | Laptop recovery: RAG chat + semantic search work again after a damaged index. **Probe fixed** (`ChromaManager.health`): the v1.17.6 `get(limit=1)` probe could pass while the query path raised (`Nothing found on disk`) â€” chat 503'd with "damaged" hints while the dashboard stayed healthy, so the rebuild banner never showed; the probe now runs a real query with a stored embedding (the exact operation search uses). `reset()` tolerates `InternalError` on `delete_collection` (broken store, collection being discarded anyway). **Auto-index always includes the AI architecture summary**: `queue_knowledge_index_unembedded` submits `with_summary=True` (startup + sync passes); `ingest_project_summary` dedupes to once per project (existing `architecture` summary reused; CLI `--summary` forces regeneration). Dashboard "Include AI architecture summary" checkbox removed. New projects + post-reset re-indexes get summaries automatically â†’ all-project chat is summary-first as designed. Deferred: summary regeneration on repo change (needs file-change detection; sync already knows changed repos, cheap hook later). Tests: +5 backend, +1 frontend updated | AI agent |
| 2026-08-12 | 1.17.6.8 | **Full re-embed without the CLI**: the Knowledge page now always shows **"Rebuild knowledge index"** (was hidden inside the damaged-index banner) â€” drop all vectors + clear flags, then "Re-index all projects" re-embeds with the current chunking/summary prompt; the confirm dialog covers both the damaged-disk and the stale-embeddings case. **Ollama timeouts during a full re-index fixed** (laptop `sentinel(2).log`): the v1.17.6.6 doc-first summary prompt (~10k-token prefill) outgrew the 600 s read timeout when contending with the embed flood (3 of 17 post-reset jobs failed at `ingest_project_summary`; files had embedded fine); `ollama_timeout_seconds` default 600 â†’ 1800. **Summaries get more output budget**: new `ollama_summary_max_tokens` default 1250 (was the shared 500 cap) â€” the fed-more context produces a structured components/stack/notes summary past 500 tokens; chat answers keep the 500 default (`_generate_with_metrics` forwards `max_tokens`). `.env.example` documents both overrides. Tests: +1 backend (summary call carries the 1250 cap, chat stays 500), +1 frontend (rebuild action visible on a healthy index) | AI agent |
| 2026-08-12 | 1.17.6.7 | **"Re-index all projects" 500 fixed**: `/api/v1/rag/index/all` submits `run_index_knowledge_all` but `_build_registry()` never registered the task (1.17.6.4 gap) â€” `KeyError` on every click. Registry contract test asserted a pre-1.17.6.4 name set (exact equality), so it stayed green; set updated + new test that router-submitted names resolve through the real registry. CLI `rag-index --all` unaffected. **CLI `rag-index --reset` fixed**: it bypassed the task and only dropped the collections, leaving `embedding_id` flags set â€” startup auto-index found nothing to re-embed and the Knowledge page kept reporting files embedded against an empty index. It now runs the same `run_reset_knowledge()` task as the API button and prints `files_unflagged`. **Flaky gate fixed**: the lifespan startup scan daemon thread (`sentinel-scan`) outlived its TestClient and could persist a `SyncRun` into a later test's engine, intermittently failing `test_system_sync_endpoint`; autouse conftest fixture now pins `auto_scan_on_startup=False` (renamed `_quiet_background`). Tests: +1 backend, +1 backend updated | AI agent |

| 2026-08-12 | 1.17.6.6 | Security scans join the daily sync chain; markdown-aware retrieval. **Scan = once per 24 h**: `nightly-security-scan` beat removed (`_BEAT_IDS` = repo-sync + world-sim-tick) â€” the daily repo-sync runs the scan at the end of its pass (sync â†’ knowledge index â†’ security scan, whenever sync is configured). **Never-scanned â‰  clean**: scanner now stamps `Project.last_scanned` every scan; portfolio security = no findings + never scanned â†’ **pending** (0), no findings + scanned â†’ **clean** (25); cache invalidates on it. **Docs chunked, code kept whole**: Markdown/`docs/` files chunked at 2000 chars/200 overlap (cap 32/file, ids `{file}#{i}`), code stays single 4k chunks. **Smarter summaries**: docs-first context (README 400 > `.md` 300 > `docs/` 150 > entry 100; 25 files Ã— 1500 chars) + 25 recent commit messages as sprint timeline; `project_summary.j2` rewritten (Overview/Architecture/Build-Run-Test/Phases, trust docs over code). **All-project queries scale**: top_k = max(requested, min(projects, 24)); summaries first, distance-ranked merge, 48k-char budget. **`__all__` chat room**: chat history persists for all-project conversations. **Frontend**: query timeout 120 s â†’ 600 s, topK 5 â†’ 10. **Context**: `ollama_num_ctx=32768` (default 2048 truncates). Migration: knowledge reset + re-index-all. Tests: +9 backend, +2 frontend (75 vitest); full pytest green | AI agent |

| 2026-08-12 | 1.17.6.5 | **Default LLM switched to `llama3.1:8b`** (was `gemma2`). Head-to-head on the architecture-summary prompt (same template + 8-file/600-char context, app defaults 500 tok / temp 0.3): gemma2 186 tokens @ 6.3 tok/s (tight, honestly flagged thin context); llama3.1:8b 294 tokens @ 9.0 tok/s (better structure â€” components/stack/notes â€” picked up AGENTS.md rules). Won on structure + speed + instruction following. `settings.ollama_model` + `world_sim_model` defaults, CLI pull guidance, `.env.example`, AGENTS.md decision table, docs current-state refs â†’ `llama3.1:8b`. Note: world-sim narratives are deterministic templates â€” `world_sim_model`/`world_sim_ai_narratives` currently unused (planned AI-narrative wiring never shipped), kept consistent for future wiring. Existing summaries keep their `model` provenance; new generations use the new model â€” laptop migration: `rag-index <project> --summary` per project. No test changes | AI agent |
| 2026-08-12 | 1.17.6.4 | Run-log cleanup + re-index-all command. **Log noise**: `httpx`/`httpcore` set to WARNING (the 1.17.6.3 run log was ~500 `POST /api/embed` lines in ~1800 â€” that detail lives in the activity feed + Ollama query log). **Deterministic single-write run log**: file handler pinned on `uvicorn`/`uvicorn.error`/`uvicorn.access` *and* root with `propagate=False` forced on the uvicorn loggers â€” every line lands in `data/logs/sentinel.log` exactly once regardless of uvicorn's own log config. **Ollama timeout**: default `ollama_timeout_seconds` 120 â†’ 600 (a laptop saturated by 4 concurrent embedding workers timed out arch-summary generation at 2 min; 10 min covers the slow gemma2 case; `SENTINEL_OLLAMA_TIMEOUT_SECONDS` overrides). **Re-index all projects**: Knowledge-page button + `POST /api/v1/rag/index/all` + CLI `rag-index --all` â€” one deterministic job loops every project with `with_summary=True`; incremental (`ingest_files` skips embedded files), so it backfills missing AI architecture summaries without re-embedding (the 1.17.6.3 timed-out summary jobs are exactly this case) and picks up files from a recent `git pull`; one project's failure never aborts the pass. Tests: +8 backend (endpoint queues one job, CLI `--all` runs the task + usage lists it, re-index-all skips embedded files + regenerates a missing summary + survives one bad project, uvicorn loggers pinned propagate=False single-write, httpx silenced), frontend reindex-button test | AI agent |
| 2026-08-11 | 1.17.6.3 | Post-laptop-log runbook pass (trigger: a re-index that indexed files but produced no architecture summary, and a bind error from a second console left open). **Summary dedupe fixed**: the v1.17.6.2 dedupe checked the SQLite row, not the embedding â€” `reset()` drops the `project_summaries` collection but keeps the rows, so post-reset re-indexes skipped the summary forever; `ingest_project_summary` now skips only when the vector exists (`get(where={"$and": ...})`, damaged-store errors count as missing) and a regeneration reuses the newest row instead of duplicating it (`force`/CLI `--summary` unchanged). **Per-run log file** (`data/logs/sentinel.log`): truncated at startup, INFO level â€” the "what happened this run" answer; `attach_file_logging()` re-attaches the file handler at lifespan startup (uvicorn's log config replaces root handlers) and pins it on the `uvicorn`/`uvicorn.error`/`uvicorn.access` loggers so crash cascades land on disk, not just the scrolling console. **run.py port-owner message**: starting while another instance runs prints the owning PID (`netstat -ano`) + a `taskkill` hint instead of a raw bind traceback. Tests: +5 backend (summary regenerates after reset, once-per-project dedupe maintained, run-log INFO write, overwrite mode, attach idempotency) | AI agent |
| 2026-08-10 | 1.17.4 | Duplicate-repo fix + feed cleanup after the laptop's first real sync (v1.17.3 did clone all 18 repos). **Duplicated projects**: sync checks only `<watch-root>/<owner>/<repo>` for an existing checkout, but the repos live flat at the watch root (`Projects\Sentinel`, â€¦) â€” no match, fresh clone, every project indexed twice; `_local_path` now falls back to any checkout directly under the root whose origin remote URL matches `<owner>/<repo>` (`_find_existing_checkout`, normalized https/ssh/case/.git-suffix) and *pulls* it instead of cloning. **world_tick feed spam**: the 60 s world-sim beat published `running` + `finished` every tick (~2880 rows/day); beats can be registered `quiet=True` and the world-sim tick now publishes no activity events (log lines unchanged; sync/scan beats + on-demand jobs keep theirs). **Dashboard build shipped**: v1.17.3's Systemâ†’Dashboard merge never reached the laptop â€” the tracked `backend/app/static` held the pre-merge build; rebuilt assets are now committed (System = Settings placeholder, Dashboard = Home server section). Tests: +8 backend (adoption variants + quiet beat), 94.5 % | AI agent |
| 2026-08-09 | 1.17.2 | Living-week fixes. **No more re-embedding on restart**: `IndexerService._index_files` deleted + re-inserted every `project_file` row per scan, nulling `embedding_id` (Chroma doc ids are the row ids) â€” auto index re-embedded all 2.9k files after every restart; rows now keyed by path, unchanged files keep id + embedding_id, vanished files drop. **Shared Chroma client**: startup knowledge-job burst raced ChromaDB's shared-system registry (`'RustBindingsAPI' has no attribute 'bindings'`) â€” `get_chroma_manager()` locks one client per path. **Activity feed caching**: `useActivity` re-seeds on WS open + retries once after an empty first load â€” cached history shows when entering the dashboard; `activity_bus` persist failures now WARN (were debug â€” laptop history could vanish silently). **Embedding t/s**: `embed_with_metrics` (Ollama `prompt_eval_count/duration`) â†’ knowledge progress ticks carry `tokens_per_second`; generations/chat unchanged; external clients (airadio) invisible by design. Tests: +10 backend / 70 vitest | AI agent |
| 2026-08-09 | 1.17.1 | Regression-fix & ops pass after the first living week. **Scanner false positive fixed**: `\bexec\s*\(` matched `session.exec(` because a dot is a word boundary â€” 17 of the laptop's 20 findings were SQLModel ORM calls in clean repos; attribute calls are now ignored (only bare identifiers match). **Sync feedback**: an unconfigured sync now publishes *why* on the live feed ("Repo sync skipped â€” token not configured"), and nothing-changed passes carry a `detail`; new `POST /api/v1/system/sync` (`{"full": bool}`) + header "Sync now" button run a background pass (409 when already running, activity events per pass). **Migration bug fixed**: `migrate_columns` only added missing columns to the *first* affected table â€” `ollamaquerylog.purpose` was silently absent (would crash chat history past the 5000-row ceiling); migrated tables are verified via `PRAGMA table_info` and repaired per table. **Sync cadence**: `SENTINEL_SYNC_INTERVAL_MINUTES` default 15 â†’ 1440 (daily; startup still syncs once). **C++ builds deferred** to Sprint 18 (Rule 4 â€” parser scope is out of control). Tests: regression tests for all four, 84 backend / 68 vitest green | AI agent |
| 2026-08-09 | 1.17 | Sprint 17 (Observability & UX pass). **Live activity**: `ActivityBus` (`app/services/activity_bus.py`) persists all notable events (sync/index/knowledge/build/test/security/ollama/job) to a bounded `activity_event` table and broadcasts them on `/api/v1/ws/jobs` (activity frames + 30 s heartbeat); new read-only `GET /api/v1/system/activity`. Ollama generation events carry `purpose` (query/summary/rag-query) + eval metrics (tok/s). **Chat rooms**: `ChatMessage` table, `GET/POST /api/v1/rag/chat/{project_id}`; RagChat replays history and persists every exchange. **Auto knowledge-index**: `SENTINEL_AUTO_INDEX_KNOWLEDGE=true` default â€” post-scan queueing for unembedded projects through shared `queue_knowledge_index_unembedded()`. **Frontend**: global status bar (live dot, latest event, Ollama tok/s), sync pill always visible incl. "Sync not configured", Dashboard live log, Knowledge page live progress, Galaxy labels + legend, HealthCard reasons. **.env fix**: config now reads repo-root `.env` (was `BASE_DIR.parent`, home dir â€” token/overrides silently ignored since Sprint 0). **Gate fix**: `scripts/build.py` booleanized `ok`-chain + flake8 `--max-line-length=100` (failures previously never aborted). Tests: 271 backend / 94.49 %, 63 vitest, gate green | AI agent |
| 2026-08-08 | 1.16.2 | Dashboard actually served: `app/main.py` pointed at `frontend/dist` while the build is staged at `backend/app/static` â€” Node-less laptop got 404s on all non-API paths. Now serves the staged build (dev fallback) and `/` returns the dashboard HTML instead of Sprint-1 health JSON. SPA-fallback + root tests added; 257 backend green. Docs: explicit venv-path commands throughout (no activation needed). Watch dirs: default changed from hardcoded `C:\Users\j` to the current user's home â€” laptop `C:\Users\james` passes the startup check with zero config (old `SENTINEL_PROJECTS_DIR` in the laptop `.env` is dead; remove it) | AI agent |
| 2026-08-07 | 1.14 | Sprint 12.2 (Bugs + UI pages). **World sim expansion bug fixed**: farmers were fixed at bootstrap (~20) so production parked ~130/day and no settlement ever reached `EXPAND_POPULATION=600` â†’ zero roads forever, even at 10K days. New step 2.5 **recruitment** (`event_generator.py`): food-secure settlements scale roles with population â€” farmers `pop//6` (capped by new per-terrain `FARM_CAPACITY` plains 200/forest 150/hills 150/mountains 80/water 0), builders `pop//12`, merchants `pop//30`, explorers `pop//60`; starving settlements recruit nobody. Growth bounded: food stores cap at `pop Ã— MAX_FOOD_DAYS` (20; with the +6%/road trade bonus, runaway int growth never happens), expansion stops at `MAX_ACTIVE_SETTLEMENTS = 60`, skill bonuses clamp at level 10 (+45% prod / +90% rebuild), raids restricted to road-connected pairs (O(roads)). Verified: seed 42 â†’ ~60 settlements / 58 roads by day 1000, stable at day 10000 (~48s). Regression: `test_roads_appear_from_natural_growth`. **Encoding**: non-UTF-8 files no longer abort indexing (`errors="replace"` in indexer/framework_detector/command_extractor; MLBattles `requirements.txt` case fixed); `test_index_project_survives_non_utf8_requirements`. **Knowledge auto-index**: after each repo sync, projects with `embedding_id IS NULL` files get a `run_index_knowledge` task per project (Ollama-gated; skipped `ollama-unavailable`, never fails sync); unreadable files marked embedded; CLI prints queued count; 2 new tests. **Frontend**: `/projects`, `/builds`, `/security` are now real pages (file list, run-trigger + history + logs, findings w/ severity) replacing Placeholder; `api/tests.ts`. Tests: 256 backend (95.08% cov) / 48 vitest. Docs: 02 Â§11.3â€“11.5 (constants + steps) + Â§13.4 (knowledge note), changelogs v1.14 | User + AI agent |
| 2026-08-08 | 1.16 | Sprint 15.1 (Native deployment, decommission Docker). Compose/Docker layer removed entirely: docker-compose*.yml, docker/, scripts/dev.py deleted; 
un.py (repo root) is the single starting point â€” startup checks (Python, .env/data dirs, frontend built, SQLite writable, Ollama) then uvicorn on 127.0.0.1:8000, flags --check/--port/--reload/--service/--install/--uninstall; scripts/install_service.py registers the Sentinel Task-Scheduler task (pythonw 
un.py --service every 5 min, idempotent, no admin); scripts/build.py reworked (verify: pytest+lint, npm test+build; --dist stages frontend into ackend/app/static which pp/main.py serves same-origin â€” no nginx/CORS); scripts/release.py archive now ships run.py + scripts + docs + ackend/app; SENTINEL_PORT replaces SENTINEL_API_PORT; env table Â§4.2, Â§13 rewritten native (troubleshooting table), laptop.md rewritten. **Pi-hole leaves the Sentinel stack** (independent LAN DNS; docs/pi-hole-idea.md): System-page panel + SENTINEL_PIHOLE_* removed, OllamaStatus untouched. Frontend: /system panel + tests updated. Tests: packaging suite reworked for native artifacts (release contents/exclusions, run.py probes), 261 backend green. Docs: 01 Â§9.2/Â§10/tech table/repo tree, 03 Phase 13, changelogs v1.16 | User + AI agent |
| 2026-08-07 | 1.13 | Sprint 12.1 (Repo auto-sync + Pi-hole v6 auth fix + SMB revert). Laptop project sync moved from an SMB share (`\\192.168.4.28\projects`) to **GitHub auto-sync**: new `RepoSyncService` (`services/sync_service.py`) lists the user's repos via the GitHub API (read-only PAT, `SENTINEL_GITHUB_TOKEN`), `git clone`s missing repos / `git pull --ff-only` existing checkouts under `SENTINEL_PROJECTS_DIR` (local clone target, mounted at `/data/projects`), then re-runs the indexer â€” source of truth is GitHub, so new repos appear automatically with zero upkeep; new `sentinel sync` CLI command + Celery beat task `repo-sync` on `SENTINEL_SYNC_INTERVAL_MINUTES` (default 15). **Pi-hole System-page bug fixed**: v6 dropped the `X-FTL-API-KEY` header â†’ `PiHoleStatus` now logs in via `POST /api/auth` with `SENTINEL_PIHOLE_PASSWORD` and sends `X-FTL-SID` (read-only, Rule 2). Desktop SMB plumbing reverted (share/junctions/firewall rules). Config: `SENTINEL_GITHUB_TOKEN`, `SENTINEL_SYNC_INTERVAL_MINUTES`, `SENTINEL_PIHOLE_PASSWORD` (API token var removed). Tests: 251 backend (95.2% cov â€” new `test_sync_service.py` via MockTransport + run_command stubs, updated Pi-hole auth tests, CLI sync tests). Docs: 02 Â§13.4 (GitHub sync runbook, env table, troubleshooting), laptop.md, AGENTS.md, changelogs v1.13 | User + AI agent |
| 2026-08-06 | 1.12 | Sprint 12 (Home Server + System page) shipped. Compose: `frontend` nginx service (multi-stage node build, `8080:80`, `/api` + WS proxy to backend), dev overrides moved to explicit `docker-compose.dev.yml` so bare `docker compose up` is prod; `SENTINEL_API_PORT`/`SENTINEL_PROJECTS_DIR`/`SENTINEL_OLLAMA_HOST` env-overridable via `.env`. Startup validation in `main.py` (`services/startup_check.py`: database/chroma/watch dirs/ollama, logged structured status). Packaging: `scripts/build.py` (backend+frontend images, test-first) + `scripts/release.py` (`dist/sentinel-0.1.0.zip` + sha256 manifest, changelog bump, `--tag`/`--dry-run`). CLI finalized (spec Â§12.6): `portfolio` now wired to `PortfolioService` scores, new `docs <id>` (deterministic doc-file list), `world-sim start`. Backend: `OllamaQueryLog` table + `generate_with_metrics` (eval_count/eval_duration â†’ tokens/sec), `OllamaStatus`/`PiHoleStatus`/`system_overview` services, router `api/v1/system.py` (`/overview`/`/ollama`/`/pihole` read-only, Pi-hole v6 read-only client). Frontend: `/system` page + nav item, `api/system.ts`, `ErrorBoundary` wrapping routes. Tests: `test_compose.py` updated for prod/dev split + frontend service, `test_system_service.py` (8), `test_startup_check.py` (5), `test_packaging.py` (5), System page vitest (4), ErrorBoundary vitest (3), e2e `system.spec.ts` (2). Total: 238 backend (95.4% cov), 36 vitest, 9 e2e. Docs: 02 Â§13.4 home-server runbook (SMB projects share, no-copy), AGENTS.md Deployment section, changelogs v1.12. Tauri explicitly deferred ("if attempted" â€” Rust not installed; web dashboard is shipped UX). | User + AI agent |
| 2026-08-06 | 1.11 | Sprint 11 (Testing & QA) complete. Backend tests expanded to 211 passing (95.6% coverage, gate â‰¥ 80%): new `test_cli.py` (index/ask/rag-index/world-sim commands, error exits), `test_tasks.py` (task registry + job envelope wiring), `test_exceptions.py` (custom exceptions â†’ `ApiError` mapping), `test_indexer.py` (repo discovery, indexing, language/framework detection), `test_health.py` (health + DB reachability), `test_compose.py` (compose config validity), `test_rag_service.py`/`test_rag_api.py`/`test_ollama_service.py`/`test_git_history.py` consolidated from earlier RAG sprints, `test_quality.py` (format/lint/coverage gates), plus parser/repository integration coverage; `test_e2e.py` full-pipeline indexâ†’scanâ†’buildâ†’testâ†’docgenâ†’export. Frontend â€” Vitest suite (29 tests, 9 files): `vitest.config.ts` (jsdom, globals, `src/test/setup.ts` with jest-dom), unit tests for `Dashboard`, `HealthCard`, `FeatureMatrix`, `ProjectTimeline`, `ArchitectureMap`, `ProjectGalaxy`, `ChatMessage`, `RagChat`, `Layout` (API modules mocked via `vi.mock`), scripts `test`/`test:watch`/`test:coverage`, api client timeout 10sâ†’30s (portfolio recompute can exceed 10s on larger local DBs). E2E â€” Playwright (`@playwright/test`, chromium): `playwright.config.ts` spawns backend (venv uvicorn, `SENTINEL_AUTO_SCAN_ON_STARTUP=false` for determinism) + Vite dev (`--host 127.0.0.1`) via webServer; `tests/e2e/{health,portfolio,observatory}.spec.ts`, 7 specs green against real `data/sqlite/sentinel.db`. `tsc` clean, `vite build` clean. Docs: 02 Â§12.1/Â§12.2/Â§12.4 rewritten, all changelogs v1.11; 03 Sprint 11 marked shipped | User + AI agent |
| 2026-08-05 | 1.10.1 | Sprint 10.5 (Observatory) complete. Backend â€” `ObservatoryService` (`services/observatory_service.py`): galaxy (project nodes + shared-tech nodes = `framework` + `Dependency.name` used by 2+ projects, `used by N projects` detail, tech-sorted links), timeline (project-created + `GitCommit.timestamp` commits + `BuildLog.started_at` builds + `TestResult.run_at` tests + `SecurityFinding.detected_at` findings inside `?days=` window; naive-UTC cutoff to match SQLite storage; descending; cap 500; messages clipped 120 chars), architecture (recursive tree from indexed `ProjectFile.path`, dirs-first, leaf counts = 1, root = total files). Router `api/v1/observatory.py` registered in `main.py`; schemas `observatory.py` (`GalaxyGraph`/`GalaxyNode`/`GalaxyLink`, `Timeline`/`TimelineEvent`, recursive `ArchitectureNode`, exported from `schemas/__init__.py`). Frontend â€” `/observatory` route + nav item "Observatory": `pages/Observatory.tsx` (3 sections), `components/ProjectGalaxy.tsx` (plain-SVG node-link graph, amber-shared list), `ProjectTimeline.tsx` (per-kind colored dots, 7/30/90/365-day selector), `ArchitectureMap.tsx` (project dropdown + indented tree), `api/observatory.ts`, types. Tests: 11 new (`tests/test_observatory.py`; galaxy filters to shared, timeline window/order/cap/exclusion + `_clip`, tree nesting/counts, API galaxy/timeline/architecture/404 via dependency override). Full suite green (152), flake8/black/isort clean on new files, `npm run build` clean. Docs: 02 Â§2.11 + Â§14.6 new, Â§2.6 stale `/projects/{id}/timeline` removed ("never built" â†’ points at Â§2.11), Â§12.1 test row, TOC Â§14.6 entry, changelog v1.10.1; 01 FG11 extension; 03 changelog. Live smoke vs real `data/sqlite/sentinel.db` (galaxy/timeline/architecture return data, 404 on unknown id). Deferred to v2: cross-file "used by" edges + AI summaries in the observatory | User + AI agent |
| 2026-08-05 | 1.10 | Sprint 10 (Portfolio Intelligence) complete: deterministic health scoring shipped (Portfolio only; observatory â†’ Sprint 10.5). Backend â€” `PortfolioService` (`services/portfolio_service.py`): 0-100 score = build 30 (latest `BuildLog` successâ†’30/failedâ†’10/noneâ†’0) + tests 30 (latest `TestResult`: greenâ†’30, else pass ratio, noneâ†’0) + security 25 (all resolvedâ†’25, unresolved deduct by severity critical 10/high 6/medium 3/low 1/info 0 floor 0, no findingsâ†’0) + docs 15 (README/Markdown/`docs/` files Ã· total indexed Ã— 15); recompute-on-read upserted to `PortfolioScore` (schema already existed from Sprint 2); `get_best_candidates(min_score=70)` returns ranked list + missing items; `feature_matrix()` returns âœ“/âš /âœ— grid over `build/test/docs/security/screenshots` (screenshots always âœ—). Router `api/v1/portfolio.py` registered in `main.py` (no flag). Frontend â€” `/portfolio` page (`pages/Portfolio.tsx`: health card grid, best candidates, feature matrix; names joined from `GET /projects/`), `components/HealthCard.tsx`, `components/FeatureMatrix.tsx`, `api/portfolio.ts` rewritten to backend schemas (route + nav item already existed from earlier sprints). Tests: 12 new (`tests/test_portfolio.py`; in-memory SQLite + StaticPool, dependency-override API tests, seeded alpha/beta/gamma fixture scoring 92.5/45/0). Full suite green (131), black/isort/flake8 (my files @ max-line-length 100) clean, `npm run build` clean, live smoke vs real DB returned scores for the 4 sample projects. Docs: 02 Â§2.7 rewritten + new Â§14.5 + Â§12.1 row + TOC, 01 FG11 rewritten, all changelogs v1.10. Deferred to Sprint 10.5: `GET /observatory/galaxy\|timeline\|architecture` + `ProjectGalaxy`/`ProjectTimeline`/`ArchitectureMap` | User + AI agent |
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1) complete: deterministic ant-farm shipped. Backend â€” `services/world_sim/{rules_engine,event_generator,skill_system,names,world_simulator}.py` (pure terrain + seeded per-day RNG; 9 daily steps; survival XP â†’ tiers 0/50/150/300/500 â†’ levels 1â€“5, +5% production/+10% rebuild per level); isolated DB `data/world_sim/world.db` (own metadata; tables `world_sim_state`, `world_settlements`, `world_roads`, `world_events`); `WorldSimulatorService` (advance in one transaction, bounded catch-up, god tools); router `/api/v1/world-sim/{state,history,settlements/{id},tick,reset,accelerate,disaster}`; Celery beat `world-sim-tick` (no new container); CLI `world-sim` wired; config `world_sim_*`. Frontend â€” `/world` route + nav, `api/world_sim.ts`, `WorldSimulatorPage` (3s tick, god controls, settlement inspector, event feed), `WorldGridMap` (2D canvas; BigInt hash copy so map == backend). Tests: 26 new (`test_world_sim.py`), full suite 119 green; flake8/black clean; `npm run build` clean. Docs: 02 Â§11 rewritten + Â§2.9/Â§5.1 updated, 01 Â§8.17/FG13 updated, all changelogs v1.9. Deferred to v2: diplomacy/tech/governments, per-agent AI, pause, spawn-resources, ML swap | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): docker-compose.yml implemented â€” new `pihole` service (official `ghcr.io/pi-hole/pihole:latest` â€” Pi-hole moved off Docker Hub; `docker.io/pi-hole/pihole` returns repository-not-found, so images come from GitHub Container Registry â€” `profiles: ["pihole"]`, 53 tcp+udp + admin 8053, volumes under `data/pihole/`, `FTLCONF_LOCAL_IPV4=192.168.4.40`, `FTLCONF_webpassword=${PIHOLE_WEBPASSWORD}` from gitignored `.env`, `TZ=${PIHOLE_TZ:-UTC}`); `backend`/`worker` `SENTINEL_OLLAMA_HOST` â†’ `http://192.168.4.40:11434` (laptop shared AI); `ollama` profile kept as desktop-local fallback. Architecture doc Â§9â†’Â§9/Â§9.1/Â§9.2 (Hardware Role & Infrastructure Services, two-machine topology) + Â§10 real IPs; impl guide Â§13.1 spec aligned + new Â§13.3 laptop deployment (OLLAMA_HOST 0.0.0.0, firewall, model pulls, compose pihole, router DHCP reservation + LAN DNS, multi-host env table incl. airadio `OLLAMA_URL`). `docker compose config` validated with dummy password; no runtime changes yet â€” laptop steps + desktop recreate are Phase 2/3 | User + AI agent |
| 2026-08-04 | 1.7 | Sprint 8 Part 2 (chat UI + live E2E): `frontend/src/api/rag.ts` (typed client for search/query/index/summaries; 120s timeout on query for local LLM), `components/ChatMessage.tsx` (user/assistant bubbles with source citations + distance + model/generated_at/confidence provenance, error state), `components/RagChat.tsx` (chat state, loading indicator, auto-scroll), `pages/KnowledgeExplorer.tsx` (project selector, Index knowledge button with optional AI architecture summary, semantic search + results, chat panel), route wiring `/knowledge` in `routes/index.tsx`. `tsc` + `vite build` clean. Live E2E vs real Ollama (native host, `nomic-embed-text` + `gemma2:2b` pulled; compose backend/worker rebuilt with chromadb and pointed at `host.docker.internal:11434` via temp override): RAG index ingested 6 file summaries + 2 test + 2 build logs into ChromaDB, semantic search returned ranked chunks, grounded query answered with 5 cited sources + provenance, `with_summary` persisted an architecture `KnowledgeSummary`, CLI `ask` printed sources + provenance, unreachable-Ollama exits 1 with pull instructions, Vite dev proxy served `/api/v1/projects/` live. Notes: docker image has no `git` binary so commit indexing degrades gracefully; full `gemma2` (vs `gemma2:2b`) needs `ollama pull gemma2` | User + AI agent | `frontend/src/api/rag.ts` (typed client for search/query/index/summaries; 120s timeout on query for local LLM), `components/ChatMessage.tsx` (user/assistant bubbles with source citations + distance + model/generated_at/confidence provenance, error state), `components/RagChat.tsx` (chat state, loading indicator, auto-scroll), `pages/KnowledgeExplorer.tsx` (project selector, Index knowledge button with optional AI architecture summary, semantic search + results, chat panel), route wiring `/knowledge` in `routes/index.tsx`. `tsc` + `vite build` clean. Live E2E vs real Ollama (native host, `nomic-embed-text` + `gemma2:2b` pulled; compose backend/worker rebuilt with chromadb and pointed at `host.docker.internal:11434` via temp override): RAG index ingested 6 file summaries + 2 test + 2 build logs into ChromaDB, semantic search returned ranked chunks, grounded query answered with 5 cited sources + provenance, `with_summary` persisted an architecture `KnowledgeSummary`, CLI `ask` printed sources + provenance, unreachable-Ollama exits 1 with pull instructions, Vite dev proxy served `/api/v1/projects/` live. Notes: docker image has no `git` binary so commit indexing degrades gracefully; full `gemma2` (vs `gemma2:2b`) needs `ollama pull gemma2` | User + AI agent |
| 2026-08-04 | 1.6 | Sprint 8 Part 1 (RAG backend core): `OllamaService` (generate/embed with `/api/embed` + legacy fallback, is_available/list_models, injectable transport), `ChromaManager` (embedded PersistentClient, 6 named collections, hnsw cosine, upsert/search/delete_by_project/count), `RagService` (index_project with raw-content ingestion + optional Ollama architecture summary persisted to `KnowledgeSummary`, semantic search with where-filter scoping, grounded `query()` returning sources + model/generated_at/confidence provenance; injectable embedder/llm), `GitHistoryService` + pure `parse_log` (`%H|%an|%aI|%s`, Windows-safe quoting, dedupe by hash), new repos (git, knowledge_summary), schemas `rag.py`/`knowledge.py`, routers `POST /api/v1/rag/search`, `POST /rag/query`, `POST /rag/index` (202 JobEnvelope on Celery `run_index_knowledge` task), `GET /projects/{id}/summaries`, CLI `ask` + `rag-index`. 91 tests passing (27 new; piped git-format quoting fixed for Windows). Chat UI + live E2E is Sprint 8 Part 2 | User + AI agent |
| 2026-08-04 | 1.5 | Sprint 7 complete: BuildRunner/TestRunner/SecurityScanner services (deterministic command discovery, pytest/jest output parsing, local advisory table, secret/static regex scanners), Celery app + `build_tasks.py` (worker + beat in compose, nightly scan schedule), repositories (build/test/security), routers `/api/v1/builds` (run/status/history, job_id == task_id), `/api/v1/tests` (run/results), `/api/v1/security` (scan/findings), CLI `build`/`test`/`scan` wired. 64 tests passing (14 new). Live-verified with docker worker: build succeeded (no-command), react build failed (exit 127, npm missing), pytest run 2 passed, security scan found vulnerability/secret/static_analysis. WS job-event broadcast over Redis pub/sub deferred to a later sprint â€” `/ws/jobs` stays heartbeat-only; build status is polled via REST | User + AI agent |
| 2026-08-04 | 1.4 | Sprint 6 complete: `/api/v1/projects` router (list/get/files), `/api/v1/ws/jobs` WebSocket (welcome + 30s heartbeat, real events land in Sprint 7), axios client + typed API modules, UI/Project/Build contexts, useProjects + useWebSocket hooks, Dashboard shows live data. Live-verified: proxied API through Vite, WS frames received, 404 passthrough | User + AI agent |
| 2026-08-04 | 1.3 | Sprint 5 complete: Vite 7 + React 19 + TS dashboard scaffolded (Layout with sidebar/header/dark toggle, Dashboard + placeholder routes, shared types mirroring SQLModel), `tsc` clean, dev server verified on 5173, `npm run build` succeeds | User + AI agent |
| 2026-08-04 | 1.2 | Sprint 4 complete: Dockerfile, compose stack, dev script, compose validation tests; verified live â€” `docker compose up -d` builds backend image, boots backend + redis, health returns 200, SQLite DB lands on `./data/sqlite/sentinel.db` (mounted volume), redis PONG, `scripts/dev.py --down` stops the stack | User + AI agent |
| 2026-08-04 | 1.1 | Sprint 0 alignment: Sprint 2 targets SQLite (was PostgreSQL), Pydantic schemas live in `schemas/` (was `models/`), `core/logging.py` (was `logger.py`), `POST /builds/status/{job_id}` â†’ GET | User + AI agent |
