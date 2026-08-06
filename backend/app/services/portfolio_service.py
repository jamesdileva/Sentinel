"""PortfolioService — deterministic portfolio intelligence (docs/02 §14.5).

Aggregates each project's build, test, security and documentation state into a
0-100 health score, persists it to the `PortfolioScore` table, and produces the
candidate ranking and feature matrix. All logic is deterministic (no AI): scores
derive purely from stored rows, and nothing here mutates project data.

Scoring (Sprint 10 decisions):
- weights: build 30 / tests 30 / security 25 / docs 15
- a component with no data yet scores 0 (never assumed healthy)
- security: unresolved findings deduct by severity; an all-resolved finding set
  (a scan happened) is "clean"; no findings at all is "pending" (never scanned)
- docs = fraction of indexed files that are README/Markdown/docs files
"""

import datetime
from datetime import timezone

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import (
    BuildLog,
    PortfolioScore,
    Project,
    ProjectFile,
    SecurityFinding,
    TestResult,
)
from app.schemas import FeatureMatrix, PortfolioCandidate, PortfolioScoreRead

logger = get_logger(__name__)

WEIGHTS = {"build": 30, "tests": 30, "security": 25, "docs": 15}

SEVERITY_PENALTY = {
    "critical": 10,
    "high": 6,
    "medium": 3,
    "low": 1,
    "info": 0,
}

_DOC_EXTENSIONS = (".md", ".markdown", ".mdx")
FEATURE_LIST = ["build", "test", "docs", "security", "screenshots"]


def is_doc_path(path: str) -> bool:
    """A file counts as documentation if it is Markdown, a README, or in docs/."""
    normalized = (path or "").replace("\\", "/").lower()
    if normalized.endswith(_DOC_EXTENSIONS):
        return True
    leaf = normalized.rsplit("/", 1)[-1]
    if leaf == "readme":
        return True
    return "/docs/" in f"/{normalized}"


