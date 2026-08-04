"""Deterministic build/test/start command discovery.

Returns the command map described in docs/02 §3.5:
{"install", "startup", "build", "test", "deploy"}.
"""

import json
from pathlib import Path

_COMMAND_KEYS = ("install", "startup", "build", "test", "deploy")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _from_package_json(root: Path) -> dict[str, str]:
    data = _read_json(root / "package.json")
    scripts: dict[str, str] = data.get("scripts", {}) or {}
    commands: dict[str, str] = {}
    if scripts:
        commands["install"] = "npm install"
        commands["startup"] = scripts.get("dev") or scripts.get("start") or ""
        commands["build"] = scripts.get("build") or ""
        commands["test"] = scripts.get("test") or ""
    return commands


def _from_pyproject_toml(root: Path) -> dict[str, str]:
    text = _read_text(root / "pyproject.toml")
    commands: dict[str, str] = {}
    has_pytest = "[tool.pytest.ini_options]" in text or "pytest" in text
    if has_pytest:
        commands["test"] = "pytest"
    return commands


def _from_requirements(root: Path) -> dict[str, str]:
    if (root / "requirements.txt").exists():
        return {"install": "pip install -r requirements.txt"}
    return {}


def extract_build_commands(path: str | Path) -> dict[str, str]:
    """Discover install/startup/build/test commands for a project."""
    root = Path(path)
    commands: dict[str, str] = {}
    for extractor in (_from_package_json, _from_pyproject_toml, _from_requirements):
        commands.update(extractor(root))

    if "install" not in commands:
        if (root / "pyproject.toml").exists():
            commands["install"] = "pip install -e ."
    return {key: commands.get(key, "") for key in _COMMAND_KEYS}
