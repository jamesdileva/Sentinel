# Project Sentinel — Sprint Plan

> **Version:** 1.1  
> **Status:** Draft — Phase 0 (Pre-MVP)  
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

### Sprint 1 — Project Scaffolding

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
  - `GET /` — Health check (returns `{"status": "ok"}`)
  - `GET /health` — System health endpoint
  - `GET /docs` — Swagger UI
- Configure CORS middleware for localhost:3000
- Basic exception handler
- CLI framework using Click or Typer

**Frontend Changes:** None.

**API Endpoints:**
- `GET /` — Health check (returns `{"status": "ok"}`)
- `GET /health` — Enhanced system health

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
3. Open `http://127.0.0.1:8000/` → see `{"status": "ok"}`
4. Open `http://127.0.0.1:8000/health` → see health details
5. Open `http://127.0.0.1:8000/docs` → see FastAPI Swagger UI
6. Run `sentinel --help` → see CLI commands listed

**Definition of Done:** Server starts without errors, health check endpoints respond, Swagger UI accessible, CLI framework initialized.

**Estimated Time:** 60 minutes

**Dependencies:** None.

---

## Phase 1: Core Services (Sprints 2-3)

### Sprint 2 — Database Schema & Models

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
3. Run `.tables` → see all tables listed
4. Verify foreign key constraints with `.schema projects`

**Definition of Done:** All tables, indexes, and relationships created successfully via `init_db()`.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 1.

---

### Sprint 3 — Repository Indexer Engine

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
  - `scan_repository(project_id)` → orchestrates full index
  - `detect_language(path)` → returns primary language
  - `detect_framework(path)` → returns framework (FastAPI, Flask, React, etc.)
  - `extract_dependencies(path)` → parses package files
  - `extract_build_commands(path)` → finds build/test/start scripts
  - `parse_files(path, extensions)` → uses correct parser per language
  - `update_incremental(project_id, changed_files)` → partial re-index
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
4. Run `detect_framework()` → verify returns "FastAPI"
5. Run `extract_dependencies()` → verify parsed correctly

**Definition of Done:** All parsers work with test fixtures, indexer service correctly populates database, all tests pass.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2.

---

## Phase 2: Docker Orchestration (Sprint 4)

### Sprint 4 — Docker Compose & Service Orchestration

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
3. Access `http://localhost:8000/health` → verify responds
4. Check logs: `docker compose logs backend`
5. Verify SQLite database file is created on the mounted volume
6. Stop: `docker compose down`

**Definition of Done:** Full stack boots without errors, all services healthy, dev script works.

**Estimated Time:** 60 minutes

**Dependencies:** Sprint 1, Sprint 2.

---

## Phase 3: Dashboard Frontend (Sprints 5-6)

### Sprint 5 — Frontend Scaffolding & Layout

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
3. Open `http://localhost:5173` → verify Dashboard loads
4. Toggle dark/light mode → verify theme changes
5. Resize browser → verify responsive layout
6. TypeScript compilation check: `npx tsc --noEmit`

**Definition of Done:** Frontend project runs, Dashboard renders, TypeScript compiles, theme toggle works.

**Estimated Time:** 60 minutes

**Dependencies:** Sprint 1 (for shared type definitions).

---

### Sprint 6 — API Client & React Contexts

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
3. Open browser dev tools → Network tab
4. Navigate to Dashboard → verify API calls are made
5. Stop backend → verify frontend handles connection errors gracefully
6. Check WebSocket connection status in browser console

**Definition of Done:** API client works, contexts provide state, hooks fetch data, types match backend.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 5, Sprint 2.

---

## Phase 4: Automation Engine (Sprint 7)

### Sprint 7 — Build/Test/Security Runners

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
  - `discover_commands(project)` → detect build/test/start scripts
  - `execute_build(project, command)` → run build in Docker subprocess
  - Capture stdout/stderr/exit code
- `TestRunner`:
  - `discover_tests(project)` → detect test frameworks
  - `run_tests(project)` → execute and parse results
  - Parse pytest/jest/mocha output into structured results
