# Project Sentinel

A local-first, privacy-respecting personal software operations platform that continuously
understands, maintains, tests, documents, and analyzes the user's software projects.

- **Personal CI/CD server** — automated build/test/scan pipelines on a schedule
- **Project intelligence platform** — structured knowledge model of every repository
- **Local AI assistant** — RAG-based Q&A over your projects via Ollama
- **Software maintenance system** — security scanning, doc generation, health scoring

Everything stays on your devices: SQLite + ChromaDB files, local Ollama LLM, no
cloud (docs/01 Rule 1).

## Status

Shipped through Sprint 15.1 (v1.16). Deployed natively on the always-on home
server — no Docker.

## Documentation

- `docs/01_Master_Architecture.md` — source of truth: vision, architecture, tech stack
- `docs/02_Implementation_Guide.md` — technical specs: schemas, APIs, services, deployment (§13)
- `docs/03_Sprint_Plan.md` — build roadmap: 15 sprints with acceptance criteria
- `docs/laptop.md` — on-server checklist for the always-on home server

## Quick Start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
cd frontend; npm install; npm run build; cd ..
.\.venv\Scripts\python.exe scripts\build.py --dist   # verify + stage the dashboard
.\.venv\Scripts\python.exe run.py                    # startup checks + serve on 127.0.0.1:8000
.\.venv\Scripts\python.exe scripts\install_service.py --install   # optional autostart
```

- Dashboard + API: http://127.0.0.1:8000 (System page: `/system`)
- Swagger UI: http://127.0.0.1:8000/docs
- CLI: `python -m app.cli --help` (inside `backend`)

## Project Rules

See `AGENTS.md` — the "constitution" every contributor and AI agent must follow.