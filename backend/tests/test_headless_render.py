"""Unit tests for headless browser rendering (v1.17.13.1).

The Edge subprocess is mocked — no browser runs in the test suite.
"""

import subprocess

import pytest

from app.utils.headless_render import (
    HeadlessRenderError,
    find_edge,
    render_url,
)


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_find_edge_uses_known_install_path(monkeypatch, tmp_path):
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_bytes(b"MZ")
    monkeypatch.setattr("app.utils.headless_render.EDGE_CANDIDATES", (str(fake_edge),))
    assert find_edge() == str(fake_edge)


def test_find_edge_falls_back_to_path(monkeypatch):
    monkeypatch.setattr(
        "app.utils.headless_render.EDGE_CANDIDATES", (r"C:\no\edge.exe",)
    )
    monkeypatch.setattr(
        "app.utils.headless_render.shutil.which", lambda name: "C:/msedge.exe"
    )
    assert find_edge() == "C:/msedge.exe"


def test_find_edge_missing_raises(monkeypatch):
    monkeypatch.setattr(
        "app.utils.headless_render.EDGE_CANDIDATES", (r"C:\no\edge.exe",)
    )
    monkeypatch.setattr("app.utils.headless_render.shutil.which", lambda name: None)
    with pytest.raises(HeadlessRenderError):
        find_edge()


def test_render_url_success(monkeypatch, tmp_path):
    out = tmp_path / "shot.png"
    out.write_bytes(b"png")
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        return _FakeResult()

    monkeypatch.setattr("app.utils.headless_render.find_edge", lambda: "edge.exe")
    monkeypatch.setattr("app.utils.headless_render.subprocess.run", fake_run)
    assert render_url("http://127.0.0.1:8000/game", str(out)) == str(out)
    assert captured["cmd"][0] == "edge.exe"
    assert "--headless=new" in captured["cmd"]
    assert captured["cmd"][-1] == "http://127.0.0.1:8000/game"


def test_render_url_non_zero_exit_raises(monkeypatch, tmp_path):
    out = tmp_path / "shot.png"

    def fake_run(cmd, capture_output, text, timeout):
        return _FakeResult(returncode=3, stderr="boom")

    monkeypatch.setattr("app.utils.headless_render.find_edge", lambda: "edge.exe")
    monkeypatch.setattr("app.utils.headless_render.subprocess.run", fake_run)
    with pytest.raises(HeadlessRenderError, match="exited 3"):
        render_url("http://x", str(out))


def test_render_url_timeout_raises(monkeypatch, tmp_path):
    out = tmp_path / "shot.png"

    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr("app.utils.headless_render.find_edge", lambda: "edge.exe")
    monkeypatch.setattr("app.utils.headless_render.subprocess.run", fake_run)
    with pytest.raises(HeadlessRenderError, match="timed out"):
        render_url("http://x", str(out))


def test_render_url_missing_output_raises(monkeypatch, tmp_path):
    out = tmp_path / "shot.png"

    def fake_run(cmd, capture_output, text, timeout):
        return _FakeResult()

    monkeypatch.setattr("app.utils.headless_render.find_edge", lambda: "edge.exe")
    monkeypatch.setattr("app.utils.headless_render.subprocess.run", fake_run)
    with pytest.raises(HeadlessRenderError, match="no output"):
        render_url("http://x", str(out))
