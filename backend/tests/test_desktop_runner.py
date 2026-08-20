"""DesktopApp engine unit tests (docs/clickthrough_plan.md Phase 3
chunk 1, v1.17.16.0). No real windows: pywinauto.Desktop is stubbed at
module level and the ctypes USER32 surface is monkeypatched where the
tests touch it. The live window path (capture/click/dialog) is covered
by the live E2E — the plan's chunk-1 acceptance.
"""

import ctypes

import pytest
from PIL import Image

from app.services import desktop_runner as dr
from app.testers._helpers import (
    TesterAssertionError,
    TesterEnvError,
    TesterTimeoutError,
)


class _FakeWindow:
    def __init__(self, title):
        self._title = title
        self.handle = 331324

    def wait(self, method, timeout):
        return None

    def window_text(self):
        return self._title

    def __repr__(self):
        return f"_FakeWindow({self._title!r})"


class _FakeDesktop:
    def __init__(self, title):
        self._title = title

    def window(self, title_re=None):
        return _FakeWindow(self._title)


def _patch_pywinauto(monkeypatch, title="AG Character & Weapon Studio"):
    import pywinauto

    monkeypatch.setattr(pywinauto, "Desktop", lambda backend=None: _FakeDesktop(title))

    def fake_rect(h, r):
        rect = ctypes.cast(r, ctypes.POINTER(ctypes.wintypes.RECT)).contents
        rect.right = 720
        rect.bottom = 680
        return 1

    monkeypatch.setattr(dr.USER32, "GetClientRect", fake_rect)


# ---------------------------------------------------------------- connect


def test_connect_refuses_nonmatching_title(monkeypatch):
    _patch_pywinauto(monkeypatch, title="Totally Different App")
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    with pytest.raises(TesterEnvError, match="Refusing to drive"):
        app.connect()


