"""Packaged-launcher detection tests (v1.17.13.5).

The detector is pure path logic — no DB, no subprocess, nothing real runs.
Matrix covers the electron-builder layouts (WorkFlow-Toolkit `release`,
TV-Scheduler `dist`), tauri layouts (deferred, but deterministic), and the
noise exclusions (installers, elevate, bundled pythons).
"""

from app.services.launcher_detect import find_packaged_launcher


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_release_win_unpacked_found(tmp_path):
    exe = _touch(tmp_path / "release" / "win-unpacked" / "WorkFlow Toolkit.exe")
    assert find_packaged_launcher(tmp_path) == exe


def test_dist_win_unpacked_found(tmp_path):
    exe = _touch(tmp_path / "dist" / "win-unpacked" / "TV Scheduler.exe")
    assert find_packaged_launcher(tmp_path) == exe


def test_tauri_out_found(tmp_path):
    exe = _touch(tmp_path / "out" / "sentinel.exe")
    assert find_packaged_launcher(tmp_path) == exe


def test_tauri_target_release_found(tmp_path):
    exe = _touch(tmp_path / "src-tauri" / "target" / "release" / "sentinel.exe")
    assert find_packaged_launcher(tmp_path) == exe


def test_prefers_win_unpacked_over_tauri(tmp_path):
    expected = _touch(tmp_path / "release" / "win-unpacked" / "App.exe")
    _touch(tmp_path / "out" / "App.exe")
    assert find_packaged_launcher(tmp_path) == expected


def test_skips_installer_and_helper_noise_inside_win_unpacked(tmp_path):
    _touch(tmp_path / "release" / "win-unpacked" / "App Setup 1.0.0.exe")
    _touch(tmp_path / "release" / "win-unpacked" / "elevate.exe")
    _touch(tmp_path / "release" / "win-unpacked" / "python.exe")
    _touch(tmp_path / "release" / "win-unpacked" / "pythonw.exe")
    _touch(tmp_path / "release" / "win-unpacked" / "venvlauncher.exe")
    expected = _touch(tmp_path / "release" / "win-unpacked" / "App.exe")
    assert find_packaged_launcher(tmp_path) == expected


def test_blockmap_never_matches(tmp_path):
    _touch(tmp_path / "release" / "win-unpacked" / "App.exe.blockmap")
    assert find_packaged_launcher(tmp_path) is None


def test_pyinstaller_dist_not_scanned(tmp_path):
    """v1.17.13.5 decision: PyInstaller `backend/dist` payload names are
    ambiguous (app.exe launchers) — browser capture covers those apps."""
    _touch(tmp_path / "backend" / "dist" / "dinner menu gen.exe")
    assert find_packaged_launcher(tmp_path) is None


def test_none_when_no_layouts(tmp_path):
    assert find_packaged_launcher(tmp_path) is None


def test_none_when_tree_missing():
    assert find_packaged_launcher("C:\\does\\not\\exist") is None


def test_sorted_first_exe_wins(tmp_path):
    first = _touch(tmp_path / "release" / "win-unpacked" / "Alpha.exe")
    _touch(tmp_path / "release" / "win-unpacked" / "Beta.exe")
    assert find_packaged_launcher(tmp_path) == first
