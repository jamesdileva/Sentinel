"""Desktop engine — drives a project's own native window (docs/
clickthrough_plan.md Phase 3 chunk 1, v1.17.16.0).

Ground-truth correction (2026-08-19, live): tkinter on this machine
(Python 3.11, Tcl/Tk 8.6.15) exposes NO accessibility tree — the Tk
build ships no MSAA/UIA providers (`tk::msaa` is not present), so
pywinauto element-driving by name works only for the app's NATIVE
Win32 dialogs. The tkinter widgets themselves are driven by physical
input (SendInput) at measured, layout-fixed coordinates — the plan's
chunk-2 technique, applied to the fixed 720x680 window.

Hard facts the engine builds on:
- window attach by title against the UIA desktop (works; guarded by the
  feature's declared title pattern — Rule 1 mirror)
- window capture via PrintWindow(PW_RENDERFULLCONTENT|PW_CLIENTONLY) —
  renders the window's own surface, occlusion-independent (plain
  PrintWindow/pywinauto capture_as_image return garbage for this
  window, live-verified)
- tk ignores posted WM_* mouse messages (live-verified) — clicks must be
  real SendInput input, which requires the window at the top of the
  z-order at the cursor position
- SetWindowPos HWND_TOPMOST fails with ERROR_INVALID_WINDOW_HANDLE for
  this window (Windows quirk, live-verified) while BringWindowToTop and
  moves work; foreground rights are enforced by Windows — a busy
  desktop (game/video fullscreen foreground) cannot be overridden
  honestly, so that state is a TesterEnvError (retryable), never a lie
- the AG window is a fixed 720x680 tk window with a deterministic
  layout; click targets are measured constants (2026-08-19) and are
  self-verifying through their effects (the file dialog appears; the
  status region repaints)

Failure mapping (same semantics as feature_runner):
- element/dialog not found, region never changes -> TesterAssertionError
- window gone, foreground unobtainable (busy desktop), capture failure
  -> TesterEnvError (investigate / retry)
- per-feature budget -> TesterTimeoutError (investigate)
"""

import ctypes
import re
import time
from pathlib import Path

from PIL import Image

from app.testers._helpers import (
    TesterAssertionError,
    TesterEnvError,
    TesterTimeoutError,
)

CONNECT_MAX_S = 30  # wait for the app window to appear
FOREGROUND_MAX_S = 6  # bring-to-front attempts before an honest env error
DIALOG_WAIT_S = 15  # wait for a native dialog to open

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

USER32 = ctypes.WinDLL("user32", use_last_error=True)
K32 = ctypes.windll.kernel32
# Dedicated gdi32 instance: ctypes.windll.gdi32 is shared process-wide and
# app/utils/window_capture.py sets GetDIBits argtypes on it (its own
# BITMAPINFO class) — a pointer to OUR struct would be rejected.
GDI32 = ctypes.WinDLL("gdi32")


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _Input(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [("mi", _MouseInput), ("ki", _KeybdInput)]

    _fields_ = [("type", ctypes.wintypes.DWORD), ("u", _Union)]


def _send_physical_click(screen_x: int, screen_y: int) -> None:
    """Real hardware-queue input (tk processes SendInput clicks; it
    ignores posted WM_* messages — live-verified)."""
    width = USER32.GetSystemMetrics(0)
    height = USER32.GetSystemMetrics(1)

    def _send(flags: int) -> None:
        inp = _Input()
        inp.type = 0  # INPUT_MOUSE
        inp.u.mi = _MouseInput(
            int(screen_x * 65536 / width),
            int(screen_y * 65536 / height),
            0,
            flags | 0x8000,  # MOUSEEVENTF_ABSOLUTE
            0,
            None,
        )
        USER32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_Input))

    _send(0x0001)  # MOUSEEVENTF_MOVE
    time.sleep(0.2)
    _send(0x0002)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.1)
    _send(0x0004)  # MOUSEEVENTF_LEFTUP


