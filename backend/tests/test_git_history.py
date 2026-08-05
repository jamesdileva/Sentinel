"""Sprint 8: GitHistoryService tests — pure parser + real temp repo."""

from pathlib import Path

from sqlmodel import Session

from app.db import connection
from app.db.models import GitCommit
from app.services.command_runner import run_command
from app.services.git_history import GitHistoryService, parse_log

LOG_TEXT = (Path(__file__).parent / "fixtures" / "sample_git_log.txt").read_text(
    encoding="utf-8"
)


def test_parse_log_parses_valid_lines_and_skips_garbage():
    commits = parse_log(LOG_TEXT)
    assert len(commits) == 3
    assert commits[0]["hash"] == "abc123def4567890abcdef1234567890abcdef12"
    assert commits[0]["author"] == "Alice Example"
    assert commits[0]["message"] == "Add CSV import for worklog"
    assert str(commits[1]["timestamp"].tzinfo) == "UTC"


def test_parse_log_ignores_empty():
    assert parse_log("") == []


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_command(f'git -C "{root}" init -q')
    run_command(f'git -C "{root}" config user.email test@example.com')
    run_command(f'git -C "{root}" config user.name Tester')
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    run_command(f'git -C "{root}" add app.py')
    run_command(f'git -C "{root}" commit -q -m "Initial app"')
    return root


def test_analyze_history_persists_commits(tmp_db, tmp_path):
    repo = _init_repo(tmp_path / "repo")
    run_command(f'git -C "{repo}" commit -q --allow-empty -m "Second change"')

    with Session(connection.get_engine()) as session:
        from app.db.models import Project

        project = Project(
            id="p-git", name="Git Repo", path=str(repo), language="python"
        )
        session.add(project)
        session.commit()
        service = GitHistoryService(session)
        commits = service.analyze_history(project)
        messages = {c.message for c in commits}

    assert len(commits) == 2
    assert {"Initial app", "Second change"} <= messages


def test_analyze_history_persists_only_once(tmp_db, tmp_path):
    repo = _init_repo(tmp_path / "repo")
    with Session(connection.get_engine()) as session:
        from app.db.models import Project

        project = Project(
            id="p-git2", name="Git Repo 2", path=str(repo), language="python"
        )
        session.add(project)
        session.commit()
        GitHistoryService(session).analyze_history(project)
        GitHistoryService(session).analyze_history(project)
        rows = session.exec(
            __import__("sqlmodel")
            .select(GitCommit)
            .where(GitCommit.project_id == project.id)
        ).all()
    assert len(rows) == 1
