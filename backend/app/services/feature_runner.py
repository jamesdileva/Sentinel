"""Feature runner — executes a project's UI click-through features
(docs/clickthrough_plan.md, v1.17.14.0; Electron engine v1.17.14.4).

Runs after the smoke tester passes, inside the same user-initiated tester
session. Two engines, chosen per feature:

- Browser: the system Microsoft Edge via Playwright's msedge channel (no
  browser download; consistent with headless_render). Headless by default;
  SENTINEL_FEATURES_HEADED=1 opts into a visible window for debugging.
- Electron (v1.17.14.4): the project's packaged desktop app window, driven
  through Playwright's CDP attach. Playwright 1.62's python package ships
  no `p.electron` wrapper (driver has it, wrapper doesn't), so the engine
  launches the packaged exe with `--remote-debugging-port=<free>` and
  `--user-data-dir=<temp sandbox>` and connects over CDP — no new
  dependency, same Page API for features.

Electron hard guarantees (Rule 1 + plan):
- the sandboxed instance runs with a fresh userData dir; the user's real
  app state is never touched (verified by sandbox artifact checks)
- the auto-launched presence instance (tester phase) is reclaimed first
  (frees TV-Scheduler's hard-coded :3050)
- the attached window's URL must be file:// or a loopback host — anything
  else is TesterEnvError
- the spawned process tree is killed on exit (self-created entities)

Failure mapping (same semantics as tester_runner):
- TesterAssertionError (incl. Playwright timeouts/errors translated) -> failed
- TesterEnvError (browser launch, missing Edge/launcher, loopback guard,
  sandbox violation) -> investigate
- TesterTimeoutError (feature budget) -> investigate
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.core.logging import get_logger
from app.services.app_sessions import _slug
from app.services.launcher_detect import find_packaged_launcher
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)
from app.testers.features import FEATURES, Feature
from app.testers.features._context import FeatureContext

logger = get_logger(__name__)

DEFAULT_TIMEOUT_MS = 15_000
VIEWPORT = {"width": 1280, "height": 800}

# Electron engine (v1.17.14.4)
ELECTRON_CONNECT_MAX_S = 30  # wait for the CDP endpoint + window target
ELECTRON_RECLAIM_MAX_S = 20  # wait for a reclaimed instance to actually die
ELECTRON_SANDBOX_BOOTSTRAP_S = 20  # wait for the sandbox to gain any file
ELECTRON_SANDBOX_STATE_S = 20  # wait for the app's own state artifact

LOOPBACK_PREFIXES = ("file://", "http://127.0.0.1", "http://localhost")


def _headed() -> bool:
    return os.environ.get("SENTINEL_FEATURES_HEADED", "").strip() not in ("", "0")


def _free_port() -> int:
    """A free loopback port (bind :0, release, return). Not reserved —
    re-checked implicitly by launch failures downstream."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _reclaim_packaged(launcher: Path) -> None:
    """Best-effort taskkill of previously auto-launched packaged instances
    (tester phase) so their ports/state do not collide with the sandboxed
    launch. The instance was launched by this session — reclaiming it is
    cleanup of self-created entities (plan: port strategy).

    A single taskkill can miss a mid-startup instance (live-fix 2026-08-18:
    the auto-launched TV-Scheduler instance survived the first kill and
    kept :3050, so the sandboxed backend hit EADDRINUSE and the app quit),
    so the image is re-checked via tasklist and the kill is retried within
    a bounded window; an instance that outlives it is a TesterEnvError —
    the run fails honestly instead of colliding on the port."""
    deadline = time.monotonic() + ELECTRON_RECLAIM_MAX_S
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {launcher.name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        still_alive = bool(
            result
            and result.returncode == 0
            and launcher.name.lower() in result.stdout.lower()
        )
        if not still_alive:
            return
        try:
            subprocess.run(
                # image name raw (no embedded quotes — list-form argv is not
                # shell-parsed; quoting the name made taskkill match nothing)
                ["taskkill", "/IM", launcher.name, "/F"],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            logger.warning("Reclaim taskkill failed for %s", launcher.name)
        time.sleep(2)
    raise TesterEnvError(
        f"packaged app {launcher.name!r} still running after reclaim "
        f"({ELECTRON_RECLAIM_MAX_S}s) — cannot launch the sandboxed instance"
    )


def _spawn_packaged(launcher: Path, port: int, sandbox: Path) -> subprocess.Popen:
    """Launch the packaged exe with the CDP port + sandboxed userData dir."""
    return subprocess.Popen(
        [
            str(launcher),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={sandbox}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _match_window_target(targets) -> str | None:
    """The window page target among a CDP /json/list payload — file:// or a
    loopback-host URL only (Rule 1); anything else (devtools, remote hosts)
    is never matched."""
    for target in targets:
        if target.get("type") != "page":
            continue
        url = target.get("url", "")
        if url.startswith(LOOPBACK_PREFIXES):
            return url
    return None


def _connect_cdp(p, port: int, launcher: Path):
    """Poll the CDP endpoint until the app's window page target appears,
    then attach and return the page. Honest TesterEnvError when the app
    never opens (crash, port conflict, stale binary)."""
    target_url = None
    deadline = time.monotonic() + ELECTRON_CONNECT_MAX_S
    while time.monotonic() < deadline:
        try:
            targets = httpx.get(f"http://127.0.0.1:{port}/json/list", timeout=3).json()
        except (httpx.HTTPError, ValueError):
            targets = []
        target_url = _match_window_target(targets)
        if target_url is not None:
            break
        time.sleep(1)
    if target_url is None:
        raise TesterEnvError(
            f"Packaged app {launcher.name!r} did not open a window within "
            f"{ELECTRON_CONNECT_MAX_S}s (CDP port {port})"
        )
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    for page in browser.contexts[0].pages:
        if page.url == target_url:
            return page
    raise TesterEnvError(
        f"Packaged app window page not found after CDP attach ({target_url})"
    )


def _verify_sandbox(sandbox: Path, launcher: Path) -> None:
    """Prove the app honored `--user-data-dir` (Rule 1): the sandbox must
    gain Chromium profile files, then the app's own state artifact
    (tv_scheduler.db / data dir / backend.log). An empty sandbox means the
    app wrote its real userData instead — TesterEnvError."""
    deadline = time.monotonic() + ELECTRON_SANDBOX_BOOTSTRAP_S
    while time.monotonic() < deadline:
        if any(sandbox.iterdir()):
            break
        time.sleep(1)
    else:
        raise TesterEnvError(
            f"Sandbox {sandbox} stayed empty after launch — the packaged "
            f"app ignored --user-data-dir (Rule 1 violation)"
        )
    deadline = time.monotonic() + ELECTRON_SANDBOX_STATE_S
    while time.monotonic() < deadline:
        for entry in sandbox.rglob("*"):
            if entry.name in ("tv_scheduler.db", "backend.log"):
                return
            if entry.is_dir() and entry.name == "data":
                return
        time.sleep(1)
    raise TesterEnvError(
        f"Packaged app initialized no state inside the sandbox {sandbox}"
    )


def _terminate_packaged(proc) -> None:
    """Taskkill the spawned process tree (self-created; the CDP attach is
    non-owning, so closing the browser does not stop the app)."""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        logger.warning("Cleanup taskkill failed for pid %s", proc.pid)


class FeatureRunner:
    """One responsibility: resolve + run a project's click-through features."""

    def __init__(self, session):
        self.session = session

    def resolve(self, project) -> list[Feature]:
        return FEATURES.get(_slug(project.name), [])

    def describe(self, project) -> list[dict]:
        return [
            {"name": f.name, "description": f.description}
            for f in self.resolve(project)
        ]

    def run(self, project, ctx: TesterContext, service, session_id: str) -> None:
        features = self.resolve(project)
        if not features:
            return
        try:
            with sync_playwright() as p:
                if any(f.electron for f in features):
                    self._run_electron(p, project, ctx, service, session_id, features)
                else:
                    self._run_browser(p, ctx, service, session_id, features)
        except PlaywrightError as exc:
            raise TesterEnvError(f"Feature run failed: {exc}") from exc

    # ------------------------------------------------------------- browser

    def _run_browser(
        self, p, ctx: TesterContext, service, session_id: str, features
    ) -> None:
        try:
            browser = p.chromium.launch(channel="msedge", headless=not _headed())
        except PlaywrightError as exc:
            raise TesterEnvError(f"Feature browser launch failed: {exc}") from exc
        page = browser.new_page(viewport=VIEWPORT)
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        try:
            self._run_features(features, ctx, service, session_id, page)
        finally:
            browser.close()

    # ------------------------------------------------------------ electron

    def _run_electron(
        self, p, project, ctx: TesterContext, service, session_id: str, features
    ) -> None:
        launcher = find_packaged_launcher(project.path)
        if launcher is None:
            raise TesterEnvError(
                f"{project.name} ships no packaged launcher — cannot run "
                f"electron features"
            )
        _reclaim_packaged(launcher)
        sandbox = Path(tempfile.mkdtemp(prefix="sentinel-feature-sandbox-"))
        port = _free_port()
        proc = _spawn_packaged(launcher, port, sandbox)
        try:
            page = _connect_cdp(p, port, launcher)
            _verify_sandbox(sandbox, launcher)
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)
            self._run_features(features, ctx, service, session_id, page)
        finally:
            _terminate_packaged(proc)
            shutil.rmtree(sandbox, ignore_errors=True)

    # ------------------------------------------------------------- common

    def _run_features(
        self, features, ctx: TesterContext, service, session_id: str, page
    ) -> None:
        for feature in features:
            ctx.checkpoint(f"feature start: {feature.name}")
            fctx = FeatureContext(
                ctx.project,
                session_id,
                service,
                ctx,
                page,
                electron=feature.electron,
                budget_s=feature.budget_s,
            )
            try:
                feature.run(fctx)
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                raise TesterAssertionError(
                    f"feature {feature.name!r} failed: {exc}"
                ) from exc
            ctx.checkpoint(f"feature pass: {feature.name}")
