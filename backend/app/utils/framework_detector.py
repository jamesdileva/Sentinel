"""Deterministic framework detection from config files and dependencies."""

import json
from pathlib import Path

_PYTHON_FRAMEWORKS: dict[str, list[str]] = {
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "streamlit": ["streamlit"],
    "langchain": ["langchain"],
    "celery": ["celery"],
    "pandas": ["pandas"],
}

_JS_FRAMEWORKS: dict[str, list[str]] = {
    "react": ["react", "react-dom", "next", "remix"],
    "electron": ["electron"],
    "express": ["express"],
    "vue": ["vue", "nuxt"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def _read_text_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def detect_framework(path: str | Path) -> str | None:
    """Detect the primary framework from package.json / pyproject.toml / requirements.

    Checks in priority order: package.json (JS projects), then Python manifests.
    """
    root = Path(path)
    package_json = root / "package.json"
    if package_json.exists():
        data = _read_json(package_json)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for framework, markers in _JS_FRAMEWORKS.items():
            if any(marker in deps for marker in markers):
                return framework
        return None

    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"
    if pyproject.exists() or requirements.exists():
        text = (
            "\n".join(_read_text_lines(pyproject))
            + "\n"
            + "\n".join(_read_text_lines(requirements)).lower()
        )
        for framework, markers in _PYTHON_FRAMEWORKS.items():
            if any(marker in text for marker in markers):
                return framework
    return None
