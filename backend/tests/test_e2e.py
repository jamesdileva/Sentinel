"""Sprint 11: full MVP pipeline as one deterministic flow (docs/02 §12.4).

index project -> security scan -> build -> test -> RAG index + query (fake
embedder/LLM, Chroma at tmp_path) -> portfolio score -> observatory views.
Everything runs in a temp database; no network, no model pulls, no data/
writes.
"""

from sqlmodel import Session

from app.db.connection import get_engine
from app.services.build_runner import BuildRunner
from app.services.chroma_manager import ChromaManager
from app.services.command_runner import CommandResult
from app.services.indexer import IndexerService
from app.services.observatory_service import ObservatoryService
from app.services.portfolio_service import PortfolioService
from app.services.rag_service import RagService
from app.services.security_scanner import SecurityScanner
from app.services.test_runner import TestRunner as TestRunnerService

FIXTURE = "tests/fixtures/sample_python_project"


def _fake_embedder(text: str) -> list[float]:
    import hashlib
    import math

    vector = [0.0] * 64
    for token in text.lower().split():
        digest = hashlib.md5(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "little") % 64] = 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _fake_llm(prompt: str) -> str:
    return "Pipeline e2e grounded answer."


def _noop(command: str, **kwargs) -> CommandResult:
    return CommandResult(
        command=command, exit_code=0, stdout="", stderr="", duration_seconds=0.1
    )


def _rag(session, tmp_path) -> RagService:
    return RagService(
        session,
        embedder=_fake_embedder,
        llm=_fake_llm,
        chroma=ChromaManager(path=tmp_path / "chroma"),
    )


def test_full_pipeline(tmp_db, tmp_path, monkeypatch):
    # 1. Index a real fixture project (language/framework/parsers chain).
    with Session(get_engine()) as session:
        project = IndexerService(session).index_project(FIXTURE)
        project_id = project.id
    assert project_id

    # 2. Security scan over the indexed files (offline regex scanners).
    with Session(get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
    assert isinstance(findings, list)

    # 3. Build and 4. test with no-op command executors -> stored rows.
    #    The fixture has no build command, so the honest outcome is a
    #    *skipped* build (success=None) — not a fake pass (v1.17.7.5).
    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
        log = BuildRunner(session).run_build(project, executor=_noop)
        assert log.success is None
        assert log.completed_at is not None
        project = TestRunnerService.get_project(session, project_id)
        result = TestRunnerService(session).run_tests(project, executor=_noop)
        assert result.summary is not None

    # 5. RAG: index the project, then ask a grounded question.
    with Session(get_engine()) as session:
        project = RagService.get_project(session, project_id)
        counts = _rag(session, tmp_path).index_project(project)
        assert counts["file_summaries"] >= 1
    with Session(get_engine()) as session:
        response = _rag(session, tmp_path).query(
            "what is this project?", project_id=project_id
        )
        assert response.answer
        assert response.model

    # 6. Portfolio scoring now has real build/test/security/docs inputs.
    with Session(get_engine()) as session:
        scores = PortfolioService(session).scores()
        assert scores, "portfolio returned no scores"
        assert any(s.project_id == project_id for s in scores)

    # 7. Observatory views reflect the indexed project.
    with Session(get_engine()) as session:
        obs = ObservatoryService(session)
        labels = [n.label for n in obs.galaxy().nodes]
        assert project.name in labels
        assert obs.architecture(project_id).count >= 1
        kinds = [e.kind for e in obs.timeline(days=365 * 3)]
        assert {"build", "test", "project-created"} <= set(kinds)
