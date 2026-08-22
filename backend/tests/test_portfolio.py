"""Sprint 10: Portfolio intelligence tests.

Covers the deterministic health-score formula (30/30/20/15/5, missing = 0),
the v1.17.18.0 screenshot component and tester-session test credit,
PortfolioScore persistence/upsert, candidate ranking with missing items,
the feature matrix symbols, and the HTTP API. In-memory SQLite; no AI, no
network.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

import app.api.v1.portfolio as portfolio_api
from app.db.models import (
    AppSession,
    BuildLog,
    PortfolioScore,
    Project,
    ProjectFile,
    SecurityFinding,
    SessionScreenshot,
    SessionStatus,
    Severity,
)
from app.db.models import TestResult as TestResultRow
from app.main import app
from app.services.portfolio_service import (
    BUILD_PROVEN,
    BUILD_STATIC,
    PortfolioService,
    is_doc_path,
    is_test_file_path,
    refresh_all_scores,
)


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
    alpha = Project(
        name="alpha",
        path="/repo/alpha",
        language="python",
        stack={"commands": {"build": "python -m build", "test": "pytest"}},
    )
    beta = Project(
        name="beta",
        path="/repo/beta",
        language="go",
        stack={"commands": {"build": "go build", "test": "go test"}},
    )
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
        # v1.17.18.0: alpha also has a passed tester session + a screenshot —
        # the screenshots component and the tester test-credit both exercise.
        alpha_session = AppSession(
            project_id=alpha.id,
            title="Tester: alpha",
            status=SessionStatus.PASSED,
            ended_at=datetime.datetime(2026, 8, 5, 10, 2, tzinfo=datetime.timezone.utc),
        )
        session.add(alpha_session)
        session.flush()
        session.add(
            SessionScreenshot(
                session_id=alpha_session.id,
                path="alpha.png",
                captured_at=datetime.datetime(
                    2026, 8, 5, 10, 3, tzinfo=datetime.timezone.utc
                ),
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
    # build 30 + tests 30 + security 20 + docs 15*50% + screenshots 5
    # = 92.5 (v1.17.18.0 weights 30/30/20/15/5)
    assert svc.compute_health_score(projects["alpha"]) == 92.5


def test_health_score_broken_project():
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    # build 21 (static survives failed run) + tests 24 (static) + security 10
    # (critical unresolved) + docs 15*33% + no screenshots = 60.0
    assert svc.compute_health_score(projects["beta"]) == 60.0


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
    assert first.screenshots_available is True
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
# Sprint 15: change-driven cache + summary
# ---------------------------------------------------------------------------


def test_score_row_is_cached_until_sources_change():
    """A second read with no newer source rows serves the cached score without
    recomputing; adding a build log recomputes because the epoch advanced."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)

    svc.scores()  # prime the cache
    with Session(engine) as session:
        original = session.exec(
            select(PortfolioScore).where(
                PortfolioScore.project_id == projects["alpha"].id
            )
        ).first()
        assert original is not None
        assert original.portfolio_score == 92.5

    # No sources changed -> cached row untouched (same id/timestamp content).
    row = svc._fresh_row(projects["alpha"])
    assert row.id == original.id

    # A new build log (newer than the stored score) -> recompute.
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            BuildLog(
                project_id=projects["alpha"].id,
                started_at=datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=1),
                success=False,
            )
        )
        session.commit()
    row = svc._fresh_row(projects["alpha"])
    assert row.build_status == "failing"
    # static 21 survives + tests 30 + security 20 + docs 7.5 + screenshots 5
    assert row.portfolio_score == 83.5


def test_summary_counts():
    engine = make_engine()
    seed(engine)
    svc = make_service(engine)
    summary = svc.summary()
    assert summary["projects"] == 3
    assert summary["buildable"] == 2  # alpha + beta have commands.build
    assert summary["open_findings"] == 1  # only beta's unresolved critical
    assert summary["avg_health"] == round((92.5 + 60.0 + 0.0) / 3, 1)


