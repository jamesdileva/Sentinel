"""Sentinel CLI — command stubs matching docs/02_Implementation_Guide.md §5.1.

Commands are wired to services as sprints land; until then they report "not
implemented" alongside any deterministic information already available.
"""

import json

import typer

from app import __version__
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.connection import check_db, init_db

app = typer.Typer(
    help="Project Sentinel - local software operations platform.", no_args_is_help=True
)


@app.command()
def index(
    project_path: str | None = typer.Argument(
        None, help="Path to the project to index"
    ),
    all_projects: bool = typer.Option(
        False, "--all", help="Index all projects in watch dirs"
    ),
):
    """Index a single project or all projects in watch directories."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.indexer import IndexerService

    with Session(get_engine()) as session:
        service = IndexerService(session)
        if all_projects:
            projects = service.scan_all_projects()
            typer.echo(f"Indexed {len(projects)} project(s) from watch dirs.")
            return
        if project_path is None:
            typer.echo("Provide a project path or use --all.", err=True)
            raise typer.Exit(code=2)
        project = service.index_project(project_path)
        typer.echo(
            f"Indexed {project.name}: language={project.language}, "
            f"framework={project.framework}, id={project.id}"
        )


@app.command()
def scan(project_id: str):
    """Run a security scan on a project."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.security_scanner import SecurityScanner

    with Session(get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
        typer.echo(f"Security scan for {project.name}: {len(findings)} finding(s).")
        for finding in findings[:20]:
            typer.echo(
                f"  [{finding.severity.value}] {finding.title} "
                f"({finding.file_path}:{finding.line_number or 0})"
            )


@app.command()
def build(project_id: str):
    """Run a build for a project."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.build_runner import BuildRunner

    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
        log = BuildRunner(session).run_build(project)
        typer.echo(
            f"Build {log.id} for {project.name}: success={log.success} "
            f"exit_code={log.exit_code}"
        )
        if log.stderr:
            typer.echo(log.stderr[:2000], err=True)


@app.command()
def test(project_id: str):
    """Run tests for a project."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.test_runner import TestRunner

    with Session(get_engine()) as session:
        project = TestRunner.get_project(session, project_id)
        result = TestRunner(session).run_tests(project)
        typer.echo(
            f"Tests for {project.name}: {result.summary} "
            f"(framework={result.framework}, {result.duration_seconds}s)"
        )
        if result.raw_output:
            typer.echo(result.raw_output[:2000])


@app.command()
def ask(
    question: str,
    project_id: str | None = typer.Option(
        None, "--project", help="Project id to scope"
    ),
    top_k: int = typer.Option(5, "--top-k", min=1, max=20),
):
    """Ask the RAG system a question about your projects."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.ollama_service import OllamaService
    from app.services.rag_service import RagService

    if not OllamaService().is_available():
        typer.echo(
            "Ollama is not reachable. Start it with `docker compose --profile ollama up` "
            "and pull models: `ollama pull gemma2 nomic-embed-text`.",
            err=True,
        )
        raise typer.Exit(code=1)
    with Session(get_engine()) as session:
        response = RagService(session).query(
            question, project_id=project_id, top_k=top_k
        )
    typer.echo(response.answer)
    if response.sources:
        typer.echo(f"\nSources ({len(response.sources)}):")
        for source in response.sources:
            location = source.file_path or source.source
            typer.echo(f"  - {location} (distance {source.distance:.3f})")
    typer.echo(
        f"\n[model={response.model} generated_at={response.generated_at.isoformat()}]"
    )


@app.command(name="rag-index")
def rag_index(
    project_id: str | None = typer.Argument(
        None, help="Project id to ingest (omit with --reset)"
    ),
    with_summary: bool = typer.Option(
        False, "--summary", help="Also generate a project summary"
    ),
    reset: bool = typer.Option(
        False, "--reset", help="Drop all knowledge collections (v1.17.6 recovery)"
    ),
):
    """Ingest a project's knowledge into ChromaDB for RAG."""
    if reset:
        from app.services.chroma_manager import get_chroma_manager

        get_chroma_manager().reset_all()
        typer.echo(
            "Knowledge index reset — re-run `sentinel rag-index <project>` to rebuild."
        )
        return
    if project_id is None:
        typer.echo("Provide a project id (or use --reset).", err=True)
        raise typer.Exit(code=2)
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.ollama_service import OllamaService
    from app.services.rag_service import RagService

    if not OllamaService().is_available():
        typer.echo(
            "Ollama is not reachable. Start it with `docker compose --profile ollama up` "
            "and pull models: `ollama pull gemma2 nomic-embed-text`.",
            err=True,
        )
        raise typer.Exit(code=1)
    with Session(get_engine()) as session:
        project = RagService.get_project(session, project_id)
        counts = RagService(session).index_project(
            project, with_summary=with_summary, force_summary=with_summary
        )
        typer.echo(f"Indexed {project.name}: {counts}")


@app.command()
def portfolio():
    """Show portfolio scores across all projects (deterministic, no AI)."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.repositories import ProjectRepository
    from app.services.portfolio_service import PortfolioService

    with Session(get_engine()) as session:
        rows = PortfolioService(session).scores()
        if not rows:
            typer.echo("No indexed projects yet. Run `sentinel index <path>` first.")
            return
        names = {p.id: p.name for p in ProjectRepository(session).list()}
        header = (
            f"{'Project':<28} {'Score':>5}  {'Build':<12} {'Test':<12} "
            f"{'Docs':>4}  Security"
        )
        typer.echo(header)
        typer.echo("-" * len(header))
        for row in sorted(rows, key=lambda r: r.portfolio_score, reverse=True):
            typer.echo(
                f"{names.get(row.project_id, row.project_id):<28} "
                f"{row.portfolio_score:>5}  "
                f"{row.build_status:<12} {row.test_status:<12} "
                f"{row.documentation_pct:>3}%  {row.security_status}"
            )


@app.command()
def docs(project_id: str):
    """List documentation files for a project (deterministic)."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.repositories import ProjectFileRepository, ProjectRepository
    from app.services.portfolio_service import is_doc_path

    with Session(get_engine()) as session:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            typer.echo(f"Unknown project: {project_id}", err=True)
            raise typer.Exit(code=1)
        files = ProjectFileRepository(session).get_by_project(project_id)
        doc_files = [f for f in files if is_doc_path(f.path)]
        total = len(files)
        pct = int(round(100.0 * len(doc_files) / total)) if total else 0
        typer.echo(
            f"Documentation for {project.name}: "
            f"{len(doc_files)}/{total} files ({pct}%)"
        )
        for f in doc_files:
            typer.echo(f"  {f.path}")


@app.command()
def health():
    """Show system health status."""
    ok = check_db()
    typer.echo(
        json.dumps(
            {
                "app": settings.app_name,
                "version": __version__,
                "database": {"reachable": ok, "path": str(settings.db_path)},
                "watch_dirs": settings.watch_dirs,
                "ollama": settings.ollama_host,
            },
            indent=2,
        )
    )
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def initdb():
    """Create all database tables (Sprint 2)."""
    init_db()
    typer.echo("Database initialized.")


@app.command()
def config(
    action: str = typer.Argument("show"),
    key: str | None = None,
    value: str | None = None,
):
    """Show or update configuration: `config show` | `config set <key> <value>`."""
    if action == "show":
        typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2, default=str))
    elif action == "set":
        typer.echo("Config persistence not implemented yet.")
    else:
        typer.echo(f"Unknown action: {action}. Use `show` or `set`.", err=True)
        raise typer.Exit(code=2)


