"""Packaged-app launcher detection (v1.17.13.5).

Finds the packaged desktop app binary a project ships, so tester runs can
auto-launch the real app and capture its window without per-tester code.
Deterministic scan only — no AI (Rule 3):

- electron-builder layouts: `release/win-unpacked/*.exe` (WorkFlow-Toolkit)
  and `dist/win-unpacked/*.exe` (TV-Scheduler)
- tauri layouts (future — Sentinel is the only tauri app, deferred):
  `out/*.exe` and `src-tauri/target/release/*.exe`
- noise excluded by name: installers (`Setup`, `*.blockmap`), `elevate.exe`,
  and bundled python helpers (`python*.exe`, `venv*`)

PyInstaller `dist/` folders are deliberately NOT scanned: the payload name
is ambiguous (`app.exe` launchers, helper binaries) and browser-served apps
capture via headless renders anyway (v1.17.13.5 decision, live review).
"""

import re
from pathlib import Path

NOISE = re.compile(
    r"(?i)setup|\.blockmap$|^elevate\.exe$|^pythonw?\.exe$|^venv\w*\.exe$"
)

_LAYOUTS: tuple[tuple[str, ...], ...] = (
    ("release", "win-unpacked"),
    ("dist", "win-unpacked"),
    ("out",),
    ("src-tauri", "target", "release"),
)


def find_packaged_launcher(project_path: str | Path) -> Path | None:
    """Path of the packaged app exe, or None when the project ships none.

    Layouts are probed in a fixed order (win-unpacked preferred); inside a
    layout the exes are sorted alphabetically and the first non-noise match
    wins. Never raises — a missing or unreadable tree is just no launcher.
    """
    root = Path(project_path)
    for parts in _LAYOUTS:
        directory = root.joinpath(*parts)
        if not directory.is_dir():
            continue
        try:
            exes = sorted(
                p for p in directory.glob("*.exe") if not NOISE.search(p.name)
            )
        except OSError:
            continue
        if exes:
            return exes[0]
    return None