def test_connect_attaches_matching_title(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    assert app.window is not None
    assert app._client == (720, 680)


def test_connect_missing_window_is_env_error(monkeypatch):
    import pywinauto

    def _raise(title_re=None):
        raise RuntimeError("no window")

    monkeypatch.setattr(
        pywinauto, "Desktop", lambda backend=None: type("D", (), {"window": _raise})()
    )
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    monkeypatch.setattr(dr, "CONNECT_MAX_S", 1)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    with pytest.raises(TesterEnvError, match="No window matching"):
        app.connect()


def test_connect_ambiguous_instances_is_clear_env_error(monkeypatch):
    import pywinauto
    from pywinauto.findwindows import ElementAmbiguousError

    class _AmbiguousDesktop:
        def window(self, title_re=None):
            raise ElementAmbiguousError("2 elements match")

    monkeypatch.setattr(pywinauto, "Desktop", lambda backend=None: _AmbiguousDesktop())
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    with pytest.raises(TesterEnvError, match="Multiple windows match"):
        app.connect()


def test_wait_for_window_returns_none_when_window_never_appears(monkeypatch):
    """v1.17.17.1: wait_for_window polls with the caller's timeout and
    returns None (not an error) when the awaited window never shows."""
    import pywinauto

    def _raise(title_re=None):
        raise RuntimeError("no window")

    monkeypatch.setattr(
        pywinauto, "Desktop", lambda backend=None: type("D", (), {"window": _raise})()
    )
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    got = dr.wait_for_window(r"^AG (Animation )?Viewer", timeout_s=1, budget_s=60)
    assert got is None


def test_wait_for_window_attaches_when_window_appears(monkeypatch):
    """The awaited child window (e.g. AG's viewer after generation) is
    attached with the same Rule-1 title guard as connect()."""
    _patch_pywinauto(monkeypatch, title="AG Animation Viewer")
    got = dr.wait_for_window(r"^AG (Animation )?Viewer", timeout_s=5, budget_s=60)
    assert got is not None
    assert got.window is not None
    assert got._client == (720, 680)


def test_wait_for_window_ambiguous_is_honest_env_error(monkeypatch):
    """Leftover viewer instances must not be silently swallowed — the
    ambiguous case stays an honest env error."""
    import pywinauto
    from pywinauto.findwindows import ElementAmbiguousError

    class _AmbiguousDesktop:
        def window(self, title_re=None):
            raise ElementAmbiguousError("2 elements match")

    monkeypatch.setattr(pywinauto, "Desktop", lambda backend=None: _AmbiguousDesktop())
    with pytest.raises(TesterEnvError, match="Multiple windows match"):
        dr.wait_for_window(r"^AG (Animation )?Viewer", timeout_s=1, budget_s=60)


# ----------------------------------------------------------- foreground


def test_bring_to_front_obtains_foreground(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    calls = []
    target = app.window.handle
    monkeypatch.setattr(
        dr.USER32, "ShowWindow", lambda h, c: calls.append(("show", c)) or 1
    )
    monkeypatch.setattr(
        dr.USER32,
        "GetForegroundWindow",
        lambda: target if calls.count(("sfw",)) else 0,
    )
    monkeypatch.setattr(
        dr.USER32, "AttachThreadInput", lambda a, b, c: calls.append(("attach", c)) or 1
    )
    monkeypatch.setattr(dr.USER32, "BringWindowToTop", lambda h: 1)
    monkeypatch.setattr(
        dr.USER32, "SetForegroundWindow", lambda h: calls.append(("sfw",)) or 1
    )
    monkeypatch.setattr(dr.K32, "GetCurrentThreadId", lambda: 7)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    app.bring_to_front()
    assert ("show", 9) in calls
    assert ("attach", True) in calls
    assert ("attach", False) in calls
    assert ("sfw",) in calls


def test_bring_to_front_busy_desktop_is_env_error(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    monkeypatch.setattr(dr.USER32, "ShowWindow", lambda h, c: 1)
    monkeypatch.setattr(dr.USER32, "GetForegroundWindow", lambda: 0)
    monkeypatch.setattr(dr.USER32, "AttachThreadInput", lambda a, b, c: 1)
    monkeypatch.setattr(dr.USER32, "BringWindowToTop", lambda h: 1)
    monkeypatch.setattr(dr.USER32, "SetForegroundWindow", lambda h: 0)
    monkeypatch.setattr(dr.K32, "GetCurrentThreadId", lambda: 7)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    monkeypatch.setattr(dr, "FOREGROUND_MAX_S", 1)
    with pytest.raises(TesterEnvError, match="foreground"):
        app.bring_to_front()


# --------------------------------------------------------------- pixels


def test_changed_pixels_counts_sampled_diffs():
    a = Image.new("RGB", (100, 100), (27, 29, 35))
    b = a.copy()
    for x in range(0, 100, 4):
        for y in range(0, 100, 4):
            b.putpixel((x, y), (0, 0, 0))
    assert dr.DesktopApp.changed_pixels(a, b, (0, 0, 100, 100)) == 625
    assert dr.DesktopApp.changed_pixels(a, b, (0, 0, 4, 4)) == 1
    assert dr.DesktopApp.changed_pixels(a, a, (0, 0, 100, 100)) == 0


def test_wait_region_change_times_out_as_assertion(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    monkeypatch.setattr(app, "capture", lambda: Image.new("RGB", (720, 680), (0, 0, 0)))
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    monkeypatch.setattr(app, "_time_left", lambda: 5.0)
    with pytest.raises(TesterAssertionError, match="never changed"):
        app.wait_region_change(
            Image.new("RGB", (720, 680), (0, 0, 0)), (0, 0, 720, 680), 40, 2
        )


def test_assert_pixel_tolerance():
    a = Image.new("RGB", (100, 100), (35, 38, 46))
    app = dr.DesktopApp(r"^x$")
    app.capture = lambda: a
    app._check_budget = lambda: None
    app.assert_pixel(10, 10, (35, 38, 46))
    app.assert_pixel(10, 10, (30, 40, 50), tolerance=20)
    with pytest.raises(TesterAssertionError, match="layout/theme"):
        app.assert_pixel(10, 10, (255, 0, 0))


# --------------------------------------------------------------- clicking


def test_send_physical_click_sends_input(monkeypatch):
    calls = []
    monkeypatch.setattr(
        dr.USER32, "GetSystemMetrics", lambda i: 1920 if i == 0 else 1080
    )
    monkeypatch.setattr(dr.USER32, "SendInput", lambda n, p, s: calls.append(n) or 1)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    dr._send_physical_click(690, 400)
    assert calls == [1, 1, 1]  # move, down, up


def test_click_sends_physical_click_at_client_offset(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    coords = []
    monkeypatch.setattr(dr, "_send_physical_click", lambda x, y: coords.append((x, y)))

    def fake_rect(h, pt):
        point = ctypes.cast(pt, ctypes.POINTER(ctypes.wintypes.POINT)).contents
        point.x += 108
        point.y += 231
        return 1

    monkeypatch.setattr(dr.USER32, "ClientToScreen", fake_rect)
    app.click(690, 90)
    assert coords == [(798, 321)]


# --------------------------------------------------------------- capture


def test_capture_returns_window_surface(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()

    def fake_dc(*args):
        return 1

    monkeypatch.setattr(dr.USER32, "GetWindowDC", fake_dc)
    monkeypatch.setattr(dr.USER32, "ReleaseDC", lambda h, d: 1)
    monkeypatch.setattr(dr.USER32, "PrintWindow", lambda h, d, f: 1)
    monkeypatch.setattr(dr.GDI32, "CreateCompatibleDC", fake_dc)
    monkeypatch.setattr(dr.GDI32, "CreateCompatibleBitmap", fake_dc)
    monkeypatch.setattr(dr.GDI32, "SelectObject", lambda h, o: 1)
    monkeypatch.setattr(
        dr.GDI32,
        "GetDIBits",
        lambda dc, b, s, r, buf, bmi, u: ctypes.memset(buf, 120, 720 * 680 * 4) or 1,
    )
    monkeypatch.setattr(dr.GDI32, "DeleteObject", lambda o: 1)
    monkeypatch.setattr(dr.GDI32, "DeleteDC", lambda d: 1)
    im = app.capture()
    assert im.size == (720, 680)
    assert im.getpixel((0, 0)) == (120, 120, 120)


def test_capture_failure_is_env_error(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    monkeypatch.setattr(dr.USER32, "GetWindowDC", lambda h: 1)
    monkeypatch.setattr(dr.USER32, "ReleaseDC", lambda h, d: 1)
    monkeypatch.setattr(dr.USER32, "PrintWindow", lambda h, d, f: 0)
    with pytest.raises(TesterEnvError, match="PrintWindow"):
        app.capture()


def test_shot_saves_png(monkeypatch, tmp_path):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    out = tmp_path / "ag.png"

    def fake_dc(*args):
        return 1

    monkeypatch.setattr(dr.USER32, "GetWindowDC", fake_dc)
    monkeypatch.setattr(dr.USER32, "ReleaseDC", lambda h, d: 1)
    monkeypatch.setattr(dr.USER32, "PrintWindow", lambda h, d, f: 1)
    monkeypatch.setattr(dr.GDI32, "CreateCompatibleDC", fake_dc)
    monkeypatch.setattr(dr.GDI32, "CreateCompatibleBitmap", fake_dc)
    monkeypatch.setattr(dr.GDI32, "SelectObject", lambda h, o: 1)
    monkeypatch.setattr(
        dr.GDI32,
        "GetDIBits",
        lambda dc, b, s, r, buf, bmi, u: ctypes.memset(buf, 120, 720 * 680 * 4) or 1,
    )
    monkeypatch.setattr(dr.GDI32, "DeleteObject", lambda o: 1)
    monkeypatch.setattr(dr.GDI32, "DeleteDC", lambda d: 1)
    app.shot(out)
    assert out.exists()
    assert Image.open(out).size == (720, 680)


# ------------------------------------------------------------ keyboard


def _record_keys(monkeypatch):
    events = []
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    monkeypatch.setattr(dr, "_send_key", lambda vk, down: events.append((vk, down)))
    return events


def test_char_to_key_letters_and_shift():
    assert dr._char_to_key("a") == (0x41, False)
    assert dr._char_to_key("Z") == (0x5A, True)
    assert dr._char_to_key("7") == (0x37, False)


def test_char_to_key_path_symbols():
    assert dr._char_to_key(":") == (0xBA, True)
    assert dr._char_to_key("\\") == (0xDC, False)
    assert dr._char_to_key("_") == (0xBD, True)
    assert dr._char_to_key(".") == (0xBE, False)
    assert dr._char_to_key(" ") == (0x20, False)


def test_char_to_key_unknown_is_env_error():
    with pytest.raises(TesterEnvError, match="no VK mapping"):
        dr._char_to_key("ç")


def test_type_text_sends_shifted_sequence(monkeypatch):
    events = _record_keys(monkeypatch)
    dr._type_text("C")
    assert events == [
        (0xA0, True),  # shift down
        (0x43, True),  # C down
        (0x43, False),  # C up
        (0xA0, False),  # shift up
    ]


def test_press_alt_sends_menu_sequence(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    events = _record_keys(monkeypatch)
    app.press_alt("n")
    assert events == [
        (0x12, True),  # menu down
        (0x4E, True),  # N down
        (0x4E, False),  # N up
        (0x12, False),  # menu up
    ]


def test_press_alt_rejects_non_letter(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    with pytest.raises(TesterEnvError, match="single letter"):
        app.press_alt("1")


def test_press_enter_sends_return(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    events = _record_keys(monkeypatch)
    app.press_enter()
    assert events == [(0x0D, True), (0x0D, False)]


def test_wait_gone_asserts_when_dialog_stays(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()

    class _Sticky:
        def wait(self, method, timeout):
            raise RuntimeError("still here")

    el = dr.Element(app, _Sticky())
    with pytest.raises(TesterAssertionError, match="never closed"):
        el.wait_gone(5)


def test_content_pixels_counts_non_bg(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    im = Image.new("RGB", (720, 680), (255, 255, 255))
    for x in range(100, 140):
        im.putpixel((x, 90), (0, 0, 0))
    monkeypatch.setattr(app, "capture", lambda: im)
    assert app.content_pixels((0, 80, 720, 100), (255, 255, 255)) == 40
    assert app.content_pixels((0, 80, 720, 100), (0, 0, 0)) == 720 * 20 - 40


# --------------------------------------------------------------- dialog


def test_dialog_attaches_and_element_drives(monkeypatch):
    backends = []

    class _El:
        def __init__(self):
            self.waits = 0

        def wait(self, method, timeout):
            self.waits += 1

        def set_edit_text(self, value):
            self.value = value

        def click_input(self):
            self.dlg_clicked = True

        def child_window(self, title):
            return _El()

    class _Desktop:
        def __init__(self):
            self.dlg = _El()

        def window(self, title_re=None):
            if title_re == r"^Select T-Pose Image$":
                return self.dlg
            return _FakeWindow("AG Character & Weapon Studio")

    import pywinauto

    def make_desktop(backend=None):
        backends.append(backend)
        return _Desktop()

    monkeypatch.setattr(pywinauto, "Desktop", make_desktop)

    def fake_rect(h, r):
        rect = ctypes.cast(r, ctypes.POINTER(ctypes.wintypes.RECT)).contents
        rect.right = 720
        rect.bottom = 680
        return 1

    monkeypatch.setattr(dr.USER32, "GetClientRect", fake_rect)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    dlg = app.dialog(r"^Select T-Pose Image$")
    assert isinstance(dlg, dr.Element)
    assert backends == ["uia", "win32"]  # connect=uia, dialog=win32
    file_name = app.element("File name:", dlg)
    file_name.wait(10)
    file_name.set_text(r"C:\p\pose.png")
    assert file_name._el.value == r"C:\p\pose.png"
    open_btn = app.element("Open", dlg)
    open_btn.click()
    assert open_btn._el.dlg_clicked is True


def test_dialog_missing_is_env_error(monkeypatch):
    _patch_pywinauto(monkeypatch)

    class _Desktop:
        def window(self, title_re=None):
            if title_re == r"^Select T-Pose Image$":
                raise RuntimeError("no dialog")
            return _FakeWindow("AG Character & Weapon Studio")

    import pywinauto

    monkeypatch.setattr(pywinauto, "Desktop", lambda backend=None: _Desktop())
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    monkeypatch.setattr(dr, "DIALOG_WAIT_S", 0)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    with pytest.raises(TesterEnvError, match="No dialog matching"):
        app.dialog(r"^Select T-Pose Image$")


def test_element_resolution_failure_is_assertion(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()

    class _El:
        def child_window(self, title):
            raise RuntimeError("nope")

    parent = dr.Element(app, _El())
    with pytest.raises(TesterAssertionError, match="could not resolve"):
        app.element("File name:", parent)


def test_element_wait_and_drive_failures_are_assertions(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()

    class _El:
        def wait(self, method, timeout):
            raise RuntimeError("gone")

    el = dr.Element(app, _El())
    with pytest.raises(TesterAssertionError, match="never appeared"):
        el.wait(5)

    class _El2:
        def wait(self, method, timeout):
            return None

        def set_edit_text(self, value):
            raise RuntimeError("readonly")

        def click_input(self):
            raise RuntimeError("disabled")

    el2 = dr.Element(app, _El2())
    with pytest.raises(TesterAssertionError, match="could not type"):
        el2.set_text("x")
    with pytest.raises(TesterAssertionError, match="could not click"):
        el2.click()


# ------------------------------------------------------------ region wait


def test_wait_region_change_returns_when_region_repaints(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    before = Image.new("RGB", (720, 680), (0, 0, 0))
    after = Image.new("RGB", (720, 680), (0, 0, 0))
    for x in range(0, 720, 4):
        for y in range(0, 680, 4):
            after.putpixel((x, y), (255, 255, 255))
    monkeypatch.setattr(app, "capture", lambda: after)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    app.wait_region_change(before, (0, 0, 720, 680), 40, 2)


def test_changed_pixels_step_catches_thin_line_step4_misses(monkeypatch):
    """A 1-2px log line can land between the step-4 sample rows; step 2
    catches it (live-fixed 2026-08-19 — the AG status line renders at
    y 543-549 while the coarse grid only sampled 540/544/548)."""
    before = Image.new("RGB", (720, 680), (0, 0, 0))
    after = Image.new("RGB", (720, 680), (0, 0, 0))
    for x in range(100, 300):
        for y in (545, 546):
            after.putpixel((x, y), (255, 255, 255))
    box = (0, 540, 720, 668)
    assert dr.DesktopApp.changed_pixels(before, after, box, step=4) == 0
    assert dr.DesktopApp.changed_pixels(before, after, box, step=2) > 0
    assert dr.DesktopApp.changed_pixels(before, after, box, step=2) >= 15


def test_wait_region_change_forwards_step(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    before = Image.new("RGB", (720, 680), (0, 0, 0))
    after = Image.new("RGB", (720, 680), (0, 0, 0))
    for x in range(100, 300):
        for y in (545, 546):
            after.putpixel((x, y), (255, 255, 255))
    monkeypatch.setattr(app, "capture", lambda: after)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    # step 4 would never pass (0 changed); step 2 sees the thin line
    app.wait_region_change(before, (0, 540, 720, 668), 15, 2, step=2)


# ------------------------------------------------------------ chunk 2


def test_pin_window_moves_and_verifies_client(monkeypatch):
    """HFT chunk 2 (v1.17.17.0): pin position + verify the client size the
    measured coordinates assume (SDL sizes are client-area — the size is
    never forced, only checked, so a resized window fails honestly)."""
    _patch_pywinauto(monkeypatch, title="HFT Order Book")

    def big_rect(h, r):
        rect = ctypes.cast(r, ctypes.POINTER(ctypes.wintypes.RECT)).contents
        rect.right = 1280
        rect.bottom = 760
        return 1

    monkeypatch.setattr(dr.USER32, "GetClientRect", big_rect)
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    calls = []
    hwnd = app.window.handle
    monkeypatch.setattr(
        dr.USER32,
        "SetWindowPos",
        lambda h, after, x, y, w, hh, flags: calls.append((h, x, y, w, hh, flags)) or 1,
    )
    app.pin_window(40, 40, expected_client=(1280, 760))
    h, x, y, w, hh, flags = calls[-1]
    assert h == hwnd
    assert (x, y) == (40, 40)
    assert (w, hh) == (0, 0)  # SWP_NOSIZE — never force the size
    assert flags & dr.SWP_NOSIZE
    assert flags & dr.SWP_NOZORDER


def test_pin_window_wrong_client_is_env_error(monkeypatch):
    _patch_pywinauto(monkeypatch, title="HFT Order Book")

    def small_rect(h, r):
        rect = ctypes.cast(r, ctypes.POINTER(ctypes.wintypes.RECT)).contents
        rect.right = 1000
        rect.bottom = 600
        return 1

    monkeypatch.setattr(dr.USER32, "GetClientRect", small_rect)
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    monkeypatch.setattr(dr.USER32, "SetWindowPos", lambda *a, **k: 1)
    with pytest.raises(TesterEnvError, match="client size is"):
        app.pin_window(40, 40, expected_client=(1280, 760))


def test_find_color_bbox_locates_control(monkeypatch):
    """Green-fill search: finds the flow-laid button's bbox (sampled step 2,
    so bounds are within +/-2 px), tolerates theme blending, and rejects
    stray pixels via min_pixels."""
    _patch_pywinauto(monkeypatch, title="HFT Order Book")
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    im = Image.new("RGB", (1280, 760), (18, 20, 23))
    for y in range(220, 248):
        for x in range(40, 400):
            im.putpixel((x, y), (32, 95, 45))
    monkeypatch.setattr(app, "capture", lambda: im)
    bbox = app.find_color_bbox((0, 0, 500, 400), (26, 89, 38), tolerance=10)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x0 <= 40 and x1 >= 398 and y0 <= 220 and y1 >= 246
    assert app.find_color_bbox((0, 0, 500, 400), (26, 89, 38), tolerance=2) is None
    assert app.find_color_bbox((600, 0, 900, 400), (26, 89, 38), tolerance=10) is None


def test_find_color_bbox_rejects_sparse_matches(monkeypatch):
    _patch_pywinauto(monkeypatch, title="HFT Order Book")
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    im = Image.new("RGB", (1280, 760), (18, 20, 23))
    im.putpixel((100, 100), (26, 89, 38))
    im.putpixel((102, 102), (26, 89, 38))
    monkeypatch.setattr(app, "capture", lambda: im)
    assert app.find_color_bbox((0, 0, 500, 400), (26, 89, 38), min_pixels=50) is None


def test_wait_region_stable_returns_when_settled(monkeypatch):
    _patch_pywinauto(monkeypatch, title="HFT Order Book")
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    static = Image.new("RGB", (1280, 760), (18, 20, 23))
    monkeypatch.setattr(app, "capture", lambda: static)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    app.wait_region_stable((0, 0, 1280, 760), settle_s=2, timeout=5)


def test_wait_region_stable_times_out_on_animated_screen(monkeypatch):
    _patch_pywinauto(monkeypatch, title="HFT Order Book")
    app = dr.DesktopApp(r"^HFT Order Book$")
    app.connect()
    frames = []
    for i in range(10):
        im = Image.new("RGB", (1280, 760), (18, 20, 23))
        im.putpixel((i, i), (255, 255, 255))
        frames.append(im)
    counter = {"i": 0}

    def _animated():
        i = counter["i"]
        counter["i"] += 1
        im = Image.new("RGB", (1280, 760), (18, 20, 23))
        im.putpixel((i % 20, i % 20), (255, 255, 255))
        return im

    monkeypatch.setattr(app, "capture", _animated)
    monkeypatch.setattr(dr.time, "sleep", lambda s: None)
    with pytest.raises(TesterAssertionError, match="never settled"):
        app.wait_region_stable((0, 0, 1280, 760), settle_s=2, timeout=3)


def test_time_left_never_negative(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$")
    app.connect()
    app.deadline = 0
    assert app._time_left() == 0.0


# --------------------------------------------------------------- budget


def test_budget_exhaustion_raises_timeout(monkeypatch):
    _patch_pywinauto(monkeypatch)
    app = dr.DesktopApp(r"^AG Character & Weapon Studio$", budget_s=0)
    with pytest.raises(TesterTimeoutError, match="budget"):
        app._check_budget()
