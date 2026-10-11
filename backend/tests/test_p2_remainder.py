"""Audit B2, B8 and B10 — the P2 findings no batch had absorbed.

B2: a path outside the project root aborted a whole incremental update.
B8: `/health` claimed "healthy" while reporting the database unreachable.
B10: operational settings accepted values that cannot work.
"""

import pytest

from app.core.config import Settings
from app.db.models import Project, ProjectFile

# --- B2 --------------------------------------------------------------------


def test_update_incremental_skips_a_path_outside_the_project(tmp_db, tmp_path):
    """v1.17.19.20 (audit B2): `absolute.relative_to(project_root)` used to
    raise ValueError on an outside path, which lost the rest of the batch."""
    from sqlmodel import Session, select

    from app.db.connection import get_engine
    from app.services.indexer import IndexerService as Indexer

    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    outside = tmp_path / "elsewhere.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    inside = project_dir / "inside.py"
    inside.write_text("print(1)\n", encoding="utf-8")

    with Session(get_engine()) as session:
        project = Project(name="b2", path=str(project_dir), language="Python")
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id

    with Session(get_engine()) as session:
        indexer = Indexer(session)
        processed = indexer.update_incremental(
            project_id,
            [str(outside), str(inside), "../escapee.py", "..\\escapee2.py"],
        )
        assert processed == 1
        rows = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        ).all()
    paths = {row.path for row in rows}
    assert "inside.py" in paths
    assert not any("outside" in path or "escapee" in path for path in paths)


def test_update_incremental_still_raises_for_an_unknown_project(tmp_db):
    """The guard is about *paths*, not about typos: an unknown project is
    still a caller error worth a clear exception."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.indexer import IndexerService as Indexer

    with Session(get_engine()) as session, pytest.raises(ValueError):
        Indexer(session).update_incremental("no-such-project", ["a.py"])


# --- B8 --------------------------------------------------------------------


def test_health_reports_degraded_when_the_database_is_unreachable(client, monkeypatch):
    """v1.17.19.20 (audit B8): `status` used to be a hard-coded "healthy" even
    when `database.reachable` was false — contradictory for monitoring."""
    from app import main

    monkeypatch.setattr(main, "check_db", lambda: False)
    response = client.get("/health")
    assert response.status_code == 200  # up, but degraded — not down
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["reachable"] is False


def test_health_stays_healthy_when_the_database_answers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_a_degraded_health_still_reaches_the_desktop_shell(client, monkeypatch):
    """The desktop shell treats any non-200 as "the backend is not there" and
    would then spawn a second one. That is why B8 is a status word, not a 503."""
    from app import main

    monkeypatch.setattr(main, "check_db", lambda: False)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


# --- B10 -------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("command_timeout_seconds", 0),
        ("ollama_timeout_seconds", -1),
        ("ollama_num_ctx", 512),  # below Ollama's own default
        ("ollama_summary_max_tokens", 0),
        ("scan_interval_minutes", 0),
        ("sync_interval_minutes", 0),
        ("world_sim_tick_seconds", 0),
        ("world_sim_time_scale", 0),
        ("max_file_size_kb", 0),
        ("rag_relevance_floor", -0.1),
        ("rag_relevance_floor", 1.5),
    ],
)
def test_impossible_operational_values_are_rejected(field, value):
    """v1.17.19.20 (audit B10): each of these makes the thing it configures
    impossible to run, so settings refuse to load."""
    with pytest.raises(Exception) as exc:
        Settings(_env_file=None, **{field: value})
    assert field in str(exc.value)


def test_the_documented_off_switch_is_still_accepted():
    """A zero is a setting here, not a broken one: the sweep is disabled."""
    fresh = Settings(_env_file=None, screenshot_retention_days=0)
    assert fresh.screenshot_retention_days == 0


def test_default_settings_still_load():
    """The guard must not reject the shipped defaults."""
    fresh = Settings(_env_file=None)
    assert fresh.command_timeout_seconds == 300
    assert fresh.ollama_num_ctx == 32768
    assert fresh.rag_relevance_floor == 0.487


def test_late_assignment_is_deliberately_unvalidated(monkeypatch):
    """Tests (and only tests) fake hostile values after load; validate_
    assignment is off so that stays possible."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "command_timeout_seconds", 0)
    assert settings.command_timeout_seconds == 0