class PortfolioService:
    """Session-scoped service; one instance per request."""

    def __init__(self, session: Session):
        self.session = session

    # --- component evaluators -------------------------------------------------

    def _latest_build(self, project_id: str) -> BuildLog | None:
        stmt = (
            select(BuildLog)
            .where(BuildLog.project_id == project_id)
            .order_by(BuildLog.started_at.desc())
        )
        return self.session.exec(stmt).first()

    def _latest_test(self, project_id: str) -> TestResult | None:
        stmt = (
            select(TestResult)
            .where(TestResult.project_id == project_id)
            .order_by(TestResult.run_at.desc())
        )
        return self.session.exec(stmt).first()

    def _findings(self, project_id: str) -> list[SecurityFinding]:
        stmt = select(SecurityFinding).where(SecurityFinding.project_id == project_id)
        return list(self.session.exec(stmt).all())

    def _files(self, project_id: str) -> list[ProjectFile]:
        stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
        return list(self.session.exec(stmt).all())

    # --- component scores -----------------------------------------------------

    def _build_component(self, project_id: str) -> tuple[float, str]:
        build = self._latest_build(project_id)
        if build is None or build.success is None:
            return 0.0, "pending"
        if build.success:
            return float(WEIGHTS["build"]), "passing"
        return round(WEIGHTS["build"] / 3.0, 1), "failing"

    def _test_component(self, project_id: str) -> tuple[float, str]:
        test = self._latest_test(project_id)
        if test is None or test.passed + test.failed + test.errors <= 0:
            return 0.0, "pending"
        if test.failed == 0 and test.errors == 0:
            return float(WEIGHTS["tests"]), "passing"
        ratio = test.passed / (test.passed + test.failed + test.errors)
        return round(WEIGHTS["tests"] * ratio, 1), "failing"

    def _security_component(self, project_id: str) -> tuple[float, str]:
        findings = self._findings(project_id)
        if not findings:
            return 0.0, "pending"
        penalty = 0.0
        has_open = False
        for finding in findings:
            if not finding.resolved:
                has_open = True
                penalty += SEVERITY_PENALTY.get(str(finding.severity.value), 0)
        if not has_open:
            return float(WEIGHTS["security"]), "clean"
        return max(0.0, WEIGHTS["security"] - penalty), "findings"

    def _docs_component(self, project_id: str) -> tuple[float, int]:
        files = self._files(project_id)
        if not files:
            return 0.0, 0
        doc_count = sum(1 for f in files if is_doc_path(f.path))
        pct = int(round(100.0 * doc_count / len(files)))
        return round(WEIGHTS["docs"] * pct / 100.0, 1), pct

    # --- results --------------------------------------------------------------

    def compute_health_score(self, project: Project) -> float:
        """0-100 portfolio health score from component state (weights sum to 100)."""
        return self._components(project)["score"]

    def _components(self, project: Project) -> dict:
        build, build_status = self._build_component(project.id)
        tests, test_status = self._test_component(project.id)
        security, security_status = self._security_component(project.id)
        docs, docs_pct = self._docs_component(project.id)
        return {
            "score": round(build + tests + security + docs, 1),
            "build_status": build_status,
            "test_status": test_status,
            "security_status": security_status,
            "docs_pct": docs_pct,
        }

    def compute_portfolio_score(self, project: Project) -> PortfolioScore:
        """Recompute a project's score and upsert its PortfolioScore row."""
        components = self._components(project)

        row = self.session.exec(
            select(PortfolioScore).where(PortfolioScore.project_id == project.id)
        ).first()
        if row is None:
            row = PortfolioScore(project_id=project.id)

        row.build_status = components["build_status"]
        row.test_status = components["test_status"]
        row.security_status = components["security_status"]
        row.documentation_pct = components["docs_pct"]
        row.screenshots_available = False
        row.portfolio_score = components["score"]
        row.updated_at = datetime.datetime.now(timezone.utc)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def scores(self) -> list[PortfolioScoreRead]:
        """Fresh scores for every indexed project (recomputed, then persisted)."""
        return [
            PortfolioScoreRead.model_validate(self.compute_portfolio_score(p))
            for p in self._all_projects()
        ]

    def get_best_candidates(self, min_score: float = 70.0) -> list[PortfolioCandidate]:
        """Ranked candidates (score >= min_score) with the items they are missing."""
        candidates: list[PortfolioCandidate] = []
        for project in self._all_projects():
            row = self.compute_portfolio_score(project)
            if row.portfolio_score < min_score:
                continue
            candidates.append(
                PortfolioCandidate(
                    project_id=row.project_id,
                    project_name=project.name,
                    score=row.portfolio_score,
                    missing=self._missing_items(row),
                )
            )
        return sorted(candidates, key=lambda c: c.score, reverse=True)

    def feature_matrix(self) -> FeatureMatrix:
        """Grid of every project x feature with a ✓ / ⚠ / ✗ cell."""
        projects = self._all_projects()
        matrix: list[list[str]] = []
        for project in projects:
            row = self.compute_portfolio_score(project)
            matrix.append(
                [
                    self._pass_symbol(row.build_status),
                    self._pass_symbol(row.test_status),
                    self._docs_symbol(row.documentation_pct),
                    self._security_symbol(row.security_status),
                    "✗",
                ]
            )
        return FeatureMatrix(
            projects=[project.name for project in projects],
            features=list(FEATURE_LIST),
            matrix=matrix,
        )

    # --- helpers --------------------------------------------------------------

    def _all_projects(self) -> list[Project]:
        stmt = select(Project).order_by(Project.name)
        return list(self.session.exec(stmt).all())

    def _missing_items(self, row: PortfolioScore) -> list[str]:
        missing: list[str] = []
        if row.build_status == "pending":
            missing.append("build")
        if row.test_status == "pending":
            missing.append("tests")
        if row.security_status == "pending":
            missing.append("security")
        if row.documentation_pct == 0:
            missing.append("docs")
        return missing

    def _pass_symbol(self, status: str) -> str:
        if status == "passing":
            return "✓"
        if status == "failing":
            return "⚠"
        return "✗"

    def _docs_symbol(self, pct: int) -> str:
        if pct >= 80:
            return "✓"
        if pct > 0:
            return "⚠"
        return "✗"

    def _security_symbol(self, status: str) -> str:
        if status == "clean":
            return "✓"
        if status == "findings":
            return "⚠"
        return "✗"