def test_clean_scan_flips_pending_to_clean():
    """v1.17.6.6: gamma has no findings — pending while never scanned, but
    clean as soon as a scan stamped `last_scanned` (the scanner does this on
    every run, so a zero-finding scan is visibly healthy)."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc._security_component(projects["gamma"]) == (0.0, "pending")
    with Session(engine, expire_on_commit=False) as session:
        gamma = session.get(Project, projects["gamma"].id)
        gamma.last_scanned = datetime.datetime.now(datetime.timezone.utc)
        session.commit()
    assert svc._security_component(gamma) == (20.0, "clean")


def test_clean_scan_invalidates_cached_pending_score():
    """A clean scan writes no finding row, so the PortfolioScore cache would
    keep serving the stale "pending" verdict — `last_scanned` must count as
    a source-epoch change (v1.17.6.6)."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    svc.scores()  # prime the cache: gamma cached as pending/0
    with Session(engine, expire_on_commit=False) as session:
        gamma = session.get(Project, projects["gamma"].id)
        gamma.last_scanned = datetime.datetime.now(datetime.timezone.utc)
        session.commit()
    row = svc._fresh_row(gamma)
    assert row.security_status == "clean"
    assert row.portfolio_score == 20.0  # security 20, no build/test/docs


# ---------------------------------------------------------------------------
# v1.17.18.0: tester-session test credit + screenshot component
# ---------------------------------------------------------------------------


def test_passed_tester_session_credits_tests():
    """gamma has no test files and no TestResult — a passed `Tester:` session
    (the tester runner's own scripted run) counts as green test evidence."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc._test_component(projects["gamma"].id) == (0.0, "pending")
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            AppSession(
                project_id=projects["gamma"].id,
                title="Tester: gamma",
                status=SessionStatus.PASSED,
                ended_at=datetime.datetime(
                    2026, 8, 6, 9, 0, tzinfo=datetime.timezone.utc
                ),
            )
        )
        session.commit()
    assert svc._test_component(projects["gamma"].id) == (30.0, "passing")


def test_failed_tester_session_does_not_credit():
    """A non-green tester session is not test evidence at all."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            AppSession(
                project_id=projects["gamma"].id,
                title="Tester: gamma",
                status=SessionStatus.FAILED,
                ended_at=datetime.datetime(
                    2026, 8, 6, 9, 0, tzinfo=datetime.timezone.utc
                ),
            )
        )
        session.commit()
    assert svc._test_component(projects["gamma"].id) == (0.0, "pending")


def test_red_test_result_dominates_tester_credit():
    """An explicit red test run stays "failing" even when a passed tester
    session exists — a failed reported run is never masked by another path."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            TestResultRow(
                project_id=projects["gamma"].id,
                run_at=datetime.datetime(
                    2026, 8, 6, 10, 0, tzinfo=datetime.timezone.utc
                ),
                passed=5,
                failed=2,
                errors=0,
            )
        )
        session.add(
            AppSession(
                project_id=projects["gamma"].id,
                title="Tester: gamma",
                status=SessionStatus.PASSED,
                ended_at=datetime.datetime(
                    2026, 8, 6, 9, 0, tzinfo=datetime.timezone.utc
                ),
            )
        )
        session.commit()
    assert svc._test_component(projects["gamma"].id) == (24.0, "failing")


# ---------------------------------------------------------------------------
# v1.17.18.6.2: tester-session BUILD credit (found live 2026-08-22: AG /
# Demake / FinSight had green builds or passed tester runs but the matrix
# showed pending because the component gated on a discoverable build command)
# ---------------------------------------------------------------------------


def _add_tester_pass(engine, project_id: str) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            AppSession(
                project_id=project_id,
                title="Tester: app",
                status=SessionStatus.PASSED,
                ended_at=datetime.datetime(
                    2026, 8, 6, 9, 0, tzinfo=datetime.timezone.utc
                ),
            )
        )
        session.commit()


def test_build_component_green_log_without_command_passes():
    """AG/Demake case: a green BuildLog exists but no build command is
    discoverable today — history must be consulted regardless (was: pending)."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    gamma = projects["gamma"]
    assert svc._build_component(gamma) == (0.0, "pending")
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            BuildLog(
                project_id=gamma.id,
                started_at=datetime.datetime(
                    2026, 8, 5, 10, 0, tzinfo=datetime.timezone.utc
                ),
                success=True,
            )
        )
        session.commit()
    assert svc._build_component(gamma) == (
        float(BUILD_STATIC + BUILD_PROVEN),
        "passing",
    )


