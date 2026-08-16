"""Windows window targeting for screenshots (Tier 4, v1.17.12.3).

Finds the top-level window owned by a process whose executable lives under
the project directory, so tester screenshots capture the app's window
instead of the whole desktop. Headless apps (no window) yield None and the
caller falls back to a full-screen grab.

Stdlib only (ctypes) — no new dependencies. Matching is by executable path
prefix (casefold), never by window title (titles are user-facing and
unstable). The largest matching window wins (Electron apps can own several).

Known honest limitation: the capture is a screen crop, so a window occluded
by other windows captures whatever is stacked above it. PrintWindow would
capture behind windows but frequently returns black frames for GPU-rendered
windows (Electron), so it is intentionally not used.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_WindowRect = tuple[int, int, int, int]

_WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

user32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.wintypes.LPARAM]
user32.EnumWindows.restype = ctypes.c_bool
user32.GetWindowRect.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.wintypes.RECT),
]
user32.GetWindowRect.restype = ctypes.c_bool
user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
user32.IsIconic.restype = ctypes.c_bool
user32.GetWindowThreadProcessId.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

kernel32.OpenProcess.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.c_bool,
    ctypes.wintypes.DWORD,
]
kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.LPWSTR,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool
kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
kernel32.CloseHandle.restype = ctypes.c_bool


def _process_exe_path(pid: int) -> str | None:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = ctypes.wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(32768)
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _window_rect(hwnd: int) -> _WindowRect | None:
    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def _area(rect: _WindowRect) -> int:
    left, top, right, bottom = rect
    return max(0, right - left) * max(0, bottom - top)


def _virtual_screen() -> _WindowRect:
    """Virtual-screen bounds (all monitors) in pixel coordinates."""
    return (
        user32.GetSystemMetrics(76),  # SM_XVIRTUALSCREEN
        user32.GetSystemMetrics(77),  # SM_YVIRTUALSCREEN
        user32.GetSystemMetrics(76) + user32.GetSystemMetrics(78),  # X + CX
        user32.GetSystemMetrics(77) + user32.GetSystemMetrics(79),  # Y + CY
    )


def find_project_window(project_path: str) -> _WindowRect | None:
    """Bounding rect of the largest visible, non-minimized top-level window
    whose process executable lives under `project_path` (casefold prefix).
    Returns None when no such window exists (headless app, app closed)."""
    root = str(Path(project_path).resolve()).casefold()
    windows: list[tuple[int, _WindowRect]] = []

    @_WNDENUMPROC
    def _enum(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = _process_exe_path(pid.value)
        if exe and exe.casefold().startswith(root):
            rect = _window_rect(hwnd)
            if rect and _area(rect) > 0:
                windows.append((_area(rect), rect))
        return True

    user32.EnumWindows(_enum, 0)
    if not windows:
        return None
    windows.sort(reverse=True)
    return windows[0][1]
