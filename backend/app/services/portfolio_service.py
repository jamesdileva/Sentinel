"""PortfolioService — deterministic portfolio intelligence (docs/02 §14.5).

Aggregates each project's build, test, security, documentation and
screenshot state into a 0-100 health score, persists it to the
`PortfolioScore` table, and produces the candidate ranking and feature
matrix. All logic is deterministic (no AI): scores derive purely from
stored rows, and nothing here mutates project data.

Scoring (Sprint 10 + Sprint 15 refinements + v1.17.18.0):
- weights: build 30 / tests 30 / security 20 / docs 15 / screenshots 5
- build = 21 static (a build command was discovered in the repo) + 9 when the
  latest build actually passed. The static part survives a failed run — the
  command does not change because a build failed (Sprint 15 decision).
- tests = 24 static (test files exist in the repo) + 6 when there is green
  evidence. Evidence since v1.17.18.0: the latest test run is green OR a
  passed tester session exists (`Tester:` sessions auto-created by the
  tester runner — a scripted run of the app's own suite is honest test
  evidence). An explicit red test run dominates (failing, static only).
- security: unresolved findings deduct by severity; scanned with no open
  findings (including zero findings — `last_scanned` is stamped on every run
  since v1.17.6.6) is "clean"; no findings AND never scanned is "pending"
- docs = fraction of indexed files that are README/Markdown/docs files;
  >= 50% counts as a green ✓ in the feature matrix (Sprint 15 threshold).
- screenshots (v1.17.18.0): 5 points when the project has at least one
  session screenshot (SessionScreenshot rows — the Sessions page captures).
  The feature-matrix column was a hardcoded ✗ stub before this version.
- a component with no data yet scores 0 (never assumed healthy)

Caching (Sprint 15): portfolio reads are cached in the `PortfolioScore` row.
A project is recomputed only when a source row (build/test/security/file/
screenshot/session) is newer than the stored score, or when no score row
exists yet — so repeated tab loads are instant and the numbers refresh
exactly when the underlying data changes (e.g. after a repo sync pulls new
commits). `refresh_all_scores()` at startup (v1.17.18.0) recomputes every
row once so rows cached under older component definitions self-heal.
"""

import datetime
from datetime import timezone

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import (
    AppSession,
    BuildLog,
    PortfolioScore,
    Project,
    ProjectFile,
    SecurityFinding,
    SessionScreenshot,
    SessionStatus,
    TestResult,
)
from app.schemas import FeatureMatrix, PortfolioCandidate, PortfolioScoreRead

logger = get_logger(__name__)

WEIGHTS = {"build": 30, "tests": 30, "security": 20, "docs": 15, "screenshots": 5}

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