# Keyboard: VK map for the characters a path/file name can contain (US
# layout). The native dialogs are driven by keystrokes — their File name
# box lives inside a DirectUIHWND that the win32 backend cannot reach.
VK_SPACE = 0x20
VK_RETURN = 0x0D
VK_LSHIFT = 0xA0
VK_OEM_1 = 0xBA  # ; / :
VK_OEM_PLUS = 0xBB  # = / +
VK_OEM_COMMA = 0xBC  # , / <
VK_OEM_MINUS = 0xBD  # - / _
VK_OEM_PERIOD = 0xBE  # . / >
VK_OEM_2 = 0xBF  # / / ?
VK_OEM_3 = 0xC0  # ` / ~
VK_OEM_5 = 0xDC  # \\ / |
VK_OEM_7 = 0xDE  # ' / "

_KEY_TO_VK = {
    " ": VK_SPACE,
    ":": (VK_OEM_1, True),
    ";": (VK_OEM_1, False),
    "+": (VK_OEM_PLUS, True),
    "=": (VK_OEM_PLUS, False),
    "<": (VK_OEM_COMMA, True),
    ",": (VK_OEM_COMMA, False),
    "_": (VK_OEM_MINUS, True),
    "-": (VK_OEM_MINUS, False),
    ">": (VK_OEM_PERIOD, True),
    ".": (VK_OEM_PERIOD, False),
    "?": (VK_OEM_2, True),
    "/": (VK_OEM_2, False),
    "~": (VK_OEM_3, True),
    "`": (VK_OEM_3, False),
    "|": (VK_OEM_5, True),
    "\\": (VK_OEM_5, False),
    '"': (VK_OEM_7, True),
    "'": (VK_OEM_7, False),
    "(": ("9", True),
    ")": ("0", True),
    "!": ("1", True),
    "@": ("2", True),
    "#": ("3", True),
    "$": ("4", True),
    "%": ("5", True),
    "^": ("6", True),
    "&": ("7", True),
    "*": ("8", True),
}


def _char_to_key(char: str) -> tuple[int, bool]:
    """(VK code, needs_shift) for one character; unknown chars are an
    honest env error — a mistyped path must never be sent silently."""
    if "a" <= char <= "z":
        return ord(char.upper()), False
    if "A" <= char <= "Z":
        return ord(char), True
    if "0" <= char <= "9":
        return ord(char), False
    mapped = _KEY_TO_VK.get(char)
    if mapped is None:
        raise TesterEnvError(
            f"cannot type character {char!r} — no VK mapping (add it to "
            f"_KEY_TO_VK in desktop_runner.py)"
        )
    if isinstance(mapped, int):
        return mapped, False
    vk, shift = mapped
    return (ord(vk), True) if isinstance(vk, str) and len(vk) == 1 else (vk, shift)


def _send_key(vk: int, down: bool) -> None:
    inp = _Input()
    inp.type = 1  # INPUT_KEYBOARD
    inp.u.ki = _KeybdInput(vk, 0, 0 if down else 2, 0, None)
    USER32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_Input))
    time.sleep(0.02)


def _tap_key(vk: int, shift: bool = False) -> None:
    if shift:
        _send_key(VK_LSHIFT, True)
    _send_key(vk, True)
    _send_key(vk, False)
    if shift:
        _send_key(VK_LSHIFT, False)
    time.sleep(0.05)


def _type_text(text: str) -> None:
    for char in text:
        vk, shift = _char_to_key(char)
        _tap_key(vk, shift)