@app.command(name="world-sim")
def world_sim(
    action: str = typer.Argument(
        "state",
        help="start | state | tick | reset | accelerate | disaster | inspect",
    ),
    days: int = typer.Option(1, "--days", min=1, max=365, help="Days to advance"),
    seed: int | None = typer.Option(None, "--seed", help="New world seed (reset)"),
    scale: int = typer.Option(1, "--scale", min=1, max=10, help="Day-per-tick ratio"),
    settlement: str | None = typer.Option(
        None, "--settlement", help="Settlement id (disaster/inspect)"
    ),
    disaster_type: str | None = typer.Option(
        None, "--type", help="flood | drought | plague"
    ),
):
    """World Simulator controls (Sprint 9)."""
    from app.services.world_sim import WorldSimulatorService

    service = WorldSimulatorService()
    if action == "start":
        service.ensure_world()
        state = service.get_state(0)
        typer.echo(
            f"World started: day={state['day_number']}, "
            f"settlements={len(state.get('settlements', []))}"
        )
    elif action == "state":
        state = service.get_state()
        typer.echo(json.dumps(state, indent=2, default=str))
    elif action == "tick":
        service.advance_day(days)
        typer.echo(
            f"Advanced {days} day(s). Day is now {service.get_state(0)['day_number']}."
        )
    elif action == "reset":
        service.reset(seed)
        typer.echo(f"World reset (seed={seed if seed is not None else 'default'}).")
    elif action == "accelerate":
        service.set_time_scale(scale)
        typer.echo(f"Time scale set to {scale} days per tick.")
    elif action == "disaster":
        if not settlement or not disaster_type:
            typer.echo("disaster requires --settlement and --type.", err=True)
            raise typer.Exit(code=2)
        service.trigger_disaster(settlement, disaster_type)
        typer.echo(f"{disaster_type.title()} struck {settlement}.")
    elif action == "inspect":
        if not settlement:
            typer.echo("inspect requires --settlement.", err=True)
            raise typer.Exit(code=2)
        detail = service.get_settlement(settlement)
        if detail is None:
            typer.echo(f"Unknown settlement: {settlement}", err=True)
            raise typer.Exit(code=1)
        typer.echo(json.dumps(detail, indent=2, default=str))
    else:
        typer.echo(
            f"Unknown action: {action}. Use start|state|tick|reset|accelerate|disaster|inspect.",
            err=True,
        )
        raise typer.Exit(code=2)