def test_build_component_tester_pass_credits_without_build_history():
    """FinSight case: no BuildLog at all, but a passed Tester session launched
    the built app — honest build proof -> full weight "passing"."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    gamma = projects["gamma"]
    assert svc._build_component(gamma) == (0.0, "pending")
    _add_tester_pass(engine, gamma.id)
    assert svc._build_component(gamma) == (
        float(BUILD_STATIC + BUILD_PROVEN),
        "passing",
    )


def test_build_component_red_build_dominates_tester_pass():
    """Symmetric with tests: an explicit red build stays "failing" even when
    a passed tester session exists."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    gamma = projects["gamma"]
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            BuildLog(
                project_id=gamma.id,
                started_at=datetime.datetime(
                    2026, 8, 5, 10, 0, tzinfo=datetime.timezone.utc
                ),
                success=False,
            )
        )
        session.commit()
    _add_tester_pass(engine, gamma.id)
    assert svc._build_component(gamma) == (float(BUILD_STATIC), "failing")


def test_screenshot_component_and_epoch():
    """Screenshots come from SessionScreenshot joined through their session;
    a new screenshot recomputes a cached score row (it is a source epoch)."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    assert svc._screenshots_available(projects["beta"].id) is False
    svc.scores()  # prime the cache
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            AppSession(
                project_id=projects["beta"].id,
                title="Manual run",
                status=SessionStatus.PASSED,
                ended_at=datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=1),
            )
        )
        session.commit()
        beta_session = session.exec(
            select(AppSession).where(
                AppSession.project_id == projects["beta"].id,
                AppSession.title == "Manual run",
            )
        ).one()
        session.add(
            SessionScreenshot(
                session_id=beta_session.id,
                path="beta.png",
                captured_at=datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=2),
            )
        )
        session.commit()
    row = svc._fresh_row(projects["beta"])
    assert row.screenshots_available is True
    # 21 build + 24 tests + 10 security + 5 docs + 5 screenshots = 65.0
    assert row.portfolio_score == 65.0


def test_refresh_all_scores_recomputes_cached_rows():
    """refresh_all_scores (startup hook) rewrites every cached row — the
    self-heal path for rows cached under older component definitions."""
    engine = make_engine()
    projects = seed(engine)
    svc = make_service(engine)
    svc.scores()  # prime the cache with the current definitions
    with Session(engine, expire_on_commit=False) as session:
        row = session.exec(
            select(PortfolioScore).where(
                PortfolioScore.project_id == projects["alpha"].id
            )
        ).first()
        row.screenshots_available = False  # simulate a stale pre-fix row
        row.portfolio_score = 87.5
        session.commit()

    refresh_all_scores(engine=engine)
    with Session(engine) as session:
        row = session.exec(
            select(PortfolioScore).where(
                PortfolioScore.project_id == projects["alpha"].id
            )
        ).first()
        assert row.screenshots_available is True
        assert row.portfolio_score == 92.5


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
    assert set(ranked[2].missing) == {
        "build",
        "tests",
        "security",
        "docs",
        "screenshots",
    }


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
    # docs at 50% is green (Sprint 15 threshold); alpha's screenshot flips
    # the last column (v1.17.18.0)
    assert matrix.matrix[0] == ["✓", "✓", "✓", "✓", "✓"]
    assert matrix.matrix[1] == ["⚠", "⚠", "⚠", "⚠", "✗"]
    assert matrix.matrix[2] == ["✗", "✗", "✗", "✗", "✗"]


def test_is_test_file_path():
    assert is_test_file_path("tests/test_main.py")
    assert is_test_file_path("tests/x_test.go")
    assert is_test_file_path("__tests__/App.test.tsx")
    assert is_test_file_path("src/app.spec.ts")
    assert is_test_file_path("src/test_util.py")
    assert is_test_file_path("src/app_test.py")
    assert not is_test_file_path("src/main.py")
    assert not is_test_file_path("README.md")


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
    assert body["matrix"][0] == ["✓", "✓", "✓", "✓", "✓"]


def test_api_summary(api_client):
    response = api_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["projects"] == 3
    assert body["buildable"] == 2
    assert body["open_findings"] == 1
    assert body["avg_health"] == 50.8
