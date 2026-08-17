"""Session recorder + screenshot capture (later.md Tier 1 + Tier 4).

Sessions are recorded by appending `[sentinel]` markers to the app's own
log (data/logs/apps/<slug>.log — the same file launched apps append their
output to), so provenance is one deterministic file. The log slice between
a session's own start and end markers is captured at `end()`.

Screenshots are grabs stored under data/screenshots/<slug>/ with a 90x60
thumbnail next to each PNG. Since v1.17.12.3 the grab is window-targeted:
when the app under test owns a visible window (matched by executable path
under the project dir), only that window's rect is captured; since v1.17.13.2
a session with no window records nothing (browser-served apps register
headless-render frames from their tester instead of a desktop grab). Capture
is user-initiated or auto on session end (Rule 2: Sentinel never presses
buttons itself — the user drives the app, the recorder only watches).
"""

import datetime
import re
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageGrab
from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    AppSession,
    Project,
    SessionCheckpoint,
    SessionScreenshot,
    SessionStatus,
)
from app.repositories import (
    ProjectRepository,
    SessionCheckpointRepository,
    SessionRepository,
    SessionScreenshotRepository,
    TriageAnalysisRepository,
)
from app.utils.window_capture import (
    _virtual_screen,
    capture_window_content,
    find_project_window,
)

logger = get_logger(__name__)

MARKER_START = "[sentinel] Session started"
MARKER_CHECKPOINT = "[sentinel] checkpoint:"
MARKER_END = "[sentinel] Session ended"

THUMB_SIZE = (90, 60)


def _clamp_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    """Window rect clamped to the virtual screen, or None when disjoint."""
    left, top, right, bottom = rect
    virtual = _virtual_screen()
    left = max(left, virtual[0])
    top = max(top, virtual[1])
    right = min(right, virtual[2])
    bottom = min(bottom, virtual[3])
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name.strip()) or "project"


def _apps_dir() -> Path:
    return Path(settings.db_path).parent.parent / "logs" / "apps"


def _screenshots_dir() -> Path:
    return Path(settings.db_path).parent.parent / "screenshots"


def _stamp(marker: str) -> str:
    return f"{marker} {datetime.datetime.now().isoformat(timespec='seconds')}"