- `SecurityScanner`:
  - `scan_project(project)` → orchestrate all scans
  - `scan_dependencies(project)` → pip-audit, npm audit
  - `scan_secrets(project_path)` → TruffleHog, Gitleaks
  - `scan_static(project_path)` → Bandit, Semgrep
- Celery tasks for each step
- API endpoints for manual triggers

**Frontend Changes:** None.

**API Endpoints:**
- `POST /api/v1/builds/run` — Trigger manual build
- `GET /api/v1/builds/status/{job_id}` — Check build status
- `POST /api/v1/tests/run` — Trigger test run
- `POST /api/v1/security/scan` — Trigger security scan
- `GET /api/v1/builds/history?project_id={id}` — Build history
- `GET /api/v1/tests/results?project_id={id}` — Test results
- `GET /api/v1/security/findings?project_id={id}` — Security findings

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
3. Trigger a build via API → verify job starts
4. Poll status endpoint → verify completion
5. Check database for BuildLog entry with correct exit code
6. Run security scan → verify findings stored

**Definition of Done:** All runners work end-to-end, API endpoints functional, Celery configured.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer for command discovery), Sprint 4 (Docker).

---

## Phase 5: RAG Integration (Sprint 8)

### Sprint 8 — RAG System & Chat Interface

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
  - `generate(prompt, model)` → text completion
  - `embed(text)` → vector embedding
  - `is_available()` → connectivity check
- `RagService`:
  - `index_project_knowledge(project)` → embed summaries into ChromaDB
  - `index_git_commits(project)` → embed commit messages
  - `index_test_logs(project)` → embed test output
  - `index_security_reports(project)` → embed findings
  - `search(query, project_id?, top_k)` → semantic search
  - `query(question, project_id?)` → RAG Q&A flow
- Prompt templates for different query types
- API endpoint: `POST /api/v1/rag/query` — ask a question
- API endpoint: `POST /api/v1/rag/search` — semantic search only

**Frontend Changes:**
- `KnowledgeExplorer` page: search bar, chat interface, results display
- `RagChat` component: chat-style interface with message history
- `ChatMessage`: styled message bubbles with source citations
- API client for RAG endpoints
- Source attribution display (links to files/commits/findings)

**API Endpoints:**
- `POST /api/v1/rag/query` — RAG question answering
- `POST /api/v1/rag/search` — Semantic search

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
6. Test chat interface in browser → verify message flow
7. Verify source links work

**Definition of Done:** RAG system indexes knowledge, answers questions with sources, chat UI functional.

**Estimated Time:** 180 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer for summaries), Sprint 5 (frontend foundations).

---

## Phase 6: World Simulator (Sprint 9)

### Sprint 9 — World Simulator v1 (deterministic ant-farm)

**Objective:** Ship World Simulator v1 as a deterministic, persistent "living
toy": settlements grow, build roads, expand, trade, and sometimes collapse.
**No generative AI in the simulation loop** (Rule 2/3) — AI is optional flavor
on event text only. Runs inside the existing stack via Celery beat; no new
container.

**Files Created:**
- `backend/app/services/world_sim/__init__.py`
- `backend/app/services/world_sim/rules_engine.py` (pure rules: terrain, food,
  growth, construction, expansion, raids, disasters; constants with tests)
- `backend/app/services/world_sim/event_generator.py` (`simulate_day`, 9 steps)
- `backend/app/services/world_sim/skill_system.py` (survival XP → levels 1–5)
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
- `POST /tick {days}` · `POST /reset {seed?}` · `POST /accelerate {time_scale}`
- `POST /disaster {settlement_id, disaster_type}` (flood/drought/plague)

**Acceptance Criteria:**
- Deterministic: same seed + tick history ⇒ identical world (tested)
- Terrain and settlement names reproducible from the seed alone
- Food/growth, construction/level ups, expansion-with-roads on thresholds
- Famine and forced disasters can abandon settlements (incl. god tool)
- Survival experience maps to skill tiers; "build back stronger" bonuses
- Bounded catch-up after downtime (CE max `world_sim_max_catchup_days`)
- Runs in-stack via Celery beat (no container); manual tick via API/CLI
- Frontend `/world` page: canvas map, day stats, event feed, god controls

