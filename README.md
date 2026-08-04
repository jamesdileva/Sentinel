# Project Sentinel

A local-first, privacy-respecting personal software operations platform that continuously
understands, maintains, tests, documents, and analyzes the user's software projects.

- **Personal CI/CD server** — automated build/test/scan pipelines on a schedule
- **Project intelligence platform** — structured knowledge model of every repository
- **Local AI assistant** — RAG-based Q&A over your projects via Ollama
- **Software maintenance system** — security scanning, doc generation, health scoring

## Status

Sprint 0 / 1 — Phase 0 (Pre-MVP). Backend scaffolding in progress.

## Documentation

- `docs/01_Master_Architecture.md` — source of truth: vision, architecture, tech stack
- `docs/02_Implementation_Guide.md` — technical specs: schemas, APIs, services, compose
- `docs/03_Sprint_Plan.md` — build roadmap: 15 sprints with acceptance criteria

## Quick Start (backend dev)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn app.main:app --reload
```

- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs
- CLI: `sentinel --help`

## Project Rules

See `AGENTS.md` — the "constitution" every contributor and AI agent must follow.
