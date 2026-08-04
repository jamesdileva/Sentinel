"""JavaScript parser — deterministic regex-based structural extraction.

A full JS AST requires the Babel/Node toolchain; regex extraction keeps the
backend dependency-free while still surfacing imports, functions, classes,
and exports (see Sprint 3 deferral note in docs/03).
"""

import re
from pathlib import Path

from app.parsers.base import BaseParser, ParsedFile

_IMPORT_RE = re.compile(
    r"""^\s*import\s+(?:(?:[\w$*\s,{}+]+)\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_FUNCTION_RE = re.compile(
    r"""(?:function\s+([\w$]+)\s*\(|const\s+([\w$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|export\s+(?:default\s+)?(?:function\s+)?([\w$]+)\s*[=(])"""  # noqa: E501
)
_CLASS_RE = re.compile(r"""^\s*class\s+([\w$]+)""", re.MULTILINE)
_EXPORT_RE = re.compile(
    r"""^\s*export\s+(?:default\s+)?(?:class|function|const|let|var|interface|type)\s+([\w$]+)""",
    re.MULTILINE,
)
_COMMENT_STRIP_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)


def _strip_comments(content: str) -> str:
    return _COMMENT_STRIP_RE.sub("", content)


class JavaScriptParser(BaseParser):
    """Extracts imports, functions, classes, and exports from JS source."""

    def supported_languages(self) -> list[str]:
        return ["javascript"]

    def parse_file(self, file_path: str) -> ParsedFile:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ParsedFile(
            path=file_path,
            language="javascript",
            content=content,
            structure=self.extract_structure(content),
            dependencies=self.extract_dependencies(content),
        )

    @staticmethod
    def extract_dependencies(content: str) -> list[str]:
        text = _strip_comments(content)
        deps = _IMPORT_RE.findall(text) + _REQUIRE_RE.findall(text)
        return sorted(set(deps))

    def extract_structure(self, content: str) -> dict:
        text = _strip_comments(content)
        functions = sorted(
            {
                name
                for match in _FUNCTION_RE.finditer(text)
                for name in match.groups()
                if name
            }
        )
        classes = sorted(_CLASS_RE.findall(text))
        exports = sorted(_EXPORT_RE.findall(text))
        return {
            "functions": functions,
            "classes": classes,
            "exports": exports,
            "imports": sorted(set(_IMPORT_RE.findall(text))),
        }


class TypeScriptParser(JavaScriptParser):
    """JavaScript parser plus TS-specific declarations."""

    def supported_languages(self) -> list[str]:
        return ["typescript"]

    def parse_file(self, file_path: str) -> ParsedFile:
        parsed = super().parse_file(file_path)
        parsed.language = "typescript"
        return parsed

    def extract_structure(self, content: str) -> dict:
        structure = super().extract_structure(content)
        structure["interfaces"] = self._extract_interfaces(content)
        structure["type_aliases"] = self._extract_type_aliases(content)
        return structure

    @staticmethod
    def _extract_interfaces(content: str) -> list[str]:
        return sorted(
            re.findall(
                r"""^\s*(?:export\s+)?interface\s+([\w$]+)""", content, re.MULTILINE
            )
        )

    @staticmethod
    def _extract_type_aliases(content: str) -> list[str]:
        return sorted(
            re.findall(
                r"""^\s*(?:export\s+)?type\s+([\w$]+)\s*=""", content, re.MULTILINE
            )
        )
