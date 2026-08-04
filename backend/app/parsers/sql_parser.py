"""SQL parser — extracts schema definitions and queries via regex."""

import re
from pathlib import Path

from app.parsers.base import BaseParser, ParsedFile

_CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["'`]?([\w.]+)["'`]?\s*\((.*?)\)""",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_RE = re.compile(
    r"""^\s*["'`]?(\w+)["'`]?\s+([A-Z]+(?:\(\d+(?:,\s*\d+)?\))?)""",
    re.IGNORECASE | re.MULTILINE,
)
_STATEMENT_RE = re.compile(
    r"""\b(SELECT|INSERT|UPDATE|DELETE|CREATE\s+INDEX|CREATE\s+VIEW|ALTER\s+TABLE)\b""",
    re.IGNORECASE,
)


class SQLParser(BaseParser):
    """Extracts CREATE TABLE schemas, columns, and top-level statement kinds."""

    def supported_languages(self) -> list[str]:
        return ["sql"]

    def parse_file(self, file_path: str) -> ParsedFile:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ParsedFile(
            path=file_path,
            language="sql",
            content=content,
            structure=self.extract_structure(content),
        )

    def extract_structure(self, content: str) -> dict:
        tables: list[dict] = []
        for match in _CREATE_TABLE_RE.finditer(content):
            table_name, body = match.group(1), match.group(2)
            columns = [
                {"name": c.group(1), "type": c.group(2).upper()}
                for c in _COLUMN_RE.finditer(body)
            ]
            tables.append({"name": table_name, "columns": columns})
        return {
            "tables": tables,
            "statements": sorted({s.upper() for s in _STATEMENT_RE.findall(content)}),
        }
