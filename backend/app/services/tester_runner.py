"""Tester runner — executes a project's scripted tester as a session
(later.md Tier 2, docs/tier2_plan.md).

Resolution order (deterministic):
1. custom tester keyed by project slug (backend/app/testers/*.py)
2. default smoke tester when the project has a startup command
3. no tester (API reports "No tester"; the button stays disabled)

A run auto-creates an AppSession ("Tester: <name>"), executes the steps
(each a checkpoint), and ends it with a status:
- passed: every step asserted
- failed: a TesterAssertionError (an expected value did not match)
- investigate: TesterEnvError / TesterTimeoutError (launch, port, env)
Screenshots: the auto-capture at end always fires; testers may capture
more. Runs are always user-initiated (Rule 2) and never call AI (Rule 3).
"""

from app.core.logging import get_logger
from app.services.app_sessions import AppSessionService, _slug
from app.services.build_runner import BuildRunner
from app.testers import DEFAULT_SMOKE, TESTERS, Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)

logger = get_logger(__name__)


class TesterUnavailableError(Exception):
    """No tester exists for this project."""


class TesterRunner:
    """One responsibility: resolve + run a project's tester as a session."""

    def __init__(self, session):
        self.session = session

    def resolve(self, project) -> Tester | None:
        custom = TESTERS.get(_slug(project.name))
        if custom is not None:
            return custom
        commands = project.stack.get("commands") if project.stack else None
        startup = (commands or {}).get("startup") or ""
        if not startup:
            commands = BuildRunner(self.session).discover_commands(project.path)
            startup = (commands or {}).get("startup") or ""
        if startup:
            return DEFAULT_SMOKE
        return None

    def describe(self, project) -> dict | None:
        tester = self.resolve(project)
        if tester is None:
            return None
        return {
            "name": tester.name,
            "description": tester.description,
            "kind": tester.kind,
        }

    def run(self, project) -> object:
        tester = self.resolve(project)
        if tester is None:
            raise TesterUnavailableError(f"No tester for {project.name}")
        service = AppSessionService(self.session)
        app_session = service.start(
            project.id, f"Tester: {tester.name}", tester.description
        )
        ctx = TesterContext(project, app_session.id, service)
        try:
            tester.run(ctx)
            outcome = f"All {ctx.steps} step(s) passed"
            status = "passed"
        except TesterAssertionError as exc:
            outcome = str(exc)
            status = "failed"
        except (TesterEnvError, TesterTimeoutError) as exc:
            outcome = str(exc)
            status = "investigate"
        except Exception as exc:  # noqa: BLE001 — a tester must never crash the job
            logger.exception("Tester %s crashed", tester.name)
            outcome = f"Tester crashed: {exc!r}"
            status = "failed"
        service.end(app_session.id, outcome, status)
        logger.info("Tester %r for %s -> %s", tester.name, project.name, status)
        return app_session
