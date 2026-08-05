"""Sprint 6: API endpoint integration tests (projects + websocket)."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import connection
from app.main import app
from app.services.indexer import IndexerService

client = TestClient(app)


def _seed_project(tmp_db) -> str:
    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(
            "tests/fixtures/sample_python_project"
        )
        return project.id


def test_list_projects_empty(tmp_db):
    resp = client.get("/api/v1/projects/")
    assert resp.status_code == 200
    assert resp.json() == {"projects": [], "total": 0}


def test_list_projects_after_index(tmp_db):
    _seed_project(tmp_db)
    resp = client.get("/api/v1/projects/")
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 1
    assert body["projects"][0]["language"] == "python"
    assert body["projects"][0]["framework"] == "fastapi"


def test_get_project_by_id(tmp_db):
    project_id = _seed_project(tmp_db)
    resp = client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == project_id
    assert body["name"] == "Sample Python Project"


def test_get_project_404(tmp_db):
    resp = client.get("/api/v1/projects/does-not-exist")
    assert resp.status_code == 404


def test_list_project_files(tmp_db):
    project_id = _seed_project(tmp_db)
    resp = client.get(f"/api/v1/projects/{project_id}/files")
    assert resp.status_code == 200
    files = resp.json()
    paths = {f["path"] for f in files}
    assert "app/main.py" in paths
    by_path = {f["path"]: f for f in files}
    assert by_path["app/main.py"]["language"] == "python"


def test_list_files_unknown_project_404(tmp_db):
    resp = client.get("/api/v1/projects/does-not-exist/files")
    assert resp.status_code == 404


def test_jobs_websocket_welcome_and_heartbeat(tmp_db):
    with client.websocket_connect("/api/v1/ws/jobs") as ws:
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["channel"] == "jobs"