@app.command()
def sync():
    """Clone/pull all repos from GitHub into watch dirs, then re-index."""
    from app.services.sync_service import run_sync

    result = run_sync()
    if result.get("skipped"):
        typer.echo(
            "SENTINEL_GITHUB_TOKEN is not configured - add it to the backend "
            "environment to enable repo syncing.",
            err=True,
        )
        raise typer.Exit(code=1)
    if result.get("error"):
        typer.echo(f"GitHub sync failed: {result['error']}", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"Synced GitHub repos: {len(result['cloned'])} cloned, "
        f"{len(result['pulled'])} updated."
    )
    for name in result["cloned"]:
        typer.echo(f"  + {name}")
    for name in result["pulled"]:
        typer.echo(f"  ~ {name}")
    for name, reason in result["failed"].items():
        typer.echo(f"  ! {name}: {reason}", err=True)
    knowledge = result.get("knowledge", {})
    if knowledge.get("skipped"):
        typer.echo(
            f"Knowledge indexing: skipped ({knowledge['skipped']}).",
            err=True,
        )
    else:
        typer.echo(
            f"Knowledge indexing: queued {knowledge.get('queued', 0)} project(s)."
        )
    typer.echo(
        f"Indexed {result['indexed']} project(s). "
        f"Next auto-sync in {_humanize_minutes(settings.sync_interval_minutes)}."
    )


def _humanize_minutes(minutes: int) -> str:
    """'1440' reads badly; say '24 hours' (v1.17.1 daily cadence)."""
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day(s)" if days == 1 else f"{days} days"
    if minutes % 60 == 0:
        return f"{minutes // 60} hour(s)"
    return f"{minutes} minute(s)"


@app.command()
def version():
    """Show the Sentinel version."""
    typer.echo(__version__)


def main() -> None:
    setup_logging()
    app()


if __name__ == "__main__":
    main()
