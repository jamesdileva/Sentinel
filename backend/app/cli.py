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
def ask(question: str):
    """Ask the RAG system a question about your projects."""
    typer.echo("RAG system not implemented yet (Sprint 8).")


@app.command()
def portfolio():
    """Show portfolio scores for all projects."""
    typer.echo("Portfolio service not implemented yet (Sprint 10).")


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
def world_sim(action: str = typer.Argument("state")):
    """World Simulator controls: state | tick | start | reset (Sprint 9)."""
    typer.echo("World Simulator not implemented yet (Sprint 9).")


@app.command()
def version():
    """Show the Sentinel version."""
    typer.echo(__version__)


def main() -> None:
    setup_logging()
    app()


if __name__ == "__main__":
    main()