def _is_readme(path: str) -> bool:
    """True when the file is a README (any location, any doc extension)."""
    leaf = (path or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return leaf == "readme" or leaf.startswith("readme.")


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
        if commands.get("build"):
            return True
        # v1.17.7.5: the index-time stack may predate a README/manifest
        # command; consult runtime discovery so the matrix matches what a
        # build would actually run.
        from app.utils.command_extractor import extract_build_commands

        return bool(extract_build_commands(project.path).get("build"))

    def _has_test_files(self, project_id: str) -> bool:
        return any(is_test_file_path(f.path) for f in self._files(project_id))

    def _latest_tester_pass(self, project_id: str) -> AppSession | None:
        """Most recent passed `Tester:` session (auto-created by the tester
        runner). A green scripted run of the app's own suite is honest test
        evidence — v1.17.18.0."""
        stmt = (
            select(AppSession)
            .where(
                AppSession.project_id == project_id,
                AppSession.status == SessionStatus.PASSED,
                AppSession.title.startswith("Tester:"),
            )
            .order_by(AppSession.ended_at.desc())
        )
        return self.session.exec(stmt).first()

    def _screenshots_available(self, project_id: str) -> bool:
        """Any session screenshot for the project (the Sessions page's
        captures count — v1.17.18.0, was a hardcoded ✗ stub)."""
        stmt = (
            select(SessionScreenshot.id)
            .join(AppSession, SessionScreenshot.session_id == AppSession.id)
            .where(AppSession.project_id == project_id)
            .limit(1)
        )
        return self.session.exec(stmt).first() is not None

    # --- component scores -----------------------------------------------------

    def _build_component(self, project: Project) -> tuple[float, str]:
        """Build component (audit2 follow-up, v1.17.18.6.2).

        Evidence, strongest first:
        1. A BuildLog row ran green -> full weight "passing"; ran red ->
           static only "failing" (explicit red dominates later green
           evidence — mirrors the tests component).
        2. No build history at all: a PASSED `Tester:` session is honest
           build proof for projects whose build step is implicit (interpreted
           apps, packaged Electron) — the tester launched the built app and
           asserted real behavior (v1.17.18.0 gave tests the same credit).
        3. Only a discovered command and nothing ran -> static "configured".
        4. Nothing known -> "pending".

        The old gate (`no build command -> pending`, before history was ever
        consulted) hid proven builds behind a discovery miss: AG and Demake
        Engine had green BuildLog rows but showed ✗."""
        has_cmd = self._has_build_command(project)
        proven_run = self._latest_tester_pass(project.id) is not None
        build = self._latest_build(project.id)

        if build is not None and build.success is False:
            return float(BUILD_STATIC), "failing"
        if build is not None and build.success is True:
            return float(BUILD_STATIC + BUILD_PROVEN), "passing"
        if proven_run:
            return float(BUILD_STATIC + BUILD_PROVEN), "passing"
        if has_cmd:
            return float(BUILD_STATIC), "configured"
        return 0.0, "pending"

    def _test_component(self, project_id: str) -> tuple[float, str]:
        test = self._latest_test(project_id)
        ran = test is not None and test.passed + test.failed + test.errors > 0
        if ran and (test.failed > 0 or test.errors > 0):
            # an explicit red run dominates any later green evidence
            return float(TESTS_STATIC), "failing"
        tester_pass = self._latest_tester_pass(project_id) is not None
        if not self._has_test_files(project_id) and not ran and not tester_pass:
            return 0.0, "pending"
        if (ran and test.failed == 0 and test.errors == 0) or tester_pass:
            return float(TESTS_STATIC + TESTS_PROVEN), "passing"
        return float(TESTS_STATIC), "configured"

    def _security_component(self, project: Project) -> tuple[float, str]:
        # v1.17.6.6: the scanner stamps `project.last_scanned` on every run,
        # so a clean scan (no finding rows at all) is now visibly "clean"
        # instead of the old permanent "pending" ✗. Pending means: never
        # scanned AND no findings — the two prove-one-another case.
        findings = self._findings(project.id)
        if not findings and project.last_scanned is None:
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

    def _docs_component(self, project_id: str) -> tuple[float, int, str]:
        """Docs verdict from PRESENCE, not density (v1.17.18.6).

        The old rule (✓ needs ≥50% of indexed files to be markdown) marked
        well-documented code-heavy projects ✗ — a 200-file repo with a
        README and a docs/ dir scored ~2%. Now:
        - "passing" ✓: README present AND at least one other doc file
        - "partial" ⚠: some docs but no README (or README alone)
        - "pending" ✗: no documentation at all
        `documentation_pct` stays as the informational density figure."""
        files = self._files(project_id)
        if not files:
            return 0.0, 0, "pending"
        doc_files = [f for f in files if is_doc_path(f.path)]
        pct = int(round(100.0 * len(doc_files) / len(files)))
        if not doc_files:
            return 0.0, pct, "pending"
        has_readme = any(_is_readme(f.path) for f in doc_files)
        has_more = len(doc_files) > (1 if has_readme else 0)
        if has_readme:
            status = "passing" if has_more else "partial"
            points = (
                float(WEIGHTS["docs"]) if status == "passing" else WEIGHTS["docs"] / 2
            )
            return points, pct, status
        return WEIGHTS["docs"] / 2, pct, "partial"

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
            # v1.17.18.0: screenshots and tester sessions are score sources too
            select(SessionScreenshot.captured_at)
            .join(AppSession, SessionScreenshot.session_id == AppSession.id)
            .where(AppSession.project_id == project_id),
            select(AppSession.ended_at).where(
                AppSession.project_id == project_id,
                AppSession.status == SessionStatus.PASSED,
                AppSession.title.startswith("Tester:"),
            ),
        ):
            for value in self.session.exec(stmt).all():
                if value is not None:
                    epochs.append(value.replace(tzinfo=None) if value.tzinfo else value)
        if project.last_indexed is not None:
            value = project.last_indexed
            epochs.append(value.replace(tzinfo=None) if value.tzinfo else value)
        # v1.17.6.6: a clean scan stamps only `last_scanned` — no finding row
        # changes — so without this the cached "pending" score would persist
        # forever after the first clean scan.
        if project.last_scanned is not None:
            value = project.last_scanned
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
        security, security_status = self._security_component(project)
        docs, docs_pct, docs_status = self._docs_component(project.id)
        screenshots_available = self._screenshots_available(project.id)
        screenshots = float(WEIGHTS["screenshots"]) if screenshots_available else 0.0
        return {
            "score": round(build + tests + security + docs + screenshots, 1),
            "build_status": build_status,
            "test_status": test_status,
            "security_status": security_status,
            "docs_pct": docs_pct,
            "docs_status": docs_status,
            "screenshots_available": screenshots_available,
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
        row.documentation_status = components["docs_status"]
        row.screenshots_available = components["screenshots_available"]
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
                    self._docs_symbol(row.documentation_status),
                    self._security_symbol(row.security_status),
                    # v1.17.18.0: real data — was a hardcoded ✗ stub
                    "✓" if row.screenshots_available else "✗",
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
                        SecurityFinding.resolved == False  # noqa: E712
                    )
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
        if getattr(row, "documentation_status", "pending") == "pending":
            missing.append("docs")
        if not row.screenshots_available:
            missing.append("screenshots")
        return missing

    def _pass_symbol(self, status: str) -> str:
        if status == "passing":
            return "✓"
        if status in ("configured", "failing"):
            return "⚠"
        return "✗"

    def _docs_symbol(self, status_or_pct) -> str:
        """Docs cell. v1.17.18.6: prefers the presence-based
        `documentation_status`; falls back to the density percentage for
        score rows cached before the migration."""
        if isinstance(status_or_pct, str):
            if status_or_pct == "passing":
                return "✓"
            if status_or_pct == "partial":
                return "⚠"
            return "✗"
        if status_or_pct >= DOCS_GREEN_PCT:
            return "✓"
        if status_or_pct > 0:
            return "⚠"
        return "✗"

    def _security_symbol(self, status: str) -> str:
        if status == "clean":
            return "✓"
        if status == "findings":
            return "⚠"
        return "✗"


def refresh_all_scores(engine=None) -> None:
    """Recompute every project's cached score row (v1.17.18.0).

    Called at backend startup so rows cached under older component
    definitions (e.g. the pre-screenshots stub, the old 25/15 weights)
    self-heal without waiting for new source data. Deterministic and cheap
    (a handful of indexed queries per project); must never break startup.
    Tests may pass a custom engine.
    """
    from app.db.connection import get_engine

    try:
        with Session(engine or get_engine()) as session:
            service = PortfolioService(session)
            projects = service._all_projects()
            for project in projects:
                service.compute_portfolio_score(project)
        logger.info("Portfolio scores refreshed for %d project(s)", len(projects))
    except Exception:  # noqa: BLE001 — startup must survive a scoring hiccup
        logger.exception("Portfolio score refresh failed")
