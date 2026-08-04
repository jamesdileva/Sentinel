"""Python parser — uses the stdlib `ast` module (deterministic)."""

import ast
from pathlib import Path

from app.parsers.base import BaseParser, ParsedFile


class PythonParser(BaseParser):
    """Extracts functions, classes, and imports from Python source."""

    def supported_languages(self) -> list[str]:
        return ["python"]

    def parse_file(self, file_path: str) -> ParsedFile:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ParsedFile(
            path=file_path,
            language="python",
            content=content,
            structure=self.extract_structure(content),
            dependencies=self.extract_imports(content),
        )

    def extract_structure(self, content: str) -> dict:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"error": "syntax_error"}
        return {
            "functions": [
                {
                    "name": node.name,
                    "line": node.lineno,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                }
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            "classes": [
                {
                    "name": node.name,
                    "line": node.lineno,
                    "bases": [ast.unparse(b) for b in node.bases],
                    "methods": [
                        m.name
                        for m in node.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                }
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
            ],
            "imports": self.extract_imports(content),
        }

    @staticmethod
    def extract_imports(content: str) -> list[str]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        return sorted(set(modules))