class Element:
    """A resolved element inside a NATIVE dialog (UIA names work there —
    the tkinter window itself has no accessibility tree)."""

    def __init__(self, app: "DesktopApp", element):
        self._app = app
        self._el = element

    def _check_budget(self) -> None:
        self._app._check_budget()

    def wait(self, timeout: float) -> None:
        self._check_budget()
        try:
            self._el.wait("exists", timeout=min(timeout, self._app._time_left()))
        except Exception as exc:
            raise TesterAssertionError(
                f"dialog element {self._el!r} never appeared: {exc}"
            ) from exc

    def wait_gone(self, timeout: float) -> None:
        """Wait for the dialog to close (e.g. after the submit keystroke)
        — verifies the action took."""
        self._check_budget()
        try:
            self._el.wait_not("exists", timeout=min(timeout, self._app._time_left()))
        except Exception as exc:
            raise TesterAssertionError(
                f"dialog {self._el!r} never closed: {exc}"
            ) from exc

    def focus(self) -> None:
        """Raise the dialog to the foreground. Tk's native file dialogs open
        WITHOUT taking foreground (live-verified 2026-08-19: the parent AG
        window keeps it), so keystrokes would go to the parent — this is
        called right after the dialog appears."""
        self._check_budget()
        hwnd = self._el.handle
        USER32.ShowWindow(hwnd, 9)
        USER32.SetForegroundWindow(hwnd)
        time.sleep(0.3)

    def set_text(self, value: str) -> None:
        self._check_budget()
        try:
            self._el.wait("enabled", timeout=min(10, self._app._time_left()))
            self._el.set_edit_text(value)
        except Exception as exc:
            raise TesterAssertionError(f"could not type into {self._el!r}: {exc}")

    def click(self) -> None:
        self._check_budget()
        try:
            self._el.wait("enabled", timeout=min(10, self._app._time_left()))
            self._el.click_input()
        except Exception as exc:
            raise TesterAssertionError(f"could not click {self._el!r}: {exc}")


