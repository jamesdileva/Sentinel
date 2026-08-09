"""PortfolioService — deterministic portfolio intelligence (docs/02 §14.5).

Aggregates each project's build, test, security and documentation state into a
0-100 health score, persists it to the `PortfolioScore` table, and produces the
candidate ranking and feature matrix. All logic is deterministic (no AI): scores
derive purely from stored rows, and nothing here mutates project data.

Scoring (Sprint 10 + Sprint 15 refinements):
- weights: build 30 / tests 30 / security 25 / docs 15
- build = 21 static (a build command was discovered in the repo) + 9 when the
  latest build actually passed. The static part survives a failed run — the
  command does not change because a build failed (Sprint 15 decision).
- tests = 24 static (test files exist in the repo) + 6 when the latest test
  run is green. Same static-first logic as build.
- security: unresolved findings deduct by severity; an all-resolved finding set
  (a scan happened) is "clean"; no findings at all is "pending" (never scanned)
- docs = fraction of indexed files that are README/Markdown/docs files;
  >= 50% counts as a green ✓ in the feature matrix (Sprint 15 threshold).
- a component with no data yet scores 0 (never assumed healthy)

Caching (Sprint 15): portfolio reads are cached in the `PortfolioScore` row.
A project is recomputed only when a source row (build/test/security/file) is
newer than the stored score, or when no score row exists yet — so repeated tab
loads are instant and the numbers refresh exactly when the underlying data
changes (e.g. after a repo sync pulls new commits).
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

# Sprint 15: static (detected) vs proven (ran green) split of the build/test
# components. The static part is granted purely from repo detection and is
# never lost to a failed run.
BUILD_STATIC = 21
BUILD_PROVEN = 9
TESTS_STATIC = 24
TESTS_PROVEN = 6

SEVERITY_PENALTY = {
    "critical": 10,
    "high": 6,
    "medium": 3,
    "low": 1,
    "info": 0,
}

_DOC_EXTENSIONS = (".md", ".markdown", ".mdx")
DOCS_GREEN_PCT = 50
FEATURE_LIST = ["build", "test", "docs", "security", "screenshots"]

# Test-file detection for the static tests component (Sprint 15).
_TEST_DIR_PARTS = ("tests", "__tests__", "test")


def is_doc_path(path: str) -> bool:
    """A file counts as documentation if it is Markdown, a README, or in docs/."""
    normalized = (path or "").replace("\\", "/").lower()
    if normalized.endswith(_DOC_EXTENSIONS):
        return True
    leaf = normalized.rsplit("/", 1)[-1]
    if leaf == "readme":
        return True
    return "/docs/" in f"/{normalized}"


def is_test_file_path(path: str) -> bool:
    """True for conventional test files: tests/ dirs, test_*.py, *_test.py,
    *.test.ts(x)/js, *.spec.ts(x)/js, __tests__/."""
    normalized = (path or "").replace("\\", "/").lower()
    parts = normalized.split("/")
    if any(part in _TEST_DIR_PARTS for part in parts):
        return True
    name = parts[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


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

    def _has_build_command(self, project: Project) -> bool:
        commands = (project.stack or {}).get("commands") or {}
        return bool(commands.get("build"))

    def _has_test_files(self, project_id: str) -> bool:
        return any(is_test_file_path(f.path) for f in self._files(project_id))

    # --- component scores -----------------------------------------------------

    def _build_component(self, project: Project) -> tuple[float, str]:
        if not self._has_build_command(project):
            return 0.0, "pending"
        build = self._latest_build(project.id)
        if build is not None and build.success is True:
            return float(BUILD_STATIC + BUILD_PROVEN), "passing"
        if build is not None and build.success is False:
            return float(BUILD_STATIC), "failing"
        return float(BUILD_STATIC), "configured"

    def _test_component(self, project_id: str) -> tuple[float, str]:
        test = self._latest_test(project_id)
        ran = test is not None and test.passed + test.failed + test.errors > 0
        if not self._has_test_files(project_id) and not ran:
            return 0.0, "pending"
        if ran and test.failed == 0 and test.errors == 0:
            return float(TESTS_STATIC + TESTS_PROVEN), "passing"
        if ran:
            return float(TESTS_STATIC), "failing"
        return float(TESTS_STATIC), "configured"

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

    # --- caching --------------------------------------------------------------

    def _source_epoch(self, project: Project) -> datetime.datetime:
        """Newest timestamp among the rows a score depends on; a score stored
        after this is still fresh and is served from cache.

        SQLite stores datetimes without tzinfo, so everything is normalized to
        naive UTC before comparing (aware/naive mixing raises TypeError).
        """
        project_id = project.id
        epochs: list[datetime.datetime] = []
        for stmt in (
            select(BuildLog.started_at).where(BuildLog.project_id == project_id),
            select(TestResult.run_at).where(TestResult.project_id == project_id),
            select(SecurityFinding.detected_at).where(
                SecurityFinding.project_id == project_id
            ),
            select(ProjectFile.created_at).where(ProjectFile.project_id == project_id),
        ):
            for value in self.session.exec(stmt).all():
                if value is not None:
                    epochs.append(value.replace(tzinfo=None) if value.tzinfo else value)
        if project.last_indexed is not None:
            value = project.last_indexed
            epochs.append(value.replace(tzinfo=None) if value.tzinfo else value)
        if not epochs:
            return datetime.datetime.min
        return max(epochs)

    def _fresh_row(self, project: Project) -> PortfolioScore:
        """Return the cached score row if it is up to date, else recompute."""
        row = self.session.exec(
            select(PortfolioScore).where(PortfolioScore.project_id == project.id)
        ).first()
        if row is not None and row.updated_at >= self._source_epoch(project):
            return row
        return self.compute_portfolio_score(project)

    # --- results --------------------------------------------------------------

    def compute_health_score(self, project: Project) -> float:
        """0-100 portfolio health score from component state (weights sum to 100)."""
        return self._components(project)["score"]

    def _components(self, project: Project) -> dict:
        build, build_status = self._build_component(project)
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
        """Fresh scores for every indexed project (cached where still valid)."""
        return [
            PortfolioScoreRead.model_validate(self._fresh_row(p))
            for p in self._all_projects()
        ]

    def get_best_candidates(self, min_score: float = 70.0) -> list[PortfolioCandidate]:
        """Ranked candidates (score >= min_score) with the items they are missing."""
        candidates: list[PortfolioCandidate] = []
        for project in self._all_projects():
            row = self._fresh_row(project)
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
            row = self._fresh_row(project)
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

    def summary(self) -> dict:
        """Dashboard numbers: project count, buildable projects, open findings,
        average health. Used by GET /api/v1/portfolio/summary (Sprint 15)."""
        projects = self._all_projects()
        rows = [self._fresh_row(p) for p in projects]
        buildable = sum(1 for p in projects if self._has_build_command(p))
        open_findings = len(
            list(
                self.session.exec(
                    select(SecurityFinding).where(
                        SecurityFinding.resolved == False
                    )  # noqa: E712
                ).all()
            )
        )
        avg_health = (
            round(sum(r.portfolio_score for r in rows) / len(rows), 1) if rows else 0.0
        )
        return {
            "projects": len(projects),
            "buildable": buildable,
            "open_findings": open_findings,
            "avg_health": avg_health,
        }

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
        if status in ("configured", "failing"):
            return "⚠"
        return "✗"

    def _docs_symbol(self, pct: int) -> str:
        if pct >= DOCS_GREEN_PCT:
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
