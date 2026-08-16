"""Headless browser rendering for screenshot captures (v1.17.13.1).

Browser-served apps (Demake's Phaser game, Sentinel's own dashboard) have no
standalone window, so the window matcher falls back to a full-screen grab of
the user's desktop — not the app. `render_url()` renders a URL in headless
Microsoft Edge and saves the frame as a PNG, deterministically and without
touching the desktop (Rule 3: no AI, just a bounded subprocess).

Edge resolves via the standard install path, then PATH (`msedge`). The render
is bounded by a subprocess timeout; failures raise `HeadlessRenderError` so
testers surface a deterministic `investigate`/`failed` instead of hanging.
"""

import shutil
import subprocess
from pathlib import Path

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

WINDOW_SIZE = "1280,800"
VIRTUAL_TIME_BUDGET_MS = 15000


class HeadlessRenderError(Exception):
    """The headless render failed (missing browser, non-zero exit, timeout)."""


def find_edge() -> str:
    """Resolve the Edge executable: known install paths, then PATH."""
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("msedge")
    if found:
        return found
    raise HeadlessRenderError("Microsoft Edge not found on this machine")


def render_url(url: str, out_path: str, timeout_s: int = 90) -> str:
    """Render `url` in headless Edge and save the frame to `out_path`.

    Returns `out_path` on success. Raises `HeadlessRenderError` when Edge is
    missing, the render exits non-zero, or no PNG is produced.
    """
    browser = find_edge()
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--screenshot={out_path}",
        f"--window-size={WINDOW_SIZE}",
        f"--virtual-time-budget={VIRTUAL_TIME_BUDGET_MS}",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise HeadlessRenderError(
            f"headless render timed out after {timeout_s}s for {url}"
        ) from exc
    if result.returncode != 0:
        raise HeadlessRenderError(
            f"headless render exited {result.returncode} for {url}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    if not Path(out_path).exists() or Path(out_path).stat().st_size == 0:
        raise HeadlessRenderError(f"headless render produced no output for {url}")
    return out_path
