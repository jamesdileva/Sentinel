"""Sprint 11: CLI coverage (app/cli.py, docs/02 §5.1).

Every `sentinel` command is exercised through typer.testing.CliRunner with a
temp database. Commands that would touch Ollama/Chroma or the real world-sim
DB are faked at the service seam so tests stay hermetic and deterministic.
"""

import datetime

import pytest
from typer.testing import CliRunner

from app import __version__, cli

runner = CliRunner()

PYTHON_FIXTURE = "tests/fixtures/sample_python_project"


@pytest.fixture()
def project_id(tmp_db) -> str:
    """Seed one project through the real IndexerService."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.indexer import IndexerService

    with Session(get_engine()) as session:
        return IndexerService(session).index_project(PYTHON_FIXTURE).id


# --- index ------------------------------------------------------------------


def test_index_missing_path(tmp_db):
    result = runner.invoke(cli.app, ["index"])
    assert result.exit_code == 2
    assert "Provide a project path" in result.output


def test_index_project(project_id):
    result = runner.invoke(cli.app, ["index", PYTHON_FIXTURE])
    assert result.exit_code == 0
    assert "Indexed" in result.output
    assert "language=" in result.output


def test_index_all(project_id, monkeypatch):
    from app.services import indexer

    monkeypatch.setattr(indexer.IndexerService, "scan_all_projects", lambda self: [])
    result = runner.invoke(cli.app, ["index", "--all"])
    assert result.exit_code == 0
    assert "Indexed 0 project(s)" in result.output


# --- pipeline commands -------------------------------------------------------


def test_scan(project_id):
    result = runner.invoke(cli.app, ["scan", project_id])
    assert result.exit_code == 0
    assert "Security scan for" in result.output


def test_scan_unknown_project(tmp_db):
    result = runner.invoke(cli.app, ["scan", "missing"])
    assert result.exit_code == 1


def test_build(project_id):
    result = runner.invoke(cli.app, ["build", project_id])
    assert result.exit_code == 0
    assert "Build" in result.output


def test_build_unknown_project(tmp_db):
    result = runner.invoke(cli.app, ["build", "missing"])
    assert result.exit_code == 1


def test_test(project_id):
    result = runner.invoke(cli.app, ["test", project_id])
    assert result.exit_code == 0
    assert "Tests for" in result.output


def test_test_unknown_project(tmp_db):
    result = runner.invoke(cli.app, ["test", "missing"])
    assert result.exit_code == 1


# --- ask / rag-index (Ollama seam) -------------------------------------------


def test_ask_ollama_unreachable(monkeypatch):
    from app.services import ollama_service

    monkeypatch.setattr(
        ollama_service.OllamaService, "is_available", lambda self: False
    )
    result = runner.invoke(cli.app, ["ask", "how do I deploy?"])
    assert result.exit_code == 1
    assert "Ollama is not reachable" in result.output


def test_ask_answers(monkeypatch):
    from app.services import ollama_service, rag_service

    class FakeResponse:
        answer = "Deploy via docker compose."
        sources = []
        model = "fake"
        generated_at = datetime.datetime(2026, 8, 5, tzinfo=datetime.timezone.utc)

    class FakeRagService:
        def __init__(self, session):
            self.session = session

        def query(self, question, project_id=None, top_k=5):
            return FakeResponse()

    monkeypatch.setattr(ollama_service.OllamaService, "is_available", lambda self: True)
    monkeypatch.setattr(rag_service, "RagService", FakeRagService)
    result = runner.invoke(cli.app, ["ask", "deploy?"])
    assert result.exit_code == 0
    assert "Deploy via docker compose" in result.output


def test_rag_index_ollama_unreachable(monkeypatch):
    from app.services import ollama_service

    monkeypatch.setattr(
        ollama_service.OllamaService, "is_available", lambda self: False
    )
    result = runner.invoke(cli.app, ["rag-index", "some-id"])
    assert result.exit_code == 1
    assert "Ollama is not reachable" in result.output


def test_rag_index_ok(project_id, monkeypatch):
    from app.services import ollama_service, rag_service

    class FakeProject:
        id = project_id
        name = "Fake"

    class FakeRagService:
        def __init__(self, session):
            self.session = session

        def index_project(self, project, with_summary=False, force_summary=False):
            return {"files": 3}

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

    monkeypatch.setattr(ollama_service.OllamaService, "is_available", lambda self: True)
    monkeypatch.setattr(rag_service, "RagService", FakeRagService)
    result = runner.invoke(cli.app, ["rag-index", project_id])
    assert result.exit_code == 0
    assert "Indexed Fake" in result.output


def test_rag_index_reset_drops_knowledge(monkeypatch):
    """v1.17.6: `rag-index --reset` wipes the shared Chroma collections
    without needing a project id or Ollama.
    v1.17.6.7: it runs the full reset task, which also clears the
    embedding flags — otherwise the auto-index finds nothing to re-embed."""
    from app.tasks import rag_tasks

    calls = []

    def fake_reset():
        calls.append("run_reset_knowledge")
        return {"scopes": "all", "files_unflagged": 1427}

    monkeypatch.setattr(rag_tasks, "run_reset_knowledge", fake_reset)
    result = runner.invoke(cli.app, ["rag-index", "--reset"])
    assert result.exit_code == 0
    assert calls == ["run_reset_knowledge"]
    assert "Knowledge index reset" in result.output
    assert "1427 file(s) unflagged" in result.output


def test_rag_index_all_reindexes_every_project(monkeypatch):
    """v1.17.6.4: `rag-index --all` runs the re-index-all task (incremental,
    backfills missing AI architecture summaries)."""
    from app.tasks import rag_tasks

    called = []

    def fake_task():
        called.append(True)
        return {"projects": 2, "failed": 0, "ok": 2}

    monkeypatch.setattr(rag_tasks, "run_index_knowledge_all", fake_task)
    result = runner.invoke(cli.app, ["rag-index", "--all"])
    assert result.exit_code == 0
    assert called == [True]
    assert "Knowledge re-index complete" in result.output


def test_rag_index_without_id_or_reset_fails(monkeypatch):
    result = runner.invoke(cli.app, ["rag-index"])
    assert result.exit_code == 2
    assert "--reset" in result.output
    assert "--all" in result.output


# --- portfolio / health / initdb / config -------------------------------------


def test_portfolio_empty(tmp_db):
    result = runner.invoke(cli.app, ["portfolio"])
    assert result.exit_code == 0
    assert "No indexed projects" in result.output


def test_portfolio_shows_scores(project_id, monkeypatch):
    from app.services import portfolio_service

    class FakeRow:
        pass

    row = FakeRow()
    row.project_id = project_id
    row.portfolio_score = 55.0
    row.build_status = "success"
    row.test_status = "success"
    row.documentation_pct = 20
    row.security_status = "pending"

    monkeypatch.setattr(
        portfolio_service.PortfolioService, "scores", lambda self: [row]
    )
    result = runner.invoke(cli.app, ["portfolio"])
    assert result.exit_code == 0
    assert "55.0" in result.output
    assert "success" in result.output


def test_docs_lists_doc_files(project_id):
    result = runner.invoke(cli.app, ["docs", project_id])
    assert result.exit_code == 0
    assert "Documentation for" in result.output


def test_docs_unknown_project(tmp_db):
    result = runner.invoke(cli.app, ["docs", "missing"])
    assert result.exit_code == 1
    assert "Unknown project" in result.output


def test_health_ok(tmp_db):
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 0
    assert '"database"' in result.output
    assert __version__ in result.output


def test_health_unreachable(monkeypatch):
    monkeypatch.setattr(cli, "check_db", lambda: False)
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 1


def test_initdb(tmp_db):
    result = runner.invoke(cli.app, ["initdb"])
    assert result.exit_code == 0
    assert "Database initialized" in result.output


def test_config_show():
    result = runner.invoke(cli.app, ["config", "show"])
    assert result.exit_code == 0
    assert "app_name" in result.output


def test_config_set_is_parse_error():
    # `set` accepts no key/value arguments, so extra args fail at parse time;
    # the in-function `set` branch is unreachable dead code for now.
    result = runner.invoke(cli.app, ["config", "set", "foo", "bar"])
    assert result.exit_code == 2


def test_config_unknown_action():
    result = runner.invoke(cli.app, ["config", "bogus"])
    assert result.exit_code == 2


# --- sync (GitHub-backed repo sync, Sprint 12.1) ------------------------------


def test_sync_unconfigured(monkeypatch):
    from app.services import sync_service

    monkeypatch.setattr(sync_service.settings, "github_token", "")
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 1
    assert "SENTINEL_GITHUB_TOKEN" in result.output


def test_sync_ok(monkeypatch):
    from app.services import sync_service

    monkeypatch.setattr(
        sync_service,
        "run_sync",
        lambda: {
            "cloned": ["jamesdileva/MyApp"],
            "pulled": ["jamesdileva/Other"],
            "failed": {},
            "indexed": 3,
        },
    )
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 0
    assert "1 cloned" in result.output
    assert "+ jamesdileva/MyApp" in result.output
    assert "Indexed 3 project(s)" in result.output


def test_sync_error(monkeypatch):
    from app.services import sync_service

    monkeypatch.setattr(
        sync_service,
        "run_sync",
        lambda: {
            "configured": True,
            "error": "HTTPStatusError: 401 Bad credentials",
        },
    )
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 1
    assert "GitHub sync failed" in result.output


# --- world-sim (service faked; real sim DB is never touched) ------------------


class FakeWorld:
    def get_state(self, day=None):
        return {"day_number": 3, "seed": 7, "settlements": [{"id": "s1"}]}

    def ensure_world(self):
        return None

    def advance_day(self, days):
        return None

    def reset(self, seed=None):
        return None

    def set_time_scale(self, scale):
        return None

    def trigger_disaster(self, settlement, disaster_type):
        return None

    def get_settlement(self, settlement):
        return None if settlement == "nope" else {"name": settlement}


@pytest.fixture()
def fake_world(monkeypatch):
    from app.services import world_sim as world_sim_module

    monkeypatch.setattr(world_sim_module, "WorldSimulatorService", lambda: FakeWorld())


def test_world_sim_state(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "state"])
    assert result.exit_code == 0
    assert '"day_number": 3' in result.output


def test_world_sim_start(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "start"])
    assert result.exit_code == 0
    assert "World started" in result.output


def test_world_sim_tick(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "tick", "--days", "2"])
    assert result.exit_code == 0
    assert "Advanced 2 day(s)" in result.output


def test_world_sim_reset(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "reset", "--seed", "9"])
    assert result.exit_code == 0
    assert "World reset" in result.output


def test_world_sim_accelerate(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "accelerate", "--scale", "5"])
    assert result.exit_code == 0
    assert "Time scale set to 5" in result.output


def test_world_sim_disaster(fake_world):
    result = runner.invoke(
        cli.app, ["world-sim", "disaster", "--settlement", "s1", "--type", "flood"]
    )
    assert result.exit_code == 0
    assert "Flood struck s1" in result.output


def test_world_sim_disaster_missing_args(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "disaster"])
    assert result.exit_code == 2
    assert "requires --settlement and --type" in result.output


def test_world_sim_inspect(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "inspect", "--settlement", "s1"])
    assert result.exit_code == 0
    assert '"name": "s1"' in result.output


def test_world_sim_inspect_unknown(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "inspect", "--settlement", "nope"])
    assert result.exit_code == 1
    assert "Unknown settlement" in result.output


def test_world_sim_unknown_action(fake_world):
    result = runner.invoke(cli.app, ["world-sim", "bogus"])
    assert result.exit_code == 2
    assert "Unknown action" in result.output


# --- misc ---------------------------------------------------------------------


def test_version():
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__