**Definition of Done:** Full backend suite plus `test_world_sim.py` green
(`pytest`), flake8/black clean, frontend `npm run build` clean; live beat tick
and god tools verified via CLI smoke; docs §2/§11 updated.

**Deferred (v2+):** diplomacy/technology/governments, per-agent AI, pausing,
`spawn-resources`, swapping the tier table for a real ML model behind the same
helpers.

---

## Phase 7: Portfolio Intelligence (Sprint 10)

### Sprint 10 — Portfolio Intelligence & Visualizations

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
  - `compute_health_score(project)` → 0-100 score from build/test/security/docs
  - `compute_portfolio_score(project)` → full PortfolioScore object
  - `get_best_candidates(min_score)` → ranked list for job hunting
  - `generate_feature_matrix()` → grid of projects × features
- `ObservatoryService` (for Architecture Maps):
  - `get_project_structure(project_id)` → nested component tree
  - `get_component_details(component_name)` → purpose, used by, added when

**Frontend Changes:**
- `Portfolio` page: container for all visualizations
- `ProjectGalaxy`: interactive node-link diagram of tech relationships
- `ProjectTimeline`: chronological history of all projects
- `HealthCard`: per-project health score with component indicators
- `FeatureMatrix`: grid view of all projects × features
- `ArchitectureMap`: expandable tree of project components

**API Endpoints:**
- `GET /api/v1/portfolio/scores` — All project scores
- `GET /api/v1/portfolio/best-candidates` — Ranked projects
- `GET /api/v1/portfolio/feature-matrix` — Feature matrix grid
- `GET /api/v1/observatory/galaxy` — Project galaxy graph data
- `GET /api/v1/observatory/timeline?days=365` — Portfolio timeline
- `GET /api/v1/observatory/architecture/{project_id}` — Architecture tree

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
3. Access `/api/v1/portfolio/scores` → verify scores returned
4. Access `/api/v1/portfolio/feature-matrix` → verify grid structure
5. Open Portfolio page → verify all visualizations render
6. Click a HealthCard → verify it navigates to project details
7. Hover galaxy nodes → verify tooltips show shared tech
8. Verify feature matrix shows ✓/⚠/✗ correctly

**Definition of Done:** All portfolio intelligence services work, visualizations render with real data.

**Estimated Time:** 240 minutes

**Dependencies:** Sprint 3 (indexer), Sprint 7 (build/test/security results), Sprint 5 (frontend).

---

## Phase 8: Testing & Quality (Sprint 11)

### Sprint 11 — Testing & QA

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
- E2E test covers: index project → scan → build → test → docgen → RAG query → portfolio score
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

### Sprint 12 — E2E Integration & MVP Release Preparation

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
- Full E2E flow works: start services → index project → run pipeline → query RAG → view portfolio
- CLI commands work from host machine
- `scripts/build.py` creates Docker images
- `scripts/release.py` generates release package
- Tauri desktop app builds successfully (if attempted)
- Documentation complete for setup and usage

**Manual Testing:**
1. Start all services: `docker compose up -d`
2. Add a local project via CLI: `sentinel index ~/my-project`
3. Trigger full pipeline: `sentinel build <id>` → `sentinel test <id>` → `sentinel scan <id>`
4. Query RAG: `sentinel ask "How does the auth module work?"`
5. View portfolio: `sentinel portfolio`
6. Check dashboard: `http://localhost:3000`
7. Run build script: `python scripts/build.py`

**Definition of Done:** Full system works end-to-end, CLI functional, release scripts ready.

**Estimated Time:** 120 minutes

**Dependencies:** All previous sprints.

---

## Phase 10: High-Value Features (Sprint 13)

### Sprint 13 — High-Value Features (Stretch Goals)

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
- `GET /api/v1/analysis/dependency-drift` — Version discrepancies
- `GET /api/v1/analysis/code-duplication` — Duplicated code blocks
- `GET /api/v1/analysis/tech-debt` — Tech debt heatmap
- `POST /api/v1/analysis/scenario` — What-if impact simulation

**Acceptance Criteria:**
- Dependency drift detector identifies version mismatches across projects
- Code duplication finder locates copy-pasted code
- Tech debt analyzer computes complexity and TODO density
- Scenario simulator propagates impact correctly
- All visualizations render correctly in browser

