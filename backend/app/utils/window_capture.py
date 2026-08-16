"""Windows window targeting for screenshots (Tier 4, v1.17.12.3).

Finds the top-level window owned by a process whose executable lives under
the project directory, so tester screenshots capture the app's window
instead of the whole desktop. Headless apps (no window) yield None and the
caller falls back to a full-screen grab.

Stdlib only (ctypes) — no new dependencies. Matching is by executable path
prefix (casefold), never by window title (titles are user-facing and
unstable). A window's process OR any of its ancestors up to a bounded depth
may match — launchers re-exec into a different interpreter (AG's tkinter GUI
is re-spawned by its venv python into the base interpreter, so the window
process's own exe lives under AppData, not the project). The largest
matching window wins (Electron apps can own several).

Window content is rendered with PrintWindow (PW_RENDERFULLCONTENT), so an
occluded window is captured as its own content, not whatever is stacked
above it — no focus stealing, no z-order changes (Rule 2). Known honest
limitation: some GPU-composited windows render a blank black frame; the
blank check rejects those and the caller falls back to a screen crop.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path

from PIL import Image

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_ANCESTOR_DEPTH = 6
PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0
BLANK_FRAME_THRESHOLD = 0.99

_WindowRect = tuple[int, int, int, int]

_WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

TH32CS_SNAPPROCESS = 0x00000002


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", ctypes.wintypes.DWORD * 3),
    ]


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
kernel32.CreateToolhelp32Snapshot.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
]
kernel32.CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(_PROCESSENTRY32W),
]
kernel32.Process32FirstW.restype = ctypes.c_bool
kernel32.Process32NextW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(_PROCESSENTRY32W),
]
kernel32.Process32NextW.restype = ctypes.c_bool

user32.GetWindowDC.argtypes = [ctypes.wintypes.HWND]
user32.GetWindowDC.restype = ctypes.wintypes.HDC
user32.ReleaseDC.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.PrintWindow.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.wintypes.HDC,
    ctypes.wintypes.UINT,
]
user32.PrintWindow.restype = ctypes.c_bool

gdi32.CreateCompatibleDC.argtypes = [ctypes.wintypes.HDC]
gdi32.CreateCompatibleDC.restype = ctypes.wintypes.HDC
gdi32.DeleteDC.argtypes = [ctypes.wintypes.HDC]
gdi32.DeleteDC.restype = ctypes.c_bool
gdi32.CreateCompatibleBitmap.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.CreateCompatibleBitmap.restype = ctypes.wintypes.HBITMAP
gdi32.SelectObject.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HGDIOBJ]
gdi32.SelectObject.restype = ctypes.wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [ctypes.wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = ctypes.c_bool
gdi32.GetDIBits.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.wintypes.HBITMAP,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(_BITMAPINFO),
    ctypes.wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int


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


def _process_snapshot() -> dict[int, tuple[int, str | None]]:
    """One Toolhelp snapshot: pid -> (parent_pid, exe path|None)."""
    tree: dict[int, tuple[int, str | None]] = {}
    handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle == ctypes.c_void_p(-1).value:
        return tree
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if kernel32.Process32FirstW(handle, ctypes.byref(entry)):
            while True:
                tree[entry.th32ProcessID] = (entry.th32ParentProcessID, None)
                if not kernel32.Process32NextW(handle, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(handle)
    for pid in list(tree):
        exe = _process_exe_path(pid)
        if exe:
            tree[pid] = (tree[pid][0], exe)
    return tree


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


def _descends_from(
    pid: int, root: str, tree: dict[int, tuple[int, str | None]]
) -> bool:
    """True when the process or any bounded ancestor's exe starts with root."""
    root = root.casefold()
    for _ in range(MAX_ANCESTOR_DEPTH + 1):
        entry = tree.get(pid)
        if entry is None:
            return False
        exe = entry[1]
        if exe and exe.casefold().startswith(root):
            return True
        pid = entry[0]
    return False


def _is_blank(image: Image.Image) -> bool:
    """True when the render is effectively all black (blank-frame failure)."""
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    if total == 0:
        return True
    return histogram[0] / total > BLANK_FRAME_THRESHOLD


def capture_window_content(hwnd: int, rect: _WindowRect) -> Image.Image | None:
    """Render the window's own content via PrintWindow (PW_RENDERFULLCONTENT),
    even when the window is occluded. Returns None when the render fails or
    comes back blank (some GPU-composited windows) — the caller then falls
    back to a screen crop of the rect."""
    left, top, right, bottom = rect
    width = max(1, right - left)
    height = max(1, bottom - top)
    hdc = user32.GetWindowDC(hwnd)
    if not hdc:
        return None
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    old_bitmap = gdi32.SelectObject(mem_dc, hbitmap)
    try:
        if not user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT):
            return None
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down rows
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB
        buffer = ctypes.create_string_buffer(width * height * 4)
        got = gdi32.GetDIBits(
            mem_dc,
            hbitmap,
            0,
            height,
            buffer,
            ctypes.byref(info),
            DIB_RGB_COLORS,
        )
        if not got:
            return None
        image = Image.frombytes("RGB", (width, height), buffer.raw, "raw", "BGRX")
        if _is_blank(image):
            return None
        return image
    finally:
        gdi32.SelectObject(mem_dc, old_bitmap)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hdc)


def find_project_window(project_path: str) -> tuple[int, _WindowRect] | None:
    """(hwnd, rect) of the largest visible, non-minimized top-level window
    whose process (or bounded ancestor chain) executable lives under
    `project_path` (casefold prefix). Returns None when no such window exists
    (headless app, app closed)."""
    root = str(Path(project_path).resolve()).casefold()
    tree = _process_snapshot()
    windows: list[tuple[int, int, _WindowRect]] = []

    @_WNDENUMPROC
    def _enum(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _descends_from(pid.value, root, tree):
            rect = _window_rect(hwnd)
            if rect and _area(rect) > 0:
                windows.append((_area(rect), hwnd, rect))
        return True

    user32.EnumWindows(_enum, 0)
    if not windows:
        return None
    windows.sort(reverse=True)
    return windows[0][1], windows[0][2]
