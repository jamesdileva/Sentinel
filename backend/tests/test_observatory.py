"""Sprint 10.5: Observatory tests.

Covers the shared-technology galaxy graph, the activity timeline (windowing,
kinds, ordering, cap), the architecture tree derived from file paths, and the
HTTP API. In-memory SQLite; no AI, no network.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

import app.api.v1.observatory as observatory_api
from app.db.models import (
    BuildLog,
    Dependency,
    GitCommit,
    Project,
    ProjectFile,
    SecurityFinding,
    Severity,
)
from app.db.models import TestResult as TestResultRow
from app.main import app
from app.services.observatory_service import ObservatoryService, _clip

NOW = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def days_ago(days: float) -> datetime.datetime:
    return NOW - datetime.timedelta(days=days)


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed(engine) -> dict[str, Project]:
    alpha = Project(name="alpha", path="/repo/alpha", language="python")
    beta = Project(name="beta", path="/repo/beta", language="typescript")
    gamma = Project(name="gamma", path="/repo/gamma", language="rust")
    with Session(engine, expire_on_commit=False) as session:
        alpha.created_at = days_ago(5)
        beta.created_at = days_ago(450)
        gamma.created_at = days_ago(500)
        session.add_all([alpha, beta, gamma])
        session.flush()

        session.add_all(
            [
                Dependency(project_id=alpha.id, name="react", version="18"),
                Dependency(project_id=alpha.id, name="fastapi", version="0.110"),
                Dependency(project_id=beta.id, name="react", version="18"),
                Dependency(project_id=beta.id, name="typescript", version="5.8"),
            ]
        )

        session.add_all(
            [
                GitCommit(
                    project_id=alpha.id,
                    hash="a" * 40,
                    message="add galaxy view",
                    timestamp=days_ago(1.2),
                ),
                GitCommit(
                    project_id=beta.id,
                    hash="b" * 40,
                    message="old work",
                    timestamp=days_ago(400),
                ),
            ]
        )
        session.add(
            BuildLog(
                project_id=alpha.id,
                started_at=days_ago(2.5),
                success=True,
            )
        )
        session.add(
            TestResultRow(
                project_id=alpha.id,
                run_at=days_ago(3),
                passed=10,
                failed=0,
                errors=0,
            )
        )
        session.add(
            SecurityFinding(
                project_id=alpha.id,
                type="secret",
                severity=Severity.MEDIUM,
                title="token in repo",
                detected_at=days_ago(4),
            )
        )
        session.add_all(
            [
                ProjectFile(
                    project_id=alpha.id, path="README.md", absolute_path="/r/README.md"
                ),
                ProjectFile(
                    project_id=alpha.id,
                    path="src/main.py",
                    absolute_path="/r/src/main.py",
                ),
                ProjectFile(
                    project_id=alpha.id,
                    path="src/util.py",
                    absolute_path="/r/src/util.py",
                ),
                ProjectFile(
                    project_id=alpha.id,
                    path="src/api/routes.py",
                    absolute_path="/r/src/api/routes.py",
                ),
                ProjectFile(
                    project_id=alpha.id,
                    path="tests/test_api.py",
                    absolute_path="/r/tests/test_api.py",
                ),
            ]
        )
        session.commit()
    return {"alpha": alpha, "beta": beta, "gamma": gamma}


def make_service(engine) -> ObservatoryService:
    return ObservatoryService(Session(engine))


# ---------------------------------------------------------------------------
# galaxy
# ---------------------------------------------------------------------------


def test_galaxy_only_shared_techs():
    engine = make_engine()
    seed(engine)
    graph = make_service(engine).galaxy()
    projects = [n for n in graph.nodes if n.kind == "project"]
    techs = [n for n in graph.nodes if n.kind == "tech"]
    assert [n.label for n in projects] == ["alpha", "beta", "gamma"]
    assert [n.label for n in techs] == ["react"]
    assert len(graph.links) == 2
    assert {link.tech for link in graph.links} == {"react"}


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def test_timeline_window_and_order():
    engine = make_engine()
    seed(engine)
    events = make_service(engine).timeline(days=365)
    assert len(events) == 5
    assert events[0].kind == "commit"
    assert events[-1].kind == "project-created"
    assert {e.kind for e in events} == {
        "project-created",
        "commit",
        "build",
        "test",
        "finding",
    }
    assert all(e.project_name == "alpha" for e in events)
    ats = [e.at for e in events]
    assert ats == sorted(ats, reverse=True)


def test_timeline_days_narrowing():
    engine = make_engine()
    seed(engine)
    service = make_service(engine)
    assert len(service.timeline(days=2)) == 1
    assert service.timeline(days=2)[0].kind == "commit"
    assert service.timeline(days=0) == service.timeline(days=365)  # guard


def test_timeline_old_activity_excluded():
    engine = make_engine()
    seed(engine)
    events = make_service(engine).timeline(days=365)
    messages = [e.message for e in events]
    assert not any("old work" in message for message in messages)


# ---------------------------------------------------------------------------
# architecture
# ---------------------------------------------------------------------------


def test_architecture_tree():
    engine = make_engine()
    projects = seed(engine)
    tree = make_service(engine).architecture(projects["alpha"].id)
    assert tree.name == "alpha"
    assert tree.kind == "dir"
    assert tree.count == 5
    names = [child.name for child in tree.children]
    assert names == ["src", "tests", "README.md"]  # dirs first, then files
    src = tree.children[0]
    assert src.kind == "dir"
    assert src.count == 3
    assert [c.name for c in src.children] == ["api", "main.py", "util.py"]
    assert src.children[0].children[0].name == "routes.py"


def test_architecture_unknown_project_raises():
    engine = make_engine()
    seed(engine)
    with pytest.raises(KeyError):
        make_service(engine).architecture("missing")


def test_clip_truncates():
    assert len(_clip("x" * 500)) == 120
    assert _clip("  hello\nworld  ") == "hello world"


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    engine = make_engine()
    projects = seed(engine)
    service = make_service(engine)
    app.dependency_overrides[observatory_api.get_observatory_service] = lambda: service
    with TestClient(app) as client:
        yield client, projects
    app.dependency_overrides.pop(observatory_api.get_observatory_service, None)


def test_api_galaxy(api_client):
    client, _ = api_client
    response = client.get("/api/v1/observatory/galaxy")
    assert response.status_code == 200
    body = response.json()
    assert len(body["links"]) == 2
    assert all(node["kind"] in ("project", "tech") for node in body["nodes"])


def test_api_timeline(api_client):
    client, _ = api_client
    response = client.get("/api/v1/observatory/timeline", params={"days": 2})
    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["kind"] == "commit"


def test_api_architecture(api_client):
    client, projects = api_client
    response = client.get(f"/api/v1/observatory/architecture/{projects['alpha'].id}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "alpha"
    assert body["count"] == 5


def test_api_architecture_404(api_client):
    client, _ = api_client
    response = client.get("/api/v1/observatory/architecture/missing")
    assert response.status_code == 404
