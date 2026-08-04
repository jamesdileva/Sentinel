"""Deterministic language detection from file extensions."""

from collections import Counter
from pathlib import Path

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "shell",
    ".bat": "batch",
    ".ps1": "powershell",
}

# Extensions that never represent source code worth counting.
_IGNORED_EXTENSIONS = {".json", ".md", ".lock"}


def detect_language(path: str | Path) -> str:
    """Return the dominant programming language in a directory.

    Counts source files by extension (excluding common config/documentation
    formats and vendor directories). Falls back to "unknown".
    """
    counts: Counter[str] = Counter()
    root = Path(path)
    for file in root.rglob("*"):
        if file.is_dir() or file.suffix in _IGNORED_EXTENSIONS:
            continue
        language = EXTENSION_TO_LANGUAGE.get(file.suffix.lower())
        if language == "tsx":
            language = "typescript"
        elif language == "jsx":
            language = "javascript"
        if language:
            counts[language] += 1
    if not counts:
        return "unknown"
    return counts.most_common(1)[0][0]


def detect_language_of_file(path: str | Path) -> str | None:
    """Language for a single file path by extension."""
    return EXTENSION_TO_LANGUAGE.get(Path(path).suffix.lower())
