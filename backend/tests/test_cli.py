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

        def index_project(self, project, with_summary=False):
            return {"files": 3}

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

    monkeypatch.setattr(ollama_service.OllamaService, "is_available", lambda self: True)
    monkeypatch.setattr(rag_service, "RagService", FakeRagService)
    result = runner.invoke(cli.app, ["rag-index", project_id])
    assert result.exit_code == 0
    assert "Indexed Fake" in result.output


# --- portfolio / health / initdb / config -------------------------------------


def test_portfolio_stub():
    result = runner.invoke(cli.app, ["portfolio"])
    assert result.exit_code == 0
    assert "not implemented" in result.output


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


# --- world-sim (service faked; real sim DB is never touched) ------------------


class FakeWorld:
    def get_state(self, day=None):
        return {"day_number": 3, "seed": 7}

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
