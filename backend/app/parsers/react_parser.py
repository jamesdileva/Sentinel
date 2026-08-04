"""React parser — component/hook/JSX detection on top of TypeScriptParser.

Components are capitalized functions returning JSX or arrow functions whose
body contains JSX. Hooks are `useX` function calls (useState, useEffect, ...).
"""

import re
from pathlib import Path

from app.parsers.base import ParsedFile
from app.parsers.javascript_parser import TypeScriptParser, _strip_comments

_HOOK_RE = re.compile(r"""\buse[A-Z][\w$]*""")
_JSX_RE = re.compile(r"return\s*\(?\s*<[A-Za-z]", re.MULTILINE)
_JSX_ELEMENT_RE = re.compile(r"""<\s*([A-Z][\w$.]*)""")


class ReactParser(TypeScriptParser):
    """TS/TSX parser extended with React component, hook, and JSX extraction."""

    def supported_languages(self) -> list[str]:
        return ["jsx", "tsx", "react"]

    def parse_file(self, file_path: str) -> ParsedFile:
        parsed = super().parse_file(file_path)
        parsed.language = (
            "typescript" if Path(file_path).suffix in {".tsx", ".ts"} else "javascript"
        )
        return parsed

    def extract_structure(self, content: str) -> dict:
        structure = super().extract_structure(content)
        structure["components"] = self._extract_components(content)
        structure["hooks"] = self._extract_hooks(content)
        structure["jsx_elements"] = self._extract_jsx_elements(content)
        return structure

    @staticmethod
    def _extract_components(content: str) -> list[dict]:
        text = _strip_comments(content)
        components: list[dict] = []
        for name in re.findall(
            r"""(?:function|const)\s+([A-Z][\w$]*)\s*[=(\s]""", text
        ):
            if name not in {c["name"] for c in components}:
                components.append({"name": name})
        return components

    @staticmethod
    def _extract_hooks(content: str) -> list[str]:
        return sorted(set(_HOOK_RE.findall(content)))

    @staticmethod
    def _extract_jsx_elements(content: str) -> list[str]:
        return sorted(
            {m for m in _JSX_ELEMENT_RE.findall(content) if m != "React.Fragment"}
        )