class AppSessionService:
    """One responsibility (Rule 4): record sessions and capture screenshots."""

    def __init__(self, session: Session):
        self.session = session
        self.repo = SessionRepository(session)
        self.checkpoint_repo = SessionCheckpointRepository(session)
        self.screenshot_repo = SessionScreenshotRepository(session)

    # ------------------------------------------------------------------ logs

    def _log_path(self, project: Project) -> Path:
        return _apps_dir() / f"{_slug(project.name)}.log"

    def _append_log(self, project: Project, line: str) -> None:
        path = self._log_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{line}\n")

    def _log_lines(self, project: Project) -> list[str]:
        path = self._log_path(project)
        if not path.exists():
            return []
        # Child processes write the log with their own locale encoding
        # (cp1252 on this machine), so tolerate non-UTF-8 bytes — the slice
        # keeps every line, unknown bytes become U+FFFD (v1.17.11.0 bugfix:
        # end() crashed with UnicodeDecodeError and left the session running).
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()

    def _slice_for(self, project: Project, session_id: str) -> str:
        """Deterministic slice of the app log between this session's markers.

        The slice runs from the session's own start marker to its own end
        marker (inclusive); an unfinished session slices to EOF. Lines
        belonging to other, interleaved sessions that fall inside this range
        stay in the slice — that is exactly what the log contains between the
        markers, and the slice is reproducible byte-for-byte.
        """
        lines = self._log_lines(project)
        start_marker = "[sentinel] Session started "
        end_marker = "[sentinel] Session ended "
        # Marker lines look like `... started <iso> <session_id>: <title>` —
        # the timestamp sits between the marker word and the id, so match on
        # the trailing ` <id>:` fragment within marker-prefixed lines.
        token = f" {session_id}:"
        start_idx = next(
            (
                i
                for i, line in enumerate(lines)
                if line.startswith(start_marker) and token in line
            ),
            None,
        )
        if start_idx is None:
            return ""
        end_idx = next(
            (
                i
                for i in range(start_idx + 1, len(lines))
                if lines[i].startswith(end_marker) and token in lines[i]
            ),
            None,
        )
        end = end_idx + 1 if end_idx is not None else len(lines)
        return "\n".join(lines[start_idx:end])

    # ------------------------------------------------------------- lifecycle

    def start(
        self, project_id: str, title: str, expected_output: str | None = None
    ) -> AppSession:
        project = ProjectRepository(self.session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        app_session = AppSession(
            project_id=project_id,
            title=title,
            expected_output=expected_output,
        )
        self.repo.add(app_session)
        self.session.commit()
        self.session.refresh(app_session)
        self._append_log(
            project,
            f"{_stamp(MARKER_START)} {app_session.id}: {title}",
        )
        return app_session

    def checkpoint(self, session_id: str, label: str) -> SessionCheckpoint:
        app_session = self._get(session_id)
        checkpoint = SessionCheckpoint(session_id=session_id, label=label)
        self.checkpoint_repo.add(checkpoint)
        self.session.commit()
        project = ProjectRepository(self.session).get(app_session.project_id)
        self._append_log(
            project,
            f"{_stamp(MARKER_CHECKPOINT)} {session_id}: {label}",
        )
        return checkpoint

    def end(
        self, session_id: str, actual_outcome: str | None, status: str
    ) -> AppSession:
        app_session = self._get(session_id)
        app_session.status = SessionStatus(status)
        app_session.actual_outcome = actual_outcome
        app_session.ended_at = datetime.datetime.now(datetime.timezone.utc)
        project = ProjectRepository(self.session).get(app_session.project_id)
        self._append_log(
            project,
            f"{_stamp(MARKER_END)} {session_id}: {status}",
        )
        app_session.log_slice = self._slice_for(project, session_id)
        self.session.add(app_session)
        self.session.commit()
        self.session.refresh(app_session)
        # Tier 4: auto-capture on session end so every session has a record
        # even when the user never pressed Capture (Rule 2: capture, not act).
        try:
            self.capture(session_id)
        except Exception:  # noqa: BLE001 — a failed auto-shot must not lose the session
            logger.warning(
                "Auto-capture failed for session %s", session_id, exc_info=True
            )
        return app_session

    # ------------------------------------------------------------ screenshots

    def capture(
        self, session_id: str, checkpoint_id: str | None = None
    ) -> SessionScreenshot | None:
        """Window-targeted grab → data/screenshots/<slug>/<iso>.png + thumb.

        v1.17.12.3: when the app under test owns a visible window (matched by
        the window process's executable path under the project dir), the
        window's own content is rendered via PrintWindow (PW_RENDERFULLCONTENT)
        — occluded windows capture their own content, not what's stacked above
        them. Blank frames (some GPU-composited windows) and rects outside the
        virtual screen fall back to a screen crop of the clamped rect.

        v1.17.13.2: the full-screen fallback is gone. A real app is either
        window-capturable (Electron, tkinter, native) or browser-served and
        registered by its tester via a headless render — grabbing whatever the
        user happens to have on screen is noise (it caught Reddit and VS Code
        during live demake runs), so a session with no project window returns
        None and records nothing.
        """
        app_session = self._get(session_id)
        project = ProjectRepository(self.session).get(app_session.project_id)
        window = find_project_window(project.path)
        if window is None:
            logger.info(
                "Skipping screenshot for session %s: no window owned by %s",
                session_id,
                project.name,
            )
            return None
        hwnd, rect = window
        bbox = _clamp_rect(rect)
        if bbox is None:
            logger.info(
                "Skipping screenshot for session %s: window off-screen", session_id
            )
            return None
        rendered = capture_window_content(hwnd, bbox)
        if rendered is not None:
            image = rendered
            method = "window-render"
        else:
            image = ImageGrab.grab(bbox=bbox)
            method = "window-crop"
        return self._save_image(image, project, session_id, checkpoint_id, method)

    def _save_image(
        self,
        image: Image.Image,
        project: Project,
        session_id: str,
        checkpoint_id: str | None,
        method: str,
    ) -> SessionScreenshot:
        """Persist a PIL image as <slug>/<iso>.png + thumb and register it."""
        shot_dir = _screenshots_dir() / _slug(project.name)
        shot_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        full_path = shot_dir / f"{stem}.png"
        thumb_path = shot_dir / f"{stem}.thumb.png"
        image.save(full_path, "PNG")
        thumb = image.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(thumb_path, "PNG")
        screenshot = SessionScreenshot(
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            path=full_path.name,
        )
        self.screenshot_repo.add(screenshot)
        self.session.commit()
        self.session.refresh(screenshot)
        logger.info(
            "Captured screenshot %s for session %s (%s)",
            full_path,
            session_id,
            method,
        )
        return screenshot

    def register_screenshot(
        self,
        session_id: str,
        png_path: str | Path,
        checkpoint_id: str | None = None,
    ) -> SessionScreenshot:
        """Register a pre-rendered PNG (e.g. a headless browser render) as a
        session screenshot — v1.17.13.1, for browser-served apps whose UI has
        no window to capture. Copies the PNG into data/screenshots/<slug>/
        with a thumbnail and adds the DB row; a missing source raises
        FileNotFoundError (the tester's error mapping surfaces it as
        investigate)."""
        app_session = self._get(session_id)
        project = ProjectRepository(self.session).get(app_session.project_id)
        source = Path(png_path)
        if not source.exists() or source.stat().st_size == 0:
            raise FileNotFoundError(f"Screenshot source missing: {source}")
        with Image.open(source) as im:
            image = im.convert("RGB")
        return self._save_image(
            image, project, session_id, checkpoint_id, "headless-render"
        )

    # ---------------------------------------------------------------- queries

    def _get(self, session_id: str) -> AppSession:
        app_session = self.repo.get(session_id)
        if app_session is None:
            raise ValueError(f"Unknown session: {session_id}")
        return app_session

    def get(self, session_id: str) -> AppSession:
        return self._get(session_id)

    def list_sessions(
        self, project_id: str | None = None, status: str | None = None
    ) -> list[AppSession]:
        return self.repo.list_sessions(project_id=project_id, status=status)

    def update(
        self,
        session_id: str,
        *,
        title: str | None = None,
        expected_output: str | None = None,
        actual_outcome: str | None = None,
        status: str | None = None,
    ) -> AppSession:
        app_session = self._get(session_id)
        if title is not None:
            app_session.title = title
        if expected_output is not None:
            app_session.expected_output = expected_output
        if actual_outcome is not None:
            app_session.actual_outcome = actual_outcome
        if status is not None:
            app_session.status = SessionStatus(status)
        self.session.add(app_session)
        self.session.commit()
        self.session.refresh(app_session)
        return app_session

    def delete(self, session_id: str) -> None:
        """Delete the session, its children, and its screenshot files."""
        app_session = self._get(session_id)
        project = ProjectRepository(self.session).get(app_session.project_id)
        shot_dir = _screenshots_dir() / _slug(project.name)
        for screenshot in self.screenshot_repo.by_session(session_id):
            for name in (screenshot.path, f"{Path(screenshot.path).stem}.thumb.png"):
                try:
                    (shot_dir / name).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove screenshot %s", name)
            self.session.delete(screenshot)
        for checkpoint in self.checkpoint_repo.by_session(session_id):
            self.session.delete(checkpoint)
        for analysis in TriageAnalysisRepository(self.session).by_session(session_id):
            self.session.delete(analysis)
        self.session.delete(app_session)
        self.session.commit()

    # ------------------------------------------------------------ portfolio

    def export_to_portfolio(self, session_id: str, screenshot_id: str) -> dict:
        """Copy a screenshot into the portfolio repo and return the card HTML.

        Sentinel never pushes (Rule 2) — the snippet is handed to the user,
        who pastes it into the portfolio's index.html and commits manually.
        """
        app_session = self._get(session_id)
        project = ProjectRepository(self.session).get(app_session.project_id)
        screenshot = self.screenshot_repo.get(screenshot_id)
        if screenshot is None or screenshot.session_id != session_id:
            raise ValueError(f"Unknown screenshot: {screenshot_id}")
        src_dir = _screenshots_dir() / _slug(project.name)
        dst_dir = Path(settings.portfolio_dir) / "images" / "sessions"
        dst_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{_slug(project.name)}-{screenshot.captured_at:%Y%m%d-%H%M%S}"
        full_dst = dst_dir / f"{stem}.png"
        thumb_dst = dst_dir / f"{stem}.thumb.png"
        import shutil

        copied = []
        for src_name, dst in (
            (screenshot.path, full_dst),
            (f"{Path(screenshot.path).stem}.thumb.png", thumb_dst),
        ):
            shutil.copy2(src_dir / src_name, dst)
            copied.append(str(dst))
        rel = f"images/sessions/{full_dst.name}"
        snippet = "\n".join(
            [
                f"<!-- {project.name} — {app_session.title} (auto-generated) -->",
                '<div class="card">',
                f"  <h3>{project.name}</h3>",
                f"  <p>{app_session.title}</p>",
                '  <div class="images">',
                f'    <img src="{rel}" onclick="openModal(this.src)">',
                "  </div>",
                '  <div class="links">',
                f'    <a href="https://github.com/jamesdileva/{quote(project.name)}">View Code</a>',
                "  </div>",
                "</div>",
            ]
        )
        return {"copied": copied, "snippet": snippet}


def resolve_screenshot(session: Session, session_id: str, filename: str) -> Path | None:
    """Resolve a screenshot file for the media route (path-traversal safe)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", filename):
        return None
    app_session = SessionRepository(session).get(session_id)
    if app_session is None:
        return None
    project = ProjectRepository(session).get(app_session.project_id)
    if project is None:
        return None
    root = _screenshots_dir().resolve()
    path = (root / _slug(project.name) / filename).resolve()
    if root not in path.parents:
        return None
    return path if path.exists() else None