**Manual Testing:**
1. Add 2+ projects with differing dependency versions
2. Run dependency drift analysis → verify mismatches detected
3. Run duplication finder → verify duplicated code highlighted
4. Run tech debt analysis → verify heatmap populated
5. Run scenario simulation → verify impact propagation

**Definition of Done:** All four high-value features work with real data, UI visualizations render.

**Estimated Time:** 240 minutes

**Dependencies:** Sprint 2 (models), Sprint 3 (indexer), Sprint 7 (pipeline results).

---

## Phase 11: Deployment Hardening (Sprint 14)

### Sprint 14 — Deployment & Maintenance

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
- `GET /api/v1/system/backup` — Trigger database backup
- `GET /api/v1/system/status` — Comprehensive system status
- `GET /api/v1/system/logs` — Recent log entries

**Acceptance Criteria:**
- `scripts/backup.py` creates consistent backup snapshot
- `scripts/restore.py` restores from backup
- `scripts/monitor.py` reports system health
- Migration runner applies schema changes safely
- Log rotation configured and tested
- Deployment guide documented

**Manual Testing:**
1. Run `python scripts/backup.py` → verify backup created
2. Corrupt database → run `python scripts/restore.py backup_file` → verify restoration
3. Run `python scripts/monitor.py` → verify health report
4. Check log rotation → verify old logs cleaned

**Definition of Done:** Backup/restore/monitor scripts work, deployment hardened, maintenance procedures documented.

**Estimated Time:** 90 minutes

**Dependencies:** Sprint 12 (release prep).

---

## Phase 12: Final Polish (Sprint 15)

### Sprint 15 — Performance Tuning & Final Polish

**Objective:** Optimize performance, fix outstanding issues, and ensure the system is production-ready.

**Files Created:**
- `backend/app/utils/cache.py`
- `frontend/src/components/VirtualizedList.tsx`
- `docs/RELEASING.md`

**Files Modified:**
- `backend/app/services/*` (add caching where needed)
- `frontend/src/components/*` (optimize rendering)

**Database Changes:**
- Add indexes for frequently queried columns
- Optimize query patterns

**Backend Changes:**
- Add Redis-based caching for expensive computations
- Optimize repository queries with eager loading
- Add request timeout middleware
- Implement response compression (gzip)

**Frontend Changes:**
- Add virtualized lists for large result sets
- Optimize re-renders with React.memo/useCallback
- Add progressive loading for dashboards
- Implement offline-first patterns where applicable

**API Endpoints:** Existing endpoints optimized.

**Acceptance Criteria:**
- Dashboard loads in < 3 seconds with 10+ projects
- RAG queries return in < 5 seconds
- Portfolio scoring completes in < 10 seconds
- No unnecessary re-renders in frontend
- Memory usage stable over 24-hour period

**Manual Testing:**
1. Add 10+ projects to the system
2. Load Dashboard → measure load time
3. Query RAG with complex question → measure response time
4. Compute portfolio scores for all projects → measure time
5. Leave running overnight → check memory/CPU stability

**Definition of Done:** System meets performance targets, no memory leaks, all UI interactions smooth.

**Estimated Time:** 120 minutes

**Dependencies:** All previous sprints.

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
8. Install Ollama models: `ollama pull gemma2`, `ollama pull nomic-embed-text`
9. Backend: `cd backend && pip install -e .`
10. Frontend: `cd frontend && npm install`
11. Run `sentinel --help` to verify CLI is installed

---

## Appendix C: Sprint Template

Use this template for any new sprint added to the plan:

