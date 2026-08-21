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

v1.17.13.5: generic app presence. Before the tester runs, the packaged
desktop app (win-unpacked/tauri launcher under the project dir) is
auto-launched when one exists and `Tester.auto_launch` allows it — the
window (when it appears) is captured with a labeled checkpoint, so desktop
apps record their real UI with no per-tester code; a missing launcher or
window is an honest skip, never a failure. After the tester runs, a
browser-served app that declared `web_url` but registered no screenshots
gets one headless render of it auto-registered.
"""

import subprocess
import time
from pathlib import Path

from app.core.logging import get_logger
from app.services.app_sessions import AppSessionService, _slug
from app.services.build_runner import BuildRunner
from app.services.feature_runner import FeatureRunner
from app.services.launcher_detect import find_packaged_launcher
from app.testers import DEFAULT_SMOKE, TESTERS, Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)
from app.utils.window_capture import find_project_window

logger = get_logger(__name__)

WINDOW_WAIT_S = 20


def _kill_tree_best_effort(launcher: Path) -> None:
    """Session-end cleanup (v1.17.14.4 live-fix): the packaged app spawns
    its backend as a separate process tree (WFT's runtime python), so
    killing just the exe leaves an orphan backend holding ports/state for
    the next run — taskkill /T takes the whole tree down."""
    try:
        subprocess.run(
            ["taskkill", "/T", "/IM", launcher.name, "/F"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        logger.warning("Session-end cleanup failed for %s", launcher.name)


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
            "features": FeatureRunner(self.session).describe(project),
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
        launcher: Path | None = None
        outcome = "unknown"
        status = "unknown"
        try:
            launcher = self._auto_launch(project, tester, ctx, service, app_session.id)
            tester.run(ctx)
            self._features(project, ctx, service, app_session.id)
            self._auto_render(project, tester, ctx, service, app_session.id)
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
        finally:
            # v1.17.18.1 (audit A4): end() + process kill in finally so the
            # packaged-app tree is always reaped, even if end() throws.
            service.end(app_session.id, outcome, status)
            if launcher is not None:
                _kill_tree_best_effort(launcher)
        logger.info("Tester %r for %s -> %s", tester.name, project.name, status)
        return app_session

    def _auto_launch(
        self, project, tester: Tester, ctx: TesterContext, service, session_id: str
    ) -> Path | None:
        """v1.17.13.5: launch the project's packaged desktop app (when one
        exists) before the tester runs, and capture its window once it
        appears — desktop apps record their real UI with no per-tester code.
        Non-fatal by design: no launcher or no window is an honest skip.
        Returns the launched launcher (for session-end tree cleanup) or
        None when nothing was launched."""
        if not tester.auto_launch:
            return None
        launcher = find_packaged_launcher(project.path)
        if launcher is None:
            logger.info("Auto-launch for %s: no packaged app found", project.name)
            return None
        launched, detail = BuildRunner._launch_app(project, f'"{launcher}"')
        if not launched:
            logger.warning("Auto-launch for %s failed: %s", project.name, detail)
            return None
        ctx.checkpoint(f"auto-launched packaged app: {launcher.name}")
        window = None
        deadline = time.time() + WINDOW_WAIT_S
        while time.time() < deadline:
            window = find_project_window(project.path)
            if window is not None:
                break
            time.sleep(1)
        if window is None:
            logger.info(
                "Auto-launch for %s: no window within %ss (app may be "
                "headless or failed to open)",
                project.name,
                WINDOW_WAIT_S,
            )
            return launcher
        checkpoint = service.checkpoint(session_id, "app window after auto-launch")
        service.capture(session_id, checkpoint.id)
        return launcher

    def _auto_render(
        self, project, tester: Tester, ctx: TesterContext, service, session_id: str
    ) -> None:
        """v1.17.13.5: a browser-served app that declared `web_url` but
        registered no screenshots gets one headless render of it — every run
        records a visual, zero per-tester code (testers that render
        themselves, like card-game and demake, are deduped)."""
        if not tester.web_url:
            return
        if service.screenshot_repo.by_session(session_id):
            logger.info(
                "Auto-render for %s: tester already registered screenshots",
                project.name,
            )
            return
        ctx.render_and_register(tester.web_url, "headless dashboard render")

    def _features(self, project, ctx: TesterContext, service, session_id: str) -> None:
        """v1.17.14.0: after the smoke tester passes, drive the project's
        UI click-through features (Playwright, loopback-only). Failures map
        through the same Tester*Error semantics as the tester itself."""
        FeatureRunner(self.session).run(project, ctx, service, session_id)
