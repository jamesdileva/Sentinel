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
from sqlmodel import Session, SQLModel, select

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
    alpha = Project(
        name="alpha", path="/repo/alpha", language="python", framework="fastapi"
    )
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
        session.add(
            SecurityFinding(
                project_id=alpha.id,
                type="static_analysis",
                severity=Severity.LOW,
                title="resolved leftover",
                detected_at=days_ago(4),
                resolved=True,
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
    assert all(project.detail is None for project in projects)


def test_galaxy_project_nodes_carry_framework():
    """v1.17.9.1: project nodes expose their framework for the focus panel."""
    engine = make_engine()
    seed(engine)
    graph = make_service(engine).galaxy()
    alpha = next(n for n in graph.nodes if n.label == "alpha")
    assert alpha.framework == "fastapi"
    assert alpha.kind == "project"
    techs = [n for n in graph.nodes if n.kind == "tech"]
    assert all(tech.framework is None for tech in techs)


def test_galaxy_groups_techs_case_insensitively():
    """v1.17.9: 'React' and 'react' from different projects merge into one
    tech node labeled with the most common casing."""
    engine = make_engine()
    seed(engine)
    with Session(engine, expire_on_commit=False) as session:
        _, beta = session.exec(select(Project)).all()[:2]
        session.add(Dependency(project_id=beta.id, name="React", version="19"))
        session.commit()
    graph = make_service(engine).galaxy()
    techs = [n for n in graph.nodes if n.kind == "tech"]
    assert [n.label for n in techs] == ["react"]
    assert "used by 2 projects" in techs[0].detail


def test_galaxy_disambiguates_duplicate_project_names():
    """v1.17.9: same-named projects (jamesdileva + juduncan checkouts) get
    their checkout dir as detail instead of identical-looking nodes."""
    engine = make_engine()
    seed(engine)
    with Session(engine, expire_on_commit=False) as session:
        _ = session.exec(select(Project).where(Project.name == "alpha")).one()
        twin = Project(name="alpha", path="/repo/juduncan/alpha", language="python")
        session.add(twin)
        session.commit()
    graph = make_service(engine).galaxy()
    projects = [n for n in graph.nodes if n.kind == "project"]
    assert [n.label for n in projects] == ["alpha", "alpha", "beta", "gamma"]
    assert sorted(p.detail for p in projects if p.detail) == [
        "juduncan",
        "repo",
    ]


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def test_timeline_window_and_order():
    engine = make_engine()
    seed(engine)
    timeline = make_service(engine).timeline(days=365)
    events = timeline.events
    assert len(events) == 5
    assert not timeline.has_more
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


def test_timeline_kind_filter():
    engine = make_engine()
    seed(engine)
    service = make_service(engine)
    assert [e.kind for e in service.timeline(days=365, kinds=["commit"]).events] == [
        "commit"
    ]
    assert [e.kind for e in service.timeline(days=365, kinds=["finding"]).events] == [
        "finding"
    ]
    assert service.timeline(days=365, kinds=["build", "test"]).events[0].kind == "build"


def test_timeline_project_filter():
    engine = make_engine()
    seed(engine)
    with Session(engine, expire_on_commit=False) as session:
        beta = session.exec(select(Project).where(Project.name == "beta")).one()
        beta.created_at = days_ago(1)
        session.add(beta)
        session.commit()
    events = make_service(engine).timeline(days=365, project_id=beta.id).events
    assert len(events) == 1
    assert events[0].kind == "project-created"
    assert events[0].project_name == "beta"


def test_timeline_pagination():
    engine = make_engine()
    seed(engine)
    service = make_service(engine)
    page1 = service.timeline(days=365, offset=0, limit=2)
    assert len(page1.events) == 2
    assert page1.has_more
    page2 = service.timeline(days=365, offset=2, limit=2)
    assert len(page2.events) == 2
    assert page2.has_more
    page3 = service.timeline(days=365, offset=4, limit=2)
    assert len(page3.events) == 1
    assert not page3.has_more
    ats = page1.events + page2.events + page3.events
    assert [e.at for e in ats] == sorted([e.at for e in ats], reverse=True)


def test_timeline_excludes_resolved_findings():
    """v1.17.7.7: resolved findings are stale scan leftovers and must not
    spam the timeline — only the open finding surfaces."""
    engine = make_engine()
    seed(engine)
    messages = [e.message for e in make_service(engine).timeline(days=365).events]
    assert any("token in repo" in message for message in messages)
    assert not any("resolved leftover" in message for message in messages)


def test_timeline_days_narrowing():
    engine = make_engine()
    seed(engine)
    service = make_service(engine)
    assert len(service.timeline(days=2).events) == 1
    assert service.timeline(days=2).events[0].kind == "commit"
    assert service.timeline(days=0).events == service.timeline(days=365).events


def test_timeline_old_activity_excluded():
    engine = make_engine()
    seed(engine)
    events = make_service(engine).timeline(days=365).events
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
    assert body["has_more"] is False


def test_api_timeline_filters_and_pagination(api_client):
    client, _ = api_client
    response = client.get(
        "/api/v1/observatory/timeline",
        params={"kind": "build,test", "offset": 0, "limit": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["kind"] == "build"
    assert body["has_more"] is True


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