```markdown
### Sprint N — [Name]

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
- [Method] [path] — [description]

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

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-05 | 1.9 | Sprint 9 (World Simulator v1) complete: deterministic ant-farm shipped. Backend — `services/world_sim/{rules_engine,event_generator,skill_system,names,world_simulator}.py` (pure terrain + seeded per-day RNG; 9 daily steps; survival XP → tiers 0/50/150/300/500 → levels 1–5, +5% production/+10% rebuild per level); isolated DB `data/world_sim/world.db` (own metadata; tables `world_sim_state`, `world_settlements`, `world_roads`, `world_events`); `WorldSimulatorService` (advance in one transaction, bounded catch-up, god tools); router `/api/v1/world-sim/{state,history,settlements/{id},tick,reset,accelerate,disaster}`; Celery beat `world-sim-tick` (no new container); CLI `world-sim` wired; config `world_sim_*`. Frontend — `/world` route + nav, `api/world_sim.ts`, `WorldSimulatorPage` (3s tick, god controls, settlement inspector, event feed), `WorldGridMap` (2D canvas; BigInt hash copy so map == backend). Tests: 26 new (`test_world_sim.py`), full suite 119 green; flake8/black clean; `npm run build` clean. Docs: 02 §11 rewritten + §2.9/§5.1 updated, 01 §8.17/FG13 updated, all changelogs v1.9. Deferred to v2: diplomacy/tech/governments, per-agent AI, pause, spawn-resources, ML swap | User + AI agent |
| 2026-08-04 | 1.8 | Sprint 8.5 (Infrastructure Services): docker-compose.yml implemented — new `pihole` service (official `ghcr.io/pi-hole/pihole:latest` — Pi-hole moved off Docker Hub; `docker.io/pi-hole/pihole` returns repository-not-found, so images come from GitHub Container Registry — `profiles: ["pihole"]`, 53 tcp+udp + admin 8053, volumes under `data/pihole/`, `FTLCONF_LOCAL_IPV4=192.168.4.40`, `FTLCONF_webpassword=${PIHOLE_WEBPASSWORD}` from gitignored `.env`, `TZ=${PIHOLE_TZ:-UTC}`); `backend`/`worker` `SENTINEL_OLLAMA_HOST` → `http://192.168.4.40:11434` (laptop shared AI); `ollama` profile kept as desktop-local fallback. Architecture doc §9→§9/§9.1/§9.2 (Hardware Role & Infrastructure Services, two-machine topology) + §10 real IPs; impl guide §13.1 spec aligned + new §13.3 laptop deployment (OLLAMA_HOST 0.0.0.0, firewall, model pulls, compose pihole, router DHCP reservation + LAN DNS, multi-host env table incl. airadio `OLLAMA_URL`). `docker compose config` validated with dummy password; no runtime changes yet — laptop steps + desktop recreate are Phase 2/3 | User + AI agent |
| 2026-08-04 | 1.7 | Sprint 8 Part 2 (chat UI + live E2E): `frontend/src/api/rag.ts` (typed client for search/query/index/summaries; 120s timeout on query for local LLM), `components/ChatMessage.tsx` (user/assistant bubbles with source citations + distance + model/generated_at/confidence provenance, error state), `components/RagChat.tsx` (chat state, loading indicator, auto-scroll), `pages/KnowledgeExplorer.tsx` (project selector, Index knowledge button with optional AI architecture summary, semantic search + results, chat panel), route wiring `/knowledge` in `routes/index.tsx`. `tsc` + `vite build` clean. Live E2E vs real Ollama (native host, `nomic-embed-text` + `gemma2:2b` pulled; compose backend/worker rebuilt with chromadb and pointed at `host.docker.internal:11434` via temp override): RAG index ingested 6 file summaries + 2 test + 2 build logs into ChromaDB, semantic search returned ranked chunks, grounded query answered with 5 cited sources + provenance, `with_summary` persisted an architecture `KnowledgeSummary`, CLI `ask` printed sources + provenance, unreachable-Ollama exits 1 with pull instructions, Vite dev proxy served `/api/v1/projects/` live. Notes: docker image has no `git` binary so commit indexing degrades gracefully; full `gemma2` (vs `gemma2:2b`) needs `ollama pull gemma2` | User + AI agent | `frontend/src/api/rag.ts` (typed client for search/query/index/summaries; 120s timeout on query for local LLM), `components/ChatMessage.tsx` (user/assistant bubbles with source citations + distance + model/generated_at/confidence provenance, error state), `components/RagChat.tsx` (chat state, loading indicator, auto-scroll), `pages/KnowledgeExplorer.tsx` (project selector, Index knowledge button with optional AI architecture summary, semantic search + results, chat panel), route wiring `/knowledge` in `routes/index.tsx`. `tsc` + `vite build` clean. Live E2E vs real Ollama (native host, `nomic-embed-text` + `gemma2:2b` pulled; compose backend/worker rebuilt with chromadb and pointed at `host.docker.internal:11434` via temp override): RAG index ingested 6 file summaries + 2 test + 2 build logs into ChromaDB, semantic search returned ranked chunks, grounded query answered with 5 cited sources + provenance, `with_summary` persisted an architecture `KnowledgeSummary`, CLI `ask` printed sources + provenance, unreachable-Ollama exits 1 with pull instructions, Vite dev proxy served `/api/v1/projects/` live. Notes: docker image has no `git` binary so commit indexing degrades gracefully; full `gemma2` (vs `gemma2:2b`) needs `ollama pull gemma2` | User + AI agent |
| 2026-08-04 | 1.6 | Sprint 8 Part 1 (RAG backend core): `OllamaService` (generate/embed with `/api/embed` + legacy fallback, is_available/list_models, injectable transport), `ChromaManager` (embedded PersistentClient, 6 named collections, hnsw cosine, upsert/search/delete_by_project/count), `RagService` (index_project with raw-content ingestion + optional Ollama architecture summary persisted to `KnowledgeSummary`, semantic search with where-filter scoping, grounded `query()` returning sources + model/generated_at/confidence provenance; injectable embedder/llm), `GitHistoryService` + pure `parse_log` (`%H|%an|%aI|%s`, Windows-safe quoting, dedupe by hash), new repos (git, knowledge_summary), schemas `rag.py`/`knowledge.py`, routers `POST /api/v1/rag/search`, `POST /rag/query`, `POST /rag/index` (202 JobEnvelope on Celery `run_index_knowledge` task), `GET /projects/{id}/summaries`, CLI `ask` + `rag-index`. 91 tests passing (27 new; piped git-format quoting fixed for Windows). Chat UI + live E2E is Sprint 8 Part 2 | User + AI agent |
| 2026-08-04 | 1.5 | Sprint 7 complete: BuildRunner/TestRunner/SecurityScanner services (deterministic command discovery, pytest/jest output parsing, local advisory table, secret/static regex scanners), Celery app + `build_tasks.py` (worker + beat in compose, nightly scan schedule), repositories (build/test/security), routers `/api/v1/builds` (run/status/history, job_id == task_id), `/api/v1/tests` (run/results), `/api/v1/security` (scan/findings), CLI `build`/`test`/`scan` wired. 64 tests passing (14 new). Live-verified with docker worker: build succeeded (no-command), react build failed (exit 127, npm missing), pytest run 2 passed, security scan found vulnerability/secret/static_analysis. WS job-event broadcast over Redis pub/sub deferred to a later sprint — `/ws/jobs` stays heartbeat-only; build status is polled via REST | User + AI agent |
| 2026-08-04 | 1.4 | Sprint 6 complete: `/api/v1/projects` router (list/get/files), `/api/v1/ws/jobs` WebSocket (welcome + 30s heartbeat, real events land in Sprint 7), axios client + typed API modules, UI/Project/Build contexts, useProjects + useWebSocket hooks, Dashboard shows live data. Live-verified: proxied API through Vite, WS frames received, 404 passthrough | User + AI agent |
| 2026-08-04 | 1.3 | Sprint 5 complete: Vite 7 + React 19 + TS dashboard scaffolded (Layout with sidebar/header/dark toggle, Dashboard + placeholder routes, shared types mirroring SQLModel), `tsc` clean, dev server verified on 5173, `npm run build` succeeds | User + AI agent |
| 2026-08-04 | 1.2 | Sprint 4 complete: Dockerfile, compose stack, dev script, compose validation tests; verified live — `docker compose up -d` builds backend image, boots backend + redis, health returns 200, SQLite DB lands on `./data/sqlite/sentinel.db` (mounted volume), redis PONG, `scripts/dev.py --down` stops the stack | User + AI agent |
| 2026-08-04 | 1.1 | Sprint 0 alignment: Sprint 2 targets SQLite (was PostgreSQL), Pydantic schemas live in `schemas/` (was `models/`), `core/logging.py` (was `logger.py`), `POST /builds/status/{job_id}` → GET | User + AI agent |
