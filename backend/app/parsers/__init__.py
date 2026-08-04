"""Parser registry — routes a file to the right parser by language + framework."""

from pathlib import Path

from app.parsers.base import BaseParser, ParsedFile
from app.parsers.fastapi_parser import FastAPIParser, FlaskParser
from app.parsers.javascript_parser import JavaScriptParser, TypeScriptParser
from app.parsers.node_parser import NodeParser
from app.parsers.python_parser import PythonParser
from app.parsers.react_parser import ReactParser
from app.parsers.sql_parser import SQLParser

_PARSERS: dict[str, BaseParser] = {
    "python": PythonParser(),
    "javascript": JavaScriptParser(),
    "typescript": TypeScriptParser(),
    "jsx": ReactParser(),
    "tsx": ReactParser(),
    "json": NodeParser(),
    "sql": SQLParser(),
}


def parser_for_language(language: str) -> BaseParser | None:
    """Return the parser registered for an extension-based language name."""
    return _PARSERS.get(language)


def parse_file_for_project(
    file_path: str | Path, project_language: str, framework: str | None
) -> ParsedFile | None:
    """Parse a file, choosing framework-aware parsers where applicable."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".py":
        if framework == "fastapi":
            return FastAPIParser().parse_file(str(path))
        if framework == "flask":
            return FlaskParser().parse_file(str(path))
        return PythonParser().parse_file(str(path))
    if suffix in {".tsx", ".jsx"} or framework == "react" and suffix in {".ts", ".js"}:
        return ReactParser().parse_file(str(path))
    if suffix == ".ts":
        return TypeScriptParser().parse_file(str(path))
    if suffix == ".js":
        return JavaScriptParser().parse_file(str(path))
    if suffix == ".json" and path.name == "package.json":
        return NodeParser().parse_file(str(path))
    if suffix == ".sql":
        return SQLParser().parse_file(str(path))
    parser = parser_for_language(project_language)
    if parser is None:
        return None
    return parser.parse_file(str(path))


__all__ = [
    "BaseParser",
    "FastAPIParser",
    "FlaskParser",
    "JavaScriptParser",
    "NodeParser",
    "ParsedFile",
    "PythonParser",
    "ReactParser",
    "SQLParser",
    "TypeScriptParser",
    "parse_file_for_project",
    "parser_for_language",
]
