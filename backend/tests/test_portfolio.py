"""Sprint 10: Portfolio intelligence tests.

Covers the deterministic health-score formula (30/30/25/15, missing = 0),
PortfolioScore persistence/upsert, candidate ranking with missing items, the
feature matrix symbols, and the HTTP API. In-memory SQLite; no AI, no network.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

import app.api.v1.portfolio as portfolio_api
from app.db.models import (
    BuildLog,
    PortfolioScore,
    Project,
    ProjectFile,
    SecurityFinding,
    Severity,
)
from app.db.models import TestResult as TestResultRow
from app.main import app
from app.services.portfolio_service import PortfolioService, is_doc_path


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed(engine) -> dict[str, Project]:
    """Three projects: alpha (healthy), beta (broken), gamma (untouched)."""
    alpha = Project(name="alpha", path="/repo/alpha", language="python")
    beta = Project(name="beta", path="/repo/beta", language="go")
    gamma = Project(name="gamma", path="/repo/gamma", language="rust")
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([alpha, beta, gamma])
        session.flush()

        session.add(
            BuildLog(
                project_id=alpha.id,
                started_at=datetime.datetime(
                    2026, 8, 5, 10, 0, tzinfo=datetime.timezone.utc
                ),
                success=True,
            )
        )
        session.add(
            BuildLog(
                project_id=beta.id,
                started_at=datetime.datetime(
                    2026, 8, 5, 10, 0, tzinfo=datetime.timezone.utc
                ),
                success=False,
            )
        )
        session.add(
            TestResultRow(
                project_id=alpha.id,
                run_at=datetime.datetime(
                    2026, 8, 5, 10, 1, tzinfo=datetime.timezone.utc
                ),
                passed=10,
                failed=0,
                errors=0,
            )
        )
        session.add(
            TestResultRow(
                project_id=beta.id,
                run_at=datetime.datetime(
                    2026, 8, 5, 10, 1, tzinfo=datetime.timezone.utc
                ),
                passed=10,
                failed=10,
                errors=0,
            )
        )
        session.add(
            SecurityFinding(
                project_id=alpha.id,
                type="dependency",
                severity=Severity.HIGH,
                title="old dep",
                resolved=True,
            )
        )
        session.add(
            SecurityFinding(
                project_id=beta.id,
                type="secret",
                severity=Severity.CRITICAL,
                title="token in repo",
                resolved=False,
            )
        )
        files = [
            ProjectFile(
                project_id=alpha.id, path="README.md", absolute_path="/r/README.md"
            ),
            ProjectFile(
                project_id=alpha.id,
                path="docs/guide.md",
                absolute_path="/r/docs/guide.md",
            ),
            ProjectFile(
                project_id=alpha.id, path="src/main.py", absolute_path="/r/src/main.py"
            ),
            ProjectFile(
                project_id=alpha.id, path="src/util.py", absolute_path="/r/src/util.py"
            ),
            ProjectFile(
                project_id=beta.id, path="README.md", absolute_path="/r/README.md"
            ),
            ProjectFile(
                project_id=beta.id, path="src/app.go", absolute_path="/r/src/app.go"
            ),
            ProjectFile(
                project_id=beta.id,
                path="tests/x_test.go",
                absolute_path="/r/tests/x_test.go",
            ),
        ]
        session.add_all(files)
        session.commit()
    return {"alpha": alpha, "beta": beta, "gamma": gamma}


def make_service(engine) -> PortfolioService:
    return PortfolioService(Session(engine))


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_is_doc_path():
    assert is_doc_path("README.md")
    assert is_doc_path("README")
    assert is_doc_path("docs/guide.md")
    assert is_doc_path("docs\\guide.markdown")
    assert is_doc_path("notes.mdx")
    assert not is_doc_path("src/main.py")
    assert not is_doc_path("README.py")
    assert not is_doc_path("")


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def test_health_score_healthy_project():
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc.compute_health_score(projects["alpha"]) == 92.5


def test_health_score_broken_project():
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc.compute_health_score(projects["beta"]) == 45.0


def test_health_score_untouched_project_is_zero():
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc.compute_health_score(projects["gamma"]) == 0.0


def test_compute_portfolio_score_upserts_row():
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    first = svc.compute_portfolio_score(projects["alpha"])
    second = svc.compute_portfolio_score(projects["alpha"])
    assert first.id == second.id
    assert first.build_status == "passing"
    assert first.test_status == "passing"
    assert first.security_status == "clean"
    assert first.documentation_pct == 50
    assert first.screenshots_available is False
    assert first.portfolio_score == 92.5


def test_scores_persists_all_projects():
    engine = make_engine()
    seed(engine)
    svc = make_service(engine)
    rows = svc.scores()
    assert [r.project_id for r in rows] == [p.id for p in svc._all_projects()]
    with Session(engine) as session:
        assert len(session.exec(select(PortfolioScore)).all()) == 3


# ---------------------------------------------------------------------------
# candidates + matrix
# ---------------------------------------------------------------------------


def test_best_candidates_ranked_with_missing():
    engine = make_engine()
    seed(engine)
    svc = make_service(engine)
    ranked = svc.get_best_candidates(min_score=0)
    assert [c.project_name for c in ranked] == ["alpha", "beta", "gamma"]
    assert ranked[0].score == 92.5
    assert ranked[0].missing == []
    assert ranked[2].score == 0.0
    assert set(ranked[2].missing) == {"build", "tests", "security", "docs"}


def test_best_candidates_min_score_filter():
    engine = make_engine()
    seed(engine)
    svc = make_service(engine)
    assert [c.project_name for c in svc.get_best_candidates(min_score=70)] == ["alpha"]
    assert svc.get_best_candidates(min_score=95) == []


def test_feature_matrix_symbols():
    engine = make_engine()
    seed(engine)
    svc = make_service(engine)
    matrix = svc.feature_matrix()
    assert matrix.features == ["build", "test", "docs", "security", "screenshots"]
    assert matrix.projects == ["alpha", "beta", "gamma"]
    assert matrix.matrix[0] == ["✓", "✓", "⚠", "✓", "✗"]
    assert matrix.matrix[1] == ["⚠", "⚠", "⚠", "⚠", "✗"]
    assert matrix.matrix[2] == ["✗", "✗", "✗", "✗", "✗"]


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    engine = make_engine()
    seed(engine)
    service = make_service(engine)
    app.dependency_overrides[portfolio_api.get_portfolio_service] = lambda: service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(portfolio_api.get_portfolio_service, None)


def test_api_scores(api_client):
    response = api_client.get("/api/v1/portfolio/scores")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert all("portfolio_score" in row for row in rows)
    assert max(row["portfolio_score"] for row in rows) == 92.5


def test_api_best_candidates(api_client):
    response = api_client.get(
        "/api/v1/portfolio/best-candidates", params={"min_score": 70}
    )
    assert response.status_code == 200
    assert [c["project_name"] for c in response.json()] == ["alpha"]


def test_api_feature_matrix(api_client):
    response = api_client.get("/api/v1/portfolio/feature-matrix")
    assert response.status_code == 200
    body = response.json()
    assert body["projects"] == ["alpha", "beta", "gamma"]
    assert body["matrix"][0] == ["✓", "✓", "⚠", "✓", "✗"]