class DesktopApp:
    """Attach to one named window by title; capture, click and read it.
    Nothing outside the declared window is ever touched (Rule 1)."""

    def __init__(self, title_pattern: str, budget_s: int = 120):
        self.title_pattern = title_pattern
        self._re = re.compile(title_pattern)
        self.budget_s = budget_s
        self.deadline = time.monotonic() + budget_s
        self._desktop = None
        self.window = None
        self._client = (0, 0)

    # ------------------------------------------------------------- budget

    def _time_left(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def _check_budget(self) -> None:
        if time.monotonic() > self.deadline:
            raise TesterTimeoutError(
                f"Native feature exceeded its {self.budget_s}s budget"
            )

    # ------------------------------------------------------------ connect

    def connect(self) -> None:
        """Attach to the app window. Refuses windows whose title does not
        match the feature's declared pattern (Rule 1)."""
        from pywinauto import Desktop
        from pywinauto.findwindows import ElementAmbiguousError

        self._desktop = Desktop(backend="uia")
        deadline = time.monotonic() + CONNECT_MAX_S
        while time.monotonic() < deadline:
            self._check_budget()
            try:
                window = self._desktop.window(title_re=self.title_pattern)
                window.wait("exists", timeout=2)
            except ElementAmbiguousError as exc:
                raise TesterEnvError(
                    f"Multiple windows match {self.title_pattern!r} — leftover "
                    f"instances of the app are running. Close them and retry "
                    f"(the tester reclaims its own previous instances)"
                ) from exc
            except Exception:
                time.sleep(1)
                continue
            if not self._re.match(window.window_text() or ""):
                raise TesterEnvError(
                    f"Refusing to drive window {window.window_text()!r}: title "
                    f"does not match the declared pattern {self.title_pattern!r} "
                    f"(Rule 1)"
                )
            self.window = window
            self._client = self._client_size()
            return
        raise TesterEnvError(
            f"No window matching {self.title_pattern!r} appeared within "
            f"{CONNECT_MAX_S}s — is the app's GUI running? (the tester "
            f"launches it; a crashed/closed GUI is an investigate)"
        )

    # ------------------------------------------------------- foreground

    def bring_to_front(self) -> None:
        """Restore + raise the window and obtain foreground. Windows grants
        foreground rights only when the desktop allows it — a game/video
        holding the foreground is an honest, retryable TesterEnvError
        (the click-through cannot work from behind another window)."""
        hwnd = self.window.handle
        USER32.ShowWindow(hwnd, 9)  # SW_RESTORE
        deadline = time.monotonic() + FOREGROUND_MAX_S
        while time.monotonic() < deadline:
            self._check_budget()
            if USER32.GetForegroundWindow() == hwnd:
                return
            fg_thread = USER32.GetWindowThreadProcessId(
                USER32.GetForegroundWindow(), None
            )
            my_thread = K32.GetCurrentThreadId()
            attached = USER32.AttachThreadInput(my_thread, fg_thread, True)
            try:
                USER32.BringWindowToTop(hwnd)
                USER32.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    USER32.AttachThreadInput(my_thread, fg_thread, False)
            time.sleep(0.7)
        raise TesterEnvError(
            "The app window could not be brought to the foreground — the "
            "desktop is busy (another app holds foreground rights). Retry "
            "the run when the desktop is free."
        )

    # ------------------------------------------------------------ capture

    def _client_size(self) -> tuple[int, int]:
        rect = ctypes.wintypes.RECT()
        USER32.GetClientRect(self.window.handle, ctypes.byref(rect))
        return rect.right, rect.bottom

    def capture(self) -> Image.Image:
        """PrintWindow(PW_RENDERFULLCONTENT|PW_CLIENTONLY) — the window's
        own surface regardless of occlusion (plain PrintWindow returns
        garbage for this window; live-verified 2026-08-19)."""
        self._check_budget()
        hwnd = self.window.handle
        user32 = USER32
        gdi32 = GDI32
        cw, ch = self._client
        hdc_win = user32.GetWindowDC(hwnd)
        try:
            hdc = gdi32.CreateCompatibleDC(hdc_win)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_win, cw, ch)
            try:
                gdi32.SelectObject(hdc, hbmp)
                ok = user32.PrintWindow(hwnd, hdc, 0x00000002 | 0x00000001)
                if not ok:
                    raise TesterEnvError("PrintWindow capture failed")

                class _Bmi(ctypes.Structure):
                    _fields_ = [
                        ("biSize", ctypes.wintypes.DWORD),
                        ("biWidth", ctypes.wintypes.LONG),
                        ("biHeight", ctypes.wintypes.LONG),
                        ("biPlanes", ctypes.wintypes.WORD),
                        ("biBitCount", ctypes.wintypes.WORD),
                        ("biCompression", ctypes.wintypes.DWORD),
                        ("biSizeImage", ctypes.wintypes.DWORD),
                        ("biXPelsPerMeter", ctypes.wintypes.LONG),
                        ("biYPelsPerMeter", ctypes.wintypes.LONG),
                        ("biClrUsed", ctypes.wintypes.DWORD),
                        ("biClrImportant", ctypes.wintypes.DWORD),
                    ]

                bmi = _Bmi()
                bmi.biSize = ctypes.sizeof(_Bmi)
                bmi.biWidth = cw
                bmi.biHeight = -ch
                bmi.biPlanes = 1
                bmi.biBitCount = 32
                buf = ctypes.create_string_buffer(cw * ch * 4)
                gdi32.GetDIBits(hdc, hbmp, 0, ch, buf, ctypes.byref(bmi), 0)
                return Image.frombuffer(
                    "RGBA", (cw, ch), buf.raw, "raw", "BGRA", 0, 1
                ).convert("RGB")
            finally:
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(hdc)
        finally:
            user32.ReleaseDC(hwnd, hdc_win)

    def shot(self, path: str | Path) -> None:
        """Save the current window capture to a PNG (same landing as page
        screenshots — the blank-gray-level check happens in FeatureContext)."""
        self.capture().save(str(path))

    # ------------------------------------------------------------ clicking

    def click(self, x: int, y: int) -> None:
        """Physical click at a client-area offset (SendInput). Coordinates
        are measured constants for the fixed window layout; the effect is
        always verified separately (dialog appears / region repaints).
        ClientToScreen converts the client point (the outer-rect math would
        ignore the title bar — live-fix 2026-08-19)."""
        self._check_budget()
        point = ctypes.wintypes.POINT(x, y)
        USER32.ClientToScreen(self.window.handle, ctypes.byref(point))
        _send_physical_click(point.x, point.y)

    # ------------------------------------------------------------ keyboard

    def type_text(self, text: str) -> None:
        """Type a string into the focused control (SendInput keystrokes).
        Used for native dialogs whose File name box lives inside a
        DirectUIHWND the win32 backend cannot reach — keyboard is the
        reliable channel (live-verified 2026-08-19)."""
        self._check_budget()
        _type_text(text)

    def press_alt(self, letter: str) -> None:
        """Alt+letter (access key — e.g. Alt+N focuses the dialog's
        "File name:" box)."""
        self._check_budget()
        if not (len(letter) == 1 and letter.isalpha()):
            raise TesterEnvError(f"press_alt expects a single letter, got {letter!r}")
        _send_key(0x12, True)  # VK_MENU down
        _tap_key(ord(letter.upper()))
        _send_key(0x12, False)

    def press_enter(self) -> None:
        """Enter key (submits the focused dialog control)."""
        self._check_budget()
        _tap_key(VK_RETURN)

    # -------------------------------------------------------------- dialog

    def dialog(self, title_pattern: str) -> Element:
        """A native top-level dialog the app opened (e.g. the Win32 file
        dialog) — its elements are UIA-drivable by name. TesterEnvError if
        it never appears (the click before it did not take). The WIN32
        backend is used here: the UIA Desktop lookup used for the app
        window times out on these native dialogs even though win32 find
        resolves them instantly (live-verified 2026-08-19)."""
        from pywinauto import Desktop as WinDesktop

        desktop = WinDesktop(backend="win32")
        deadline = time.monotonic() + DIALOG_WAIT_S
        while time.monotonic() < deadline:
            self._check_budget()
            try:
                dlg = desktop.window(title_re=title_pattern)
                dlg.wait("exists", timeout=2)
                return Element(self, dlg)
            except Exception:
                time.sleep(1)
        raise TesterEnvError(
            f"No dialog matching {title_pattern!r} appeared within " f"{DIALOG_WAIT_S}s"
        )

    def element(self, title: str, parent: Element) -> Element:
        """A child element by name inside a dialog (UIA names work for
        native dialogs; the tkinter window itself has no tree)."""
        self._check_budget()
        try:
            return Element(self, parent._el.child_window(title=title))
        except Exception as exc:
            raise TesterAssertionError(f"could not resolve {title!r}: {exc}")

    # -------------------------------------------------------------- pixels

    @staticmethod
    def changed_pixels(
        before: Image.Image,
        after: Image.Image,
        box: tuple[int, int, int, int],
        step: int = 4,
    ) -> int:
        """Sampled pixel diff inside a client box (step 4 by default — fast,
        and the app repaints whole regions, not single pixels). Smaller
        steps catch sparse text lines (live-fixed 2026-08-19: a 1-2px log
        line can land between the coarse sample rows)."""
        pb, pa = before.load(), after.load()
        x0, y0, x1, y1 = box
        x1 = min(x1, before.width)
        y1 = min(y1, before.height)
        changed = 0
        for y in range(y0, y1, step):
            for x in range(x0, x1, step):
                if pb[x, y] != pa[x, y]:
                    changed += 1
        return changed

    def wait_region_change(
        self,
        before: Image.Image,
        box: tuple[int, int, int, int],
        min_changed: int,
        timeout: float,
        step: int = 4,
    ) -> None:
        """Poll captures until the region differs enough from the baseline.
        TesterAssertionError on timeout — the transition never happened."""
        deadline = time.monotonic() + min(timeout, self._time_left())
        while time.monotonic() < deadline:
            self._check_budget()
            if self.changed_pixels(before, self.capture(), box, step) >= min_changed:
                return
            time.sleep(1)
        raise TesterAssertionError(
            f"region {box} never changed within "
            f"{min(timeout, self.budget_s)}s (expected >= {min_changed} px)"
        )

    def assert_pixel(
        self, x: int, y: int, rgb: tuple[int, int, int], tolerance: int = 6
    ) -> None:
        """Theme-signature anchor: a pixel in the current capture must be
        within tolerance of the measured color (deterministic layout)."""
        self._check_budget()
        actual = self.capture().getpixel((x, y))
        if any(abs(a - b) > tolerance for a, b in zip(actual, rgb)):
            raise TesterAssertionError(
                f"pixel ({x},{y}) = {actual}, expected ~{rgb} — the window "
                f"layout/theme differs from the measured signature"
            )

    def content_pixels(
        self, box: tuple[int, int, int, int], bg: tuple[int, int, int]
    ) -> int:
        """How many pixels in a client box differ from the background color —
        e.g. the text glyphs inside an entry (live-measured: the pose path
        fills ~1600 px; the empty entry has 0)."""
        self._check_budget()
        im = self.capture().load()
        x0, y0, x1, y1 = box
        x1 = min(x1, self._client[0])
        y1 = min(y1, self._client[1])
        count = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                if im[x, y] != bg:
                    count += 1
        return count
